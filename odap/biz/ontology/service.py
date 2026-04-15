"""
本体管理模块
包含：
1. 本体定义的导入导出
2. 本体版本管理
3. 策略执行模拟
4. 策略版本回退
"""

import sys
import os
import json
import datetime
import shutil

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.biz.ontology.schema.battlefield import ENTITY_TYPES, ROLES, BATTLEFIELD_CONFIG

class OntologyManager:
    """
    本体管理器
    """
    
    def __init__(self, ontology_dir="ontology/versions", policy_dir="core/policies"):
        """
        初始化本体管理器

        Args:
            ontology_dir: 本体版本存储目录
            policy_dir: 策略版本存储目录
        """
        self.ontology_dir = ontology_dir
        self.policy_dir = policy_dir
        self.current_ontology = {
            "entity_types": ENTITY_TYPES,
            "roles": ROLES,
            "battlefield_config": BATTLEFIELD_CONFIG
        }
        self.policy_history = []  # 策略执行历史
        self._ensure_dir()
        print("本体管理器初始化成功")

    def _ensure_dir(self):
        """
        确保本体版本目录和策略目录存在
        """
        if not os.path.exists(self.ontology_dir):
            os.makedirs(self.ontology_dir)
            print(f"创建本体版本目录: {self.ontology_dir}")

        if not os.path.exists(self.policy_dir):
            os.makedirs(self.policy_dir)
            print(f"创建策略版本目录: {self.policy_dir}")

    def export_ontology(self, version=None, description=""):
        """
        导出本体

        Args:
            version: 版本号
            description: 版本描述

        Returns:
            导出文件路径
        """
        if not version:
            version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        export_data = {
            "version": version,
            "description": description,
            "timestamp": datetime.datetime.now().isoformat(),
            "ontology": self.current_ontology
        }

        export_file = os.path.join(self.ontology_dir, f"ontology_{version}.json")

        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"本体已导出到: {export_file}")
        print(f"版本: {version}")
        print(f"描述: {description}")

        self._update_version_record(version, description)

        return export_file

    def import_ontology(self, import_file):
        """
        导入本体

        Args:
            import_file: 导入文件路径

        Returns:
            导入是否成功
        """
        if not os.path.exists(import_file):
            print(f"导入文件不存在: {import_file}")
            return False

        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            if "ontology" not in import_data:
                print("导入文件格式错误: 缺少ontology字段")
                return False

            ontology_data = import_data["ontology"]
            self.current_ontology = ontology_data

            version = import_data.get("version", "unknown")
            description = import_data.get("description", "")

            print(f"本体导入成功")
            print(f"版本: {version}")
            print(f"描述: {description}")

            return True
        except Exception as e:
            print(f"导入本体失败: {e}")
            return False

    def list_versions(self):
        """
        列出所有本体版本

        Returns:
            版本列表
        """
        versions = []

        for filename in os.listdir(self.ontology_dir):
            if filename.startswith("ontology_") and filename.endswith(".json"):
                version = filename.replace("ontology_", "").replace(".json", "")
                file_path = os.path.join(self.ontology_dir, filename)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    versions.append({
                        "version": version,
                        "description": data.get("description", ""),
                        "timestamp": data.get("timestamp", ""),
                        "file": filename
                    })
                except Exception as e:
                    print(f"读取版本文件失败 {filename}: {e}")

        versions.sort(key=lambda x: x["timestamp"], reverse=True)

        print("本体版本列表:")
        print("====================================")
        for i, v in enumerate(versions, 1):
            print(f"{i}. 版本: {v['version']}")
            print(f"   描述: {v['description']}")
            print(f"   时间: {v['timestamp']}")
            print(f"   文件: {v['file']}")
            print()
        print("====================================")

        return versions

    def rollback_version(self, version):
        """
        回滚到指定版本

        Args:
            version: 版本号

        Returns:
            回滚是否成功
        """
        import_file = os.path.join(self.ontology_dir, f"ontology_{version}.json")

        if not os.path.exists(import_file):
            print(f"版本文件不存在: {import_file}")
            return False

        backup_version = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_backup"
        self.export_ontology(version=backup_version, description="回滚前备份")

        success = self.import_ontology(import_file)

        if success:
            print(f"成功回滚到版本: {version}")
        else:
            print(f"回滚失败")

        return success

    def _update_version_record(self, version, description):
        """
        更新版本记录

        Args:
            version: 版本号
            description: 版本描述
        """
        record_file = os.path.join(self.ontology_dir, "version_record.json")

        if os.path.exists(record_file):
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        else:
            records = []

        records.append({
            "version": version,
            "description": description,
            "timestamp": datetime.datetime.now().isoformat()
        })

        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def get_current_ontology(self):
        """
        获取当前本体

        Returns:
            当前本体
        """
        return self.current_ontology

    def update_ontology(self, entity_types=None, roles=None, battlefield_config=None):
        """
        更新本体

        Args:
            entity_types: 实体类型
            roles: 角色
            battlefield_config: 战场配置
        """
        if entity_types:
            self.current_ontology["entity_types"] = entity_types

        if roles:
            self.current_ontology["roles"] = roles

        if battlefield_config:
            self.current_ontology["battlefield_config"] = battlefield_config

        print("本体已更新")

    def export_policy(self, policy_name, version=None, description=""):
        """
        导出策略

        Args:
            policy_name: 策略名称
            version: 版本号
            description: 版本描述

        Returns:
            导出文件路径
        """
        if not version:
            version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        policy_data = {
            "policy_name": policy_name,
            "version": version,
            "description": description,
            "timestamp": datetime.datetime.now().isoformat(),
            "roles": self.current_ontology.get("roles", {}),
            "battlefield_config": self.current_ontology.get("battlefield_config", {})
        }

        export_file = os.path.join(self.policy_dir, f"policy_{policy_name}_{version}.json")

        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(policy_data, f, ensure_ascii=False, indent=2)

        print(f"策略已导出到: {export_file}")
        print(f"策略名称: {policy_name}")
        print(f"版本: {version}")
        print(f"描述: {description}")

        self._update_policy_record(policy_name, version, description)

        return export_file

    def import_policy(self, policy_file):
        """
        导入策略

        Args:
            policy_file: 导入文件路径

        Returns:
            导入是否成功
        """
        if not os.path.exists(policy_file):
            print(f"导入文件不存在: {policy_file}")
            return False

        try:
            with open(policy_file, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)

            policy_name = policy_data.get("policy_name", "unknown")
            version = policy_data.get("version", "unknown")
            description = policy_data.get("description", "")

            print(f"策略导入成功")
            print(f"策略名称: {policy_name}")
            print(f"版本: {version}")
            print(f"描述: {description}")

            return True
        except Exception as e:
            print(f"导入策略失败: {e}")
            return False

    def list_policies(self):
        """
        列出所有策略版本

        Returns:
            策略列表
        """
        policies = []

        for filename in os.listdir(self.policy_dir):
            if filename.startswith("policy_") and filename.endswith(".json"):
                parts = filename.replace("policy_", "").replace(".json", "").split("_")
                policy_name = parts[0] if parts else "unknown"
                version = "_".join(parts[1:]) if len(parts) > 1 else "unknown"
                file_path = os.path.join(self.policy_dir, filename)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    policies.append({
                        "policy_name": data.get("policy_name", policy_name),
                        "version": data.get("version", version),
                        "description": data.get("description", ""),
                        "timestamp": data.get("timestamp", ""),
                        "file": filename
                    })
                except Exception as e:
                    print(f"读取策略文件失败 {filename}: {e}")

        policies.sort(key=lambda x: x["timestamp"], reverse=True)

        print("策略版本列表:")
        print("====================================")
        for i, p in enumerate(policies, 1):
            print(f"{i}. 策略名称: {p['policy_name']}")
            print(f"   版本: {p['version']}")
            print(f"   描述: {p['description']}")
            print(f"   时间: {p['timestamp']}")
            print(f"   文件: {p['file']}")
            print()
        print("====================================")

        return policies

    def rollback_policy(self, policy_name, version):
        """
        回滚策略到指定版本

        Args:
            policy_name: 策略名称
            version: 版本号

        Returns:
            回滚是否成功
        """
        import_file = os.path.join(self.policy_dir, f"policy_{policy_name}_{version}.json")

        if not os.path.exists(import_file):
            print(f"策略版本文件不存在: {import_file}")
            return False

        backup_version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.export_policy(policy_name, version=backup_version, description="策略回滚前备份")

        success = self.import_policy(import_file)

        if success:
            print(f"成功回滚策略 {policy_name} 到版本: {version}")
        else:
            print(f"策略回滚失败")

        return success

    def _update_policy_record(self, policy_name, version, description):
        """
        更新策略记录

        Args:
            policy_name: 策略名称
            version: 版本号
            description: 版本描述
        """
        record_file = os.path.join(self.policy_dir, "policy_record.json")

        if os.path.exists(record_file):
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        else:
            records = []

        records.append({
            "policy_name": policy_name,
            "version": version,
            "description": description,
            "timestamp": datetime.datetime.now().isoformat()
        })

        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def simulate_policy_execution(self, role, action, target_type=None):
        """
        模拟策略执行

        Args:
            role: 角色
            action: 操作
            target_type: 目标类型

        Returns:
            模拟结果
        """
        result = {
            "role": role,
            "action": action,
            "target_type": target_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "allowed": True,
            "reason": ""
        }

        roles = self.current_ontology.get("roles", {})

        if role not in roles:
            result["allowed"] = False
            result["reason"] = f"角色 {role} 不存在"
        else:
            role_config = roles[role]
            permissions = role_config.get("permissions", [])
            restrictions = role_config.get("restrictions", [])

            action_permission_map = {
                "view_intelligence": ["view_intelligence"],
                "request_support": ["request_support"],
                "command_units": ["command_units"],
                "authorize_attacks": ["authorize_attacks"],
                "approve_missions": ["approve_missions"],
                "analyze_data": ["analyze_data"],
                "generate_reports": ["generate_reports"],
                "attack": ["authorize_attacks"],
                "command": ["command_units"]
            }

            required_permissions = action_permission_map.get(action, [])

            for perm in required_permissions:
                if perm not in permissions:
                    result["allowed"] = False
                    result["reason"] = f"角色 {role} 缺少必要权限: {perm}"
                    break

            for restriction in restrictions:
                if restriction == "cannot_attack" and action == "attack":
                    result["allowed"] = False
                    result["reason"] = f"角色 {role} 被限制执行攻击操作"
                    break
                elif restriction == "cannot_command" and action == "command":
                    result["allowed"] = False
                    result["reason"] = f"角色 {role} 被限制执行指挥操作"
                    break
                elif restriction == "cannot_attack_civilian_infrastructure" and target_type == "CivilianInfrastructure":
                    result["allowed"] = False
                    result["reason"] = f"角色 {role} 被限制攻击民用设施"
                    break

        if result["allowed"]:
            result["reason"] = f"角色 {role} 有权执行 {action} 操作"

        self.policy_history.append(result)

        print("策略执行模拟:")
        print("====================================")
        print(f"角色: {result['role']}")
        print(f"操作: {result['action']}")
        print(f"目标类型: {result['target_type']}")
        print(f"结果: {'允许' if result['allowed'] else '拒绝'}")
        print(f"原因: {result['reason']}")
        print(f"时间: {result['timestamp']}")
        print("====================================")

        return result

    def get_policy_history(self):
        """
        获取策略执行历史

        Returns:
            策略执行历史列表
        """
        return self.policy_history

    def clear_policy_history(self):
        """
        清除策略执行历史
        """
        self.policy_history = []
        print("策略执行历史已清除")

if __name__ == "__main__":
    manager = OntologyManager()

    manager.export_ontology(description="初始本体")
    manager.list_versions()

    manager.export_policy("default", description="默认策略")
    manager.list_policies()

    print("\n策略执行模拟:")
    manager.simulate_policy_execution("pilot", "attack")
    manager.simulate_policy_execution("commander", "attack")
    manager.simulate_policy_execution("commander", "attack", "CivilianInfrastructure")

    print("\n策略执行历史:")
    for h in manager.get_policy_history():
        print(f"- {h['timestamp']}: {h['role']} -> {h['action']} ({h['allowed']})")