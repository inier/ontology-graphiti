"""前端API兼容层 - 数据摄入/模拟路由"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional
import os
import uuid

from odap.biz.integration.frontend_compat.api._deps import (
    local_audit_log,
    log_ingest,
    log_error,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-simulation"])


# ==================== 数据摄入路由 ====================

@router.get("/ingest/news/progress/{task_id}")
async def get_news_ingest_progress(task_id: str,
    user=Depends(get_current_user)):
    """
    获取新闻摄入进度

    返回各阶段状态:
    - intent_analyzing: 意图分析
    - searching: 联网搜索
    - ingesting: 数据摄入
    - building: 本体构建
    - completed/failed: 完成/失败
    """
    try:
        from odap.biz.core.ontology.design.services.qa_ontology_builder import get_qa_builder

        builder = get_qa_builder()
        progress = await builder.get_progress(task_id)

        if not progress:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")

        return progress
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/status/{task_id}")
async def get_ingest_status(task_id: str,
    user=Depends(get_current_user)):
    """获取摄入任务状态（兼容前端）"""
    try:
        from celery.result import AsyncResult

        task_result = AsyncResult(task_id)

        if task_result.ready():
            result = task_result.get()
            return {
                "task_id": task_id,
                "status": result.get('status', 'completed'),
                "result": result,
            }
        else:
            return {
                "task_id": task_id,
                "status": "pending",
                "result": None,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/file")
@local_audit_log(action="INGEST_FILE", resource="file")
async def ingest_file(request: Request, file: UploadFile = File(...), scenario_id: Optional[str] = Form(None),
    user=Depends(get_current_user)):
    """文件上传摄入（兼容前端）"""
    try:
        from odap.tasks import process_file_upload_task

        filename = file.filename
        file_extension = os.path.splitext(filename)[1].lower()

        content = await file.read()

        if file_extension not in ['.json', '.csv', '.txt']:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        process_file_upload_task.delay(
            task_id,
            filename,
            content,
            file_extension,
            scenario_id,
        )

        log_ingest('file', filename=filename, user="system")

        return {
            "success": True,
            "task_id": task_id,
            "filename": filename,
            "file_size": len(content),
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error(str(e), context="ingest_file")
        raise HTTPException(status_code=500, detail=str(e))
