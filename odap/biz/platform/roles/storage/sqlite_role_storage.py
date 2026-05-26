"""SQLite存储实现 - 角色管理"""

import sqlite3
import json
import os
import uuid
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..api.schemas import Role, RoleType, Permission, PermissionScope


DEFAULT_DB_DIR = os.path.join(os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "roles.db")


class SQLiteRoleStorage:
    """角色管理的SQLite存储实现"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建权限表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                scope TEXT NOT NULL,
                actions TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # 创建角色表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                role_type TEXT NOT NULL,
                permissions TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 创建角色权限关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id TEXT NOT NULL,
                permission_id TEXT NOT NULL,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id),
                FOREIGN KEY (permission_id) REFERENCES permissions(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_skills (
                role_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (role_id, skill_id),
                FOREIGN KEY (role_id) REFERENCES roles(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_policies (
                role_id TEXT NOT NULL,
                policy_id TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (role_id, policy_id),
                FOREIGN KEY (role_id) REFERENCES roles(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_roles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                workspace_id TEXT,
                bound_at TEXT NOT NULL,
                bound_by TEXT NOT NULL DEFAULT 'system',
                UNIQUE(user_id, role_id, workspace_id),
                FOREIGN KEY (role_id) REFERENCES roles(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # 初始化默认权限数据
        self._init_default_permissions()
        self._init_default_roles()
    
    def _serialize_json(self, data: Any) -> str:
        """序列化JSON数据"""
        return json.dumps(data, ensure_ascii=False)
    
    def _deserialize_json(self, data: str) -> Any:
        """反序列化JSON数据"""
        if not data:
            return None
        try:
            return json.loads(data)
        except:
            return None
    
    def _init_default_permissions(self):
        """初始化默认权限数据"""
        default_permissions = [
            {
                "id": "p1",
                "name": "系统管理",
                "description": "系统级管理权限",
                "scope": PermissionScope.SYSTEM,
                "actions": ["*"]
            },
            {
                "id": "p2",
                "name": "项目管理",
                "description": "项目级管理权限",
                "scope": PermissionScope.PROJECT,
                "actions": ["read", "write", "delete"]
            },
            {
                "id": "p3",
                "name": "团队管理",
                "description": "团队级管理权限",
                "scope": PermissionScope.PROJECT,
                "actions": ["read", "update"]
            },
            {
                "id": "p4",
                "name": "资源访问",
                "description": "资源级访问权限",
                "scope": PermissionScope.RESOURCE,
                "actions": ["read"]
            },
            {
                "id": "p5",
                "name": "有限访问",
                "description": "有限的资源访问权限",
                "scope": PermissionScope.RESOURCE,
                "actions": ["limited_read"]
            }
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for perm in default_permissions:
            # 检查权限是否已存在
            cursor.execute('SELECT id FROM permissions WHERE id = ?', (perm['id'],))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO permissions (id, name, description, scope, actions, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    perm['id'],
                    perm['name'],
                    perm['description'],
                    perm['scope'].value,
                    self._serialize_json(perm['actions']),
                    datetime.now().isoformat()
                ))
        
        conn.commit()
        conn.close()
    
    def _init_default_roles(self):
        """初始化默认角色数据"""
        default_roles = [
            {
                "id": "1",
                "name": "系统管理员",
                "description": "拥有系统所有权限",
                "role_type": RoleType.SYSTEM_ADMIN,
                "permissions": ["p1"]
            },
            {
                "id": "2",
                "name": "项目所有者",
                "description": "项目级管理权限",
                "role_type": RoleType.PROJECT_OWNER,
                "permissions": ["p2"]
            },
            {
                "id": "3",
                "name": "团队领导",
                "description": "团队级管理权限",
                "role_type": RoleType.TEAM_LEADER,
                "permissions": ["p3"]
            },
            {
                "id": "4",
                "name": "成员",
                "description": "普通成员权限",
                "role_type": RoleType.MEMBER,
                "permissions": ["p4"]
            },
            {
                "id": "5",
                "name": "访客",
                "description": "访客权限",
                "role_type": RoleType.GUEST,
                "permissions": ["p5"]
            }
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for role_data in default_roles:
            # 检查角色是否已存在
            cursor.execute('SELECT id FROM roles WHERE id = ?', (role_data['id'],))
            if not cursor.fetchone():
                # 插入角色
                cursor.execute('''
                    INSERT INTO roles (id, name, description, role_type, permissions, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    role_data['id'],
                    role_data['name'],
                    role_data['description'],
                    role_data['role_type'].value,
                    self._serialize_json(role_data['permissions']),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                # 插入角色权限关联
                for perm_id in role_data['permissions']:
                    cursor.execute('''
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                        VALUES (?, ?)
                    ''', (role_data['id'], perm_id))
        
        conn.commit()
        conn.close()
    
    # 权限相关操作
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """获取权限"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM permissions WHERE id = ?', (permission_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return Permission(
            id=row[0],
            name=row[1],
            description=row[2],
            scope=PermissionScope(row[3]),
            actions=self._deserialize_json(row[4]) or []
        )
    
    def list_permissions(self) -> List[Permission]:
        """列出所有权限"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM permissions')
        rows = cursor.fetchall()
        
        conn.close()
        
        permissions = []
        for row in rows:
            permissions.append(Permission(
                id=row[0],
                name=row[1],
                description=row[2],
                scope=PermissionScope(row[3]),
                actions=self._deserialize_json(row[4]) or []
            ))
        
        return permissions
    
    # 角色相关操作
    def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取角色基本信息
        cursor.execute('SELECT * FROM roles WHERE id = ?', (role_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # 获取角色的权限
        cursor.execute('''
            SELECT p.* FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = ?
        ''', (role_id,))
        perm_rows = cursor.fetchall()
        
        conn.close()
        
        permissions = []
        for perm_row in perm_rows:
            permissions.append(Permission(
                id=perm_row[0],
                name=perm_row[1],
                description=perm_row[2],
                scope=PermissionScope(perm_row[3]),
                actions=self._deserialize_json(perm_row[4]) or []
            ))
        
        return Role(
            id=row[0],
            name=row[1],
            description=row[2],
            role_type=RoleType(row[3]),
            permissions=permissions,
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6])
        )
    
    def list_roles(self) -> List[Role]:
        """列出所有角色"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM roles')
        rows = cursor.fetchall()
        
        conn.close()
        
        roles = []
        for row in rows:
            role = self.get_role(row[0])
            if role:
                roles.append(role)
        
        return roles
    
    def create_role(self, role_data: Dict[str, Any]) -> Role:
        """创建角色"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 生成角色ID (使用UUID避免冲突)
        new_id = f"r_{uuid.uuid4().hex[:12]}"
        
        # 插入角色
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO roles (id, name, description, role_type, permissions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_id,
            role_data['name'],
            role_data['description'],
            role_data['role_type'].value,
            self._serialize_json(role_data['permissions']),
            now,
            now
        ))
        
        # 插入角色权限关联
        for perm_id in role_data['permissions']:
            cursor.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (new_id, perm_id))
        
        conn.commit()
        conn.close()
        
        return self.get_role(new_id)
    
    def update_role(self, role_id: str, role_data: Dict[str, Any]) -> Role:
        """更新角色"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新角色基本信息
        update_fields = []
        update_values = []
        
        if 'name' in role_data:
            update_fields.append('name = ?')
            update_values.append(role_data['name'])
        if 'description' in role_data:
            update_fields.append('description = ?')
            update_values.append(role_data['description'])
        if 'role_type' in role_data:
            update_fields.append('role_type = ?')
            update_values.append(role_data['role_type'].value)
        if 'permissions' in role_data:
            update_fields.append('permissions = ?')
            update_values.append(self._serialize_json(role_data['permissions']))
        
        update_fields.append('updated_at = ?')
        update_values.append(datetime.now().isoformat())
        update_values.append(role_id)
        
        query = f"UPDATE roles SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, update_values)
        
        # 更新角色权限关联
        if 'permissions' in role_data:
            # 删除旧的权限关联
            cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
            # 插入新的权限关联
            for perm_id in role_data['permissions']:
                cursor.execute('''
                    INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                ''', (role_id, perm_id))
        
        conn.commit()
        conn.close()
        
        return self.get_role(role_id)
    
    def delete_role(self, role_id: str) -> bool:
        """删除角色"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM user_roles WHERE role_id = ?', (role_id,))
        cursor.execute('DELETE FROM role_skills WHERE role_id = ?', (role_id,))
        cursor.execute('DELETE FROM role_policies WHERE role_id = ?', (role_id,))
        cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
        cursor.execute('DELETE FROM roles WHERE id = ?', (role_id,))
        affected_rows = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return affected_rows > 0

    def bind_skill(self, role_id: str, skill_id: str, enabled: bool = True) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO role_skills (role_id, skill_id, enabled)
            VALUES (?, ?, ?)
        ''', (role_id, skill_id, 1 if enabled else 0))
        conn.commit()
        conn.close()
        return True

    def unbind_skill(self, role_id: str, skill_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM role_skills WHERE role_id = ? AND skill_id = ?', (role_id, skill_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_role_skills(self, role_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT skill_id, enabled FROM role_skills WHERE role_id = ?', (role_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"skill_id": r[0], "enabled": bool(r[1])} for r in rows]

    def bind_policy(self, role_id: str, policy_id: str, priority: int = 0, enabled: bool = True) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO role_policies (role_id, policy_id, priority, enabled)
            VALUES (?, ?, ?, ?)
        ''', (role_id, policy_id, priority, 1 if enabled else 0))
        conn.commit()
        conn.close()
        return True

    def unbind_policy(self, role_id: str, policy_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM role_policies WHERE role_id = ? AND policy_id = ?', (role_id, policy_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_role_policies(self, role_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT policy_id, priority, enabled FROM role_policies WHERE role_id = ? ORDER BY priority DESC', (role_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"policy_id": r[0], "priority": r[1], "enabled": bool(r[2])} for r in rows]

    def save_role(self, role: Role) -> Role:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO roles (id, name, description, role_type, permissions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            role.id,
            role.name,
            role.description,
            role.role_type.value if hasattr(role.role_type, 'value') else role.role_type,
            self._serialize_json([p.id for p in role.permissions]) if role.permissions else self._serialize_json([]),
            role.created_at.isoformat() if hasattr(role.created_at, 'isoformat') else role.created_at,
            role.updated_at.isoformat() if hasattr(role.updated_at, 'isoformat') else role.updated_at,
        ))
        cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role.id,))
        for perm in role.permissions:
            cursor.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role.id, perm.id))
        conn.commit()
        conn.close()
        return role

    def assign_role_to_user(self, role_id: str, user_id: str, workspace_id: Optional[str] = None, bound_by: str = 'system') -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if workspace_id is not None:
            cursor.execute('SELECT id FROM user_roles WHERE user_id = ? AND role_id = ? AND workspace_id = ?', (user_id, role_id, workspace_id))
        else:
            cursor.execute('SELECT id FROM user_roles WHERE user_id = ? AND role_id = ? AND workspace_id IS NULL', (user_id, role_id))
        if cursor.fetchone():
            conn.close()
            return False
        binding_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO user_roles (id, user_id, role_id, workspace_id, bound_at, bound_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (binding_id, user_id, role_id, workspace_id, now, bound_by))
        conn.commit()
        conn.close()
        return True

    def revoke_role_from_user(self, role_id: str, user_id: str, workspace_id: Optional[str] = None) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if workspace_id is not None:
            cursor.execute('DELETE FROM user_roles WHERE user_id = ? AND role_id = ? AND workspace_id = ?', (user_id, role_id, workspace_id))
        else:
            cursor.execute('DELETE FROM user_roles WHERE user_id = ? AND role_id = ? AND workspace_id IS NULL', (user_id, role_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_user_roles(self, user_id: str) -> List[Role]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT role_id FROM user_roles WHERE user_id = ?', (user_id,))
        role_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        roles = []
        for rid in role_ids:
            role = self.get_role(rid)
            if role:
                roles.append(role)
        return roles

    def get_user_roles_in_workspace(self, user_id: str, workspace_id: str) -> List[Role]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT role_id FROM user_roles WHERE user_id = ? AND workspace_id = ?', (user_id, workspace_id))
        role_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        roles = []
        for rid in role_ids:
            role = self.get_role(rid)
            if role:
                roles.append(role)
        return roles