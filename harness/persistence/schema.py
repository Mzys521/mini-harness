SCHEMA_SQL = """
-- 会话表: 一次用户会话
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 运行表: 会话中的每次 Agent 运行
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
);

-- 步骤表: 运行中的每个执行步骤(同一运行内 sequence 唯一)
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

    FOREIGN KEY (run_id)
        REFERENCES runs(id),

    UNIQUE(run_id, sequence)
);

-- 消息表: 会话中的对话消息
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
);

-- 检查点表: 状态快照(用于崩溃恢复)
CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_sequence INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES runs(id)
);


-- 日志表: 运行中的事件
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_events_run_created
ON events(run_id, created_at);


-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_runs_conversation
ON runs(conversation_id);

CREATE INDEX IF NOT EXISTS idx_steps_run_sequence
ON steps(run_id, sequence);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
ON messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_checkpoints_run_sequence
ON checkpoints(run_id, step_sequence);
"""