import os
import sys
import json
import logging
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("simulator_web")

SCENARIOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
    "storage", 
    "scenarios"
)

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
from odap.infra.graph.graph_service import GraphManager

class ScenarioStore:
    """
    场景持久化存储
    管理场景元数据和关联的 OntologyDocument
    数据保存在 ontology/versions/scenarios/ 目录
    """

    def __init__(self, storage_dir: str = SCENARIOS_DIR, graph_manager: GraphManager = None):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._scenarios_file = os.path.join(self.storage_dir, "scenarios.json")
        self._scenarios: Dict[str, Dict[str, Any]] = {}
        self._documents: Dict[str, List[Dict[str, Any]]] = {}
        self._graph_manager = graph_manager
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
            if "events" in doc:
                events.extend(doc["events"])
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events

    def get_entities(self, scenario_id: str, snapshot_time: str = None) -> List[Dict[str, Any]]:
        """获取实体快照（支持时间点查询）"""
        docs = self._documents.get(scenario_id, [])
        entity_map: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            if "entities" in doc:
                for entity in doc["entities"]:
                    entity_id = entity.get("entity_id")
                    if entity_id:
                        entity_map[entity_id] = entity
        return list(entity_map.values())

    def get_relations(self, scenario_id: str) -> Dict[str, Any]:
        """获取关系图谱"""
        entities = self.get_entities(scenario_id)
        docs = self._documents.get(scenario_id, [])
        nodes = []
        links = []
        node_ids = set()

        for entity in entities:
            entity_id = entity.get("entity_id")
            if entity_id and entity_id not in node_ids:
                nodes.append({
                    "id": entity_id,
                    "name": entity.get("name", entity_id),
                    "type": entity.get("entity_type", "Entity"),
                    "side": entity.get("basic_properties", {}).get("side"),
                })
                node_ids.add(entity_id)

        for doc in docs:
            if "events" in doc:
                for event in doc["events"]:
                    participants = event.get("participants", [])
                    if len(participants) >= 2:
                        for i in range(len(participants) - 1):
                            source = participants[i]
                            target = participants[i + 1]
                            if source in node_ids and target in node_ids:
                                links.append({
                                    "id": f"rel-{uuid.uuid4().hex[:8]}",
                                    "source": source,
                                    "target": target,
                                    "type": event.get("event_type", "association"),
                                    "event_id": event.get("event_id"),
                                })

        return {"nodes": nodes, "links": links}

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        return self._scenarios.get(scenario_id)

    def get_documents(self, scenario_id: str) -> List[Dict[str, Any]]:
        return self._documents.get(scenario_id, [])

    def sync_to_graphiti(self, scenario_id: str) -> Dict[str, Any]:
        """将场景同步到 Graphiti"""
        if scenario_id not in self._scenarios:
            return {"status": "error", "error": f"Scenario {scenario_id} not found"}
        
        documents = self._documents.get(scenario_id, [])
        
        if not self._graph_manager:
            return {"status": "warning", "message": "GraphManager not initialized, using fallback", "synced_scenario": scenario_id}
        
        try:
            synced_entities = 0
            synced_events = 0
            
            for doc in documents:
                # 同步实体
                if "entities" in doc:
                    for entity_dict in doc["entities"]:
                        entity_id = entity_dict.get("entity_id", "")
                        entity_type = entity_dict.get("entity_type", "Entity")
                        properties = entity_dict.get("basic_properties", {})
                        
                        if entity_id:
                            # 添加name属性到properties以便在Graphiti中显示
                            if "name" in entity_dict and "name" not in properties:
                                properties["name"] = entity_dict["name"]
                            
                            self._graph_manager.add_entity(
                                entity_id=entity_id,
                                entity_type=entity_type,
                                properties=properties
                            )
                            synced_entities += 1
                
                # 同步事件和关系
                if "events" in doc:
                    for event_dict in doc["events"]:
                        participants = event_dict.get("participants", [])
                        event_type = event_dict.get("event_type", "ASSOCIATION")
                        
                        # 为事件参与者创建关系
                        if len(participants) >= 2:
                            for i in range(len(participants) - 1):
                                source = participants[i]
                                target = participants[i + 1]
                                
                                rel_properties = {
                                    "event_id": event_dict.get("event_id"),
                                    "timestamp": event_dict.get("timestamp"),
                                    "event_type": event_type,
                                    "description": event_dict.get("description"),
                                    "scenario_id": scenario_id
                                }
                                
                                self._graph_manager.add_relationship(
                                    source_id=source,
                                    target_id=target,
                                    relationship=event_type.upper().replace(" ", "_"),
                                    properties=rel_properties
                                )
                                synced_events += 1
            
            # 更新场景统计
            if scenario_id in self._scenarios:
                self._scenarios[scenario_id]["last_synced"] = datetime.now(timezone.utc).isoformat()
                self._scenarios[scenario_id]["synced_entities"] = synced_entities
                self._scenarios[scenario_id]["synced_events"] = synced_events
                self._save()
            
            return {
                "status": "success",
                "synced_scenario": scenario_id,
                "synced_entities": synced_entities,
                "synced_events": synced_events,
                "graph_mode": self._graph_manager._mode
            }
            
        except Exception as e:
            logger.error(f"Sync to Graphiti failed: {e}")
            return {"status": "error", "error": str(e), "synced_scenario": scenario_id}

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

        # 异步任务追踪（联网检索）
        self._tasks: Dict[str, Dict[str, Any]] = {}
        
        # 初始化 GraphManager
        self._graph_manager = GraphManager()

        # 数据层 - 传入 graph_manager
        self.scenario_store = ScenarioStore(graph_manager=self._graph_manager)
        self.news_ingester = NewsIngester(llm_client=llm_client, tavily_api_key=tavily_api_key)
        self.manual_handler = ManualInputHandler(llm_client=llm_client)
        self.random_gen = RandomEventGenerator(llm_client=llm_client)
        self.doc_io = OntologyDocumentIO(version_manager=self.versions)

        # 订阅本体更新 Hook
        self.pipeline.register_ontology_hook(self._on_ontology_updated)

        # 构建 FastAPI 应用
        self.app = self._build_app()

    def _build_app(self, static_dir: str = None) -> 'FastAPI':
        app = FastAPI(
            title="ODAP Mock Data Generator v2.0",
            description="模拟数据生成与本体热写入服务",
            version="2.0.0"
        )

        # CORS 配置
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 静态文件服务
        if static_dir:
            app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # ── 基础接口 ──────────────────────────────────────

        @app.get("/")
        async def root():
            return {"service": "ODAP Mock Data Generator", "version": "2.0.0", "status": "running"}

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
            result = self.scenario_store.sync_to_graphiti(scenario_id)
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

        # ── 数据摄入 ─────────────────────────────────────

        @app.post("/api/ingest/manual")
        async def ingest_manual(body: dict):
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
            except Exception as e:
                return {
                    "task_id": f"err-{uuid.uuid4().hex[:8]}",
                    "success": False,
                    "error": str(e)
                }

        @app.post("/api/ingest/text")
        async def ingest_text(body: dict):
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
            except Exception as e:
                return {
                    "task_id": f"err-{uuid.uuid4().hex[:8]}",
                    "success": False,
                    "error": str(e)
                }

        @app.post("/api/ingest/news")
        async def ingest_news(body: dict):
            """新闻 URL 摄入（联网检索 + LLM 归纳）"""
            url = body.get("url", "")
            scenario_id = body.get("scenario_id")
            
            if not url:
                return {"success": False, "error": "URL 不能为空"}
            
            try:
                doc = await self.news_ingester.ingest_url(url, scenario_id=scenario_id)
                ver = await self.pipeline.ingest(doc)
                
                if scenario_id:
                    doc.scenario_id = scenario_id
                    self.scenario_store.add_document(scenario_id, doc)
                    asyncio.create_task(asyncio.to_thread(self.scenario_store.sync_to_graphiti, scenario_id))
                
                return {
                    "success": True,
                    "task_id": ver.version_id,
                    "version": ver.version_id
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }

        @app.post("/api/ingest/random")
        async def ingest_random(body: dict):
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
        async def import_scenario(file: UploadFile = File(...), scenario_id: str = None):
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
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }

        # ── 版本管理 ─────────────────────────────────────

        @app.get("/api/versions")
        async def list_versions():
            versions = await self.versions.list(limit=100)
            version_dicts = [v.to_dict() if hasattr(v, 'to_dict') else v for v in versions]
            return {"versions": version_dicts, "total": len(version_dicts)}

        @app.get("/api/versions/{version_id}")
        async def get_version(version_id: str):
            ver = await self.versions.get(version_id)
            if not ver:
                raise HTTPException(status_code=404, detail="版本不存在")
            return ver.to_dict() if hasattr(ver, 'to_dict') else ver

        @app.post("/api/versions/{version_id}/rollback")
        async def rollback(version_id: str):
            try:
                result = await self.versions.rollback(version_id)
                return result
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/versions/diff")
        async def diff_versions(version_a: str, version_b: str):
            try:
                diff = await self.versions.diff(version_a, version_b)
                return diff
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        # ── 实体历史 ─────────────────────────────────────

        @app.get("/api/entities/{entity_id}/history")
        async def get_entity_history(entity_id: str):
            try:
                history = await self.pipeline.get_entity_history(entity_id)
                return history
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        # ── 统计信息 ─────────────────────────────────────

        @app.get("/api/stats")
        async def stats():
            return {
                "pipeline": self.pipeline.get_stats(),
                "scenarios": len(self.scenario_store.list_scenarios()),
                "ws_clients": len(self._ws_clients),
            }

        # ── WebSocket 实时事件流 ───────────────────────────

        @app.websocket("/ws/events")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._ws_clients.add(websocket)
            
            try:
                while True:
                    await asyncio.sleep(1)
            except WebSocketDisconnect:
                self._ws_clients.remove(websocket)
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
        logger.info(f"启动 ODAP Mock Data Generator Web 服务: http://{self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level=log_level)

    async def start_async(self):
        """异步启动（用于与现有 asyncio 事件循环集成）"""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
