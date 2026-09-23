# 文件：harness/mcp/store.py
"""由前端登记的 MCP Server 的持久化。

只做数据访问：不做连通性检查、不注册工具、不生成时间戳。
编排在 `harness/app/mcp_api.py` 与 `harness/app/assembly.py`。
"""
import json

from harness.mcp.config import (
    MCPServerConfig,
    MCPTransport,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_servers (
    name TEXT PRIMARY KEY,
    transport TEXT NOT NULL,
    url TEXT,
    command TEXT,
    args_json TEXT NOT NULL DEFAULT '[]',
    env_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    tool_prefix TEXT,
    allowed_tools_json TEXT,
    created_at TEXT NOT NULL
);
"""


class SQLiteMCPServerStore:
    """前端登记的 MCP Server 清单。

    表由本类自行创建（不进入核心 `persistence/schema.py`）：MCP 是可选能力。
    运行期登记的 Server 只使用 `default_tool_policy`，不在库里保存逐个工具的策略——
    策略需要「谁信任谁」的人工判断，不适合由前端提交决定。
    """

    def __init__(self, database) -> None:
        self.database = database
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        connection = self.database.connect()
        try:
            connection.executescript(_SCHEMA)
            connection.commit()
        finally:
            connection.close()

    def create_server(
        self,
        config: MCPServerConfig,
        *,
        created_at: str,
    ) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO mcp_servers (
                    name, transport, url, command, args_json, env_json,
                    enabled, tool_prefix, allowed_tools_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    transport = excluded.transport,
                    url = excluded.url,
                    command = excluded.command,
                    args_json = excluded.args_json,
                    env_json = excluded.env_json,
                    enabled = excluded.enabled,
                    tool_prefix = excluded.tool_prefix,
                    allowed_tools_json = excluded.allowed_tools_json
                """,
                (
                    config.name,
                    config.transport.value,
                    config.url,
                    config.command,
                    json.dumps(list(config.args), ensure_ascii=False),
                    json.dumps(config.env, ensure_ascii=False),
                    1 if config.enabled else 0,
                    config.tool_prefix,
                    (
                        None
                        if config.allowed_tools is None
                        else json.dumps(
                            sorted(config.allowed_tools),
                            ensure_ascii=False,
                        )
                    ),
                    created_at,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_server(self, name: str) -> MCPServerConfig | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM mcp_servers WHERE name = ?",
                (name,),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else _to_config(row)

    def get_servers(self) -> list[MCPServerConfig]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM mcp_servers ORDER BY created_at, name"
            ).fetchall()
        finally:
            connection.close()
        return [_to_config(row) for row in rows]

    def delete_server(self, name: str) -> bool:
        connection = self.database.connect()
        try:
            cursor = connection.execute(
                "DELETE FROM mcp_servers WHERE name = ?",
                (name,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return cursor.rowcount > 0


def _to_config(row) -> MCPServerConfig:
    allowed = row["allowed_tools_json"]
    return MCPServerConfig(
        name=row["name"],
        transport=MCPTransport(row["transport"]),
        url=row["url"],
        command=row["command"],
        args=tuple(json.loads(row["args_json"] or "[]")),
        env=dict(json.loads(row["env_json"] or "{}")),
        enabled=bool(row["enabled"]),
        tool_prefix=row["tool_prefix"],
        allowed_tools=(
            None if allowed is None else frozenset(json.loads(allowed))
        ),
    )
