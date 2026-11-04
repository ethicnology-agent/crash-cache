# Observability deployment

This optional Compose project runs PostgreSQL, crash-cache and Metabase. It does not include native crash processing, Symbolicator or a symbol server. Use a distinct Compose project name and fresh dedicated volumes; do not point it at existing deployment data.

Copy `.env.example` to a private `.env` in this directory and set four independent hexadecimal passwords. Generate each with `openssl rand -hex 32`; hexadecimal also avoids URI escaping in the database URL. Never commit the populated file or expanded Compose output. All published ports bind to loopback. PostgreSQL has no published network port.

```sh
docker compose --env-file deploy/observability/.env -f deploy/observability/compose.yml -p crash-cache-observability --profile observability --profile dashboards up -d --build
```

Create a project using `crash-cache project create` inside the application container. Replace the printed bind address in the DSN with the address reachable by the client. Creating a project prints its ingestion key; keep that output private.

Initialization creates an application database role, a Metabase metadata role and a read-only analytics role. Initialization runs only on new volumes; changing environment passwords does not rotate existing database credentials. The application applies its schema migrations on startup. Use PostgreSQL owner access for schema installation and the read-only role for dashboard queries.

Follow [the dashboard guide](../../docs/metabase.md) to provision aggregate charts. Supply the Metabase URL, operator credentials, read-only database password, project and date range through private environment variables. The provisioner creates or updates its marked objects and refuses to overwrite unrelated objects. Re-run it to verify stable object IDs. No production throughput, SDK overhead or real-device compatibility claim follows from these synthetic checks.
