import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CompileResult:
    success: bool
    rego_text: str = ""
    errors: List[str] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)


class MarkdownCompiler:
    ROLE_MAP = {
        "系统管理员": "system_admin",
        "管理员": "admin",
        "负责人": "director",
        "分析师": "analyst",
        "操作员": "operator",
        "观察员": "observer",
        "审计员": "auditor",
        "访客": "guest",
        "成员": "member",
        "组长": "team_leader",
        "项目负责人": "project_owner",
    }

    ACTION_MAP = {
        "查询": "view",
        "查看": "view",
        "读取": "read",
        "写入": "write",
        "创建": "create",
        "删除": "delete",
        "更新": "update",
        "交锋": "engage",
        "守卫": "hold",
        "撤出": "withdraw",
        "支援": "support",
        "移动": "move",
        "观察": "observe",
        "通信": "communicate",
        "分析": "analyze_data",
        "报告": "generate_reports",
        "查看信息": "view_information",
        "决策": "decide",
        "执行": "perform",
        "协调": "coordinate_units",
        "审批": "approve",
        "导出": "export",
        "导入": "import",
    }

    EFFECT_MAP = {
        "允许": "allow",
        "拒绝": "deny",
        "禁止": "deny",
    }

    CONDITION_KEYWORDS = {
        "工作日": "weekday",
        "值班时间": "duty_hours",
        "工作时间": "working_hours",
        "需确认": "needs_confirmation",
        "需审批": "needs_approval",
        "高风险": "high_risk",
        "仅管理员": "admin_only",
        "需双人确认": "dual_confirmation",
        "密级": "clearance",
        "工作空间": "workspace",
    }

    RULE_PATTERN = re.compile(
        r'##\s*规则\s*[:：]\s*(.+?)(?:\n|$)',
        re.IGNORECASE
    )

    WHEN_PATTERN = re.compile(
        r'当\s*\[(.+?)\]\s*(?:且|and)?\s*\[(.+?)\]\s*时\s*\[(允许|拒绝|禁止)\]',
        re.DOTALL
    )

    WHEN_SINGLE_PATTERN = re.compile(
        r'当\s*\[(.+?)\]\s*时\s*\[(允许|拒绝|禁止)\]',
        re.DOTALL
    )

    ROLE_CONDITION_PATTERN = re.compile(
        r'角色(?:为|是|:：)\s*(.+?)(?:\s*[，,且and]|$)',
        re.IGNORECASE
    )

    ACTION_CONDITION_PATTERN = re.compile(
        r'操作(?:为|是|:：)\s*(.+?)(?:\s*[，,且and]|$)',
        re.IGNORECASE
    )

    CLEARANCE_CONDITION_PATTERN = re.compile(
        r'密级(?:为|是|<=|>=|:：)\s*(.+?)(?:\s*[，,且and]|$)',
        re.IGNORECASE
    )

    WORKSPACE_CONDITION_PATTERN = re.compile(
        r'工作空间(?:为|是|:：)\s*(.+?)(?:\s*[，,且and]|$)',
        re.IGNORECASE
    )

    def compile(self, markdown_text: str) -> CompileResult:
        if not markdown_text or not markdown_text.strip():
            return CompileResult(success=False, errors=["Markdown内容不能为空"])

        rules = self._parse_rules(markdown_text)
        if not rules:
            return CompileResult(success=False, errors=["未找到有效的策略规则，请使用 '## 规则: 规则名' 格式"])

        rego_text = self._generate_rego(rules)
        validation = self.validate(rego_text)
        if not validation["valid"]:
            return CompileResult(success=False, errors=validation["errors"], rego_text=rego_text)

        return CompileResult(success=True, rego_text=rego_text, rules=rules)

    def validate(self, rego_text: str) -> Dict[str, Any]:
        errors = []
        if not rego_text or not rego_text.strip():
            return {"valid": False, "errors": ["Rego内容为空"]}

        if not re.search(r'package\s+\w+', rego_text):
            errors.append("缺少package声明")

        if not re.search(r'(default\s+)?allow\s*(:=|=)\s*(true|false)', rego_text):
            errors.append("缺少default allow声明")

        open_braces = rego_text.count('{')
        close_braces = rego_text.count('}')
        if open_braces != close_braces:
            errors.append(f"花括号不匹配: {{ {open_braces} 个, }} {close_braces} 个")

        for i, line in enumerate(rego_text.split('\n'), 1):
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('package'):
                if not stripped.endswith(('}', ',', '[', ']', '(', ')')) and '{' not in stripped and '}' not in stripped:
                    if re.match(r'^\w+\s*(:=|=)', stripped) and not stripped.endswith(('true', 'false', '"', "'", ')', ']', '}')):
                        if not stripped.endswith(','):
                            pass

        return {"valid": len(errors) == 0, "errors": errors}

    def _parse_rules(self, markdown_text: str) -> List[Dict[str, Any]]:
        rules = []
        sections = re.split(r'(?=##\s*规则\s*[:：])', markdown_text)

        for section in sections:
            if not section.strip():
                continue

            rule_match = self.RULE_PATTERN.match(section.strip())
            if not rule_match:
                continue

            rule_name = rule_match.group(1).strip()
            rule_body = section[rule_match.end():]

            when_match = self.WHEN_PATTERN.search(rule_body)
            if when_match:
                condition1 = when_match.group(1).strip()
                condition2 = when_match.group(2).strip()
                effect = when_match.group(3).strip()
                rule = self._build_rule(rule_name, [condition1, condition2], effect)
                rules.append(rule)
                continue

            when_single = self.WHEN_SINGLE_PATTERN.search(rule_body)
            if when_single:
                condition = when_single.group(1).strip()
                effect = when_single.group(2).strip()
                rule = self._build_rule(rule_name, [condition], effect)
                rules.append(rule)
                continue

            conditions = self._parse_freeform_conditions(rule_body)
            effect = self._detect_effect(rule_body)
            if conditions:
                rule = self._build_rule(rule_name, conditions, effect)
                rules.append(rule)

        return rules

    def _build_rule(self, name: str, conditions: List[str], effect: str) -> Dict[str, Any]:
        parsed_conditions = []
        for cond in conditions:
            parsed = self._parse_condition(cond)
            parsed_conditions.append(parsed)

        effect_en = self.EFFECT_MAP.get(effect, "allow")

        return {
            "name": name,
            "conditions": parsed_conditions,
            "effect": effect_en,
        }

    def _parse_condition(self, condition_text: str) -> Dict[str, Any]:
        role_match = self.ROLE_CONDITION_PATTERN.search(condition_text)
        if role_match:
            role_cn = role_match.group(1).strip()
            role_en = self.ROLE_MAP.get(role_cn, role_cn)
            return {"type": "role", "value": role_en, "rego": f'input.subject.roles[_] == "{role_en}"'}

        action_match = self.ACTION_CONDITION_PATTERN.search(condition_text)
        if action_match:
            action_cn = action_match.group(1).strip()
            action_en = self.ACTION_MAP.get(action_cn, action_cn)
            return {"type": "action", "value": action_en, "rego": f'input.action.type == "{action_en}"'}

        clearance_match = self.CLEARANCE_CONDITION_PATTERN.search(condition_text)
        if clearance_match:
            level = clearance_match.group(1).strip()
            return {"type": "clearance", "value": level, "rego": f'input.subject.clearance_level == "{level}"'}

        workspace_match = self.WORKSPACE_CONDITION_PATTERN.search(condition_text)
        if workspace_match:
            ws = workspace_match.group(1).strip()
            return {"type": "workspace", "value": ws, "rego": f'input.resource.workspace_id == "{ws}"'}

        return {"type": "custom", "value": condition_text, "rego": f'input.context["{condition_text}"] == true'}

    def _parse_freeform_conditions(self, text: str) -> List[str]:
        conditions = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- ') or stripped.startswith('* '):
                cond_text = stripped[2:].strip()
                if any(kw in cond_text for kw in ['角色', '操作', '密级', '工作空间', '时间', '条件']):
                    conditions.append(cond_text)
        return conditions

    def _detect_effect(self, text: str) -> str:
        if re.search(r'(拒绝|禁止|deny|forbidden)', text, re.IGNORECASE):
            return "拒绝"
        return "允许"

    def _generate_rego(self, rules: List[Dict[str, Any]]) -> str:
        lines = ["package domain.markdown_policy", ""]
        lines.append("import future.keywords.if")
        lines.append("import future.keywords.in")
        lines.append("")
        lines.append("default allow := false")
        lines.append("")

        for i, rule in enumerate(rules):
            rule_name_safe = re.sub(r'[^a-zA-Z0-9_]', '_', rule["name"]).lower()
            effect = rule["effect"]

            if rule["conditions"]:
                cond_lines = []
                for cond in rule["conditions"]:
                    if cond.get("rego"):
                        cond_lines.append(f"    {cond['rego']}")

                if cond_lines:
                    lines.append(f'{effect} if {{')
                    for cl in cond_lines:
                        lines.append(cl)
                    lines.append('}')
                    lines.append('')

        lines.append("subject_clearance_level := input.subject.clearance_level")
        lines.append("resource_classification := input.resource.classification")
        lines.append("subject_workspace := input.subject.workspace_id")
        lines.append("resource_workspace := input.resource.workspace_id")
        lines.append("")
        lines.append("clearance_order := {")
        lines.append('    "public": 1,')
        lines.append('    "confidential": 2,')
        lines.append('    "secret": 3,')
        lines.append('    "top_secret": 4,')
        lines.append('}')
        lines.append("")
        lines.append("clearance_sufficient if {")
        lines.append("    clearance_order[subject_clearance_level] >= clearance_order[resource_classification]")
        lines.append("}")
        lines.append("")
        lines.append("workspace_isolated if {")
        lines.append("    subject_workspace == resource_workspace")
        lines.append("}")

        return "\n".join(lines)
