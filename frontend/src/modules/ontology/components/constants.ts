function strHash(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

const NODE_SHAPES = ['circle', 'rect', 'diamond', 'ellipse', 'triangle', 'hexagon'] as const;

export function getNodeColor(nodeType: string): string {
  const h = strHash(nodeType) % 360;
  return `hsl(${h}, 55%, 48%)`;
}

export function getNodeShape(nodeType: string): string {
  return NODE_SHAPES[strHash(nodeType) % NODE_SHAPES.length];
}

export function getEdgeStyle(edgeType: string): { stroke: string; lineWidth: number; lineDash?: number[] } {
  const h = strHash(edgeType) % 360;
  const variant = strHash(edgeType + '_v') % 3;
  const base = { stroke: `hsl(${h}, 45%, 42%)`, lineWidth: 1 };
  if (variant === 0) return base;
  if (variant === 1) return { ...base, lineDash: [4, 3] };
  return { ...base, lineDash: [2, 2] };
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

export const ZOOM_STEP = 0.2;
export const ZOOM_MIN = 0.1;
export const ZOOM_MAX = 5.0;
export const LOD_LABEL_THRESHOLD = 0.45;
export const LOD_EDGE_LABEL_THRESHOLD = 0.7;
export const LOD_BIG_GRAPH_THRESHOLD = 200;
export const LAYOUT_MAX_ITERATIONS = 500;
export const LAYOUT_CANVAS_SIZE = 4000;
export const LAYOUT_CENTER: [number, number] = [2000, 2000];
export const MINIMAP_MAX_SIZE = 200;

export type LayoutType = 'force' | 'circular' | 'grid' | 'dagre' | 'radial';

export const LAYOUT_OPTIONS = [
  { value: 'force', label: '力导向' },
  { value: 'circular', label: '环形' },
  { value: 'grid', label: '网格' },
  { value: 'dagre', label: '层次' },
  { value: 'radial', label: '辐射' },
] as const;  