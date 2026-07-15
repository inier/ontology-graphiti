/**
 * semantic-admin 模块路由声明（仅用于本模块 index.ts 导出与文档说明）
 * 实际路由注册在 AppRoutes.tsx 中统一完成（按项目现有模式直接写 Route 元素）
 */
import type { ComponentType } from 'react';

/** 路由元数据（供 AppRoutes 消费参考，不直接用数组 push） */
export interface SemanticAdminRouteMeta {
  path: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>;
  breadcrumb: string;
}

export const semanticAdminRouteMeta: SemanticAdminRouteMeta[] = [
  { path: '/semantic-admin', component: () => null, breadcrumb: '语义管理' },
  { path: '/semantic-admin/usl', component: () => null, breadcrumb: 'USL 规范配置' },
  { path: '/semantic-admin/pipeline', component: () => null, breadcrumb: '本体学习流水线' },
  { path: '/semantic-admin/candidates', component: () => null, breadcrumb: '候选审核台' },
  { path: '/semantic-admin/quality', component: () => null, breadcrumb: '质量指标面板' },
  { path: '/semantic-admin/dashboard', component: () => null, breadcrumb: '治理仪表盘' },
  { path: '/semantic-admin/approvals', component: () => null, breadcrumb: '审批工作台' },
];
