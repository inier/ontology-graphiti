"""抽象接口模块 (T347, T351-T352)"""
from .branch_repository import BranchRepository
from .merge_engine import MergeEngine, MergeResult

__all__ = ["BranchRepository", "MergeEngine", "MergeResult"]
