"""
共享的 SQLite 存储基类 — 消除 9 个模块重复的连接/初始化样板。

设计原则：
  - 仅提取真正通用的逻辑（连接管理、目录创建、列迁移辅助）
  - _init_db 由子类重写（各模块表结构不同）
  - 兼容所有 9 个现有模块的直接替换（保持相同的 __init__ 签名）

用法：
  class MyStorage(SqliteBaseStorage):
      def __init__(self, db_path=None):
          super().__init__(db_path, db_name="my_module.db")

      def _init_db(self):
          conn = self._get_conn()
          c = conn.cursor()
          c.execute('''CREATE TABLE IF NOT EXISTS my_table (...)''')
          conn.commit()
          conn.close()
"""

import os
import sqlite3
from typing import Optional, TypeVar

T = TypeVar("T", bound="SqliteBaseStorage")


class SqliteBaseStorage:
    """SQLite 存储基类：连接管理 + 列迁移辅助。

    子类必需重写 _init_db()（或在 __init__ 后手动调用）。
    """

    def __init__(self, db_path: Optional[str] = None, db_name: str = "data.db"):
        if db_path is None:
            data_dir = os.environ.get(
                "DATA_DIR", os.path.join(os.getcwd(), "data")
            )
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, db_name)
        self.db_path = db_path
        # 子类重写的 _init_db 会自动调用
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """子类重写此方法以创建表。基类默认不创建任何表。"""

    @staticmethod
    def _migrate_add_column(
        cursor: sqlite3.Cursor, table: str, column: str, column_type: str
    ):
        """安全添加列——兼容 SQLite 不支持 IF NOT EXISTS for ALTER TABLE。"""
        try:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
            )
        except sqlite3.OperationalError:
            pass  # 列已存在，跳过
