"""
OntologyHotWritePipeline — 本体热写入管道
实现 ADR-031/032 的无重启实时本体扩展

流程: 验证 → 版本化 → Graphiti写入 → Hook广播
热生效保证: Graphiti add_episode() 即时生效 + HookSystem 广播下游刷新
"""

import asyncio
import logging
from typing import Optional, Any

from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyDocumentSchema, OntologyValidationError
)
from odap.biz.ontology.version_manager import OntologyVersionManager, OntologyVersion
from odap.infra.events import HookRegistry, HookPhase, HookContext

logger = logging.getLogger("ontology_hot_write")


class OntologyHotWritePipeline:
    """
    本体热写入管道

    设计目标: 写入数据后立即对系统其他组件生效，无需重启服务。

    热生效保障:
    1. Graphiti.add_episode() 异步追加写入，立即更新 Neo4j 图
    2. HookSystem.emit() 异步广播，订阅方（Intelligence Agent、Web UI）自动感知
    3. OntologyVersionManager 提供版本化快照，支持回退
    """

    _instance: Optional['OntologyHotWritePipeline'] = None

    def __init__(
        self,
        graph_manager=None,
        version_manager: Optional[OntologyVersionManager] = None,
        hook_registry: Optional[HookRegistry] = None,
    ):
        self.graph = graph_manager
        self.versions = version_manager or OntologyVersionManager.get_instance()
        self.hooks = hook_registry or HookRegistry.get_instance()
        # 写入计数（用于统计）
        self._ingest_count = 0
        self._error_count = 0

    @classmethod
    def get_instance(cls) -> 'OntologyHotWritePipeline':
        if cls._instance is None:
            cls._instance = OntologyHotWritePipeline()
        return cls._instance

    @classmethod
    def initialize(cls, graph_manager, version_manager=None, hook_registry=None) -> 'OntologyHotWritePipeline':
        """初始化并注册 graph_manager"""
        cls._instance = OntologyHotWritePipeline(
            graph_manager=graph_manager,
            version_manager=version_manager,
            hook_registry=hook_registry,
        )
        return cls._instance

    async def ingest(self, doc: OntologyDocument) -> OntologyVersion:
        """
        完整写入流程:
        1. Schema 验证
        2. 版本化（不可变快照）
        3. 写入 Graphiti Episode（核心图谱实时扩展）
        4. 触发 Hook（异步广播，不阻塞当前请求）
        """
        # ── 1. Schema 验证 ─────────────────────────────
        validation = OntologyDocumentSchema.validate(doc)
        if not validation.is_valid:
            self._error_count += 1
            raise OntologyValidationError(validation.errors)
        if validation.warnings:
            for w in validation.warnings:
                logger.warning(f"[Schema Warning] {w}")

        # ── 2. 版本化 ───────────────────────────────────
        version = await self.versions.commit(doc)

        # ── 3. 写入 Graphiti ────────────────────────────
        if self.graph is not None:
            try:
                await self._write_to_graphiti(doc, version)
            except Exception as e:
                logger.error(f"Graphiti 写入失败（版本 {version.version_id} 已保存）: {e}")
                # 不回滚版本，Graphiti 写失败属于降级，版本记录保留

        # ── 4. 触发 Hook（异步，不阻塞响应）─────────────
        event_payload = {
            "version_id": version.version_id,
            "doc_id": doc.doc_id,
            "doc_type": doc.doc_type,
            "entity_count": len(doc.entities),
            "relation_count": len(doc.relations),
            "event_count": len(doc.events),
            "action_count": len(doc.actions),
            "title": doc.meta.title,
            "scenario_id": doc.scenario_id,
        }
        asyncio.create_task(self._emit_hook(event_payload))

        self._ingest_count += 1
        logger.info(
            f"热写入完成: {version.version_id} | "
            f"实体:{len(doc.entities)} 关系:{len(doc.relations)} 事件:{len(doc.events)}"
        )
        return version

    async def _write_to_graphiti(self, doc: OntologyDocument, version: OntologyVersion):
        """写入 Graphiti Episode"""
        episode_text = doc.to_episode_text()
        metadata = {
            "doc_id": doc.doc_id,
            "doc_type": doc.doc_type,
            "version_id": version.version_id,
            "source_type": doc.source.type,
            "scenario_id": doc.scenario_id,
        }
        # 调用 graph_manager 的 add_episode 方法
        if hasattr(self.graph, 'add_episode'):
            await self.graph.add_episode(
                content=episode_text,
                episode_type="ontology_document",
                metadata=metadata,
            )
        logger.debug(f"Graphiti Episode 写入: {doc.doc_id}")

    async def _emit_hook(self, payload: dict):
        """发射 Hook 事件"""
        try:
            context = HookContext(event_name="ontology.updated")
            context.set_data("payload", payload)

            hooks = self.hooks.get_hooks("ontology.updated", HookPhase.POST)
            for hook in hooks:
                try:
                    result = hook.handler(context, payload)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Hook {hook.name} 执行失败: {e}")
        except Exception as e:
            logger.error(f"Hook 广播失败: {e}")

    async def rollback(self, version_id: str) -> OntologyVersion:
        """
        回退到指定版本
        实现: 取出历史版本的 doc，作为新版本重新写入（append-only）
        """
        doc = await self.versions.get_doc(version_id)
        if doc is None:
            raise ValueError(f"版本 {version_id} 不存在或快照已丢失")

        # 修改提交信息，指示这是回退操作
        doc.ontology_version.parent_version = version_id
        doc.ontology_version.commit_message = f"回退到版本 {version_id}"

        logger.info(f"回退到版本: {version_id}")
        return await self.ingest(doc)

    def register_ontology_hook(self, handler):
        """
        注册 ontology.updated 事件订阅者

        Usage:
            async def my_handler(context, payload):
                print(payload["version_id"])
            pipeline.register_ontology_hook(my_handler)
        """
        self.hooks.register(
            event="ontology.updated",
            name=getattr(handler, "__name__", str(id(handler))),
            handler=handler,
            phase=HookPhase.POST,
            description="本体更新订阅",
        )

    def get_stats(self) -> dict:
        return {
            "ingest_count": self._ingest_count,
            "error_count": self._error_count,
            "version_count": self.versions.get_version_count(),
            "latest_version": self.versions.get_latest_version_id(),
        }
