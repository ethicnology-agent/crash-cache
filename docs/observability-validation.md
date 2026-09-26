# Observability validation — September 26, 2026

The bounded laboratory test confirmed event and session idempotence, queryable installation counts, device/session correlation and six functioning Metabase questions. These measurements describe this workload and environment. They are not production capacity, mobile SDK overhead, game performance or native symbolication benchmarks.

## Tested identity and environment

| Item | Recorded value |
|---|---|
| Backend source | `1e420da` plus the uncommitted observability working-tree changes under review |
| Benchmark harness SHA-256 | `bedab6300a22baa69acdc20b0be33bab9153a18ea36b04fce09a79edcb84a4e7` |
| Host | Mac mini M4, 24 GiB RAM |
| Container runtime | Podman 6.1.2, Linux VM allocated 6 CPUs and 8 GiB RAM |
| Request path | Host loopback to the containerized laboratory |
| Measured database | PostgreSQL 16.15 (`postgres:16-alpine`) |
| Symbolicator present | 26.9.0; this HTTP ingestion workload did not benchmark it |
| Metabase | 0.63.18 |
| Backend build mode | Release, built with `cargo build --locked --release -j 1` in the pinned Rust 1.93 Docker builder |
| Workload | 100 distinct synthetic events, five direct event retries, three session initializations, six additional mixed/reordered/retried session cases |
| Concurrency | Four concurrent requests for the distinct-event batch |
| Warmup | Three session initialization requests before the event batch |
| Repetitions | One run per rate-limit configuration |
| Request timeout | 10 seconds |

The measured existing laboratory used PostgreSQL 16.15. The separately maintained optional deployment pins PostgreSQL 18.6; its version must not be substituted into this evidence. A source base plus a dirty working tree is less precise than a committed source or binary checksum. The HTTP measurements used local release image `sha256:d806b1da58fb779d3a6802548f5f9b849685f22f5bc36470da2b0b260cb87b32`. The subsequent compressed Crashpad multipart correction is included in source commit `d774d58` and local release image `sha256:2bf42fb4e6e5a2a19ec2c10dcb6ed85be087efb0e5b21268b6338cc6f40bd4e7`; the earlier latency numbers are not a second benchmark of that corrected image. These are laboratory image identities, not published release artifacts.

## HTTP acknowledgement measurements

The first run exercised the existing per-IP limiter. It returned 60 HTTP 200 responses and 54 HTTP 429 responses out of 114 requests. This demonstrates rate-limit behavior; it is not a successful end-to-end ingestion benchmark or a backend saturation point. The run started at 15:08:23 UTC.

The second run, after the laboratory rate-limit override, acknowledged all 114 requests successfully. It started at 15:09:57 UTC. The following figures include the caller, network path and scheduler. Three initialization requests warm the distinct-event batch but remain part of the all-request measurements.

| Measurement | Rate-limited run | Run with laboratory override |
|---|---:|---:|
| Requests | 114 | 114 |
| HTTP 200 | 60 | 114 |
| HTTP 429 | 54 | 0 |
| Failed or invalid acknowledgements | 54 | 0 |
| Complete harness elapsed time | 0.278 s | 0.281 s |
| Distinct-event batch elapsed time | 0.180 s | 0.182 s |
| All-request latency p50 | 6.305 ms | 6.443 ms |
| All-request latency p95 | 12.575 ms | 12.185 ms |
| All-request latency p99 | 18.103 ms | 19.055 ms |
| All-request maximum | 27.668 ms | 22.552 ms |
| Distinct-event latency p50 | 6.386 ms | 6.475 ms |
| Distinct-event latency p95 | 8.703 ms | 8.768 ms |
| Distinct-event latency p99 | 18.071 ms | 18.977 ms |
| Distinct-event maximum | 18.103 ms | 19.055 ms |
| Request bytes sent | 54,692 | 54,595 |
| Uncompressed payload bytes | 70,636 | 70,636 |

The successful 100-event batch produced approximately 548 acknowledgements per second during its 0.182-second burst. This short quotient is not sustainable throughput. There was no steady-state saturation search, long soak, representative production network, repeated statistical trial or concurrent native symbolication load. The rate-limited latency distribution includes rejections; it must not be interpreted as successful-ingestion latency.

An HTTP 200 response proves acknowledgement only. Database verification after queue processing established the following separately; no digest-completion latency was captured.

## Persisted state after the successful run

| Database assertion | Observed |
|---|---:|
| Reports | 100 |
| Distinct event IDs | 100 |
| Issues | 1 |
| Issue occurrence count | 100 |
| Sessions | 3 |
| Distinct installation hashes among those sessions | 3 |
| Pending archives belonging to this run | 0 |
| Queue errors belonging to this run | 0 |

Final session states were exactly `ok` at sequence `0`, `exited` at sequence `2`, and `crashed` at sequence `2`. Older sequence-1 updates and duplicate terminal updates did not replace the final states. An already-known event carrying a newer crashed session preserved that session update without adding an event or issue occurrence. This verifies the expected database result for the controlled retry/reordering workload rather than relying on HTTP status alone.

Focused regression evidence also covered an existing terminal session surviving schema migration and a malformed historical timestamp causing an explicit migration error. The duplicate-event/session regression failed before its fix and passed after the event work moved into a nested transaction, preserving the outer session update. These are bounded correctness proofs, not a claim of full Sentry protocol compatibility.

## Metabase and access verification

The provisioner ran twice against the same instance and retained the same database, dashboard and six question identities. Each question was then executed through the real Metabase API with the selected test project and the half-open UTC date range September 26–27, 2026. All six returned `completed`. Counts include the controlled application tests as well as synthetic inputs; they are not a production population.

| Question | Result rows | Single API round-trip time |
|---|---:|---:|
| Session starts and installations | 3 | 16.72 ms |
| Observed active installations | 3 | 15.67 ms |
| Release health | 3 | 17.97 ms |
| Platforms, systems and devices | 1 | 19.68 ms |
| Errors by runtime and component | 7 | 17.56 ms |
| Duplicate cross-layer captures | 0 | 15.88 ms |

These are individual API timings captured at 15:18:12 UTC, not percentiles or browser rendering measurements. No dashboard interaction or chart rendering latency was measured. An empty duplicate-capture question is expected when no matching repeated logical error identifier exists; event-ID uniqueness and issue counts were checked independently above.

The query connection identified itself as `metabase_readonly`. Privilege inspection confirmed that it was not a superuser, could not create database/schema objects, could select all application tables and had no table-level INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER or REFERENCES privilege. This was verified through read-only catalog queries; no write was attempted.

The device question initially failed to correlate the application's compact 32-hex session tag with the backend's canonical hyphenated UUID. On the same eight observations, the original comparison correlated zero and the corrected comparison correlated all eight. The final question reported one installation, two correlated sessions and zero uncorrelated observations. The comparison validates the accepted UUID forms while preserving both project and installation checks; stored tags are not rewritten.

The [read-only UUID correlation regression](sql/session-correlation-check.sql) returned zero failures across eight cases: compact, hyphenated and uppercase UUIDs matched; different projects, different installations, missing installation identities and malformed UUID inputs did not.

## Reproduce and interpret

Use a disposable project and private environment variables. Keep the DSN, database password, admin credentials, local connection information, raw dumps and raw envelopes outside Git. Start or reuse an isolated stack according to the [laboratory guide](../deploy/observability/README.md), record its actual versions/build mode, then run the maintained harness:

```sh
python3 scripts/benchmark_sentry.py \
  --events 100 --concurrency 4 --retries 5 --timeout 10 \
  --revision "$BACKEND_REVISION" --output "$BENCHMARK_REPORT"
```

`CRASH_CACHE_DSN` is read from the private environment. Use a fresh run identity for an independent trial. Retain the first rate-limit response distribution; if a laboratory override is used for compatibility testing, record it explicitly and do not silently call it a production recommendation. After queue processing, compare reports, issue occurrence count, exact session sequences/statuses and queue state with the generated report's `expected_after_digest`. Do not assume that the harness's initially unverified expected counts are measurements.

Run `python3 scripts/provision_metabase.py` twice with the operator environment described in the laboratory guide. Confirm stable object identities and completion of all six questions. Use the maintained SQL directly when diagnosing results:

```sh
psql "$DATABASE_URL" -v project_id="$PROJECT_ID" \
  -v from="$FROM_TIMESTAMP" -v until="$UNTIL_TIMESTAMP" \
  -f docs/sql/observability.sql
psql "$DATABASE_URL" -f docs/sql/session-correlation-check.sql
```

Use a SELECT-only connection for these commands. The second query must return zero failure rows. The client must emit the documented foreground observations before active-installation counts are meaningful. See [application-session and activity semantics](observability.md) for date-boundary behavior, missing observations and installation-versus-person limitations.

No measurements in this report establish smartphone CPU/memory/battery overhead, a production ingestion capacity, complete Sentry server parity, exact player counts or graphical cross-platform application behavior. The bounded native crash evidence below establishes one resolved function, not complete symbol coverage; broader claims require their own identified artifacts and representative tests.

## Real SDK transport compatibility

A Linux Crashpad client sends a gzip-compressed multipart body, including a roughly 13 MiB native minidump. The initial implementation accepted a plain 3 MiB multipart request but rejected compressed multipart with HTTP 400. Three focused router regressions established this distinction. After bounded decompression before multipart parsing, both supported requests pass and a decompressed payload above the configured limit returns HTTP 413. At that stage, the ordinary Rust suite passed 46 tests, and six explicitly enabled PostgreSQL migration/replay and Symbolicator integration tests passed against isolated services.


Crashpad also supplies SDK scope metadata as MessagePack. A focused regression failed because the backend generated a replacement event identity instead of preserving the one in the MessagePack payload. After decoding that metadata, the same regression passed, together with malformed/ambiguous metadata rejection and the compressed multipart size-limit tests. The subsequent ordinary suite recorded 48 passed and zero failed. Six opt-in integration tests were ignored in that run; their earlier isolated execution is separate evidence, not an additional execution of the updated code.

## Linux ARM64 native crash and classification

Read-only database verification at 16:10 UTC confirmed the controlled Godot 4.7.2 Linux ARM64 run and its subsequent native crash. These were headless functional tests inside the laboratory Linux VM, not a desktop graphics, smartphone or gameplay performance measurement.

| Controlled capture | Stored layer | Stored component | Reports |
|---|---|---|---:|
| Godot handled error | `godot` | `diagnostics` | 1 |
| Rust handled error | `rust` | `diagnostics` | 1 |
| Rust caught panic | `rust` | `diagnostics` | 1 |
| Rust storage failure | `rust` | `storage` | 1 |
| Native null-pointer crash | `native` | `runtime` | 1 |

All four nonfatal reports had one shared installation identity, with no missing identity, and the native crash matched that same installation. Every report recorded Linux with kernel version `7.1.10` and the SDK runtime `native`; the layer/component tags distinguish Godot, Rust and native failures despite their common SDK runtime. These counts establish receipt of each controlled capture once in this selected run, not the absence of duplicate reporting for every possible failure path.

The native report preserved the `native_crash` classification and the `SIGSEGV / SEGV_MAPERR / 0x0` exception. Its stored Symbolicator result was `partial`, with exactly one resolved frame: `sentry::SentryBadCode::crash_with_null_dereference()`. This proves that the actual SDK minidump travelled through ingestion and symbolication to a persisted named function. It does not establish a fully symbolicated stack, source-line coverage, crash-free session accounting, native crash coverage on every supported OS, or symbolication throughput/latency. No new networking, FPS, memory or SDK-overhead measurements accompanied this verification.

## Dashboard visualization follow-up

The same dashboard now includes eight overview questions (three numeric indicators and five charts) followed by the original six verification tables. Hourly foreground observations and session starts use the recorded timestamps. Session outcomes remain separated into exited, crashed, abnormal, unhandled and open states. The device chart shows installations per device/system/app-version grouping, not a sum of unique people. No synthetic history was added to make the charts look populated.

All fourteen questions completed against the real read-only source after provisioning. The existing six question IDs and the dashboard/public-link identity were preserved. A further provisioning run retained all fourteen question IDs and all fifteen dashboard tile IDs, including the laboratory note. Unauthenticated browser rendering was inspected at 1440-pixel desktop and 412-pixel mobile widths using Chrome headless 153.0.8010.12. Panels stacked on mobile without document-level horizontal overflow; detailed tables retain their own scrolling. These checks validate the tested laboratory dashboard, not all browser/platform combinations.


## Rich telemetry and guided investigation follow-up

The September 26 laboratory deployment added typed Sentry log ingestion and attachment metadata while retaining the original compressed envelope or multipart bytes. Replaying the same valid standalone log envelope twice returned HTTP 200 both times and stored one log. Different envelopes are not assumed to contain duplicate log occurrences. Mixed session/log envelopes and opaque Crashpad multipart attachments have focused regression coverage. Existing historical archives were not backfilled; zero indexed attachments can mean that an older archive predates this extraction.

Godot Android exceptions can reference a stack through `exception.thread_id` and `threads.values`. Missing exception stacks are now filled only from an unambiguous matching thread; explicit exception stacks retain precedence. The regression failed with that resolver disconnected and passed after restoration. An actual Pixel 6a script-error receipt subsequently stored local variables from the matching thread stack; source context was absent. This backend result does not establish successful Godot screenshot capture.

The final ordinary Rust test run passed 53 tests. Twelve explicitly enabled tests also passed against isolated PostgreSQL and Symbolicator services, including six rich-telemetry tests, migration rollback/reapply and replay checks. The laboratory image `0142428afaa8847d813e557f296d0b1c12610fd069b307a936c5225755b339d8` was built incrementally from an existing dependency builder and deployed with a successful health response; this is not a clean Docker build claim.

The dashboard layout now separates five views: Overview (8 questions), Diagnostic quality (6), Collection (8), Error investigation (4), and Data tables (6). The original tables moved out of the overview. Navigation retains the existing overview public link, and repeated navigation provisioning preserved all 32 question identities and tile layouts. Sixteen Python contract tests passed, and 33 read-only SQL fixture contracts passed against PostgreSQL, including a non-UTC connection timezone and combined detail filters.

A real browser click on the Pixel 6a device bar opened the investigation dashboard with the selected device, project and date range. Detail filters cover capture layer, application version and device model. The shared investigation contains bounded metadata summaries, not raw error messages, variables or source contents. Custom public URL navigation is intentional because unauthenticated Metabase dashboards do not provide the full authenticated drill-through experience. Section navigation uses each destination's default period; only the configured chart drill-through carries the selected period and project.

Public rendering was inspected at desktop and 412-pixel mobile widths; the tested layouts stacked without document-level horizontal overflow. These are laboratory views over injected test data, not production activity. Active installation counts are not identifiable people, session-owner differences remain documented, and the charts do not establish complete Sentry protocol parity or healthy collection when evidence is absent.
