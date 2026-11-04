# Authenticated event investigation

Install `docs/sql/investigation.sql` after application migrations, with `ON_ERROR_STOP` enabled. It creates read-only relational views for projects, reports, issues, ordered frames, breadcrumbs, logs, attachment metadata and sessions. These views do not decode archive payloads and are not a tenant authorization boundary.

Use database-owner access to install the views. Restrict the Explorer analytics role to the required schemas/views and revoke access to project ingestion keys and archive payloads. In Metabase, apply collection/database permissions for the intended operators; project filters provide analysis scope, not authorization. Do not publicly share diagnostic cards or dashboards.

After synchronizing database metadata, run `python3 scripts/provision_explorer.py --project <id> --database <id> --event-details` with `METABASE_URL` and operator credentials in the private environment. Re-running preserves managed object IDs and refuses unmanaged or publicly shared objects. The provisioner creates the investigation dashboards and optional exact-event stack/context panels. Attachments are metadata only at this stage; there is no binary evidence endpoint.

Compare issue occurrences after applying project/time filters to reports; lifetime issue totals must not be filtered by last-seen time to infer period counts. Order frames by position and breadcrumbs by chronology. Log correlation requires the same project and an exact nonzero trace ID. Missing frames, identities or logs remain missing rather than being inferred from nearby events.

## Activity and period comparisons

The additional Usage questions count explicit `app_session`/`app_activity` observations and recorded session starts. They do not establish people, store downloads or concurrent users. Installations require consistent pseudonymous identity on events and sessions. System correlation requires matching project, identity and canonical session UUID; unmatched rows remain unknown.

Periods use continuous selected UTC calendar days within 2000–2100. Previous-period comparisons use an equal UTC duration; zero previous counts leave percentage change undefined. Coverage panels distinguish absent telemetry from known zero observations. Day/week/month counts are distinct within each bucket and must not be summed into a larger-period unique count. Re-run provisioning to add the Usage questions and named project/date selectors.

## Guided navigation

Overview, Usage and Errors share project and period scope. Problem rows link to filtered occurrences, and event rows link to the selected stack/context. Primary navigation carries relative date selections and the active project. Tabs distinguish captured stacks, breadcrumbs/logs, files and context. Files still list metadata only.

Provisioning preserves existing tab IDs as well as card/dashboard IDs. Test re-provisioning against the actual supported Metabase version before rollout. Responsive arrangements prioritize summary figures before navigation; wide diagnostic tables can still require horizontal scrolling. Synthetic fixtures can exercise empty, partial and larger problem lists without importing production data.
