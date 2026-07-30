/**
 * useSigmaGraph — Sigma.js 图谱实例生命周期管理 hook
 *
 * 负责：创建/销毁 Sigma 实例、增量更新图数据、布局切换、事件绑定
 * 增强功能：节点拖拽、选中高亮 reducer、最短路径搜索、社区发现着色、悬浮提示
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import Sigma from 'sigma';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import { circular as circularLayout } from 'graphology-layout';
import type { GraphNode, GraphEdge, SigmaLayoutType } from '../types';
import { getNodeColor, getSideColor, getNodeShapeSigma, getEdgeStyle, LOD_LABEL_THRESHOLD } from '../utils/graphStyles';
import { findShortestPath, detectCommunities } from '../utils/graphAlgo';

export interface HoverData {
  type: 'node' | 'edge';
  data: GraphNode | GraphEdge;
  position: { x: number; y: number };
}

interface UseSigmaGraphOptions {
  containerRef: React.RefObject<HTMLDivElement | null>;
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout?: SigmaLayoutType;
  showLabels?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onCanvasClick?: () => void;
  onHover?: (data: HoverData) => void;
  onHoverEnd?: () => void;
  enableDrag?: boolean;
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
  highlightPath: (source: string, target: string) => boolean;
  highlightNode: (nodeId: string) => void;
  applyCommunityColoring: () => number;
  enableCommunityMode: (enable: boolean) => void;
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
  onHover,
  onHoverEnd,
  enableDrag = true,
}: UseSigmaGraphOptions): UseSigmaGraphReturn {
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [currentLayout, setCurrentLayout] = useState<SigmaLayoutType>(initialLayout);
  const [communityMode, setCommunityMode] = useState(false);
  const [communityColors, setCommunityColors] = useState<Map<string, string>>(new Map());
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;
  const onCanvasClickRef = useRef(onCanvasClick);
  const onHoverRef = useRef(onHover);
  onHoverRef.current = onHover;
  const onHoverEndRef = useRef(onHoverEnd);
  onHoverEndRef.current = onHoverEnd;

  const buildGraph = useCallback((nodeList: GraphNode[], edgeList: GraphEdge[]): Graph => {
    const g = new Graph({ multi: false, type: 'directed' });

    const validNodes = nodeList.filter(n => n.id != null && typeof n.id === 'string' && n.id.trim() !== '');

    for (const n of validNodes) {
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
        originalColor: color,
        ...n.properties,
      });
    }

    for (const e of edgeList) {
      if (e.source == null || e.target == null) continue;
      const source = String(e.source).trim();
      const target = String(e.target).trim();
      if (!source || !target) continue;
      if (source === 'null' || source === 'undefined' || target === 'null' || target === 'undefined') continue;
      if (!g.hasNode(source) || !g.hasNode(target)) continue;
      const style = getEdgeStyle(e.type);
      g.addEdge(source, target, {
        edgeType: e.type,
        label: e.label || e.type,
        color: style.stroke,
        size: style.width,
        noArrow: e.type === 'located_at',
      }, e.id);
    }

    return g;
  }, []);

  const applyLayout = useCallback((g: Graph, layoutType: SigmaLayoutType) => {
    switch (layoutType) {
      case 'force':
      case 'forceatlas2': {
        try {
          const settings = forceAtlas2.inferSettings(g);
          forceAtlas2.assign(g, { iterations: 100, settings });
        } catch {
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
        try {
          circularLayout.assign(g);
        } catch { /* ignore */ }
        break;
      }
    }
  }, []);

  const applyCommunityColoringInternal = useCallback((g: Graph) => {
    const result = detectCommunities(g);
    const nodeColors = new Map<string, string>();

    // P0-C3 fix: communities 类型已从 Map 改为 plain object {[node: string]: number}
    // （见 graphAlgo.ts:17），这里改为对象索引访问，原 .get() 会抛 TypeError
    g.forEachNode((node) => {
      const communityId = result.communities[node];
      if (communityId !== undefined) {
        const color = result.communityColors.get(communityId) || '#999';
        g.setNodeAttribute(node, 'color', color);
        nodeColors.set(node, color);
      }
    });

    setCommunityColors(nodeColors);
    setCommunityMode(true);
    return result.communityCount;
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || nodes.length === 0) return;

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
      allowInvalidContainer: true,
      touchEnabled: true,
      mouseEnabled: true,
    });

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

    sigma.on('enterNode', ({ node, event }) => {
      const n = nodes.find((item) => item.id === node);
      if (n && event) {
        onHoverRef.current?.({
          type: 'node',
          data: n,
          position: { x: event.clientX, y: event.clientY },
        });
      }
    });

    sigma.on('leaveNode', () => {
      onHoverEndRef.current?.();
    });

    sigma.on('enterEdge', ({ edge, event }) => {
      const e = edges.find((item) => item.id === edge);
      if (e && event) {
        onHoverRef.current?.({
          type: 'edge',
          data: e,
          position: { x: event.clientX, y: event.clientY },
        });
      }
    });

    sigma.on('leaveEdge', () => {
      onHoverEndRef.current?.();
    });

    sigma.on('enterStage', () => {
      onHoverEndRef.current?.();
    });

    if (enableDrag) {
      let draggedNode: string | null = null;

      sigma.on('downNode', ({ node, event }) => {
        draggedNode = node;
        event?.preventDefault();
        event?.stopPropagation();
      });

      sigma.on('mousemove', ({ event }) => {
        if (!draggedNode || !event) return;

        const containerRect = container.getBoundingClientRect();
        const x = ((event.clientX - containerRect.left) / containerRect.width) * 2 - 1;
        const y = -((event.clientY - containerRect.top) / containerRect.height) * 2 + 1;

        const graphCoords = sigma.viewportToGraph({ x, y });
        g.setNodeAttribute(draggedNode, 'x', graphCoords.x);
        g.setNodeAttribute(draggedNode, 'y', graphCoords.y);
      });

      sigma.on('upNode', () => {
        draggedNode = null;
      });

      sigma.on('mouseup', () => {
        draggedNode = null;
      });
    }

    sigma.getCamera().on('updated', () => {
      const ratio = sigma.getCamera().ratio;
      setZoomLevel(Math.round((1 / ratio) * 100) / 100);
    });

    sigmaRef.current = sigma;

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

  const setLayout = useCallback((layoutType: SigmaLayoutType) => {
    const g = graphRef.current;
    if (!g) return;
    setCurrentLayout(layoutType);
    applyLayout(g, layoutType);
  }, [applyLayout]);

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

  const clearSelection = useCallback(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    sigma.setSetting('nodeReducer', null as unknown as Sigma['settings']['nodeReducer']);
    sigma.setSetting('edgeReducer', null as unknown as Sigma['settings']['edgeReducer']);

    if (communityMode) {
      const g = graphRef.current;
      if (g) {
        g.forEachNode((node) => {
          const color = communityColors.get(node) || getNodeColor(g.getNodeAttribute(node, 'nodeType') as string);
          g.setNodeAttribute(node, 'color', color);
        });
      }
    } else {
      const g = graphRef.current;
      if (g) {
        g.forEachNode((node) => {
          const originalColor = g.getNodeAttribute(node, 'originalColor') as string;
          g.setNodeAttribute(node, 'color', originalColor || '#999');
        });
      }
    }
  }, [communityMode, communityColors]);

  const highlightPath = useCallback((source: string, target: string): boolean => {
    const sigma = sigmaRef.current;
    const g = graphRef.current;
    if (!sigma || !g) return false;

    const result = findShortestPath(g, source, target);
    if (!result.pathFound) return false;

    const pathNodeSet = new Set(result.nodes);
    const pathEdgeSet = new Set(result.edges);

    sigma.setSetting('nodeReducer', (node, data) => ({
      ...data,
      size: pathNodeSet.has(node) ? (data.size || 12) * 1.5 : (data.size || 12) * 0.5,
      opacity: pathNodeSet.has(node) ? 1 : 0.2,
      color: pathNodeSet.has(node) ? '#FF6B6B' : data.color,
    }));

    sigma.setSetting('edgeReducer', (edge, data) => ({
      ...data,
      size: pathEdgeSet.has(edge) ? (data.size || 1) * 3 : (data.size || 1) * 0.3,
      opacity: pathEdgeSet.has(edge) ? 1 : 0.1,
      color: pathEdgeSet.has(edge) ? '#FF6B6B' : data.color,
    }));

    return true;
  }, []);

  const highlightNode = useCallback((nodeId: string) => {
    const sigma = sigmaRef.current;
    const g = graphRef.current;
    if (!sigma || !g || !g.hasNode(nodeId)) return;

    const neighbors = new Set<string>();
    const adjacentEdges = new Set<string>();

    g.forEachNeighbor(nodeId, (neighbor) => {
      neighbors.add(neighbor);
    });

    g.forEachEdge((edge, attributes, source, target) => {
      if (source === nodeId || target === nodeId) {
        adjacentEdges.add(edge);
      }
    });

    neighbors.add(nodeId);

    sigma.setSetting('nodeReducer', (node, data) => ({
      ...data,
      size: neighbors.has(node) ? (data.size || 12) * 1.3 : (data.size || 12) * 0.4,
      opacity: neighbors.has(node) ? 1 : 0.2,
      color: node === nodeId ? '#4ECDC4' : (neighbors.has(node) ? data.color : '#ccc'),
    }));

    sigma.setSetting('edgeReducer', (edge, data) => ({
      ...data,
      size: adjacentEdges.has(edge) ? (data.size || 1) * 2 : (data.size || 1) * 0.2,
      opacity: adjacentEdges.has(edge) ? 1 : 0.1,
    }));
  }, []);

  const applyCommunityColoring = useCallback(() => {
    const g = graphRef.current;
    if (!g) return 0;
    return applyCommunityColoringInternal(g);
  }, [applyCommunityColoringInternal]);

  const enableCommunityMode = useCallback((enable: boolean) => {
    setCommunityMode(enable);
    if (!enable) {
      const g = graphRef.current;
      if (g) {
        g.forEachNode((node) => {
          const originalColor = g.getNodeAttribute(node, 'originalColor') as string;
          g.setNodeAttribute(node, 'color', originalColor || '#999');
        });
      }
      setCommunityColors(new Map());
    } else {
      applyCommunityColoring();
    }
  }, [applyCommunityColoring]);

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
    highlightPath,
    highlightNode,
    applyCommunityColoring,
    enableCommunityMode,
  };
}