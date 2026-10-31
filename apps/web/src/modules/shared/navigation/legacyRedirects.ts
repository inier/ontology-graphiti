/**
 * 旧路由重定向表（F4 / F5 / SPEC AC-18、AC-23）
 *
 * 规则：被收敛的旧路由一律保留 `<Navigate replace />` + `route_redirect` 埋点，
 * 不做 404、不静默丢失书签。
 *
 * `/policies` 已是 redirect，SPEC §13 已订正为非真重复路由，此处仅登记不重复声明，
 * 实际 Route 定义仍在 routeDefs 中（单一来源）。
 */

export interface LegacyRedirect {
  /** 旧路由路径（精确匹配） */
  readonly from: string;
  /** 新路由路径 */
  readonly to: string;
  /** 收敛原因（埋点属性，便于排查"这条为什么被合并"） */
  readonly reason: string;
}

export const LEGACY_REDIRECTS: readonly LegacyRedirect[] = [
  { from: '/ontology', to: '/ontology/designer', reason: '本体工作区落地页收敛' },
  { from: '/ontology/graph', to: '/ontology/explorer', reason: 'Iter3 D5 图谱改名消歧' },
  { from: '/business/extraction', to: '/ingest', reason: '摄入入口收敛到单一摄入页' },
  { from: '/simulator', to: '/simulation?tab=simulator', reason: 'Iter2 D4 仿真入口合并' },
  { from: '/simulation/deduction', to: '/simulation?tab=deduction', reason: 'Iter2 D4 仿真入口合并' },
  { from: '/workspace', to: '/workspace/manage', reason: '工作空间落地页收敛' },
  { from: '/policies', to: '/policy-editor', reason: '策略页三处归一（保留别名）' },
  { from: '/semantic-admin/dashboard', to: '/semantic-admin/quality', reason: 'Iter7 C3 总览与质量同一组 API' },
  { from: '/semantic-admin/pipeline', to: '/semantic-admin/pipeline-runs', reason: 'F5 pipeline 双路由归一' },
  { from: '/knowledge/navigation', to: '/knowledge', reason: 'F5 Knowledge 两处归一' },
  { from: '/admin', to: '/ontology/designer', reason: '无独立管理后台，收敛到本体建模' },
  { from: '/decisions', to: '/decisions/ledger', reason: '决策主线三视图（台账/待办/详情）落地页收敛，一级菜单仍只保留一项' },
] as const;

export const LEGACY_REDIRECT_MAP: ReadonlyMap<string, LegacyRedirect> = new Map(
  LEGACY_REDIRECTS.map((r) => [r.from, r]),
);
