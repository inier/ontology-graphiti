"""
L3 Application Intent — 意图识别 (Phase 2 桥接, 从 cognition/ 迁移).

从 biz/core/cognition/impl/intent_recognizer 重新导出。
"""

from odap.biz.core.cognition.impl.intent_recognizer import (
    IntentRecognizer,
    recognize_intent,
)

__all__ = ["IntentRecognizer", "recognize_intent"]
