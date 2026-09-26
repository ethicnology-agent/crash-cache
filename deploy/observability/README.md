# Observability laboratory

This opt-in Compose deployment isolates the compatibility laboratory from the existing root Compose stack. It runs PostgreSQL, crash-cache, Symbolicator and a private HTTP symbol source. The additional `dashboards` profile runs Metabase. Do not point it at an existing deployment's database volume. There are no fixed container names, so a distinct Compose project name isolates networks and volumes.

The definitions use the Compose specification and can be run with Docker Compose or `podman compose` with a compatible provider. Linux can run Podman directly; macOS needs an existing running Podman machine with sufficient memory and disk. Provisioning dashboards uses only Python 3's standard library and runs on both systems. Neither Compose syntax nor this script establishes that a particular host/runtime combination has been tested.

## Configure and start

From the repository root, copy `deploy/observability/.env.example` to `deploy/observability/.env`, restrict it to the operator, and populate the four independent passwords. Generate hexadecimal values with `openssl rand -hex 32`; using hex also avoids URI-encoding ambiguity in the application database URL. The populated `.env` is ignored by Git. Do not publish expanded `compose config` output, container inspection output or environment dumps: they contain credentials.

Set `SYMBOLS_DIRECTORY` to an existing absolute directory holding matching build artifacts and `SYMBOLICATOR_SOURCES_FILE` to an existing absolute private JSON file copied from `sources.example.json`. The example uses an internal HTTP source and the `native` layout. For ELF, place matching debug files at `.build-id/<first-two-build-id-hex>/<remaining-build-id-hex>.debug` under the symbols directory. The source URL includes `.build-id/` because Symbolicator appends only the remaining build-ID path. Keep symbols readable by the unprivileged static-file container. Never substitute symbols from a different build. Adding an image or library without its matching symbols does not establish symbolication.

```sh
podman compose --env-file deploy/observability/.env \
  -f deploy/observability/compose.yml -p crash-cache-observability \
  --profile observability up -d --build
```

Add `--profile dashboards` before `up` to include Metabase. The Compose provider must support profiles, conditional `depends_on`, environment-variable requirements and resource limits. On an SELinux-enforcing Linux host, configure appropriate labels for these dedicated bind mounts; do not disable SELinux globally or relabel unrelated shared directories.

The ingestion endpoint and dashboard are published only on loopback. PostgreSQL, Symbolicator and the symbol HTTP server have no published host ports. Access a remote laboratory through a deliberate authenticated tunnel; do not expose an unauthenticated symbol server or dashboard setup endpoint publicly. Symbolicator allows private-address sources so it can reach the internal static server; source definitions are operator-owned, never supplied by events. This relaxes Symbolicator's destination restriction only within this trusted laboratory deployment: keep its API reachable exclusively by crash-cache on the private network and retain operator-only control of the sources file. Without `connect_to_reserved_ips: true`, a correct build-ID path can still fail with `destination is restricted`; that is a source-access failure, not proof of missing symbols. After correcting an access failure, account for cached download failures when repeating the verification.

The database initialization script runs only on the first initialization of the dedicated volume. It creates a migration-capable application role, a separate Metabase application-database role and a SELECT-only analytics role with default privileges on future application tables. Changing passwords in `.env` does not rotate existing database roles. Rotate credentials deliberately rather than deleting the volume to make startup succeed.

The configured memory ceilings total approximately 3.7 GiB without dashboards and 4.7 GiB with dashboards; these are limits, not measured usage or minimum host requirements. Build memory is separate. The application payload ceilings are laboratory settings suitable for native dump testing, not a proven production sizing recommendation.

## Provision the dashboard

Set these variables in a private operator environment, using the running instance and a project already created through `crash-cache project create`:

```text
METABASE_URL
METABASE_ADMIN_EMAIL
METABASE_ADMIN_PASSWORD
METABASE_READONLY_PASSWORD
CRASH_CACHE_PROJECT_ID
```

`METABASE_SOURCE_HOST` defaults to the Compose service `postgres`, and `METABASE_SOURCE_PORT` to `5432`. These are resolved from inside Metabase, not from the machine running the script. Optional `OBSERVABILITY_FROM` and `OBSERVABILITY_UNTIL` are ISO dates, with the latter exclusive; defaults cover the previous 30 days through tomorrow. Use an admin password satisfying the instance's password policy. No credentials are command-line arguments.

```sh
python3 scripts/provision_metabase.py
```

On a fresh instance the script performs initial setup with usage tracking disabled. On an initialized instance it logs in with the supplied credentials. It creates or updates a dedicated read-only PostgreSQL connection, a managed collection, fourteen parameterized questions and a dashboard with project and date filters. It executes every question before reporting the dashboard URL, then ends its API session. Re-running updates those same objects; an unmanaged name collision or ambiguous duplicate causes a clear failure instead of overwriting unrelated work. Do not add manual cards to this managed dashboard because reprovisioning restores its maintained overview-and-detail layout. Duplicate it first for local customization.

Metabase's database-creation endpoint does not persist `description`; the script marks the newly returned database ID using a separate update. If execution stops between those two requests, inspect the source's identity and connection details. Only after confirming that it is this script's interrupted creation, supply `METABASE_ADOPT_DATABASE_ID` with that exact ID for one recovery run. Adoption checks the expected name, engine, connection and blank/managed description. Remove the override afterward. A matching name alone never establishes ownership.

The overview contains three numeric indicators, hourly activity and session charts, stacked session outcomes, error volume by capture layer and horizontal device bars. A visible note identifies controlled laboratory data; the six verification tables remain below the charts. The responsive Metabase layout stacks the panels on narrow screens. Chart definitions live in `scripts/dashboard_charts.py` and reuse the maintained SQL semantics. Whole-period active installations use a distinct count rather than adding daily distinct counts. Release-build suffixes are collapsed only for the outcome visualization, where session counts are additive; the detailed release table preserves the original values.

Questions cover session starts, observed active installations, release health, platform/system/device distribution, errors by runtime/component and duplicate cross-layer captures. Empty results are legitimate before observations arrive. See [measurement semantics and required client observations](../../docs/observability.md). SDK runtime (`platform`, such as `dart` or `native`) is different from operating system (`contexts.os.name`, such as Linux or macOS); the dashboard exposes both. Heartbeats and crash recovery must be verified in the application separately.

The script targets Metabase **0.63.18**. It uses the [official API](https://www.metabase.com/docs/latest/api) and [native SQL parameters](https://www.metabase.com/docs/latest/questions/native-editor/sql-parameters). Dashboard creation uses `PUT /api/dashboard/:id` with `dashcards`, not the deprecated cards endpoint. The laboratory owner must validate the script against the running pinned image and run it twice to verify idempotence; static checks alone are not deployment evidence.

## Versions and lifecycle

Images are pinned to Symbolicator 26.9.0, PostgreSQL 18.6, Python 3.14.7 and Metabase 0.63.18. Patch tags are explicit but not immutable digests; record resolved image digests with runtime measurements. The existing Rust 1.93 builder is retained: reqwest 0.13.5 declares Rust 1.85 and the checked Linux dependency manifests do not require a version above 1.93. Host testing on another Rust version does not prove the container build. The Dockerfile now builds with `--locked` so deployment cannot silently resolve a different dependency set.

Stop the project with the same Compose file, environment, project name and profiles followed by `down`. Named volumes remain. Do not add `--volumes` unless intentionally deleting the laboratory's database and symbol cache. Keep database exports, raw envelopes, dumps, symbols and operational credentials outside Git. No lifecycle command here operates the separate existing root Compose deployment.
