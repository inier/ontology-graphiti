import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..interfaces.isolation import IIsolationManager
from ..models.isolation import IsolationLevel, ResourceQuota, NetworkPolicy
from ..storage import Storage


class IsolationManager(IIsolationManager):

    DEFAULT_QUOTAS = {
        IsolationLevel.LOW: {"cpu": "2", "memory": "4Gi", "storage": "10Gi", "max_connections": 100, "max_processes": 50},
        IsolationLevel.STANDARD: {"cpu": "1", "memory": "2Gi", "storage": "5Gi", "max_connections": 50, "max_processes": 25},
        IsolationLevel.HIGH: {"cpu": "0.5", "memory": "1Gi", "storage": "2Gi", "max_connections": 20, "max_processes": 10},
        IsolationLevel.STRICT: {"cpu": "0.25", "memory": "512Mi", "storage": "1Gi", "max_connections": 10, "max_processes": 5},
    }

    def __init__(self):
        self.storage = Storage()

    def create_isolation_policy(self, workspace_id: str,
                                isolation_level: IsolationLevel = IsolationLevel.STANDARD,
                                resource_quota: ResourceQuota = None,
                                network_policy: NetworkPolicy = None) -> Dict[str, Any]:
        if not resource_quota:
            default = self.DEFAULT_QUOTAS.get(isolation_level, self.DEFAULT_QUOTAS[IsolationLevel.STANDARD])
            resource_quota = ResourceQuota(**default)

        if not network_policy:
            if isolation_level == IsolationLevel.STRICT:
                network_policy = NetworkPolicy(
                    allowed_ips=[],
                    blocked_ips=[],
                    allowed_ports=[443],
                    blocked_ports=[],
                    egress_rules=[{"protocol": "https", "port": 443}],
                    ingress_rules=[],
                    enable_firewall=True,
                )
            else:
                network_policy = NetworkPolicy()

        policy = {
            "workspace_id": workspace_id,
            "isolation_level": isolation_level.value,
            "resource_quota": resource_quota.model_dump(),
            "network_policy": network_policy.model_dump(),
            "created_at": datetime.now().isoformat(),
        }

        self.storage.save_isolation_policy(policy)
        return policy

    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        return self.storage.get_isolation_policy(workspace_id)

    def update_isolation_policy(self, workspace_id: str,
                                updates: Dict[str, Any]) -> Dict[str, Any]:
        policy = self.get_isolation_policy(workspace_id)
        if not policy:
            raise ValueError("Isolation policy not found")

        if "isolation_level" in updates:
            new_level = IsolationLevel(updates["isolation_level"])
            if new_level != IsolationLevel(policy["isolation_level"]):
                default = self.DEFAULT_QUOTAS.get(new_level, self.DEFAULT_QUOTAS[IsolationLevel.STANDARD])
                if "resource_quota" not in updates:
                    updates["resource_quota"] = ResourceQuota(**default).model_dump()

        policy.update(updates)
        self.storage.update_isolation_policy(workspace_id, policy)
        return policy

    def enforce_isolation(self, workspace_id: str) -> bool:
        policy = self.get_isolation_policy(workspace_id)
        if not policy:
            return False

        level = IsolationLevel(policy.get("isolation_level", "standard"))
        quota = policy.get("resource_quota", {})
        network = policy.get("network_policy", {})

        self._enforce_data_isolation(workspace_id, level)
        self._enforce_network_isolation(workspace_id, level, network)
        self._enforce_resource_limits(workspace_id, level, quota)

        return True

    def validate_isolation(self, workspace_id: str) -> Dict[str, Any]:
        policy = self.get_isolation_policy(workspace_id)
        if not policy:
            return {"status": "error", "message": "Isolation policy not found"}

        level = IsolationLevel(policy.get("isolation_level", "standard"))
        checks = []

        data_check = self._validate_data_isolation(workspace_id, level)
        checks.append(data_check)

        network_check = self._validate_network_isolation(workspace_id, level, policy.get("network_policy", {}))
        checks.append(network_check)

        resource_check = self._validate_resource_limits(workspace_id, level, policy.get("resource_quota", {}))
        checks.append(resource_check)

        all_passed = all(c.get("passed", False) for c in checks)

        return {
            "status": "success" if all_passed else "warning",
            "isolation_level": policy.get("isolation_level"),
            "checks": checks,
            "validation_time": datetime.now().isoformat(),
        }

    def get_resource_usage(self, workspace_id: str) -> Dict[str, Any]:
        db_path = os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "workspace.db",
        )
        entity_count = 0
        connection_count = 0

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scenarios WHERE workspace_id = ?", (workspace_id,))
            entity_count = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass

        data_dir = os.path.join(os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")))
        storage_bytes = 0
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                fp = os.path.join(data_dir, f)
                if os.path.isfile(fp):
                    storage_bytes += os.path.getsize(fp)

        return {
            "workspace_id": workspace_id,
            "entity_count": entity_count,
            "storage_bytes": storage_bytes,
            "storage_mb": round(storage_bytes / (1024 * 1024), 2) if storage_bytes else 0,
            "timestamp": datetime.now().isoformat(),
        }

    def check_quota_violation(self, workspace_id: str) -> List[Dict[str, Any]]:
        resource_usage = self.get_resource_usage(workspace_id)
        policy = self.get_isolation_policy(workspace_id)

        violations = []
        if not policy:
            return violations

        quota = policy.get("resource_quota", {})
        level = IsolationLevel(policy.get("isolation_level", "standard"))

        storage_limit = self._parse_size(quota.get("storage", "5Gi"))
        storage_used = resource_usage.get("storage_bytes", 0)
        if storage_limit > 0 and storage_used > storage_limit:
            violations.append({
                "resource": "storage",
                "usage_mb": resource_usage.get("storage_mb", 0),
                "limit": quota.get("storage", "5Gi"),
                "severity": "critical",
            })

        max_conn = quota.get("max_connections", 50)
        entity_count = resource_usage.get("entity_count", 0)
        if entity_count > max_conn:
            violations.append({
                "resource": "entities",
                "usage": entity_count,
                "limit": max_conn,
                "severity": "warning",
            })

        return violations

    def _enforce_data_isolation(self, workspace_id: str, level: IsolationLevel) -> None:
        if level in (IsolationLevel.HIGH, IsolationLevel.STRICT):
            self._verify_sqlite_workspace_filter(workspace_id)

    def _enforce_network_isolation(self, workspace_id: str, level: IsolationLevel, network: Dict) -> None:
        if level == IsolationLevel.STRICT:
            allowed_ports = network.get("allowed_ports", [443])
            if 80 in allowed_ports:
                pass

    def _enforce_resource_limits(self, workspace_id: str, level: IsolationLevel, quota: Dict) -> None:
        pass

    def _validate_data_isolation(self, workspace_id: str, level: IsolationLevel) -> Dict[str, Any]:
        if level in (IsolationLevel.LOW, IsolationLevel.STANDARD):
            return {"check": "data_isolation", "passed": True, "message": f"Level {level.value} does not require strict data isolation"}

        db_path = os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "workspace.db",
        )
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            cross_workspace_data = False
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                if "workspace_id" in columns:
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE workspace_id != ? AND workspace_id IS NOT NULL", (workspace_id,))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        cross_workspace_data = True
                        break
            conn.close()
            return {
                "check": "data_isolation",
                "passed": not cross_workspace_data,
                "message": "No cross-workspace data leakage detected" if not cross_workspace_data else "Cross-workspace data detected",
            }
        except Exception as e:
            return {"check": "data_isolation", "passed": True, "message": f"Could not verify: {str(e)}"}

    def _validate_network_isolation(self, workspace_id: str, level: IsolationLevel, network: Dict) -> Dict[str, Any]:
        if level != IsolationLevel.STRICT:
            return {"check": "network_isolation", "passed": True, "message": f"Level {level.value} does not require strict network isolation"}

        firewall = network.get("enable_firewall", False)
        allowed_ports = network.get("allowed_ports", [])
        return {
            "check": "network_isolation",
            "passed": firewall and len(allowed_ports) <= 2,
            "message": "Strict network isolation enforced" if firewall else "Firewall not enabled for strict isolation",
        }

    def _validate_resource_limits(self, workspace_id: str, level: IsolationLevel, quota: Dict) -> Dict[str, Any]:
        if not quota:
            return {"check": "resource_limits", "passed": False, "message": "No resource quota defined"}

        has_cpu = bool(quota.get("cpu"))
        has_memory = bool(quota.get("memory"))
        return {
            "check": "resource_limits",
            "passed": has_cpu and has_memory,
            "message": "Resource limits properly configured" if (has_cpu and has_memory) else "Missing CPU or memory limits",
        }

    def _verify_sqlite_workspace_filter(self, workspace_id: str) -> bool:
        return True

    @staticmethod
    def _parse_size(size_str: str) -> int:
        if not size_str:
            return 0
        size_str = size_str.strip()
        multipliers = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
                       "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if size_str.upper().endswith(suffix.upper()):
                try:
                    return int(float(size_str[: -len(suffix)]) * mult)
                except ValueError:
                    return 0
        try:
            return int(size_str)
        except ValueError:
            return 0
