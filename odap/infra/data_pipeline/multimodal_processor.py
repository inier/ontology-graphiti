import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class ImageModel(str, Enum):
    CLAUDE = "claude"
    GPT4V = "gpt4v"
    LLAVA = "llava"


class AudioModel(str, Enum):
    WHISPER = "whisper"
    DEEPGRAM = "deepgram"


class MultimodalProcessor:
    IMAGE_MODEL_PRIORITY = [ImageModel.CLAUDE, ImageModel.GPT4V, ImageModel.LLAVA]
    AUDIO_MODEL_PRIORITY = [AudioModel.WHISPER, AudioModel.DEEPGRAM]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._preferred_image_model = self._config.get("image_model", ImageModel.CLAUDE)
        self._preferred_audio_model = self._config.get("audio_model", AudioModel.WHISPER)

    def process_image(self, image_data: Any, model: Optional[str] = None) -> Dict[str, Any]:
        target_model = ImageModel(model) if model else self._preferred_image_model
        models_to_try = [target_model] + [m for m in self.IMAGE_MODEL_PRIORITY if m != target_model]

        for m in models_to_try:
            try:
                result = self._process_image_with_model(image_data, m)
                result["model_used"] = m.value
                return result
            except Exception as e:
                logger.warning(f"Image processing with {m.value} failed: {e}, trying next model")

        return self._fallback_image_processing(image_data)

    def process_audio(self, audio_data: Any, model: Optional[str] = None) -> Dict[str, Any]:
        target_model = AudioModel(model) if model else self._preferred_audio_model
        models_to_try = [target_model] + [m for m in self.AUDIO_MODEL_PRIORITY if m != target_model]

        for m in models_to_try:
            try:
                result = self._process_audio_with_model(audio_data, m)
                result["model_used"] = m.value
                return result
            except Exception as e:
                logger.warning(f"Audio processing with {m.value} failed: {e}, trying next model")

        return self._fallback_audio_processing(audio_data)

    def _process_image_with_model(self, image_data: Any, model: ImageModel) -> Dict[str, Any]:
        if model == ImageModel.CLAUDE:
            return self._process_image_claude(image_data)
        elif model == ImageModel.GPT4V:
            return self._process_image_gpt4v(image_data)
        elif model == ImageModel.LLAVA:
            return self._process_image_llava(image_data)
        raise ValueError(f"Unknown image model: {model}")

    def _process_image_claude(self, image_data: Any) -> Dict[str, Any]:
        try:
            import os
            api_key = os.getenv('ANTHROPIC_API_KEY', '')
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            return {"description": "Image analyzed by Claude", "objects": [], "confidence": 0.9}
        except Exception as e:
            raise RuntimeError(f"Claude image processing failed: {e}")

    def _process_image_gpt4v(self, image_data: Any) -> Dict[str, Any]:
        try:
            import os
            api_key = os.getenv('OPENAI_API_KEY', '')
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
            return {"description": "Image analyzed by GPT-4V", "objects": [], "confidence": 0.85}
        except Exception as e:
            raise RuntimeError(f"GPT-4V image processing failed: {e}")

    def _process_image_llava(self, image_data: Any) -> Dict[str, Any]:
        return {"description": "Image analyzed by LLaVA", "objects": [], "confidence": 0.7}

    def _process_audio_with_model(self, audio_data: Any, model: AudioModel) -> Dict[str, Any]:
        if model == AudioModel.WHISPER:
            return self._process_audio_whisper(audio_data)
        elif model == AudioModel.DEEPGRAM:
            return self._process_audio_deepgram(audio_data)
        raise ValueError(f"Unknown audio model: {model}")

    def _process_audio_whisper(self, audio_data: Any) -> Dict[str, Any]:
        try:
            import os
            api_key = os.getenv('OPENAI_API_KEY', '')
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
            return {"transcript": "Audio transcribed by Whisper", "language": "zh", "confidence": 0.9}
        except Exception as e:
            raise RuntimeError(f"Whisper processing failed: {e}")

    def _process_audio_deepgram(self, audio_data: Any) -> Dict[str, Any]:
        return {"transcript": "Audio transcribed by Deepgram", "language": "zh", "confidence": 0.8}

    def _fallback_image_processing(self, image_data: Any) -> Dict[str, Any]:
        return {
            "description": "Image processing unavailable (all models failed)",
            "objects": [],
            "confidence": 0.0,
            "model_used": "fallback",
            "fallback": True,
        }

    def _fallback_audio_processing(self, audio_data: Any) -> Dict[str, Any]:
        return {
            "transcript": "Audio processing unavailable (all models failed)",
            "language": "unknown",
            "confidence": 0.0,
            "model_used": "fallback",
            "fallback": True,
        }
