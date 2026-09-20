# 文件：harness/platform/schema.py
PLATFORM_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS platform_plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    limits_json TEXT NOT NULL,
    tool_permissions_json TEXT NOT NULL,
    rates_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES platform_plans(id)
);

CREATE TABLE IF NOT EXISTS platform_api_keys (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    FOREIGN KEY (tenant_id) REFERENCES platform_tenants(id)
);

CREATE TABLE IF NOT EXISTS platform_run_accounts (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES platform_tenants(id),
    FOREIGN KEY (plan_id) REFERENCES platform_plans(id)
);

CREATE TABLE IF NOT EXISTS platform_usage_events (
    id TEXT PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    run_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES platform_tenants(id),
    FOREIGN KEY (plan_id) REFERENCES platform_plans(id)
);

CREATE TABLE IF NOT EXISTS platform_metered_runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    metered_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES platform_tenants(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS platform_audit_events (
    id TEXT PRIMARY KEY,
    actor_api_key_id TEXT NOT NULL,
    tenant_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_platform_audit_created
ON platform_audit_events(created_at);

CREATE INDEX IF NOT EXISTS idx_platform_api_keys_tenant
ON platform_api_keys(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_platform_run_accounts_tenant
ON platform_run_accounts(tenant_id, created_at);

CREATE INDEX IF NOT EXISTS idx_platform_usage_tenant_metric_time
ON platform_usage_events(tenant_id, metric, created_at);

CREATE INDEX IF NOT EXISTS idx_platform_usage_run
ON platform_usage_events(run_id);

CREATE INDEX IF NOT EXISTS idx_platform_tenants_plan
ON platform_tenants(plan_id, status);
"""
