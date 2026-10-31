/**
 * 图标语义角色期望表（ADR-092 第 8/11 条）
 *
 * 独立成模块的原因：`check-lucide-icons.mjs` 需要保持 ≤300 行（团队单文件上限），
 * 而这张表会随设计侧 §5.2 的终裁不断增补，属于"数据"而非"逻辑"。
 *
 * 修改规则：
 *   1. 只能按设计侧 §5.2 终裁结果修改，禁止前端自行增删角色
 *   2. 值 = [lucide 图标名, minSize]；minSize 仅允许 16/20/24
 *   3. 改动后必须同步 `src/modules/shared/components/iconRegistry.ts`，否则 check:icons 失败
 */
/** pinned 版本 —— 与 apps/web/package.json 互为校验 */
export const PINNED_VERSION = '1.58.0';

/* ── 设计侧 §5.2 终裁表（语义角色 → 期望图标名 + minSize） ──────────────
 * A 组 8 条语义冲突裁决 + B 组 22 项 ODAP 专有概念 + 通用 UI 语义。
 * 通用 UI 语义（generic: true）为本轮新增登记项，变更须走设计侧终审。 */
export const EXPECTED = {
  // A 组：工作区 / 冲突裁决
  dashboard: ['LayoutDashboard', 20],
  ontology: ['Network', 20],
  knowledge: ['BookOpen', 16],
  ask: ['MessageCircleQuestion', 20],
  governance: ['ShieldCheck', 20],
  settings: ['Settings', 20],
  platformGovernance: ['Scale', 20],
  // 图谱节点类型（§4.4）
  objectType: ['Box', 16],
  linkType: ['Link', 16],
  actionType: ['Zap', 16],
  instance: ['Circle', 16],
  event: ['Clock', 16],
  metric: ['Gauge', 16],
  rule: ['Shield', 16],
  agent: ['Bot', 16],
  // 工具栏
  play: ['Play', 16],
  pause: ['Pause', 16],
  stop: ['Square', 16],
  locate: ['Locate', 16],
  export: ['Download', 16],
  layers: ['Layers', 20],
  search: ['Search', 16],
  filter: ['Filter', 16],
  expandNeighbors: ['Waypoints', 20],
  hide: ['EyeOff', 16],
  undo: ['Undo2', 16],
  redo: ['Redo2', 16],
  // B 组：ODAP 专有概念
  gap: ['CircleDashed', 16],
  asset: ['Package', 20],
  routingTicket: ['Ticket', 16],
  usl: ['Layers', 20],
  metricType: ['Gauge', 16],
  provenance: ['Footprints', 20],
  history: ['History', 16],
  decision: ['Signpost', 20],
  simulation: ['FlaskConical', 20],
  drift: ['Radar', 20],
  scan: ['ScanLine', 20],
  changeProposal: ['FileDiff', 20],
  shaclShape: ['Shapes', 20],
  ontologyVersion: ['GitCommit', 16],
  tbox: ['Boxes', 20],
  abox: ['Circle', 16],
  qualityGate: ['ShieldCheck', 20],
  gapLoop: ['RefreshCw', 20],
  tag: ['Tags', 16],
  chart: ['ChartLine', 20],
  runtime: ['Cpu', 20],
  path: ['Route', 20],
  approval: ['Stamp', 16],
  modeling: ['PenTool', 20],
  blueprint: ['Workflow', 20],
  versionBranch: ['GitFork', 20],
  // 通用 UI 语义（设计侧未单列，按 §5.2 优先级原则①一语义一图标登记）
  create: ['Plus', 16],
  edit: ['SquarePen', 16],
  delete: ['Trash2', 16],
  confirm: ['Check', 16],
  cancel: ['X', 16],
  merge: ['GitMerge', 20],
  diff: ['GitCompare', 20],
  externalLink: ['ExternalLink', 16],
  retry: ['RefreshCcw', 16],
  empty: ['Inbox', 24],
  error: ['CircleAlert', 24],
  loading: ['LoaderCircle', 24],
  success: ['CircleCheck', 16],
  failed: ['CircleX', 16],
  warning: ['TriangleAlert', 16],
  info: ['Info', 16],
  chevronRight: ['ChevronRight', 16],
  chevronDown: ['ChevronDown', 16],
  chevronLeft: ['ChevronLeft', 16],
  viewTable: ['Table', 16],
  viewCard: ['LayoutGrid', 16],
  density: ['SlidersHorizontal', 16],
  palette: ['Palette', 16],
  appearanceDark: ['Moon', 16],
  appearanceLight: ['Sun', 16],
  pin: ['Pin', 16],
  owner: ['User', 16],
  date: ['Calendar', 16],
  document: ['FileText', 16],
  channel: ['MessageSquare', 16],
  tree: ['ListTree', 20],
  task: ['ClipboardList', 16],
};
