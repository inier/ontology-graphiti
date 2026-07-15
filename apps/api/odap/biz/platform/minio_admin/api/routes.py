"""MinIO 对象存储管理 API

提供 MinIO 桶列表、对象浏览、元数据查看、文件删除和存储统计功能。
管理员可查看全量数据；普通用户受限于当前工作空间。

路由前缀: /api/minio-admin
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/minio-admin", tags=["minio-admin"])

# 已知的 bucket 及其用途描述
BUCKET_META = {
    "odap-documents": {"display_name": "知识库文档", "description": "知识库上传的原始文档（docx/pdf/xlsx 等）"},
    "odap-ingestion": {"display_name": "本体摄入", "description": "本体设计摄入流程的中间文件"},
    "odap-audit-archive": {"display_name": "审计归档", "description": "过期审计日志的压缩归档"},
}


def _get_minio():
    """获取 MinIO 客户端单例"""
    from odap.infra.storage.minio_client import get_minio_client
    return get_minio_client()


def _require_minio():
    """获取 MinIO 客户端，不可用时抛出 503"""
    minio = _get_minio()
    if not minio.available:
        raise HTTPException(status_code=503, detail="MinIO 服务不可用，请检查 MinIO 容器状态")
    return minio


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _extract_workspace_id(user: dict) -> str:
    return user.get("ws_id", "default") if isinstance(user, dict) else "default"


def _is_admin(user: dict) -> bool:
    """JWT payload 兼容多种角色字段格式"""
    if not isinstance(user, dict):
        return False
    if user.get("role") == "admin":
        return True
    roles = user.get("roles", [])
    if isinstance(roles, list) and "admin" in roles:
        return True
    if user.get("role_type") == "system_admin":
        return True
    return False


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, workspace_id: str = "default"):
    """审计便捷函数

    优先 storage_audit，回退 log_audit；审计异常永远不打断业务。
    """
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=details.get("bucket", "") if details else "",
            details={**(details or {}), "user": user_id, "workspace_id": workspace_id},
            service="platform_minio",
        )
        return
    except Exception:
        pass
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="minio_admin",
            user=user_id,
            service="platform_minio",
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


# ── 连接状态 ──────────────────────────────────────────

@router.get("/status")
async def get_status(user=Depends(get_current_user)):
    """MinIO 连接状态"""
    minio = _get_minio()
    ping_result = minio.ping()
    return {
        "available": ping_result.get("status") == "success",
        "endpoint": minio._endpoint,
        "sdk_installed": minio._client is not None,
        "detail": ping_result.get("message", "ok") if ping_result.get("status") != "success" else "ok",
    }


# ── 桶列表 ────────────────────────────────────────────

@router.get("/buckets")
async def list_buckets(user=Depends(get_current_user)):
    """列出所有 bucket 及基本统计"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"

    try:
        # 使用底层 SDK 列出所有 bucket
        raw_buckets = minio._client.list_buckets()
        result = []
        for bucket in raw_buckets:
            name = bucket.name
            # 获取对象数量和总大小
            try:
                objects = minio._client.list_objects(name, recursive=True)
                obj_list = list(objects)
                total_size = sum(obj.size or 0 for obj in obj_list)
                obj_count = len(obj_list)
            except Exception:
                total_size = 0
                obj_count = 0

            meta = BUCKET_META.get(name, {})
            result.append({
                "name": name,
                "display_name": meta.get("display_name", name),
                "description": meta.get("description", ""),
                "object_count": obj_count,
                "total_size": total_size,
                "total_size_display": _format_size(total_size),
                "creation_date": bucket.creation_date.isoformat() if bucket.creation_date else None,
            })

        _audit("minio_list_buckets", _uid, "success", details={"count": len(result)})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_list_buckets_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── 对象浏览 ──────────────────────────────────────────

@router.get("/objects")
async def list_objects(
    bucket: str = Query(..., description="Bucket 名称"),
    prefix: Optional[str] = Query(None, description="路径前缀过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    user=Depends(get_current_user)):
    """列出 bucket 中的对象，支持前缀过滤和分页"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    _ws_id = _extract_workspace_id(user)

    try:
        result = minio.list_objects(bucket, prefix=prefix)
        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "列出对象失败"))

        objects = result.get("objects", [])

        # 非管理员按工作空间过滤（odap-documents 桶中按 kb_id 关联的工作空间过滤）
        # 注：完整的工作空间隔离需要查询 kb → workspace 映射，此处简化为管理员全量可见
        if not _is_admin(user):
            # 普通用户只能看到自己工作空间相关的文档
            # 当前简化策略：仅允许管理员访问 MinIO 管理接口
            raise HTTPException(status_code=403, detail="仅管理员可访问对象存储管理")

        # 分离目录和文件
        dirs = [o for o in objects if o.get("is_dir")]
        files = [o for o in objects if not o.get("is_dir")]

        # 按名称排序
        dirs.sort(key=lambda x: x.get("name", ""))
        files.sort(key=lambda x: x.get("name", ""))

        # 合并后分页
        all_items = dirs + files
        total = len(all_items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = all_items[start:end]

        # 格式化返回
        formatted = []
        for obj in page_items:
            name = obj.get("name", "")
            display_name = name.split("/")[-1] if not obj.get("is_dir") else name.rstrip("/").split("/")[-1]
            formatted.append({
                "name": name,
                "display_name": display_name or name,
                "size": obj.get("size", 0),
                "size_display": _format_size(obj.get("size", 0)),
                "content_type": obj.get("content_type", ""),
                "last_modified": obj.get("last_modified"),
                "is_dir": obj.get("is_dir", False),
            })

        return {
            "bucket": bucket,
            "prefix": prefix or "",
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_list_objects_failed", _uid, "failure", str(e),
               details={"bucket": bucket, "prefix": prefix})
        raise HTTPException(status_code=500, detail=str(e))


# ── 对象元数据 ────────────────────────────────────────

@router.get("/objects/metadata")
async def get_object_metadata(
    bucket: str = Query(..., description="Bucket 名称"),
    key: str = Query(..., description="对象 key"),
    user=Depends(get_current_user)):
    """获取对象的详细元数据"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"

    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可访问对象存储管理")

    try:
        # 使用底层 SDK 获取对象元数据（stat_object）
        stat = minio._client.stat_object(bucket, key)
        return {
            "bucket": bucket,
            "key": key,
            "size": stat.size,
            "size_display": _format_size(stat.size or 0),
            "content_type": stat.content_type,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "etag": stat.etag,
            "metadata": dict(stat.metadata) if stat.metadata else {},
        }
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_get_metadata_failed", _uid, "failure", str(e),
               details={"bucket": bucket, "key": key})
        raise HTTPException(status_code=500, detail=str(e))


# ── 预览 URL ──────────────────────────────────────────

@router.get("/objects/presigned-url")
async def get_presigned_url(
    bucket: str = Query(..., description="Bucket 名称"),
    key: str = Query(..., description="对象 key"),
    expires_hours: int = Query(1, ge=1, le=24, description="URL 有效期（小时）"),
    user=Depends(get_current_user)):
    """获取对象的 presigned URL 用于下载/预览"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"

    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可访问对象存储管理")

    try:
        result = minio.get_presigned_url(bucket, key, expires=timedelta(hours=expires_hours))
        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "生成预览链接失败"))
        return {"url": result["url"], "expires_seconds": result["expires_seconds"]}
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_presigned_url_failed", _uid, "failure", str(e),
               details={"bucket": bucket, "key": key})
        raise HTTPException(status_code=500, detail=str(e))


# ── 删除对象 ──────────────────────────────────────────

@router.delete("/objects")
async def delete_object(
    bucket: str = Query(..., description="Bucket 名称"),
    key: str = Query(..., description="对象 key"),
    user=Depends(get_current_user)):
    """删除单个对象"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"

    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可删除对象")

    try:
        result = minio.delete_object(bucket, key)
        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "删除失败"))

        _audit("minio_delete_object", _uid, "success",
               details={"bucket": bucket, "key": key})
        return {"message": f"对象 {key} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_delete_object_failed", _uid, "failure", str(e),
               details={"bucket": bucket, "key": key})
        raise HTTPException(status_code=500, detail=str(e))


# ── 存储统计 ──────────────────────────────────────────

@router.get("/stats")
async def get_storage_stats(user=Depends(get_current_user)):
    """汇总存储统计信息"""
    minio = _require_minio()
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"

    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可访问存储统计")

    try:
        raw_buckets = minio._client.list_buckets()
        bucket_stats = []
        total_objects = 0
        total_size = 0

        for bucket in raw_buckets:
            try:
                objects = list(minio._client.list_objects(bucket.name, recursive=True))
                obj_count = len(objects)
                bucket_size = sum(obj.size or 0 for obj in objects)

                # 按内容类型统计
                content_types = {}
                for obj in objects:
                    ct = obj.content_type or "unknown"
                    if ct not in content_types:
                        content_types[ct] = {"count": 0, "size": 0}
                    content_types[ct]["count"] += 1
                    content_types[ct]["size"] += obj.size or 0

                bucket_stats.append({
                    "name": bucket.name,
                    "object_count": obj_count,
                    "total_size": bucket_size,
                    "total_size_display": _format_size(bucket_size),
                    "content_types": content_types,
                })
                total_objects += obj_count
                total_size += bucket_size
            except Exception as e:
                bucket_stats.append({
                    "name": bucket.name,
                    "object_count": 0,
                    "total_size": 0,
                    "total_size_display": "0 B",
                    "content_types": {},
                    "error": str(e),
                })

        return {
            "total_buckets": len(raw_buckets),
            "total_objects": total_objects,
            "total_size": total_size,
            "total_size_display": _format_size(total_size),
            "buckets": bucket_stats,
        }
    except HTTPException:
        raise
    except Exception as e:
        _audit("minio_stats_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))
