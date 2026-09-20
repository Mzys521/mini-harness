# 文件：harness/persistence/database.py
import json
import sqlite3
from pathlib import Path
from typing import Any

from harness.persistence.schema import SCHEMA_SQL

def dump_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )

def load_json(value: str):
    return json.loads(value)

class Database:
    """SQLite 连接与 Schema 初始化。

    Phase 10 开启 WAL 以改善单机 Reader/Writer 并发；SQLite WAL 不适合跨主机网络文件系统。
    """

    def __init__(
        self,
        path: str,
        *,
        observability=None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self.path = path
        self.observability = observability
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}"
        )
        return connection

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        connection = self.connect()

        try:
            # WAL 提升同机并发；FULL 优先保证提交持久性。
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(SCHEMA_SQL)

            # 兼容早期教程数据库：CREATE TABLE IF NOT EXISTS 不会自动增加新列。
            self._ensure_column(
                connection,
                table="runs",
                column="current_step",
                ddl="INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                table="runs",
                column="provider_response_id",
                ddl="TEXT",
            )
            self._ensure_column(
                connection,
                table="runs",
                column="error_message",
                ddl="TEXT",
            )
            self._ensure_column(
                connection,
                table="conversations",
                column="updated_at",
                ddl="TEXT",
                backfill_sql=(
                    "UPDATE conversations "
                    "SET updated_at = created_at "
                    "WHERE updated_at IS NULL"
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        *,
        table: str,
        column: str,
        ddl: str,
        backfill_sql: str | None = None,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }
        if column in columns:
            return

        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
        )
        if backfill_sql:
            connection.execute(backfill_sql)

    def uow(self):
        from harness.persistence.unit_of_work import UnitOfWork

        return UnitOfWork(
            self,
            observability=self.observability,
        )
