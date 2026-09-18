ALTER TABLE copilot.analysis_jobs
    ADD COLUMN workflow_thread_id varchar(64),
    ADD COLUMN generated_sql text,
    ADD COLUMN answer text,
    ADD COLUMN error_code varchar(80);

CREATE TABLE copilot.agent_steps (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    analysis_job_id uuid NOT NULL REFERENCES copilot.analysis_jobs(id) ON DELETE CASCADE,
    step_name varchar(80) NOT NULL,
    status varchar(32) NOT NULL,
    attempt integer NOT NULL DEFAULT 0,
    input_summary_json text NOT NULL,
    output_summary_json text NOT NULL,
    duration_ms bigint NOT NULL,
    error_code varchar(80),
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT chk_agent_steps_status CHECK (status IN ('SUCCEEDED', 'FAILED', 'WAITING')),
    CONSTRAINT chk_agent_steps_attempt CHECK (attempt >= 0),
    CONSTRAINT chk_agent_steps_duration CHECK (duration_ms >= 0),
    CONSTRAINT uq_agent_steps_replay UNIQUE (
        analysis_job_id, step_name, attempt, status
    )
);

CREATE INDEX idx_agent_steps_job_created
    ON copilot.agent_steps(analysis_job_id, created_at);
CREATE INDEX idx_agent_steps_tenant_job
    ON copilot.agent_steps(tenant_id, analysis_job_id);
