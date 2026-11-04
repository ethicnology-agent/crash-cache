-- Run as the deployment database owner, after migrations and investigation.sql:
-- psql --single-transaction -v ON_ERROR_STOP=1 -f docs/sql/explorer-permissions.sql
-- Fixed role names match deploy/observability/init-databases.sql.
ALTER DEFAULT PRIVILEGES FOR ROLE crash_cache IN SCHEMA public
    REVOKE SELECT ON TABLES FROM metabase_readonly;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM metabase_readonly;
DO $$
DECLARE
    item RECORD;
BEGIN
    FOR item IN SELECT tablename FROM pg_tables
                WHERE schemaname='public' AND tablename NOT IN ('archive','project') LOOP
        EXECUTE format('GRANT SELECT ON TABLE public.%I TO metabase_readonly',item.tablename);
    END LOOP;
END $$;
GRANT SELECT (id,name,created_at) ON public.project TO metabase_readonly;
GRANT SELECT (hash,project_id,original_size,created_at) ON public.archive TO metabase_readonly;
GRANT USAGE ON SCHEMA public,crash_cache_explorer TO metabase_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA crash_cache_explorer TO metabase_readonly;
