# Observability deployment

This optional Compose project runs PostgreSQL, crash-cache and Metabase. It does not include native crash processing, Symbolicator or a symbol server. Use a distinct Compose project name and fresh dedicated volumes; do not point it at existing deployment data.

Copy `.env.example` to a private `.env` in this directory and set four independent hexadecimal passwords. Generate each with `openssl rand -hex 32`; hexadecimal also avoids URI escaping in the database URL. Never commit the populated file or expanded Compose output. All published ports bind to loopback. PostgreSQL has no published network port.

```sh
docker compose --env-file deploy/observability/.env -f deploy/observability/compose.yml -p crash-cache-observability --profile observability --profile dashboards up -d --build
```

Create a project using `crash-cache project create` inside the application container. Replace the printed bind address in the DSN with the address reachable by the client. Creating a project prints its ingestion key; keep that output private.

Initialization creates an application database role, a Metabase metadata role and a read-only analytics role. Initialization runs only on new volumes; changing environment passwords does not rotate existing database credentials. The application applies its schema migrations on startup. Use PostgreSQL owner access for schema installation and the read-only role for dashboard queries.

Follow [the dashboard guide](../../docs/metabase.md) to provision aggregate charts. Supply the Metabase URL, operator credentials, read-only database password, project and date range through private environment variables. The provisioner creates or updates its marked objects and refuses to overwrite unrelated objects. Re-run it to verify stable object IDs. No production throughput, SDK overhead or real-device compatibility claim follows from these synthetic checks.

## Optional authenticated evidence

The dashboards profile also starts a same-origin Caddy proxy on `METABASE_PROXY_PORT` (default 3002). Use the proxy URL for browser access and `METABASE_URL`; the direct Metabase port remains available for local diagnosis. The backend uses `METABASE_AUTH_URL` to authorize administrator downloads over the protected internal HTTP network. It makes no authentication request during ingestion or startup.

After migrations, install `docs/sql/investigation.sql` and then `docs/sql/explorer-permissions.sql` as the database owner with `psql --single-transaction -v ON_ERROR_STOP=1`. The explicit grants are required before provisioning this fresh deployment. They also revoke broad legacy access to archive payloads and ingestion keys. See [the Explorer guide](../../docs/explorer.md) for the authorization boundary and the evidence-origin option. Neither Symbolicator nor any symbol source is part of this deployment.
