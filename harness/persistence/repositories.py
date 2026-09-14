# 仓储接口（Repository）定义：
# 使用 typing.Protocol 声明"结构化"接口——实现类无需显式继承，
# 只要方法签名一致，即可作为对应仓储的实现（如后续的 SQLite 实现）。

from typing import Protocol
from datetime import datetime

from harness.state.models import (
    Run,
    Step,
    Checkpoint,
    Conversation,
    RunState,
    StepState,
    StepType,
)

from harness.persistence.database import (
    dump_json,
    load_json,
)

from harness.context.models import (
    Message ,
    MessageRole,
)

# Run 仓储：负责任务运行实例（Run）的持久化读写
class RunRepository(Protocol):
    def add(self , run: Run) -> None: ...                 # 新增一条运行记录
    def get(self , run_id: str) -> Run | None: ...        # 按 ID 查询运行记录，不存在返回 None
    def update(self , run: Run) -> None: ...              # 更新运行记录（状态 / 当前步骤等）

# Step 仓储：负责运行过程中每个执行步骤（Step）的持久化读写
class StepRepository(Protocol):
    def add(self , step: Step) -> None: ...               # 追加一个执行步骤
    def list_by_run(self, run_id: str) -> list[Step]: ... # 按运行 ID 取出全部步骤（按 sequence 顺序）

# Checkpoint 仓储：负责检查点（Checkpoint）的持久化读写
class CheckpointRepository(Protocol):
    def add(self , checkpoint: Checkpoint) -> None: ...   # 保存检查点（用于崩溃后恢复）
    def get_latest(self, run_id: str) -> Checkpoint | None: ... # 取该运行最新的检查点，不存在返回 None

class SQLiteRunRepository:
    """RunRepository 的 SQLite 实现"""

    def __init__(self , connection,)-> None:
        """参数 connection: 已开启事务的 sqlite3 连接"""
        self.connection = connection

    def add(self , run: Run) -> None:
        """新增一条运行记录。参数 run: 待保存的运行实例"""
        self.connection.execute(
            """
            INSERT INTO runs (
                id,
                conversation_id,
                status,
                current_step,
                error_message,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id ,
                run.conversation_id,
                run.status.value,
                run.current_step,
                run.error_message,
                run.created_at.isoformat(),
                run.updated_at.isoformat(),
            ),
        )

    def get(self , run_id: str) -> Run | None:
        """按 ID 查询运行记录。
        参数 run_id: 运行ID
        返回: Run 实例；不存在返回 None
        """
        row = self.connection.execute(
            """
            SELECT * FROM runs WHERE id = ?
            """,
            (run_id,)
        ).fetchone()

        if row is None:
            return None
        
        return Run(
            id = row["id"],
            conversation_id= row["conversation_id"],
            status=RunState(row["status"]),
            current_step=row["current_step"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def update(self, run: Run) -> None:
        """更新运行记录的状态/当前步骤等字段。参数 run: 待更新的运行实例"""
        self.connection.execute(
            """
                UPDATE runs
                SET
                    status = ?,
                    current_step = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
            """,
            (
                run.status.value,
                run.current_step,
                run.error_message,
                run.updated_at.isoformat(),
                run.id,
            ),
        )

class SQLiteCheckpointRepository:
    """CheckpointRepository 的 SQLite 实现"""

    def __init__(self, connection) -> None:
        """参数 connection: 已开启事务的 sqlite3 连接"""
        self.connection = connection


    def add(self , checkpoint: Checkpoint) ->None:
        """保存一个检查点。
        参数 checkpoint: 检查点对象
        """
        self.connection.execute(
            """
                INSERT INTO checkpoints (
                    id,
                    run_id,
                    step_sequence,
                    state_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """,
            (
                checkpoint.id,
                checkpoint.run_id,
                checkpoint.step_sequence,
                dump_json(checkpoint.state),
                checkpoint.created_at.isoformat(),
            ),
        )

    def get_latest(self , run_id: str) -> Checkpoint | None:
        """取该运行最新的检查点(按步骤序号倒序取第一条)。
        参数 run_id: 运行ID
        返回: Checkpoint；不存在返回 None
        """
        row = self.connection.execute(
            """
            SELECT * FROM checkpoints WHERE run_id = ?
            ORDER BY step_sequence DESC
            LIMIT 1
            """,
            (run_id,)
        ).fetchone()

        if row is None:
            return None

        return Checkpoint(
            id = row["id"],
            run_id = row["run_id"],
            step_sequence = row["step_sequence"],
            state = load_json(row["state_json"]),
            created_at = datetime.fromisoformat(row["created_at"]),
        )

class SQLiteStepRepository:
    """StepRepository 的 SQLite 实现"""

    def __init__(self, connection , ) -> None:
        """参数 connection: 已开启事务的 sqlite3 连接"""
        self.connection = connection


    def add(self , step : Step,)-> None:
        """追加一个执行步骤。参数 step: 待保存的步骤"""
        self.connection.execute(
            """
            INSERT INTO steps (
                id,
                run_id,
                sequence,
                type,
                status,
                input_json,
                output_json,
                error_message,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_by_run(self, run_id: str):
        """按运行 ID 取出全部步骤(按 sequence 升序)。
        参数 run_id: 运行ID
        返回: Step 列表
        """
        rows = self.connection.execute(
            """
            SELECT * FROM steps WHERE run_id = ?
            ORDER BY sequence ASC
            """,
            (run_id,)
        )

        return [
            Step(
                id = row["id"],
                run_id = row["run_id"],
                sequence = row["sequence"],
                type = StepType(row["type"]),
                status = StepState(row["status"]),
                input_data = load_json(row["input_json"]),
                output_data = load_json(row["output_json"]),
                error_message = row["error_message"],
                created_at = datetime.fromisoformat(row["created_at"]),
                updated_at = datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

class SQLiteMessageRepository:
    """会话消息的 SQLite 实现"""

    def __init__(self , connection , ) -> None:
        """参数 connection: 已开启事务的 sqlite3 连接"""
        self.connection = connection

    def add(self , * , message_id: str , conversation_id: str , message: Message , created_at ,) -> None:
        """保存一条消息。
        参数 message_id: 消息ID / conversation_id: 所属会话ID / message: 消息对象 / created_at: 创建时间
        """
        self.connection.execute(
            """
            INSERT INTO messages (
                id,
                conversation_id,
                role,
                content,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                message.role.value,
                message.content,
                dump_json(
                    message.metadata
                ),
                created_at.isoformat(),
            ),
        )
    
    def list_recent(self, * , conversation_id: str , limit: int ,) -> list[Message]:
        """取会话最近 limit 条消息(最终按时间升序返回)。
        参数 conversation_id: 会话ID / limit: 条数
        返回: Message 列表
        """
        rows = self.connection.execute(
            """
            SELECT *
            FROM (
                SELECT *
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            )
            ORDER BY created_at ASC
            """,
            (
                conversation_id,
                limit,
            ),
        ).fetchall()

        return [
            Message(
                role=MessageRole(
                    row["role"]
                ),
                content=row["content"],
                metadata=load_json(
                    row["metadata_json"]
                ),
            )
            for row in rows
        ]

class SQLiteConversationRepository:
    """会话的 SQLite 实现"""

    def __init__(self , connection , ) -> None:
        """参数 connection: 已开启事务的 sqlite3 连接"""
        self.connection = connection

    def add(self , conversation,) -> None:
        """新增一条会话记录。参数 conversation: 会话对象"""
        self.connection.execute(
            """
            INSERT INTO conversations (
                id,
                user_id,
                tenant_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation.id,
                conversation.user_id,
                conversation.tenant_id,
                conversation.created_at.isoformat(),
                conversation.updated_at.isoformat(),
            ),
        )

    def get(self , conversation_id: str):
        """按 ID 查询会话。
        参数 conversation_id: 会话ID
        返回: Conversation；不存在返回 None
        """
        row = self.connection.execute(
            """
            SELECT *
            FROM conversations
            WHERE id = ?
            """,
            (
                conversation_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return Conversation(
            id=row["id"],
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            updated_at=datetime.fromisoformat(
                row["updated_at"]
            ),
        )










