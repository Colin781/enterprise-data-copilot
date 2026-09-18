ALTER TABLE copilot.analysis_jobs
    ADD COLUMN result_columns_json text,
    ADD COLUMN result_rows_json text,
    ADD COLUMN chart_spec_json text,
    ADD COLUMN citations_json text;
