"""MultimodalProcessor 单元测试"""

import unittest
from unittest.mock import patch, MagicMock
import os

from odap.infra.data_pipeline.multimodal_processor import (
    MultimodalProcessor,
    ImageModel,
    AudioModel,
)


class TestImageModel(unittest.TestCase):
    """ImageModel 枚举测试"""

    def test_is_str_enum(self):
        self.assertIsInstance(ImageModel.CLAUDE, str)
        self.assertEqual(ImageModel.CLAUDE, "claude")

    def test_all_values(self):
        expected = ["claude", "gpt4v", "llava"]
        actual = [m.value for m in ImageModel]
        self.assertEqual(actual, expected)


class TestAudioModel(unittest.TestCase):
    """AudioModel 枚举测试"""

    def test_is_str_enum(self):
        self.assertIsInstance(AudioModel.WHISPER, str)
        self.assertEqual(AudioModel.WHISPER, "whisper")

    def test_all_values(self):
        expected = ["whisper", "deepgram"]
        actual = [m.value for m in AudioModel]
        self.assertEqual(actual, expected)


class TestMultimodalProcessorInit(unittest.TestCase):
    """初始化测试"""

    def test_default_config(self):
        proc = MultimodalProcessor()
        self.assertEqual(proc._preferred_image_model, ImageModel.CLAUDE)
        self.assertEqual(proc._preferred_audio_model, AudioModel.WHISPER)

    def test_custom_config(self):
        proc = MultimodalProcessor(config={
            "image_model": ImageModel.GPT4V,
            "audio_model": AudioModel.DEEPGRAM,
        })
        self.assertEqual(proc._preferred_image_model, ImageModel.GPT4V)
        self.assertEqual(proc._preferred_audio_model, AudioModel.DEEPGRAM)


class TestProcessImage(unittest.TestCase):
    """图像处理测试"""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_process_image_with_claude_mock_api(self):
        """测试 Claude 图像处理 - mock httpx 调用"""
        proc = MultimodalProcessor(config={"image_model": ImageModel.CLAUDE})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "A test image description"}]
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = proc.process_image(b"fake-image-data")
        self.assertEqual(result["model_used"], "claude")
        self.assertIn("description", result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_process_image_with_gpt4v_mock_api(self):
        """测试 GPT-4V 图像处理 - mock httpx 调用"""
        proc = MultimodalProcessor(config={"image_model": ImageModel.GPT4V})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "A test image description"}}]
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        def mock_get_config(key, default=""):
            if key == "llm.api_key":
                return "test-key"
            return default

        with patch("httpx.Client", return_value=mock_client), \
             patch("odap.infra.data_pipeline.multimodal_processor.get_config", side_effect=mock_get_config):
            result = proc.process_image(b"fake-image-data")
        self.assertEqual(result["model_used"], "gpt4v")
        self.assertIn("description", result)

    @patch.dict(os.environ, {"LLAVA_API_URL": "http://localhost:8080/api"})
    def test_process_image_with_llava_mock_api(self):
        """测试 LLaVA 图像处理 - mock httpx 调用"""
        proc = MultimodalProcessor(config={"image_model": ImageModel.LLAVA})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"description": "A test image from LLaVA"}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = proc.process_image(b"fake-image-data")
        self.assertEqual(result["model_used"], "llava")
        self.assertIn("description", result)

    def test_process_image_no_api_key_falls_back(self):
        """测试无 API Key 时降级到 fallback"""
        proc = MultimodalProcessor()
        # 所有模型都需要 API Key/URL，无 Key 时应全部失败并 fallback
        result = proc.process_image(b"fake-image-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")

    def test_process_image_fallback_format(self):
        """测试 fallback 输出格式"""
        proc = MultimodalProcessor()
        result = proc._fallback_image_processing(b"fake-image-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "error")


class TestProcessAudio(unittest.TestCase):
    """音频处理测试"""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_process_audio_with_whisper_mock_api(self):
        """测试 Whisper 音频处理 - mock httpx 调用"""
        proc = MultimodalProcessor(config={"audio_model": AudioModel.WHISPER})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "text": "Test transcription",
            "language": "zh",
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        def mock_get_config(key, default=""):
            if key == "llm.api_key":
                return "test-key"
            return default

        with patch("httpx.Client", return_value=mock_client), \
             patch("odap.infra.data_pipeline.multimodal_processor.get_config", side_effect=mock_get_config):
            result = proc.process_audio(b"fake-audio-data")
        self.assertEqual(result["model_used"], "whisper")
        self.assertIn("transcript", result)

    @patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key"})
    def test_process_audio_with_deepgram_mock_api(self):
        """测试 Deepgram 音频处理 - mock httpx 调用"""
        proc = MultimodalProcessor(config={"audio_model": AudioModel.DEEPGRAM})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "channels": [{"alternatives": [{"transcript": "Test deepgram transcription"}]}],
                "language": "en",
            }
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = proc.process_audio(b"fake-audio-data")
        self.assertEqual(result["model_used"], "deepgram")
        self.assertIn("transcript", result)

    def test_process_audio_no_api_key_falls_back(self):
        """测试无 API Key 时降级到 fallback"""
        proc = MultimodalProcessor()
        result = proc.process_audio(b"fake-audio-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")

    def test_process_audio_fallback_format(self):
        """测试 fallback 输出格式"""
        proc = MultimodalProcessor()
        result = proc._fallback_audio_processing(b"fake-audio-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")
        self.assertIn("status", result)
        self.assertEqual(result["status"], "error")


class TestFallbackProcessing(unittest.TestCase):
    """回退处理测试"""

    def test_fallback_image_result_format(self):
        proc = MultimodalProcessor()
        result = proc._fallback_image_processing(b"data")
        self.assertIn("description", result)
        self.assertIn("objects", result)
        self.assertIn("confidence", result)
        self.assertIn("model_used", result)
        self.assertIn("fallback", result)
        self.assertIn("status", result)
        self.assertEqual(result["confidence"], 0.0)

    def test_fallback_audio_result_format(self):
        proc = MultimodalProcessor()
        result = proc._fallback_audio_processing(b"data")
        self.assertIn("transcript", result)
        self.assertIn("language", result)
        self.assertIn("confidence", result)
        self.assertIn("model_used", result)
        self.assertIn("fallback", result)
        self.assertIn("status", result)
        self.assertEqual(result["confidence"], 0.0)


class TestModelPriority(unittest.TestCase):
    """模型优先级测试"""

    def test_image_model_priority(self):
        self.assertEqual(
            MultimodalProcessor.IMAGE_MODEL_PRIORITY,
            [ImageModel.CLAUDE, ImageModel.GPT4V, ImageModel.LLAVA],
        )

    def test_audio_model_priority(self):
        self.assertEqual(
            MultimodalProcessor.AUDIO_MODEL_PRIORITY,
            [AudioModel.WHISPER, AudioModel.DEEPGRAM],
        )


class TestEncodeHelpers(unittest.TestCase):
    """编码辅助方法测试"""

    def test_encode_image_bytes(self):
        proc = MultimodalProcessor()
        import base64
        result = proc._encode_image(b"test-data")
        self.assertEqual(result, base64.b64encode(b"test-data").decode("utf-8"))

    def test_encode_image_base64_string(self):
        proc = MultimodalProcessor()
        # Already base64 string should pass through
        result = proc._encode_image("alreadybase64data")
        self.assertEqual(result, "alreadybase64data")

    def test_encode_image_invalid_type(self):
        proc = MultimodalProcessor()
        with self.assertRaises(ValueError):
            proc._encode_image(12345)

    def test_get_audio_bytes_bytes(self):
        proc = MultimodalProcessor()
        result = proc._get_audio_bytes(b"audio-data")
        self.assertEqual(result, b"audio-data")

    def test_get_audio_bytes_invalid_type(self):
        proc = MultimodalProcessor()
        with self.assertRaises(ValueError):
            proc._get_audio_bytes(12345)


if __name__ == "__main__":
    unittest.main()
