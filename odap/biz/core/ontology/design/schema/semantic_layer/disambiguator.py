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
            "传感器": ["sensor", "探测设备", "监测站"],
            "目标": ["target", "对象", "标的"],
            "风险": ["risk", "危险", "威胁"],
            "单位": ["unit", "组织", "编队"],
            "负责人": ["principal", "主管", "负责人"],
            "信息": ["information", "情报", "info"],
        }
        self._expansion_rules: List[Dict[str, Any]] = [
            {"pattern": "状态", "expansion": ["当前状态", "运行状态", "系统状态"]},
            {"pattern": "位置", "expansion": ["坐标位置", "地理位置", "部署位置"]},
            {"pattern": "能力", "expansion": ["作业能力", "监测能力", "防护能力"]},
        ]
        self._initialized = True

    def reset(self):
        """重置为默认状态（用于测试，避免单例污染）"""
        self._synonyms = {
            "传感器": ["sensor", "探测设备", "监测站"],
            "目标": ["target", "对象", "标的"],
            "风险": ["risk", "危险", "威胁"],
            "单位": ["unit", "组织", "编队"],
            "负责人": ["principal", "主管", "负责人"],
            "信息": ["information", "情报", "info"],
        }
        self._expansion_rules = [
            {"pattern": "状态", "expansion": ["当前状态", "运行状态", "系统状态"]},
            {"pattern": "位置", "expansion": ["坐标位置", "地理位置", "部署位置"]},
            {"pattern": "能力", "expansion": ["作业能力", "监测能力", "防护能力"]},
        ]

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

    def load_domain(self, domain_name: str, semantic_config: Dict[str, Any]) -> Dict[str, Any]:
        """从语义配置加载一个领域的术语到 Disambiguator

        Args:
            domain_name: 领域名（sanguo/xiyou）
            semantic_config: 语义配置字典，含 canonical_terms 和 expansion_rules

        Returns:
            加载统计: {"synonyms_added": int, "rules_added": int}
        """
        synonyms_added = 0
        rules_added = 0

        # 加载规范术语及其同义词
        canonical_terms = semantic_config.get("canonical_terms", {})
        for canonical, term_info in canonical_terms.items():
            for synonym in term_info.get("synonyms", []):
                result = self.add_synonym(canonical, synonym)
                if result.get("status") == "success":
                    synonyms_added += 1
            for synonym in term_info.get("near_synonyms", []):
                result = self.add_synonym(canonical, synonym)
                if result.get("status") == "success":
                    synonyms_added += 1
            for alias in term_info.get("aliases", []):
                result = self.add_synonym(canonical, alias)
                if result.get("status") == "success":
                    synonyms_added += 1

        # 加载扩展规则
        expansion_rules = semantic_config.get("expansion_rules", [])
        for rule in expansion_rules:
            pattern = rule.get("pattern", "")
            for exp in rule.get("expansion", []):
                result = self.add_expansion_rule(pattern, exp)
                if result.get("status") == "success":
                    rules_added += 1

        logger.info(
            "Loaded domain '%s': %d synonyms, %d expansion rules",
            domain_name, synonyms_added, rules_added
        )
        return {"synonyms_added": synonyms_added, "rules_added": rules_added}
