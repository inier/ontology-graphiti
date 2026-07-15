import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

/** 菜单项类型 */
export interface MenuItem {
  id: string;
  parent_id: string | null;
  name: string;
  code: string;
  menu_type: 'directory' | 'menu' | 'action';
  link_type: 'internal' | 'iframe';
  path?: string;
  url?: string;
  icon: string;
  sort_order: number;
  is_active: boolean;
  is_visible: boolean;
  description: string;
  created_at: string;
  updated_at: string;
  children?: MenuItem[];
}

const BASE = `${API_BASE}/api/menu-config`;

export const menuConfigApi = {
  /** 获取当前用户可见的菜单树 */
  getUserTree: (): Promise<{ tree: MenuItem[] }> =>
    fetchJson(`${BASE}/tree`),

  /** 获取完整菜单树（管理员，含禁用） */
  getFullTree: (): Promise<{ tree: MenuItem[] }> =>
    fetchJson(`${BASE}/tree/all`),

  /** 获取全部菜单项扁平列表（管理员） */
  listAllItems: (menuType?: string): Promise<{ items: MenuItem[]; total: number }> => {
    const params = menuType ? `?menu_type=${encodeURIComponent(menuType)}` : '';
    return fetchJson(`${BASE}/items/all${params}`);
  },

  /** 创建菜单项 */
  createItem: (data: Partial<MenuItem>): Promise<MenuItem> =>
    fetchJson(`${BASE}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  /** 更新菜单项 */
  updateItem: (id: string, data: Partial<MenuItem>): Promise<MenuItem> =>
    fetchJson(`${BASE}/items/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  /** 删除菜单项（级联删除子节点） */
  deleteItem: (id: string): Promise<{ status: string; message: string }> =>
    fetchJson(`${BASE}/items/${id}`, { method: 'DELETE' }),

  /** 设置角色的菜单权限（全量替换） */
  setRoleMenus: (roleId: string, menuItemIds: string[]): Promise<any> =>
    fetchJson(`${BASE}/role-menus`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role_id: roleId, menu_item_ids: menuItemIds }),
    }),

  /** 获取角色已分配的菜单项 */
  getRoleMenus: (roleId: string): Promise<{ role_id: string; menu_ids: string[]; items: MenuItem[] }> =>
    fetchJson(`${BASE}/role-menus/${encodeURIComponent(roleId)}`),

  /** 获取菜单项关联的角色（反向查询） */
  getMenuRoles: (menuItemId: string): Promise<{ menu_item_id: string; role_ids: string[] }> =>
    fetchJson(`${BASE}/menu-roles/${encodeURIComponent(menuItemId)}`),
};
