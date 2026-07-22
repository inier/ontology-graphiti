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
  sigmaRef?: React.RefObject<Sigma | null>;
  graphRef?: React.RefObject<Graph | null>;
  highlightPath?: (source: string, target: string) => boolean;
  highlightNode?: (nodeId: string) => void;
  applyCommunityColoring?: () => number;
  enableCommunityMode?: (enable: boolean) => void;
}

// ─── Props ───

interface GraphViewBaseProps {
  engine?: GraphEngine;
  nodes: GraphNode[];
  edges: GraphEdge[];
  className?: string;
  style?: CSSProperties;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onCanvasClick?: () => void;
  onHover?: (data: { type: 'node' | 'edge'; data: GraphNode | GraphEdge; position: { x: number; y: number } }) => void;
  onHoverEnd?: () => void;
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
  onHover,
  onHoverEnd,
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
    highlightPath,
    highlightNode,
    applyCommunityColoring,
    enableCommunityMode,
  } = useSigmaGraph({
    containerRef,
    nodes,
    edges,
    layout,
    showLabels,
    onNodeClick,
    onEdgeClick,
    onCanvasClick,
    onHover,
    onHoverEnd,
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
            highlightPath,
            highlightNode,
            applyCommunityColoring,
            enableCommunityMode,
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
