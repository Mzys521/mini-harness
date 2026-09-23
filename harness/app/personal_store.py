"""SQL-only storage for personal preferences, skills and scheduled tasks."""
from contextlib import closing
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_preferences (
 id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS personal_skills (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 instructions TEXT NOT NULL, enabled INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS personal_automations (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, prompt TEXT NOT NULL,
 workspace_id TEXT, skill_ids TEXT NOT NULL, next_run TEXT NOT NULL,
 interval_seconds INTEGER NOT NULL, enabled INTEGER NOT NULL,
 last_status TEXT NOT NULL, last_error TEXT NOT NULL,
 last_run_id TEXT, last_session_id TEXT, created_at TEXT NOT NULL);
"""


class PersonalStore:
    def __init__(self, database: Any):
        self.database = database
        with closing(database.connect()) as conn:
            conn.executescript(SCHEMA)

    def rows(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with closing(self.database.connect()) as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def execute(self, sql: str, args: tuple = ()) -> int:
        with closing(self.database.connect()) as conn, conn:
            return conn.execute(sql, args).rowcount

    def claim(self, task_id: str, expected: str, next_run: str, enabled: bool) -> bool:
        return self.execute(
            "UPDATE personal_automations SET next_run=?,enabled=?,last_status='dispatching',"
            "last_error='' WHERE id=? AND next_run=? AND enabled=1",
            (next_run, int(enabled), task_id, expected),
        ) == 1
