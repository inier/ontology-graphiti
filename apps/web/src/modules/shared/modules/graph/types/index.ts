/**
 * 通用图谱类型定义 — Sigma.js + Cytoscape.js 双引擎共用
 */

// ─── 通用图谱数据模型 ───

export interface GraphNode {
  id: string;
  label: string;
  /** 节点类型，用于样式映射 */
  type: string;
  /** 侧边标记（red/blue/neutral），用于描边色 */
  side?: string;
  /** 自定义属性 */
  properties?: Record<string, unknown>;
  /** 父节点 ID（复合节点场景） */
  parent?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  /** 边类型，用于样式映射 */
  type: string;
  /** 边标签 */
  label?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ─── 样式策略 ───

/** 哈希自动着色（GraphCanvas 默认） */
export type HashStyleStrategy = 'hash';

/** 固定类型映射着色（OntologySemanticNetwork 等） */
export type MappingStyleStrategy = 'mapping';

export type NodeStyleStrategy = HashStyleStrategy | MappingStyleStrategy;

export interface NodeStyleConfig {
  fill: string;
  stroke: string;
  /** Cytoscape shape 或 Sigma type */
  shape: string;
  size?: number;
}

export interface EdgeStyleConfig {
  stroke: string;
  width?: number;
  lineDash?: number[];
  arrow?: boolean;
}

// ─── 布局类型 ───

export type SigmaLayoutType = 'force' | 'forceatlas2' | 'circular' | 'grid' | 'radial';
export type CytoscapeLayoutType = 'dagre' | 'cose-bilkent' | 'circle' | 'grid' | 'concentric' | 'breadthfirst';

export const SIGMA_LAYOUT_OPTIONS = [
  { value: 'force', label: '力导向' },
  { value: 'forceatlas2', label: 'ForceAtlas2' },
  { value: 'circular', label: '环形' },
  { value: 'grid', label: '网格' },
  { value: 'radial', label: '辐射' },
] as const;

export const CYTOSCAPE_LAYOUT_OPTIONS = [
  { value: 'dagre', label: '层次' },
  { value: 'cose-bilkent', label: '力导向' },
  { value: 'circle', label: '环形' },
  { value: 'grid', label: '网格' },
  { value: 'concentric', label: '同心圆' },
  { value: 'breadthfirst', label: '广度优先' },
] as const;

// ─── 引擎类型 ───

export type GraphEngine = 'sigma' | 'cytoscape';

// ─── LOD 配置 ───

export interface LODConfig {
  /** 节点标签显隐阈值 */
  labelThreshold: number;
  /** 边标签显隐阈值 */
  edgeLabelThreshold: number;
  /** 大图判定阈值（节点数） */
  bigGraphThreshold: number;
}

export const DEFAULT_LOD: LODConfig = {
  labelThreshold: 0.45,
  edgeLabelThreshold: 0.7,
  bigGraphThreshold: 200,
};

// ─── 缩放配置 ───

export interface ZoomConfig {
  min: number;
  max: number;
  step: number;
}

export const DEFAULT_ZOOM: ZoomConfig = {
  min: 0.1,
  max: 5.0,
  step: 0.2,
};

// ─── 选中状态 ───

export type SelectionState = 'selected' | 'highlight' | 'dim' | 'default';

export interface GraphSelection {
  selectedNodeId: string | null;
  highlightedNodeIds: Set<string>;
  highlightedEdgeIds: Set<string>;
}
