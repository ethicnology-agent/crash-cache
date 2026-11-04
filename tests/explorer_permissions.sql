-- Execute only against the disposable migrated test database with investigation.sql installed.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF current_database() NOT LIKE 'crash_cache_test%' THEN
        RAISE EXCEPTION 'This regression requires a disposable crash_cache_test database';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='crash_cache') THEN
        CREATE ROLE crash_cache;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='metabase_readonly') THEN
        CREATE ROLE metabase_readonly;
    END IF;
END $$;
-- Reproduce a deployment upgraded from the old broad grants.
GRANT SELECT ON public.archive,public.project TO metabase_readonly;
\ir ../docs/sql/explorer-permissions.sql
SELECT 1 / ((NOT has_column_privilege('metabase_readonly','public.archive','compressed_payload','SELECT'))::int) AS binary_payload_is_private;
SELECT 1 / ((NOT has_column_privilege('metabase_readonly','public.project','public_key','SELECT'))::int) AS ingestion_key_is_private;
SELECT 1 / (has_column_privilege('metabase_readonly','public.archive','created_at','SELECT')::int) AS pipeline_metadata_is_readable;
SELECT 1 / (has_table_privilege('metabase_readonly','crash_cache_explorer.attachments','SELECT')::int) AS attachment_metadata_is_readable;
SET LOCAL ROLE metabase_readonly;
SELECT count(*) FROM crash_cache_explorer.reports;
SELECT count(created_at) FROM public.archive;
ROLLBACK;
