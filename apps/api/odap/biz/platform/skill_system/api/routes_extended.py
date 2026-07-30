"""API路由 - 扩展Skill管理功能

统一运行时 SKILL_CATALOG 与文件系统扫描的数据源：
- 目录Skills：合并 SKILL_CATALOG 运行时技能 + 文件系统扫描
- 分类：从 SKILL_CATALOG 提取 category + 文件系统子目录
- 已加载：反映 DomainHarness 实际可用工具

安全说明：
- 所有写操作端点强制 admin 认证（Depends(verify_admin)）。
- category / name / filename 仅允许 [A-Za-z0-9_-] 白名单字符，并校验
  resolve() 后路径仍位于 OPENHARNESS_SKILLS_DIR 之下，防止路径穿越。
"""

import re
import os
import shutil
import tempfile
import zipfile
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends, Body
from ..services import get_skill_service, get_hotplug_service
from ..models.skill import SkillType, SkillStatus
from odap.infra.security.jwt_auth import get_current_user, verify_admin

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skill", tags=["skill-extended"])

skill_service = get_skill_service()
hotplug_service = get_hotplug_service()

OPENHARNESS_SKILLS_DIR = Path(__file__).parent.parent.parent.parent.parent / "skills"

# 安全：白名单字符集，防止路径穿越与非法字符
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
# 安全：允许的文件扩展名
_ALLOWED_FILE_EXTS = (".md", ".yaml", ".yml", ".zip")


def _validate_safe_name(value: str, field_name: str) -> str:
    """校验 category/name/filename 等标识符仅含安全字符。

    防止路径穿越（如 ../、绝对路径、空字节）与 shell 元字符注入。
    """
    if not value or not _SAFE_NAME_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: only alphanumeric, underscore and hyphen are allowed",
        )
    return value


def _validate_filename(filename: str) -> str:
    """校验上传文件名：白名单字符 + 允许的扩展名。"""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    # 拆分 stem 与 suffix 分别校验，避免 .md.md 之类绕过
    stem = filename
    suffix = ""
    for ext in _ALLOWED_FILE_EXTS:
        if filename.lower().endswith(ext):
            stem = filename[: -len(ext)]
            suffix = ext
            break
    if not suffix:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(_ALLOWED_FILE_EXTS)} files are allowed",
        )
    if not _SAFE_NAME_RE.match(stem):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename stem: only alphanumeric, underscore and hyphen are allowed",
        )
    return stem + suffix


def _ensure_within_skills_dir(target: Path) -> Path:
    """断言 target 解析后仍位于 OPENHARNESS_SKILLS_DIR 之下，否则拒绝。"""
    resolved = target.resolve()
    base = OPENHARNESS_SKILLS_DIR.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Resolved path escapes the skills directory",
        )
    return resolved


def _get_catalog_skills() -> List[Dict[str, Any]]:
    """从 SKILL_CATALOG 获取运行时技能列表"""
    try:
        from odap.tools import SKILL_CATALOG

        skills = []
        for name, entry in SKILL_CATALOG.items():
            skills.append({
                "name": name,
                "category": entry.get("category", "general"),
                "description": entry.get("description", ""),
                "source": "catalog",
                "files": [],
                "enabled": True,
            })
        return skills
    except Exception:
        logger.warning("silent except caught in {exc} (line 42)", exc_info=True)
        return []


def _get_harness_tools() -> List[str]:
    """从 DomainHarness 获取实际可用的工具名称列表"""
    try:
        from odap.infra.openharness.tool_adapter import get_domain_harness

        harness = get_domain_harness()
        if harness is None:
            logger.warning("_get_harness_tools: get_domain_harness() returned None")
            # Fallback: 从 SKILL_CATALOG 获取工具名
            try:
                from odap.tools import SKILL_CATALOG
                return list(SKILL_CATALOG.keys())
            except Exception as e2:
                logger.warning(f"_get_harness_tools: SKILL_CATALOG fallback failed: {e2}")
                return []

        if hasattr(harness, '_tool_list'):
            tool_names = [t.name for t in harness._tool_list if hasattr(t, 'name')]
            if tool_names:
                return tool_names
            logger.warning("_get_harness_tools: harness._tool_list is empty")

        # Fallback: 从 SKILL_CATALOG 获取
        try:
            from odap.tools import SKILL_CATALOG
            return list(SKILL_CATALOG.keys())
        except Exception as e2:
            logger.warning(f"_get_harness_tools: SKILL_CATALOG fallback failed: {e2}")
            return []
    except Exception as e:
        logger.warning(f"_get_harness_tools failed: {e}", exc_info=True)
        return []


def _scan_filesystem_skills() -> List[Dict[str, Any]]:
    """扫描文件系统中的 Skills（支持扁平结构、嵌套结构和分类文件结构）"""
    skills = []
    if not OPENHARNESS_SKILLS_DIR.exists():
        return skills

    seen_names = set()

    # 1. 扫描扁平结构：{skill_name}.md 直接放在 skills 目录下
    for md_file in OPENHARNESS_SKILLS_DIR.glob("*.md"):
        if md_file.is_file() and not md_file.name.startswith('.'):
            skill_name = md_file.stem
            skill_info = {
                "name": skill_name,
                "category": "general",
                "path": str(md_file),
                "files": [md_file.name],
                "source": "filesystem",
            }

            try:
                content = md_file.read_text(encoding='utf-8')
                parsed = parse_skill_markdown(content)
                if parsed.get("name"):
                    skill_info["name"] = parsed["name"]
                skill_info["parsed"] = parsed
                skill_info["description"] = parsed.get("description", "")
                seen_names.add(skill_info["name"])
            except Exception:
                logger.warning(f"Failed to parse skill file: {md_file}", exc_info=True)

            skills.append(skill_info)

    # 2. 扫描嵌套结构和分类文件结构
    for category_dir in OPENHARNESS_SKILLS_DIR.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue

        category = category_dir.name

        # 2a. 扫描分类下的直接 .md 文件（如 {category}/{skill_name}.md）
        for md_file in category_dir.glob("*.md"):
            if md_file.is_file() and not md_file.name.startswith('.'):
                skill_name = md_file.stem
                if skill_name in seen_names:
                    continue
                skill_info = {
                    "name": skill_name,
                    "category": category,
                    "path": str(md_file),
                    "files": [md_file.name],
                    "source": "filesystem",
                }

                try:
                    content = md_file.read_text(encoding='utf-8')
                    parsed = parse_skill_markdown(content)
                    if parsed.get("name"):
                        skill_info["name"] = parsed["name"]
                    skill_info["parsed"] = parsed
                    skill_info["description"] = parsed.get("description", "")
                    seen_names.add(skill_info["name"])
                except Exception:
                    logger.warning(f"Failed to parse skill file: {md_file}", exc_info=True)

                skills.append(skill_info)

        # 2b. 扫描嵌套结构：{category}/{skill_name}/SKILL.md
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                continue

            skill_name = skill_dir.name
            if skill_name in seen_names:
                continue

            skill_info = {
                "name": skill_name,
                "category": category,
                "path": str(skill_dir),
                "files": [],
                "source": "filesystem",
            }

            try:
                content = skill_md_path.read_text(encoding='utf-8')
                parsed = parse_skill_markdown(content)
                if parsed.get("name"):
                    skill_info["name"] = parsed["name"]
                skill_info["parsed"] = parsed
                skill_info["description"] = parsed.get("description", "")
                skill_info["files"].append("SKILL.md")
                seen_names.add(skill_info["name"])
            except Exception:
                logger.warning(f"Failed to parse skill: {skill_md_path}", exc_info=True)

            for ref_dir in ["references", "tests"]:
                ref_path = skill_dir / ref_dir
                if ref_path.exists() and ref_path.is_dir():
                    skill_info["files"].append(f"{ref_dir}/")

            skills.append(skill_info)

    return skills


def _get_catalog_categories() -> List[Dict[str, Any]]:
    """从 SKILL_CATALOG 提取分类信息"""
    try:
        from odap.tools import SKILL_CATALOG

        cat_map: Dict[str, int] = {}
        for entry in SKILL_CATALOG.values():
            cat = entry.get("category", "general")
            cat_map[cat] = cat_map.get(cat, 0) + 1

        return [{"name": cat, "skill_count": count, "source": "catalog"} for cat, count in cat_map.items()]
    except Exception:
        logger.warning("silent except caught in {exc} (line 111)", exc_info=True)
        return []


def _get_filesystem_categories() -> List[Dict[str, Any]]:
    """从文件系统提取分类信息（支持扁平结构、嵌套结构和分类文件结构）"""
    categories = {}
    if not OPENHARNESS_SKILLS_DIR.exists():
        return []

    # 统计扁平结构的 skill（归到 "general" 分类）
    flat_count = sum(1 for f in OPENHARNESS_SKILLS_DIR.glob("*.md") 
                    if f.is_file() and not f.name.startswith('.'))
    if flat_count > 0:
        categories["general"] = {
            "name": "general",
            "skill_count": flat_count,
            "path": str(OPENHARNESS_SKILLS_DIR),
            "source": "filesystem",
        }

    # 统计嵌套结构和分类文件结构的 skill
    for category_dir in OPENHARNESS_SKILLS_DIR.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue

        cat_name = category_dir.name
        skill_count = 0

        # 分类下的直接 .md 文件
        skill_count += sum(1 for f in category_dir.glob("*.md") 
                          if f.is_file() and not f.name.startswith('.'))

        # 分类下的嵌套 skill 目录
        for skill_dir in category_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                if (skill_dir / "SKILL.md").exists():
                    skill_count += 1

        categories[cat_name] = {
            "name": cat_name,
            "skill_count": skill_count,
            "path": str(category_dir),
            "source": "filesystem",
        }

    return list(categories.values())


@router.post("/upload")
async def upload_skill_file(
    skill_file: UploadFile = File(...),
    category: str = "custom",
    user=Depends(verify_admin),
) -> Dict[str, Any]:
    """上传Skill文件（SKILL.md）

    安全：仅 admin 可调用；category 与 filename 经白名单校验，
    并断言最终路径位于 OPENHARNESS_SKILLS_DIR 之下。
    """
    try:
        safe_category = _validate_safe_name(category, "category")
        safe_filename = _validate_filename(skill_file.filename or "")

        skill_dir = OPENHARNESS_SKILLS_DIR / safe_category
        file_path = skill_dir / safe_filename
        # 二次防护：resolve() 后断言仍在 skills 目录下
        _ensure_within_skills_dir(file_path)

        if not skill_dir.exists():
            skill_dir.mkdir(parents=True, exist_ok=True)

        content = await skill_file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        skill_info = {
            "filename": safe_filename,
            "category": safe_category,
            "path": str(file_path),
            "size": len(content)
        }

        if safe_filename.endswith('.md'):
            try:
                skill_md = content.decode('utf-8')
                parsed = parse_skill_markdown(skill_md)
                skill_info["parsed"] = parsed
                
                # 自动注册到SkillManager
                if parsed.get("name"):
                    try:
                        skill_service.register_skill(
                            name=parsed["name"],
                            skill_type=SkillType.ACTION,
                            description=parsed.get("description", ""),
                            category=safe_category
                        )
                        logger.info(f"Auto-registered skill '{parsed.get('name')}' from upload")
                    except Exception as reg_err:
                        logger.warning(f"Failed to auto-register skill: {reg_err}")
            except Exception:
                logger.warning("silent except caught in {exc} (line 166)", exc_info=True)
                pass

        return {"status": "success", "data": skill_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-zip")
async def upload_skill_zip(
    skill_file: UploadFile = File(...),
    category: str = "custom",
    user=Depends(verify_admin),
) -> Dict[str, Any]:
    """上传Skill压缩包（.zip）

    自动解压、校验SKILL.md、解析元数据并注册到系统中。
    """
    tmp_dir = None
    try:
        safe_category = _validate_safe_name(category, "category")
        
        filename = skill_file.filename or ""
        if not filename.lower().endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only .zip files are allowed for zip upload")

        # 1. 保存到临时目录
        tmp_dir = tempfile.mkdtemp(prefix="skill_upload_")
        zip_path = Path(tmp_dir) / filename
        with open(zip_path, 'wb') as f:
            content = await skill_file.read()
            f.write(content)

        # 2. 解压
        extract_dir = Path(tmp_dir) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 安全检查：防止Zip Slip
                for zip_name in zip_ref.namelist():
                    target_path = extract_dir / zip_name
                    if not str(target_path.resolve()).startswith(str(extract_dir.resolve())):
                        raise HTTPException(status_code=400, detail="Invalid zip structure: path traversal detected")
                zip_ref.extractall(extract_dir)
        except HTTPException:
            raise
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid zip file")

        # 3. 查找SKILL.md
        skill_md_path = None
        for root, dirs, files in os.walk(extract_dir):
            # 忽略隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            if 'SKILL.md' in files:
                skill_md_path = Path(root) / 'SKILL.md'
                break

        if not skill_md_path or not skill_md_path.exists():
            raise HTTPException(status_code=400, detail="No valid SKILL.md found in uploaded zip")

        # 4. 解析SKILL.md
        skill_content = skill_md_path.read_text(encoding='utf-8')
        parsed = parse_skill_markdown(skill_content)

        if not parsed.get("name"):
            raise HTTPException(status_code=400, detail="SKILL.md missing required 'name' field (must be in '# SkillName' format)")

        safe_name = _validate_safe_name(parsed["name"], "skill_name")

        # 5. 移动到目标目录
        target_skill_dir = OPENHARNESS_SKILLS_DIR / safe_category / safe_name
        _ensure_within_skills_dir(target_skill_dir)

        if target_skill_dir.exists():
            shutil.rmtree(target_skill_dir)

        # 将解压后的整个文件夹移动过去
        source_dir = skill_md_path.parent
        shutil.copytree(source_dir, target_skill_dir, symlinks=False)

        # 6. 注册到SkillManager
        registered_skill = skill_service.register_skill(
            name=safe_name,
            skill_type=SkillType.ACTION,
            description=parsed.get("description", ""),
            category=safe_category
        )

        # 7. 返回结果
        skill_info = {
            "name": safe_name,
            "category": safe_category,
            "path": str(target_skill_dir),
            "parsed": parsed,
            "registered": True,
            "skill_id": registered_skill.get("skill_id") if isinstance(registered_skill, dict) else getattr(registered_skill, 'id', None)
        }

        return {"status": "success", "data": skill_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload skill zip")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时目录
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass


@router.post("/upload/json")
async def upload_skill_json(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "custom",
    input_schema: Optional[str] = None,
    output_schema: Optional[str] = None,
    implementation: Optional[str] = None,
    user=Depends(verify_admin),
) -> Dict[str, Any]:
    """通过JSON上传Skill配置（仅 admin）"""
    try:
        # 校验 name/category 防止注入到注册表与文件系统
        _validate_safe_name(name, "name")
        _validate_safe_name(category, "category")

        skill = skill_service.register_skill(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category
        )

        if input_schema and output_schema:
            import json
            skill_service.add_version(
                skill_id=skill["skill_id"],
                version="1.0.0",
                implementation=implementation or "",
                schema={
                    "input": json.loads(input_schema) if input_schema else {},
                    "output": json.loads(output_schema) if output_schema else {}
                },
                changelog="Initial version"
            )

        return skill
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan")
async def scan_skills_directory() -> Dict[str, Any]:
    """扫描skills目录，合并运行时 SKILL_CATALOG 和文件系统扫描结果。
    状态字段从数据库已注册技能中同步，确保 enabled 状态真实反映。
    """
    try:
        catalog_skills = _get_catalog_skills()
        fs_skills = _scan_filesystem_skills()

        catalog_names = {s["name"] for s in catalog_skills}
        merged = list(catalog_skills)

        for fs_skill in fs_skills:
            if fs_skill["name"] not in catalog_names:
                merged.append(fs_skill)

        # 用数据库中已注册的状态修正 enabled 字段
        registered = skill_service.list_skills(page_size=500)
        name_status_map: Dict[str, str] = {}
        for r in registered.get("skills", []):
            name_status_map[r["name"]] = r.get("status", "active")

        for s in merged:
            name = s.get("name", "")
            if name in name_status_map:
                status = name_status_map[name]
                s["enabled"] = status == "active"
                s["status"] = status
            else:
                s["enabled"] = True
                s["status"] = "active"

        return {"skills": merged, "total": len(merged)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_skill_categories() -> Dict[str, Any]:
    """获取所有Skill分类（合并 SKILL_CATALOG 和文件系统）"""
    try:
        catalog_cats = _get_catalog_categories()
        fs_cats = _get_filesystem_categories()

        merged: Dict[str, Dict[str, Any]] = {}

        for cat in catalog_cats:
            merged[cat["name"]] = {
                "name": cat["name"],
                "skill_count": cat["skill_count"],
                "source": cat["source"],
            }

        for cat in fs_cats:
            name = cat["name"]
            if name in merged:
                merged[name]["skill_count"] += cat["skill_count"]
                merged[name]["source"] = "catalog+filesystem"
                merged[name]["path"] = cat.get("path", "")
            else:
                merged[name] = {
                    "name": name,
                    "skill_count": cat["skill_count"],
                    "path": cat.get("path", ""),
                    "source": cat["source"],
                }

        return {"categories": list(merged.values())}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_skills() -> Dict[str, Any]:
    """获取所有Skills（包含已注册、SKILL_CATALOG 和文件系统扫描的）"""
    try:
        registered = skill_service.list_skills(page_size=100)
        catalog_info = skill_service.get_catalog_info()
        scanned = await scan_skills_directory()
        harness_tools = _get_harness_tools()

        # 构建 name → status 映射，用已注册数据修正 scanned 的 enabled 状态
        name_status_map: Dict[str, str] = {}
        for r in registered.get("skills", []):
            name_status_map[r["name"]] = r.get("status", "active")

        scanned_skills = []
        for s in scanned.get("skills", []):
            s_copy = dict(s)
            name = s_copy.get("name", "")
            if name in name_status_map:
                status = name_status_map[name]
                s_copy["enabled"] = status in ("active",)
                s_copy["status"] = status
            else:
                s_copy["enabled"] = True
                s_copy["status"] = "active"
            scanned_skills.append(s_copy)

        return {
            "registered": registered.get("skills", []),
            "scanned": scanned_skills,
            "catalog": catalog_info,
            "harness_tools": harness_tools,
            "total_registered": registered.get("total", 0),
            "total_scanned": len(scanned_skills),
            "total_catalog": catalog_info.get("catalog_count", 0),
            "total_harness": len(harness_tools),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-and-register")
async def scan_and_register_skills(
    user=Depends(verify_admin),
) -> Dict[str, Any]:
    """扫描文件系统并自动注册Skill到系统（仅 admin）"""
    try:
        fs_skills = _scan_filesystem_skills()
        
        # 获取已注册的 skill 名称列表
        registered_result = skill_service.list_skills(page_size=100)
        registered_names = {s["name"] for s in registered_result.get("skills", [])}
        
        registered_count = 0
        skipped_count = 0
        errors = []
        
        for skill_info in fs_skills:
            skill_name = skill_info["name"]
            
            # 跳过已注册的 skill
            if skill_name in registered_names:
                skipped_count += 1
                continue
            
            try:
                skill_service.register_skill(
                    name=skill_name,
                    skill_type=SkillType.ACTION,
                    description=skill_info.get("description", ""),
                    category=skill_info.get("category", "general")
                )
                registered_count += 1
            except Exception as e:
                errors.append({
                    "name": skill_name,
                    "error": str(e)
                })
                logger.warning(f"Failed to register skill '{skill_name}': {e}")
        
        return {
            "status": "success",
            "data": {
                "total_scanned": len(fs_skills),
                "registered": registered_count,
                "skipped_already_registered": skipped_count,
                "errors": errors,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to scan and register skills")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle/{skill_name}")
async def toggle_skill(
    skill_name: str,
    enabled: bool = True,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """启用/禁用Skill（需登录）"""
    try:
        _validate_safe_name(skill_name, "skill_name")
        result = skill_service.get_skill_by_name(skill_name)
        if result.get("status") == "error":
            return {"status": "success", "message": f"Skill '{skill_name}' not registered, treating as enabled", "enabled": True}

        skill_id = result.get("skill_id")
        if not skill_id:
            return {"status": "error", "message": f"Skill '{skill_name}' has no skill_id"}

        if enabled:
            return skill_service.activate_skill(skill_id)
        else:
            return skill_service.deactivate_skill(skill_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/loaded")
async def get_loaded_skills():
    """获取已加载的Skills（合并 HotplugManager + DomainHarness 实际可用工具）"""
    try:
        hotplug_loaded = hotplug_service.get_loaded_skills()
        harness_tools = _get_harness_tools()

        loaded_set = set(hotplug_loaded) | set(harness_tools)

        return {"skills": sorted(loaded_set), "hotplug_count": len(hotplug_loaded), "harness_count": len(harness_tools)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/reload")
async def reload_skill(skill_id: str, user=Depends(verify_admin)):
    """热重载Skill（仅 admin）"""
    try:
        _validate_safe_name(skill_id, "skill_id")
        success = hotplug_service.reload_skill(skill_id)
        if success:
            return {"status": "success", "message": f"Skill {skill_id} reloaded"}
        return {"status": "error", "message": f"Failed to reload skill {skill_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/save")
async def save_skill_content(
    payload: Dict[str, Any] = Body(...),
    user=Depends(verify_admin),
) -> Dict[str, Any]:
    """保存Skill内容到文件系统（仅 admin）

    安全：name/category 经白名单校验，并断言最终路径位于
    OPENHARNESS_SKILLS_DIR 之下，防止路径穿越。
    """
    try:
        name = payload.get("name", "")
        category = payload.get("category", "custom")
        content = payload.get("content", "")

        safe_name = _validate_safe_name(name, "name")
        safe_category = _validate_safe_name(category, "category")

        skill_dir = OPENHARNESS_SKILLS_DIR / safe_category / safe_name
        # 二次防护：resolve() 后断言仍在 skills 目录下
        _ensure_within_skills_dir(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md_path = skill_dir / "SKILL.md"
        _ensure_within_skills_dir(skill_md_path)
        skill_md_path.write_text(content, encoding='utf-8')

        return {"status": "success", "message": f"Skill '{safe_name}' saved to {skill_dir}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def parse_skill_markdown(content: str) -> Dict[str, Any]:
    """解析SKILL.md内容"""
    result = {
        "name": "",
        "description": "",
        "input_schema": {},
        "output_schema": {},
        "sections": {}
    }

    lines = content.split('\n')
    current_section = None
    section_content = []

    for line in lines:
        line = line.rstrip()

        if line.startswith('# '):
            result["name"] = line[2:].strip()
        elif line.startswith('## '):
            if current_section and section_content:
                result["sections"][current_section] = '\n'.join(section_content).strip()

            current_section = line[3:].strip().lower().replace(' ', '_')
            section_content = []
        elif line.startswith('##'):
            pass
        else:
            if current_section:
                section_content.append(line)

    if current_section and section_content:
        result["sections"][current_section] = '\n'.join(section_content).strip()

    if 'description' in result["sections"]:
        result["description"] = result["sections"]['description']

    for key in ["input_schema", "output_schema"]:
        if key in result["sections"]:
            try:
                schema_content = result["sections"][key]
                if '```yaml' in schema_content:
                    yaml_content = schema_content.split('```yaml')[1].split('```')[0].strip()
                elif '```json' in schema_content:
                    yaml_content = schema_content.split('```json')[1].split('```')[0].strip()
                else:
                    yaml_content = schema_content.strip()

                result[key] = yaml.safe_load(yaml_content) or {}
            except Exception:
                logger.warning("silent except caught in {exc} (line 424)", exc_info=True)
                pass

    return result
