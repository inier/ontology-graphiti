"""
API 版本控制服务
实现 API 版本控制机制，确保向后兼容
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("api_version")


class APIVersion(str, Enum):
    """API 版本枚举"""
    V1 = "v1"
    V2 = "v2"
    CURRENT = "v2"


class APIChangeType(str, Enum):
    """API 变更类型"""
    ADDED = "added"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass
class APIEndpoint:
    """API 端点定义"""
    path: str
    method: str
    version: APIVersion
    description: str
    parameters: List[Dict] = field(default_factory=list)
    response: Dict = field(default_factory=dict)
    deprecated: bool = False
    deprecated_since: Optional[str] = None
    replacement: Optional[str] = None


@dataclass
class APIChangeLog:
    """API 变更日志"""
    version: APIVersion
    date: str
    changes: List[Dict[str, Any]]
    breaking_changes: List[Dict[str, Any]]


class APIVersionController:
    """
    API 版本控制器

    功能:
    1. 管理 API 版本定义
    2. 处理版本间的兼容性
    3. 生成变更日志
    4. 提供版本迁移指南
    """

    def __init__(self):
        self._endpoints: Dict[str, List[APIEndpoint]] = {}
        self._version_history: List[APIChangeLog] = []
        self._init_default_versions()

    def _init_default_versions(self):
        """初始化默认版本信息"""
        # V1 API 端点（已废弃）
        self._register_endpoint(APIEndpoint(
            path="/api/ingest/news",
            method="POST",
            version=APIVersion.V1,
            description="新闻摄入（V1版本，已废弃）",
            deprecated=True,
            deprecated_since="v2.0.0",
            replacement="/api/v2/ingest/news"
        ))

        # V2 API 端点（当前版本）
        self._register_endpoint(APIEndpoint(
            path="/api/ingest/news",
            method="POST",
            version=APIVersion.V2,
            description="新闻摄入（V2版本）",
            parameters=[
                {"name": "query", "type": "string", "required": False, "description": "搜索关键词"},
                {"name": "url", "type": "string", "required": False, "description": "新闻URL"},
                {"name": "scenario_id", "type": "string", "required": False, "description": "场景ID"},
                {"name": "workspace_id", "type": "string", "required": False, "description": "工作空间ID"}
            ],
            response={
                "success": {"type": "boolean", "description": "是否成功"},
                "task_id": {"type": "string", "description": "任务ID"},
                "status": {"type": "string", "description": "任务状态"},
                "answer": {"type": "string", "description": "生成的回答"},
                "sources_count": {"type": "integer", "description": "来源数量"}
            }
        ))

        self._register_endpoint(APIEndpoint(
            path="/api/ingest/news/progress/{task_id}",
            method="GET",
            version=APIVersion.V2,
            description="获取新闻摄入进度",
            parameters=[
                {"name": "task_id", "type": "string", "required": True, "description": "任务ID"}
            ]
        ))

        # 初始化版本历史
        self._version_history.append(APIChangeLog(
            version=APIVersion.V2,
            date="2026-04-26",
            changes=[
                {"endpoint": "/api/ingest/news", "type": "modified", "description": "重构为统一的本体构建流程"},
                {"endpoint": "/api/ingest/news/progress/{task_id}", "type": "added", "description": "新增进度查询接口"}
            ],
            breaking_changes=[]
        ))

    def _register_endpoint(self, endpoint: APIEndpoint):
        """注册 API 端点"""
        key = f"{endpoint.method}:{endpoint.path}"
        if key not in self._endpoints:
            self._endpoints[key] = []
        self._endpoints[key].append(endpoint)

    def get_endpoint(
        self,
        path: str,
        method: str,
        version: Optional[APIVersion] = None
    ) -> Optional[APIEndpoint]:
        """获取 API 端点"""
        key = f"{method}:{path}"
        endpoints = self._endpoints.get(key, [])

        if not endpoints:
            return None

        if version:
            for endpoint in endpoints:
                if endpoint.version == version:
                    return endpoint

        # 返回最新版本
        for endpoint in sorted(endpoints, key=lambda e: e.version.value, reverse=True):
            if not endpoint.deprecated:
                return endpoint

        return None

    def get_all_endpoints(self, version: APIVersion) -> List[APIEndpoint]:
        """获取指定版本的所有端点"""
        result = []
        for endpoints in self._endpoints.values():
            for endpoint in endpoints:
                if endpoint.version == version:
                    result.append(endpoint)
        return result

    def get_version_info(self, version: APIVersion) -> Dict[str, Any]:
        """获取版本信息"""
        endpoints = self.get_all_endpoints(version)
        return {
            "version": version.value,
            "status": "current" if version == APIVersion.CURRENT else "legacy",
            "endpoints_count": len(endpoints),
            "endpoints": [
                {
                    "path": e.path,
                    "method": e.method,
                    "description": e.description,
                    "deprecated": e.deprecated
                }
                for e in endpoints
            ]
        }

    def check_compatibility(
        self,
        current_version: APIVersion,
        target_version: APIVersion
    ) -> Dict[str, Any]:
        """检查版本兼容性"""
        current_endpoints = {f"{e.method}:{e.path}" for e in self.get_all_endpoints(current_version)}
        target_endpoints = {f"{e.method}:{e.path}" for e in self.get_all_endpoints(target_version)}

        added = target_endpoints - current_endpoints
        removed = current_endpoints - target_endpoints

        return {
            "compatible": len(removed) == 0,
            "breaking_changes": list(removed),
            "new_features": list(added),
            "migration_guide": self._generate_migration_guide(current_version, target_version)
        }

    def _generate_migration_guide(
        self,
        from_version: APIVersion,
        to_version: APIVersion
    ) -> str:
        """生成迁移指南"""
        if from_version == APIVersion.V1 and to_version == APIVersion.V2:
            return """
## 从 V1 迁移到 V2 指南

### 主要变更
1. `/api/ingest/news` 现在返回完整的任务信息，包括 `task_id`, `answer` 等
2. 新增进度查询接口: `GET /api/ingest/news/progress/{task_id}`

### 迁移步骤
1. 更新 API 基础路径从 `/api/` 到 `/api/v2/`
2. 处理新的响应格式
3. 使用 task_id 查询进度

### 示例
```bash
# 旧版 (V1)
curl -X POST /api/ingest/news -d '{"query": "test"}'

# 新版 (V2)
curl -X POST /api/ingest/news -d '{"query": "test"}'
# 响应: {"task_id": "xxx", "status": "completed", "answer": "..."}
```
"""
        return "暂无迁移指南"

    def get_change_log(self, version: Optional[APIVersion] = None) -> List[Dict]:
        """获取变更日志"""
        if version:
            for log in self._version_history:
                if log.version == version:
                    return [
                        {
                            "version": log.version.value,
                            "date": log.date,
                            "changes": log.changes,
                            "breaking_changes": log.breaking_changes
                        }
                    ]
            return []
        return [
            {
                "version": log.version.value,
                "date": log.date,
                "changes": log.changes,
                "breaking_changes": log.breaking_changes
            }
            for log in self._version_history
        ]


# 全局实例
_version_controller: Optional[APIVersionController] = None


def get_version_controller() -> APIVersionController:
    """获取版本控制器单例"""
    global _version_controller
    if _version_controller is None:
        _version_controller = APIVersionController()
    return _version_controller