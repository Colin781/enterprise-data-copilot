ALTER TABLE copilot.analysis_jobs
    ADD COLUMN result_truncated boolean NOT NULL DEFAULT false;
