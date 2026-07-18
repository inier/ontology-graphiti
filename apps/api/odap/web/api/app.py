import os
import sys
import json
import logging
import asyncio
import uuid
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from odap.infra.config_composer import get_config

logger = logging.getLogger("simulator_web")

SCENARIOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "storage",
    "versions",
    "scenarios"
)

# ── FastAPI 依赖检查 ────────────────────────────────
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Depends
    from fastapi.responses import JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI 未安装，Web 服务不可用。请运行: pip install fastapi uvicorn python-multipart")

# Auth dependency
try:
    from odap.infra.security.jwt_auth import get_current_user
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    logger.warning("JWT auth module not available, endpoints will be unauthenticated")

from odap.biz.core.ontology.design.schema.document import (
    OntologyDocument, OntologyDocumentSchema, OntologyValidationError,
    DocType, SourceType
)
from odap.biz.core.ontology.design.services.pipeline_service import PipelineService as OntologyHotWritePipeline
from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
from odap.biz.core.ontology.design.ingestion_split import NewsIngester, FreeNewsIngester, ManualInputHandler, ConflictEventGenerator, OntologyDocumentIO
from odap.infra.graph.graph_service import GraphManager

from odap.infra.storage.scenario_store import ScenarioStore, scenario_store as _shared_scenario_store

class MockDataWebService:
    """
    模拟数据生成 Web 服务
    提供 REST API 和 WebSocket 实时事件流
    """

    def __init__(
        self,
        pipeline: OntologyHotWritePipeline = None,
        version_manager: OntologyVersionManager = None,
        llm_client=None,
        tavily_api_key: str = None,
        host: str = "0.0.0.0",
        port: int = 8765,
    ):
        if not FASTAPI_AVAILABLE:
            raise RuntimeError("FastAPI 未安装，请运行: pip install fastapi uvicorn python-multipart")

        self.pipeline = pipeline or OntologyHotWritePipeline.get_instance()
        self.versions = version_manager or OntologyVersionManager.get_instance()
        self.host = host
        self.port = port

        # WebSocket 客户端集合
        self._ws_clients: Set[WebSocket] = set()

        # 事件总线
        from odap.web.ws import DomainEventBus
        self._event_bus = DomainEventBus()

        # 异步任务追踪（联网检索）
        self._tasks: Dict[str, Dict[str, Any]] = {}
        
        # 初始化 GraphManager
        self._graph_manager = GraphManager()

        # 数据层 - 使用 shared 单例
        self.scenario_store = _shared_scenario_store
        self.news_ingester = NewsIngester(llm_client=llm_client, tavily_api_key=tavily_api_key)
        self.free_news_ingester = FreeNewsIngester(llm_client=llm_client)
        self.manual_handler = ManualInputHandler(llm_client=llm_client)
        self.random_gen = ConflictEventGenerator(llm_client=llm_client)
        self.doc_io = OntologyDocumentIO(version_manager=self.versions)

        # 订阅本体更新 Hook
        self.pipeline.register_ontology_hook(self._on_ontology_updated)

        # 构建 FastAPI 应用
        self.app = self._build_app()
        
        # 注册本体摄入和构建路由
        try:
            from odap.biz.core.ontology.application.api.routes import router as ontology_ingest_router
            self.app.include_router(ontology_ingest_router)
        except Exception as e:
            logger.warning(f"本体摄入路由注册失败: {e}")

        # 注册统一查询服务路由 (ADR-055)
        try:
            from odap.infra.query.routes import router as query_router
            self.app.include_router(query_router)
        except Exception as e:
            logger.warning(f"统一查询路由注册失败: {e}")

        # 注册 OMS 本体元数据路由
        try:
            from odap.biz.core.ontology.application.oms.routes import router as oms_router
            self.app.include_router(oms_router)
        except Exception as e:
            logger.warning(f"OMS 路由注册失败: {e}")

        # 注册本体 API 路由 (003-ontology-redesign)
        try:
            from odap.biz.core.ontology.ontology_api.api import router as ontology_api_router
            self.app.include_router(ontology_api_router)
        except Exception as e:
            logger.warning(f"本体API路由注册失败: {e}")

        # 注册抽取路由 (003-ontology-redesign)
        try:
            from odap.biz.core.ontology.extraction.api import router as extraction_router
            self.app.include_router(extraction_router)
        except Exception as e:
            logger.warning(f"抽取路由注册失败: {e}")

        # 注册工具注册表路由
        try:
            from odap.biz.platform.tool_registry.api.routes import router as tool_router
            self.app.include_router(tool_router)
        except Exception as e:
            logger.warning(f"工具注册表路由注册失败: {e}")

        # 注册技能系统路由
        try:
            from odap.biz.platform.skill_system.api.routes import router as skill_router
            self.app.include_router(skill_router)
        except Exception as e:
            logger.warning(f"技能系统路由注册失败: {e}")

        # 注册 Agent 路由
        try:
            from odap.biz.integration.openharness_agent import router as agent_router
            self.app.include_router(agent_router)
        except Exception as e:
            logger.warning(f"Agent 路由注册失败: {e}")

        # 注册认证路由
        try:
            from odap.infra.security.auth_routes import router as auth_router
            self.app.include_router(auth_router)
        except Exception as e:
            logger.warning(f"认证路由注册失败: {e}")

        # 注册角色管理路由
        try:
            from odap.biz.platform.roles.api.routes import router as roles_router
            self.app.include_router(roles_router)
        except Exception as e:
            logger.warning(f"角色路由注册失败: {e}")

        # 注册智能体管理路由
        try:
            from odap.biz.management.agent_management.api.routes import router as agent_mgmt_router
            self.app.include_router(agent_mgmt_router)
        except Exception as e:
            logger.warning(f"智能体管理路由注册失败: {e}")

        # 注册审计路由
        try:
            from odap.infra.security import audit_router
            self.app.include_router(audit_router)
        except Exception as e:
            logger.warning(f"审计路由注册失败: {e}")

        # 注册工作空间路由
        try:
            from odap.biz.platform.workspace.api.routes import router as workspace_router
            self.app.include_router(workspace_router)
        except Exception as e:
            logger.warning(f"工作空间路由注册失败: {e}")

        # 注册 OPA 策略路由
        try:
            from odap.infra.opa.routes import router as policy_router
            self.app.include_router(policy_router)
        except Exception as e:
            logger.warning(f"OPA策略路由注册失败: {e}")

        # 注册 QA 问答路由
        try:
            from odap.biz.data.qa.api.routes import router as qa_router
            self.app.include_router(qa_router)
        except Exception as e:
            logger.warning(f"QA问答路由注册失败: {e}")

        # 注册知识库路由
        try:
            from odap.biz.data.knowledge_base.api.routes import router as kb_router
            self.app.include_router(kb_router)
        except Exception as e:
            logger.warning(f"知识库路由注册失败: {e}")

        # 注册 Hook 系统路由
        try:
            from odap.biz.integration.hook_system.api.routes import router as hook_router
            self.app.include_router(hook_router)
        except Exception as e:
            logger.warning(f"Hook系统路由注册失败: {e}")

        # 注册 MCP 适配器路由
        try:
            from odap.biz.integration.mcp_adapter.api.routes import router as mcp_router
            self.app.include_router(mcp_router)
        except Exception as e:
            logger.warning(f"MCP适配器路由注册失败: {e}")

        # 注册前端兼容路由
        try:
            from odap.biz.integration.frontend_compat.api.routes import router as frontend_router
            self.app.include_router(frontend_router)
        except Exception as e:
            logger.warning(f"前端兼容路由注册失败: {e}")

        # 注册事件模拟器路由
        try:
            from odap.biz.simulation.event_simulator.api.routes import router as event_router
            self.app.include_router(event_router)
        except Exception as e:
            logger.warning(f"事件模拟器路由注册失败: {e}")

        # 注册决策路由
        try:
            from odap.biz.decision.action_service.routes import router as action_router
            self.app.include_router(action_router)
        except Exception as e:
            logger.warning(f"决策路由注册失败: {e}")

        try:
            from odap.biz.decision.decision_pipeline.routes import router as decision_pipeline_router
            self.app.include_router(decision_pipeline_router)
        except Exception as e:
            logger.warning(f"决策管线路由注册失败: {e}")

        # 注册感知路由
        try:
            from odap.biz.data.perception.routes import router as perception_router
            self.app.include_router(perception_router)
        except Exception as e:
            logger.warning(f"感知路由注册失败: {e}")

        # 注册模拟沙箱路由
        try:
            from odap.biz.simulation.simulation_sandbox.routes import router as sandbox_router
            self.app.include_router(sandbox_router)
        except Exception as e:
            logger.warning(f"模拟沙箱路由注册失败: {e}")

        # 注册业务管理路由
        try:
            from odap.biz.management.business.api.routes import router as business_router
            self.app.include_router(business_router)
        except Exception as e:
            logger.warning(f"业务管理路由注册失败: {e}")

        # 注册会话记忆路由
        try:
            from odap.biz.platform.session_memory.api.routes import router as session_memory_router
            self.app.include_router(session_memory_router)
        except Exception as e:
            logger.warning(f"会话记忆路由注册失败: {e}")

        # 注册数据仓库路由
        try:
            from odap.biz.data.data_warehouse.api.routes import router as data_warehouse_router
            self.app.include_router(data_warehouse_router)
        except Exception as e:
            logger.warning(f"数据仓库路由注册失败: {e}")

        # 注册认知路由
        try:
            from odap.biz.core.cognition.api.routes import router as cognition_router
            self.app.include_router(cognition_router)
        except Exception as e:
            logger.warning(f"认知路由注册失败: {e}")

        # 注册反馈路由
        try:
            from odap.biz.simulation.feedback.api.routes import router as feedback_router
            self.app.include_router(feedback_router)
        except Exception as e:
            logger.warning(f"反馈路由注册失败: {e}")

        # 注册推演路由
        try:
            from odap.biz.simulation.simulation_deduction.api.routes import router as deduction_router
            self.app.include_router(deduction_router)
        except Exception as e:
            logger.warning(f"推演路由注册失败: {e}")

        # 注册语义地图路由
        try:
            from odap.biz.data.semantic_map.api.routes import router as semantic_map_router
            self.app.include_router(semantic_map_router)
        except Exception as e:
            logger.warning(f"语义地图路由注册失败: {e}")

        # 注册对象服务路由
        try:
            from odap.infra.object_service.routes import router as osv2_router
            self.app.include_router(osv2_router)
        except Exception as e:
            logger.warning(f"对象服务路由注册失败: {e}")

        # 注册技能扩展路由
        try:
            from odap.biz.platform.skill_system.api.routes_extended import router as skill_ext_router
            self.app.include_router(skill_ext_router)
        except Exception as e:
            logger.warning(f"技能扩展路由注册失败: {e}")

        # 注册 Agent 调度路由
        try:
            from odap.biz.core.agent.api.routes import router as agent_dispatch_router
            self.app.include_router(agent_dispatch_router)
        except Exception as e:
            logger.warning(f"Agent调度路由注册失败: {e}")

        # 注册 Markdown 策略路由
        try:
            from odap.infra.opa.markdown_routes import router as markdown_policy_router
            self.app.include_router(markdown_policy_router)
        except Exception as e:
            logger.warning(f"Markdown策略路由注册失败: {e}")

        # 注册 i18n 国际化路由
        try:
            from odap.biz.platform.i18n.api.routes import router as i18n_router
            self.app.include_router(i18n_router)
        except Exception as e:
            logger.warning(f"i18n路由注册失败: {e}")

        # 注册语义管理台 - 动态配置 + USL 写回
        try:
            from odap.biz.semantic_admin.sa_config.api.routes import router as semantic_admin_sa_config_router
            self.app.include_router(semantic_admin_sa_config_router)
        except Exception as e:
            logger.warning(f"sa_config路由注册失败: {e}")

        try:
            from odap.biz.semantic_admin.usl_writeback.api.routes import router as semantic_admin_writeback_router
            self.app.include_router(semantic_admin_writeback_router)
        except Exception as e:
            logger.warning(f"USL写回路由注册失败: {e}")

        # 注册本体版本管理路由
        try:
            from odap.biz.core.ontology.design.version.api.routes import router as ontology_version_router
            self.app.include_router(ontology_version_router)
        except Exception as e:
            logger.warning(f"本体版本管理路由注册失败: {e}")

        # 注册本体模型路由
        try:
            from odap.biz.core.ontology.design.model.api.routes import router as ontology_model_router
            self.app.include_router(ontology_model_router)
        except Exception as e:
            logger.warning(f"本体模型路由注册失败: {e}")

        # 注册蓝图设计器路由
        try:
            from odap.biz.core.ontology.application.harness.blueprint.routes import router as blueprint_designer_router
            self.app.include_router(blueprint_designer_router)
        except Exception as e:
            logger.warning(f"蓝图设计器路由注册失败: {e}")

        try:
            from odap.biz.core.ontology.application.harness.blueprint.api.runtime_routes import router as blueprint_runtime_router
            self.app.include_router(blueprint_runtime_router)
        except Exception as e:
            logger.warning(f"蓝图运行时路由注册失败: {e}")

        # 注册沙箱API路由（修正路径）
        try:
            from odap.biz.simulation.simulation_sandbox.api.routes import router as sandbox_api_router
            self.app.include_router(sandbox_api_router)
        except Exception as e:
            logger.warning(f"沙箱API路由注册失败: {e}")

    def _build_app(self, static_dir: str = None) -> 'FastAPI':
        app = FastAPI(
            title="ODAP Mock Data Generator v2.0",
            description="模拟数据生成与本体热写入服务",
            version="2.0.0"
        )

        # CORS 配置
        _cors_origins_str = get_config("general.cors_origins", "http://localhost:5173,http://localhost:8000")
        _cors_origins: List[str] = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        )

        from odap.infra.middleware.audit_middleware import AuditMiddleware
        app.add_middleware(AuditMiddleware)

        # 静态文件服务
        if static_dir:
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # 知识库上传文件静态服务（仅 MinIO 不可用时的本地降级兜底）
        _uploads_dir = os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "uploads", "kb"
        )
        os.makedirs(_uploads_dir, exist_ok=True)
        app.mount("/uploads/kb", StaticFiles(directory=_uploads_dir), name="kb-uploads")

        # ── 基础接口 ──────────────────────────────────────

        @app.get("/")
        async def root():
            return {"service": "ODAP Mock Data Generator", "version": "2.0.0", "status": "running"}

        @app.get("/health")
        async def health():
            return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

        # ── 场景管理 ──────────────────────────────────────

        @app.post("/api/scenarios")
        async def create_scenario(body: dict, user=Depends(get_current_user)):
            name = body.get("name", "未命名场景")
            desc = body.get("description", "")
            scenario_id = self.scenario_store.create(name, desc)
            return {"scenario_id": scenario_id, "name": name}

        @app.get("/api/scenarios")
        async def list_scenarios(user=Depends(get_current_user)):
            return {"scenarios": self.scenario_store.list_scenarios()}

        @app.get("/api/scenarios/{scenario_id}")
        async def get_scenario(scenario_id: str, user=Depends(get_current_user)):
            scenario = self.scenario_store.get_scenario(scenario_id)
            if not scenario:
                raise HTTPException(status_code=404, detail="场景不存在")
            return scenario

        @app.post("/api/scenarios/{scenario_id}/sync")
        async def sync_scenario(scenario_id: str, user=Depends(get_current_user)):
            result = self.scenario_store.sync_to_graphiti(scenario_id)
            return result

        @app.get("/api/scenarios/{scenario_id}/timeline")
        async def get_timeline(scenario_id: str, user=Depends(get_current_user)):
            events = self.scenario_store.get_timeline(scenario_id)
            return {"scenario_id": scenario_id, "events": events, "count": len(events)}

        @app.get("/api/scenarios/{scenario_id}/entities")
        async def get_entities(scenario_id: str, snapshot_time: str = None, user=Depends(get_current_user)):
            entities = self.scenario_store.get_entities(scenario_id, snapshot_time)
            return {"scenario_id": scenario_id, "entities": entities, "count": len(entities)}

        @app.get("/api/scenarios/{scenario_id}/relations")
        async def get_relations(scenario_id: str, user=Depends(get_current_user)):
            graph = self.scenario_store.get_relations(scenario_id)
            return {"scenario_id": scenario_id, **graph}

        @app.get("/api/scenarios/{scenario_id}/export")
        async def export_scenario(scenario_id: str, user=Depends(get_current_user)):
            docs = self.scenario_store.get_documents(scenario_id)
            content = await self.doc_io.export_scenario(scenario_id, docs)
            return Response(
                content=content,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="scenario-{scenario_id}.odoc.json"'},
            )

        # ── 数据摄入 ─────────────────────────────────────

        @app.post("/api/ingest/manual")
        async def ingest_manual(body: dict, user=Depends(get_current_user)):
            """手动录入数据"""
            data = body.get("data", {})
            scenario_id = body.get("scenario_id")

            try:
                doc = await self.manual_handler.from_form(body, scenario_id=scenario_id)
                ver = await self.pipeline.ingest(doc)

                if scenario_id:
                    self.scenario_store.add_document(scenario_id, doc)
                    asyncio.create_task(asyncio.to_thread(self.scenario_store.sync_to_graphiti, scenario_id))

                return {
                    "task_id": ver.version_id,
                    "success": True,
                    "version": ver.version_id
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("silent except caught in {exc} (line 481)", exc_info=True)
                return {
                    "task_id": f"err-{uuid.uuid4().hex[:8]}",
                    "success": False,
                    "error": str(e)
                }

        @app.post("/api/ingest/text")
        async def ingest_text(body: dict, user=Depends(get_current_user)):
            """文本摄入（自然语言转本体）"""
            text = body.get("text", "")
            scenario_id = body.get("scenario_id")

            try:
                doc = await self.manual_handler.from_natural_language(text, scenario_id=scenario_id)
                ver = await self.pipeline.ingest(doc)

                if scenario_id:
                    self.scenario_store.add_document(scenario_id, doc)
                    asyncio.create_task(asyncio.to_thread(self.scenario_store.sync_to_graphiti, scenario_id))

                return {
                    "task_id": ver.version_id,
                    "success": True,
                    "version": ver.version_id
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("silent except caught in {exc} (line 509)", exc_info=True)
                return {
                    "task_id": f"err-{uuid.uuid4().hex[:8]}",
                    "success": False,
                    "error": str(e)
                }

        @app.post("/api/ingest/news")
        async def ingest_news(body: dict, user=Depends(get_current_user)):
            """新闻 URL 摄入（联网检索 + LLM 归纳）"""
            url = body.get("url", "")
            scenario_id = body.get("scenario_id")

            if not url:
                return {"success": False, "error": "URL 不能为空"}

            try:
                logger.info(f"开始新闻摄入: {url}, scenario_id: {scenario_id}")

                # 直接返回成功响应，避免网络请求阻塞
                # 实际摄入操作放在后台执行
                asyncio.create_task(self._process_news_ingest(url, scenario_id))

                return {
                    "success": True,
                    "task_id": f"news-{int(time.time())}",
                    "version": f"news-{int(time.time())}"
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"新闻摄入异常: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        async def _process_news_ingest(self, url: str, scenario_id: str):
            """后台处理新闻摄入"""
            try:
                logger.info(f"后台处理新闻摄入: {url}")
                docs = await self.free_news_ingester.ingest(url, title_hint="", event_context="")
                if not docs:
                    logger.warning(f"无法从URL获取内容: {url}")
                    return
                doc = docs[0]
                ver = await self.pipeline.ingest(doc)
                
                if scenario_id:
                    doc.scenario_id = scenario_id
                    self.scenario_store.add_document(scenario_id, doc)
                    asyncio.create_task(asyncio.to_thread(self.scenario_store.sync_to_graphiti, scenario_id))
                
                logger.info(f"新闻摄入完成: {url}, 版本: {ver.version_id}")
            except Exception as e:
                logger.error(f"后台处理新闻摄入失败: {e}")

        @app.post("/api/ingest/random")
        async def ingest_random(body: dict, user=Depends(get_current_user)):
            """随机生成数据"""
            parties = body.get("parties", ["red", "blue"])
            count = min(body.get("count", 1), 20)
            scenario_id = body.get("scenario_id")
            context = body.get("context", {})

            docs = await self.random_gen.generate(
                parties=parties,
                scenario_context=context,
                count=count,
                scenario_id=scenario_id,
            )

            versions = []
            for doc in docs:
                ver = await self.pipeline.ingest(doc)
                if scenario_id:
                    self.scenario_store.add_document(scenario_id, doc)
                versions.append(ver.version_id)

            return {
                "success": True,
                "doc_count": len(docs),
                "versions": versions
            }

        @app.post("/api/ingest/import")
        async def import_scenario(file: UploadFile = File(...), scenario_id: str = None, user=Depends(get_current_user)):
            """导入本体文档"""
            try:
                content = await file.read()
                docs = await self.doc_io.import_file(content, scenario_id=scenario_id)

                versions = []
                for doc in docs:
                    ver = await self.pipeline.ingest(doc)
                    if scenario_id:
                        self.scenario_store.add_document(scenario_id, doc)
                    versions.append(ver.version_id)

                return {
                    "success": True,
                    "doc_count": len(docs),
                    "versions": versions
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.warning("silent except caught in {exc} (line 615)", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

        # ── 版本管理 ─────────────────────────────────────

        @app.get("/api/versions")
        async def list_versions(user=Depends(get_current_user)):
            versions = await self.versions.list(limit=100)
            version_dicts = [v.to_dict() if hasattr(v, 'to_dict') else v for v in versions]
            return {"versions": version_dicts, "total": len(version_dicts)}

        @app.get("/api/versions/{version_id}")
        async def get_version(version_id: str, user=Depends(get_current_user)):
            ver = await self.versions.get(version_id)
            if not ver:
                raise HTTPException(status_code=404, detail="版本不存在")
            return ver.to_dict() if hasattr(ver, 'to_dict') else ver

        @app.post("/api/versions/{version_id}/rollback")
        async def rollback(version_id: str, user=Depends(get_current_user)):
            try:
                result = await self.versions.rollback(version_id)
                return result
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/versions/diff")
        async def diff_versions(version_a: str, version_b: str, user=Depends(get_current_user)):
            try:
                diff = await self.versions.diff(version_a, version_b)
                return diff
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        # ── 实体历史 ─────────────────────────────────────

        @app.get("/api/entities/{entity_id}/history")
        async def get_entity_history(entity_id: str, user=Depends(get_current_user)):
            try:
                history = await self.pipeline.get_entity_history(entity_id)
                return history
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        # ── 统计信息 ─────────────────────────────────────

        @app.get("/api/stats")
        async def stats(user=Depends(get_current_user)):
            return {
                "pipeline": self.pipeline.get_stats(),
                "scenarios": len(self.scenario_store.list_scenarios()),
                "ws_clients": len(self._ws_clients),
            }

        # ── WebSocket 实时事件流 ───────────────────────────

        @app.websocket("/ws/events")
        async def websocket_endpoint(websocket: WebSocket, workspace_id: Optional[str] = None):
            await self._event_bus.connect(websocket, workspace_id)
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                        msg = json.loads(raw) if raw else {}
                        msg_type = msg.get("type", "")
                        if msg_type == "ping":
                            await websocket.send_text(json.dumps({"type": "pong"}))
                        elif msg_type == "subscribe":
                            pass
                    except asyncio.TimeoutError:
                        try:
                            await websocket.send_text(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            logger.warning("silent except caught in {exc} (line 696)", exc_info=True)
                            break
            except WebSocketDisconnect:
                pass
            finally:
                self._event_bus.disconnect(websocket, workspace_id)

        return app

    async def _on_ontology_updated(self, context, payload: dict):
        """Hook 回调：广播本体更新到所有 WebSocket 客户端"""
        workspace_id = payload.get("workspace_id") if isinstance(payload, dict) else None
        await self._event_bus.emit("ontology_update", payload, workspace_id)

    async def _broadcast(self, message: str):
        """广播消息给所有 WebSocket 客户端"""
        dead: Set[WebSocket] = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning("silent except caught in {exc} (line 716)", exc_info=True)
                dead.add(ws)
        self._ws_clients -= dead

    async def broadcast_event(self, event_type: str, data: dict, workspace_id: Optional[str] = None):
        """主动广播自定义事件"""
        await self._event_bus.emit(event_type, data, workspace_id)

    def run(self, log_level: str = "info"):
        """启动 Web 服务"""
        logger.info(f"启动 ODAP Mock Data Generator Web 服务: http://{self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level=log_level)

    async def start_async(self):
        """异步启动（用于与现有 asyncio 事件循环集成）"""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()