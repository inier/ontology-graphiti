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
  role_type: 'system_admin' | 'project_owner' | 'team_leader' | 'member' | 'guest';
  permissions: Permission[];
  created_at: string;
  updated_at: string;
}

export interface RoleCreate {
  name: string;
  description: string;
  role_type: 'system_admin' | 'project_owner' | 'team_leader' | 'member' | 'guest';
  permissions: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  role_type?: 'system_admin' | 'project_owner' | 'team_leader' | 'member' | 'guest';
  permissions?: string[];
}