"""
配置组合引擎 - 对齐 docs/03-modules/infra/DESIGN.md

配置分层:
- L0: 系统默认配置
- L1: 环境变量覆盖
- L2: 配置文件 (YAML/JSON)
- L3: 工作空间级配置
- L4: 用户级配置

优先级: L4 > L3 > L2 > L1 > L0
"""

import os
import json
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy


class ConfigLayer(int, Enum):
    SYSTEM = 0
    ENV = 1
    FILE = 2
    WORKSPACE = 3
    USER = 4


@dataclass
class ConfigSchema:
    key: str
    type: type
    default: Any = None
    required: bool = False
    description: str = ""
    choices: Optional[List[Any]] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    sensitive: bool = False
    layer: ConfigLayer = ConfigLayer.FILE

    def validate(self, value: Any) -> bool:
        if value is None and self.required:
            return False
        if value is not None:
            if self.choices and value not in self.choices:
                return False
            if self.min_val is not None and isinstance(value, (int, float)) and value < self.min_val:
                return False
            if self.max_val is not None and isinstance(value, (int, float)) and value > self.max_val:
                return False
        return True


@dataclass
class ConfigValidationError:
    key: str
    message: str
    layer: ConfigLayer = ConfigLayer.FILE


def deep_merge(base: Dict, override: Dict) -> Dict:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ConfigurationComposer:
    """配置组合引擎"""

    def __init__(self):
        self._schema: Dict[str, ConfigSchema] = {}
        self._layers: Dict[int, Dict[str, Dict]] = {i: {} for i in range(5)}
        self._lock = threading.RLock()
        self._init_system_defaults()
        self._load_env_layer()

    def _init_system_defaults(self):
        defaults = {
            "server.host": ConfigSchema("server.host", str, "0.0.0.0", description="服务监听地址"),
            "server.port": ConfigSchema("server.port", int, 8000, description="服务端口", min_val=1, max_val=65535),
            "server.debug": ConfigSchema("server.debug", bool, False, description="调试模式"),
            "llm.provider": ConfigSchema("llm.provider", str, "openai", choices=["openai", "azure", "local"]),
            "llm.model": ConfigSchema("llm.model", str, "gpt-4", description="LLM 模型名称"),
            "llm.temperature": ConfigSchema("llm.temperature", float, 0.7, min_val=0.0, max_val=2.0),
            "graphiti.url": ConfigSchema("graphiti.url", str, "http://localhost:8008", description="Graphiti 服务地址"),
            "opa.url": ConfigSchema("opa.url", str, "http://localhost:8181", description="OPA 服务地址"),
            "jwt.secret": ConfigSchema("jwt.secret", str, "change-me", sensitive=True),
            "jwt.algorithm": ConfigSchema("jwt.algorithm", str, "HS256", choices=["HS256", "RS256"]),
            "jwt.access_ttl": ConfigSchema("jwt.access_ttl", int, 900, description="Access Token TTL (秒)"),
            "jwt.refresh_ttl": ConfigSchema("jwt.refresh_ttl", int, 604800, description="Refresh Token TTL (秒)"),
            "logging.level": ConfigSchema("logging.level", str, "info", choices=["debug", "info", "warning", "error"]),
            "rate_limit.enabled": ConfigSchema("rate_limit.enabled", bool, True),
            "rate_limit.requests_per_second": ConfigSchema("rate_limit.requests_per_second", float, 100.0, min_val=1.0),
            "workspace.max_count": ConfigSchema("workspace.max_count", int, 100, min_val=1),
            "ontology.validation.enabled": ConfigSchema("ontology.validation.enabled", bool, True),
            "ontology.version.preserve_count": ConfigSchema("ontology.version.preserve_count", int, 50, min_val=1),
        }
        for key, schema in defaults.items():
            self._schema[key] = schema
            self._layers[ConfigLayer.SYSTEM][key] = schema.default

    def _load_env_layer(self):
        mapping = {
            "SERVER_HOST": "server.host",
            "SERVER_PORT": "server.port",
            "SERVER_DEBUG": "server.debug",
            "LLM_PROVIDER": "llm.provider",
            "LLM_MODEL": "llm.model",
            "LLM_TEMPERATURE": "llm.temperature",
            "GRAPHITI_URL": "graphiti.url",
            "OPA_URL": "opa.url",
            "JWT_SECRET": "jwt.secret",
            "JWT_ALGORITHM": "jwt.algorithm",
            "JWT_ACCESS_TTL": "jwt.access_ttl",
            "JWT_REFRESH_TTL": "jwt.refresh_ttl",
            "LOG_LEVEL": "logging.level",
            "RATE_LIMIT_ENABLED": "rate_limit.enabled",
            "RATE_LIMIT_RPS": "rate_limit.requests_per_second",
        }
        for env_key, config_key in mapping.items():
            value = os.getenv(env_key)
            if value is not None:
                schema = self._schema.get(config_key)
                if schema:
                    typed_value = self._coerce_type(value, schema.type)
                    self._layers[ConfigLayer.ENV][config_key] = typed_value

    def load_file_config(self, file_path: str) -> List[ConfigValidationError]:
        errors = []
        if not os.path.exists(file_path):
            return [ConfigValidationError("", f"Config file not found: {file_path}")]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                elif file_path.endswith(('.yaml', '.yml')):
                    try:
                        import yaml
                        data = yaml.safe_load(f)
                    except ImportError:
                        data = json.load(f)
                else:
                    data = json.load(f)

            flat = self._flatten(data)
            for key, value in flat.items():
                schema = self._schema.get(key)
                if schema and not schema.validate(value):
                    errors.append(ConfigValidationError(key, f"Invalid value: {value}"))
                with self._lock:
                    self._layers[ConfigLayer.FILE][key] = value
        except Exception as e:
            errors.append(ConfigValidationError("", str(e)))
        return errors

    def set_workspace_config(self, configs: Dict[str, Any]):
        with self._lock:
            self._layers[ConfigLayer.WORKSPACE] = deepcopy(configs)

    def set_user_config(self, configs: Dict[str, Any]):
        with self._lock:
            self._layers[ConfigLayer.USER] = deepcopy(configs)

    def get(self, key: str) -> Any:
        for layer in [ConfigLayer.USER, ConfigLayer.WORKSPACE, ConfigLayer.FILE, ConfigLayer.ENV, ConfigLayer.SYSTEM]:
            value = self._layers[layer].get(key)
            if value is not None:
                return value
        schema = self._schema.get(key)
        return schema.default if schema else None

    def get_all(self) -> Dict[str, Any]:
        result = {}
        with self._lock:
            for key in self._schema:
                result[key] = self.get(key)
        return result

    def get_effective_for_workspace(self, workspace_id: str = None) -> Dict[str, Any]:
        result = {}
        for layer in [ConfigLayer.SYSTEM, ConfigLayer.ENV, ConfigLayer.FILE]:
            for key, value in self._layers[layer].items():
                if value is not None:
                    result[key] = value
        if workspace_id:
            ws_config = self._layers[ConfigLayer.WORKSPACE]
            result.update(ws_config)
        return result

    def validate_all(self) -> List[ConfigValidationError]:
        errors = []
        for key, schema in self._schema.items():
            value = self.get(key)
            if schema.required and value is None:
                errors.append(ConfigValidationError(key, f"Required config {key} is missing"))
            elif value is not None and not schema.validate(value):
                errors.append(ConfigValidationError(key, f"Invalid value for {key}: {value}"))
        return errors

    def get_schema(self) -> Dict[str, Dict]:
        return {k: {
            "type": v.type.__name__,
            "default": v.default,
            "required": v.required,
            "description": v.description,
            "choices": v.choices,
            "sensitive": v.sensitive,
        } for k, v in self._schema.items()}

    def diff(self, key: str = None) -> Dict[str, Dict[str, Any]]:
        result = {}
        with self._lock:
            keys = [key] if key else list(self._schema.keys())
            for k in keys:
                layer_values = {}
                for layer_name in ["SYSTEM", "ENV", "FILE", "WORKSPACE", "USER"]:
                    layer = getattr(ConfigLayer, layer_name)
                    layer_values[layer_name] = self._layers[layer].get(k)
                result[k] = layer_values
        return result

    def _flatten(self, data: Dict, prefix: str = "") -> Dict[str, Any]:
        result = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and not any(isinstance(v, (dict, list)) for v in value.values()):
                for sub_key, sub_val in value.items():
                    result[f"{full_key}.{sub_key}"] = sub_val
            elif isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value
        return result

    def _coerce_type(self, value: str, target_type: type) -> Any:
        if target_type == bool:
            return value.lower() in ('true', '1', 'yes')
        if target_type == int:
            return int(value)
        if target_type == float:
            return float(value)
        return value


_global_composer: Optional[ConfigurationComposer] = None


def get_config_composer() -> ConfigurationComposer:
    global _global_composer
    if _global_composer is None:
        _global_composer = ConfigurationComposer()
    return _global_composer
