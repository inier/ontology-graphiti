import { useState, useEffect, useRef } from 'react';
import { Card, Row, Col, Drawer, Descriptions, Tag, Select, Space, Button, Table, Empty, Spin, message, Tooltip, Typography } from 'antd';
import {
  CheckCircleFilled,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  ExpandOutlined,
  ExportOutlined,
  FilterOutlined,
  SearchOutlined
} from '@ant-design/icons';
import { Graph } from '@antv/g6';
import { PageHeader } from '../../shared';

const { Text, Paragraph } = Typography;

export interface OntologyVersion {
  id: string;
  versionId: string;
  createdAt: Date;
  entityCount: number;
  relationCount: number;
  status: 'completed' | 'failed' | 'building';
}

export interface SemanticNode {
  id: string;
  name: string;
  type: 'concept' | 'domain' | 'instance' | 'event';
  properties?: Record<string, any>;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

export interface SemanticEdge {
  id: string;
  source: string;
  target: string;
  name: string;
  type: string;
}

export interface OntologySemanticNetworkProps {
  versions: OntologyVersion[];
  currentVersion: string;
  onVersionChange?: (versionId: string) => void;
  onNodeClick?: (node: SemanticNode) => void;
  onNodeEdit?: (node: SemanticNode) => void;
  onNodeDelete?: (node: SemanticNode) => void;
  onRefresh?: () => void;
}

const NODE_COLORS = {
  concept: { fill: '#1890ff', stroke: '#096dd9' },
  domain: { fill: '#52c41a', stroke: '#389e0d' },
  instance: { fill: '#722ed1', stroke: '#531dab' },
  event: { fill: '#faad14', stroke: '#d48806' }
};

const NODE_TYPE_LABELS = {
  concept: { label: '概念', color: 'blue' },
  domain: { label: '领域', color: 'green' },
  instance: { label: '实例', color: 'purple' },
  event: { label: '事件', color: 'orange' }
};

const EDGE_COLORS: Record<string, string> = {
  related_to: '#8c8c8c',
  includes: '#52c41a',
  equivalent: '#1890ff',
  causes: '#ff4d4f'
};

const EDGE_LINE_STYLES: Record<string, number[]> = {
  related_to: [],
  includes: [5, 5],
  equivalent: [],
  causes: [2, 2]
};

function SemanticNetworkGraph({
  nodes,
  edges,
  selectedNodeId,
  onNodeClick
}: {
  nodes: SemanticNode[];
  edges: SemanticEdge[];
  selectedNodeId?: string;
  onNodeClick?: (node: SemanticNode) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    let mounted = true;
    let currentGraph: Graph | null = null;

    const initGraph = async () => {
      if (!containerRef.current || !mounted || nodes.length === 0) return;

      if (graphRef.current) {
        try {
          if (graphRef.current.destroy) {
            graphRef.current.destroy();
          }
        } catch (e) { console.warn('销毁旧图实例失败:', e); }
        graphRef.current = null;
      }

      const graphData = {
        nodes: nodes.map((n) => ({
          id: n.id,
          data: {
            label: n.name,
            nodeType: n.type,
            properties: n.properties || {}
          }
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          data: { edgeType: e.type, edgeName: e.name }
        }))
      };

      const graph = new Graph({
        container: containerRef.current,
        width: containerRef.current.clientWidth || 800,
        height: 600,
        data: graphData,
        node: {
          type: 'circle',
          style: (d: any) => {
            const colors = NODE_COLORS[d.data?.nodeType as keyof typeof NODE_COLORS] || NODE_COLORS.concept;
            const isSelected = d.id === selectedNodeId;
            return {
              size: 50,
              fill: colors.fill,
              stroke: isSelected ? '#1890ff' : colors.stroke,
              lineWidth: isSelected ? 4 : 2,
              cursor: 'pointer'
            };
          },
          labelText: (d: any) => d.data?.label || '',
          labelFill: '#fff',
          labelFontSize: 12,
          labelOffsetY: 4
        },
        edge: {
          type: 'line',
          style: (d: any) => {
            const color = EDGE_COLORS[d.data?.edgeType] || '#8c8c8c';
            const dash = EDGE_LINE_STYLES[d.data?.edgeType] || [];
            return {
              stroke: color,
              lineWidth: 2,
              lineDash: dash,
              endArrow: {
                type: 'triangle',
                size: 6,
                fill: color
              }
            };
          },
          labelText: (d: any) => d.data?.edgeName || '',
          labelFill: '#8c8c8c',
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: '#fff',
          labelBackgroundPadding: [2, 4, 2, 4]
        },
        layout: {
          type: 'force',
          preventOverlap: true,
          nodeSize: 60,
          linkDistance: 120,
          nodeStrength: -300,
          edgeStrength: 0.5,
          collideStrength: 0.8
        },
        behaviors: [
          { type: 'drag-canvas' },
          { type: 'zoom-canvas' },
          { type: 'drag-element' }
        ],
        autoFit: 'view'
      });

      if (!mounted) {
        try { graph.destroy(); } catch (e) { /* ignore */ }
        return;
      }

      graph.render();

      graph.on('node:click', (evt: any) => {
        if (!mounted) return;
        try {
          const nodeId = evt.item?.get?.('id');
          if (nodeId === undefined || nodeId === null) return;
          const node = nodes.find((n) => n.id === nodeId);
          if (node) onNodeClick?.(node);
        } catch (e) { console.warn('节点点击事件处理错误:', e); }
      });

      currentGraph = graph;
      graphRef.current = graph;
    };

    initGraph();

    return () => {
      mounted = false;
      if (currentGraph) {
        try {
          if (currentGraph.destroy) {
            currentGraph.destroy();
          }
        } catch (e) { console.warn('清理 currentGraph 失败:', e); }
        currentGraph = null;
      }
      if (graphRef.current) {
        try {
          if (graphRef.current.destroy) {
            graphRef.current.destroy();
          }
        } catch (e) { console.warn('清理 graphRef 失败:', e); }
        graphRef.current = null;
      }
    };
  }, [nodes, edges, selectedNodeId]);

  if (nodes.length === 0) {
    return (
      <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="暂无语义网络数据，请先通过数据摄入添加实体" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: 600, background: '#fafafa', borderRadius: 4 }}
    />
  );
}

function GraphToolbar({
  layout,
  onLayoutChange,
  onZoomIn,
  onZoomOut,
  onReset,
  onExport
}: {
  layout: 'force' | 'circular' | 'grid';
  onLayoutChange: (layout: 'force' | 'circular' | 'grid') => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onReset?: () => void;
  onExport?: () => void;
}) {
  return (
    <Space size={8} wrap>
      <Select
        value={layout}
        onChange={onLayoutChange}
        options={[
          { value: 'force', label: '力导向' },
          { value: 'circular', label: '环形' },
          { value: 'grid', label: '网格' }
        ]}
        style={{ width: 100 }}
      />
      <Tooltip title="放大">
        <Button icon={<ZoomInOutlined />} onClick={onZoomIn} />
      </Tooltip>
      <Tooltip title="缩小">
        <Button icon={<ZoomOutOutlined />} onClick={onZoomOut} />
      </Tooltip>
      <Tooltip title="重置">
        <Button icon={<ExpandOutlined />} onClick={onReset} />
      </Tooltip>
      <Tooltip title="导出">
        <Button icon={<ExportOutlined />} onClick={onExport} />
      </Tooltip>
    </Space>
  );
}

function Legend() {
  return (
    <Space size={16} style={{ padding: '8px 16px', background: '#fafafa', borderRadius: 4 }}>
      <Space size={4}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: NODE_COLORS.concept.fill, border: `2px solid ${NODE_COLORS.concept.stroke}` }} />
        <Text type="secondary" style={{ fontSize: 12 }}>概念</Text>
      </Space>
      <Space size={4}>
        <div style={{ width: 12, height: 12, borderRadius: 2, background: NODE_COLORS.domain.fill, border: `2px solid ${NODE_COLORS.domain.stroke}` }} />
        <Text type="secondary" style={{ fontSize: 12 }}>领域</Text>
      </Space>
      <Space size={4}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: NODE_COLORS.instance.fill, border: `2px solid ${NODE_COLORS.instance.stroke}` }} />
        <Text type="secondary" style={{ fontSize: 12 }}>实例</Text>
      </Space>
      <Space size={4}>
        <div style={{ width: 12, height: 12, transform: 'rotate(45deg)', background: NODE_COLORS.event.fill, border: `2px solid ${NODE_COLORS.event.stroke}` }} />
        <Text type="secondary" style={{ fontSize: 12 }}>事件</Text>
      </Space>
    </Space>
  );
}

function NodeDetailDrawer({
  node,
  edges,
  allNodes,
  open,
  onClose,
  onEdit,
  onDelete
}: {
  node: SemanticNode | null;
  edges: SemanticEdge[];
  allNodes: SemanticNode[];
  open: boolean;
  onClose: () => void;
  onEdit?: (node: SemanticNode) => void;
  onDelete?: (node: SemanticNode) => void;
}) {
  if (!node) return null;

  const relatedEdges = edges.filter(e => e.source === node.id || e.target === node.id);
  const relatedNodes = relatedEdges.map(e => {
    const targetId = e.source === node.id ? e.target : e.source;
    return allNodes.find(n => n.id === targetId);
  }).filter(Boolean) as SemanticNode[];

  return (
    <Drawer
      title={
        <Space>
          <Tag color={NODE_TYPE_LABELS[node.type].color}>{NODE_TYPE_LABELS[node.type].label}</Tag>
          <Text strong>{node.name}</Text>
        </Space>
      }
      placement="right"
      size="large"
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Button size="small" type="text" onClick={() => onEdit?.(node)}>编辑</Button>
          <Button size="small" type="text" danger onClick={() => onDelete?.(node)}>删除</Button>
        </Space>
      }
    >
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="节点ID">{node.id}</Descriptions.Item>
        <Descriptions.Item label="名称">{node.name}</Descriptions.Item>
        <Descriptions.Item label="类型">
          <Tag color={NODE_TYPE_LABELS[node.type].color}>{NODE_TYPE_LABELS[node.type].label}</Tag>
        </Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 24 }}>
        <Text strong style={{ display: 'block', marginBottom: 12 }}>属性</Text>
        {node.properties && Object.keys(node.properties).length > 0 ? (
          <Descriptions column={1} size="small">
            {Object.entries(node.properties).map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>
                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : (
          <Text type="secondary">暂无属性</Text>
        )}
      </div>

      <div style={{ marginTop: 24 }}>
        <Text strong style={{ display: 'block', marginBottom: 12 }}>关系 ({relatedEdges.length})</Text>
        {relatedEdges.length > 0 ? (
          <Table
            size="small"
            dataSource={relatedEdges}
            columns={[
              { title: '关系', dataIndex: 'name', key: 'name', render: (text: string) => <Tag>{text}</Tag> },
              { title: '类型', dataIndex: 'type', key: 'type', render: (text: string) => <Tag color="blue">{text}</Tag> },
              {
                title: '关联节点',
                key: 'target',
                render: (_: any, record: SemanticEdge) => {
                  const targetId = record.source === node.id ? record.target : record.source;
                  const target = allNodes.find(n => n.id === targetId);
                  return target ? <Text>{target.name}</Text> : '-';
                }
              }
            ]}
            rowKey="id"
            pagination={false}
          />
        ) : (
          <Text type="secondary">暂无关系</Text>
        )}
      </div>
    </Drawer>
  );
}

export function OntologySemanticNetwork({
  versions,
  currentVersion,
  onVersionChange,
  onNodeClick,
  onNodeEdit,
  onNodeDelete,
  onRefresh
}: OntologySemanticNetworkProps) {
  const [nodes, setNodes] = useState<SemanticNode[]>([]);
  const [edges, setEdges] = useState<SemanticEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<SemanticNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [layout, setLayout] = useState<'force' | 'circular' | 'grid'>('force');

  useEffect(() => {
    loadGraphData();
  }, [currentVersion]);

  const loadGraphData = async () => {
    try {
      setLoading(true);
      const mockNodes: SemanticNode[] = [
        { id: '1', name: '人工智能', type: 'concept', properties: { 描述: '模拟人类智能的技术', 置信度: 0.95 } },
        { id: '2', name: '教育行业', type: 'domain', properties: { 描述: '教育相关领域', 规模: '万亿级' } },
        { id: '3', name: '技术应用', type: 'concept', properties: { 描述: '技术的实际应用', 应用场景: '在线教育' } },
        { id: '4', name: '挑战', type: 'concept', properties: { 描述: '面临的问题和挑战', 优先级: '高' } },
        { id: '5', name: '发展趋势', type: 'event', properties: { 描述: '未来发展方向', 时间范围: '2026-2030' } }
      ];

      const mockEdges: SemanticEdge[] = [
        { id: 'e1', source: '1', target: '2', name: '影响', type: 'related_to' },
        { id: 'e2', source: '2', target: '4', name: '面临', type: 'related_to' },
        { id: 'e3', source: '1', target: '3', name: '包括', type: 'includes' },
        { id: 'e4', source: '3', target: '5', name: '导致', type: 'causes' },
        { id: 'e5', source: '1', target: '5', name: '促进', type: 'related_to' }
      ];

      setNodes(mockNodes);
      setEdges(mockEdges);
    } catch (error) {
      console.error('加载语义网络失败', error);
      message.error('加载语义网络失败');
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = (node: SemanticNode) => {
    setSelectedNode(node);
    onNodeClick?.(node);
  };

  const handleCloseDrawer = () => {
    setSelectedNode(null);
  };

  const currentVersionData = versions.find(v => v.versionId === currentVersion);

  return (
    <div style={{ padding: 24 }}>
      <PageHeader title="本体语义网络" />

      <Card style={{ borderRadius: 8, marginBottom: 16 }} bodyStyle={{ padding: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={8}>
            <Space>
              <Text type="secondary">版本选择:</Text>
              <Select
                value={currentVersion}
                onChange={onVersionChange}
                options={versions.map(v => ({
                  label: `${v.versionId} - ${new Date(v.createdAt).toLocaleString('zh-CN')}`,
                  value: v.versionId
                }))}
                style={{ width: 200 }}
              />
              {currentVersionData && (
                <Tag color={currentVersionData.status === 'completed' ? 'green' : currentVersionData.status === 'building' ? 'blue' : 'red'}>
                  {currentVersionData.status === 'completed' ? '已完成' : currentVersionData.status === 'building' ? '构建中' : '失败'}
                </Tag>
              )}
            </Space>
          </Col>
          <Col span={16}>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Space>
                <Button icon={<SearchOutlined />} type="text">搜索节点</Button>
                <Button icon={<FilterOutlined />} type="text">筛选</Button>
                <Button icon={<ReloadOutlined />} onClick={() => { loadGraphData(); onRefresh?.(); }}>
                  刷新
                </Button>
              </Space>
            </div>
          </Col>
        </Row>
      </Card>

      <Card
        title="本体语义网络"
        extra={<GraphToolbar layout={layout} onLayoutChange={setLayout} />}
        style={{ borderRadius: 8, marginBottom: 16 }}
      >
        {loading ? (
          <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" />
          </div>
        ) : (
          <SemanticNetworkGraph
            nodes={nodes}
            edges={edges}
            selectedNodeId={selectedNode?.id}
            onNodeClick={handleNodeClick}
          />
        )}
      </Card>

      <Legend />

      <NodeDetailDrawer
        node={selectedNode}
        edges={edges}
        allNodes={nodes}
        open={!!selectedNode}
        onClose={handleCloseDrawer}
        onEdit={onNodeEdit}
        onDelete={onNodeDelete}
      />
    </div>
  );
}

export default OntologySemanticNetwork;