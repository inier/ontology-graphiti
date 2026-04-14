"""
智谱 AI (Zhipu AI) LLM 客户端适配器
解决 graphiti 只能使用 OpenAI 官方 API 的问题

智谱 AI 兼容 OpenAI Chat Completions API，但不支持 Responses API
"""

import json
import logging
import re
from typing import Any, Optional

import httpx

from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)


class ZhipuAIClient(OpenAIClient):
    """
    智谱 AI 客户端适配器
    继承 OpenAIClient，覆盖 _generate_response 方法使用智谱 AI API
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        cache: bool = False,
        client: Any = None,
        max_tokens: int = 4096,
        reasoning: str = 'minimal',
        verbosity: str = 'low'
    ):
        # 先用父类初始化
        super().__init__(config, cache, client, max_tokens, reasoning, verbosity)

        # 然后覆盖为智谱 AI 的配置
        if config:
            self.api_key = config.api_key
            self.model = config.model
            self.temperature = config.temperature
            # 智能处理 base_url：去掉尾部 /chat/completions 避免拼接重复
            raw = config.base_url.rstrip('/')
            if raw.endswith('/chat/completions'):
                self.base_url = raw[:-len('/chat/completions')]
            else:
                self.base_url = raw
        else:
            self.base_url = "https://open.bigmodel.cn/api/paas/v4"
            self.api_key = ""
            self.model = "glm-4"
            self.temperature = 0.7

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: Any = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium
    ) -> tuple[dict[str, Any], int, int]:
        """
        生成响应 - 使用 OpenAI 兼容 Chat Completions API

        与父类 OpenAIClient 不同，这里不使用 OpenAI Responses API（text_format），
        而是在 user message 末尾追加 JSON schema 提示来引导结构化输出，
        然后手动解析 JSON 响应。这确保了对任何 OpenAI 兼容 API 的通用性。

        Returns:
            tuple: (response_dict, input_tokens, output_tokens)
        """
        # 复制 messages 避免修改原列表
        work_messages = [Message(role=m.role, content=m.content) for m in messages]

        # 当有 response_model 时，在最后一条消息追加 JSON schema 提示
        # （模拟 OpenAI Responses API 的 text_format 行为）
        if response_model is not None and work_messages:
            schema = response_model.model_json_schema()
            # 提取 properties 和 required，生成简洁的格式提示
            properties = schema.get('properties', {})
            required_fields = schema.get('required', [])
            field_descs = []
            for fname, finfo in properties.items():
                ftype = finfo.get('type', finfo.get('$ref', 'any'))
                fdesc = finfo.get('description', '')
                field_descs.append(f'    "{fname}": {ftype} ({fdesc})' if fdesc else f'    "{fname}": {ftype}')

            schema_hint = (
                "\n\nIMPORTANT: You MUST respond with a valid JSON object matching this structure:\n"
                "{\n" + "\n".join(field_descs) + "\n}\n"
                f"Required fields: {required_fields}\n"
                "Do NOT wrap the JSON in markdown code blocks. Do NOT include any explanation outside the JSON."
            )
            last = work_messages[-1]
            last.content += schema_hint

        # 将 messages 转换为 API 格式
        api_messages = []
        for msg in work_messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=120.0) as http_client:
            response = await http_client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise Exception(f"API request failed with status {response.status_code}: {response.text}")

            result = response.json()

            # 提取响应内容
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
            else:
                content = str(result)

            # 提取 token 使用量
            prompt_tokens = result.get('usage', {}).get('prompt_tokens', 0)
            completion_tokens = result.get('usage', {}).get('completion_tokens', 0)

            # 解析 JSON 响应
            response_dict = self._extract_json(content)

            # 当有 response_model 时，校正 LLM 返回的字段名以匹配 Pydantic schema
            # （部分非 OpenAI 模型会自创字段名如 entity_name 代替 name）
            if response_model is not None and response_dict:
                response_dict = self._normalize_fields(response_dict, response_model)
                # 对于仍有缺失 required 字段的情况，尝试填充推断值
                response_dict = self._fill_missing_fields(response_dict, response_model)

            return response_dict, prompt_tokens, completion_tokens

    def _extract_json(self, content: str) -> dict[str, Any]:
        """从 LLM 输出中提取 JSON，处理 markdown 代码块和包裹层。

        支持的格式：
        1. 直接 JSON 字符串
        2. markdown 代码块包裹的 JSON
        3. 嵌套在 {"response": ...} 中的 JSON
        """
        text = content.strip()

        # 如果已经是合法 JSON dict，检查是否有包裹层
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                # 检查是否有 {"response": "..."} 包裹层需要递归解包
                if 'response' in obj:
                    inner = obj['response']
                    if isinstance(inner, str):
                        # 内层可能是 JSON 字符串或包含代码块的文本
                        return self._extract_json(inner)
                    elif isinstance(inner, dict):
                        return inner
                    elif isinstance(inner, list):
                        # 模型把数组包在 response 里，包装成 expected 格式
                        # graphiti 的 ExtractedEntities 期望 {"extracted_entities": [...]}
                        return {"extracted_entities": inner}
                return obj
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取 JSON
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(1).strip())
                if isinstance(obj, dict):
                    return obj
                elif isinstance(obj, list):
                    return {"extracted_entities": obj}
            except json.JSONDecodeError:
                pass

        # 最后尝试：找到第一个 { 到最后一个 } 的范围
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            try:
                obj = json.loads(text[brace_start:brace_end + 1])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        # 如果找到 [ ... ] 数组格式
        bracket_start = text.find('[')
        bracket_end = text.rfind(']')
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            try:
                arr = json.loads(text[bracket_start:bracket_end + 1])
                if isinstance(arr, list):
                    return {"extracted_entities": arr}
            except json.JSONDecodeError:
                pass

        # 全部失败，返回原始内容
        return {"response": text}

    # --- 字段名模糊匹配映射 ---

    # 常见的 LLM 字段名变体映射（lowercase → canonical）
    _FIELD_ALIASES: dict[str, str] = {
        'entity_name': 'name',
        'entity_text': 'name',
        'entity_label': 'name',
        'entity_type': 'entity_type_id',
        'type_id': 'entity_type_id',
        'type': 'entity_type_id',
        'source_node': 'source',
        'target_node': 'target',
        'target_entity': 'target',
        'source_entity': 'source',
        'fact': 'content',
        'description': 'content',
        'relationship': 'content',
        'relation_type': 'content',
        'edge_type': 'content',
    }

    def _normalize_fields(self, data: Any, response_model: Any) -> Any:
        """递归校正 JSON 字段名以匹配 Pydantic schema。

        通过解析 model_json_schema() 中的 $defs 获取所有嵌套类型的字段定义，
        然后递归遍历 JSON 数据做字段名映射。
        """
        schema = response_model.model_json_schema()
        defs = schema.get('$defs', {})
        return self._normalize_recursive(data, schema, defs)

    def _fill_missing_fields(self, data: Any, response_model: Any) -> Any:
        """为缺失的 required 字段填充推断默认值。

        这是最后一道防线：当非 OpenAI 模型漏掉了 required 字段时，
        尝试根据上下文推断合理的默认值，避免 Pydantic 校验失败。
        """
        schema = response_model.model_json_schema()
        defs = schema.get('$defs', {})
        return self._fill_recursive(data, schema, defs)

    def _fill_recursive(self, data: Any, type_schema: dict, defs: dict) -> Any:
        """递归遍历 data，为缺失的 required 字段填充默认值，并修正类型错误。"""
        if isinstance(data, list):
            items_schema = type_schema.get('items', {})
            return [self._fill_recursive(item, items_schema, defs) for item in data]

        if not isinstance(data, dict):
            return data

        resolved = self._resolve_ref(type_schema, defs)
        props = resolved.get('properties', {})
        required = set(resolved.get('required', []))

        if not props:
            return data

        # 1. 修正已有字段类型错误（如 entity_type_id 应为 int 但 LLM 返回了字符串）
        for key, value in list(data.items()):
            if key in props:
                prop_schema = self._resolve_ref(props[key], defs)
                corrected = self._coerce_type(value, prop_schema, key)
                if corrected is not None:
                    data[key] = corrected
                    logger.debug(f"Coerced field '{key}': {repr(value)} → {repr(corrected)}")

        # 2. 检查缺失的 required 字段
        missing = required - set(data.keys())
        for field in missing:
            inferred = self._infer_field_value(field, props.get(field, {}), data)
            if inferred is not None:
                data[field] = inferred
                logger.debug(f"Filled missing required field '{field}' = {repr(inferred)}")

        # 递归处理嵌套字段
        for key, value in data.items():
            if key in props:
                prop_schema = self._resolve_ref(props[key], defs)
                data[key] = self._fill_recursive(value, prop_schema, defs)

        return data

    def _coerce_type(self, value: Any, prop_schema: dict, field_name: str) -> Any:
        """尝试将值修正为 schema 要求的类型。返回修正后的值，或 None 表示无需修正。"""
        if value is None:
            return None

        py_type = prop_schema.get('type', '')
        any_of = prop_schema.get('anyOf', [])

        # 处理 anyOf 类型（如 Optional[int] = anyOf[{'type':'integer'},{'type':'null'}]）
        target_type = py_type
        if any_of:
            for t in any_of:
                if isinstance(t, dict) and t.get('type') != 'null':
                    target_type = t['type']
                    break

        # str → int
        if target_type == 'integer' and isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0

        # str → float
        if target_type == 'number' and isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        # int → str（较少见但可能）
        if target_type == 'string' and isinstance(value, (int, float)):
            return str(value)

        return None

    def _infer_field_value(self, field: str, prop_info: dict, data: dict) -> Any:
        """根据字段名和已有数据推断默认值。"""
        lower = field.lower()

        # fact/content 类字段：从 relation_type 和 entity names 推断
        if lower in ('fact', 'content', 'description'):
            parts = []
            src = data.get('source_entity_name') or data.get('source') or ''
            tgt = data.get('target_entity_name') or data.get('target') or ''
            rel = data.get('relation_type') or data.get('content') or ''
            if src and tgt:
                parts.append(f"{src}")
                if rel:
                    parts.append(f"[{rel}]")
                parts.append(f"{tgt}")
            if parts:
                return ' '.join(parts)

        # name 类字段
        if lower == 'name':
            for alias in ('entity_name', 'entity_text', 'label'):
                if alias in data:
                    return data[alias]

        # entity_type_id 类字段
        if lower == 'entity_type_id':
            return 0  # 默认类型

        return None

    def _normalize_recursive(self, data: Any, type_schema: dict, defs: dict) -> Any:
        """递归遍历 data，根据 type_schema 中的 properties 做字段名映射。"""
        if isinstance(data, list):
            # 数组：获取 items 的 schema
            items_schema = type_schema.get('items', {})
            return [self._normalize_recursive(item, items_schema, defs) for item in data]

        if not isinstance(data, dict):
            return data

        # 解析 $ref
        resolved = self._resolve_ref(type_schema, defs)
        props = resolved.get('properties', {})

        if not props:
            return data

        corrected = {}
        for key, value in data.items():
            if key in props:
                # 字段名正确，递归处理嵌套值
                prop_schema = self._resolve_ref(props[key], defs)
                corrected[key] = self._normalize_recursive(value, prop_schema, defs)
            else:
                # 字段名不在 schema 中，尝试模糊匹配
                matched = self._fuzzy_match_field(key, props)
                if matched:
                    prop_schema = self._resolve_ref(props[matched], defs)
                    corrected[matched] = self._normalize_recursive(value, prop_schema, defs)
                    logger.debug(f"Field mapped: '{key}' -> '{matched}'")
                else:
                    corrected[key] = value
        return corrected

    def _resolve_ref(self, schema: dict, defs: dict) -> dict:
        """解析 $ref 引用，返回实际的 schema 定义。"""
        ref = schema.get('$ref', '')
        if ref.startswith('#/$defs/'):
            def_name = ref[len('#/$defs/'):]
            return defs.get(def_name, schema)
        return schema

    def _fuzzy_match_field(self, key: str, properties: dict) -> Optional[str]:
        """通过别名表或语义相似度匹配字段名。"""
        lowered = key.lower().replace('-', '_').replace(' ', '_')

        # 1. 精确别名匹配
        if lowered in self._FIELD_ALIASES:
            target = self._FIELD_ALIASES[lowered]
            if target in properties:
                return target

        # 2. 包含关系匹配
        for prop_name in properties:
            prop_lower = prop_name.lower().replace('-', '_').replace(' ', '_')
            if lowered in prop_lower or prop_lower in lowered:
                return prop_name

        # 3. 下划线分词后交叉匹配
        key_parts = set(lowered.split('_'))
        best_match = None
        best_overlap = 0
        for prop_name in properties:
            prop_parts = set(prop_name.lower().replace('-', '_').replace(' ', '_').split('_'))
            overlap = len(key_parts & prop_parts)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = prop_name
        if best_match and best_overlap > 0:
            return best_match

        return None
