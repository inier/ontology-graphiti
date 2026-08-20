/**
 * 角色类型（对齐后端 biz/platform/roles/api/schemas.RoleType）
 * 覆盖全部 11 个全局角色 + 2 个遗留角色（director/intelligence）。
 */
export type RoleType =
  | 'admin'
  | 'system_admin'
  | 'project_owner'
  | 'team_leader'
  | 'member'
  | 'guest'
  | 'commander'
  | 'analyst'
  | 'operator'
  | 'observer'
  | 'schema_auditor'
  | 'director'
  | 'intelligence';

export interface Permission {
  id: string;
  name: string;
  description: string;
  scope: 'system' | 'project' | 'resource' | 'data';
  actions: string[];
}

export interface Role {
  id: string;
  name: string;
  description: string;
  role_type: RoleType;
  permissions: Permission[];
  created_at: string;
  updated_at: string;
}

export interface RoleCreate {
  name: string;
  description: string;
  role_type: RoleType;
  permissions: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  role_type?: RoleType;
  permissions?: string[];
}
