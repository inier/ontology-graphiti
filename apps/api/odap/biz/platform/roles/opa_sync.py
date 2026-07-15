class RoleOPASync:
    def __init__(self):
        self._opa_manager = None

    @property
    def opa_manager(self):
        if self._opa_manager is None:
            try:
                from odap.infra.opa.opa_service import OPAManagerV2
                self._opa_manager = OPAManagerV2()
            except Exception:
                pass
        return self._opa_manager

    def sync_role_to_opa(self, role_data: dict) -> bool:
        try:
            opa = self.opa_manager
            if not opa:
                return False
            role_name = role_data.get("name", "unknown")
            role_type = role_data.get("role_type", "member")
            permissions = role_data.get("permissions", [])
            rego = self._generate_rego(role_name, role_type, permissions)
            policy_id = f"role_{role_data.get('id', 'unknown')}"
            return opa.load_policy(policy_id, rego)
        except Exception:
            return False

    def remove_role_from_opa(self, role_id: str) -> bool:
        try:
            opa = self.opa_manager
            if not opa:
                return False
            policy_id = f"role_{role_id}"
            return opa.delete_policy(policy_id)
        except Exception:
            return False

    def _generate_rego(self, role_name, role_type, permissions):
        allow_actions = []
        for p in permissions:
            if isinstance(p, str):
                allow_actions.append(p)
            elif isinstance(p, dict):
                allow_actions.extend(p.get("actions", []))
        actions_str = ", ".join(f'"{a}"' for a in allow_actions) if allow_actions else '""'
        return f"""package odap.roles.{role_name}
default allow = false
allow {{
    input.role == "{role_name}"
    input.action in [{actions_str}]
}}
"""
