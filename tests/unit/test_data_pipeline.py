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
    def test_process_image_with_claude(self):
        proc = MultimodalProcessor(config={"image_model": ImageModel.CLAUDE})
        result = proc.process_image(b"fake-image-data")
        self.assertIn("model_used", result)
        self.assertEqual(result["model_used"], "claude")
        self.assertIn("description", result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_process_image_with_gpt4v(self):
        proc = MultimodalProcessor(config={"image_model": ImageModel.GPT4V})
        result = proc.process_image(b"fake-image-data")
        self.assertIn("model_used", result)
        self.assertEqual(result["model_used"], "gpt4v")

    def test_process_image_with_llava(self):
        proc = MultimodalProcessor(config={"image_model": ImageModel.LLAVA})
        result = proc.process_image(b"fake-image-data")
        self.assertIn("model_used", result)
        self.assertEqual(result["model_used"], "llava")

    def test_process_image_fallback(self):
        # LLaVA 不需要 API Key，所以会成功而非 fallback
        # 测试 fallback 方法本身的输出格式
        proc = MultimodalProcessor()
        result = proc._fallback_image_processing(b"fake-image-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")
        self.assertEqual(result["confidence"], 0.0)

    def test_process_image_with_model_param(self):
        proc = MultimodalProcessor()
        result = proc.process_image(b"data", model="llava")
        self.assertEqual(result["model_used"], "llava")


class TestProcessAudio(unittest.TestCase):
    """音频处理测试"""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_process_audio_with_whisper(self):
        proc = MultimodalProcessor(config={"audio_model": AudioModel.WHISPER})
        result = proc.process_audio(b"fake-audio-data")
        self.assertIn("model_used", result)
        self.assertEqual(result["model_used"], "whisper")
        self.assertIn("transcript", result)

    def test_process_audio_with_deepgram(self):
        proc = MultimodalProcessor(config={"audio_model": AudioModel.DEEPGRAM})
        result = proc.process_audio(b"fake-audio-data")
        self.assertEqual(result["model_used"], "deepgram")

    def test_process_audio_fallback(self):
        # Deepgram 不需要 API Key，所以会成功而非 fallback
        # 测试 fallback 方法本身的输出格式
        proc = MultimodalProcessor()
        result = proc._fallback_audio_processing(b"fake-audio-data")
        self.assertTrue(result.get("fallback", False))
        self.assertEqual(result["model_used"], "fallback")

    def test_process_audio_with_model_param(self):
        proc = MultimodalProcessor()
        result = proc.process_audio(b"data", model="deepgram")
        self.assertEqual(result["model_used"], "deepgram")


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
        self.assertEqual(result["confidence"], 0.0)

    def test_fallback_audio_result_format(self):
        proc = MultimodalProcessor()
        result = proc._fallback_audio_processing(b"data")
        self.assertIn("transcript", result)
        self.assertIn("language", result)
        self.assertIn("confidence", result)
        self.assertIn("model_used", result)
        self.assertIn("fallback", result)
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


if __name__ == "__main__":
    unittest.main()
