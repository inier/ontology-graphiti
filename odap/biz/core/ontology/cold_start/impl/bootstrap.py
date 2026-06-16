"""
冷启动引导服务 (T321)

当新工作空间无数据时，从模板库加载示例本体。
关键能力：
- detect_empty_workspace(workspace_id) - 检查是否需要冷启动
- bootstrap(workspace_id, industry) - 引导加载指定行业模板
- bootstrap_if_needed(workspace_id, industry) - 一键引导
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from ..models import ColdStartReport, Industry
from ..models.template_loader import list_industries, load_template

logger = logging.getLogger(__name__)


class ColdStartBootstrap:
    """冷启动引导器"""

    def __init__(
        self,
        ontology_loader: Optional[Callable[[Dict[str, Any]], int]] = None,
        storage: Optional[Any] = None,
    ):
        """
        Args:
            ontology_loader: 可选回调，接收模板 dict 并返回实际写入的实体类型数。
                             None 表示不真实写入（dry-run / 测试场景）。
            storage: 可选存储实例，用于查询工作空间数据。
                     支持 SQLiteIngestStorage（有 list_scenarios / get_ingest_records）
                     或任何具有 list_ontologies 方法的对象。
        """
        self.ontology_loader = ontology_loader
        self.storage = storage

    def detect_empty_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        检查工作空间是否为空。

        判断逻辑（按优先级）：
        1. 若注入了 storage 且有 list_scenarios / get_ingest_records，查询实际数据
        2. 若注入了 storage 且有 list_ontologies，查询本体列表
        3. 通过 design contract 延迟查询 ontology 列表
        4. 以上均不可用时，默认视为非空（安全降级，避免误触发 bootstrap）
        """
        # 1. 通过注入的 storage 查询 ingest 数据
        if self.storage is not None:
            try:
                if hasattr(self.storage, "list_scenarios"):
                    scenarios = self.storage.list_scenarios()
                    if scenarios:
                        return {
                            "workspace_id": workspace_id,
                            "is_empty": False,
                            "reason": "storage has scenarios",
                        }
                if hasattr(self.storage, "get_ingest_records"):
                    records = self.storage.get_ingest_records(limit=1)
                    if records:
                        return {
                            "workspace_id": workspace_id,
                            "is_empty": False,
                            "reason": "storage has ingest records",
                        }
                if hasattr(self.storage, "list_ontologies"):
                    ontologies = self.storage.list_ontologies(workspace_id=workspace_id)
                    if ontologies:
                        return {
                            "workspace_id": workspace_id,
                            "is_empty": False,
                            "reason": "workspace has ontologies",
                        }
            except Exception as exc:
                logger.warning("detect_empty_workspace via storage failed: %s", exc)

        # 2. 通过 design contract 延迟查询 ontology 列表
        try:
            from odap.biz.core.ontology.design.contract import get_design_contract

            contract = get_design_contract()
            ontologies = contract.list_ontologies(
                workspace_id=workspace_id, limit=1, offset=0
            )
            if ontologies:
                return {
                    "workspace_id": workspace_id,
                    "is_empty": False,
                    "reason": "workspace has ontologies via contract",
                }
        except Exception as exc:
            logger.debug("detect_empty_workspace via contract failed: %s", exc)

        # 3. 无可用数据源时视为空工作空间
        return {
            "workspace_id": workspace_id,
            "is_empty": True,
            "reason": "no data found in workspace",
        }

    def bootstrap(self, workspace_id: str, industry: str | Industry) -> ColdStartReport:
        """
        从指定行业模板引导加载示例本体。
        """
        template = load_template(industry)
        if template is None:
            available = list_industries()
            raise ValueError(
                f"Industry template not found: {industry}. "
                f"Available: {available}"
            )

        entity_types = template.get("entity_types", [])
        relationships = template.get("relationships", [])
        sample_data = template.get("sample_data", [])

        # 真实加载（若有注入）
        loaded_count = len(entity_types)
        if self.ontology_loader is not None:
            try:
                loaded_count = self.ontology_loader(template)
            except Exception as exc:
                logger.exception("ontology_loader failed: %s", exc)
                loaded_count = 0

        return ColdStartReport(
            workspace_id=workspace_id,
            industry=Industry(industry) if isinstance(industry, str) and industry in {i.value for i in Industry} else industry,  # type: ignore[arg-type]
            template_name=template.get("name", "unknown"),
            template_version=str(template.get("version", "1.0.0")),
            entity_type_count=len(entity_types),
            relationship_count=len(relationships),
            sample_data_count=len(sample_data),
            entity_types=[et.get("name", "") for et in entity_types],
            notes=f"Loaded {loaded_count} entity types from template '{template.get('name')}'",
        )

    def bootstrap_if_needed(
        self,
        workspace_id: str,
        industry: str | Industry,
    ) -> Dict[str, Any]:
        """
        检测后引导：若工作空间为空则执行 bootstrap。
        返回 Dict[str, Any] 格式（供服务层直接使用）。
        """
        try:
            return self._do_bootstrap_if_needed(workspace_id, industry)
        except Exception as exc:
            logger.exception("bootstrap_if_needed failed: %s", exc)
            return {"status": "error", "message": f"bootstrap failed: {exc}", "workspace_id": workspace_id}

    def _do_bootstrap_if_needed(self, workspace_id: str, industry: str | Industry) -> Dict[str, Any]:
        status = self.detect_empty_workspace(workspace_id)
        if not status.get("is_empty", True):
            return {"status": "skipped", "reason": "workspace is not empty", "workspace_id": workspace_id}
        report = self.bootstrap(workspace_id, industry)
        return self._report_to_dict(report)

    @staticmethod
    def _report_to_dict(report) -> Dict[str, Any]:
        return {
            "status": "success",
            "workspace_id": report.workspace_id,
            "industry": report.industry.value,
            "template": report.template_name,
            "entity_types_loaded": report.entity_type_count,
            "sample_data_loaded": report.sample_data_count,
            "report_id": report.id,
            "loaded_at": report.loaded_at.isoformat(),
        }
