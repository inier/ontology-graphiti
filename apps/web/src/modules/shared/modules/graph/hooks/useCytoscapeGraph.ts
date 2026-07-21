/**
 * useCytoscapeGraph — Cytoscape.js 图谱实例生命周期管理 hook
 *
 * 负责：创建/销毁 Cytoscape 实例、增量更新、布局切换、事件绑定、选中高亮
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import type { GraphNode, GraphEdge, CytoscapeLayoutType, NodeStyleConfig, EdgeStyleConfig } from '../types';
import { getNodeColor, getSideColor, getNodeShapeCytoscape, getEdgeStyle, ZOOM_STEP, ZOOM_MIN, ZOOM_MAX } from '../utils/graphStyles';

// 注册扩展
cytoscape.use(dagre);
cytoscape.use(coseBilkent);

interface UseCytoscapeGraphOptions {
  containerRef: React.RefObject<HTMLDivElement | null>;
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout?: CytoscapeLayoutType;
  /** 节点样式映射（固定类型着色），不传则用哈希自动着色 */
  nodeStyleMap?: Record<string, NodeStyleConfig>;
  /** 边样式映射 */
  edgeStyleMap?: Record<string, EdgeStyleConfig>;
  /** dagre 布局方向 */
  dagreRankDir?: 'TB' | 'BT' | 'LR' | 'RL';
  /** 节点点击回调 */
  onNodeClick?: (node: GraphNode) => void;
  /** 边点击回调 */
  onEdgeClick?: (edge: GraphEdge) => void;
  /** 画布点击回调 */
  onCanvasClick?: () => void;
}

interface UseCytoscapeGraphReturn {
  cy: cytoscape.Core | null;
  zoomLevel: number;
  setLayout: (layout: CytoscapeLayoutType) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  resetZoom: () => void;
  focusNode: (nodeId: string) => void;
  searchNodes: (keyword: string) => string | null;
  selectNode: (nodeId: string) => void;
  clearSelection: () => void;
  exportPng: () => string | null;
}

export function useCytoscapeGraph({
  containerRef,
  nodes,
  edges,
  layout: initialLayout = 'dagre',
  nodeStyleMap,
  edgeStyleMap,
  dagreRankDir = 'TB',
  onNodeClick,
  onEdgeClick,
  onCanvasClick,
}: UseCytoscapeGraphOptions): UseCytoscapeGraphReturn {
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [currentLayout, setCurrentLayout] = useState<CytoscapeLayoutType>(initialLayout);
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;
  const onCanvasClickRef = useRef(onCanvasClick);
  onCanvasClickRef.current = onCanvasClick;

  // ─── 构建样式表 ───
  const buildStylesheet = useCallback(() => {
    const styles: Array<{ selector: string; style: Record<string, unknown> }> = [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': 11,
          color: '#333',
          'text-background-color': '#fff',
          'text-background-opacity': 0.6,
          'text-background-padding': '2px',
          cursor: 'pointer',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': '#ccc',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': '#ccc',
          'arrow-scale': 0.8,
          'curve-style': 'bezier',
          'font-size': 9,
          color: '#8c8c8c',
          'text-background-color': '#fff',
          'text-background-opacity': 0.7,
          'text-background-padding': '1px',
        },
      },
      // 选中态
      {
        selector: 'node.selected',
        style: {
          'border-width': 3,
          'border-color': '#ff4d4f',
          'font-size': 13,
          'font-weight': 'bold',
          color: '#ff4d4f',
          'z-index': 10,
        },
      },
      {
        selector: 'node.highlight',
        style: {
          'border-width': 3,
          'border-color': '#1890ff',
          'font-weight': 'bold',
          color: '#1890ff',
          'z-index': 9,
        },
      },
      {
        selector: 'node.dim',
        style: {
          opacity: 0.3,
        },
      },
      {
        selector: 'edge.highlight',
        style: {
          width: 2.5,
          'line-color': '#1890ff',
          'target-arrow-color': '#1890ff',
          'font-size': 11,
          color: '#1890ff',
          'z-index': 9,
        },
      },
      {
        selector: 'edge.dim',
        style: {
          opacity: 0.15,
        },
      },
    ];

    // 按节点类型注册样式
    if (nodeStyleMap) {
      for (const [type, config] of Object.entries(nodeStyleMap)) {
        styles.push({
          selector: `node[nodeType="${type}"]`,
          style: {
            'background-color': config.fill,
            'border-color': config.stroke,
            'border-width': 2,
            shape: config.shape,
            width: config.size ?? 50,
            height: config.size ?? 50,
          },
        });
      }
    } else {
      // 哈希自动着色：通过 data() 函数在元素上设置颜色
      styles.push({
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'border-color': 'data(borderColor)',
          'border-width': 2,
          shape: 'data(shape)',
          width: 36,
          height: 36,
        },
      });
    }

    // 按边类型注册样式
    if (edgeStyleMap) {
      for (const [type, config] of Object.entries(edgeStyleMap)) {
        const edgeStyle: Record<string, unknown> = {
          'line-color': config.stroke,
          width: config.width ?? 1.5,
          'target-arrow-color': config.stroke,
        };
        if (config.lineDash && config.lineDash.length > 0) {
          edgeStyle['line-style'] = 'dashed';
        }
        if (config.arrow === false) {
          edgeStyle['target-arrow-shape'] = 'none';
        }
        styles.push({
          selector: `edge[edgeType="${type}"]`,
          style: edgeStyle,
        });
      }
    } else {
      styles.push({
        selector: 'edge',
        style: {
          'line-color': 'data(color)',
          width: 'data(width)',
        },
      });
    }

    return styles;
  }, [nodeStyleMap, edgeStyleMap]);

  // ─── 构建 Cytoscape 元素 ───
  const buildElements = useCallback((nodeList: GraphNode[], edgeList: GraphEdge[]): cytoscape.ElementDefinition[] => {
    const elements: cytoscape.ElementDefinition[] = [];

    const validNodes = nodeList.filter(n => n.id != null && typeof n.id === 'string' && n.id.trim() !== '');
    const validNodeIds = new Set(validNodes.map(n => n.id));

    for (const n of validNodes) {
      const nodeData: Record<string, unknown> = {
        id: n.id,
        label: n.label,
        nodeType: n.type,
        ...n.properties,
      };

      if (!nodeStyleMap) {
        nodeData.color = getNodeColor(n.type);
        nodeData.borderColor = getSideColor(n.side || 'neutral');
        nodeData.shape = getNodeShapeCytoscape(n.type);
      }

      elements.push({ group: 'nodes', data: nodeData });
    }

    for (const e of edgeList) {
      if (e.source == null || e.target == null || !validNodeIds.has(e.source) || !validNodeIds.has(e.target)) {
        continue;
      }
      const edgeData: Record<string, unknown> = {
        id: e.id,
        source: e.source,
        target: e.target,
        edgeType: e.type,
        label: e.label || e.type,
      };

      if (!edgeStyleMap) {
        const style = getEdgeStyle(e.type);
        edgeData.color = style.stroke;
        edgeData.width = style.width;
        if (e.type === 'located_at') {
          edgeData.noArrow = true;
        }
      }

      elements.push({ group: 'edges', data: edgeData });
    }

    return elements;
  }, [nodeStyleMap, edgeStyleMap]);

  // ─── 获取布局配置 ───
  const getLayoutConfig = useCallback((layoutType: CytoscapeLayoutType): cytoscape.LayoutOptions => {
    switch (layoutType) {
      case 'dagre':
        return {
          name: 'dagre',
          rankDir: dagreRankDir,
          nodeSep: 30,
          rankSep: 60,
          animate: false,
        } as cytoscape.LayoutOptions;
      case 'cose-bilkent':
        return {
          name: 'cose-bilkent',
          animate: false,
          nodeRepulsion: 300,
          idealEdgeLength: 120,
        } as cytoscape.LayoutOptions;
      case 'circle':
        return { name: 'circle', animate: false };
      case 'grid':
        return { name: 'grid', animate: false };
      case 'concentric':
        return { name: 'concentric', animate: false };
      case 'breadthfirst':
        return { name: 'breadthfirst', animate: false };
      default:
        return { name: 'dagre', rankDir: dagreRankDir, animate: false } as cytoscape.LayoutOptions;
    }
  }, [dagreRankDir]);

  // ─── 初始化 Cytoscape 实例 ───
  useEffect(() => {
    const container = containerRef.current;
    if (!container || nodes.length === 0) return;

    const elements = buildElements(nodes, edges);
    const stylesheet = buildStylesheet();

    const cy = cytoscape({
      container,
      elements,
      style: stylesheet as cytoscape.StylesheetStyle[],
      layout: getLayoutConfig(currentLayout),
      minZoom: ZOOM_MIN,
      maxZoom: ZOOM_MAX,
      boxSelectionEnabled: false,
    });

    // 事件绑定
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeId = node.id();
      const n = nodes.find((item) => item.id === nodeId);
      if (n) onNodeClickRef.current?.(n);
    });

    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      const edgeId = edge.id();
      const e = edges.find((item) => item.id === edgeId);
      if (e) onEdgeClickRef.current?.(e);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onCanvasClickRef.current?.();
      }
    });

    // 缩放状态同步
    cy.on('zoom', () => {
      setZoomLevel(Math.round(cy.zoom() * 100) / 100);
    });

    cyRef.current = cy;

    // 初始 fitView
    setTimeout(() => {
      cy.fit(undefined, 40);
      setZoomLevel(Math.round(cy.zoom() * 100) / 100);
    }, 300);

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, buildElements, buildStylesheet, getLayoutConfig]);

  // ─── 布局切换 ───
  const setLayout = useCallback((layoutType: CytoscapeLayoutType) => {
    const cy = cyRef.current;
    if (!cy) return;
    setCurrentLayout(layoutType);
    const layout = cy.layout(getLayoutConfig(layoutType));
    layout.run();
    setTimeout(() => cy.fit(undefined, 40), 500);
  }, [getLayoutConfig]);

  // ─── 缩放控制 ───
  const zoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() + ZOOM_STEP, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const zoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: Math.max(cy.zoom() - ZOOM_STEP, ZOOM_MIN), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const fitView = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.fit(undefined, 40);
  }, []);

  const resetZoom = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: 1, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  // ─── 搜索定位 ───
  const focusNode = useCallback((nodeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;
    const node = cy.$(`#${nodeId}`);
    if (node.length > 0) {
      cy.animate({ center: { eles: node } }, { duration: 300 });
      cy.zoom({ level: 1.5, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
    }
  }, []);

  const searchNodes = useCallback((keyword: string): string | null => {
    const cy = cyRef.current;
    if (!cy || !keyword.trim()) return null;
    const kw = keyword.trim().toLowerCase();
    const found = cy.nodes().filter((n) => {
      const label = (n.data('label') || '').toLowerCase();
      return label.includes(kw);
    });
    if (found.length > 0) {
      const nodeId = found.first().id();
      focusNode(nodeId);
      return nodeId;
    }
    return null;
  }, [focusNode]);

  // ─── 选中高亮 ───
  const selectNode = useCallback((nodeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    // 清除所有状态
    cy.elements().removeClass('selected highlight dim');

    const node = cy.$(`#${nodeId}`);
    if (node.length === 0) return;

    // 选中节点
    node.addClass('selected');

    // 高亮关联节点和边
    const connectedEdges = node.connectedEdges();
    const connectedNodes = connectedEdges.connectedNodes().not(node);

    connectedEdges.addClass('highlight');
    connectedNodes.addClass('highlight');

    // dim 其余
    cy.nodes().not(node).not(connectedNodes).addClass('dim');
    cy.edges().not(connectedEdges).addClass('dim');
  }, []);

  const clearSelection = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass('selected highlight dim');
  }, []);

  // ─── 导出 PNG ───
  const exportPng = useCallback((): string | null => {
    const cy = cyRef.current;
    if (!cy) return null;
    return cy.png({ output: 'blob' }) as unknown as string;
  }, []);

  return {
    cy: cyRef.current,
    zoomLevel,
    setLayout,
    zoomIn,
    zoomOut,
    fitView,
    resetZoom,
    focusNode,
    searchNodes,
    selectNode,
    clearSelection,
    exportPng,
  };
}
