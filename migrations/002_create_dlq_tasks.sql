-- Durable record of Celery tasks that exhausted all retries.
CREATE TABLE IF NOT EXISTS dlq_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    task_name TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dlq_tasks_created_at ON dlq_tasks (created_at);
