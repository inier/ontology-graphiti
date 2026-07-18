"""搜索服务编排层"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """搜索服务 - 委托给 WebSearchSkill 执行"""

    def search(self, query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
        """执行搜索"""
        try:
            from odap.tools.web.web_skills import _web_search_skill
            result = _web_search_skill.run({
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
            })
            if result.success:
                return result.data
            return {"status": "error", "message": result.error}
        except Exception as e:
            logger.error(f"Search service error: {e}")
            return {"status": "error", "message": str(e)}
