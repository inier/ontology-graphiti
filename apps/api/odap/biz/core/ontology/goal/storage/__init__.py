"""OntoFlow Goal - SQLite 持久化层"""
from .sqlite_goal_storage import SQLiteGoalStorage

Storage = SQLiteGoalStorage


def get_goal_storage() -> SQLiteGoalStorage:
    """返回默认 goal 存储实例（无单例；调用方自行持有生命周期）。

    供 C3 门面（odap.biz.core.ontology.public）转发给外部消费者
    （如 semantic_admin 的结构变更提案路径），避免外部深插 goal.storage。
    """
    return SQLiteGoalStorage()


__all__ = ["Storage", "SQLiteGoalStorage", "get_goal_storage"]
