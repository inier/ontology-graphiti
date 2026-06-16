/**
 * GraphView — 图谱原子层组件
 *
 * 支持 Sigma.js（全局浏览）和 Cytoscape.js（局部操作）双引擎
 * 根据引擎类型自动选择对应的 hook 管理生命周期
 */
import type { FC, CSSProperties, ReactNode } from 'react';
import { useRef } from 'react';
import type Sigma from 'sigma';
import type Graph from 'graphology';
import type { GraphEngine, GraphNode, GraphEdge, SigmaLayoutType, CytoscapeLayoutType, NodeStyleConfig, EdgeStyleConfig } from '../types';
import { useSigmaGraph } from '../hooks/useSigmaGraph';
import { useCytoscapeGraph } from '../hooks/useCytoscapeGraph';

// ─── API 类型 ───

export interface GraphViewApi {
  engine: GraphEngine;
  zoomLevel: number;
  setLayout: (layout: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  resetZoom: () => void;
  focusNode: (nodeId: string) => void;
  searchNodes: (keyword: string) => string | null;
  selectNode?: (nodeId: string) => void;
  clearSelection: () => void;
  exportPng?: () => string | null;
  /** Sigma 实例 ref（仅 sigma 引擎可用，通过 .current 取值保证实时性） */
  sigmaRef?: React.RefObject<Sigma | null>;
  /** Graphology 实例 ref（仅 sigma 引擎可用，通过 .current 取值保证实时性） */
  graphRef?: React.RefObject<Graph | null>;
}

// ─── Props ───

interface GraphViewBaseProps {
  /** 引擎类型 */
  engine?: GraphEngine;
  /** 节点数据 */
  nodes: GraphNode[];
  /** 边数据 */
  edges: GraphEdge[];
  /** 容器样式 */
  className?: string;
  style?: CSSProperties;
  /** 节点点击回调 */
  onNodeClick?: (node: GraphNode) => void;
  /** 边点击回调 */
  onEdgeClick?: (edge: GraphEdge) => void;
  /** 画布点击回调 */
  onCanvasClick?: () => void;
  /** 子组件（工具栏、控件等通过 function children 获取图谱实例） */
  children?: ReactNode | ((api: GraphViewApi) => ReactNode);
}

interface SigmaGraphViewProps extends GraphViewBaseProps {
  engine?: 'sigma';
  layout?: SigmaLayoutType;
  showLabels?: boolean;
}

interface CytoscapeGraphViewProps extends GraphViewBaseProps {
  engine: 'cytoscape';
  layout?: CytoscapeLayoutType;
  nodeStyleMap?: Record<string, NodeStyleConfig>;
  edgeStyleMap?: Record<string, EdgeStyleConfig>;
  dagreRankDir?: 'TB' | 'BT' | 'LR' | 'RL';
}

export type GraphViewProps = SigmaGraphViewProps | CytoscapeGraphViewProps;

// ─── Sigma 引擎视图 ───

const SigmaGraphView: FC<SigmaGraphViewProps> = ({
  nodes,
  edges,
  layout = 'forceatlas2',
  showLabels = true,
  onNodeClick,
  onEdgeClick,
  onCanvasClick,
  className,
  style,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const {
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
  } = useSigmaGraph({
    containerRef,
    nodes,
    edges,
    layout,
    showLabels,
    onNodeClick,
    onEdgeClick,
    onCanvasClick,
  });

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%', ...style }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {typeof children === 'function'
        ? children({
            engine: 'sigma',
            zoomLevel,
            setLayout: (l: string) => setLayout(l as SigmaLayoutType),
            zoomIn,
            zoomOut,
            fitView,
            resetZoom,
            focusNode,
            searchNodes,
            clearSelection,
            sigmaRef,
            graphRef,
          })
        : children}
    </div>
  );
};

// ─── Cytoscape 引擎视图 ───

const CytoscapeGraphView: FC<CytoscapeGraphViewProps> = ({
  nodes,
  edges,
  layout = 'dagre',
  nodeStyleMap,
  edgeStyleMap,
  dagreRankDir = 'TB',
  onNodeClick,
  onEdgeClick,
  onCanvasClick,
  className,
  style,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const {
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
  } = useCytoscapeGraph({
    containerRef,
    nodes,
    edges,
    layout,
    nodeStyleMap,
    edgeStyleMap,
    dagreRankDir,
    onNodeClick,
    onEdgeClick,
    onCanvasClick,
  });

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%', ...style }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {typeof children === 'function'
        ? children({
            engine: 'cytoscape',
            zoomLevel,
            setLayout: (l: string) => setLayout(l as CytoscapeLayoutType),
            zoomIn,
            zoomOut,
            fitView,
            resetZoom,
            focusNode,
            searchNodes,
            selectNode,
            clearSelection,
            exportPng,
          })
        : children}
    </div>
  );
};

// ─── 主组件 ───

const GraphView: FC<GraphViewProps> = (props) => {
  if (props.engine === 'cytoscape') {
    return <CytoscapeGraphView {...props} />;
  }
  return <SigmaGraphView {...props} />;
};

export default GraphView;
