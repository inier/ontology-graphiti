import logging
import base64
import os
from typing import Dict, Any, Optional, List
from enum import Enum

from odap.infra.config_composer import get_config

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
        api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        import httpx

        base64_image = self._encode_image(image_data)
        api_base = os.getenv('ANTHROPIC_API_BASE', 'https://api.anthropic.com')

        with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = client.post(
                f"{api_base}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": base64_image,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Describe this image in detail. List any objects detected and provide a confidence assessment.",
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()

        content_blocks = data.get("content", [])
        description = ""
        for block in content_blocks:
            if block.get("type") == "text":
                description += block.get("text", "")

        return {
            "description": description.strip() or "Image processed by Claude",
            "objects": [],
            "confidence": 0.9,
        }

    def _process_image_gpt4v(self, image_data: Any) -> Dict[str, Any]:
        api_key = get_config("llm.api_key", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        import httpx

        base64_image = self._encode_image(image_data)
        api_base = get_config("llm.api_base", "https://api.openai.com/v1")
        model = os.getenv('OPENAI_VISION_MODEL', 'gpt-4o')

        with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Describe this image in detail. List any objects detected and provide a confidence assessment.",
                                },
                            ],
                        }
                    ],
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()

        description = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return {
            "description": description.strip() or "Image processed by GPT-4V",
            "objects": [],
            "confidence": 0.85,
        }

    def _process_image_llava(self, image_data: Any) -> Dict[str, Any]:
        llava_url = os.getenv('LLAVA_API_URL', '')
        if not llava_url:
            raise RuntimeError("LLAVA_API_URL not set, LLaVA service not available")

        import httpx

        base64_image = self._encode_image(image_data)

        with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = client.post(
                llava_url,
                json={
                    "image": base64_image,
                    "prompt": "Describe this image in detail.",
                },
            )
            response.raise_for_status()
            data = response.json()

        description = data.get("description", data.get("text", ""))

        return {
            "description": description.strip() or "Image processed by LLaVA",
            "objects": [],
            "confidence": 0.7,
        }

    def _process_audio_with_model(self, audio_data: Any, model: AudioModel) -> Dict[str, Any]:
        if model == AudioModel.WHISPER:
            return self._process_audio_whisper(audio_data)
        elif model == AudioModel.DEEPGRAM:
            return self._process_audio_deepgram(audio_data)
        raise ValueError(f"Unknown audio model: {model}")

    def _process_audio_whisper(self, audio_data: Any) -> Dict[str, Any]:
        api_key = get_config("llm.api_key", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        import httpx

        api_base = get_config("llm.api_base", "https://api.openai.com/v1")
        audio_bytes = self._get_audio_bytes(audio_data)

        with httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            response = client.post(
                f"{api_base}/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                files={
                    "file": ("audio.wav", audio_bytes, "audio/wav"),
                },
                data={
                    "model": "whisper-1",
                    "response_format": "verbose_json",
                },
            )
            response.raise_for_status()
            data = response.json()

        return {
            "transcript": data.get("text", ""),
            "language": data.get("language", "unknown"),
            "confidence": 0.9,
        }

    def _process_audio_deepgram(self, audio_data: Any) -> Dict[str, Any]:
        api_key = os.getenv('DEEPGRAM_API_KEY', '')
        if not api_key:
            raise RuntimeError("DEEPGRAM_API_KEY not set, Deepgram service not available")

        import httpx

        audio_bytes = self._get_audio_bytes(audio_data)

        with httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            response = client.post(
                "https://api.deepgram.com/v1/listen?punctuate=true",
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "audio/wav",
                },
                content=audio_bytes,
            )
            response.raise_for_status()
            data = response.json()

        channel = data.get("results", {}).get("channels", [{}])[0]
        alternative = channel.get("alternatives", [{}])[0]
        transcript = alternative.get("transcript", "")
        language = data.get("results", {}).get("language", "unknown")

        return {
            "transcript": transcript,
            "language": language,
            "confidence": 0.8,
        }

    def _encode_image(self, image_data: Any) -> str:
        if isinstance(image_data, str):
            if os.path.isfile(image_data):
                with open(image_data, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            return image_data
        if isinstance(image_data, bytes):
            return base64.b64encode(image_data).decode("utf-8")
        raise ValueError(f"Unsupported image_data type: {type(image_data)}")

    def _get_audio_bytes(self, audio_data: Any) -> bytes:
        if isinstance(audio_data, bytes):
            return audio_data
        if isinstance(audio_data, str):
            if os.path.isfile(audio_data):
                with open(audio_data, "rb") as f:
                    return f.read()
            import base64
            try:
                return base64.b64decode(audio_data)
            except Exception:
                raise ValueError("audio_data string is neither a file path nor valid base64")
        raise ValueError(f"Unsupported audio_data type: {type(audio_data)}")

    def _fallback_image_processing(self, image_data: Any) -> Dict[str, Any]:
        return {
            "status": "error",
            "message": "Image processing unavailable (all models failed)",
            "description": "",
            "objects": [],
            "confidence": 0.0,
            "model_used": "fallback",
            "fallback": True,
        }

    def _fallback_audio_processing(self, audio_data: Any) -> Dict[str, Any]:
        return {
            "status": "error",
            "message": "Audio processing unavailable (all models failed)",
            "transcript": "",
            "language": "unknown",
            "confidence": 0.0,
            "model_used": "fallback",
            "fallback": True,
        }
