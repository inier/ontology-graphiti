"""菜单配置服务 — RBAC 三级菜单树 + 角色权限"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..storage import Storage

logger = logging.getLogger(__name__)

# ── 内置全局角色（与 JWT payload["role"] / GlobalRole 枚举对齐） ──
# menu_config 的角色权限以 global_role 字符串为 role_id（与侧边栏 tree 接口
# _user_role_ids() 的提取键一致），而非 roles 模块的自定义角色 id（r_xxx）。
GLOBAL_ROLES: List[Dict[str, str]] = [
    {"id": "admin", "name": "系统管理员", "description": "全部菜单权限（无需分配）"},
    {"id": "system_admin", "name": "系统管理员(内部)", "description": "系统级管理员"},
    {"id": "project_owner", "name": "项目负责人", "description": "项目级管理者"},
    {"id": "team_leader", "name": "团队负责人", "description": "团队级管理者"},
    {"id": "analyst", "name": "分析师", "description": "数据分析与决策推演"},
    {"id": "operator", "name": "操作员", "description": "日常业务操作"},
    {"id": "commander", "name": "指挥官", "description": "决策指挥"},
    {"id": "observer", "name": "观察者", "description": "只读查看"},
    {"id": "member", "name": "成员", "description": "常规成员"},
    {"id": "guest", "name": "访客", "description": "受限访问"},
    {"id": "schema_auditor", "name": "语义审计员", "description": "本体/语义配置审计"},
]

# ── 审计工具（懒加载 + 容错） ──
def _menu_audit(action: str, *, result_status: str = "success",
                result_message: str = "", resource: str = None,
                details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="platform_menu",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class MenuConfigService:
    """菜单配置业务逻辑（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._storage = Storage()
        self._initialized = True

    # ── 菜单项 CRUD ──

    def list_items(
        self, active_only: bool = True, menu_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = self._storage.list_menu_items(active_only=active_only, menu_type=menu_type)
        return {"items": items, "total": len(items)}

    def get_item(self, item_id: str) -> Dict[str, Any]:
        item = self._storage.get_menu_item(item_id)
        if not item:
            return {"status": "error", "message": "菜单项不存在"}
        return item

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        code = data.get("code") or self._auto_code(data)
        # 校验 code 唯一
        if self._storage.get_menu_item_by_code(code):
            _menu_audit(
                action="menu_create",
                result_status="failure",
                result_message=f"权限码 '{code}' 已存在"[:200],
                resource="",
                details={"code": code, "name_len": len(data.get("name", ""))},
            )
            return {"status": "error", "message": f"权限码 '{code}' 已存在"}
        item = {
            "id": data.get("id") or uuid.uuid4().hex[:12],
            "parent_id": data.get("parent_id") or None,
            "name": data["name"],
            "code": code,
            "menu_type": data.get("menu_type", "menu"),
            "link_type": data.get("link_type", "internal"),
            "path": data.get("path"),
            "url": data.get("url"),
            "icon": data.get("icon", "AppstoreOutlined"),
            "sort_order": data.get("sort_order", 0),
            "is_active": data.get("is_active", True),
            "is_visible": data.get("is_visible", True),
            "description": data.get("description", ""),
            "created_at": now,
            "updated_at": now,
        }
        result = self._storage.save_menu_item(item)
        _menu_audit(
            action="menu_create",
            result_status="success",
            resource=item["id"],
            details={
                "menu_id": item["id"],
                "menu_type": item.get("menu_type", ""),
                "code": code,
                "name_len": len(item.get("name", "")),
            },
        )
        return result

    def update_item(self, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._storage.get_menu_item(item_id)
        if not existing:
            _menu_audit(
                action="menu_update",
                result_status="failure",
                result_message="Menu not found",
                resource=item_id,
                details={"menu_id": item_id},
            )
            return {"status": "error", "message": "菜单项不存在"}
        # 如果更新 code，检查唯一性
        new_code = data.get("code")
        if new_code and new_code != existing["code"]:
            dup = self._storage.get_menu_item_by_code(new_code)
            if dup and dup["id"] != item_id:
                _menu_audit(
                    action="menu_update",
                    result_status="failure",
                    result_message=f"Duplicate code: {new_code}"[:200],
                    resource=item_id,
                    details={"menu_id": item_id},
                )
                return {"status": "error", "message": f"权限码 '{new_code}' 已存在"}
        changed = []
        for key in ("parent_id", "name", "code", "menu_type", "link_type",
                     "path", "url", "icon", "sort_order", "is_active",
                     "is_visible", "description"):
            if key in data:
                existing[key] = data[key]
                changed.append(key)
        existing["updated_at"] = datetime.now().isoformat()
        result = self._storage.save_menu_item(existing)
        _menu_audit(
            action="menu_update",
            result_status="success",
            resource=item_id,
            details={
                "menu_id": item_id,
                "changed_fields": changed,
                "field_count": len(changed),
            },
        )
        return result

    def delete_item(self, item_id: str) -> Dict[str, Any]:
        deleted = self._storage.delete_menu_item(item_id)
        _menu_audit(
            action="menu_delete",
            result_status="success" if deleted else "failure",
            result_message="" if deleted else "Menu not found",
            resource=item_id,
            details={"menu_id": item_id},
        )
        if deleted:
            return {"status": "success", "message": "已删除"}
        return {"status": "error", "message": "菜单项不存在"}

    # ── 树形结构 ──

    def get_tree(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """返回完整菜单树（嵌套 children）"""
        items = self._storage.list_menu_items(active_only=active_only)
        return self._build_tree(items)

    def get_user_menu_tree(
        self, role_ids: List[str], is_admin: bool = False,
    ) -> List[Dict[str, Any]]:
        """根据用户角色返回可见菜单树"""
        if is_admin:
            items = self._storage.list_menu_items(active_only=True)
        else:
            items = self._storage.get_menus_for_roles(role_ids, active_only=True)
            items = self._ensure_parent_directories(items)
        return self._build_tree(items)

    def _ensure_parent_directories(
        self, items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """补全菜单项缺失的父目录节点，确保树形结构完整。

        当角色被授予某个子菜单但未显式被授予其父目录时，
        仍需要把父目录（以及递归祖先目录）补回来，否则 _build_tree
        会把子菜单错误地提升为顶级菜单。
        """
        ids = {i["id"] for i in items}
        missing_ids = set()
        for item in items:
            pid = item.get("parent_id")
            if pid and pid not in ids:
                missing_ids.add(pid)
        if not missing_ids:
            return items
        parents = self._storage.list_menu_items_by_ids(
            list(missing_ids), active_only=True
        )
        # 过滤掉非 directory 的父节点（防御：防止越级授权）
        parents = [p for p in parents if p.get("menu_type") == "directory"]
        return items + self._ensure_parent_directories(parents)

    def _build_tree(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """扁平列表 → 树形结构"""
        item_map: Dict[str, Dict] = {}
        roots: List[Dict] = []

        for item in items:
            node = {**item, "children": []}
            item_map[item["id"]] = node

        for item in items:
            node = item_map[item["id"]]
            pid = item.get("parent_id")
            if pid and pid in item_map:
                item_map[pid]["children"].append(node)
            else:
                roots.append(node)

        return roots

    # ── 角色权限 ──

    def set_role_menus(self, role_id: str, menu_item_ids: List[str]) -> Dict[str, Any]:
        self._storage.set_role_menus(role_id, menu_item_ids)
        return {"status": "success", "role_id": role_id, "count": len(menu_item_ids)}

    def get_role_menus(self, role_id: str) -> Dict[str, Any]:
        menu_ids = self._storage.get_role_menu_ids(role_id)
        items = self._storage.list_menu_items_by_ids(menu_ids, active_only=False)
        return {"role_id": role_id, "menu_ids": menu_ids, "items": items}

    def get_menu_roles(self, menu_item_id: str) -> Dict[str, Any]:
        role_ids = self._storage.get_menu_role_ids(menu_item_id)
        return {"menu_item_id": menu_item_id, "role_ids": role_ids}

    # ── 内置全局角色（与 JWT role 对齐的菜单权限维度） ──

    def list_global_roles(self) -> Dict[str, Any]:
        """返回内置全局角色列表（供 /menu-config 页面角色下拉使用）。

        与侧边栏 tree 接口 _user_role_ids() 提取的 role 值一一对应，
        解决"配置页角色(roles 表 r_xxx) ≠ JWT role(global_role)"导致的
        菜单权限配置不生效问题。
        """
        return {"roles": GLOBAL_ROLES, "total": len(GLOBAL_ROLES)}

    # ── 工具方法 ──

    def _auto_code(self, data: Dict[str, Any]) -> str:
        """自动生成权限码"""
        menu_type = data.get("menu_type", "menu")
        name = data.get("name", "unnamed")
        prefix = {"directory": "dir", "menu": "menu", "action": "act"}.get(menu_type, "menu")
        slug = name.lower().replace(" ", "_")[:30]
        return f"{prefix}:{slug}:{uuid.uuid4().hex[:6]}"

    # ── 四步法种子数据初始化（Iter 1 / MENU_REFACTOR_PLAN.md） ──

    def init_default_menu(self) -> Dict[str, Any]:
        """幂等初始化四步法默认菜单树。

        - 首次调用：写入 54 个菜单项（6 目录 + 48 菜单/子目录）
          （Iter 5 后：演本体含决策智能 /decisions，ADR-076）
        - 后续调用：跳过已存在的 code，仅写入新增项
        - 不覆盖用户自定义菜单（通过 code 唯一性判断）
        - 同步为内置全局角色（除 admin）写入默认 role_menus（幂等，仅当角色无任何分配）

        Returns:
            {"status": "success", "created": N, "skipped": M, "total": T}
        """
        from ..seeds.seed_four_steps import get_four_steps_seed_data

        seed_items = get_four_steps_seed_data()
        created = 0
        skipped = 0
        for item in seed_items:
            existing = self._storage.get_menu_item_by_code(item["code"])
            if existing:
                skipped += 1
                continue
            item["created_at"] = datetime.now().isoformat()
            item["updated_at"] = item["created_at"]
            self._storage.save_menu_item(item)
            created += 1
        role_grants = self._ensure_default_role_menus()
        _menu_audit(
            action="menu_init_default",
            result_status="success",
            resource="default_menu",
            details={"created": created, "skipped": skipped,
                     "total_seed": len(seed_items), "role_grants": role_grants},
        )
        return {
            "status": "success",
            "created": created,
            "skipped": skipped,
            "total": len(seed_items),
            "role_grants": role_grants,
        }

    def _ensure_default_role_menus(self) -> int:
        """为内置全局角色写入默认菜单权限（幂等：仅当角色尚无任何分配时）。

        设计说明：menu_config 的角色权限与 JWT role（global_role 字符串）对齐，
        配置页必须用本服务的全局角色 id 保存 role_menus，侧边栏 tree 接口才能
        命中。非 admin 角色默认放权（全部可见菜单），管理员可在 /menu-config
        页面收紧。返回实际写入的角色数。
        """
        granted = 0
        try:
            all_ids = [i["id"] for i in
                       self._storage.list_menu_items(active_only=True)]
        except Exception:  # 存储不可用时不阻断种子初始化
            logger.warning("_ensure_default_role_menus: 读取菜单列表失败", exc_info=True)
            return 0
        for role in GLOBAL_ROLES:
            role_id = role["id"]
            if role_id == "admin":
                continue  # admin 由 is_admin 短路，无需 role_menus
            try:
                if self._storage.get_role_menu_ids(role_id):
                    continue  # 已有显式配置，不覆盖
                self._storage.set_role_menus(role_id, all_ids)
                granted += 1
            except Exception:
                logger.warning("_ensure_default_role_menus: 角色 %s 写入失败", role_id,
                               exc_info=True)
        return granted
