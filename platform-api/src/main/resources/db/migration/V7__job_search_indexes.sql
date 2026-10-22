-- Match tenant/owner predicates and the stable (created_at, id) page ordering.
CREATE INDEX idx_jobs_tenant_page
    ON copilot.analysis_jobs (tenant_id, created_at DESC, id DESC);
CREATE INDEX idx_jobs_owner_page
    ON copilot.analysis_jobs (tenant_id, created_by, created_at DESC, id DESC);
CREATE INDEX idx_jobs_status_page
    ON copilot.analysis_jobs (tenant_id, status, created_at DESC, id DESC);
CREATE INDEX idx_jobs_source_page
    ON copilot.analysis_jobs (tenant_id, data_source_id, created_at DESC, id DESC);
