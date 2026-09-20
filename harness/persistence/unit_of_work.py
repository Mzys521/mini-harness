# 文件：harness/persistence/unit_of_work.py
from contextlib import nullcontext

from harness.persistence.repositories import (
    SQLiteCheckpointRepository,
    SQLiteConversationRepository,
    SQLiteEventRepository,
    SQLiteMessageRepository,
    SQLiteRunRepository,
    SQLiteStepRepository,
)

class UnitOfWork:
    """一组共享同一个 SQLite Transaction 的 Repository。"""

    def __init__(
        self,
        database,
        *,
        observability=None,
    ) -> None:
        self.database = database
        self.observability = observability
        self.connection = None
        self._span_context = None

    def __enter__(self):
        self._span_context = (
            self.observability.span(
                "persistence.transaction",
                {"db.system.name": "sqlite"},
            )
            if self.observability is not None
            else nullcontext()
        )
        self._span_context.__enter__()

        self.connection = self.database.connect()
        self.conversations = SQLiteConversationRepository(
            self.connection
        )
        self.runs = SQLiteRunRepository(
            self.connection
        )
        self.steps = SQLiteStepRepository(
            self.connection
        )
        self.messages = SQLiteMessageRepository(
            self.connection
        )
        self.checkpoints = SQLiteCheckpointRepository(
            self.connection
        )
        self.events = SQLiteEventRepository(
            self.connection
        )
        return self

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            if self.connection is not None:
                self.connection.close()
            self._span_context.__exit__(
                exc_type,
                exc,
                traceback,
            )
