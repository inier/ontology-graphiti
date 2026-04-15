"""
Intelligence Agent — 基于 LLM ReAct 模式的情报分析 Agent

与 SelfCorrectingOrchestrator（关键词正则路由）不同，Intelligence Agent 使用
LLM 进行自然语言理解、多步推理和工具调用，实现真正的情报分析闭环。

Phase 1-B: Intelligence Agent 单体闭环
- Slice 1.5: LLM 驱动 + Skill 调用 + Graphiti 记忆 + OPA 集成
- Slice 1.6: RAG 增强推理（Graphiti 历史模式匹配 + 上下文注入）
- Slice 1.7: 结构化链路追踪 + 性能基线
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
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import httpx
from odap.tools import SKILL_CATALOG, get_registry
from odap.infra.opa import OPAManager
from odap.infra.graph import GraphManager

# 结构化链路追踪日志
logger = logging.getLogger("intelligence_agent")


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

    使用 LLM 驱动的 ReAct (Reasoning + Acting) 模式：
    1. RAG 上下文注入：从 Graphiti 检索历史情报记忆
    2. LLM 推理需要调用的工具和参数
    3. 执行工具获取数据
    4. LLM 综合分析生成结构化报告
    5. 将分析过程写入 Graphiti 记忆

    每一步都经过 OPA 权限检查（对于高危险操作）。
    """

    MAX_ITERATIONS = 5  # 最多工具调用轮次

    def __init__(self, user_role: str = "intelligence_analyst"):
        self.user_role = user_role
        self.opa_manager = OPAManager()
        self.graph_manager = GraphManager()
        self.llm_api_key = os.getenv('OPENAI_API_KEY', '')
        self.llm_api_base = os.getenv('OPENAI_API_BASE', '')
        self.llm_model = os.getenv('OPENAI_MODEL', '')

        # 智能处理 base_url
        raw = self.llm_api_base.rstrip('/')
        if raw.endswith('/chat/completions'):
            self.llm_base = raw[:-len('/chat/completions')]
        else:
            self.llm_base = raw

        # 构建工具描述
        self.tools = self._build_tools()

        # 链路追踪上下文
        self._trace_root: Optional[TraceSpan] = None
        self._spans: List[Dict] = []

    def _build_tools(self) -> List[Dict]:
        """从 SKILL_CATALOG 构建 OpenAI function calling 格式的工具列表"""
        tools = []
        # 只暴露 intelligence 和 analysis 类别的工具给 Intelligence Agent
        allowed_categories = {"intelligence", "analysis", "ontology", "recommendation"}

        for name, entry in SKILL_CATALOG.items():
            category = entry.get("category", "legacy")
            if category not in allowed_categories:
                continue

            # 从 BaseSkill 获取参数 schema（如果有的话）
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
                # 旧式 skill，用通用参数
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

    def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None,
                  max_retries: int = 3) -> Dict:
        """调用 LLM Chat Completions API（含指数退避重试）"""
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
        for attempt in range(1, max_retries + 1):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                wait = 2 ** attempt  # 2s, 4s, 8s
                print(f"  ⚠️ LLM 请求超时 ({attempt}/{max_retries})，{wait}s 后重试...")
                time.sleep(wait)
            except httpx.HTTPStatusError as e:
                last_error = e
                # 4xx 不重试（除了 429）
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"  ⚠️ LLM HTTP {e.response.status_code} ({attempt}/{max_retries})，{wait}s 后重试...")
                time.sleep(wait)

        raise ConnectionError(f"LLM 调用失败（已重试 {max_retries} 次）: {last_error}")

    def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """执行 Skill 工具，返回 JSON 字符串结果"""
        if tool_name not in SKILL_CATALOG:
            return json.dumps({"error": f"工具不存在: {tool_name}"}, ensure_ascii=False)

        handler = SKILL_CATALOG[tool_name]["handler"]

        # OPA 权限检查（高危险工具）
        category = SKILL_CATALOG[tool_name].get("category", "")
        if category == "operations":
            allowed = self.opa_manager.check_permission(
                self.user_role,
                arguments.get("action", "unknown"),
                {"type": "unknown"}
            )
            if not allowed:
                return json.dumps({"status": "denied", "message": "权限不足"}, ensure_ascii=False)

        try:
            # 旧式 handler 接收 **kwargs
            result = handler(**arguments)
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, default=str)
            return json.dumps({"result": str(result)}, ensure_ascii=False)
        except TypeError:
            # 参数不匹配，尝试用空参数
            try:
                result = handler()
                if isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False, default=str)
                return json.dumps({"result": str(result)}, ensure_ascii=False)
            except Exception as e2:
                return json.dumps({"error": f"执行失败: {e2}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"执行失败: {e}"}, ensure_ascii=False)

    def _save_to_graphiti(self, query: str, report: Dict):
        """将分析过程写入 Graphiti 记忆（使用 graph_manager 的统一接口）"""
        episode_text = f"情报分析请求: {query}\n"
        episode_text += f"分析结果:\n"
        for key, value in report.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (dict, list)):
                episode_text += f"  {key}: {json.dumps(value, ensure_ascii=False, default=str)}\n"
            else:
                episode_text += f"  {key}: {value}\n"

        success = self.graph_manager.add_episode(
            name=f"intel_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            content=episode_text,
            source_description=f"IntelligenceAgent/{self.user_role}",
        )

        if success:
            print("  [记忆] 分析结果已写入 Graphiti")
        else:
            print("  [记忆] Graphiti 不可用，跳过记忆写入")

    def _retrieve_rag_context(self, query: str) -> str:
        """
        RAG 上下文检索：从 Graphiti 获取与 query 相关的历史情报记忆。

        这是 Slice 1.6 的核心实现——在 LLM 推理前注入历史上下文，
        让 Agent 能够利用过去的分析经验增强当前判断。
        """
        span = TraceSpan(self._trace_root.trace_id, "rag_retrieval", self._trace_root.span_id)
        span.add_event("rag_query", {"query": query})

        context = self.graph_manager.retrieve_rag_context(query, top_k=5)

        if context:
            span.add_event("rag_hits", {"context_length": len(context)})
            print(f"  [RAG] 检索到历史上下文 ({len(context)} 字符)")
        else:
            span.add_event("rag_miss", {"reason": "no_results"})

        result = span.finish()
        self._spans.append(result)
        return context

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        执行情报分析（ReAct 循环 + RAG 增强）

        Args:
            query: 自然语言查询（如"分析B区威胁"）

        Returns:
            结构化分析报告（含 _metadata 和 _trace）
        """
        # 初始化链路追踪
        trace_id = uuid.uuid4().hex[:16]
        self._trace_root = TraceSpan(trace_id, "analyze")
        self._trace_root.add_event("query_received", {
            "query": query,
            "user_role": self.user_role,
        })
        self._spans = []

        print(f"\n{'='*60}")
        print(f"🔍 Intelligence Agent: {query}")
        print(f"👤 角色: {self.user_role}")
        print(f"🔗 Trace ID: {trace_id}")
        print(f"{'='*60}")

        start_time = time.perf_counter()

        # === RAG 上下文注入（Slice 1.6） ===
        rag_context = self._retrieve_rag_context(query)

        # 构建系统提示（含 RAG 上下文）
        rag_section = ""
        if rag_context:
            rag_section = f"""
### 历史情报记忆（RAG 检索结果）
以下是从知识图谱中检索到的与当前查询相关的历史情报，请参考这些历史信息辅助你的分析：

{rag_context}

请在分析中明确引用历史情报中的相关模式（如有），并在 recommendations 中标注 "historical_patterns" 字段。
"""

        system_prompt = f"""你是一个战场情报分析 Agent。你的任务是通过调用工具收集战场数据，然后综合分析生成结构化报告。

可用工具包括：
- search_radar: 搜索雷达系统
- analyze_domain: 分析领域态势
- analyze_force_comparison: 分析力量对比
- analyze_weapon_capabilities: 分析武器能力
- analyze_civilian_infrastructure: 分析民用基础设施
- analyze_battle_events: 分析战场事件
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
  "enemy_units": [...],
  "enemy_weapons": [...],
  "civilian_risk": [...],
  "friendly_status": [...],
  "recommendations": [...],
  "historical_patterns": [...]
}}

重要规则：
- 不要编造数据，只用工具返回的真实数据
- 如果工具返回错误，如实报告
- 最后一步必须返回 JSON 格式的报告，不要调用任何工具
- historical_patterns 字段应引用 RAG 提供的历史情报中的相关模式（如无则返回空数组）"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        tool_call_history = []

        for iteration in range(self.MAX_ITERATIONS):
            # 创建轮次 Span
            iter_span = TraceSpan(trace_id, f"iteration_{iteration + 1}", self._trace_root.span_id)

            print(f"\n--- 轮次 {iteration + 1}/{self.MAX_ITERATIONS} ---")

            try:
                response = self._call_llm(messages, tools=self.tools)
                iter_span.add_event("llm_response", {
                    "model": self.llm_model,
                    "finish_reason": response["choices"][0].get("finish_reason", "unknown"),
                })
            except Exception as e:
                iter_span.add_event("llm_error", {"error": str(e)})
                self._spans.append(iter_span.finish())
                print(f"❌ LLM 调用失败: {e}")
                break

            choice = response["choices"][0]
            message = choice["message"]

            # 检查是否有工具调用
            if message.get("tool_calls"):
                # 添加助手消息（含 tool_calls）
                messages.append(message)

                for tool_call in message["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    fn_args = json.loads(tool_call["function"]["arguments"])
                    tool_call_id = tool_call["id"]

                    print(f"  🔧 调用工具: {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")

                    # 执行工具
                    tool_result = self._execute_tool(fn_name, fn_args)
                    print(f"  📋 结果: {tool_result[:200]}{'...' if len(tool_result) > 200 else ''}")

                    iter_span.add_event("tool_execution", {
                        "tool": fn_name,
                        "args_preview": json.dumps(fn_args, ensure_ascii=False)[:100],
                        "result_length": len(tool_result),
                    })

                    # 添加工具结果
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
                # 没有工具调用，提取最终回答
                final_content = message.get("content", "")
                print(f"\n📝 最终回答:\n{final_content}")

                iter_span.add_event("final_answer", {
                    "content_length": len(final_content),
                })

                # 尝试解析为 JSON 报告
                report = self._extract_report(final_content)

                elapsed = (time.perf_counter() - start_time) * 1000

                # 添加元数据
                report["_metadata"] = {
                    "agent": "IntelligenceAgent",
                    "user_role": self.user_role,
                    "query": query,
                    "tool_calls": tool_call_history,
                    "iterations": iteration + 1,
                    "execution_time_ms": round(elapsed, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "rag_context_provided": rag_context != "",
                }

                # 写入 Graphiti 记忆
                self._save_to_graphiti(query, report)

                # 链路追踪收尾
                self._spans.append(iter_span.finish())
                self._trace_root.add_event("analysis_complete", {
                    "iterations": iteration + 1,
                    "execution_time_ms": round(elapsed, 2),
                    "threat_level": report.get("threat_level", "unknown"),
                })
                self._spans.append(self._trace_root.finish())

                # 性能基线日志
                logger.info(json.dumps({
                    "trace_id": trace_id,
                    "query": query,
                    "threat_level": report.get("threat_level"),
                    "iterations": iteration + 1,
                    "execution_time_ms": round(elapsed, 2),
                    "rag_enabled": rag_context != "",
                    "spans": len(self._spans),
                }, ensure_ascii=False))

                report["_trace"] = {
                    "trace_id": trace_id,
                    "spans": self._spans,
                }

                return report

            self._spans.append(iter_span.finish())

        # 超过最大轮次
        elapsed = (time.perf_counter() - start_time) * 1000
        self._trace_root.add_event("max_iterations_reached", {
            "iterations": self.MAX_ITERATIONS,
        })
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
            },
            "_trace": {
                "trace_id": trace_id,
                "spans": self._spans,
            },
        }

    def _extract_report(self, content: str) -> Dict:
        """从 LLM 输出中提取 JSON 报告"""
        import re

        # 尝试直接解析
        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块提取
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(1).strip())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        # 尝试找 JSON 对象
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                obj = json.loads(content[brace_start:brace_end + 1])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        # 无法解析，返回纯文本
        return {
            "summary": content[:500],
            "raw_response": content,
            "parsing": "failed"
        }


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    agent = IntelligenceAgent(user_role="intelligence_analyst")

    # 测试场景
    queries = [
        "分析B区威胁",
        "当前战场态势如何？",
        "搜索D区的雷达系统",
    ]

    for query in queries:
        report = agent.analyze(query)
        print(f"\n📊 报告摘要: {report.get('summary', 'N/A')}")
        print(f"⏱️ 耗时: {report.get('_metadata', {}).get('execution_time_ms', 'N/A')}ms")
        print(f"🔗 Trace: {report.get('_trace', {}).get('trace_id', 'N/A')}")
        print(f"🧠 RAG: {'已启用' if report.get('_metadata', {}).get('rag_context_provided') else '未启用'}")
        print()
