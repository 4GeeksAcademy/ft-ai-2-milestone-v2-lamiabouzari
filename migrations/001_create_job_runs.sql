-- Background-process run tracking. This table is intentionally separate from
-- reporting.pipeline_runs, which belongs to the Milestone 6 reporting flow.
CREATE TABLE IF NOT EXISTS job_runs (
    id UUID PRIMARY KEY,
    job_name TEXT NOT NULL,
    target_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_job_runs_job_name_target_date
    ON job_runs (job_name, target_date);

-- No separate lock is used: the processing row is the distributed lock. The
-- partial unique index makes simultaneous claims safe at database level.
CREATE UNIQUE INDEX IF NOT EXISTS ux_job_runs_processing_job
    ON job_runs (job_name)
    WHERE status = 'processing';
