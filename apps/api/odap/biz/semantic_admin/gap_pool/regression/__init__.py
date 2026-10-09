"""缺口回归集 + 配对回放（ADR-088 子项目 B）。

回归集是缺口回路的验证臂：把缺口 occurrence 固化为不可变 held-out 验证集，
配对回放产出 fixed/regressed/unchanged 差分报告，作为人工裁决证据
（门控归人不归模型——不自动接受/驳回）。
"""
from .builder import RegressionSetBuilder
from .runner import PairedReplayRunner
from .service import RegressionService
from .storage import SQLiteGapRegressionStorage

__all__ = [
    "RegressionSetBuilder",
    "PairedReplayRunner",
    "RegressionService",
    "SQLiteGapRegressionStorage",
]
