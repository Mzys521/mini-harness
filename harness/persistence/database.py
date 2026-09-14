import sqlite3
import json

from pathlib import Path
from harness.persistence.schema import SCHEMA_SQL
from typing import Any


class Database:
    """SQLite 数据库封装: 负责连接创建与建表初始化"""

    def __init__(self , path: str,) -> None:
        """参数 path: SQLite 数据库文件路径"""
        self.path = path


    # 创建数据库连接 SQLite3
    def connect(self) -> sqlite3.Connection:
        """创建并配置一个数据库连接。
        返回: 关闭自动提交、支持按列名取值的连接
        """
        connection = sqlite3.connect(self.path , autocommit=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize(self) -> None:
        """建库初始化: 创建父目录并执行建表脚本(幂等，可重复调用)"""

        Path(self.path).parent.mkdir(parents=True, exist_ok=True,)

        connection = self.connect()

        # 建表脚本整体执行: 失败回滚并抛出，成功提交后关闭连接
        try: 
            connection.executescript(SCHEMA_SQL)
            connection.commit()
        
        except Exception :
            connection.rollback()
            raise
        finally:
            connection.close()


def dump_json(value : Any) -> str:
    """把对象序列化为紧凑 JSON(保留中文，无法序列化的对象转字符串)。
    参数 value: 待序列化对象
    返回: JSON 字符串
    """
    return json.dumps(
        value,
        ensure_ascii= False,
        separators=(",", ":"),
        default= str ,
    )

def load_json(value : str) -> Any:
    """解析 JSON 字符串。
    参数 value: JSON 字符串
    返回: 解析后的 Python 对象
    """
    return json.loads(value)







