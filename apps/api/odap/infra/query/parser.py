import re
from typing import Any, Dict, Optional, Tuple

from .protocols import QuerySource


class ParsedQuery:
    def __init__(
        self,
        source: QuerySource,
        filters: Dict[str, Any],
        action: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ):
        self.source = source
        self.filters = filters
        self.action = action
        self.action_params = action_params or {}
        self.limit = limit


class QueryParser:
    SOURCE_MAP = {
        ".schema": QuerySource.SCHEMA,
        ".entity": QuerySource.ENTITY,
        ".topo": QuerySource.TOPO,
        ".temporal": QuerySource.TEMPORAL,
        ".unstructured": QuerySource.UNSTRUCTURED,
    }

    def parse(self, query: str, limit: int = 20) -> ParsedQuery:
        query = query.strip()
        source, query = self._strip_source_prefix(query)
        filters: Dict[str, Any] = {}
        with_match = re.search(r"with\(([^)]+)\)", query)
        if with_match:
            filters = self._parse_filters(with_match.group(1))
        action: Optional[str] = None
        action_params: Dict[str, Any] = {}
        if source == QuerySource.TOPO:
            action, action_params = self._parse_topo_action(query, action_params)
        elif source == QuerySource.TEMPORAL:
            action, action_params = self._parse_temporal_action(query, action_params)
        return ParsedQuery(
            source=source,
            filters=filters,
            action=action,
            action_params=action_params,
            limit=limit,
        )

    def _strip_source_prefix(self, query: str):
        for prefix, src in self.SOURCE_MAP.items():
            if query.startswith(prefix):
                return src, query[len(prefix):].strip()
        return QuerySource.ENTITY, query

    def _parse_topo_action(self, query: str, action_params: Dict[str, Any]):
        if "neighbors(" in query:
            params = self._match_paren_call(query, "neighbors")
            if params:
                return "neighbors", self._parse_neighbors_params(params)
        if "path(" in query:
            params = self._match_paren_call(query, "path")
            if params:
                return "path", self._parse_path_params(params)
        if "relations(" in query:
            params = self._match_paren_call(query, "relations")
            if params:
                return "relations", self._parse_neighbors_params(params)
        return None, action_params

    def _parse_temporal_action(self, query: str, action_params: Dict[str, Any]):
        at_match = re.search(r"at\('([^']+)'\)", query)
        if at_match:
            action_params["valid_time"] = at_match.group(1)
            return "at", action_params
        history_match = re.search(r"history\(([^)]+)\)", query)
        if history_match:
            return "history", self._parse_neighbors_params(history_match.group(1))
        return None, action_params

    def _match_paren_call(self, query: str, name: str) -> Optional[str]:
        match = re.search(rf"{name}\(([^)]+)\)", query)
        return match.group(1) if match else None

    def _parse_filters(self, filter_str: str) -> Dict[str, Any]:
        filters: Optional[Dict[str, Any]] = None
        if filters is None:
            filters = {}
        for pair in filter_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                filters[key] = value
        return filters

    def _parse_neighbors_params(self, params_str: str) -> Dict[str, Any]:
        params: Optional[Dict[str, Any]] = None
        if params is None:
            params = {}
        for pair in params_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                try:
                    params[key] = int(value)
                except ValueError:
                    params[key] = value
        return params

    def _parse_path_params(self, params_str: str) -> Dict[str, Any]:
        params = self._parse_neighbors_params(params_str)
        if "max_hops" in params:
            params["max_depth"] = params.pop("max_hops")
        return params
