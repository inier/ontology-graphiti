"""
L3 Application Intent — 意图识别 (Phase 2 桥接, 从 cognition/ 迁移).

从 biz/core/cognition/impl/intent_recognizer 重新导出。

注：`recognize_intent` 已重构为 `IntentRecognizer` 的方法，模块级函数不再存在；
此前仍按旧符号 re-export，导致本包在 import 期就抛 ImportError。
"""

from odap.biz.core.cognition.impl.intent_recognizer import IntentRecognizer

__all__ = ["IntentRecognizer"]
