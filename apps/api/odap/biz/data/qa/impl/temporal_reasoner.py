import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class TemporalReasoner:
    def __init__(self, graphiti_client=None):
        self.graphiti = graphiti_client

    def answer_temporal_question(
        self,
        question: str,
        valid_time: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        parsed = self._parse_temporal_question(question, valid_time)
        if not parsed.get("valid_time"):
            return {
                "status": "error",
                "message": "无法解析时间表达式",
                "question": question,
            }

        entities = self._query_temporal_entities(
            parsed["valid_time"],
            parsed.get("transaction_time"),
            workspace_id,
        )

        answer = self._generate_temporal_answer(question, parsed, entities)

        return {
            "status": "success",
            "question": question,
            "valid_time": parsed["valid_time"],
            "time_type": parsed.get("time_type", "specific"),
            "answer": answer,
            "entities": entities[:10],
            "entity_count": len(entities),
        }

    def _parse_temporal_question(
        self, question: str, valid_time: Optional[str] = None
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "valid_time": valid_time,
            "transaction_time": None,
            "time_type": "specific",
            "original_question": question,
        }

        if valid_time:
            result["time_type"] = "explicit"
            return result

        patterns = [
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "specific_date"),
            (r"(\d{4})年(\d{1,2})月", "specific_month"),
            (r"(\d{4})年", "specific_year"),
            (r"上周|上一周", "last_week"),
            (r"这周|本周|这周", "this_week"),
            (r"上个月|上月", "last_month"),
            (r"这个月|本月", "this_month"),
            (r"昨天|昨日", "yesterday"),
            (r"今天|今日|现在|当前|此刻", "now"),
            (r"(\d+)小时前", "hours_ago"),
            (r"(\d+)天前", "days_ago"),
            (r"事件发生时|当时|那时候", "event_time"),
        ]

        now = datetime.now(timezone.utc)

        for pattern, time_type in patterns:
            match = re.search(pattern, question)
            if match:
                result["time_type"] = time_type
                result["match_text"] = match.group(0)

                if time_type == "specific_date":
                    y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    result["valid_time"] = datetime(y, m, d, tzinfo=timezone.utc).isoformat()
                elif time_type == "specific_month":
                    y, m = int(match.group(1)), int(match.group(2))
                    result["valid_time"] = datetime(y, m, 1, tzinfo=timezone.utc).isoformat()
                elif time_type == "specific_year":
                    y = int(match.group(1))
                    result["valid_time"] = datetime(y, 1, 1, tzinfo=timezone.utc).isoformat()
                elif time_type == "last_week":
                    result["valid_time"] = (now - timedelta(weeks=1)).isoformat()
                elif time_type == "this_week":
                    result["valid_time"] = now.isoformat()
                elif time_type == "last_month":
                    result["valid_time"] = (now - timedelta(days=30)).isoformat()
                elif time_type == "this_month":
                    result["valid_time"] = now.isoformat()
                elif time_type == "yesterday":
                    result["valid_time"] = (now - timedelta(days=1)).isoformat()
                elif time_type == "now":
                    result["valid_time"] = now.isoformat()
                elif time_type == "hours_ago":
                    hours = int(match.group(1))
                    result["valid_time"] = (now - timedelta(hours=hours)).isoformat()
                elif time_type == "days_ago":
                    days = int(match.group(1))
                    result["valid_time"] = (now - timedelta(days=days)).isoformat()
                elif time_type == "event_time":
                    result["valid_time"] = None
                    result["time_type"] = "event_time"

                break

        return result

    def _query_temporal_entities(
        self,
        valid_time: Optional[str],
        transaction_time: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.graphiti:
            return []

        try:
            entities = self.graphiti.query_temporal(
                valid_time=valid_time,
                transaction_time=transaction_time,
            )
            if workspace_id and workspace_id != "default":
                entities = [
                    e for e in entities
                    if e.get("properties", {}).get("workspace_id", "") == workspace_id
                    or not e.get("properties", {}).get("workspace_id")
                ]
            return entities
        except Exception as e:
            logger.warning(f"TemporalReasoner query failed: {e}")
            return []

    def _generate_temporal_answer(
        self,
        question: str,
        parsed: Dict[str, Any],
        entities: List[Dict[str, Any]],
    ) -> str:
        if not entities:
            time_desc = parsed.get("valid_time", "指定时间")
            return f"在{time_desc}时，未找到相关数据。"

        time_type = parsed.get("time_type", "specific")
        time_desc = parsed.get("match_text", parsed.get("valid_time", "指定时间"))

        parts = [f"在{time_desc}时，共找到 {len(entities)} 条相关记录："]

        for i, entity in enumerate(entities[:5], 1):
            props = entity.get("properties", {})
            name = props.get("name", entity.get("id", "未知"))
            etype = props.get("type", props.get("entity_type", ""))
            desc = f"[{i}] {name}"
            if etype:
                desc += f" (类型: {etype})"
            for key in ("status", "state", "affiliation", "area"):
                if key in props and props[key]:
                    desc += f" | {key}: {props[key]}"
            parts.append(desc)

        if len(entities) > 5:
            parts.append(f"... 还有 {len(entities) - 5} 条记录")

        return "\n".join(parts)
