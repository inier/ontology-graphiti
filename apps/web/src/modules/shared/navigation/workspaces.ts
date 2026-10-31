/**
 * 6 个顶级工作区定义（F4 / SPEC §7「工作区收敛 60+ 路由 → 6 个工作区」）
 *
 * 这是前端信息架构的单一真源：
 *   - 全局导航（WorkspaceRail）由它渲染（AC-19：仅呈现 6 个工作区）
 *   - 路由一致性测试遍历它，断言每个 nav 目标都存在对应路由（AC-20：无死链）
 *
 * `iconRole` 必须取自 shared/components/iconRegistry.ts 的已登记语义角色。
 */
import type { IconRole } from '@/modules/shared/components/Icon';

export type WorkspaceId =
  | 'workspace'
  | 'ontology'
  | 'knowledge'
  | 'ask'
  | 'governance'
  | 'platform';

export interface WorkspaceNavItem {
  /** 导航目标路由，必须存在于路由表 */
  readonly path: string;
  readonly label: string;
  readonly iconRole: IconRole;
}

export interface WorkspaceDef {
  readonly id: WorkspaceId;
  readonly label: string;
  readonly iconRole: IconRole;
  /** 该工作区的默认落地路由（点击一级项时跳转） */
  readonly home: string;
  /** 归属该工作区的二级项 */
  readonly items: readonly WorkspaceNavItem[];
  /** 判定当前路由属于本工作区的路径前缀（按最长匹配优先） */
  readonly prefixes: readonly string[];
}

export const WORKSPACES: readonly WorkspaceDef[] = [
  {
    id: 'workspace',
    label: '工作台',
    iconRole: 'dashboard',
    home: '/',
    prefixes: ['/', '/workspace', '/guide', '/my-agents', '/agent', '/agent-chat'],
    items: [
      { path: '/', label: '概览', iconRole: 'dashboard' },
      { path: '/workspace/manage', label: '工作空间', iconRole: 'tbox' },
      { path: '/guide', label: '使用引导', iconRole: 'info' },
      { path: '/my-agents', label: '我的智能体', iconRole: 'agent' },
      { path: '/agent', label: '智能体工作台', iconRole: 'agent' },
    ],
  },
  {
    id: 'ontology',
    label: '本体',
    iconRole: 'ontology',
    home: '/ontology/designer',
    prefixes: ['/ontology', '/blueprint', '/versions', '/business'],
    items: [
      { path: '/ontology/designer', label: '本体建模', iconRole: 'modeling' },
      { path: '/ontology/explorer', label: '图谱探查', iconRole: 'ontology' },
      { path: '/ontology/relations', label: '关系与派生', iconRole: 'modeling' },
      { path: '/ontology/health', label: '质量健康度', iconRole: 'scan' },
      { path: '/ontology/views', label: '对象视图', iconRole: 'objectType' },
      { path: '/ontology/service-catalog', label: '服务目录', iconRole: 'routingTicket' },
      { path: '/ontology/semantic-map', label: '语义地图', iconRole: 'usl' },
      { path: '/ontology/abution-graph', label: '图谱视图', iconRole: 'objectType' },
      { path: '/ontology/goals', label: '本体目标', iconRole: 'decision' },
      { path: '/blueprint', label: '蓝图编排', iconRole: 'blueprint' },
      { path: '/versions', label: '版本历史', iconRole: 'ontologyVersion' },
      { path: '/business/process', label: '业务流程', iconRole: 'blueprint' },
      { path: '/business/rules', label: '业务规则', iconRole: 'rule' },
      { path: '/business/indicators', label: '业务指标', iconRole: 'metric' },
      { path: '/business/logic', label: '业务逻辑', iconRole: 'modeling' },
      { path: '/business/entities', label: '业务对象', iconRole: 'instance' },
    ],
  },
  {
    id: 'knowledge',
    label: '知识',
    iconRole: 'knowledge',
    home: '/wiki',
    prefixes: ['/wiki', '/knowledge', '/ingest', '/he', '/mcp'],
    items: [
      { path: '/wiki', label: 'Wiki 条目', iconRole: 'document' },
      { path: '/wiki/dedupe', label: '去重合并', iconRole: 'merge' },
      { path: '/knowledge', label: '知识库', iconRole: 'knowledge' },
      { path: '/ingest', label: '数据摄入', iconRole: 'export' },
      { path: '/he/extraction', label: '语义抽取', iconRole: 'scan' },
      { path: '/mcp/tools', label: 'MCP 工具', iconRole: 'runtime' },
    ],
  },
  {
    id: 'ask',
    label: '问答与决策',
    iconRole: 'ask',
    home: '/qa',
    prefixes: ['/qa', '/decisions', '/simulation'],
    items: [
      { path: '/qa', label: '智能问答', iconRole: 'ask' },
      { path: '/qa/query', label: '问答演练', iconRole: 'search' },
      { path: '/qa/evaluation', label: '意图评测', iconRole: 'chart' },
      { path: '/qa/cognition', label: '认知引擎', iconRole: 'scan' },
      { path: '/qa/memory', label: '会话记忆', iconRole: 'history' },
      { path: '/qa/copilot', label: 'Copilot 对话', iconRole: 'ask' },
      { path: '/decisions/ledger', label: '决策情报', iconRole: 'decision' },
      { path: '/decisions/actions', label: '动作执行', iconRole: 'approval' },
      { path: '/simulation', label: '仿真推演', iconRole: 'simulation' },
      { path: '/simulation/memory', label: '记忆面板', iconRole: 'history' },
      { path: '/simulation/perception', label: '感知面板', iconRole: 'scan' },
      { path: '/simulation/sandbox', label: '沙箱推演', iconRole: 'simulation' },
    ],
  },
  {
    id: 'governance',
    label: '语义治理',
    iconRole: 'governance',
    home: '/semantic-admin',
    prefixes: ['/semantic-admin'],
    items: [
      { path: '/semantic-admin', label: '治理总览', iconRole: 'governance' },
      { path: '/semantic-admin/assets', label: '语义资产', iconRole: 'asset' },
      { path: '/semantic-admin/usl', label: 'USL 配置', iconRole: 'usl' },
      { path: '/semantic-admin/usl-ontologies', label: 'USL 本体', iconRole: 'tbox' },
      { path: '/semantic-admin/pipeline-runs', label: '管线运行', iconRole: 'blueprint' },
      { path: '/semantic-admin/candidates', label: '候选审核', iconRole: 'qualityGate' },
      { path: '/semantic-admin/quality', label: '质量看板', iconRole: 'chart' },
      { path: '/semantic-admin/approvals', label: '审批', iconRole: 'approval' },
      { path: '/semantic-admin/gaps', label: '语义缺口', iconRole: 'gap' },
      { path: '/semantic-admin/gaps/stats', label: '缺口统计', iconRole: 'chart' },
      { path: '/semantic-admin/routing-tickets', label: '路由工单', iconRole: 'routingTicket' },
    ],
  },
  {
    id: 'platform',
    label: '平台管理',
    iconRole: 'settings',
    home: '/settings',
    prefixes: [
      '/settings',
      '/roles',
      '/users',
      '/policy-editor',
      '/opa-monitor',
      '/audit',
      '/menu-config',
      '/i18n-admin',
      '/skills',
      '/admin',
      '/iframe-viewer',
    ],
    items: [
      { path: '/settings', label: '系统设置', iconRole: 'settings' },
      { path: '/settings/channels/default', label: '渠道接入', iconRole: 'channel' },
      { path: '/settings/storage', label: '对象存储', iconRole: 'settings' },
      { path: '/roles', label: '角色权限', iconRole: 'owner' },
      { path: '/users', label: '用户管理', iconRole: 'owner' },
      { path: '/policy-editor', label: '策略治理', iconRole: 'platformGovernance' },
      { path: '/opa-monitor', label: '策略运行时', iconRole: 'platformGovernance' },
      { path: '/audit', label: '审计日志', iconRole: 'history' },
      { path: '/menu-config', label: '菜单配置', iconRole: 'tree' },
      { path: '/i18n-admin', label: '国际化', iconRole: 'document' },
      { path: '/skills', label: '技能管理', iconRole: 'runtime' },
      { path: '/admin/agents', label: '智能体管理', iconRole: 'agent' },
      { path: '/iframe-viewer', label: '外部页面', iconRole: 'externalLink' },
    ],
  },
] as const;

/** 仅 6 个 —— AC-19 断言用 */
export const WORKSPACE_IDS = WORKSPACES.map((w) => w.id);

/** 根据当前 pathname 判定所属工作区（最长前缀优先） */
export function findWorkspaceByPath(pathname: string): WorkspaceDef | undefined {
  let best: { ws: WorkspaceDef; len: number } | undefined;
  for (const ws of WORKSPACES) {
    for (const prefix of ws.prefixes) {
      const hit = pathname === prefix || pathname.startsWith(`${prefix}/`);
      if (hit && (!best || prefix.length > best.len)) {
        best = { ws, len: prefix.length };
      }
    }
  }
  return best?.ws;
}
