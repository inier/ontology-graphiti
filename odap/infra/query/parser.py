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
    }

    def parse(self, query: str, limit: int = 20) -> ParsedQuery:
        query = query.strip()
        source = QuerySource.ENTITY
        filters: Optional[Dict[str, Any]] = None
        if filters is None:
            filters = {}
        action = None
        action_params: Optional[Dict[str, Any]] = None
        if action_params is None:
            action_params = {}

        for prefix, src in self.SOURCE_MAP.items():
            if query.startswith(prefix):
                source = src
                query = query[len(prefix):].strip()
                break

        with_match = re.search(r"with\(([^)]+)\)", query)
        if with_match:
            filters = self._parse_filters(with_match.group(1))

        if source == QuerySource.TOPO:
            if "neighbors(" in query:
                action = "neighbors"
                params_match = re.search(r"neighbors\(([^)]+)\)", query)
                if params_match:
                    action_params = self._parse_neighbors_params(params_match.group(1))
            elif "path(" in query:
                action = "path"
                params_match = re.search(r"path\(([^)]+)\)", query)
                if params_match:
                    action_params = self._parse_path_params(params_match.group(1))
            elif "relations(" in query:
                action = "relations"
                params_match = re.search(r"relations\(([^)]+)\)", query)
                if params_match:
                    action_params = self._parse_neighbors_params(params_match.group(1))

        if source == QuerySource.TEMPORAL:
            at_match = re.search(r"at\('([^']+)'\)", query)
            if at_match:
                action = "at"
                action_params["valid_time"] = at_match.group(1)
            history_match = re.search(r"history\(([^)]+)\)", query)
            if history_match:
                action = "history"
                action_params = self._parse_neighbors_params(history_match.group(1))

        return ParsedQuery(
            source=source,
            filters=filters,
            action=action,
            action_params=action_params,
            limit=limit,
        )

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
