/**
 * Wiki 模块 mock 网关 —— 显式开关，绝不冒充真实数据。
 *
 * 开关：`services/wikiConfig.ts` 的 WIKI_API_MOCK（默认开，因后端 F1 端点本轮未就绪）。
 * 开启时页面顶部必须显示"演示数据（mock 开关开启）"横幅，见 pages/WikiListPage.tsx。
 *
 * 数据刻意使用典型业务样本：本体术语、指标名、中文标题、超长标题、特殊字符、空数组，
 * 不使用 foo/bar/test 占位。
 */
import type {
  DedupeCandidate,
  ReferenceGraph,
  WikiEntry,
  WikiEntryList,
  WikiListQuery,
  WikiMergeRequest,
  WikiVersion,
} from './wikiTypes';
import { WikiApiError } from './wikiError';

const WS = 'ws-odap-main';

const ENTRY_SEED: Array<Partial<WikiEntry> & Pick<WikiEntry, 'id' | 'title' | 'status'> & { days: number }> = [
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    title: '退货率口径说明（Metric: ReturnRate）',
    status: 'published',
    owner_id: 'u-arch-zhang',
    version: '1.4.0',
    tags: ['指标口径', '本体'],
    concept_refs: ['Metric:ReturnRate', 'ObjectType:Order'],
    days: 12,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V2',
    title: '客户流失（Churn）与「客户流失率」的口径差异',
    status: 'draft',
    owner_id: 'u-pm-lin',
    version: '0.1.0',
    tags: ['术语对齐'],
    concept_refs: ['Metric:ChurnRate'],
    days: 3,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V3',
    title:
      '关于跨域语义层（USL）与本体约束编排六步管线的联合验收说明及灰度回滚预案——2026 年 Q3 复盘与 Q4 排期',
    status: 'review',
    owner_id: 'u-be-chen',
    version: '0.9.1',
    tags: ['架构', '验收', '灰度'],
    concept_refs: ['ObjectType:UslPackage', 'RelationType:dependsOn'],
    days: 1,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V4',
    title: 'Q&A：供应链「牛鞭效应」vs "Bullwhip Effect" 术语对齐 <v2.1>',
    status: 'published',
    owner_id: 'u-designer-yan',
    version: '2.1.0',
    tags: ['术语表', '供应链', '100%-匹配'],
    concept_refs: [],
    days: 40,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V5',
    title: 'SHACL 形状约束落库与写路径校验不变量',
    status: 'published',
    owner_id: 'u-arch-zhang',
    version: '1.0.2',
    tags: ['本体治理'],
    concept_refs: ['Shape:OrderShape'],
    days: 220,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
    title: '旧版返回值语义（已被「退货率口径说明」取代）',
    status: 'superseded',
    owner_id: 'u-arch-zhang',
    version: '0.6.0',
    tags: ['指标口径'],
    concept_refs: ['Metric:ReturnRate'],
    days: 300,
  },
  {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V7',
    title: '图谱实体软删除语义（归档）',
    status: 'archived',
    owner_id: 'u-be-chen',
    version: '0.3.0',
    tags: [],
    concept_refs: [],
    days: 410,
  },
];

function isoDaysAgo(days: number): string {
  const d = new Date('2026-10-17T08:00:00.000Z');
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString();
}

function hashOf(seed: string): string {
  // 仅用于 mock 的稳定伪哈希（sha256 长度格式），不参与任何真实判重
  let h = 0n;
  for (const ch of seed) h = (h * 131n + BigInt(ch.codePointAt(0) ?? 0)) % (1n << 64n);
  return h.toString(16).padStart(16, '0').repeat(4).slice(0, 64);
}

export const MOCK_ENTRIES: WikiEntry[] = ENTRY_SEED.map((seed) => ({
  id: seed.id,
  title: seed.title,
  status: seed.status,
  owner_id: seed.owner_id ?? 'u-arch-zhang',
  version: seed.version ?? '0.1.0',
  source_ref: `docs/04-ui/wiki/${seed.id}.md`,
  superseded_by: seed.status === 'superseded' ? '01J9Z6Q2X8K3M4N5P6R7S8T9V1' : null,
  content_hash: hashOf(seed.id),
  last_verified: isoDaysAgo(seed.days),
  tags: seed.tags ?? [],
  concept_refs: seed.concept_refs ?? [],
  workspace_id: WS,
  created_at: isoDaysAgo(seed.days + 30),
  updated_at: isoDaysAgo(seed.days),
}));

const MOCK_CONTENT: Record<string, string> = {
  '01J9Z6Q2X8K3M4N5P6R7S8T9V1': [
    '# 退货率口径说明',
    '',
    '## 定义',
    '退货率 = 统计周期内退货订单数 / 同期已签收订单数。',
    '分子分母必须来自同一 TBox 版本快照，跨版本混算会导致口径漂移。',
    '',
    '## 归属本体元素',
    '- `Metric:ReturnRate`（指标节点）',
    '- `ObjectType:Order`（订单对象类型）',
    '- `RelationType:refundOf`（退货关系）',
    '',
    '## 已知边界',
    '1. 部分退款按订单维度计一次，不按退款笔数计。',
    '2. 仅统计已签收订单；未签收订单在签收后才进入分母。',
  ].join('\n'),
};

const MOCK_VERSIONS: WikiVersion[] = [
  {
    id: 'wv-1',
    entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    version: '1.4.0',
    content: MOCK_CONTENT['01J9Z6Q2X8K3M4N5P6R7S8T9V1'],
    content_hash: hashOf('wv-1'),
    author_id: 'u-arch-zhang',
    change_note: '补充「部分退款按订单维度计一次」的边界说明',
    created_at: isoDaysAgo(12),
  },
  {
    id: 'wv-2',
    entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    version: '1.3.0',
    content: '# 退货率口径说明\n\n分母改为「已签收订单数」。',
    content_hash: hashOf('wv-2'),
    author_id: 'u-pm-lin',
    change_note: '分母从「全部订单」改为「已签收订单」，与财务口径对齐',
    created_at: isoDaysAgo(38),
  },
  {
    id: 'wv-3',
    entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    version: '1.2.0',
    content: '# 退货率口径说明\n\n初版。',
    content_hash: hashOf('wv-3'),
    author_id: 'u-arch-zhang',
    change_note: '首次发布，锚定 TBox v2026.08 快照',
    created_at: isoDaysAgo(96),
  },
];

const MOCK_REFERENCES: ReferenceGraph = {
  entry_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
  outgoing: [
    { kind: 'tbox_node', ref: 'Metric:ReturnRate', label: '指标 · 退货率' },
    { kind: 'tbox_node', ref: 'ObjectType:Order', label: '对象类型 · 订单' },
    { kind: 'metric', ref: 'metric.return_rate.p90', label: '指标平台 · return_rate P90' },
    { kind: 'opa_decision', ref: 'opa/decision/2026-09-11/7f3a', label: 'OPA 决策记录' },
  ],
  incoming: [
    { kind: 'doc', ref: '01J9Z6Q2X8K3M4N5P6R7S8T9V6', label: '旧版返回值语义（已取代）' },
    { kind: 'graph_edge', ref: 'edge:Order-refundOf-ReturnOrder', label: '图谱边 · refundOf' },
  ],
};

const MOCK_DEDUPE: DedupeCandidate[] = [
  {
    left_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    right_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
    left_title: '退货率口径说明（Metric: ReturnRate）',
    right_title: '旧版返回值语义（已被「退货率口径说明」取代）',
    similarity: 0.94,
    reason: 'content_hash 前缀相同，且 87% 段落文本一致',
    content_hash: hashOf('01J9Z6Q2X8K3M4N5P6R7S8T9V1'),
    conflicting_fields: ['version', 'status', 'last_verified'],
  },
  {
    left_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V4',
    right_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V2',
    left_title: 'Q&A：供应链「牛鞭效应」vs "Bullwhip Effect" 术语对齐 <v2.1>',
    right_title: '客户流失（Churn）与「客户流失率」的口径差异',
    similarity: 0.71,
    reason: '标签重合 1 项（术语表族），标题语义向量距离 0.29',
    content_hash: hashOf('01J9Z6Q2X8K3M4N5P6R7S8T9V4'),
    conflicting_fields: ['tags'],
  },
];

/** 模拟网络时延，使 Loading 态真实可见（不用于掩盖失败） */
const delay = (ms = 180) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** 故障注入：测试与演示错误态用，默认关闭 */
export type MockFailureMode = 'none' | 'list' | 'detail' | 'dedupe' | 'merge';
let failureMode: MockFailureMode = 'none';
export function setMockFailure(mode: MockFailureMode): void {
  failureMode = mode;
}

function fail(mode: MockFailureMode, code: string, message: string, status: number, detail: Record<string, unknown> | null = null): void {
  if (failureMode === mode) {
    throw new WikiApiError({ error_code: code, message, detail, trace_id: `mock-${mode}-${Date.now()}` }, status);
  }
}

export const mockGateway = {
  async list(query: WikiListQuery): Promise<WikiEntryList> {
    await delay();
    fail('list', 'WIKI_LIST_UPSTREAM_TIMEOUT', '条目列表上游 SQLite 查询超时（read txn 8s）', 504);
    const keyword = (query.keyword ?? '').trim().toLowerCase();
    const filtered = MOCK_ENTRIES.filter((e) => {
      if (query.status && query.status !== 'all' && e.status !== query.status) return false;
      if (query.owner && e.owner_id !== query.owner) return false;
      if (query.tag && !e.tags.includes(query.tag)) return false;
      if (keyword && !e.title.toLowerCase().includes(keyword)) return false;
      return true;
    });
    const page = query.page ?? 1;
    const pageSize = query.page_size ?? 10;
    const start = (page - 1) * pageSize;
    return { data: filtered.slice(start, start + pageSize), total: filtered.length, page, page_size: pageSize };
  },

  async detail(entryId: string): Promise<WikiEntry> {
    await delay();
    fail('detail', 'WIKI_ENTRY_NOT_FOUND', `条目 ${entryId} 不存在或已物理删除（软删除状态应为 archived）`, 404);
    const found = MOCK_ENTRIES.find((e) => e.id === entryId);
    if (!found) {
      throw new WikiApiError(
        { error_code: 'WIKI_ENTRY_NOT_FOUND', message: `条目 ${entryId} 不存在`, detail: null, trace_id: `mock-${Date.now()}` },
        404,
      );
    }
    return found;
  },

  async versions(entryId: string): Promise<WikiVersion[]> {
    await delay();
    return MOCK_VERSIONS.filter((v) => v.entry_id === entryId).sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  async references(entryId: string): Promise<ReferenceGraph> {
    await delay();
    return { ...MOCK_REFERENCES, entry_id: entryId };
  },

  async dedupe(): Promise<DedupeCandidate[]> {
    await delay();
    fail('dedupe', 'DOCS_DEDUPE_INDEX_MISSING', '去重索引未建立，请先执行 POST /api/v1/docs/governance/verify', 409);
    return MOCK_DEDUPE;
  },

  async merge(req: WikiMergeRequest): Promise<{ kept: string; superseded: string }> {
    await delay(240);
    fail('merge', 'WIKI_VERSION_CONFLICT', '合并前版本校验失败：discard 侧已被他人更新', 409, {
      conflicting_entry_id: req.discard_id,
      current_version: '0.7.0',
    });
    return { kept: req.keep_id, superseded: req.discard_id };
  },

  async content(entryId: string): Promise<string> {
    await delay();
    return MOCK_CONTENT[entryId] ?? `# ${MOCK_ENTRIES.find((e) => e.id === entryId)?.title ?? '条目'}\n\n（正文由后端 wiki_versions.content 提供）`;
  },
};
