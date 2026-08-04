"""Iter 4.1: Multimodal Router — MIME-based dispatch + result aggregation.

ADR-074 §4.1: 多模态处理模块按 MIME 类型分派到对应解析器，
解析结果归集后供下游 HE 抽取消费。

架构（复用优先，不重写已有实现）：
    ┌─────────────────────────────────────────────────────┐
    │ MultimodalRouter                                    │
    │   route(mime_type, source_ref) → ParsedModality     │
    │ ┌─────────────────────────────────────────────────┐ │
    │ │ TextParser   → 原文透传（下游 HE 负责结构化）    │ │
    │ │ ImageParser  → 复用 MultimodalProcessor (VLM)    │ │
    │ │ AudioParser  → 复用 MultimodalProcessor (ASR)    │ │
    │ │ VideoParser  → 关键帧抽取 → ImageParser（降级）  │ │
    │ └─────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────┘
                            ↓
    ┌─────────────────────────────────────────────────────┐
    │ ResultAggregator                                     │
    │   aggregate(List[ParsedModality]) → AggregatedResult │
    │   合并多模态文本 + 元数据 + 置信度                   │
    └─────────────────────────────────────────────────────┘

设计要点（AGENTS.md / project_memory）：
- 函数 ≤40 行（Constitution I）
- 不新建接口（Constitution IV）— 用 dataclass + 策略表
- 失败降级不抛异常（返回 fallback=True 的 ParsedModality）
- 不 hardcode 配置（通过 get_config / 环境变量）
"""

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("multimodal_router")


# ------------------------------------------------------------------
# 数据模型
# ------------------------------------------------------------------


@dataclass
class ParsedModality:
    """单个模态的解析结果。"""

    modality: str  # text | image | audio | video
    text: str  # 解析出的文本（图像描述/音频转写/视频描述/原文）
    confidence: float = 0.0
    model_used: str = ""
    source_ref: str = ""
    mime_type: str = ""
    fallback: bool = False  # True 表示降级路径（解析失败但返回了占位文本）
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "text": self.text,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "source_ref": self.source_ref,
            "mime_type": self.mime_type,
            "fallback": self.fallback,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedResult:
    """多模态解析归集结果。"""

    combined_text: str  # 合并后的文本（供 HE feed 消费）
    modalities: List[ParsedModality] = field(default_factory=list)
    total_confidence: float = 0.0
    all_fallback: bool = False  # True 表示所有模态均降级

    def to_dict(self) -> Dict[str, Any]:
        return {
            "combined_text": self.combined_text,
            "modalities": [m.to_dict() for m in self.modalities],
            "total_confidence": self.total_confidence,
            "all_fallback": self.all_fallback,
            "modality_count": len(self.modalities),
        }


# ------------------------------------------------------------------
# 解析器（策略表注册，不建抽象工厂）
# ------------------------------------------------------------------


class TextParser:
    """文本解析器 — 原文透传，下游 HE 负责结构化抽取。

    source_ref 可以是：
    - 文本本身（最常见）
    - file:// 路径（读取文件内容）
    - minio:// 引用（调用方应先下载为文本再传入）
    """

    def parse(self, source_ref: str, mime_type: str = "text/plain") -> ParsedModality:
        text, is_fallback = self._resolve_text(source_ref)
        return ParsedModality(
            modality="text",
            text=text,
            confidence=0.0 if is_fallback else 1.0,
            model_used="passthrough",
            source_ref=source_ref,
            mime_type=mime_type,
            fallback=is_fallback,
            metadata={"char_count": len(text)},
        )

    def _resolve_text(self, source_ref: str) -> tuple[str, bool]:
        """返回 (text, is_fallback)。file:// 读取失败时返回空串 + fallback=True。"""
        if not source_ref:
            return "", False
        # file:// 协议 — 读取本地文件
        if source_ref.startswith("file:///"):
            path = source_ref[8:]  # 去掉 file:///
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read(), False
            except Exception as exc:
                logger.warning("TextParser 读取文件失败 %s: %s", path, exc)
                return "", True  # 降级：返回空串 + fallback 标记（不污染下游）
        return source_ref, False


class ImageParser:
    """图像解析器 — 复用 MultimodalProcessor (VLM: Claude/GPT4V/LLaVA)。"""

    def __init__(self, processor: Any = None):
        self._processor = processor

    def _get_processor(self) -> Any:
        if self._processor is not None:
            return self._processor
        try:
            from odap.infra.data_pipeline.multimodal_processor import MultimodalProcessor
            self._processor = MultimodalProcessor()
        except Exception as exc:
            logger.warning("MultimodalProcessor 初始化失败: %s", exc)
            self._processor = None
        return self._processor

    def parse(self, source_ref: str, mime_type: str = "image/png") -> ParsedModality:
        processor = self._get_processor()
        if processor is None:
            return self._fallback(source_ref, mime_type, "processor_unavailable")

        # source_ref 可能是 base64 / 文件路径 / bytes
        image_data = self._resolve_image_data(source_ref)
        if image_data is None:
            return self._fallback(source_ref, mime_type, "invalid_image_data")

        try:
            result = processor.process_image(image_data)
            return ParsedModality(
                modality="image",
                text=result.get("description", ""),
                confidence=float(result.get("confidence", 0.0)),
                model_used=result.get("model_used", "unknown"),
                source_ref=source_ref,
                mime_type=mime_type,
                fallback=result.get("fallback", False),
                metadata={"objects": result.get("objects", [])},
            )
        except Exception as exc:
            logger.warning("ImageParser 解析失败: %s", exc)
            return self._fallback(source_ref, mime_type, str(exc))

    def _resolve_image_data(self, source_ref: str) -> Any:
        """source_ref → 可被 MultimodalProcessor 处理的格式（文件路径/base64/bytes）。"""
        if not source_ref:
            return None
        # file:// 协议 — 转为本地路径
        if source_ref.startswith("file:///"):
            path = source_ref[8:]
            if os.path.isfile(path):
                return path
            logger.warning("ImageParser 文件不存在: %s", path)
            return None
        # minio:// 引用 — 调用方应先下载为 bytes 再传入，此处返回原值由 processor 处理
        return source_ref

    def _fallback(self, source_ref: str, mime_type: str, reason: str) -> ParsedModality:
        return ParsedModality(
            modality="image",
            text="[图像解析失败，无可用描述]",
            confidence=0.0,
            model_used="fallback",
            source_ref=source_ref,
            mime_type=mime_type,
            fallback=True,
            metadata={"error": reason},
        )


class AudioParser:
    """音频解析器 — 复用 MultimodalProcessor (ASR: Whisper/Deepgram)。"""

    def __init__(self, processor: Any = None):
        self._processor = processor

    def _get_processor(self) -> Any:
        if self._processor is not None:
            return self._processor
        try:
            from odap.infra.data_pipeline.multimodal_processor import MultimodalProcessor
            self._processor = MultimodalProcessor()
        except Exception as exc:
            logger.warning("MultimodalProcessor 初始化失败: %s", exc)
            self._processor = None
        return self._processor

    def parse(self, source_ref: str, mime_type: str = "audio/wav") -> ParsedModality:
        processor = self._get_processor()
        if processor is None:
            return self._fallback(source_ref, mime_type, "processor_unavailable")

        audio_data = self._resolve_audio_data(source_ref)
        if audio_data is None:
            return self._fallback(source_ref, mime_type, "invalid_audio_data")

        try:
            result = processor.process_audio(audio_data)
            return ParsedModality(
                modality="audio",
                text=result.get("transcript", ""),
                confidence=float(result.get("confidence", 0.0)),
                model_used=result.get("model_used", "unknown"),
                source_ref=source_ref,
                mime_type=mime_type,
                fallback=result.get("fallback", False),
                metadata={"language": result.get("language", "unknown")},
            )
        except Exception as exc:
            logger.warning("AudioParser 解析失败: %s", exc)
            return self._fallback(source_ref, mime_type, str(exc))

    def _resolve_audio_data(self, source_ref: str) -> Any:
        if not source_ref:
            return None
        if source_ref.startswith("file:///"):
            path = source_ref[8:]
            if os.path.isfile(path):
                return path
            logger.warning("AudioParser 文件不存在: %s", path)
            return None
        return source_ref

    def _fallback(self, source_ref: str, mime_type: str, reason: str) -> ParsedModality:
        return ParsedModality(
            modality="audio",
            text="[音频解析失败，无可用转写]",
            confidence=0.0,
            model_used="fallback",
            source_ref=source_ref,
            mime_type=mime_type,
            fallback=True,
            metadata={"error": reason},
        )


class VideoParser:
    """视频解析器 — 关键帧抽取 + ImageParser（降级方案）。

    ADR-074 §4.1: 完整 VLM 集成是后续工作。当前实现：
    1. 若 OPENAI_VISION_MODEL 可用，尝试用 ffmpeg 抽取关键帧 → ImageParser
    2. 否则返回降级占位（不阻塞流程，记录 fallback=True）
    """

    def __init__(self, image_parser: Optional[ImageParser] = None):
        self._image_parser = image_parser or ImageParser()

    def parse(self, source_ref: str, mime_type: str = "video/mp4") -> ParsedModality:
        # 尝试抽取关键帧
        frame_path = self._extract_key_frame(source_ref)
        if frame_path is None:
            return self._fallback(source_ref, mime_type, "frame_extraction_unavailable")

        try:
            # 用 ImageParser 解析关键帧
            frame_result = self._image_parser.parse(frame_path, "image/png")
            return ParsedModality(
                modality="video",
                text=frame_result.text,
                confidence=frame_result.confidence * 0.8,  # 视频降级置信度打折
                model_used=f"frame_extract+{frame_result.model_used}",
                source_ref=source_ref,
                mime_type=mime_type,
                fallback=frame_result.fallback,
                metadata={
                    "frame_path": frame_path,
                    "note": "基于关键帧的降级解析，完整 VLM 集成待后续",
                },
            )
        finally:
            # 清理临时帧文件（避免磁盘泄漏，M1 修复）
            try:
                if os.path.isfile(frame_path):
                    os.remove(frame_path)
            except OSError:
                pass

    def _extract_key_frame(self, source_ref: str) -> Optional[str]:
        """用 ffmpeg 抽取视频关键帧到唯一临时文件。失败返回 None。"""
        if not source_ref or not source_ref.startswith("file:///"):
            return None

        video_path = source_ref[8:]
        if not os.path.isfile(video_path):
            return None

        # 检查 ffmpeg 是否可用
        if shutil.which("ffmpeg") is None:
            logger.debug("ffmpeg 不可用，跳过关键帧抽取")
            return None

        # 使用 mkstemp 生成唯一临时文件（避免并发竞态，M1 修复）
        fd, frame_path = tempfile.mkstemp(suffix=".png", prefix="video_frame_")
        os.close(fd)  # 关闭文件描述符，由 ffmpeg 写入
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-i", video_path,
                    "-frames:v", "1",  # 抽取 1 帧
                    "-q:v", "2",
                    "-y",  # 覆盖
                    frame_path,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0 or not os.path.isfile(frame_path):
                os.remove(frame_path)
                return None
            return frame_path
        except Exception as exc:
            logger.debug("ffmpeg 关键帧抽取失败: %s", exc)
            try:
                os.remove(frame_path)
            except OSError:
                pass
            return None

    def _fallback(self, source_ref: str, mime_type: str, reason: str) -> ParsedModality:
        return ParsedModality(
            modality="video",
            text="[视频解析失败，VLM 集成待后续迭代]",
            confidence=0.0,
            model_used="fallback",
            source_ref=source_ref,
            mime_type=mime_type,
            fallback=True,
            metadata={"error": reason},
        )


# ------------------------------------------------------------------
# 路由器（MIME → Parser 策略表）
# ------------------------------------------------------------------


class MultimodalRouter:
    """按 MIME 类型分派到对应解析器。

    Usage:
        router = MultimodalRouter()
        result = router.route("image/png", "/path/to/image.png")
        # result: ParsedModality
    """

    def __init__(
        self,
        text_parser: Optional[TextParser] = None,
        image_parser: Optional[ImageParser] = None,
        audio_parser: Optional[AudioParser] = None,
        video_parser: Optional[VideoParser] = None,
    ):
        self._text = text_parser or TextParser()
        self._image = image_parser or ImageParser()
        self._audio = audio_parser or AudioParser()
        self._video = video_parser or VideoParser(self._image)

    def route(
        self,
        mime_type: str,
        source_ref: str,
        **kwargs: Any,
    ) -> ParsedModality:
        """按 MIME 类型路由到对应解析器。

        Args:
            mime_type: MIME 类型 (e.g. "text/plain", "image/png", "audio/wav", "video/mp4").
            source_ref: 数据引用（文本内容 / file:// 路径 / base64 / minio:// 引用）.
            **kwargs: 透传给解析器的额外参数.

        Returns:
            ParsedModality: 解析结果（失败时返回 fallback=True 的占位结果）.
        """
        if not mime_type:
            return ParsedModality(
                modality="unknown",
                text="",
                source_ref=source_ref,
                mime_type=mime_type,
                fallback=True,
                metadata={"error": "mime_type is required"},
            )

        mime_lower = mime_type.lower()
        parser = self._select_parser(mime_lower)
        return parser.parse(source_ref, mime_type=mime_lower)

    def _select_parser(self, mime_lower: str) -> Any:
        """策略表：MIME 前缀 → 解析器。"""
        if mime_lower.startswith("text/"):
            return self._text
        if mime_lower.startswith("image/"):
            return self._image
        if mime_lower.startswith("audio/"):
            return self._audio
        if mime_lower.startswith("video/"):
            return self._video
        # 未知 MIME — 当作文本处理（最宽容降级）
        logger.warning("未知 MIME 类型 %s，降级为文本处理", mime_lower)
        return self._text

    def route_batch(
        self,
        items: List[Dict[str, str]],
    ) -> List[ParsedModality]:
        """批量路由多个模态项。

        Args:
            items: [{"mime_type": "...", "source_ref": "..."}, ...]

        Returns:
            List[ParsedModality]: 与 items 等长的结果列表.
        """
        return [
            self.route(item.get("mime_type", ""), item.get("source_ref", ""))
            for item in items
        ]


# ------------------------------------------------------------------
# 结果归集器
# ------------------------------------------------------------------


class ResultAggregator:
    """归集多模态解析结果为统一文本 + 元数据。

    Usage:
        aggregator = ResultAggregator()
        result = aggregator.aggregate([parsed_text, parsed_image])
        # result.combined_text 可直接喂给 HE feed
    """

    def aggregate(self, modalities: List[ParsedModality]) -> AggregatedResult:
        """合并多个 ParsedModality 为 AggregatedResult。"""
        if not modalities:
            return AggregatedResult(combined_text="", total_confidence=0.0)

        # 按模态排序：text → image → audio → video（保证文本在前）
        order = {"text": 0, "image": 1, "audio": 2, "video": 3}
        sorted_mods = sorted(
            modalities, key=lambda m: order.get(m.modality, 99)
        )

        # 合并文本（每个模态带标签）
        text_parts: List[str] = []
        for mod in sorted_mods:
            if not mod.text:
                continue
            label = self._label_for(mod)
            text_parts.append(f"[{label}]\n{mod.text}")

        combined = "\n\n".join(text_parts)

        # 加权平均置信度（fallback 模态权重降低）
        total_weight = 0.0
        weighted_sum = 0.0
        for mod in sorted_mods:
            weight = 0.3 if mod.fallback else 1.0
            weighted_sum += mod.confidence * weight
            total_weight += weight
        avg_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

        all_fallback = all(m.fallback for m in sorted_mods)

        return AggregatedResult(
            combined_text=combined,
            modalities=sorted_mods,
            total_confidence=round(avg_confidence, 4),
            all_fallback=all_fallback,
        )

    def _label_for(self, mod: ParsedModality) -> str:
        labels = {
            "text": "原文",
            "image": "图像描述",
            "audio": "音频转写",
            "video": "视频描述",
        }
        label = labels.get(mod.modality, mod.modality)
        if mod.fallback:
            label += "（降级）"
        return label


# ------------------------------------------------------------------
# 模块级便捷函数
# ------------------------------------------------------------------


_router_singleton: Optional[MultimodalRouter] = None
_aggregator_singleton: Optional[ResultAggregator] = None


def get_multimodal_router() -> MultimodalRouter:
    """返回 MultimodalRouter 单例。"""
    global _router_singleton
    if _router_singleton is None:
        _router_singleton = MultimodalRouter()
    return _router_singleton


def get_result_aggregator() -> ResultAggregator:
    """返回 ResultAggregator 单例。"""
    global _aggregator_singleton
    if _aggregator_singleton is None:
        _aggregator_singleton = ResultAggregator()
    return _aggregator_singleton


__all__ = [
    "ParsedModality",
    "AggregatedResult",
    "TextParser",
    "ImageParser",
    "AudioParser",
    "VideoParser",
    "MultimodalRouter",
    "ResultAggregator",
    "get_multimodal_router",
    "get_result_aggregator",
]
