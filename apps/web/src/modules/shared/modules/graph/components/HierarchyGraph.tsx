/**
 * HierarchyGraph — 层级关系图谱层（Cytoscape.js 引擎）
 *
 * 合并了 InheritanceGraph + GoalLineage 的能力
 * 支持：dagre/force/circular 布局、节点选中高亮、边点击、搜索、导出PNG、侧面板 slot
 */
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Empty, Space, Tag, Select, Input, Button, Tooltip } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { ZoomInOutlined, ZoomOutOutlined, FullscreenOutlined, ExportOutlined, SearchOutlined } from '@ant-design/icons';
import GraphView from './GraphView';
import type { GraphViewApi } from './GraphView';
import type { GraphNode, GraphEdge, CytoscapeLayoutType, NodeStyleConfig, EdgeStyleConfig } from '../types';
import { CYTOSCAPE_LAYOUT_OPTIONS } from '../types';

// ─── Props ───

interface HierarchyGraphProps {
  /** 图谱标题 */
  title?: string;
  /** 节点数据 */
  nodes: GraphNode[];
  /** 边数据 */
  edges: GraphEdge[];
  /** 节点样式映射 */
  nodeStyleMap?: Record<string, NodeStyleConfig>;
  /** 边样式映射 */
  edgeStyleMap?: Record<string, EdgeStyleConfig>;
  /** dagre 布局方向 */
  dagreRankDir?: 'TB' | 'BT' | 'LR' | 'RL';
  /** 默认布局 */
  defaultLayout?: CytoscapeLayoutType;
  /** 侧面板 slot */
  detailPanel?: React.ReactNode;
  /** 图例 slot */
  legend?: React.ReactNode;
  /** 左侧过滤栏 slot */
  filterPanel?: React.ReactNode;
  /** 工具栏扩展按钮 slot */
  toolbarExtra?: React.ReactNode;
  /** 节点点击回调 */
  onNodeClick?: (node: GraphNode) => void;
  /** 边点击回调 */
  onEdgeClick?: (edge: GraphEdge) => void;
  /** 刷新回调 */
  onRefresh?: () => void;
  /** 图谱高度 */
  height?: number;
}

export function HierarchyGraph({
  title,
  nodes,
  edges,
  nodeStyleMap,
  edgeStyleMap,
  dagreRankDir = 'TB',
  defaultLayout = 'dagre',
  detailPanel,
  legend,
  filterPanel,
  toolbarExtra,
  onNodeClick,
  onEdgeClick,
  onRefresh,
  height = 600,
}: HierarchyGraphProps) {
  const apiRef = useRef<GraphViewApi | null>(null);
  const [layout, setLayout] = useState<CytoscapeLayoutType>(defaultLayout);
  const [searchText, setSearchText] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // ─── 布局切换 ───
  const handleLayoutChange = useCallback((newLayout: string) => {
    setLayout(newLayout as CytoscapeLayoutType);
    apiRef.current?.setLayout(newLayout);
  }, []);

  // ─── 搜索 ───
  useEffect(() => {
    if (searchText.trim()) {
      const found = apiRef.current?.searchNodes(searchText);
      if (found && apiRef.current?.selectNode) {
        apiRef.current.selectNode(found);
        setSelectedNodeId(found);
      }
    } else {
      apiRef.current?.clearSelection();
      setSelectedNodeId(null);
    }
  }, [searchText]);

  // ─── 节点点击 → 选中高亮 ───
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNodeId(node.id);
    if (apiRef.current?.selectNode) {
      apiRef.current.selectNode(node.id);
    }
    onNodeClick?.(node);
  }, [onNodeClick]);

  // ─── 画布点击 → 清除选中 ───
  const handleCanvasClick = useCallback(() => {
    setSelectedNodeId(null);
    apiRef.current?.clearSelection();
  }, []);

  // ─── 导出 PNG ───
  const handleExportPng = useCallback(() => {
    const dataUrl = apiRef.current?.exportPng?.();
    if (dataUrl) {
      const link = document.createElement('a');
      link.download = `${title || 'graph'}-${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    }
  }, [title]);

  // ─── 空数据 ───
  if (nodes.length === 0) {
    return (
      <Card style={{ borderRadius: 8 }}>
        <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无层级关系数据" />
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={title}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 0 } }}
      extra={
        <Space>
          <Input.Search
            placeholder="搜索节点"
            size="small"
            style={{ width: 160 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={(v) => setSearchText(v)}
            allowClear
          />
          <Select
            size="small"
            value={layout}
            onChange={handleLayoutChange}
            style={{ width: 100 }}
            options={[...CYTOSCAPE_LAYOUT_OPTIONS]}
          />
          <Tooltip title="放大">
            <Button size="small" icon={<ZoomInOutlined />} onClick={() => apiRef.current?.zoomIn()} />
          </Tooltip>
          <Tooltip title="缩小">
            <Button size="small" icon={<ZoomOutOutlined />} onClick={() => apiRef.current?.zoomOut()} />
          </Tooltip>
          <Tooltip title="适应视图">
            <Button size="small" icon={<FullscreenOutlined />} onClick={() => apiRef.current?.fitView()} />
          </Tooltip>
          <Tooltip title="导出PNG">
            <Button size="small" icon={<ExportOutlined />} onClick={handleExportPng} />
          </Tooltip>
          {onRefresh && (
            <Button size="small" onClick={onRefresh}>刷新</Button>
          )}
          {toolbarExtra}
        </Space>
      }
    >
      <div style={{ display: 'flex' }}>
        {/* 左侧过滤栏 */}
        {filterPanel && (
          <div style={{ width: 200, padding: 12, borderRight: '1px solid #f0f0f0' }}>
            {filterPanel}
          </div>
        )}

        {/* 图谱区域 */}
        <div style={{ flex: 1, position: 'relative' }}>
          <GraphView
            engine="cytoscape"
            nodes={nodes}
            edges={edges}
            layout={layout}
            nodeStyleMap={nodeStyleMap}
            edgeStyleMap={edgeStyleMap}
            dagreRankDir={dagreRankDir}
            onNodeClick={handleNodeClick}
            onEdgeClick={onEdgeClick}
            onCanvasClick={handleCanvasClick}
            style={{ height, background: '#fafafa' }}
          >
            {(api: GraphViewApi) => {
              apiRef.current = api;
              return null;
            }}
          </GraphView>

          {/* 图例 */}
          {legend && (
            <div style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10 }}>
              {legend}
            </div>
          )}
        </div>
      </div>

      {/* 侧面板 */}
      {detailPanel}

      {/* 底部状态栏 */}
      <div style={{ padding: '6px 16px', fontSize: 12, color: '#8c8c8c', borderTop: '1px solid #f0f0f0' }}>
        <Space size={16}>
          <span>节点: {nodes.length} · 关系: {edges.length}</span>
          {selectedNodeId && <Tag color="blue">已选中: {selectedNodeId}</Tag>}
        </Space>
      </div>
    </Card>
  );
}
