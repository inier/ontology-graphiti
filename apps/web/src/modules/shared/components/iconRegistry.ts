/**
 * 语义角色 → Lucide 图标 静态注册表（ADR-092 第 12 条）
 *
 * 约束（违反即 CI 失败，见 scripts/check-lucide-icons.mjs）：
 *  1. 必须具名导入（禁止 `import * as Icons`），只列 §5.2 终裁过的图标集合
 *  2. 主键是「语义角色」（稳定），右侧 iconName 是「须按 pinned 版本导出清单解析」的候选
 *  3. minSize：16px 复杂度门禁。多内轮廓/密集字形最小 20px，禁止硬缩到 16px
 *
 * 本文件是 Icon 包装模块的内部数据，业务代码请使用 <Icon role="..." />。
 * 真源：docs/ui/UIUX-DESIGN-v2.md §5.2 + docs/07-adr/ADR-092_icon-library-lock.md
 */
import {
  LayoutDashboard,
  Network,
  BookOpen,
  MessageCircleQuestion,
  ShieldCheck,
  Settings,
  Scale,
  Box,
  Link,
  Zap,
  Circle,
  Clock,
  Gauge,
  Shield,
  Bot,
  Play,
  Pause,
  Square,
  Locate,
  Download,
  Layers,
  Search,
  Filter,
  Waypoints,
  EyeOff,
  Undo2,
  Redo2,
  CircleDashed,
  Package,
  Ticket,
  Footprints,
  History,
  Signpost,
  FlaskConical,
  Radar,
  ScanLine,
  FileDiff,
  Shapes,
  GitCommit,
  Boxes,
  RefreshCw,
  Tags,
  ChartLine,
  Cpu,
  Route,
  Stamp,
  PenTool,
  Workflow,
  GitFork,
  Plus,
  SquarePen,
  Trash2,
  Check,
  X,
  GitMerge,
  GitCompare,
  ExternalLink,
  RefreshCcw,
  Inbox,
  CircleAlert,
  LoaderCircle,
  CircleCheck,
  CircleX,
  TriangleAlert,
  Info,
  ChevronRight,
  ChevronDown,
  ChevronLeft,
  Table,
  LayoutGrid,
  SlidersHorizontal,
  Palette,
  Moon,
  Sun,
  Pin,
  User,
  Calendar,
  FileText,
  ListTree,
  ClipboardList,
  MessageSquare,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

/** 图标尺寸仅三档（--odap-size-icon-inline/button/standalone） */
export type IconSize = 16 | 20 | 24;

export interface IconRoleSpec {
  readonly icon: LucideIcon;
  /** pinned 版本的导出名，供 CI 语义角色表校验比对 */
  readonly iconName: string;
  /** 16px 复杂度门禁：允许的最小渲染尺寸 */
  readonly minSize: IconSize;
}

export const ICON_ROLES = {
  /* ── 6 个工作区（§6.5） ── */
  dashboard: { icon: LayoutDashboard, iconName: 'LayoutDashboard', minSize: 20 },
  ontology: { icon: Network, iconName: 'Network', minSize: 20 },
  knowledge: { icon: BookOpen, iconName: 'BookOpen', minSize: 16 },
  ask: { icon: MessageCircleQuestion, iconName: 'MessageCircleQuestion', minSize: 20 },
  governance: { icon: ShieldCheck, iconName: 'ShieldCheck', minSize: 20 },
  settings: { icon: Settings, iconName: 'Settings', minSize: 20 },
  platformGovernance: { icon: Scale, iconName: 'Scale', minSize: 20 },

  /* ── 图谱节点类型（§4.4，与 shape 冗余编码自洽） ── */
  objectType: { icon: Box, iconName: 'Box', minSize: 16 },
  linkType: { icon: Link, iconName: 'Link', minSize: 16 },
  actionType: { icon: Zap, iconName: 'Zap', minSize: 16 },
  instance: { icon: Circle, iconName: 'Circle', minSize: 16 },
  event: { icon: Clock, iconName: 'Clock', minSize: 16 },
  metric: { icon: Gauge, iconName: 'Gauge', minSize: 16 },
  rule: { icon: Shield, iconName: 'Shield', minSize: 16 },
  agent: { icon: Bot, iconName: 'Bot', minSize: 16 },

  /* ── 工具栏 ── */
  play: { icon: Play, iconName: 'Play', minSize: 16 },
  pause: { icon: Pause, iconName: 'Pause', minSize: 16 },
  stop: { icon: Square, iconName: 'Square', minSize: 16 },
  locate: { icon: Locate, iconName: 'Locate', minSize: 16 },
  export: { icon: Download, iconName: 'Download', minSize: 16 },
  layers: { icon: Layers, iconName: 'Layers', minSize: 20 },
  search: { icon: Search, iconName: 'Search', minSize: 16 },
  filter: { icon: Filter, iconName: 'Filter', minSize: 16 },
  expandNeighbors: { icon: Waypoints, iconName: 'Waypoints', minSize: 20 },
  hide: { icon: EyeOff, iconName: 'EyeOff', minSize: 16 },
  undo: { icon: Undo2, iconName: 'Undo2', minSize: 16 },
  redo: { icon: Redo2, iconName: 'Redo2', minSize: 16 },

  /* ── ODAP 专有概念（§5.2 B 组） ── */
  gap: { icon: CircleDashed, iconName: 'CircleDashed', minSize: 16 },
  asset: { icon: Package, iconName: 'Package', minSize: 20 },
  routingTicket: { icon: Ticket, iconName: 'Ticket', minSize: 16 },
  usl: { icon: Layers, iconName: 'Layers', minSize: 20 },
  metricType: { icon: Gauge, iconName: 'Gauge', minSize: 16 },
  provenance: { icon: Footprints, iconName: 'Footprints', minSize: 20 },
  history: { icon: History, iconName: 'History', minSize: 16 },
  decision: { icon: Signpost, iconName: 'Signpost', minSize: 20 },
  simulation: { icon: FlaskConical, iconName: 'FlaskConical', minSize: 20 },
  drift: { icon: Radar, iconName: 'Radar', minSize: 20 },
  scan: { icon: ScanLine, iconName: 'ScanLine', minSize: 20 },
  changeProposal: { icon: FileDiff, iconName: 'FileDiff', minSize: 20 },
  shaclShape: { icon: Shapes, iconName: 'Shapes', minSize: 20 },
  ontologyVersion: { icon: GitCommit, iconName: 'GitCommit', minSize: 16 },
  tbox: { icon: Boxes, iconName: 'Boxes', minSize: 20 },
  abox: { icon: Circle, iconName: 'Circle', minSize: 16 },
  qualityGate: { icon: ShieldCheck, iconName: 'ShieldCheck', minSize: 20 },
  gapLoop: { icon: RefreshCw, iconName: 'RefreshCw', minSize: 20 },
  tag: { icon: Tags, iconName: 'Tags', minSize: 16 },
  chart: { icon: ChartLine, iconName: 'ChartLine', minSize: 20 },
  runtime: { icon: Cpu, iconName: 'Cpu', minSize: 20 },
  path: { icon: Route, iconName: 'Route', minSize: 20 },
  approval: { icon: Stamp, iconName: 'Stamp', minSize: 16 },
  modeling: { icon: PenTool, iconName: 'PenTool', minSize: 20 },
  blueprint: { icon: Workflow, iconName: 'Workflow', minSize: 20 },
  versionBranch: { icon: GitFork, iconName: 'GitFork', minSize: 20 },

  /* ── 通用 UI 语义（非 ODAP 专有，一次约定全局复用） ── */
  create: { icon: Plus, iconName: 'Plus', minSize: 16 },
  edit: { icon: SquarePen, iconName: 'SquarePen', minSize: 16 },
  delete: { icon: Trash2, iconName: 'Trash2', minSize: 16 },
  confirm: { icon: Check, iconName: 'Check', minSize: 16 },
  cancel: { icon: X, iconName: 'X', minSize: 16 },
  merge: { icon: GitMerge, iconName: 'GitMerge', minSize: 20 },
  diff: { icon: GitCompare, iconName: 'GitCompare', minSize: 20 },
  externalLink: { icon: ExternalLink, iconName: 'ExternalLink', minSize: 16 },
  retry: { icon: RefreshCcw, iconName: 'RefreshCcw', minSize: 16 },
  empty: { icon: Inbox, iconName: 'Inbox', minSize: 24 },
  error: { icon: CircleAlert, iconName: 'CircleAlert', minSize: 24 },
  loading: { icon: LoaderCircle, iconName: 'LoaderCircle', minSize: 24 },
  success: { icon: CircleCheck, iconName: 'CircleCheck', minSize: 16 },
  failed: { icon: CircleX, iconName: 'CircleX', minSize: 16 },
  warning: { icon: TriangleAlert, iconName: 'TriangleAlert', minSize: 16 },
  info: { icon: Info, iconName: 'Info', minSize: 16 },
  chevronRight: { icon: ChevronRight, iconName: 'ChevronRight', minSize: 16 },
  chevronDown: { icon: ChevronDown, iconName: 'ChevronDown', minSize: 16 },
  chevronLeft: { icon: ChevronLeft, iconName: 'ChevronLeft', minSize: 16 },
  viewTable: { icon: Table, iconName: 'Table', minSize: 16 },
  viewCard: { icon: LayoutGrid, iconName: 'LayoutGrid', minSize: 16 },
  density: { icon: SlidersHorizontal, iconName: 'SlidersHorizontal', minSize: 16 },
  palette: { icon: Palette, iconName: 'Palette', minSize: 16 },
  appearanceDark: { icon: Moon, iconName: 'Moon', minSize: 16 },
  appearanceLight: { icon: Sun, iconName: 'Sun', minSize: 16 },
  pin: { icon: Pin, iconName: 'Pin', minSize: 16 },
  owner: { icon: User, iconName: 'User', minSize: 16 },
  date: { icon: Calendar, iconName: 'Calendar', minSize: 16 },
  document: { icon: FileText, iconName: 'FileText', minSize: 16 },
  channel: { icon: MessageSquare, iconName: 'MessageSquare', minSize: 16 },
  tree: { icon: ListTree, iconName: 'ListTree', minSize: 20 },
  task: { icon: ClipboardList, iconName: 'ClipboardList', minSize: 16 },
} as const satisfies Record<string, IconRoleSpec>;

export type IconRole = keyof typeof ICON_ROLES;

export const ICON_ROLE_NAMES = Object.keys(ICON_ROLES) as IconRole[];
