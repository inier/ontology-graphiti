from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import time
import uuid

router = APIRouter(prefix="/api/policies", tags=["policies"])

_policies_store: Dict[str, Dict[str, Any]] = {}


def _init_default_policies():
    if _policies_store:
        return
    defaults = [
        {
            "policy_id": "policy-access-control",
            "name": "访问控制策略",
            "description": "基于角色的访问控制策略，定义不同角色的权限范围",
            "category": "access_control",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 访问控制策略\n\n定义系统管理员、项目经理、团队成员和访客的权限。",
            "rego_content": 'package domain\n\ndefault allow = false\n\nallow {\n    input.role == "system_admin"\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "policy_id": "policy-data-privacy",
            "name": "数据隐私策略",
            "description": "数据访问和隐私保护策略",
            "category": "data_privacy",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 数据隐私策略\n\n保护敏感数据，限制未授权访问。",
            "rego_content": 'package domain.data_privacy\n\ndefault allow = false\n\nallow {\n    input.clearance_level >= input.resource.clearance_required\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "policy_id": "policy-compliance",
            "name": "合规审计策略",
            "description": "操作合规性和审计追踪策略",
            "category": "compliance",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 合规审计策略\n\n确保所有操作符合合规要求。",
            "rego_content": 'package domain.compliance\n\ndefault allow = false\n\nallow {\n    input.action == "read"\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
    ]
    for p in defaults:
        _policies_store[p["policy_id"]] = p


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    markdown_content: str = Field(..., min_length=1)
    category: str = "custom"


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    markdown_content: Optional[str] = None
    status: Optional[str] = None


@router.get("")
async def list_policies(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _init_default_policies()
    policies = list(_policies_store.values())
    if status:
        policies = [p for p in policies if p["status"] == status]
    if category:
        policies = [p for p in policies if p["category"] == category]
    policies = policies[:limit]
    return {"policies": policies, "total": len(policies)}


@router.post("")
async def create_policy(data: PolicyCreate):
    _init_default_policies()
    policy_id = f"policy-{uuid.uuid4().hex[:8]}"
    rego_content = _markdown_to_rego(data.markdown_content)
    policy = {
        "policy_id": policy_id,
        "name": data.name,
        "description": data.description,
        "category": data.category,
        "status": "enabled",
        "version": "1.0.0",
        "markdown_content": data.markdown_content,
        "rego_content": rego_content,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    _policies_store[policy_id] = policy
    return policy


@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return policy


@router.put("/{policy_id}")
async def update_policy(policy_id: str, data: PolicyUpdate):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if data.name is not None:
        policy["name"] = data.name
    if data.description is not None:
        policy["description"] = data.description
    if data.markdown_content is not None:
        policy["markdown_content"] = data.markdown_content
        policy["rego_content"] = _markdown_to_rego(data.markdown_content)
    if data.status is not None:
        policy["status"] = data.status
    version_parts = policy["version"].split(".")
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    policy["version"] = ".".join(version_parts)
    policy["updated_at"] = datetime.utcnow().isoformat()
    return {
        "policy_id": policy_id,
        "name": policy["name"],
        "status": policy["status"],
        "version": policy["version"],
    }


@router.post("/{policy_id}/toggle")
async def toggle_policy_status(policy_id: str, enabled: bool = Query(True)):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    policy["status"] = "enabled" if enabled else "disabled"
    policy["updated_at"] = datetime.utcnow().isoformat()
    return {"policy_id": policy_id, "status": policy["status"]}


def _markdown_to_rego(markdown: str) -> str:
    converter = MarkdownPolicyConverter()
    return converter.convert(markdown)


class MarkdownPolicyConverter:
    ROLE_MAP = {
        "commander": "commander",
        "intelligence_officer": "intelligence_officer",
        "intelligence": "intelligence_officer",
        "operator": "operator",
        "admin": "admin",
        "auditor": "auditor",
        "guest": "guest",
    }

    ACTION_MAP = {
        "查询": "view",
        "攻击": "attack",
        "防御": "defend",
        "撤退": "retreat",
        "增援": "reinforce",
        "移动": "move",
        "观察": "observe",
        "通信": "communicate",
        "分析": "analyze_data",
        "报告": "generate_reports",
        "查看情报": "view_intelligence",
        "决策": "decide",
        "执行": "perform",
        "命令": "command_unit",
    }

    CONDITION_MAP = {
        "需确认": "needs_confirmation",
        "需审批": "needs_approval",
        "高风险": "high_risk",
        "仅管理员": "admin_only",
        "需双人确认": "dual_confirmation",
    }

    def convert(self, markdown: str) -> str:
        lines = markdown.strip().split("\n")
        package_name = "domain.custom"
        role = ""
        allowed_actions = []
        rules = []
        current_section = ""

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                pkg = stripped[2:].strip().lower().replace(" ", "_")
                package_name = f"policies.{pkg}"
            elif stripped.startswith("## "):
                current_section = stripped[3:].strip().lower()
                if "角色" in current_section or "role" in current_section:
                    role_match = current_section.replace("角色", "").replace("role", "").strip().replace(":", "").strip()
                    if role_match:
                        role = self.ROLE_MAP.get(role_match, role_match)
            elif stripped.startswith("- "):
                item = stripped[2:].strip()
                if "允许" in current_section or "操作" in current_section or "allow" in current_section:
                    action_info = self._parse_action(item)
                    if action_info:
                        allowed_actions.append(action_info)
                elif "规则" in current_section or "rule" in current_section:
                    rule = self._parse_rule(item)
                    if rule:
                        rules.append(rule)

        return self._generate_rego(package_name, role, allowed_actions, rules)

    def _parse_action(self, item: str) -> dict:
        action = {"name": "", "conditions": []}
        paren_match = ""
        if "（" in item and "）" in item:
            main_part = item[:item.index("（")].strip()
            paren_match = item[item.index("（") + 1:item.index("）")].strip()
        elif "(" in item and ")" in item:
            main_part = item[:item.index("(")].strip()
            paren_match = item[item.index("(") + 1:item.index(")")].strip()
        else:
            main_part = item.strip()

        action["name"] = self.ACTION_MAP.get(main_part, main_part.lower().replace(" ", "_"))

        if paren_match:
            for cond_key, cond_val in self.CONDITION_MAP.items():
                if cond_key in paren_match:
                    action["conditions"].append(cond_val)

        return action

    def _parse_rule(self, item: str) -> dict:
        rule = {"conditions": [], "result": "allow"}
        if "如果" in item or "if" in item.lower():
            cond_part = item.split("那么") if "那么" in item else [item, ""]
            condition_text = cond_part[0].replace("如果", "").strip()
            result_text = cond_part[1].strip() if len(cond_part) > 1 else "允许"

            if "角色是" in condition_text:
                role_val = condition_text.split("角色是")[1].split("且")[0].split("或")[0].strip()
                rule["conditions"].append(f'input.user.role == "{self.ROLE_MAP.get(role_val, role_val)}"')
            if "操作是" in condition_text:
                action_val = condition_text.split("操作是")[1].split("且")[0].split("或")[0].strip()
                rule["conditions"].append(f'input.action == "{self.ACTION_MAP.get(action_val, action_val)}"')

            if "拒绝" in result_text or "禁止" in result_text:
                rule["result"] = "deny"

        return rule

    def _generate_rego(self, package_name: str, role: str,
                       allowed_actions: list, rules: list) -> str:
        lines = [f"package {package_name}", ""]
        lines.append("import future.keywords.if")
        lines.append("import future.keywords.in")
        lines.append("")
        lines.append("default allow := false")
        lines.append("")

        if role:
            lines.append(f'allow if {{')
            lines.append(f'    input.user.role == "{role}"')
            lines.append(f'    input.action in role_permissions["{role}"]')
            lines.append(f'}}')
            lines.append("")

        if allowed_actions:
            action_names = [a["name"] for a in allowed_actions]
            lines.append(f'allow if {{')
            lines.append(f'    input.action in allowed_actions')
            lines.append(f'}}')
            lines.append("")

            for action in allowed_actions:
                if action["conditions"]:
                    cond_strs = []
                    for c in action["conditions"]:
                        if c == "needs_confirmation":
                            cond_strs.append("input.confirmed == true")
                        elif c == "needs_approval":
                            cond_strs.append("input.approved == true")
                        elif c == "high_risk":
                            cond_strs.append('input.risk_level != "high"')
                        elif c == "admin_only":
                            cond_strs.append('input.user.role == "admin"')
                        elif c == "dual_confirmation":
                            cond_strs.append("input.confirmation_count >= 2")

                    if cond_strs:
                        lines.append(f'allow if {{')
                        lines.append(f'    input.action == "{action["name"]}"')
                        for cs in cond_strs:
                            lines.append(f'    {cs}')
                        lines.append(f'}}')
                        lines.append("")

        for rule in rules:
            if rule["conditions"]:
                lines.append(f'{rule["result"]} if {{')
                for cond in rule["conditions"]:
                    lines.append(f'    {cond}')
                lines.append(f'}}')
                lines.append("")

        lines.append("allowed_actions := [")
        for i, name in enumerate([a["name"] for a in allowed_actions]):
            comma = "," if i < len(allowed_actions) - 1 else ""
            lines.append(f'    "{name}"{comma}')
        lines.append("]")
        lines.append("")

        if role:
            lines.append(f'role_permissions := {{')
            lines.append(f'    "{role}": allowed_actions,')
            lines.append(f'}}')

        return "\n".join(lines)
