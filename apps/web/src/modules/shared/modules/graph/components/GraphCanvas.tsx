/**
 * GraphCanvas — 通用图谱浏览层（Sigma.js 引擎）
 *
 * 合并了原 GraphCanvas + OntologySemanticNetwork 的能力
 * 支持：5种布局、搜索定位、类型筛选、审计过滤、Minimap、LOD、版本切换
 * 增强：最短路径搜索、社区发现、节点拖拽、选中高亮、全屏模式、键盘快捷键
 */
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Empty, Space, Tag, Button, Tooltip, message } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { 
  FullscreenOutlined, 
  FullscreenExitOutlined, 
  TeamOutlined, 
  UndoOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import GraphView from './GraphView';
import type { GraphViewApi } from './GraphView';
import type { GraphNode, GraphEdge, SigmaLayoutType, NodeStyleConfig, EdgeStyleConfig } from '../types';
import { SIGMA_LAYOUT_OPTIONS } from '../types';
import { GraphToolbar } from './GraphToolbar';
import { GraphControls } from './GraphControls';
import { MinimapPanel } from './MinimapPanel';
import { PathSearchPanel } from './PathSearchPanel';
import { GraphTooltip } from './GraphTooltip';

const AUDIT_KEYWORDS = new Set(['AuditLog', 'AuditUser', 'AuditResource', 'AuditService']);
function isAuditType(t: string) { return AUDIT_KEYWORDS.has(t); }

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  nodeStyleMap?: Record<string, NodeStyleConfig>;
  edgeStyleMap?: Record<string, EdgeStyleConfig>;
  detailPanel?: React.ReactNode;
  legend?: React.ReactNode;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onRefresh?: () => void;
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
  const [fullscreen, setFullscreen] = useState(false);
  const [showPathSearch, setShowPathSearch] = useState(false);
  const [communityMode, setCommunityMode] = useState(false);
  const [tooltipData, setTooltipData] = useState<{ type: 'node' | 'edge'; data: GraphNode | GraphEdge; position: { x: number; y: number } } | null>(null);

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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key.toLowerCase()) {
          case 'f':
            e.preventDefault();
            setShowPathSearch(prev => !prev);
            break;
          case '0':
            e.preventDefault();
            apiRef.current?.resetZoom();
            break;
          case ']':
            e.preventDefault();
            apiRef.current?.zoomIn();
            break;
          case '[':
            e.preventDefault();
            apiRef.current?.zoomOut();
            break;
        }
      }
      switch (e.key) {
        case 'Escape':
          if (fullscreen) {
            handleFullscreen();
          }
          if (tooltipData) {
            setTooltipData(null);
          }
          apiRef.current?.clearSelection();
          break;
        case ' ':
          e.preventDefault();
          apiRef.current?.fitView();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [fullscreen, tooltipData]);

  const entityTypes = useMemo(() => {
    const typeSet = new Set<string>();
    nodes.forEach((n) => typeSet.add(n.type));
    return Array.from(typeSet).sort();
  }, [nodes]);

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

  const handleSearch = useCallback((kw: string) => {
    return apiRef.current?.searchNodes(kw) ?? null;
  }, []);

  const handleLayoutChange = useCallback((newLayout: string) => {
    setLayout(newLayout as SigmaLayoutType);
    apiRef.current?.setLayout(newLayout);
  }, []);

  const handleZoomIn = useCallback(() => apiRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => apiRef.current?.zoomOut(), []);
  const handleCenterView = useCallback(() => apiRef.current?.fitView(), []);
  const handleZoomReset = useCallback(() => apiRef.current?.resetZoom(), []);

  useEffect(() => {
    if (searchText.trim()) {
      apiRef.current?.searchNodes(searchText);
    } else {
      apiRef.current?.clearSelection();
    }
  }, [searchText]);

  const handleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
      setFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const handleCommunityToggle = useCallback(() => {
    if (!communityMode) {
      const count = apiRef.current?.applyCommunityColoring?.();
      if (count !== undefined && count > 0) {
        setCommunityMode(true);
        message.success(`社区发现完成，共识别 ${count} 个社区`);
      } else {
        message.warning('社区发现失败');
      }
    } else {
      apiRef.current?.enableCommunityMode?.(false);
      setCommunityMode(false);
      message.info('已退出社区着色模式');
    }
  }, [communityMode]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    apiRef.current?.highlightNode?.(node.id);
    onNodeClick?.(node);
  }, [onNodeClick]);

  const handleCanvasClick = useCallback(() => {
    apiRef.current?.clearSelection();
    setTooltipData(null);
  }, []);

  const handleHover = useCallback((data: { type: 'node' | 'edge'; data: GraphNode | GraphEdge; position: { x: number; y: number } }) => {
    setTooltipData(data);
  }, []);

  const handleHoverEnd = useCallback(() => {
    setTooltipData(null);
  }, []);

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
    <div ref={wrapperRef} style={{ textAlign: 'left', height: fullscreen ? '100vh' : 'auto' }}>
      <Card style={{ borderRadius: 8, height: fullscreen ? '100vh' : 'auto' }} styles={{ body: { padding: 0 } }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ flex: 1 }}>
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

          <Space size="middle">
            <Tooltip title="最短路径搜索 (Ctrl+F)">
              <Button
                type={showPathSearch ? 'primary' : 'default'}
                icon={<SearchOutlined />}
                onClick={() => setShowPathSearch(!showPathSearch)}
              >
                路径搜索
              </Button>
            </Tooltip>

            <Tooltip title="社区发现">
              <Button
                type={communityMode ? 'primary' : 'default'}
                icon={<TeamOutlined />}
                onClick={handleCommunityToggle}
              >
                {communityMode ? '退出社区' : '社区发现'}
              </Button>
            </Tooltip>

            <Tooltip title="重置视图 (Ctrl+0)">
              <Button
                icon={<UndoOutlined />}
                onClick={() => {
                  apiRef.current?.clearSelection();
                  apiRef.current?.resetZoom();
                  setCommunityMode(false);
                }}
              >
                重置
              </Button>
            </Tooltip>

            <Tooltip title={fullscreen ? '退出全屏 (Esc)' : '全屏'}>
              <Button
                icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                onClick={handleFullscreen}
              />
            </Tooltip>
          </Space>
        </div>

        {showPathSearch && (
          <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <PathSearchPanel
              nodes={filteredNodes}
              onSearch={(source, target) => apiRef.current?.highlightPath?.(source, target) ?? false}
              onClear={() => apiRef.current?.clearSelection()}
            />
          </div>
        )}

        <div style={{ position: 'relative', height: fullscreen ? 'calc(100vh - 120px)' : canvasHeight, overflow: 'hidden' }}>
          <GraphView
            engine="sigma"
            nodes={filteredNodes}
            edges={filteredEdges}
            layout={layout}
            showLabels={filteredNodes.length <= 200}
            onNodeClick={handleNodeClick}
            onEdgeClick={onEdgeClick}
            onCanvasClick={handleCanvasClick}
            onHover={handleHover}
            onHoverEnd={handleHoverEnd}
            style={{ height: '100%', background: '#f5f7fa' }}
          >
            {(api: GraphViewApi) => {
              apiRef.current = api;
              return null;
            }}
          </GraphView>

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

          {legend && (
            <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10 }}>
              {legend}
            </div>
          )}
        </div>

        {detailPanel}

        <div style={{ marginTop: 0, padding: '8px 16px', fontSize: 12, color: '#8c8c8c', borderTop: '1px solid #f0f0f0' }}>
          <Space size={16}>
            <span>滚轮缩放 · 拖动画布 · 点击节点聚焦关联</span>
            <span>节点: {filteredNodes.length} · 关系: {filteredEdges.length}</span>
            {filterType !== 'all' && (
              <Tag color="blue">已筛选: {filterType} ({filteredNodes.length}个)</Tag>
            )}
            {communityMode && (
              <Tag color="purple">社区着色模式</Tag>
            )}
            <span style={{ marginLeft: 'auto' }}>
              快捷键: <kbd>Ctrl+F</kbd> 搜索路径 · <kbd>空格</kbd> 适应视图 · <kbd>Esc</kbd> 清除选择
            </span>
          </Space>
        </div>
      </Card>

      <GraphTooltip
        tooltipData={tooltipData}
        onClose={() => setTooltipData(null)}
      />
    </div>
  );
}