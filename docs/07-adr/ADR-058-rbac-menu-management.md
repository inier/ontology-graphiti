# ADR-058: RBAC 三级菜单管理架构

## 状态
已采纳（2026-07-03）

## 上下文

ODAP 管理后台需要一个灵活的菜单权限管理系统。原有实现采用简单的分组列表模式（group_label/group_icon），存在以下问题：

1. 菜单结构扁平，无法表达多级层次（如"系统管理 → 用户管理 → 查看/编辑/删除"）
2. 分组信息硬编码在前端代码中，无法通过后台动态配置
3. 缺少权限码（permission code）机制，无法实现细粒度的操作级权限控制
4. 角色与菜单的关联关系缺失，无法按角色分配可见菜单

同时，项目已有 OPA 作为业务层权限引擎（ADR-028），但 OPA 擅长的是资源级 ABAC 策略，不适合管理 UI 菜单的显示/隐藏逻辑。需要一个轻量级的菜单 RBAC 层与 OPA 互补。

## 决策

采用经典 RBAC 三级菜单模型，实现自引用树形结构：

### 1. 三级层次定义

| 层级 | MenuType | 说明 | 前端渲染 |
|------|----------|------|----------|
| 一级 | directory | 目录/分组 | 侧边栏分组标题（不可点击） |
| 二级 | menu | 可导航菜单 | 侧边栏可点击链接 |
| 三级 | action | 操作/按钮 | 不渲染在侧边栏，用于权限码校验 |

### 2. 数据模型

MenuItem 采用 parent_id 自引用构建树：
- `parent_id = null` → 顶级目录
- `parent_id = <directory_id>` → 菜单项
- `parent_id = <menu_id>` → 操作项

关键字段：
- `code`: 权限码，格式 `{module}:{resource}:{action}`（如 `system:user:list`）
- `link_type`: internal（内部路由）或 iframe（嵌入外部页面）
- `is_visible`: 控制是否在侧边栏显示
- `sort_order`: 同级排序

### 3. 角色-菜单关联

通过 `role_menus` 关联表实现多对多：
- `set_role_menus(role_id, menu_item_ids)`: 为角色分配菜单权限
- `get_role_menu_ids(role_id)`: 查询角色的菜单ID列表
- `get_menus_for_roles(role_ids)`: 按角色列表获取菜单（用于前端渲染）

admin 角色自动获得全部菜单，不受 role_menus 限制。

### 4. API 设计

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| /api/menu-config/tree | GET | 当前用户可见菜单树 | 认证用户 |
| /api/menu-config/tree/all | GET | 完整菜单树（含禁用） | admin |
| /api/menu-config/items | GET | 扁平菜单列表 | 认证用户 |
| /api/menu-config/items | POST/PUT/DELETE | 菜单 CRUD | admin |
| /api/menu-config/role-menus | POST | 设置角色菜单权限 | admin |
| /api/menu-config/role-menus/{role_id} | GET | 查询角色菜单 | admin |
| /api/menu-config/menu-roles/{menu_id} | GET | 反向查询：菜单→角色 | admin |

### 5. 前端集成

- ProLayout.tsx / AdminLayout.tsx 通过 `useDynamicMenuItems()` hook 调用 `/api/menu-config/tree`
- 将三级树转换为侧边栏结构：directory → 分组，menu → 可导航子项，action → 跳过
- iframe 类型菜单自动转换为 `/iframe-viewer?url=...&title=...` 路径
- 动态菜单与静态 primaryMenus 合并渲染

### 6. 与 OPA 的关系

菜单 RBAC 层负责 UI 可见性控制（"看得到"），OPA 负责 API 级资源权限（"用得了"）。两者互补：
- 菜单 RBAC：粗粒度，控制页面/按钮可见性，基于角色
- OPA：细粒度，控制数据行/字段级访问，基于属性策略

### 7. 实现模块

后端：`odap/biz/platform/menu_config/`（api/models/services/storage 四层）
前端：`frontend/src/modules/menu-config/`（pages/services）
数据库：SQLite `menu_items` 表 + `role_menus` 关联表
种子数据：28 项初始菜单（6 个分组），在 app.py lifespan 中初始化

## 后果

**正面**：
- 三级层次支持任意深度的菜单组织（实际使用三级已足够）
- 权限码机制为未来按钮级权限控制预留扩展点
- 角色-菜单多对多关联，支持灵活的权限分配
- 反向查询（菜单→角色）便于权限审计
- 与 OPA 分层互补，职责清晰

**负面**：
- 种子数据硬编码在 app.py lifespan 中，修改需重启
- 菜单树的递归构建在大量菜单时可能有性能问题（当前 <100 项，可忽略）

## 可逆性
高。menu_items 表可独立重构，不影响其他业务模块。

## 关联 ADR
- ADR-020（管理员控制台统一界面）
- ADR-028（OPA 统一权限校验）
- ADR-007（前端技术栈）
