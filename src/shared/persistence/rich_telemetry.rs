//! Queryable log records and attachment metadata; payload bytes stay in archives.
use diesel::{RunQueryDsl, sql_query, sql_types::{Double, Integer, Jsonb, Nullable, Text}};
use crate::shared::{domain::DomainError, parser::{Envelope, sentry_log::parse_logs}};
use super::DbConnection;

pub fn store_envelope_context(conn: &mut DbConnection, project_id: i32, archive_hash: &str, envelope: &Envelope) -> Result<(), DomainError> {
    for (item_index, log_index, log) in parse_logs(envelope)? {
        sql_query("INSERT INTO telemetry_log (project_id,archive_hash,item_index,log_index,timestamp,trace_id,span_id,level,body,severity_number,attributes) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT (archive_hash,item_index,log_index) DO NOTHING")
            .bind::<Integer,_>(project_id).bind::<Text,_>(archive_hash).bind::<Integer,_>(item_index as i32).bind::<Integer,_>(log_index as i32)
            .bind::<Double,_>(log.timestamp).bind::<Nullable<Text>,_>(log.trace_id)
            .bind::<Nullable<Text>,_>(log.span_id).bind::<Text,_>(log.level)
            .bind::<Text,_>(log.body).bind::<Nullable<Integer>,_>(log.severity_number)
            .bind::<Jsonb,_>(log.attributes).execute(conn)?;
    }
    Ok(())
}
