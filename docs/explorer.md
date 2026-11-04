# Authenticated event investigation

Install `docs/sql/investigation.sql` after application migrations, with `ON_ERROR_STOP` enabled. It creates read-only relational views for projects, reports, issues, ordered frames, breadcrumbs, logs, attachment metadata and sessions. These views do not decode archive payloads and are not a tenant authorization boundary.

Use database-owner access to install the views. Restrict the Explorer analytics role to the required schemas/views and revoke access to project ingestion keys and archive payloads. In Metabase, apply collection/database permissions for the intended operators; project filters provide analysis scope, not authorization. Do not publicly share diagnostic cards or dashboards.

After synchronizing database metadata, run `python3 scripts/provision_explorer.py --project <id> --database <id> --event-details` with `METABASE_URL` and operator credentials in the private environment. Re-running preserves managed object IDs and refuses unmanaged or publicly shared objects. The provisioner creates the investigation dashboards and optional exact-event stack/context panels. Attachments are metadata only at this stage; there is no binary evidence endpoint.

Compare issue occurrences after applying project/time filters to reports; lifetime issue totals must not be filtered by last-seen time to infer period counts. Order frames by position and breadcrumbs by chronology. Log correlation requires the same project and an exact nonzero trace ID. Missing frames, identities or logs remain missing rather than being inferred from nearby events.
