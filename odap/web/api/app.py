"""
SimulatorWebService — 模拟器 Web 服务
实现 ADR-031 L1: Web Visualization Service

提供:
- REST API: 场景管理 / 数据写入 / 版本管理
- WebSocket: 实时事件流推送
- 静态前端: simulator_ui/ 目录

依赖: fastapi, uvicorn, python-multipart (可选 aiofiles)
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("simulator_web")

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ontology", "versions", "scenarios")

# ── FastAPI 依赖检查 ────────────────────────────────
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
    from fastapi.responses import JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI 未安装，Web 服务不可用。请运行: pip install fastapi uvicorn python-multipart")

from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyDocumentSchema, OntologyValidationError,
    DocType, SourceType
)
from odap.biz.ontology.hot_write import OntologyHotWritePipeline
from odap.biz.ontology.version_manager import OntologyVersionManager
from odap.biz.ontology.ingestion import NewsIngester, ManualInputHandler, RandomEventGenerator, OntologyDocumentIO
from odap.infra.events import HookRegistry, HookPhase


class ScenarioStore:
    """
    场景持久化存储
    管理场景元数据和关联的 OntologyDocument
    数据保存在 ontology/versions/scenarios/ 目录
    """

    def __init__(self, storage_dir: str = SCENARIOS_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._scenarios_file = os.path.join(self.storage_dir, "scenarios.json")
        self._scenarios: Dict[str, Dict[str, Any]] = {}
        self._documents: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    def _load(self):
        """从磁盘加载所有场景"""
        if os.path.exists(self._scenarios_file):
            try:
                with open(self._scenarios_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._scenarios = data.get("scenarios", {})
                    self._documents = data.get("documents", {})
            except Exception as e:
                logger.warning(f"加载场景失败: {e}, 将创建新存储")
                self._scenarios = {}
                self._documents = {}

    def _save(self):
        """保存所有场景到磁盘"""
        try:
            with open(self._scenarios_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "scenarios": self._scenarios,
                    "documents": self._documents,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存场景失败: {e}")

    def create(self, name: str, description: str = "") -> str:
        scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        self._scenarios[scenario_id] = {
            "scenario_id": scenario_id,
            "name": name,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "doc_count": 0,
            "event_count": 0,
            "entity_count": 0,
        }
        self._documents[scenario_id] = []
        self._save()
        return scenario_id

    def add_document(self, scenario_id: str, doc: OntologyDocument):
        if scenario_id not in self._documents:
            self._documents[scenario_id] = []
        doc_dict = {
            "doc_id": doc.doc_id,
            "meta": doc.meta.model_dump() if hasattr(doc.meta, 'model_dump') else vars(doc.meta),
            "entities": [e.to_dict() if hasattr(e, 'to_dict') else e for e in doc.entities],
            "events": [ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in doc.events],
            "ontology_version": doc.ontology_version.__dict__ if doc.ontology_version else None,
        }
        self._documents[scenario_id].append(doc_dict)
        if scenario_id in self._scenarios:
            self._scenarios[scenario_id]["doc_count"] = len(self._documents[scenario_id])
            self._scenarios[scenario_id]["event_count"] = sum(len(d.get("events", [])) for d in self._documents[scenario_id])
            self._scenarios[scenario_id]["entity_count"] = sum(len(d.get("entities", [])) for d in self._documents[scenario_id])
        self._save()

    def get_timeline(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取时间线（所有事件按时间戳排序）"""
        docs = self._documents.get(scenario_id, [])
        events = []
        for doc in docs:
            doc_events = doc.get("events", [])
            for ev in doc_events:
                events.append({
                    "timestamp": ev.get("timestamp", ""),
                    "event_type": ev.get("event_type", "unknown"),
                    "description": ev.get("description", ""),
                    "doc_id": doc.get("doc_id", ""),
                    "doc_title": doc.get("meta", {}).get("title", ""),
                    "version_id": doc.get("ontology_version", {}).get("version_id", "") if doc.get("ontology_version") else "",
                })
        return sorted(events, key=lambda e: e.get("timestamp", ""))

    def get_entities(self, scenario_id: str, snapshot_time: str = None) -> List[Dict[str, Any]]:
        """获取实体列表（支持时间点快照）"""
        docs = self._documents.get(scenario_id, [])
        entity_map: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            for entity in doc.get("entities", []):
                entity_id = entity.get("entity_id", "")
                if entity_id:
                    entity_map[entity_id] = {
                        **entity,
                        "version_id": doc.get("ontology_version", {}).get("version_id", "") if doc.get("ontology_version") else "",
                    }
        return list(entity_map.values())

    def get_relations(self, scenario_id: str) -> Dict[str, Any]:
        """获取关系图数据（节点 + 边，D3.js 格式）"""
        entities = self.get_entities(scenario_id)
        docs = self._documents.get(scenario_id, [])

        nodes = [{"id": e.get("entity_id", ""), "name": e.get("name", ""), "type": e.get("entity_type", ""),
                   "side": e.get("basic_properties", {}).get("side", "neutral") if isinstance(e.get("basic_properties"), dict) else "neutral",
                   "combat_power": e.get("statistical_properties", {}).get("combat_power", 0.5) if isinstance(e.get("statistical_properties"), dict) else 0.5}
                 for e in entities if e.get("entity_id")]

        links = []
        entity_ids = {e["id"] for e in nodes}
        for doc in docs:
            for rel in doc.get("relations", []):
                src = rel.get("source_entity", "")
                tgt = rel.get("target_entity", "")
                if src in entity_ids and tgt in entity_ids:
                    links.append({
                        "source": src,
                        "target": tgt,
                        "type": rel.get("relation_type", "unknown"),
                        "id": rel.get("relation_id", ""),
                    })

        return {"nodes": nodes, "links": links}

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        return self._scenarios.get(scenario_id)

    def get_documents(self, scenario_id: str) -> List[Dict[str, Any]]:
        return self._documents.get(scenario_id, [])

    def sync_to_graphiti(self, scenario_id: str) -> Dict[str, Any]:
        """
        将场景数据同步到 graphiti
        调用 graph_manager 的加载接口
        """
        try:
            from odap.infra.graph import GraphManager
            manager = GraphManager()
            manager.clear_graph()
            manager._load_data_to_neo4j()
            return {"status": "success", "synced_scenario": scenario_id}
        except Exception as e:
            logger.error(f"同步到 graphiti 失败: {e}")
            return {"status": "error", "error": str(e)}


class SimulatorWebService:
    """
    模拟器 Web 服务

    提供 REST API + WebSocket 实时事件流 + 静态前端
    """

    def __init__(
        self,
        pipeline: Optional[OntologyHotWritePipeline] = None,
        version_manager: Optional[OntologyVersionManager] = None,
        llm_client=None,
        tavily_api_key: str = None,
        static_dir: str = None,
        host: str = "0.0.0.0",
        port: int = 8765,
    ):
        if not FASTAPI_AVAILABLE:
            raise RuntimeError("FastAPI 未安装，请运行: pip install fastapi uvicorn python-multipart")

        self.pipeline = pipeline or OntologyHotWritePipeline.get_instance()
        self.versions = version_manager or OntologyVersionManager.get_instance()
        self.host = host
        self.port = port

        # 数据层
        self.scenario_store = ScenarioStore()
        self.news_ingester = NewsIngester(llm_client=llm_client, tavily_api_key=tavily_api_key)
        self.manual_handler = ManualInputHandler(llm_client=llm_client)
        self.random_gen = RandomEventGenerator(llm_client=llm_client)
        self.doc_io = OntologyDocumentIO(version_manager=self.versions)

        # WebSocket 客户端集合
        self._ws_clients: Set[WebSocket] = set()

        # 异步任务追踪（联网检索）
        self._tasks: Dict[str, Dict[str, Any]] = {}

        # 订阅本体更新 Hook
        self.pipeline.register_ontology_hook(self._on_ontology_updated)

        # 构建 FastAPI 应用
        self.app = self._build_app(static_dir)

    def _build_app(self, static_dir: str = None) -> 'FastAPI':
        app = FastAPI(
            title="ODAP Simulator v2.0",
            description="战场事件模拟与本体构建平台",
            version="2.0.0",
        )

        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 静态文件
        _static_dir = static_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "simulator_ui"
        )
        if os.path.exists(_static_dir):
            app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="static")

        # ── 路由注册 ─────────────────────────────────────

        @app.get("/")
        async def root():
            return {"service": "ODAP Simulator", "version": "2.0.0", "status": "running"}

        @app.get("/health")
        async def health():
            return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

        # ── 场景管理 ──────────────────────────────────────

        @app.post("/api/scenarios")
        async def create_scenario(body: dict):
            name = body.get("name", "未命名场景")
            desc = body.get("description", "")
            scenario_id = self.scenario_store.create(name, desc)
            return {"scenario_id": scenario_id, "name": name}

        @app.get("/api/scenarios")
        async def list_scenarios():
            return {"scenarios": self.scenario_store.list_scenarios()}

        @app.get("/api/scenarios/{scenario_id}")
        async def get_scenario(scenario_id: str):
            scenario = self.scenario_store.get_scenario(scenario_id)
            if not scenario:
                raise HTTPException(status_code=404, detail="场景不存在")
            return scenario

        @app.post("/api/scenarios/{scenario_id}/sync")
        async def sync_scenario(scenario_id: str):
            """将场景数据同步到 graphiti"""
            result = self.scenario_store.sync_to_graphiti(scenario_id)
            if result.get("status") == "error":
                raise HTTPException(status_code=500, detail=result.get("error"))
            return result

        @app.get("/api/scenarios/{scenario_id}/timeline")
        async def get_timeline(scenario_id: str):
            events = self.scenario_store.get_timeline(scenario_id)
            return {"scenario_id": scenario_id, "events": events, "count": len(events)}

        @app.get("/api/scenarios/{scenario_id}/entities")
        async def get_entities(scenario_id: str, snapshot_time: str = None):
            entities = self.scenario_store.get_entities(scenario_id, snapshot_time)
            return {"scenario_id": scenario_id, "entities": entities, "count": len(entities)}

        @app.get("/api/scenarios/{scenario_id}/relations")
        async def get_relations(scenario_id: str):
            graph = self.scenario_store.get_relations(scenario_id)
            return {"scenario_id": scenario_id, **graph}

        @app.get("/api/scenarios/{scenario_id}/export")
        async def export_scenario(scenario_id: str):
            docs = self.scenario_store.get_documents(scenario_id)
            content = await self.doc_io.export_scenario(scenario_id, docs)
            return Response(
                content=content,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="scenario-{scenario_id}.odoc.json"'},
            )

        # ── 数据写入 ──────────────────────────────────────

        @app.post("/api/ingest/manual")
        async def ingest_manual(body: dict):
            """手动输入 OntologyDocument，触发热写入"""
            scenario_id = body.get("scenario_id")
            try:
                # 尝试解析 OntologyDocument
                if "doc_id" in body or "doc_type" in body:
                    doc = OntologyDocument.from_dict(body)
                else:
                    doc = await self.manual_handler.from_form(body, scenario_id=scenario_id)

                version = await self.pipeline.ingest(doc)

                if scenario_id:
                    self.scenario_store.add_document(scenario_id, doc)
                    asyncio.create_task(asyncio.to_thread(self.scenario_store.sync_to_graphiti, scenario_id))

                return {
                    "success": True,
                    "doc_id": doc.doc_id,
                    "version_id": version.version_id,
                }
            except (OntologyValidationError, ValueError) as e:
                raise HTTPException(status_code=422, detail=str(e))

        @app.post("/api/ingest/text")
        async def ingest_text(body: dict):
            """自然语言输入 → OntologyDocument → 热写入"""
            text = body.get("text", "")
            scenario_id = body.get("scenario_id")
            if not text:
                raise HTTPException(status_code=400, detail="text 不能为空")

            doc = await self.manual_handler.from_natural_language(text, scenario_id=scenario_id)
            version = await self.pipeline.ingest(doc)

            if scenario_id:
                self.scenario_store.add_document(scenario_id, doc)

            return {"success": True, "doc_id": doc.doc_id, "version_id": version.version_id}

        @app.post("/api/ingest/news")
        async def ingest_news(body: dict):
            """联网检索归纳（异步任务）"""
            query = body.get("query", "")
            context = body.get("context", "")
            scenario_id = body.get("scenario_id")
            if not query:
                raise HTTPException(status_code=400, detail="query 不能为空")

            task_id = f"task-{uuid.uuid4().hex[:8]}"
            self._tasks[task_id] = {"status": "running", "started_at": datetime.now().isoformat()}

            async def _run():
                try:
                    docs = await self.news_ingester.ingest(query, context)
                    versions = []
                    for doc in docs:
                        if scenario_id:
                            doc.scenario_id = scenario_id
                        ver = await self.pipeline.ingest(doc)
                        if scenario_id:
                            self.scenario_store.add_document(scenario_id, doc)
                        versions.append(ver.version_id)
                    self._tasks[task_id] = {
                        "status": "completed",
                        "doc_count": len(docs),
                        "versions": versions,
                    }
                except Exception as e:
                    self._tasks[task_id] = {"status": "failed", "error": str(e)}

            asyncio.create_task(_run())
            return {"task_id": task_id, "status": "running"}

        @app.get("/api/ingest/tasks/{task_id}")
        async def get_task(task_id: str):
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")
            return task

        @app.post("/api/ingest/random")
        async def ingest_random(body: dict):
            """按涉事方随机生成事件"""
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
                "versions": versions,
                "docs": [d.to_dict() for d in docs],
            }

        @app.post("/api/ingest/import")
        async def import_scenario(file: UploadFile = File(...), scenario_id: str = None):
            """导入 .odoc.json 文件，触发本体写入"""
            content = await file.read()
            try:
                docs = await self.doc_io.import_file(content, scenario_id=scenario_id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

            versions = []
            for doc in docs:
                ver = await self.pipeline.ingest(doc)
                if scenario_id:
                    self.scenario_store.add_document(scenario_id, doc)
                versions.append(ver.version_id)

            return {"success": True, "doc_count": len(docs), "versions": versions}

        # ── 版本管理 ──────────────────────────────────────

        @app.get("/api/versions")
        async def list_versions(limit: int = 50, offset: int = 0):
            versions = await self.versions.list(limit=limit, offset=offset)
            return {
                "versions": [v.to_dict() for v in versions],
                "total": self.versions.get_version_count(),
            }

        @app.get("/api/versions/{version_id}")
        async def get_version(version_id: str):
            ver = await self.versions.get(version_id)
            if not ver:
                raise HTTPException(status_code=404, detail="版本不存在")
            return ver.to_dict()

        @app.post("/api/versions/{version_id}/rollback")
        async def rollback(version_id: str):
            new_ver = await self.pipeline.rollback(version_id)
            return {"success": True, "new_version_id": new_ver.version_id}

        @app.get("/api/versions/{version_a}/diff/{version_b}")
        async def diff_versions(version_a: str, version_b: str):
            from dataclasses import asdict
            diff = await self.versions.diff(version_a, version_b)
            return asdict(diff)

        @app.get("/api/entities/{entity_id}/history")
        async def entity_history(entity_id: str):
            history = await self.versions.get_entity_history(entity_id)
            from dataclasses import asdict
            return {"entity_id": entity_id, "history": [asdict(h) for h in history]}

        # ── 统计 ──────────────────────────────────────────

        @app.get("/api/stats")
        async def stats():
            return {
                "pipeline": self.pipeline.get_stats(),
                "scenarios": len(self.scenario_store.list_scenarios()),
                "ws_clients": len(self._ws_clients),
            }

        # ── WebSocket 实时事件流 ───────────────────────────

        @app.websocket("/ws/events")
        async def ws_events(websocket: WebSocket):
            await websocket.accept()
            self._ws_clients.add(websocket)
            logger.info(f"WebSocket 客户端连接，当前连接数: {len(self._ws_clients)}")
            try:
                # 发送连接确认
                await websocket.send_text(json.dumps({
                    "type": "connected",
                    "message": "ODAP Simulator 实时事件流",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                while True:
                    # 等待 ping / 保持连接
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    if data == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
            except (WebSocketDisconnect, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.error(f"WebSocket 错误: {e}")
            finally:
                self._ws_clients.discard(websocket)
                logger.info(f"WebSocket 客户端断开，当前连接数: {len(self._ws_clients)}")

        return app

    async def _on_ontology_updated(self, context, payload: dict):
        """Hook 回调：广播本体更新到所有 WebSocket 客户端"""
        message = json.dumps({
            "type": "ontology_update",
            "data": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str)
        await self._broadcast(message)

    async def _broadcast(self, message: str):
        """广播消息给所有 WebSocket 客户端"""
        dead: Set[WebSocket] = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    async def broadcast_event(self, event_type: str, data: dict):
        """主动广播自定义事件"""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str)
        await self._broadcast(message)

    def run(self, log_level: str = "info"):
        """启动 Web 服务"""
        logger.info(f"启动 ODAP Simulator Web 服务: http://{self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level=log_level)

    async def start_async(self):
        """异步启动（用于与现有 asyncio 事件循环集成）"""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
