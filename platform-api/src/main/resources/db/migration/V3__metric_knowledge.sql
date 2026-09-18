CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE copilot.metric_documents (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    title varchar(240) NOT NULL,
    version integer NOT NULL,
    status varchar(32) NOT NULL,
    source_type varchar(16) NOT NULL,
    source_name varchar(255) NOT NULL,
    content_sha256 varchar(64) NOT NULL,
    created_by uuid REFERENCES copilot.app_users(id),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT uq_metric_documents_tenant_title_version UNIQUE (tenant_id, title, version),
    CONSTRAINT chk_metric_documents_version CHECK (version > 0),
    CONSTRAINT chk_metric_documents_status CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CONSTRAINT chk_metric_documents_source_type CHECK (source_type IN ('MARKDOWN', 'PDF'))
);

CREATE UNIQUE INDEX uq_metric_documents_active_title
    ON copilot.metric_documents(tenant_id, title)
    WHERE status = 'ACTIVE';

CREATE TABLE copilot.metric_chunks (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    document_id uuid NOT NULL REFERENCES copilot.metric_documents(id) ON DELETE CASCADE,
    document_version integer NOT NULL,
    section_key varchar(500) NOT NULL,
    section_title varchar(500) NOT NULL,
    source_locator varchar(120) NOT NULL,
    ordinal integer NOT NULL,
    content text NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(section_title, '') || ' ' || coalesce(content, ''))
    ) STORED,
    embedding vector(64) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT uq_metric_chunks_document_ordinal UNIQUE (document_id, ordinal),
    CONSTRAINT chk_metric_chunks_ordinal CHECK (ordinal >= 0)
);

CREATE INDEX idx_metric_documents_tenant_status
    ON copilot.metric_documents(tenant_id, status, updated_at DESC);
CREATE INDEX idx_metric_chunks_tenant_document
    ON copilot.metric_chunks(tenant_id, document_id);
CREATE INDEX idx_metric_chunks_search
    ON copilot.metric_chunks USING gin(search_vector);
CREATE INDEX idx_metric_chunks_embedding
    ON copilot.metric_chunks USING hnsw (embedding vector_cosine_ops);
