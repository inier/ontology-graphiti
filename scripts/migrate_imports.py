"""
ADR-068 Phase 3 Migration Helper — 批量更新违规 import 到新路径。

扫描 lint 检测到的违规 import，自动替换为推荐的新导入路径。
只修改导入语句，不改逻辑代码。

使用方式:
  python scripts/migrate_imports.py --dry-run    # 预览将要修改的内容
  python scripts/migrate_imports.py              # 执行迁移
  python scripts/migrate_imports.py --file <path>  # 迁移单个文件

安全: 每次修改前自动备份原文件为 .bak
"""

import ast
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 旧 import → (新 import, 说明)
IMPORT_REPLACEMENTS: Dict[str, Tuple[str, str]] = {
    # === L2 Construction 桥接 (已有) ===
    "from odap.biz.core.ontology.design.services.ingest_service import IngestService": (
        "from odap.biz.core.ontology.construction.pipeline.services import IngestService",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.ingest_service import get_ingest_service": (
        "from odap.biz.core.ontology.construction.pipeline.services import get_ingest_service",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.build_service import OntologyBuilderService": (
        "from odap.biz.core.ontology.construction.pipeline.services import OntologyBuilderService",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.build_service import get_builder_service": (
        "from odap.biz.core.ontology.construction.pipeline.services import get_builder_service",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.pipeline_service import PipelineService": (
        "from odap.biz.core.ontology.construction.pipeline.services import PipelineService",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.pipeline_service import get_pipeline_service": (
        "from odap.biz.core.ontology.construction.pipeline.services import get_pipeline_service",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.qa_ontology_builder import QAOntologyBuilder": (
        "from odap.biz.core.ontology.construction.pipeline.services import QAOntologyBuilder",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.qa_ontology_builder import get_qa_builder": (
        "from odap.biz.core.ontology.construction.pipeline.services import get_qa_builder",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.qa_ontology_builder import QABuildStatus": (
        "from odap.biz.core.ontology.construction.pipeline.services import QABuildStatus",
        "L2 construction bridge"
    ),
    "from odap.biz.core.ontology.design.services.qa_ontology_builder import QABuildProgress": (
        "from odap.biz.core.ontology.construction.pipeline.services import QABuildProgress",
        "L2 construction bridge"
    ),

    # === L1 Design 直导 (走顶层 __init__.py) ===
    "from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager": (
        "from odap.biz.core.ontology import OntologyVersionManager",
        "L1 design __init__.py (deprecated path, future: design.version)"
    ),
    "from odap.biz.core.ontology.design.services.version_service import OntologyVersion": (
        "from odap.biz.core.ontology.design.models.version import OntologyVersion",
        "L1 design models"
    ),
    "from odap.biz.core.ontology.design.services.version_service import OntologyDiff": (
        "from odap.biz.core.ontology.design.models.version import OntologyDiff",
        "L1 design models"
    ),
    "from odap.biz.core.ontology.design.services.version_service import EntitySnapshot": (
        "from odap.biz.core.ontology.design.models.version import EntitySnapshot",
        "L1 design models"
    ),
    "from odap.biz.core.ontology.design.services.validation_service import ValidationService": (
        "from odap.biz.core.ontology.reasoning.consistency import ValidationService",
        "+AI reasoning consistency"
    ),

    # === L1 Design 引擎 (走直接导入) ===
    "from odap.biz.core.ontology.design.services.edit_lock_service import get_edit_lock_service": (
        "from odap.biz.core.ontology.design.services.edit_lock_service import get_edit_lock_service",
        "L1 design engine (ok, internal cross-ref)"
    ),

    # === L2 Ingestion 桥接 ===
    "from odap.biz.core.ontology.design.ingestion.impl.pdf_processor import PDFProcessor": (
        "from odap.biz.core.ontology.construction.ingestion.services import PDFProcessor",
        "L2 construction ingestion"
    ),
    "from odap.biz.core.ontology.design.ingestion.impl.word_processor import WordProcessor": (
        "from odap.biz.core.ontology.construction.ingestion.services import WordProcessor",
        "L2 construction ingestion"
    ),
    "from odap.biz.core.ontology.design.ingestion.impl.ocr_processor import OCRProcessor": (
        "from odap.biz.core.ontology.construction.ingestion.services import OCRProcessor",
        "L2 construction ingestion"
    ),

    # === OMS 存储 → 走顶层 ===
    "from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage": (
        "from odap.biz.core.ontology import OMSStorage",
        "L3 OMS via __init__.py"
    ),

    # === 搜索服务 → 保持原路径 (Phase 3+ 迁移) ===
    # SearchService 尚无新桥接，标记为已知待迁移
    "from odap.biz.core.ontology.design.services.search_service import SearchService": (
        "from odap.biz.core.ontology.design.services.search_service import SearchService",
        "L1 design search (TODO: create search bridge in Phase 3+)"
    ),
    "from odap.biz.core.ontology.design.services.transform_service import get_transform_service": (
        "from odap.biz.core.ontology.design.services.transform_service import get_transform_service",
        "L1 design transform (TODO: create transform bridge in Phase 3+)"
    ),
}


def replace_imports(filepath: Path, dry_run: bool = False) -> List[str]:
    """替换单个文件中的旧 import"""
    with open(filepath, encoding="utf-8") as f:
        original = f.read()

    modified = original
    changes = []

    for old_import, (new_import, reason) in IMPORT_REPLACEMENTS.items():
        if old_import in modified and old_import != new_import:
            modified = modified.replace(old_import, new_import)
            changes.append(f"  {old_import.split('import')[-1].strip()}")
            changes.append(f"    → {new_import.split('import')[-1].strip()} ({reason})")

    if not changes:
        return []

    if dry_run:
        return changes

    # 备份
    backup = str(filepath) + ".bak"
    shutil.copy2(filepath, backup)

    # 写入
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(modified)

    return changes


def migrate_all(dry_run: bool = False) -> int:
    """扫描并迁移所有违规文件"""
    scan_dirs = [
        PROJECT_ROOT / "apps" / "api" / "odap" / "biz",
        PROJECT_ROOT / "apps" / "api" / "odap" / "infra",
        PROJECT_ROOT / "apps" / "api" / "odap" / "web",
        PROJECT_ROOT / "apps" / "api" / "odap" / "tools",
    ]

    total_changes = 0
    files_modified = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            changes = replace_imports(py_file, dry_run=dry_run)
            if changes:
                files_modified += 1
                total_changes += len(changes) // 2
                if dry_run:
                    print(f"\n[{py_file.relative_to(PROJECT_ROOT)}]")
                    for c in changes:
                        print(c)

    if dry_run:
        print(f"\n  Dry run: {total_changes} imports would be updated in {files_modified} files")
        print("  Run without --dry-run to apply changes")
    else:
        print(f"  Migrated {total_changes} imports in {files_modified} files")
        print("  Backups saved as .bak files")

    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    migrate_all(dry_run=dry)
