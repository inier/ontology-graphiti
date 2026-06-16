/**
 * GraphCanvas — 通用图谱浏览层（Sigma.js 引擎）
 *
 * 合并了原 GraphCanvas + OntologySemanticNetwork 的能力
 * 支持：5种布局、搜索定位、类型筛选、审计过滤、Minimap、LOD、版本切换
 */
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Card, Empty, Space, Tag } from 'antd';
import GraphView from './GraphView';
import type { GraphViewApi } from './GraphView';
import type { GraphNode, GraphEdge, SigmaLayoutType, NodeStyleConfig, EdgeStyleConfig } from '../types';
import { SIGMA_LAYOUT_OPTIONS } from '../types';
import { GraphToolbar } from './GraphToolbar';
import { GraphControls } from './GraphControls';
import { MinimapPanel } from './MinimapPanel';

const AUDIT_KEYWORDS = new Set(['AuditLog', 'AuditUser', 'AuditResource', 'AuditService']);
function isAuditType(t: string) { return AUDIT_KEYWORDS.has(t); }

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** 节点样式映射（固定类型着色），不传则用哈希自动着色 */
  nodeStyleMap?: Record<string, NodeStyleConfig>;
  /** 边样式映射 */
  edgeStyleMap?: Record<string, EdgeStyleConfig>;
  /** 侧面板 slot */
  detailPanel?: React.ReactNode;
  /** 图例 slot */
  legend?: React.ReactNode;
  /** 节点点击回调 */
  onNodeClick?: (node: GraphNode) => void;
  /** 边点击回调 */
  onEdgeClick?: (edge: GraphEdge) => void;
  /** 刷新回调 */
  onRefresh?: () => void;
  /** 版本列表 */
  versions?: Array<{
    version_id: string;
    created_at: string;
    entity_count: number;
    relation_count: number;
    commit_message?: string;
    event_count?: number;
  }>;
  currentVersion?: string;
  onVersionChange?: (versionId: string) => void;
  versionsLoading?: boolean;
  /** 外部指定画布高度，不传则自适应 */
  height?: number | string;
}

export function GraphCanvas({
  nodes,
  edges,
  nodeStyleMap,
  edgeStyleMap,
  detailPanel,
  legend,
  onNodeClick,
  onEdgeClick,
  onRefresh,
  versions,
  currentVersion,
  onVersionChange,
  versionsLoading,
  height: externalHeight,
}: GraphCanvasProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<GraphViewApi | null>(null);
  const [layout, setLayout] = useState<SigmaLayoutType>('forceatlas2');
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [showAudit, setShowAudit] = useState(false);
  const [canvasHeight, setCanvasHeight] = useState<number | string>(() =>
    externalHeight ?? (typeof window !== 'undefined' ? window.innerHeight - 200 : 700)
  );
  const [minimapOpen, setMinimapOpen] = useState(false);

  // ─── 自适应高度 ───
  useEffect(() => {
    if (externalHeight !== undefined) {
      setCanvasHeight(externalHeight);
      return;
    }
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const updateHeight = () => {
      const rect = wrapper.getBoundingClientRect();
      const available = window.innerHeight - rect.top - 16 * 2 - 64 - 8;
      setCanvasHeight(Math.max(400, available));
    };
    updateHeight();
    const ro = new ResizeObserver(updateHeight);
    ro.observe(wrapper);
    window.addEventListener('resize', updateHeight);
    return () => { ro.disconnect(); window.removeEventListener('resize', updateHeight); };
  }, [externalHeight]);

  // ─── 实体类型列表 ───
  const entityTypes = useMemo(() => {
    const typeSet = new Set<string>();
    nodes.forEach((n) => typeSet.add(n.type));
    return Array.from(typeSet).sort();
  }, [nodes]);

  // ─── 过滤 ───
  const filteredNodes = useMemo(() => {
    let result = nodes;
    if (!showAudit) result = result.filter((n) => !isAuditType(n.type));
    if (filterType !== 'all') result = result.filter((n) => n.type === filterType);
    return result;
  }, [nodes, filterType, showAudit]);

  const filteredEdges = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    return edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
  }, [edges, filteredNodes]);

  // ─── 搜索 ───
  const handleSearch = useCallback((kw: string) => {
    return apiRef.current?.searchNodes(kw) ?? null;
  }, []);

  // ─── 布局切换 ───
  const handleLayoutChange = useCallback((newLayout: string) => {
    setLayout(newLayout as SigmaLayoutType);
    apiRef.current?.setLayout(newLayout);
  }, []);

  // ─── 缩放控制 ───
  const handleZoomIn = useCallback(() => apiRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => apiRef.current?.zoomOut(), []);
  const handleCenterView = useCallback(() => apiRef.current?.fitView(), []);
  const handleZoomReset = useCallback(() => apiRef.current?.resetZoom(), []);

  // ─── 搜索文本变化时执行搜索 ───
  useEffect(() => {
    if (searchText.trim()) {
      apiRef.current?.searchNodes(searchText);
    } else {
      apiRef.current?.clearSelection();
    }
  }, [searchText]);

  // ─── 空数据 ───
  if (nodes.length === 0) {
    return (
      <Card style={{ borderRadius: 8 }}>
        <div style={{ height: canvasHeight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无图谱数据，请先添加对象类型和关系类型" />
        </div>
      </Card>
    );
  }

  return (
    <div ref={wrapperRef} style={{ textAlign: 'left' }}>
      <Card style={{ borderRadius: 8 }} styles={{ body: { padding: 0 } }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
          <GraphToolbar
            onRefresh={onRefresh}
            layout={layout}
            onLayoutChange={handleLayoutChange}
            searchText={searchText}
            onSearchChange={setSearchText}
            filterType={filterType}
            onFilterChange={setFilterType}
            entityTypes={entityTypes}
            versions={versions}
            currentVersion={currentVersion}
            onVersionChange={onVersionChange}
            versionsLoading={versionsLoading}
            showAudit={showAudit}
            onShowAuditChange={setShowAudit}
          />
        </div>

        <div style={{ position: 'relative', height: canvasHeight, overflow: 'hidden' }}>
          <GraphView
            engine="sigma"
            nodes={filteredNodes}
            edges={filteredEdges}
            layout={layout}
            showLabels={filteredNodes.length <= 200}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onCanvasClick={() => apiRef.current?.clearSelection()}
            style={{ height: '100%', background: '#f5f7fa' }}
          >
            {(api: GraphViewApi) => {
              apiRef.current = api;
              return null;
            }}
          </GraphView>

          {/* 缩放控件 + Minimap */}
          <div style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 10, display: 'flex', flexDirection: 'row-reverse', alignItems: 'flex-end' }}>
            <GraphControls
              zoomLevel={apiRef.current?.zoomLevel ?? 1}
              minimapOpen={minimapOpen}
              onCenterView={handleCenterView}
              onZoomIn={handleZoomIn}
              onZoomOut={handleZoomOut}
              onZoomReset={handleZoomReset}
              onToggleMinimap={() => setMinimapOpen((v) => !v)}
            />
            <MinimapPanel
              visible={minimapOpen}
              sigmaRef={apiRef.current?.sigmaRef}
              graphRef={apiRef.current?.graphRef}
            />
          </div>

          {/* 图例 */}
          {legend && (
            <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10 }}>
              {legend}
            </div>
          )}
        </div>

        {/* 侧面板 */}
        {detailPanel}

        {/* 底部状态栏 */}
        <div style={{ marginTop: 0, padding: '8px 16px', fontSize: 12, color: '#8c8c8c', borderTop: '1px solid #f0f0f0' }}>
          <Space size={16}>
            <span>滚轮缩放 · 拖动画布 · 点击节点聚焦关联</span>
            <span>节点: {filteredNodes.length} · 关系: {filteredEdges.length}</span>
            {filterType !== 'all' && (
              <Tag color="blue">已筛选: {filterType} ({filteredNodes.length}个)</Tag>
            )}
          </Space>
        </div>
      </Card>
    </div>
  );
}
