# 文件：harness/persistence/schema.py
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    provider_response_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id),
    UNIQUE(run_id, sequence)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_sequence INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS durable_runs (
    run_id TEXT PRIMARY KEY,
    execution_json TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_expires_at TEXT,
    available_at TEXT NOT NULL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    trace_carrier_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS durable_approvals (
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    PRIMARY KEY (run_id, call_id, tool_name),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS durable_run_budget_calls (
    run_id TEXT NOT NULL,
    call_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, call_key),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS tool_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    external_operation_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_runs_conversation
ON runs(conversation_id);

CREATE INDEX IF NOT EXISTS idx_steps_run_sequence
ON steps(run_id, sequence);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
ON messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_checkpoints_run_sequence
ON checkpoints(run_id, step_sequence);

CREATE INDEX IF NOT EXISTS idx_events_run_created
ON events(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_durable_runs_claim
ON durable_runs(status, available_at, lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_durable_approvals_run
ON durable_approvals(run_id, status);

CREATE INDEX IF NOT EXISTS idx_durable_budget_run
ON durable_run_budget_calls(run_id);

CREATE INDEX IF NOT EXISTS idx_tool_idempotency_run
ON tool_idempotency(run_id, call_id);
"""
