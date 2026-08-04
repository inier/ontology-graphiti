"""Iter 4.1: Multimodal router + parsers + aggregator tests.

Tests cover:
- TextParser: passthrough, file:// reading, empty input
- ImageParser: mocked processor success, processor unavailable fallback
- AudioParser: mocked processor success, processor unavailable fallback
- VideoParser: ffmpeg unavailable fallback, mocked frame extraction
- MultimodalRouter: MIME dispatch, unknown MIME, empty MIME, batch routing
- ResultAggregator: single, multiple, all fallback, empty, ordering
- process_multimodal_impl: text short-circuit, image routing, error handling
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from odap.infra.data_pipeline.multimodal_router import (
    AggregatedResult,
    AudioParser,
    ImageParser,
    MultimodalRouter,
    ParsedModality,
    ResultAggregator,
    TextParser,
    VideoParser,
    get_multimodal_router,
    get_result_aggregator,
)


# ------------------------------------------------------------------
# TextParser
# ------------------------------------------------------------------


class TestTextParser:
    def test_parse_returns_text_unchanged(self):
        parser = TextParser()
        result = parser.parse("hello world")
        assert result.modality == "text"
        assert result.text == "hello world"
        assert result.confidence == 1.0
        assert result.model_used == "passthrough"
        assert result.fallback is False

    def test_parse_empty_string(self):
        parser = TextParser()
        result = parser.parse("")
        assert result.text == ""
        assert result.confidence == 1.0

    def test_parse_file_protocol_reads_file(self, tmp_path):
        test_file = tmp_path / "input.txt"
        test_file.write_text("content from file", encoding="utf-8")
        parser = TextParser()
        result = parser.parse(f"file:///{test_file}")
        assert result.text == "content from file"
        assert result.fallback is False

    def test_parse_file_protocol_missing_file_falls_back(self):
        """C1 修复：文件读取失败返回空文本 + fallback=True（不污染下游 HE KA）。"""
        parser = TextParser()
        result = parser.parse("file:///nonexistent/path.txt")
        assert result.fallback is True
        assert result.text == ""
        assert result.confidence == 0.0

    def test_parse_metadata_includes_char_count(self):
        parser = TextParser()
        result = parser.parse("abc")
        assert result.metadata["char_count"] == 3


# ------------------------------------------------------------------
# ImageParser
# ------------------------------------------------------------------


class TestImageParser:
    def test_parse_success_with_mock_processor(self):
        mock_processor = MagicMock()
        mock_processor.process_image.return_value = {
            "description": "A cat sitting on a mat",
            "objects": [{"name": "cat", "confidence": 0.95}],
            "confidence": 0.9,
            "model_used": "claude",
            "fallback": False,
        }
        parser = ImageParser(processor=mock_processor)
        result = parser.parse("base64data", "image/png")

        assert result.modality == "image"
        assert result.text == "A cat sitting on a mat"
        assert result.confidence == 0.9
        assert result.model_used == "claude"
        assert result.fallback is False
        assert result.metadata["objects"] == [{"name": "cat", "confidence": 0.95}]

    def test_parse_processor_unavailable_returns_fallback(self):
        parser = ImageParser(processor=None)
        # Force _get_processor to return None
        with patch.object(parser, "_get_processor", return_value=None):
            result = parser.parse("data", "image/png")

        assert result.modality == "image"
        assert result.fallback is True
        assert result.confidence == 0.0
        assert result.model_used == "fallback"

    def test_parse_processor_raises_returns_fallback(self):
        mock_processor = MagicMock()
        mock_processor.process_image.side_effect = RuntimeError("API error")
        parser = ImageParser(processor=mock_processor)
        result = parser.parse("data", "image/png")

        assert result.fallback is True
        assert "API error" in result.metadata["error"]

    def test_parse_empty_source_ref(self):
        mock_processor = MagicMock()
        parser = ImageParser(processor=mock_processor)
        result = parser.parse("", "image/png")

        assert result.fallback is True
        assert "invalid_image_data" in result.metadata["error"]
        mock_processor.process_image.assert_not_called()

    def test_parse_file_protocol_existing_file(self, tmp_path):
        img_file = tmp_path / "photo.png"
        img_file.write_bytes(b"\x89PNG fake data")
        mock_processor = MagicMock()
        mock_processor.process_image.return_value = {
            "description": "desc",
            "confidence": 0.8,
            "model_used": "gpt4v",
            "fallback": False,
        }
        parser = ImageParser(processor=mock_processor)
        result = parser.parse(f"file:///{img_file}", "image/png")

        assert result.fallback is False
        mock_processor.process_image.assert_called_once_with(str(img_file))


# ------------------------------------------------------------------
# AudioParser
# ------------------------------------------------------------------


class TestAudioParser:
    def test_parse_success_with_mock_processor(self):
        mock_processor = MagicMock()
        mock_processor.process_audio.return_value = {
            "transcript": "hello world",
            "language": "en",
            "confidence": 0.9,
            "model_used": "whisper",
            "fallback": False,
        }
        parser = AudioParser(processor=mock_processor)
        result = parser.parse("base64audio", "audio/wav")

        assert result.modality == "audio"
        assert result.text == "hello world"
        assert result.confidence == 0.9
        assert result.model_used == "whisper"
        assert result.metadata["language"] == "en"

    def test_parse_processor_unavailable_returns_fallback(self):
        parser = AudioParser(processor=None)
        with patch.object(parser, "_get_processor", return_value=None):
            result = parser.parse("data", "audio/wav")

        assert result.fallback is True
        assert result.confidence == 0.0

    def test_parse_processor_raises_returns_fallback(self):
        mock_processor = MagicMock()
        mock_processor.process_audio.side_effect = RuntimeError("ASR error")
        parser = AudioParser(processor=mock_processor)
        result = parser.parse("data", "audio/wav")

        assert result.fallback is True
        assert "ASR error" in result.metadata["error"]

    def test_parse_empty_source_ref(self):
        mock_processor = MagicMock()
        parser = AudioParser(processor=mock_processor)
        result = parser.parse("", "audio/wav")

        assert result.fallback is True
        mock_processor.process_audio.assert_not_called()


# ------------------------------------------------------------------
# VideoParser
# ------------------------------------------------------------------


class TestVideoParser:
    def test_parse_no_file_protocol_returns_fallback(self):
        parser = VideoParser()
        result = parser.parse("base64data", "video/mp4")

        assert result.modality == "video"
        assert result.fallback is True

    def test_parse_ffmpeg_unavailable_returns_fallback(self, tmp_path):
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video")
        parser = VideoParser()
        with patch("shutil.which", return_value=None):
            result = parser.parse(f"file:///{video_file}", "video/mp4")

        assert result.fallback is True
        assert "frame_extraction_unavailable" in result.metadata["error"]

    def test_parse_with_mocked_frame_extraction(self, tmp_path):
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video")
        frame_file = tmp_path / "frame.png"
        frame_file.write_bytes(b"\x89PNG fake frame")

        mock_image_parser = MagicMock()
        mock_image_parser.parse.return_value = ParsedModality(
            modality="image",
            text="Video frame shows a car",
            confidence=0.85,
            model_used="claude",
            source_ref=str(frame_file),
            mime_type="image/png",
            fallback=False,
        )

        parser = VideoParser(image_parser=mock_image_parser)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("os.path.isfile", return_value=True):
                result = parser.parse(f"file:///{video_file}", "video/mp4")

        assert result.modality == "video"
        assert result.text == "Video frame shows a car"
        assert result.confidence == pytest.approx(0.68, abs=0.01)  # 0.85 * 0.8
        assert "frame_extract+claude" == result.model_used


# ------------------------------------------------------------------
# MultimodalRouter
# ------------------------------------------------------------------


class TestMultimodalRouter:
    def test_route_text_delegates_to_text_parser(self):
        router = MultimodalRouter()
        result = router.route("text/plain", "hello")
        assert result.modality == "text"
        assert result.text == "hello"

    def test_route_image_delegates_to_image_parser(self):
        mock_processor = MagicMock()
        mock_processor.process_image.return_value = {
            "description": "desc",
            "confidence": 0.9,
            "model_used": "claude",
            "fallback": False,
        }
        router = MultimodalRouter(image_parser=ImageParser(processor=mock_processor))
        result = router.route("image/png", "data")
        assert result.modality == "image"
        assert result.text == "desc"

    def test_route_audio_delegates_to_audio_parser(self):
        mock_processor = MagicMock()
        mock_processor.process_audio.return_value = {
            "transcript": "transcript",
            "confidence": 0.9,
            "model_used": "whisper",
            "fallback": False,
        }
        router = MultimodalRouter(audio_parser=AudioParser(processor=mock_processor))
        result = router.route("audio/wav", "data")
        assert result.modality == "audio"
        assert result.text == "transcript"

    def test_route_video_delegates_to_video_parser(self):
        mock_video = MagicMock()
        mock_video.parse.return_value = ParsedModality(
            modality="video", text="video desc", confidence=0.7
        )
        router = MultimodalRouter(video_parser=mock_video)
        result = router.route("video/mp4", "data")
        assert result.modality == "video"
        mock_video.parse.assert_called_once()

    def test_route_unknown_mime_degrades_to_text(self):
        router = MultimodalRouter()
        result = router.route("application/json", '{"key": "value"}')
        assert result.modality == "text"
        assert result.text == '{"key": "value"}'

    def test_route_empty_mime_returns_fallback(self):
        router = MultimodalRouter()
        result = router.route("", "data")
        assert result.modality == "unknown"
        assert result.fallback is True

    def test_route_batch_returns_list(self):
        router = MultimodalRouter()
        items = [
            {"mime_type": "text/plain", "source_ref": "text1"},
            {"mime_type": "text/plain", "source_ref": "text2"},
        ]
        results = router.route_batch(items)
        assert len(results) == 2
        assert results[0].text == "text1"
        assert results[1].text == "text2"

    def test_route_batch_empty_items(self):
        router = MultimodalRouter()
        results = router.route_batch([])
        assert results == []

    def test_mime_type_is_lowercased(self):
        router = MultimodalRouter()
        result = router.route("TEXT/PLAIN", "hello")
        assert result.modality == "text"
        assert result.mime_type == "text/plain"


# ------------------------------------------------------------------
# ResultAggregator
# ------------------------------------------------------------------


class TestResultAggregator:
    def test_aggregate_empty_list(self):
        agg = ResultAggregator()
        result = agg.aggregate([])
        assert result.combined_text == ""
        assert result.total_confidence == 0.0
        assert result.modalities == []

    def test_aggregate_single_text(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="text", text="hello", confidence=1.0)
        ])
        assert "hello" in result.combined_text
        assert result.total_confidence == 1.0
        assert result.all_fallback is False

    def test_aggregate_multiple_modalities(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="image", text="image desc", confidence=0.8),
            ParsedModality(modality="text", text="main text", confidence=1.0),
        ])
        # text should come before image
        assert result.combined_text.index("main text") < result.combined_text.index("image desc")
        assert result.total_confidence > 0
        assert len(result.modalities) == 2

    def test_aggregate_all_fallback(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="image", text="fail1", confidence=0.0, fallback=True),
            ParsedModality(modality="audio", text="fail2", confidence=0.0, fallback=True),
        ])
        assert result.all_fallback is True
        # fallback modalities have lower weight
        assert result.total_confidence == 0.0

    def test_aggregate_mixed_fallback(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="text", text="ok", confidence=1.0, fallback=False),
            ParsedModality(modality="image", text="fail", confidence=0.5, fallback=True),
        ])
        assert result.all_fallback is False
        # text has weight 1.0, image has weight 0.3
        # weighted: (1.0*1.0 + 0.5*0.3) / (1.0 + 0.3) = 1.15 / 1.3
        assert result.total_confidence == pytest.approx(0.8846, abs=0.01)

    def test_aggregate_labels_modalities(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="text", text="content", confidence=1.0),
        ])
        assert "[原文]" in result.combined_text

    def test_aggregate_skips_empty_text(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="text", text="", confidence=1.0),
            ParsedModality(modality="image", text="img desc", confidence=0.8),
        ])
        assert "原文" not in result.combined_text
        assert "图像描述" in result.combined_text

    def test_aggregate_fallback_label(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="image", text="fail", confidence=0.0, fallback=True),
        ])
        assert "（降级）" in result.combined_text

    def test_aggregate_ordering_text_image_audio_video(self):
        agg = ResultAggregator()
        result = agg.aggregate([
            ParsedModality(modality="video", text="v", confidence=0.5),
            ParsedModality(modality="audio", text="a", confidence=0.5),
            ParsedModality(modality="image", text="i", confidence=0.5),
            ParsedModality(modality="text", text="t", confidence=0.5),
        ])
        # Verify order: text → image → audio → video
        order = [m.modality for m in result.modalities]
        assert order == ["text", "image", "audio", "video"]


# ------------------------------------------------------------------
# Singletons
# ------------------------------------------------------------------


class TestSingletons:
    def test_get_multimodal_router_returns_instance(self):
        router = get_multimodal_router()
        assert isinstance(router, MultimodalRouter)

    def test_get_result_aggregator_returns_instance(self):
        agg = get_result_aggregator()
        assert isinstance(agg, ResultAggregator)


# ------------------------------------------------------------------
# ParsedModality / AggregatedResult serialization
# ------------------------------------------------------------------


class TestDataclasses:
    def test_parsed_modality_to_dict(self):
        mod = ParsedModality(
            modality="text", text="hello", confidence=0.9,
            model_used="passthrough", source_ref="ref", mime_type="text/plain",
            fallback=False, metadata={"key": "value"},
        )
        d = mod.to_dict()
        assert d["modality"] == "text"
        assert d["text"] == "hello"
        assert d["confidence"] == 0.9
        assert d["metadata"] == {"key": "value"}

    def test_aggregated_result_to_dict(self):
        result = AggregatedResult(
            combined_text="text",
            modalities=[ParsedModality(modality="text", text="text", confidence=1.0)],
            total_confidence=0.95,
            all_fallback=False,
        )
        d = result.to_dict()
        assert d["combined_text"] == "text"
        assert d["modality_count"] == 1
        assert d["total_confidence"] == 0.95
        assert len(d["modalities"]) == 1


# ------------------------------------------------------------------
# process_multimodal_impl integration
# ------------------------------------------------------------------


class TestProcessMultimodalImpl:
    def test_text_short_circuits_to_feed_he_kb(self):
        """Text MIME type should bypass MultimodalRouter and go directly to feed_he_kb."""
        from odap.infra.queue.tasks import process_multimodal_impl
        with patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok", "session_id": "test"}
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="hello text",
                mime_type="text/plain",
                ontology_id="ont1",
            )
        assert result["status"] == "ok"
        mock_feed.assert_called_once()
        call_kwargs = mock_feed.call_args
        assert call_kwargs.kwargs["text"] == "hello text"

    def test_text_uses_kwargs_text_when_provided(self):
        from odap.infra.queue.tasks import process_multimodal_impl
        with patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok"}
            process_multimodal_impl(
                workspace_id="ws1",
                source_ref="ignored",
                mime_type="text/plain",
                text="actual text",
                ontology_id="ont1",
            )
        assert mock_feed.call_args.kwargs["text"] == "actual text"

    def test_empty_mime_returns_error(self):
        from odap.infra.queue.tasks import process_multimodal_impl
        result = process_multimodal_impl(
            workspace_id="ws1",
            source_ref="data",
            mime_type="",
        )
        assert result["status"] == "error"
        assert "mime_type is required" in result["message"]

    def test_image_routes_through_multimodal_router(self):
        """Image MIME type should go through MultimodalRouter → feed_he_kb."""
        from odap.infra.queue.tasks import process_multimodal_impl

        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="image", text="image description", confidence=0.9,
            model_used="claude", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="[图像描述]\nimage description",
            modalities=[],
            total_confidence=0.9,
        )

        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok", "session_id": "img_session"}
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="base64data",
                mime_type="image/png",
                ontology_id="ont1",
            )

        assert result["status"] == "success"
        assert result["modality"] == "image"
        assert result["model_used"] == "claude"
        assert result["confidence"] == 0.9
        assert result["fallback"] is False
        mock_router.route.assert_called_once_with("image/png", "base64data")
        mock_feed.assert_called_once()

    def test_image_with_empty_parsed_text_returns_error(self):
        from odap.infra.queue.tasks import process_multimodal_impl

        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="image", text="", confidence=0.0, fallback=True,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="", modalities=[], total_confidence=0.0,
        )

        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ):
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="data",
                mime_type="image/png",
            )

        assert result["status"] == "error"
        assert "跳过 HE 喂入" in result["message"]

    def test_all_fallback_does_not_feed_he_kb(self):
        """C2 修复：所有模态降级时，即使 combined_text 非空（占位文本）也不喂 HE KA。"""
        from odap.infra.queue.tasks import process_multimodal_impl

        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="image", text="[图像解析失败，无可用描述]",
            confidence=0.0, model_used="fallback", fallback=True,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="[图像描述（降级）]\n[图像解析失败，无可用描述]",
            modalities=[], total_confidence=0.0,
            all_fallback=True,  # 关键：全降级
        )

        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="data",
                mime_type="image/png",
            )

        assert result["status"] == "error"
        assert result["fallback"] is True
        assert "跳过 HE 喂入" in result["message"]
        mock_feed.assert_not_called()  # 关键：不应喂入 HE KA

    def test_router_exception_returns_error(self):
        from odap.infra.queue.tasks import process_multimodal_impl

        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            side_effect=RuntimeError("init failed"),
        ):
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="data",
                mime_type="image/png",
            )

        assert result["status"] == "error"
        assert "init failed" in result["message"]

    def test_audio_routes_through_router(self):
        from odap.infra.queue.tasks import process_multimodal_impl

        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="audio", text="transcript text", confidence=0.85,
            model_used="whisper", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="[音频转写]\ntranscript text",
            modalities=[], total_confidence=0.85,
        )

        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok"}
            result = process_multimodal_impl(
                workspace_id="ws1",
                source_ref="audio_data",
                mime_type="audio/wav",
                ontology_id="ont1",
            )

        assert result["status"] == "success"
        assert result["modality"] == "audio"
        mock_router.route.assert_called_once_with("audio/wav", "audio_data")
