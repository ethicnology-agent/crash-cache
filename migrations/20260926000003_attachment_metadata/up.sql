CREATE TABLE attachment_metadata (
    id BIGSERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES project(id),
    archive_hash TEXT NOT NULL REFERENCES archive(hash),
    event_id TEXT,
    item_index INTEGER NOT NULL,
    filename TEXT,
    attachment_type TEXT,
    content_type TEXT,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (archive_hash, item_index)
);
CREATE INDEX attachment_metadata_project_event ON attachment_metadata(project_id, event_id);
