CREATE TABLE copilot.tenants (
    id uuid PRIMARY KEY,
    slug varchar(80) NOT NULL UNIQUE,
    name varchar(160) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE TABLE copilot.app_users (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    email varchar(254) NOT NULL,
    password_hash varchar(100) NOT NULL,
    display_name varchar(160) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT uq_app_users_tenant_email UNIQUE (tenant_id, email)
);

CREATE TABLE copilot.user_roles (
    user_id uuid NOT NULL REFERENCES copilot.app_users(id) ON DELETE CASCADE,
    role varchar(32) NOT NULL,
    PRIMARY KEY (user_id, role),
    CONSTRAINT chk_user_roles_role CHECK (role IN ('ADMIN', 'ANALYST', 'VIEWER'))
);

CREATE TABLE copilot.data_sources (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    name varchar(160) NOT NULL,
    source_type varchar(32) NOT NULL,
    host varchar(255) NOT NULL,
    port integer NOT NULL,
    database_name varchar(128) NOT NULL,
    allowed_schema varchar(63) NOT NULL,
    secret_ref varchar(255) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT uq_data_sources_tenant_name UNIQUE (tenant_id, name),
    CONSTRAINT chk_data_sources_port CHECK (port BETWEEN 1 AND 65535)
);

CREATE TABLE copilot.analysis_jobs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    data_source_id uuid NOT NULL REFERENCES copilot.data_sources(id),
    created_by uuid NOT NULL REFERENCES copilot.app_users(id),
    question varchar(4000) NOT NULL,
    status varchar(32) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    request_hash varchar(64) NOT NULL,
    trace_id varchar(64) NOT NULL,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    CONSTRAINT uq_analysis_jobs_idempotency UNIQUE (tenant_id, created_by, idempotency_key),
    CONSTRAINT chk_analysis_jobs_status CHECK (
        status IN (
            'CREATED', 'PLANNING', 'VALIDATING', 'WAITING_APPROVAL', 'RUNNING',
            'COMPLETED', 'REJECTED', 'FAILED', 'CANCELLED'
        )
    )
);

CREATE TABLE copilot.approvals (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    analysis_job_id uuid NOT NULL REFERENCES copilot.analysis_jobs(id),
    requested_by uuid NOT NULL REFERENCES copilot.app_users(id),
    decided_by uuid REFERENCES copilot.app_users(id),
    status varchar(32) NOT NULL,
    reason varchar(500) NOT NULL,
    decision_comment varchar(500),
    version bigint NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    decided_at timestamp with time zone,
    CONSTRAINT uq_approvals_job UNIQUE (analysis_job_id),
    CONSTRAINT chk_approvals_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE TABLE copilot.audit_events (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES copilot.tenants(id),
    actor_user_id uuid REFERENCES copilot.app_users(id),
    action varchar(80) NOT NULL,
    resource_type varchar(80) NOT NULL,
    resource_id uuid,
    outcome varchar(32) NOT NULL,
    trace_id varchar(64) NOT NULL,
    details_json text NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE INDEX idx_app_users_tenant ON copilot.app_users(tenant_id);
CREATE INDEX idx_data_sources_tenant ON copilot.data_sources(tenant_id);
CREATE INDEX idx_analysis_jobs_tenant_created ON copilot.analysis_jobs(tenant_id, created_at);
CREATE INDEX idx_analysis_jobs_tenant_status ON copilot.analysis_jobs(tenant_id, status);
CREATE INDEX idx_approvals_tenant_status ON copilot.approvals(tenant_id, status);
CREATE INDEX idx_audit_events_tenant_created ON copilot.audit_events(tenant_id, created_at);
