import { fetchJson, API_BASE } from '../../shared';
import type { Role, RoleCreate, RoleUpdate, Permission } from '../types';

export async function listRoles(): Promise<Role[]> {
  const data = await fetchJson<{ roles: Role[]; total: number } | Role[]>(`${API_BASE}/api/roles`);
  return Array.isArray(data) ? data : (data.roles || []);
}

export async function getRole(roleId: string): Promise<Role> {
  return fetchJson<Role>(`${API_BASE}/api/roles/${roleId}`);
}

export async function createRole(role: RoleCreate): Promise<Role> {
  return fetchJson<Role>(`${API_BASE}/api/roles`, {
    method: 'POST',
    body: JSON.stringify(role),
  });
}

export async function updateRole(roleId: string, role: RoleUpdate): Promise<Role> {
  return fetchJson<Role>(`${API_BASE}/api/roles/${roleId}`, {
    method: 'PUT',
    body: JSON.stringify(role),
  });
}

export async function deleteRole(roleId: string): Promise<void> {
  await fetchJson<void>(`${API_BASE}/api/roles/${roleId}`, { method: 'DELETE' });
}

export async function listPermissions(): Promise<Permission[]> {
  const data = await fetchJson<Permission[] | { permissions: Permission[] }>(`${API_BASE}/api/roles/permissions/all`);
  return Array.isArray(data) ? data : (data.permissions || []);
}
