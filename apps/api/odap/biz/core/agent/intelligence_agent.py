"""
Intelligence Agent — 基于 OpenHarness QueryEngine 的情报分析 Agent

重构为完全基于 OH QueryEngine：
- ReAct 循环由 QueryEngine.submit_message() 驱动
- 工具通过 GraphitiToolAdapter 注册到 OH ToolRegistry
- 权限检查通过 OH PermissionChecker + OPA 扩展
- RAG 上下文注入作为 OH HookExecutor 的 UserPromptSubmit 钩子
- 自校正策略通过 OH PostToolUse 钩子实现
- CircuitBreaker + FaultRecovery 降级保障

保留的领域扩展：
- RAG 上下文检索（_retrieve_rag_context）
- 结构化报告提取（_extract_report）
- 自校正策略（CORRECTION_STRATEGIES）
- 链路追踪（TraceSpan）
- Graphiti 记忆写入
"""

import json
import os
import sys
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_dir = os.path.dirname(base_dir)
load_dotenv(os.path.join(root_dir, '.env'))

from odap.tools import SKILL_CATALOG, get_registry
from odap.infra.opa import OPAManager
from odap.infra.query import QueryService
from odap.infra.query import get_graph_write_proxy
from odap.infra.resilience.circuit_breaker import CircuitOpenError, get_circuit_breaker
from odap.infra.resilience.fault_tolerance import FaultRecoveryManager, FailureType

# 导入 OH 集成层
from odap.infra.openharness.engine_adapter import (
    OHQueryEngineFactory,
    GraphitiToolAdapter,
    OPENHARNESS_AVAILABLE,
    _FallbackContext,
)

logger = logging.getLogger("intelligence_agent")


# ---------------------------------------------------------------------------
# 审计辅助：IntelligenceAgent analyze / process_message
# ---------------------------------------------------------------------------

def _ia_audit(
    action: str,
    *,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: str = "",
    latency_ms: Optional[int] = None,
) -> None:
    """IntelligenceAgent 审计：优先 storage_audit → 回退 log_audit → logger.warning"""
    _details = dict(details or {})
    if latency_ms is not None:
        _details.setdefault("latency_ms", latency_ms)
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            resource=resource,
            details=_details,
            service="agent_action",
            result_status=result_status,
            result_message=result_message,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed: {e}")

    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource,
            user="system",
            service="agent_action",
            details=_details,
            result_status=result_status,
            result_message=result_message,
            duration_ms=latency_ms,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (log_audit fallback): {e}")


class TraceSpan:
    """轻量级链路追踪 Span"""

    def __init__(self, trace_id: str, span_name: str, parent_id: str = None):
        self.trace_id = trace_id
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.span_name = span_name
        self.start_time = time.perf_counter()
        self.events: List[Dict] = []

    def add_event(self, name: str, attributes: Dict = None):
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self) -> Dict:
        elapsed = (time.perf_counter() - self.start_time) * 1000
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "span_name": self.span_name,
            "duration_ms": round(elapsed, 2),
            "events": self.events,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
        }


class IntelligenceAgent:
    """
    情报分析 Agent

    基于 OpenHarness QueryEngine 的 ReAct 模式：
    1. RAG 上下文注入：从 Graphiti 检索历史情报记忆
    2. OH QueryEngine 驱动 LLM → 工具选择 → 执行 → 观察 → 循环
    3. 自校正策略处理工具执行失败
    4. 将分析过程写入 Graphiti 记忆

    当 OH 不可用时，降级到自建 ReAct 循环。
    """

    MAX_ITERATIONS = 5
    MAX_CORRECTION_ATTEMPTS = 3

    CORRECTION_STRATEGIES = {
        "permission_denied": "fallback",
        "execution_error": "retry",
        "result_invalid": "degrade",
        "timeout": "retry",
    }

    _knowledge_cache: Dict[str, Any] = {}

    @classmethod
    def invalidate_cache(cls, ontology_id: str = None):
        if ontology_id is not None:
            cls._knowledge_cache.pop(ontology_id, None)
        else:
            cls._knowledge_cache.clear()

    def __init__(self, user_role: str = "intelligence_analyst"):
        self.user_role = user_role
        self.opa_manager = OPAManager()
        self._query_service = QueryService()
        self._write_proxy = get_graph_write_proxy()

        from odap.infra.security import security_config
        self.llm_api_key = security_config.OPENAI_API_KEY
        self.llm_api_base = security_config.OPENAI_API_BASE
        self.llm_model = security_config.OPENAI_MODEL

        raw = self.llm_api_base.rstrip('/')
        if raw.endswith('/chat/completions'):
            self.llm_base = raw[:-len('/chat/completions')]
        else:
            self.llm_base = raw

        if not self.llm_base.startswith('http://') and not self.llm_base.startswith('https://'):
            self.llm_base = 'https://' + self.llm_base

        import httpx
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_connections=10),
            follow_redirects=True
        )

        # 构建工具描述（fallback 模式使用）
        self.tools = self._build_tools()

        # 韧性基础设施
        self.fault_manager = FaultRecoveryManager.get_instance()
        self._llm_circuit_breaker = get_circuit_breaker("llm", failure_threshold_pct=0.5)

        # OH QueryEngine 工厂
        self._engine_factory = OHQueryEngineFactory.get_instance()
        self._engine_factory.configure(
            api_key=self.llm_api_key,
            base_url=self.llm_base,
            model=self.llm_model,
            opa_manager=self.opa_manager,
        )

        # 链路追踪上下文
        self._trace_root: Optional[TraceSpan] = None
        self._spans: List[Dict] = []

    def _build_tools(self) -> List[Dict]:
        """从 SKILL_CATALOG 构建 OpenAI function calling 格式的工具列表"""
        tools = []
        allowed_categories = {"intelligence", "analysis", "ontology", "recommendation", "web"}

        for name, entry in SKILL_CATALOG.items():
            category = entry.get("category", "legacy")
            if category not in allowed_categories:
                continue

            registry = get_registry()
            skill = registry.get(name)
            params = {"type": "object", "properties": {}, "required": []}

            if skill and skill.input_schema:
                schema = skill.input_schema.model_json_schema()
                params = {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                }
            else:
                params = {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "查询内容"},
                    },
                    "required": [],
                }

            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": entry["description"],
                    "parameters": params,
                }
            })

        return tools

    def _get_system_prompt(self, rag_context: str = "") -> str:
        """构建系统提示词（含 RAG 上下文）"""
        rag_section = ""
        if rag_context:
            rag_section = f"""
### 历史情报记忆（RAG 检索结果）
以下是从知识图谱中检索到的与当前查询相关的历史情报，请参考这些历史信息辅助你的分析：

{rag_context}

请在分析中明确引用历史情报中的相关模式（如有），并在 recommendations 中标注 "historical_patterns" 字段。
"""

        return f"""你是一个领域情报分析 Agent。你的任务是通过调用工具收集领域数据，然后综合分析生成结构化报告。

可用工具包括：
- search_sensor: 搜索传感器系统
- analyze_domain: 分析领域态势
- analyze_resource_comparison: 分析资源对比
- analyze_equipment_capabilities: 分析设备能力
- analyze_public_assets: 分析公共资产
- analyze_incident_events: 分析领域事件
- analyze_entity_status: 分析实体状态
- query_ontology: 查询本体数据

分析流程：
1. 先理解用户的查询意图
2. 调用合适的工具收集数据
3. 综合所有数据（包括历史情报记忆）生成结构化报告
{rag_section}
报告格式要求（JSON）：
{{
  "summary": "一句话总结",
  "threat_level": "low/medium/high/critical",
  "opponent_units": [...],
  "opponent_equipment": [...],
  "public_risk": [...],
  "own_status": [...],
  "recommendations": [...],
  "historical_patterns": [...]
}}

重要规则：
- 不要编造数据，只用工具返回的真实数据
- 如果工具返回错误，如实报告
- 最后一步必须返回 JSON 格式的报告，不要调用任何工具
- historical_patterns 字段应引用 RAG 提供的历史情报中的相关模式（如无则返回空数组）"""

    async def analyze(self, query: str) -> Dict[str, Any]:
        """
        执行情报分析（start/success/failed 三维度审计）

        优先使用 OH QueryEngine（完全复用 OH 运行时），
        OH 不可用时降级到自建 ReAct 循环。
        """
        # 初始化链路追踪
        trace_id = uuid.uuid4().hex[:16]
        self._trace_root = TraceSpan(trace_id, "analyze")
        self._trace_root.add_event("query_received", {
            "query": query,
            "user_role": self.user_role,
        })
        self._spans = []

        logger.info(f"\n{'=' * 60}")
        logger.info(f'Intelligence Agent: {query}')
        logger.info(f'角色: {self.user_role} | Trace ID: {trace_id}')
        logger.info(f"{'=' * 60}")

        start_time = time.perf_counter()

        # analyze start 审计
        try:
            _ia_audit(
                "agent_analyze_start",
                resource="intelligence_agent",
                details={
                    "agent_id": "intelligence_agent",
                    "user_role": self.user_role,
                    "query_len": len(query or ""),
                    "trace_id": trace_id,
                },
                result_status="success",
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

        try:
            # RAG 上下文注入
            rag_context = self._retrieve_rag_context(query)

            # 尝试 OH QueryEngine 路径
            if self._engine_factory.is_available:
                result = await self._analyze_with_engine(query, rag_context, trace_id, start_time)
                if result is not None:
                    # 成功分支：审计
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    has_err = bool(result.get("error"))
                    try:
                        _ia_audit(
                            "agent_analyze_success" if not has_err else "agent_analyze_failed",
                            resource="intelligence_agent",
                            details={
                                "agent_id": "intelligence_agent",
                                "user_role": self.user_role,
                                "query_len": len(query or ""),
                                "trace_id": trace_id,
                                "engine": "openharness_query_engine",
                                "has_error": has_err,
                                "summary_len": len(str(result.get("summary", "")) or ""),
                                "threat_level": result.get("threat_level", "unknown"),
                            },
                            result_status="failure" if has_err else "success",
                            result_message=(result.get("error") or "")[:500],
                            latency_ms=elapsed_ms,
                        )
                    except Exception as e:
                        logger.warning(f"audit failed: {e}")
                    return result
                # QueryEngine 失败，降级

            # 降级到自建 ReAct 循环
            result = await self._analyze_fallback(query, rag_context, trace_id, start_time)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            has_err = bool(result.get("error"))
            try:
                _ia_audit(
                    "agent_analyze_success" if not has_err else "agent_analyze_failed",
                    resource="intelligence_agent",
                    details={
                        "agent_id": "intelligence_agent",
                        "user_role": self.user_role,
                        "query_len": len(query or ""),
                        "trace_id": trace_id,
                        "engine": "fallback_react",
                        "has_error": has_err,
                        "summary_len": len(str(result.get("summary", "")) or ""),
                        "threat_level": result.get("threat_level", "unknown"),
                    },
                    result_status="failure" if has_err else "success",
                    result_message=(result.get("error") or "")[:500],
                    latency_ms=elapsed_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return result
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            try:
                _ia_audit(
                    "agent_analyze_failed",
                    resource="intelligence_agent",
                    details={
                        "agent_id": "intelligence_agent",
                        "user_role": self.user_role,
                        "query_len": len(query or ""),
                        "trace_id": trace_id,
                    },
                    result_status="failure",
                    result_message=f"analyze failed: {exc}"[:500],
                    latency_ms=elapsed_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    async def _analyze_with_engine(self, query: str, rag_context: str,
                                   trace_id: str, start_time: float) -> Optional[Dict[str, Any]]:
        """通过 OH QueryEngine 运行分析（主路径）"""
        span = TraceSpan(trace_id, "query_engine_analyze", self._trace_root.span_id)
        span.add_event("engine_path", {"engine": "openharness_query_engine"})

        try:
            engine = self._engine_factory.create_engine(
                system_prompt=self._get_system_prompt(rag_context),
                max_turns=self.MAX_ITERATIONS,
            )
            if not engine:
                return None

            # 通过 CircuitBreaker 保护提交
            final_text = ""
            steps = []

            async def _submit():
                text_parts = []
                events = []
                async for event in engine.submit_message(query):
                    if hasattr(event, 'text'):
                        text_parts.append(event.text)
                    events.append(event)
                return events, "".join(text_parts)

            if self._llm_circuit_breaker:
                _, final_text = await self._llm_circuit_breaker.acall(_submit)
            else:
                _, final_text = await _submit()

            span.add_event("engine_complete", {"response_length": len(final_text)})

        except CircuitOpenError:
            logger.warning("CircuitBreaker 打开，降级到自建循环")
            self._spans.append(span.finish())
            return None
        except Exception as e:
            logger.warning(f"QueryEngine 执行失败: {e}，降级到自建循环")
            self._spans.append(span.finish())
            return None

        # 提取报告
        report = self._extract_report(final_text)

        elapsed = (time.perf_counter() - start_time) * 1000

        report["_metadata"] = {
            "agent": "IntelligenceAgent",
            "user_role": self.user_role,
            "query": query,
            "tool_calls": [],
            "iterations": 0,
            "execution_time_ms": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rag_context_provided": rag_context != "",
            "engine": "openharness_query_engine",
        }

        await self._save_to_graphiti(query, report)

        self._spans.append(span.finish())
        self._trace_root.add_event("analysis_complete", {
            "execution_time_ms": round(elapsed, 2),
            "engine": "openharness_query_engine",
        })
        self._spans.append(self._trace_root.finish())

        report["_trace"] = {"trace_id": trace_id, "spans": self._spans}
        self._emit_task_completed(report)
        return report

    async def _analyze_fallback(self, query: str, rag_context: str,
                                trace_id: str, start_time: float) -> Dict[str, Any]:
        """降级路径：自建 ReAct 循环"""
        span = TraceSpan(trace_id, "fallback_analyze", self._trace_root.span_id)
        span.add_event("fallback_path", {"reason": "OH QueryEngine unavailable"})

        system_prompt = self._get_system_prompt(rag_context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        tool_call_history = []

        for iteration in range(self.MAX_ITERATIONS):
            iter_span = TraceSpan(trace_id, f"iteration_{iteration + 1}", self._trace_root.span_id)
            logger.info(f'\n--- 轮次 {iteration + 1}/{self.MAX_ITERATIONS} ---')

            try:
                response = await self._call_llm(messages, tools=self.tools)
                iter_span.add_event("llm_response", {"model": self.llm_model})
            except Exception as e:
                iter_span.add_event("llm_error", {"error": str(e)})
                self._spans.append(iter_span.finish())
                recovery = await self.fault_manager.handle_failure("intelligence_agent", error=e)
                if recovery.get("action") == "retry" and recovery.get("attempt", 0) <= self.MAX_CORRECTION_ATTEMPTS:
                    continue
                break

            choice = response["choices"][0]
            message = choice["message"]

            if message.get("tool_calls"):
                messages.append(message)
                for tool_call in message["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    fn_args = json.loads(tool_call["function"]["arguments"])
                    tool_call_id = tool_call["id"]

                    logger.info(f'  调用工具: {fn_name}({json.dumps(fn_args, ensure_ascii=False)})')
                    tool_result = self._execute_tool(fn_name, fn_args)

                    iter_span.add_event("tool_execution", {
                        "tool": fn_name,
                        "result_length": len(tool_result),
                    })

                    # 自校正
                    tool_result_data = json.loads(tool_result) if tool_result else {}
                    if tool_result_data.get("error") or tool_result_data.get("status") == "denied":
                        correction = await self._attempt_correction(fn_name, fn_args, tool_result_data, iteration)
                        if correction:
                            tool_result = correction

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result,
                    })
                    tool_call_history.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result_preview": tool_result[:100],
                    })
            else:
                final_content = message.get("content", "")
                report = self._extract_report(final_content)
                elapsed = (time.perf_counter() - start_time) * 1000

                report["_metadata"] = {
                    "agent": "IntelligenceAgent",
                    "user_role": self.user_role,
                    "query": query,
                    "tool_calls": tool_call_history,
                    "iterations": iteration + 1,
                    "execution_time_ms": round(elapsed, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "rag_context_provided": rag_context != "",
                    "engine": "fallback_react",
                }

                await self._save_to_graphiti(query, report)

                self._spans.append(iter_span.finish())
                self._trace_root.add_event("analysis_complete", {
                    "iterations": iteration + 1,
                    "execution_time_ms": round(elapsed, 2),
                })
                self._spans.append(self._trace_root.finish())

                report["_trace"] = {"trace_id": trace_id, "spans": self._spans}
                self._emit_task_completed(report)
                return report

            self._spans.append(iter_span.finish())

        elapsed = (time.perf_counter() - start_time) * 1000
        self._spans.append(span.finish())
        self._trace_root.add_event("max_iterations_reached", {"iterations": self.MAX_ITERATIONS})
        self._spans.append(self._trace_root.finish())

        return {
            "error": "超过最大推理轮次",
            "summary": "分析未能完成",
            "tool_calls": tool_call_history,
            "_metadata": {
                "agent": "IntelligenceAgent",
                "user_role": self.user_role,
                "query": query,
                "iterations": self.MAX_ITERATIONS,
                "execution_time_ms": round(elapsed, 2),
                "rag_context_provided": rag_context != "",
                "engine": "fallback_react",
            },
            "_trace": {"trace_id": trace_id, "spans": self._spans},
        }

    # -----------------------------------------------------------------------
    # 以下为领域特有逻辑，保留不变
    # -----------------------------------------------------------------------

    from odap.infra.monitoring import monitor_performance

    @monitor_performance('llm_calls', 'chat_completions')
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None,
                        max_retries: int = 3) -> Dict:
        """调用 LLM Chat Completions API（fallback 模式使用）"""
        try:
            self._llm_circuit_breaker._pre_call_check()
        except CircuitOpenError:
            return {
                "choices": [{
                    "message": {
                        "content": '{"summary": "LLM 服务暂时不可用，使用降级模式", "threat_level": "unknown", "recommendations": ["请稍后重试"], "historical_patterns": []}',
                        "role": "assistant"
                    },
                    "finish_reason": "stop"
                }]
            }

        url = f"{self.llm_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        last_error = None
        llm_start = time.perf_counter()
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.http_client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                self._llm_circuit_breaker._finish_call(llm_start, True, None)
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                wait = 2 ** attempt
                import asyncio
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                last_error = e
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                wait = 2 ** attempt
                import asyncio
                await asyncio.sleep(wait)

        self._llm_circuit_breaker._finish_call(llm_start, False, str(last_error))
        raise ConnectionError(f"LLM 调用失败（已重试 {max_retries} 次）: {last_error}")

    def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """执行 Skill 工具，返回 JSON 字符串结果"""
        if tool_name not in SKILL_CATALOG:
            return json.dumps({"error": f"工具不存在: {tool_name}"}, ensure_ascii=False)

        handler = SKILL_CATALOG[tool_name]["handler"]
        category = SKILL_CATALOG[tool_name].get("category", "")
        if category == "operations":
            allowed = self.opa_manager.check_permission(
                self.user_role, arguments.get("action", "unknown"), {"type": "unknown"}
            )
            if not allowed:
                return json.dumps({"status": "denied", "message": "权限不足"}, ensure_ascii=False)

        try:
            result = handler(**arguments)
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, default=str)
            return json.dumps({"result": str(result)}, ensure_ascii=False)
        except TypeError:
            try:
                result = handler()
                if isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False, default=str)
                return json.dumps({"result": str(result)}, ensure_ascii=False)
            except Exception as e2:
                return json.dumps({"error": f"执行失败: {e2}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"执行失败: {e}"}, ensure_ascii=False)

    async def _save_to_graphiti(self, query: str, report: Dict):
        """将分析过程写入 Graphiti 记忆"""
        episode_text = f"情报分析请求: {query}\n分析结果:\n"
        for key, value in report.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (dict, list)):
                episode_text += f"  {key}: {json.dumps(value, ensure_ascii=False, default=str)}\n"
            else:
                episode_text += f"  {key}: {value}\n"

        try:
            result = await self._write_proxy.add_episode(
                name=f"intel_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                content=episode_text,
                source_description=f"IntelligenceAgent/{self.user_role}",
            )
            if result.get("status") == "success":
                logger.info('  [记忆] 分析结果已写入 Graphiti')
        except Exception as e:
            logger.info(f'  [记忆] Graphiti 写入失败: {e}')

    def _retrieve_rag_context(self, query: str) -> str:
        """RAG 上下文检索：从 Graphiti 获取历史情报记忆"""
        span = TraceSpan(self._trace_root.trace_id, "rag_retrieval", self._trace_root.span_id)
        span.add_event("rag_query", {"query": query})

        result = self._query_service.execute(
            workspace_id="default",
            query=f".entity with(search='{query}')",
            limit=5,
        )
        if result.rows:
            context = json.dumps(result.rows, ensure_ascii=False, default=str)
        else:
            context = ""

        if context:
            span.add_event("rag_hits", {"context_length": len(context)})
            logger.info(f'  [RAG] 检索到历史上下文 ({len(context)} 字符)')
        else:
            span.add_event("rag_miss", {"reason": "no_results"})

        self._spans.append(span.finish())
        return context

    def _extract_report(self, content: str) -> Dict:
        """从 LLM 输出中提取 JSON 报告"""
        import re

        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(1).strip())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                obj = json.loads(content[brace_start:brace_end + 1])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        return {"summary": content[:500], "raw_response": content, "parsing": "failed"}

    async def _attempt_correction(
        self, tool_name: str, tool_args: Dict, error_result: Dict, iteration: int
    ) -> Optional[str]:
        """自校正循环"""
        error_msg = error_result.get("error", "") or error_result.get("message", "")
        status = error_result.get("status", "")

        if status == "denied":
            error_type = "permission_denied"
        elif "timeout" in error_msg.lower():
            error_type = "timeout"
        elif "execution" in error_msg.lower() or "执行失败" in error_msg:
            error_type = "execution_error"
        else:
            error_type = "result_invalid"

        strategy = self.CORRECTION_STRATEGIES.get(error_type, "degrade")
        logger.info(f'  自校正: tool={tool_name}, error_type={error_type}, strategy={strategy}')

        if strategy == "retry" and iteration < self.MAX_ITERATIONS - 1:
            try:
                return self._execute_tool(tool_name, {})
            except Exception:
                return None

        elif strategy == "fallback":
            try:
                registry = get_registry()
                failed_skill = registry.get(tool_name)
                if failed_skill is not None:
                    failed_category = failed_skill.metadata.category
                    all_skills = registry.list_skills()
                    for skill_info in all_skills:
                        if (skill_info["name"] != tool_name and
                                skill_info.get("category") == failed_category):
                            fallback_result = self._execute_tool(skill_info["name"], {})
                            logger.info(f'  使用替代工具: {skill_info["name"]}')
                            return fallback_result
            except Exception:
                pass
            return None

        elif strategy == "degrade":
            return json.dumps({
                "summary": f"工具 {tool_name} 执行降级，原始错误: {error_msg[:100]}",
                "threat_level": "unknown",
                "degraded": True,
            }, ensure_ascii=False)

        return None

    def _emit_task_completed(self, report: Dict[str, Any]):
        """分析完成后广播事件"""
        try:
            import asyncio
            from odap.web.ws.event_bus import get_event_bus
            bus = get_event_bus()
            metadata = report.get("_metadata", {})
            event_data = {
                "agent_id": "intelligence_agent",
                "agent_type": "intelligence",
                "result": {k: v for k, v in report.items() if not k.startswith("_")},
                "target_agents": ["director"],
                "query": metadata.get("query", ""),
                "threat_level": report.get("threat_level", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(bus.emit("agent:task_completed", event_data))
                else:
                    loop.run_until_complete(bus.emit("agent:task_completed", event_data))
            except RuntimeError:
                asyncio.run(bus.emit("agent:task_completed", event_data))
        except Exception as e:
            logger.warning(f"广播事件失败: {e}")

    async def shutdown(self):
        """关闭资源"""
        if hasattr(self, 'http_client'):
            await self.http_client.aclose()
