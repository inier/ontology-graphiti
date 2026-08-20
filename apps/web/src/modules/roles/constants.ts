/**
 * 角色常量（唯一来源，避免各页面角色列表不一致）
 *
 * - `GLOBAL_ROLES`：11 个全局角色，对齐后端
 *   `infra/security/auth_models.GlobalRole` 与
 *   `biz/platform/menu_config/services/menu_config_service.GLOBAL_ROLES`。
 *   JWT payload["role"] / menu_config role_menus 均以这些 value 为键。
 * - `ROLE_TYPE_OPTIONS`：13 个自定义角色类型，对齐后端
 *   `biz/platform/roles/api/schemas.RoleType`（含遗留 director/intelligence）。
 *
 * 新增后端角色时，必须同步维护本文件，保证各界面角色下拉一致。
 */

export interface RoleOption {
  value: string;
  label: string;
  color: string;
  description?: string;
}

/** 全局角色（11 项，与后端 GlobalRole / GLOBAL_ROLES 一一对应） */
export const GLOBAL_ROLES: RoleOption[] = [
  { value: 'admin', label: '系统管理员', color: 'red', description: '全部菜单权限（无需分配）' },
  { value: 'system_admin', label: '系统管理员(内部)', color: 'volcano', description: '系统级管理员' },
  { value: 'project_owner', label: '项目负责人', color: 'orange', description: '项目级管理者' },
  { value: 'team_leader', label: '团队负责人', color: 'gold', description: '团队级管理者' },
  { value: 'analyst', label: '分析师', color: 'magenta', description: '数据分析与决策推演' },
  { value: 'operator', label: '操作员', color: 'geekblue', description: '日常业务操作' },
  { value: 'commander', label: '指挥官', color: 'purple', description: '决策指挥' },
  { value: 'observer', label: '观察者', color: 'default', description: '只读查看' },
  { value: 'member', label: '成员', color: 'green', description: '常规成员' },
  { value: 'guest', label: '访客', color: 'gray', description: '受限访问' },
  { value: 'schema_auditor', label: '语义审计员', color: 'cyan', description: '本体/语义配置审计' },
];

/** 自定义角色类型（13 项：11 全局角色 + 2 遗留角色，对齐后端 RoleType） */
export const ROLE_TYPE_OPTIONS: RoleOption[] = [
  ...GLOBAL_ROLES,
  { value: 'director', label: '负责人', color: 'lime', description: '遗留角色：推荐引擎使用' },
  { value: 'intelligence', label: '情报员', color: 'cyan', description: '遗留角色：cognition engine 使用' },
];

const ROLE_MAP = new Map<string, RoleOption>(ROLE_TYPE_OPTIONS.map((r) => [r.value, r]));

/** 取角色显示名（未命中时原样返回） */
export const getRoleLabel = (role: string): string => ROLE_MAP.get(role)?.label ?? role;

/** 取角色标签颜色（AntD Tag color，未命中时 default） */
export const getRoleColor = (role: string): string => ROLE_MAP.get(role)?.color ?? 'default';

/** 仅按全局角色取显示名（未命中时原样返回） */
export const getGlobalRoleLabel = (role: string): string =>
  GLOBAL_ROLES.find((r) => r.value === role)?.label ?? role;
