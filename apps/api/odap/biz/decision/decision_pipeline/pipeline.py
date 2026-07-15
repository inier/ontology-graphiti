import logging
import uuid
from typing import Optional, Dict, Any

from .schemas import (
    AnalysisInput, AnalysisResult, DecisionResult, DecisionOption,
    ActionCommand, PipelineResult, PipelineStageStatus,
)

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


class DecisionPipeline:
    def __init__(self):
        self._semantic_retriever = None
        self._decision_engine = None
        self._action_executor = None
        self._feedback_loop = None
        self._opa_manager = None
        self._pipelines: Dict[str, Dict[str, Any]] = {}

    @property
    def semantic_retriever(self):
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
                self._decision_engine = DecisionRecommendationEngine()
            except Exception as e:
                logger.warning(f"DecisionPipeline: DecisionRecommendationEngine import failed: {e}")
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
            "status": "running",
            "started_at": started_at.isoformat(),
            "stages_count": 5,
            "stages": ["analyze", "decide", "validate", "perform", "feedback"],
        }

        def _stages_stats(stages_dict: Dict[str, PipelineStageStatus]):
            success = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.COMPLETED)
            failure = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.FAILED)
            skipped = sum(1 for s in stages_dict.values() if s == PipelineStageStatus.SKIPPED)
            return success, failure, skipped

        # Stage 1: Analyze (理解)
        result.stages['analyze'] = PipelineStageStatus.RUNNING
        try:
            analysis = await self._analyze(input_data)
            result.analysis = analysis
            result.stages['analyze'] = PipelineStageStatus.COMPLETED
        except Exception as e:
            logger.error(f"DecisionPipeline analyze failed: {e}")
            result.stages['analyze'] = PipelineStageStatus.FAILED
            result.error = f"Analyze failed: {e}"
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

        succ, fail, skip = _stages_stats(result.stages)
        # 如果任何 stage 失败但最终 return 了，按 failure 记；否则按 success
        overall_status = "success" if fail == 0 else "failure"
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
            confidence=0.7,
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
                recommendation = self.decision_engine.recommend(request)
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
                    reasoning=getattr(recommendation, 'reasoning', ''),
                    confidence=getattr(recommendation, 'confidence', 0.5),
                )
            except Exception as e:
                logger.warning(f"DecisionEngine recommend failed, using fallback: {e}")

        return await self._fallback_decide(analysis, input_data)

    async def _fallback_decide(self, analysis: AnalysisResult, input_data: AnalysisInput) -> DecisionResult:
        from odap.biz.core.ontology.application.oms.services import get_oms_service
        oms = get_oms_service()

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
            confidence=0.5,
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
        )

        record = await self.action_executor.submit_action(action_request)
        return record


_pipeline_instance = None


def get_decision_pipeline() -> DecisionPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = DecisionPipeline()
    return _pipeline_instance
