from harness.persistence.repositories import(
    SQLiteRunRepository,
    SQLiteStepRepository,
    SQLiteCheckpointRepository,
    SQLiteConversationRepository,
    SQLiteMessageRepository,
)
from contextlib import nullcontext

class UnitOfWork:
    """工作单元: 用一个事务连接集中管理各仓储，统一提交/回滚(上下文管理器)"""

    def __init__(self , database , * , observability = None) -> None:
        """参数 database: Database 实例(提供 connect 方法)"""
        self.observability = observability
        self.database = database
        self.connection = None
        self._span_context = None

    def __enter__(self):
        """进入 with 块: 建立连接并完成各仓储绑定。
        返回: self
        """
        self._span_context = (
            self.observability.span(
                "persistence.transaction",
                {"db.system.name": "sqlite"},
            )
            if self.observability
            else nullcontext()
        )
        self._span_context.__enter__()
        self.connection = self.database.connect()
        self._init_repositories()  # 沿用 Phase 4（阶段4）Repository（仓储）初始化。
        return self

    def _init_repositories(self):
        self.runs = SQLiteRunRepository(self.connection)                # 运行仓储
        self.steps = SQLiteStepRepository(self.connection)              # 步骤仓储
        self.checkpoints = SQLiteCheckpointRepository(self.connection)  # 检查点仓储
        self.conversations = (    # 会话仓储
            SQLiteConversationRepository(
                self.connection
            )
        )

        self.messages = (    # 消息仓储
            SQLiteMessageRepository(
                self.connection
            )
        )
        return self

    def commit(self) -> None:
        """提交当前事务"""
        self.connection.commit()

    def rollback(self) -> None:
        """回滚当前事务"""
        self.connection.rollback()

    def __exit__(self , exc_type , exc , traceback) -> None:
        """退出 with 块: 有异常则回滚，最后关闭连接。
        参数 exc_type/exc/traceback: 上下文中的异常信息(无异常均为 None)
        """
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.connection.close()

