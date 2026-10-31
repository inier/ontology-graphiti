export { SkillManagement } from './pages/SkillManagement';
// useSkillStore 已删除：与 SkillManagement 页面（走 @/modules/shared 的 api 对象）重复，
// 且全站零消费（只在 barrel 里被导出）。归档于 .workbuddy/archive/zero-ref-2026-10-20/。
export { default as MCPManager } from './components/MCPManager';
export { default as ToolRegistry } from './components/ToolRegistry';
export { default as HookManager } from './components/HookManager';
