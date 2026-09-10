import logging
import uuid
from typing import Optional, Dict, Any

from .schemas import (
    AnalysisInput, AnalysisResult, DecisionResult, DecisionOption,
    ActionCommand, PipelineResult, PipelineStageStatus,
)
from odap.biz.decision.interfaces.isemantic_retriever import ISemanticRetriever
from odap.biz.decision.interfaces.idecision_oms_service import IDecisionOMSService
from odap.infra.events import get_event_bus

logger = logging.getLogger(__name__)


def _dp_audit(action: str, *, result_status: str = "success",
              result_message: str = "", resource: str = None,
              details: Dict[str, Any] = None) -> None:
    """Decision Pipeline 审计便捷函数：失败仅 warning，不阻断业务"""
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="decision_pipeline",
        )
    except Exception as e:
        logger.warning(f"Audit write failed (decision_pipeline) action={action}: {e}")


def _compute_retrieval_confidence(objects) -> float:
    """从检索结果的真实相关性得分派生分析置信度。

    取有效得分均值并夹到 [0,1]。用均值而非最大值：决策支撑链路上高估置信度是危险方向
    （单个侥幸命中不该让整份分析显得可信）。无任何有效得分时返回 0.0，即 schema 默认值，
    含义是"无证据可支撑置信度"，而非编造 0.7 之类的假精确值（规则 14）。
    """
    scores = [o.score for o in objects if o.score is not None]
    if not scores:
        return 0.0
    return round(min(1.0, max(0.0, sum(scores) / len(scores))), 4)


class DecisionPipeline:
    def __init__(self):
        self._semantic_retriever = None
        self._decision_engine = None
        self._action_executor = None
        self._feedback_loop = None
        self._opa_manager = None
        self._pipelines: Dict[str, Dict[str, Any]] = {}

    @property
    def semantic_retriever(self) -> Optional[ISemanticRetriever]:
        if self._semantic_retriever is None:
            from odap.biz.data.qa.semantic_retriever.retriever import get_semantic_retriever
            self._semantic_retriever = get_semantic_retriever()
        return self._semantic_retriever

    def create_pipeline(self, name: str = "", description: str = "",
                        stages_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建决策流水线（关键生命周期，必记审计）"""
        pipeline_id = f"dp_{uuid.uuid4().hex[:12]}"
        stages = (stages_config or {}).get("stages",
                                           ["analyze", "decide", "validate", "perform", "feedback"])
        try:
            self._pipelines[pipeline_id] = {
                "pipeline_id": pipeline_id,
                "name": name,
                "description": description,
                "stages_count": len(stages),
                "stages": stages,
                "status": "created",
                "created_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            }
            _dp_audit(
                "pipeline_create",
                result_status="success",
                resource=pipeline_id,
                details={
                    "pipeline_id": pipeline_id,
                    "stages_count": len(stages),
                },
            )
            return {
                "pipeline_id": pipeline_id,
                "name": name,
                "stages_count": len(stages),
                "status": "created",
            }
        except Exception as e:
            _dp_audit(
                "pipeline_create",
                result_status="failure",
                resource=pipeline_id,
                result_message=str(e),
                details={"pipeline_id": pipeline_id, "stages_count": len(stages)},
            )
            raise

    @property
    def decision_engine(self):
        if self._decision_engine is None:
            try:
                from odap.biz.decision.decision_recommendation.engine import DecisionRecommendationEngine
                from odap.infra.graph.graph_service import GraphManager
                gm = GraphManager()
                graphiti_client = getattr(gm, "graph", None)
                self._decision_engine = DecisionRecommendationEngine(
                    graphiti_client=graphiti_client,
                )
            except Exception as e:
                logger.warning(f"DecisionPipeline: DecisionRecommendationEngine init failed: {e}")
                self._decision_engine = None
        return self._decision_engine

    @property
    def action_executor(self):
        if self._action_executor is None:
            from odap.biz.decision.action_service.executor import get_action_executor
            self._action_executor = get_action_executor()
        return self._action_executor

    @property
    def feedback_loop(self):
        if self._feedback_loop is None:
            from odap.biz.decision.action_service.feedback_loop import get_feedback_loop
            self._feedback_loop = get_feedback_loop()
        return self._feedback_loop

    @property
    def opa(self):
        if self._opa_manager is None:
            try:
                from odap.infra.opa.opa_service import OPAManagerV2
                self._opa_manager = OPAManagerV2()
            except Exception as e:
                logger.warning(f"DecisionPipeline: OPAManagerV2 import failed (fail-closed): {e}")
                self._opa_manager = None
        return self._opa_manager

    async def execute(self, input_data: AnalysisInput) -> PipelineResult:
        import datetime as _dt
        pipeline_id = f"dp_{uuid.uuid4().hex[:12]}"
        result = PipelineResult(pipeline_id=pipeline_id)
        result.stages = {
            'analyze': PipelineStageStatus.PENDING,
            'decide': PipelineStageStatus.PENDING,
            'validate': PipelineStageStatus.PENDING,
            'perform': PipelineStageStatus.PENDING,
            'feedback': PipelineStageStatus.PENDING,
        }
        started_at = _dt.datetime.now(_dt.timezone.utc)
        self._pipelines[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "workspace_id": input_data.workspace_id or "",
            "status": "running",
            "started_at": started_at.isoformat(),
            "stages_count": 5,
            "stages": ["analyze", "decide", "validate", "perform", "feedback"],
            "stage_status": dict(result.stages),
        }

        def _stages_stats(stages_dict: Dict[str, PipelineStageStatus]):
            success = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.COMPLETED)
            failure = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.FAILED)
            skipped = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.SKIPPED)
            return success, failure, skipped

        # ADR-076 §7：workspace_id 缺失 → 快速失败（不写任何数据）
        if not input_data.workspace_id:
            raise ValueError("workspace_id 缺失，决策流水线拒绝执行（ADR-076 工作空间隔离规则）")

        # Stage 1: Analyze (理解)
        result.stages['analyze'] = PipelineStageStatus.RUNNING
        try:
            analysis = await self._analyze(input_data)
            result.analysis = analysis
            result.stages['analyze'] = PipelineStageStatus.COMPLETED
            await get_event_bus().emit_decision_step(pipeline_id, "analyze",
                f"Analysis complete: {analysis.summary[:200] if analysis.summary else 'N/A'}")
        except Exception as e:
            logger.error(f"DecisionPipeline analyze failed: {e}")
            result.stages['analyze'] = PipelineStageStatus.FAILED
            result.error = f"Analyze failed: {e}"
            await get_event_bus().emit_decision_step(pipeline_id, "analyze_failed", str(e)[:200])
            succ, fail, skip = _stages_stats(result.stages)
            _dp_audit(
                "pipeline_execute",
                result_status="failure",
                resource=pipeline_id,
                result_message=result.error,
                details={
                    "pipeline_id": pipeline_id,
                    "stages_count": len(result.stages),
                    "success_stages_count": succ,
                    "failure_stages_count": fail,
                    "skipped_stages_count": skip,
                    "duration_seconds": round(
                        (_dt.datetime.now(_dt.timezone.utc) - started_at).total_seconds(), 3),
                },
            )
            return result

        # Stage 2: Decide (决策)
        result.stages['decide'] = PipelineStageStatus.RUNNING
        try:
            decision = await self._decide(analysis, input_data)
            result.decision = decision
            result.stages['decide'] = PipelineStageStatus.COMPLETED
            rec_name = decision.recommended_option.name if decision.recommended_option else ""
            desc = f"Decision made: {rec_name[:200] if rec_name else 'N/A'}"
            await get_event_bus().emit_decision_step(pipeline_id, "decide", desc)
        except Exception as e:
            logger.error(f"DecisionPipeline decide failed: {e}")
            result.stages['decide'] = PipelineStageStatus.FAILED
            result.error = f"Decide failed: {e}"
            succ, fail, skip = _stages_stats(result.stages)
            _dp_audit(
                "pipeline_execute",
                result_status="failure",
                resource=pipeline_id,
                result_message=result.error,
                details={
                    "pipeline_id": pipeline_id,
                    "stages_count": len(result.stages),
                    "success_stages_count": succ,
                    "failure_stages_count": fail,
                    "skipped_stages_count": skip,
                    "duration_seconds": round(
                        (_dt.datetime.now(_dt.timezone.utc) - started_at).total_seconds(), 3),
                },
            )
            return result

        # Stage 3: Validate (策略校验)
        result.stages['validate'] = PipelineStageStatus.RUNNING
        try:
            validated = await self._validate(decision, input_data)
            result.decision = validated
            result.stages['validate'] = PipelineStageStatus.COMPLETED

            # ADR-076：决策持久化为一等公民（OPA 门禁在 Stage 3 已完成，满足"落库前过门禁"；失败不阻断主流程）
            try:
                from odap.biz.decision.decision_record import get_decision_service
                record = self._build_decision_record(validated, analysis, input_data)
                saved = await get_decision_service().record_decision(record)
                validated.decision_id = saved.decision_id
            except Exception as persist_err:
                logger.warning("决策持久化失败（不阻断主流程）: %s", persist_err)
        except Exception as e:
            logger.error(f"DecisionPipeline validate failed: {e}")
            result.stages['validate'] = PipelineStageStatus.FAILED
            result.error = f"Validate failed: {e}"
            succ, fail, skip = _stages_stats(result.stages)
            _dp_audit(
                "pipeline_execute",
                result_status="failure",
                resource=pipeline_id,
                result_message=result.error,
                details={
                    "pipeline_id": pipeline_id,
                    "stages_count": len(result.stages),
                    "success_stages_count": succ,
                    "failure_stages_count": fail,
                    "skipped_stages_count": skip,
                    "duration_seconds": round(
                        (_dt.datetime.now(_dt.timezone.utc) - started_at).total_seconds(), 3),
                },
            )
            return result

        # Stage 4: Perform (执行)
        if validated.recommended_option and validated.opa_approved:
            result.stages['perform'] = PipelineStageStatus.RUNNING
            try:
                action_record = await self._perform(validated, input_data)
                result.action_record = action_record
                result.stages['perform'] = PipelineStageStatus.COMPLETED
            except Exception as e:
                logger.error(f"DecisionPipeline perform failed: {e}")
                result.stages['perform'] = PipelineStageStatus.FAILED
                result.error = f"Perform failed: {e}"
                succ, fail, skip = _stages_stats(result.stages)
                _dp_audit(
                    "pipeline_execute",
                    result_status="failure",
                    resource=pipeline_id,
                    result_message=result.error,
                    details={
                        "pipeline_id": pipeline_id,
                        "stages_count": len(result.stages),
                        "success_stages_count": succ,
                        "failure_stages_count": fail,
                        "skipped_stages_count": skip,
                        "duration_seconds": round(
                            (_dt.datetime.now(_dt.timezone.utc) - started_at).total_seconds(), 3),
                    },
                )
                return result
        else:
            result.stages['perform'] = PipelineStageStatus.SKIPPED

        # Stage 5: Feedback (反馈)
        if result.action_record and result.action_record.get('status') == 'completed':
            result.stages['feedback'] = PipelineStageStatus.RUNNING
            try:
                feedback = await self.feedback_loop.close_loop(result.action_record)
                result.feedback = feedback
                result.stages['feedback'] = PipelineStageStatus.COMPLETED
            except Exception as e:
                logger.warning(f"DecisionPipeline feedback failed: {e}")
                result.stages['feedback'] = PipelineStageStatus.FAILED
        else:
            result.stages['feedback'] = PipelineStageStatus.SKIPPED

        # ADR-076 §6.3：决策结果回填（OPA 拒绝/执行失败路径必须留痕；失败不阻断主流程）
        if result.decision and result.decision.decision_id:
            try:
                await self._backfill_decision_outcome(result, input_data.workspace_id)
            except Exception as backfill_err:
                logger.warning("决策结果回填失败（不阻断主流程）: %s", backfill_err)

        succ, fail, skip = _stages_stats(result.stages)
        # 如果任何 stage 失败但最终 return 了，按 failure 记；否则按 success
        overall_status = "success" if fail == 0 else "failure"

        # ADR-064 增补：同步最终阶段状态到进度注册表（供进度查询）
        if pipeline_id in self._pipelines:
            self._pipelines[pipeline_id]["stage_status"] = {
                k: v.value for k, v in result.stages.items()
            }
            self._pipelines[pipeline_id]["status"] = (
                "completed" if overall_status == "success" else "failed"
            )
            self._pipelines[pipeline_id]["finished_at"] = (
                _dt.datetime.now(_dt.timezone.utc).isoformat()
            )

        _dp_audit(
            "pipeline_execute",
            result_status=overall_status,
            resource=pipeline_id,
            details={
                "pipeline_id": pipeline_id,
                "stages_count": len(result.stages),
                "success_stages_count": succ,
                "failure_stages_count": fail,
                "skipped_stages_count": skip,
                "duration_seconds": round(
                    (_dt.datetime.now(_dt.timezone.utc) - started_at).total_seconds(), 3),
            },
        )
        # ADR-065 R3: 通知外部订阅者
        if fail == 0:
            await get_event_bus().emit_decision_completed(
                pipeline_id,
                reasoning=result.decision.reasoning[:500] if result.decision else "",
                evidence=(
                    [result.decision.recommended_option.name]
                    + [o.name for o in result.decision.alternative_options]
                )[:5] if result.decision and result.decision.recommended_option else [],
            )
        return result

    def cancel_pipeline(self, pipeline_id: str, reason: str = "",
                        user_id: str = "anonymous") -> Dict[str, Any]:
        """取消执行中或待执行的流水线（关键生命周期，必记审计）"""
        import datetime as _dt
        if not pipeline_id:
            _dp_audit(
                "pipeline_cancel",
                result_status="failure",
                resource="unknown",
                result_message="Empty pipeline_id",
                details={"user_id": user_id},
            )
            return {"status": "error", "message": "pipeline_id is required"}

        info = self._pipelines.get(pipeline_id)
        if not info:
            _dp_audit(
                "pipeline_cancel",
                result_status="failure",
                resource=pipeline_id,
                result_message="Pipeline not found",
                details={"pipeline_id": pipeline_id, "user_id": user_id},
            )
            return {"status": "error", "message": "Pipeline not found"}

        try:
            info["status"] = "cancelled"
            info["cancelled_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
            info["cancelled_by"] = user_id
            _dp_audit(
                "pipeline_cancel",
                result_status="success",
                resource=pipeline_id,
                details={
                    "pipeline_id": pipeline_id,
                    "user_id": user_id,
                    "stages_count": info.get("stages_count", 0),
                    "reason_len": len(reason or ""),
                    "original_status": "running",
                },
            )
            return {
                "status": "ok",
                "pipeline_id": pipeline_id,
                "cancelled": True,
            }
        except Exception as e:
            _dp_audit(
                "pipeline_cancel",
                result_status="failure",
                resource=pipeline_id,
                result_message=str(e),
                details={
                    "pipeline_id": pipeline_id,
                    "user_id": user_id,
                    "stages_count": info.get("stages_count", 0),
                },
            )
            raise

    def get_pipeline_progress(self, pipeline_id: str = "", workspace_id: str = "") -> Dict[str, Any]:
        """ADR-064 增补：流水线进度可观测查询。

        Args:
            pipeline_id: 指定流水线 ID；为空则列出全部。
            workspace_id: 过滤条件（安全要求：按 workspace 过滤）。

        Returns:
            {
                "pipelines": [
                    {
                        "pipeline_id", "workspace_id", "status",
                        "stage_status": {stage: status},   # 当前阶段进度
                        "completed_stages", "total_stages", "progress_ratio",
                        "started_at", "finished_at",
                    }, ...
                ],
                "count": int,
            }
        """
        items = []
        for pid, info in self._pipelines.items():
            if pipeline_id and pid != pipeline_id:
                continue
            if workspace_id and info.get("workspace_id", "") != workspace_id:
                continue

            stages = info.get("stages", [])
            stage_status = info.get("stage_status", {})
            completed = sum(
                1 for s in stages
                if stage_status.get(s) in ("completed", "skipped", "failed")
            )
            total = len(stages) or 1
            items.append({
                "pipeline_id": pid,
                "workspace_id": info.get("workspace_id", ""),
                "status": info.get("status", "unknown"),
                "stage_status": stage_status,
                "current_stage": _current_stage(stages, stage_status),
                "completed_stages": completed,
                "total_stages": total,
                "progress_ratio": round(completed / total, 4),
                "started_at": info.get("started_at"),
                "finished_at": info.get("finished_at"),
            })
        return {"pipelines": items, "count": len(items)}

    async def _analyze(self, input_data: AnalysisInput) -> AnalysisResult:
        retrieval = await self.semantic_retriever.retrieve(input_data.query, top_k=10)

        entities = []
        for obj in retrieval.objects:
            entities.append({
                'object_id': obj.object_id,
                'object_type': obj.object_type,
                'properties': obj.properties,
                'links': [{'target_id': l.get('target_id'), 'link_type': l.get('link_type')} for l in obj.links],
            })

        return AnalysisResult(
            summary=retrieval.answer_context[:500] if retrieval.answer_context else "",
            entities=entities,
            patterns=[],
            risks=[],
            confidence=_compute_retrieval_confidence(retrieval.objects),
            raw_context=retrieval.answer_context,
        )

    async def _decide(self, analysis: AnalysisResult, input_data: AnalysisInput) -> DecisionResult:
        if self.decision_engine:
            try:
                from odap.biz.decision.decision_recommendation.models import RecommendationRequest
                request = RecommendationRequest(
                    analysis_result={
                        'summary': analysis.summary,
                        'entities': analysis.entities,
                        'risks': analysis.risks,
                        'context': input_data.context,
                    },
                    constraints=input_data.context.get('constraints', {}),
                )
                # ADR-076 修复：原 recommend() 方法不存在（同步调用必然 AttributeError 走兜底），
                # 实际方法为 generate_recommendation（async）
                recommendation = await self.decision_engine.generate_recommendation(request)
                recommended = None
                alternatives = []
                if recommendation and hasattr(recommendation, 'recommended_option') and recommendation.recommended_option:
                    opt = recommendation.recommended_option
                    recommended = DecisionOption(
                        option_id=getattr(opt, 'option_id', 'opt_1'),
                        name=getattr(opt, 'name', 'Recommended'),
                        description=getattr(opt, 'description', ''),
                        risk_level=getattr(opt, 'risk_level', 'low'),
                        expected_outcome=getattr(opt, 'expected_outcome', ''),
                        priority=1,
                    )
                return DecisionResult(
                    decision_id=f"dec_{uuid.uuid4().hex[:12]}",
                    recommended_option=recommended,
                    alternative_options=alternatives,
                    reasoning=(
                        recommendation.recommended_option.rationale
                        if recommendation.recommended_option
                        else getattr(recommendation, 'decision_summary', '')
                    ),
                    confidence=recommendation.confidence,
                )
            except Exception as e:
                logger.warning(f"DecisionEngine recommend failed, using fallback: {e}")

        return await self._fallback_decide(analysis, input_data)

    async def _fallback_decide(self, analysis: AnalysisResult, input_data: AnalysisInput) -> DecisionResult:
        from odap.biz.core.ontology.public import get_oms_service
        oms: IDecisionOMSService = get_oms_service()

        options = []
        for entity in analysis.entities[:5]:
            obj_type = entity.get('object_type', '')
            action_types = oms.list_action_types(target_type=obj_type)
            for act in action_types[:3]:
                options.append(DecisionOption(
                    option_id=f"opt_{uuid.uuid4().hex[:8]}",
                    name=act.get('display_name', act.get('name', '')),
                    description=act.get('description', ''),
                    action_type_id=act['action_type_id'],
                    target_object_id=entity.get('object_id', ''),
                    target_object_type=obj_type,
                    parameters={},
                    risk_level='high' if act.get('confirmation_required') else 'low',
                    priority=len(options) + 1,
                ))

        recommended = options[0] if options else None
        alternatives = options[1:] if len(options) > 1 else []

        return DecisionResult(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            recommended_option=recommended,
            alternative_options=alternatives,
            reasoning=f"Based on analysis of {len(analysis.entities)} entities, {len(options)} actions available",
            confidence=analysis.confidence,
        )

    async def _validate(self, decision: DecisionResult, input_data: AnalysisInput) -> DecisionResult:
        if not decision.recommended_option:
            decision.opa_approved = False
            return decision

        if self.opa:
            try:
                result = self.opa.check_permission_abac(
                    user=input_data.agent_id or input_data.context.get('user', 'system'),
                    action=decision.recommended_option.action_type_id,
                    resource=decision.recommended_option.target_object_id,
                    environment={'workspace_id': input_data.workspace_id},
                )
                decision.opa_approved = result.get('allow', False)
                decision.opa_decision = result
            except Exception as e:
                logger.error(f"OPA validation failed (fail-closed): {e}")
                decision.opa_approved = False
                decision.opa_decision = {'allow': False, 'reason': f'OPA check error (fail-closed): {e}'}
        else:
            decision.opa_approved = False
            decision.opa_decision = {'allow': False, 'reason': 'No OPA configured (fail-closed)'}

        return decision

    async def _perform(self, decision: DecisionResult, input_data: AnalysisInput) -> Dict[str, Any]:
        from odap.biz.decision.action_service.schemas import ActionRequest

        option = decision.recommended_option
        action_request = ActionRequest(
            action_type_id=option.action_type_id,
            target_object_id=option.target_object_id,
            target_object_type=option.target_object_type,
            parameters=option.parameters,
            requested_by=input_data.agent_id or 'decision_pipeline',
            reason=decision.reasoning,
            agent_id=input_data.agent_id,
            decision_id=decision.decision_id or None,  # ADR-076：决策关联穿透
        )

        record = await self.action_executor.submit_action(action_request)

        # ADR-076 Q3：Decision -[:TRIGGERED]-> ActionRecord 边（失败不阻断）
        if decision.decision_id and input_data.workspace_id and record:
            try:
                from odap.biz.decision.decision_record import get_decision_service
                ar_dict = record if isinstance(record, dict) else record.model_dump()
                await get_decision_service().link_triggered_action(
                    decision.decision_id, input_data.workspace_id, ar_dict
                )
            except Exception as link_err:
                logger.warning("TRIGGERED 边建立失败（不阻断）: %s", link_err)
        return record


    def _build_decision_record(self, decision: DecisionResult, analysis: AnalysisResult, input_data: AnalysisInput):
        """DecisionResult + AnalysisResult → DecisionRecord（ADR-076 §3 映射）。"""
        from odap.biz.decision.decision_record import DecisionRecord

        option = decision.recommended_option
        return DecisionRecord(
            decision_id=decision.decision_id,
            workspace_id=input_data.workspace_id or "",
            context_summary=analysis.summary or input_data.query,
            constraints=input_data.context.get("constraints", {}),
            reasoning=decision.reasoning,
            reasoning_trace=(
                [{"step": 1, "engine": "decision_pipeline", "rule_text": decision.reasoning[:500]}]
                if decision.reasoning
                else []
            ),
            confidence=decision.confidence,
            evidence_episode_ids=[],
            evidence_entity_ids=[
                e.get("object_id", "") for e in analysis.entities[:10] if e.get("object_id")
            ],
            recommended_option=option.name if option else "",
            alternative_options=[o.name for o in decision.alternative_options],
            decision_method="recommendation_engine" if self.decision_engine else "heuristic_fallback",
            decision_type="general",
            agent_id=input_data.agent_id,
            opa_approved=decision.opa_approved,
            opa_decision=decision.opa_decision,
        )

    async def _backfill_decision_outcome(self, result: PipelineResult, workspace_id: str) -> None:
        """ADR-076 §6.3：按 action 执行状态回填决策结果（rejected 路径必须留痕）。"""
        from odap.biz.decision.decision_record import DecisionOutcome, get_decision_service

        decision = result.decision
        ar = result.action_record
        if ar is not None and not isinstance(ar, dict):
            ar = ar.model_dump()
        ar = ar or {}
        status = str(ar.get("status", ""))

        if not decision.opa_approved and not ar:
            outcome = DecisionOutcome.REJECTED
        elif status == "completed":
            outcome = DecisionOutcome.SUCCESS
        elif status == "rejected":
            outcome = DecisionOutcome.REJECTED
        elif status == "failed":
            outcome = DecisionOutcome.FAILURE
        else:
            outcome = DecisionOutcome.PENDING

        feedback = result.feedback if isinstance(result.feedback, dict) else {}
        await get_decision_service().update_decision_outcome(
            decision_id=decision.decision_id,
            workspace_id=workspace_id or "",
            outcome=outcome,
            outcome_details={
                "action_record_id": ar.get("action_record_id"),
                "action_status": status or None,
                "feedback_pipeline": feedback,
            },
            feedback_summary=feedback.get("status"),
        )


def _current_stage(stages, stage_status) -> str:
    """返回当前所处阶段名（首个 running 或最后的 pending 之后）"""
    for s in stages:
        if stage_status.get(s) == "running":
            return s
    # 无 running：返回第一个 pending
    for s in stages:
        if stage_status.get(s) in (None, "pending"):
            return s
    return stages[-1] if stages else ""


_pipeline_instance = None


def get_decision_pipeline() -> DecisionPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = DecisionPipeline()
    return _pipeline_instance
