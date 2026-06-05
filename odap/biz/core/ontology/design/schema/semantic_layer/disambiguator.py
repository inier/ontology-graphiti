import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class Disambiguator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._synonyms: Dict[str, List[str]] = {
            "雷达": ["radar", "雷达站", "探测设备"],
            "目标": ["target", "对象", "标的"],
            "威胁": ["threat", "危险", "风险"],
            "单位": ["unit", "部队", "编队"],
            "指挥官": ["commander", "指挥员", "指挥"],
            "情报": ["intelligence", "信息", "intel"],
        }
        self._expansion_rules: List[Dict[str, Any]] = [
            {"pattern": "状态", "expansion": ["当前状态", "运行状态", "系统状态"]},
            {"pattern": "位置", "expansion": ["坐标位置", "地理位置", "部署位置"]},
            {"pattern": "能力", "expansion": ["作战能力", "侦察能力", "防护能力"]},
        ]
        self._initialized = True

    def disambiguate(self, term: str) -> Dict[str, Any]:
        canonical = self._find_canonical(term)
        synonyms = self._find_synonyms(canonical or term)
        expansions = self._find_expansions(term)
        return {
            "original": term,
            "canonical": canonical,
            "synonyms": synonyms,
            "expansions": expansions,
        }

    def _find_canonical(self, term: str) -> Optional[str]:
        term_lower = term.lower()
        for canonical, syns in self._synonyms.items():
            if term_lower == canonical.lower() or term_lower in [s.lower() for s in syns]:
                return canonical
        return None

    def _find_synonyms(self, term: str) -> List[str]:
        return self._synonyms.get(term, [])

    def _find_expansions(self, term: str) -> List[str]:
        expansions = []
        for rule in self._expansion_rules:
            if rule["pattern"] in term:
                expansions.extend(rule["expansion"])
        return expansions

    def add_synonym(self, canonical: str, synonym: str) -> Dict[str, Any]:
        if canonical not in self._synonyms:
            self._synonyms[canonical] = []
        if synonym not in self._synonyms[canonical]:
            self._synonyms[canonical].append(synonym)
        return {"status": "success", "canonical": canonical, "synonym": synonym}

    def add_expansion_rule(self, pattern: str, expansion: str) -> Dict[str, Any]:
        for rule in self._expansion_rules:
            if rule["pattern"] == pattern:
                if expansion not in rule["expansion"]:
                    rule["expansion"].append(expansion)
                return {"status": "success", "pattern": pattern, "expansion": expansion}
        self._expansion_rules.append({"pattern": pattern, "expansion": [expansion]})
        return {"status": "success", "pattern": pattern, "expansion": expansion}

    def get_synonyms(self) -> Dict[str, List[str]]:
        return dict(self._synonyms)

    def get_expansion_rules(self) -> List[Dict[str, Any]]:
        return list(self._expansion_rules)
