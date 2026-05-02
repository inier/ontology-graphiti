"""API路由 - 扩展Skill管理功能"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from typing import Dict, Any, List, Optional
import os
import yaml
import shutil
from pathlib import Path
from ..services.skill_service import SkillService
from ..services.hotplug_service import HotplugService
from ..models.skill import SkillType, SkillStatus

router = APIRouter(prefix="/api/skill", tags=["skill"])

skill_service = SkillService()
hotplug_service = HotplugService()

OPENHARNESS_SKILLS_DIR = Path(__file__).parent.parent.parent.parent.parent / "openharness" / ".claude" / "skills"


@router.post("/upload")
async def upload_skill_file(
    skill_file: UploadFile = File(...),
    category: str = "custom"
) -> Dict[str, Any]:
    """上传Skill文件（SKILL.md）"""
    try:
        if not skill_file.filename.endswith(('.md', '.yaml', '.yml')):
            raise HTTPException(status_code=400, detail="只支持 .md, .yaml, .yml 文件")

        content = await skill_file.read()
        skill_dir = OPENHARNESS_SKILLS_DIR / category

        if not skill_dir.exists():
            skill_dir.mkdir(parents=True, exist_ok=True)

        file_path = skill_dir / skill_file.filename
        with open(file_path, 'wb') as f:
            f.write(content)

        skill_info = {
            "filename": skill_file.filename,
            "category": category,
            "path": str(file_path),
            "size": len(content)
        }

        if skill_file.filename.endswith('.md'):
            try:
                skill_md = content.decode('utf-8')
                parsed = parse_skill_markdown(skill_md)
                skill_info["parsed"] = parsed
            except Exception:
                pass

        return {"status": "success", "data": skill_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/json")
async def upload_skill_json(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "custom",
    input_schema: Optional[str] = None,
    output_schema: Optional[str] = None,
    implementation: Optional[str] = None
) -> Dict[str, Any]:
    """通过JSON上传Skill配置"""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan")
async def scan_skills_directory() -> Dict[str, Any]:
    """扫描skills目录，返回所有可用的Skills"""
    try:
        skills = []
        if not OPENHARNESS_SKILLS_DIR.exists():
            return {"skills": [], "total": 0}

        for category_dir in OPENHARNESS_SKILLS_DIR.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                category = category_dir.name

                for skill_dir in category_dir.iterdir():
                    if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                        skill_info = {
                            "name": skill_dir.name,
                            "category": category,
                            "path": str(skill_dir),
                            "files": []
                        }

                        skill_md_path = skill_dir / "SKILL.md"
                        if skill_md_path.exists():
                            try:
                                content = skill_md_path.read_text(encoding='utf-8')
                                parsed = parse_skill_markdown(content)
                                skill_info["parsed"] = parsed
                                skill_info["description"] = parsed.get("description", "")
                                skill_info["files"].append("SKILL.md")
                            except Exception:
                                pass

                        for ref_dir in ["references", "tests"]:
                            ref_path = skill_dir / ref_dir
                            if ref_path.exists() and ref_path.is_dir():
                                skill_info["files"].append(f"{ref_dir}/")

                        skills.append(skill_info)

        return {"skills": skills, "total": len(skills)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_skill_categories() -> Dict[str, Any]:
    """获取所有Skill分类"""
    try:
        categories = []
        if OPENHARNESS_SKILLS_DIR.exists():
            for category_dir in OPENHARNESS_SKILLS_DIR.iterdir():
                if category_dir.is_dir() and not category_dir.name.startswith('.'):
                    skill_count = sum(1 for d in category_dir.iterdir() if d.is_dir() and not d.name.startswith('.'))
                    categories.append({
                        "name": category_dir.name,
                        "skill_count": skill_count,
                        "path": str(category_dir)
                    })

        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_skills() -> Dict[str, Any]:
    """获取所有Skills（包含已注册和目录扫描的）"""
    try:
        registered = skill_service.list_skills()

        scanned = await scan_skills_directory()

        return {
            "registered": registered.get("skills", []),
            "scanned": scanned.get("skills", []),
            "total_registered": registered.get("total", 0),
            "total_scanned": scanned.get("total", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle/{skill_name}")
async def toggle_skill(
    skill_name: str,
    enabled: bool = True
) -> Dict[str, Any]:
    """启用/禁用Skill"""
    try:
        result = skill_service.get_skill(skill_name)
        if result.get("status") == "error":
            return {"status": "success", "message": f"Skill '{skill_name}' not registered, treating as enabled", "enabled": True}

        if enabled:
            return skill_service.activate_skill(skill_name)
        else:
            return skill_service.deactivate_skill(skill_name)
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
                pass

    return result


@router.get("/skills")
async def list_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    skill_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """列出已注册的Skills"""
    try:
        filters = {}
        if skill_type:
            filters["type"] = skill_type
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category

        return skill_service.list_skills(filters, page, page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills")
async def register_skill(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None
):
    """注册Skill"""
    try:
        return skill_service.register_skill(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取Skill"""
    try:
        result = skill_service.get_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/versions")
async def add_version(
    skill_id: str,
    version: str,
    implementation: str,
    schema: Optional[Dict[str, Any]] = None,
    changelog: str = ""
):
    """添加版本"""
    try:
        return skill_service.add_version(skill_id, version, implementation, schema, changelog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/activate")
async def activate_skill(skill_id: str):
    """激活Skill"""
    try:
        return skill_service.activate_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/deactivate")
async def deactivate_skill(skill_id: str):
    """停用Skill"""
    try:
        return skill_service.deactivate_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/load")
async def load_skill(skill_id: str, version: Optional[str] = None):
    """加载Skill"""
    try:
        return hotplug_service.load_skill(skill_id, version)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/unload")
async def unload_skill(skill_id: str):
    """卸载Skill"""
    try:
        return hotplug_service.unload_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/loaded")
async def get_loaded_skills():
    """获取已加载的Skills"""
    try:
        return {"skills": hotplug_service.get_loaded_skills()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
