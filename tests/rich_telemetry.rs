use axum::{body::Body, http::{Request, StatusCode}, Router};
use crash_cache::features::{digest::DigestReportUseCase, ingest::{AppState, HealthStats, ProjectCache, IngestReportUseCase, create_api_router}};
use crash_cache::shared::{compression::GzipCompressor, persistence::{DbPool, Repositories, establish_connection_pool, run_migrations}};
use diesel::{prelude::*, sql_types::{BigInt, Integer}};
use serde_json::{Value, json};
use std::sync::{Arc, RwLock};
use std::time::Duration;
use tokio::sync::Semaphore;
use tower::ServiceExt;

fn setup() -> (Router, DbPool, Repositories, i32) {
    let url = std::env::var("DATABASE_URL").expect("isolated DATABASE_URL required");
    assert!(url.contains("crash_cache_test"));
    let pool = establish_connection_pool(&url, 4, 10);
    run_migrations(&pool);
    let repos = Repositories::new(pool.clone());
    let project = repos.project.create(None, None).unwrap();
    let state = AppState {
        ingest_use_case: IngestReportUseCase::new(repos.archive.clone(), repos.queue.clone(), repos.project.clone()),
        compression_semaphore: Arc::new(Semaphore::new(1)), pool: pool.clone(),
        project_repo: repos.project.clone(), project_cache: ProjectCache::new(Duration::from_secs(1)),
        health_cache: Arc::new(RwLock::new(HealthStats::default())), health_cache_ttl: Duration::from_secs(1),
        max_uncompressed_payload_bytes: 4 * 1024 * 1024, session_repo: repos.session.clone(),
        session_status_repo: repos.session_status.clone(), session_release_repo: repos.session_release.clone(),
        session_environment_repo: repos.session_environment.clone(),
    };
    (create_api_router(state), pool, repos, project)
}

fn envelope(header: Value, items: Vec<(Value, Vec<u8>)>) -> Vec<u8> {
    let mut bytes = format!("{header}\n").into_bytes();
    for (mut header, payload) in items {
        header["length"] = json!(payload.len());
        bytes.extend_from_slice(format!("{header}\n").as_bytes());
        bytes.extend_from_slice(&payload);
        bytes.push(b'\n');
    }
    bytes
}
fn log() -> Value {
    json!({"timestamp":1790424000.125,"trace_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","span_id":"bbbbbbbbbbbbbbbb","level":"info","body":"map loaded","severity_number":9,"attributes":{"layer":{"type":"string","value":"flutter"},"piece_count":{"type":"integer","value":12},"modes":{"type":"array","value":["creative","test"]}}})
}
fn logs(values: Vec<Value>) -> (Value,Vec<u8>) {
    (json!({"type":"log","item_count":values.len(),"content_type":"application/vnd.sentry.items.log+json"}), serde_json::to_vec(&json!({"items":values})).unwrap())
}
async fn send(router: &Router, project: i32, body: Vec<u8>) -> StatusCode {
    router.clone().oneshot(Request::builder().method("POST")
        .uri(format!("/api/{project}/envelope/?sentry_key=test"))
        .body(Body::from(body)).unwrap()).await.unwrap().status()
}
fn count(pool: &DbPool, project: i32, table: &str) -> i64 {
    #[derive(QueryableByName)] struct Count { #[diesel(sql_type = BigInt)] value: i64 }
    diesel::sql_query(format!("SELECT count(*) AS value FROM {table} WHERE project_id=$1"))
        .bind::<Integer,_>(project).get_result::<Count>(&mut pool.get().unwrap()).unwrap().value
}
fn digest(pool: &DbPool, repos: &Repositories) {
    DigestReportUseCase::new(repos.clone(), pool.clone(), GzipCompressor::new()).process_batch(1000).unwrap();
}

#[tokio::test]
#[ignore = "requires isolated PostgreSQL DATABASE_URL"]
async fn rich_logs_are_not_errors_and_exact_retries_are_idempotent() {
    let (router,pool,repos,project) = setup();
    let batch = envelope(json!({}),vec![logs(vec![log(),log()])]);
    for _ in 0..2 { assert_eq!(send(&router,project,batch.clone()).await,StatusCode::OK); digest(&pool,&repos); }
    assert_eq!(count(&pool,project,"telemetry_log"),2,"identical entries in one batch are distinct occurrences");
    assert_eq!(count(&pool,project,"report"),0,"logs must not manufacture error events");
    let other_project = repos.project.create(None,None).unwrap();
    assert_eq!(send(&router,other_project,batch).await,StatusCode::OK); digest(&pool,&repos);
    assert_eq!(count(&pool,other_project,"telemetry_log"),2);
    let another_batch = envelope(json!({"sent_at":"2026-09-26T12:01:00Z"}),vec![logs(vec![log()])]);
    assert_eq!(send(&router,project,another_batch).await,StatusCode::OK); digest(&pool,&repos);
    assert_eq!(count(&pool,project,"telemetry_log"),3,"a new envelope must not heuristically discard identical log content");
}

#[tokio::test]
#[ignore = "requires isolated PostgreSQL DATABASE_URL"]
async fn rich_mixed_sessions_logs_and_invalid_batches_are_atomic() {
    let (router,pool,repos,project) = setup();
    let sid = uuid::Uuid::new_v4().to_string();
    let session = json!({"sid":sid,"did":"synthetic-installation","init":true,"seq":1,"started":"2026-09-26T12:00:00Z","status":"ok","errors":0,"attrs":{"release":"test@1"}});
    let session_item = || (json!({"type":"session"}),serde_json::to_vec(&session).unwrap());
    let bad = envelope(json!({}),vec![session_item(),logs(vec![log(),json!({"body":"missing required fields"})])]);
    assert_eq!(send(&router,project,bad).await,StatusCode::BAD_REQUEST);
    assert_eq!(count(&pool,project,"session"),0);
    assert_eq!(count(&pool,project,"archive"),0,"invalid batch must not be partially admitted");
    let good = envelope(json!({}),vec![session_item(),logs(vec![log()])]);
    assert_eq!(send(&router,project,good).await,StatusCode::OK); digest(&pool,&repos);
    assert_eq!(count(&pool,project,"session"),1);
    assert_eq!(count(&pool,project,"telemetry_log"),1);
    assert_eq!(count(&pool,project,"report"),0);
}

