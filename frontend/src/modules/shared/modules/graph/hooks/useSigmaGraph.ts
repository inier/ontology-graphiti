/**
 * useSigmaGraph — Sigma.js 图谱实例生命周期管理 hook
 *
 * 负责：创建/销毁 Sigma 实例、增量更新图数据、布局切换、事件绑定
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import Sigma from 'sigma';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import { circular as circularLayout } from 'graphology-layout';
import type { GraphNode, GraphEdge, SigmaLayoutType } from '../types';
import { getNodeColor, getSideColor, getNodeShapeSigma, getEdgeStyle, LOD_LABEL_THRESHOLD } from '../utils/graphStyles';

interface UseSigmaGraphOptions {
  /** 容器 ref */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** 节点数据 */
  nodes: GraphNode[];
  /** 边数据 */
  edges: GraphEdge[];
  /** 初始布局 */
  layout?: SigmaLayoutType;
  /** 是否显示标签 */
  showLabels?: boolean;
  /** 节点点击回调 */
  onNodeClick?: (node: GraphNode) => void;
  /** 边点击回调 */
  onEdgeClick?: (edge: GraphEdge) => void;
  /** 画布点击回调（清除选中） */
  onCanvasClick?: () => void;
}

interface UseSigmaGraphReturn {
  sigmaRef: React.RefObject<Sigma | null>;
  graphRef: React.RefObject<Graph | null>;
  zoomLevel: number;
  setLayout: (layout: SigmaLayoutType) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  resetZoom: () => void;
  focusNode: (nodeId: string) => void;
  searchNodes: (keyword: string) => string | null;
  clearSelection: () => void;
}

export function useSigmaGraph({
  containerRef,
  nodes,
  edges,
  layout: initialLayout = 'forceatlas2',
  showLabels = true,
  onNodeClick,
  onEdgeClick,
  onCanvasClick,
}: UseSigmaGraphOptions): UseSigmaGraphReturn {
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [currentLayout, setCurrentLayout] = useState<SigmaLayoutType>(initialLayout);
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;
  const onCanvasClickRef = useRef(onCanvasClick);
  onCanvasClickRef.current = onCanvasClick;

  // ─── 构建图数据 ───
  const buildGraph = useCallback((nodeList: GraphNode[], edgeList: GraphEdge[]): Graph => {
    const g = new Graph({ multi: false, type: 'directed' });

    for (const n of nodeList) {
      const color = getNodeColor(n.type);
      const sideColor = getSideColor(n.side || 'neutral');
      g.addNode(n.id, {
        label: n.label,
        nodeType: n.type,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 12,
        color,
        borderColor: sideColor,
        type: getNodeShapeSigma(n.type),
        ...n.properties,
      });
    }

    for (const e of edgeList) {
      if (g.hasNode(e.source) && g.hasNode(e.target)) {
        const style = getEdgeStyle(e.type);
        g.addEdge(e.source, e.target, {
          edgeType: e.type,
          label: e.label || e.type,
          color: style.stroke,
          size: style.width,
          noArrow: e.type === 'located_at',
        });
      }
    }

    return g;
  }, []);

  // ─── 应用布局 ───
  const applyLayout = useCallback((g: Graph, layoutType: SigmaLayoutType) => {
    switch (layoutType) {
      case 'force':
      case 'forceatlas2': {
        try {
          const settings = forceAtlas2.inferSettings(g);
          forceAtlas2.assign(g, { iterations: 100, settings });
        } catch {
          // 降级：随机布局
          g.forEachNode((node) => {
            g.setNodeAttribute(node, 'x', Math.random() * 500);
            g.setNodeAttribute(node, 'y', Math.random() * 500);
          });
        }
        break;
      }
      case 'circular': {
        try {
          circularLayout.assign(g);
        } catch { /* ignore */ }
        break;
      }
      case 'grid': {
        // grid 需要手动排列
        const nodeCount = g.order;
        const cols = Math.ceil(Math.sqrt(nodeCount));
        let idx = 0;
        g.forEachNode((node) => {
          g.setNodeAttribute(node, 'x', (idx % cols) * 80);
          g.setNodeAttribute(node, 'y', Math.floor(idx / cols) * 80);
          idx++;
        });
        break;
      }
      case 'radial': {
        // 使用 circular 作为近似
        try {
          circularLayout.assign(g);
        } catch { /* ignore */ }
        break;
      }
    }
  }, []);

  // ─── 初始化 Sigma 实例 ───
  useEffect(() => {
    const container = containerRef.current;
    if (!container || nodes.length === 0) return;

    // 检查容器是否有有效尺寸，避免 Sigma 报 "Container has no width" 错误
    const rect = container.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const g = buildGraph(nodes, edges);
    applyLayout(g, currentLayout);
    graphRef.current = g;

    const sigma = new Sigma(g, container, {
      renderLabels: showLabels,
      renderEdgeLabels: false,
      labelRenderedSizeThreshold: 6,
      minCameraRatio: 0.1,
      maxCameraRatio: 10,
      defaultNodeColor: '#999',
      defaultEdgeColor: '#ccc',
    });

    // 事件绑定
    sigma.on('clickNode', ({ node }) => {
      const n = nodes.find((item) => item.id === node);
      if (n) onNodeClickRef.current?.(n);
    });

    sigma.on('clickEdge', ({ edge }) => {
      const e = edges.find((item) => item.id === edge);
      if (e) onEdgeClickRef.current?.(e);
    });

    sigma.on('clickStage', () => {
      onCanvasClickRef.current?.();
    });

    // 缩放状态同步
    sigma.getCamera().on('updated', () => {
      const ratio = sigma.getCamera().ratio;
      setZoomLevel(Math.round((1 / ratio) * 100) / 100);
    });

    sigmaRef.current = sigma;

    // 初始 fitView
    setTimeout(() => {
      const camera = sigma.getCamera();
      camera.animate({ ratio: 1 }, { duration: 300 });
    }, 500);

    return () => {
      sigma.kill();
      sigmaRef.current = null;
      graphRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges]);

  // ─── 布局切换 ───
  const setLayout = useCallback((layoutType: SigmaLayoutType) => {
    const g = graphRef.current;
    if (!g) return;
    setCurrentLayout(layoutType);
    applyLayout(g, layoutType);
  }, [applyLayout]);

  // ─── 缩放控制 ───
  const zoomIn = useCallback(() => {
    const camera = sigmaRef.current?.getCamera();
    if (!camera) return;
    camera.animate({ ratio: camera.ratio / 1.3 }, { duration: 200 });
  }, []);

  const zoomOut = useCallback(() => {
    const camera = sigmaRef.current?.getCamera();
    if (!camera) return;
    camera.animate({ ratio: camera.ratio * 1.3 }, { duration: 200 });
  }, []);

  const fitView = useCallback(() => {
    const camera = sigmaRef.current?.getCamera();
    if (!camera) return;
    camera.animate({ ratio: 1, x: 0.5, y: 0.5 }, { duration: 400 });
  }, []);

  const resetZoom = useCallback(() => {
    const camera = sigmaRef.current?.getCamera();
    if (!camera) return;
    camera.animate({ ratio: 1 }, { duration: 200 });
  }, []);

  // ─── 搜索定位 ───
  const focusNode = useCallback((nodeId: string) => {
    const sigma = sigmaRef.current;
    const g = graphRef.current;
    if (!sigma || !g || !g.hasNode(nodeId)) return;
    const attrs = g.getNodeAttributes(nodeId);
    const camera = sigma.getCamera();
    camera.animate({ x: attrs.x, y: attrs.y, ratio: 0.5 }, { duration: 300 });
  }, []);

  const searchNodes = useCallback((keyword: string): string | null => {
    const g = graphRef.current;
    if (!g || !keyword.trim()) return null;
    const kw = keyword.trim().toLowerCase();
    let found: string | null = null;
    g.forEachNode((node) => {
      if (found) return;
      const label = (g.getNodeAttribute(node, 'label') || '').toLowerCase();
      if (label.includes(kw)) {
        found = node;
      }
    });
    if (found) focusNode(found);
    return found;
  }, [focusNode]);

  // ─── 清除选中 ───
  const clearSelection = useCallback(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    // 重置 reducer — 传 null 清除自定义 reducer
    sigma.setSetting('nodeReducer', null as unknown as Sigma['settings']['nodeReducer']);
    sigma.setSetting('edgeReducer', null as unknown as Sigma['settings']['edgeReducer']);
  }, []);

  return {
    sigmaRef,
    graphRef,
    zoomLevel,
    setLayout,
    zoomIn,
    zoomOut,
    fitView,
    resetZoom,
    focusNode,
    searchNodes,
    clearSelection,
  };
}
