/**
 * 图谱样式工具函数 — Sigma.js + Cytoscape.js 共用
 *
 * 保持与原 constants.ts 的视觉一致性
 */

function strHash(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

// ─── 节点颜色 ───

export function getNodeColor(nodeType: string): string {
  const h = strHash(nodeType) % 360;
  return `hsl(${h}, 55%, 48%)`;
}

export function getContrastColor(nodeType: string): string {
  const color = getNodeColor(nodeType);
  const m = color.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
  if (m) {
    const lightness = parseInt(m[3], 10);
    return lightness > 45 ? '#fff' : '#eee';
  }
  return '#fff';
}

export function getSideColor(side: string): string {
  const sideMap: Record<string, string> = { red: '#ff4d4f', blue: '#1890ff', neutral: '#8c8c8c' };
  return sideMap[side] || getNodeColor(side);
}

// ─── 节点形状 ───

const NODE_SHAPES_SIGMA = ['circle', 'circle', 'diamond', 'circle', 'circle', 'circle'] as const;
const NODE_SHAPES_CYTOSCAPE = ['ellipse', 'rectangle', 'diamond', 'ellipse', 'triangle', 'hexagon'] as const;

export function getNodeShapeSigma(nodeType: string): string {
  return NODE_SHAPES_SIGMA[strHash(nodeType) % NODE_SHAPES_SIGMA.length];
}

export function getNodeShapeCytoscape(nodeType: string): string {
  return NODE_SHAPES_CYTOSCAPE[strHash(nodeType) % NODE_SHAPES_CYTOSCAPE.length];
}

// ─── 边样式 ───

export interface EdgeStyleResult {
  stroke: string;
  width: number;
  lineDash: number[];
}

export function getEdgeStyle(edgeType: string): EdgeStyleResult {
  const h = strHash(edgeType) % 360;
  const variant = strHash(edgeType + '_v') % 3;
  const base: EdgeStyleResult = { stroke: `hsl(${h}, 45%, 42%)`, width: 1, lineDash: [] };
  if (variant === 1) return { ...base, lineDash: [4, 3] };
  if (variant === 2) return { ...base, lineDash: [2, 2] };
  return base;
}

// ─── 常量 ───

export const ZOOM_STEP = 0.2;
export const ZOOM_MIN = 0.1;
export const ZOOM_MAX = 5.0;
export const LOD_LABEL_THRESHOLD = 0.45;
export const LOD_EDGE_LABEL_THRESHOLD = 0.7;
export const LOD_BIG_GRAPH_THRESHOLD = 200;
export const MINIMAP_MAX_SIZE = 200;
