-- Preserve existing 64-dimensional vectors. Other models require explicit re-ingestion.
DROP INDEX copilot.idx_metric_chunks_embedding;
ALTER TABLE copilot.metric_chunks ALTER COLUMN embedding TYPE vector;
ALTER TABLE copilot.metric_chunks ADD COLUMN embedding_profile varchar(300)
    NOT NULL DEFAULT 'hashing:64';
CREATE INDEX idx_chunks_profile ON copilot.metric_chunks(tenant_id, embedding_profile);
CREATE INDEX idx_chunks_embedding_64 ON copilot.metric_chunks
    USING hnsw ((embedding::vector(64)) vector_cosine_ops)
    WHERE vector_dims(embedding) = 64;
CREATE INDEX idx_chunks_embedding_1536 ON copilot.metric_chunks
    USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
    WHERE vector_dims(embedding) = 1536;
