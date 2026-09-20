# 文件：harness/persistence/repositories.py
from datetime import datetime

from harness.context.models import Message, MessageRole
from harness.persistence.database import dump_json, load_json
from harness.state.ids import new_id
from harness.state.models import (
    Checkpoint,
    Conversation,
    Run,
    RunStatus,
    RuntimeEvent,
    Step,
    StepStatus,
    StepType,
    utc_now,
)

class SQLiteConversationRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add(self, conversation: Conversation) -> None:
        self.connection.execute(
            """
            INSERT INTO conversations (
                id, user_id, tenant_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation.id,
                conversation.user_id,
                conversation.tenant_id,
                conversation.created_at.isoformat(),
                conversation.updated_at.isoformat(),
            ),
        )

    def get(self, conversation_id: str) -> Conversation | None:
        row = self.connection.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None

        return Conversation(
            id=row["id"],
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(
                row["updated_at"] or row["created_at"]
            ),
        )

class SQLiteRunRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add(self, run: Run) -> None:
        self.connection.execute(
            """
            INSERT INTO runs (
                id, conversation_id, status, current_step,
                provider_response_id, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.conversation_id,
                run.status.value,
                run.current_step,
                run.provider_response_id,
                run.error_message,
                run.created_at.isoformat(),
                run.updated_at.isoformat(),
            ),
        )

    def get(self, run_id: str) -> Run | None:
        row = self.connection.execute(
            "SELECT * FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None

        return Run(
            id=row["id"],
            conversation_id=row["conversation_id"],
            status=RunStatus(row["status"]),
            current_step=int(row["current_step"] or 0),
            provider_response_id=row["provider_response_id"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def update(self, run: Run) -> None:
        cursor = self.connection.execute(
            """
            UPDATE runs
            SET status = ?,
                current_step = ?,
                provider_response_id = ?,
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                run.status.value,
                run.current_step,
                run.provider_response_id,
                run.error_message,
                run.updated_at.isoformat(),
                run.id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(
                f"run not found: {run.id}"
            )

class SQLiteStepRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add(self, step: Step) -> None:
        self.connection.execute(
            """
            INSERT INTO steps (
                id, run_id, sequence, type, status,
                input_json, output_json, error_message,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step.id,
                step.run_id,
                step.sequence,
                step.type.value,
                step.status.value,
                dump_json(step.input_data),
                dump_json(step.output_data),
                step.error_message,
                step.created_at.isoformat(),
                step.updated_at.isoformat(),
            ),
        )

    def get(
        self,
        *,
        run_id: str,
        sequence: int,
    ) -> Step | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM steps
            WHERE run_id = ? AND sequence = ?
            """,
            (run_id, sequence),
        ).fetchone()
        return self._from_row(row) if row else None

    def update(self, step: Step) -> None:
        cursor = self.connection.execute(
            """
            UPDATE steps
            SET type = ?, status = ?, input_json = ?,
                output_json = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                step.type.value,
                step.status.value,
                dump_json(step.input_data),
                dump_json(step.output_data),
                step.error_message,
                step.updated_at.isoformat(),
                step.id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(
                f"step not found: {step.id}"
            )

    def list_by_run(self, run_id: str) -> list[Step]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM steps
            WHERE run_id = ?
            ORDER BY sequence ASC
            """,
            (run_id,),
        ).fetchall()
        return [
            self._from_row(row)
            for row in rows
        ]

    @staticmethod
    def _from_row(row) -> Step:
        return Step(
            id=row["id"],
            run_id=row["run_id"],
            sequence=int(row["sequence"]),
            type=StepType(row["type"]),
            status=StepStatus(row["status"]),
            input_data=load_json(row["input_json"]),
            output_data=load_json(row["output_json"]),
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

class SQLiteMessageRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add_user(
        self,
        *,
        conversation_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        self._add(
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata=metadata or {},
        )

    def add_assistant(
        self,
        *,
        conversation_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        self._add(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            metadata=metadata or {},
        )

    def _add(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("msg"),
                conversation_id,
                role,
                content,
                dump_json(metadata),
                utc_now().isoformat(),
            ),
        )

    def list_recent(
        self,
        *,
        conversation_id: str,
        limit: int = 100,
    ) -> list[Message]:
        rows = self.connection.execute(
            """
            SELECT role, content, metadata_json
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

        return [
            Message(
                role=MessageRole(row["role"]),
                content=row["content"],
                metadata=load_json(row["metadata_json"]),
            )
            for row in reversed(rows)
        ]

class SQLiteCheckpointRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add(self, checkpoint: Checkpoint) -> None:
        self.connection.execute(
            """
            INSERT INTO checkpoints (
                id, run_id, step_sequence, state_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                checkpoint.id,
                checkpoint.run_id,
                checkpoint.step_sequence,
                dump_json(checkpoint.state),
                checkpoint.created_at.isoformat(),
            ),
        )

    def get_latest(self, run_id: str) -> Checkpoint | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM checkpoints
            WHERE run_id = ?
            ORDER BY step_sequence DESC, created_at DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None

        return Checkpoint(
            id=row["id"],
            run_id=row["run_id"],
            step_sequence=int(row["step_sequence"]),
            state=load_json(row["state_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

class SQLiteEventRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def add(self, event: RuntimeEvent) -> None:
        self.connection.execute(
            """
            INSERT INTO events (
                id, run_id, step_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.run_id,
                event.step_id,
                event.event_type,
                dump_json(event.payload),
                event.created_at.isoformat(),
            ),
        )

    def list_by_run(self, run_id: str) -> list[RuntimeEvent]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM events
            WHERE run_id = ?
            ORDER BY created_at ASC
            """,
            (run_id,),
        ).fetchall()

        return [
            RuntimeEvent(
                id=row["id"],
                run_id=row["run_id"],
                step_id=row["step_id"],
                event_type=row["event_type"],
                payload=load_json(row["payload_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
