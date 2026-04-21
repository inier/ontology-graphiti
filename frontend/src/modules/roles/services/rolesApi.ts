import { API_BASE } from '../../../config';
import type { Role, RoleCreate, RoleUpdate, Permission } from '../types';

export async function listRoles(): Promise<Role[]> {
  const response = await fetch(`${API_BASE}/api/roles`);
  if (!response.ok) {
    throw new Error('获取角色列表失败');
  }
  return response.json();
}

export async function getRole(roleId: string): Promise<Role> {
  const response = await fetch(`${API_BASE}/api/roles/${roleId}`);
  if (!response.ok) {
    throw new Error('获取角色详情失败');
  }
  return response.json();
}

export async function createRole(role: RoleCreate): Promise<Role> {
  const response = await fetch(`${API_BASE}/api/roles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(role),
  });
  if (!response.ok) {
    throw new Error('创建角色失败');
  }
  return response.json();
}

export async function updateRole(roleId: string, role: RoleUpdate): Promise<Role> {
  const response = await fetch(`${API_BASE}/api/roles/${roleId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(role),
  });
  if (!response.ok) {
    throw new Error('更新角色失败');
  }
  return response.json();
}

export async function deleteRole(roleId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/roles/${roleId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('删除角色失败');
  }
}

export async function listPermissions(): Promise<Permission[]> {
  const response = await fetch(`${API_BASE}/api/roles/permissions/all`);
  if (!response.ok) {
    throw new Error('获取权限列表失败');
  }
  return response.json();
}