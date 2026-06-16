/**
 * OntologySemanticNetwork — 语义网络页面（GraphCanvas 配置化薄包装层）
 *
 * 使用 Sigma.js 引擎，通过 nodeStyleMap/edgeStyleMap 实现固定类型着色
 * 保留：NodeDetailDrawer、Legend、版本选择器
 */
import { useState, useEffect } from 'react';
import { Drawer, Descriptions, Tag, Select, Space, Button, Table, Typography, message } from 'antd';
import { ReloadOutlined, SearchOutlined, FilterOutlined } from '@ant-design/icons';
import { PageHeader } from '@/modules/shared';
import { GraphCanvas } from '@/modules/shared/modules/graph';
import type { GraphNode, GraphEdge, NodeStyleConfig, EdgeStyleConfig } from '@/modules/shared/modules/graph';

const { Text } = Typography;

// ─── 类型定义 ───

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
  properties?: Record<string, unknown>;
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

// ─── 固定样式映射 ───

const NODE_STYLE_MAP: Record<string, NodeStyleConfig> = {
  concept: { fill: '#1890ff', stroke: '#096dd9', shape: 'circle', size: 50 },
  domain: { fill: '#52c41a', stroke: '#389e0d', shape: 'rectangle', size: 50 },
  instance: { fill: '#722ed1', stroke: '#531dab', shape: 'circle', size: 50 },
  event: { fill: '#faad14', stroke: '#d48806', shape: 'diamond', size: 50 },
};

const EDGE_STYLE_MAP: Record<string, EdgeStyleConfig> = {
  related_to: { stroke: '#8c8c8c', width: 1.5, lineDash: [], arrow: true },
  includes: { stroke: '#52c41a', width: 1.5, lineDash: [5, 5], arrow: true },
  equivalent: { stroke: '#1890ff', width: 1.5, lineDash: [], arrow: true },
  causes: { stroke: '#ff4d4f', width: 1.5, lineDash: [2, 2], arrow: true },
};

const NODE_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  concept: { label: '概念', color: 'blue' },
  domain: { label: '领域', color: 'green' },
  instance: { label: '实例', color: 'purple' },
  event: { label: '事件', color: 'orange' },
};

// ─── Legend 组件 ───

function Legend() {
  return (
    <Space size={16} style={{ padding: '8px 16px', background: '#fafafa', borderRadius: 4 }}>
      {Object.entries(NODE_STYLE_MAP).map(([type, config]) => (
        <Space key={type} size={4}>
          <div style={{
            width: 12, height: 12,
            borderRadius: config.shape === 'circle' ? '50%' : config.shape === 'diamond' ? 0 : 2,
            transform: config.shape === 'diamond' ? 'rotate(45deg)' : undefined,
            background: config.fill,
            border: `2px solid ${config.stroke}`,
          }} />
          <Text type="secondary" style={{ fontSize: 12 }}>{NODE_TYPE_LABELS[type]?.label ?? type}</Text>
        </Space>
      ))}
    </Space>
  );
}

// ─── NodeDetailDrawer ───

function NodeDetailDrawer({
  node,
  edges,
  allNodes,
  open,
  onClose,
  onEdit,
  onDelete,
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

  const relatedEdges = edges.filter((e) => e.source === node.id || e.target === node.id);

  return (
    <Drawer
      title={
        <Space>
          <Tag color={NODE_TYPE_LABELS[node.type]?.color}>{NODE_TYPE_LABELS[node.type]?.label}</Tag>
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
      <Descriptions column={1} variant="bordered" size="small">
        <Descriptions.Item label="节点ID">{node.id}</Descriptions.Item>
        <Descriptions.Item label="名称">{node.name}</Descriptions.Item>
        <Descriptions.Item label="类型">
          <Tag color={NODE_TYPE_LABELS[node.type]?.color}>{NODE_TYPE_LABELS[node.type]?.label}</Tag>
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
                render: (_: unknown, record: SemanticEdge) => {
                  const targetId = record.source === node.id ? record.target : record.source;
                  const target = allNodes.find((n) => n.id === targetId);
                  return target ? <Text>{target.name}</Text> : '-';
                },
              },
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

// ─── 主组件 ───

export function OntologySemanticNetwork({
  versions,
  currentVersion,
  onVersionChange,
  onNodeClick,
  onNodeEdit,
  onNodeDelete,
  onRefresh,
}: OntologySemanticNetworkProps) {
  const [semanticNodes, setSemanticNodes] = useState<SemanticNode[]>([]);
  const [semanticEdges, setSemanticEdges] = useState<SemanticEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<SemanticNode | null>(null);

  useEffect(() => {
    loadGraphData();
  }, [currentVersion]);

  const loadGraphData = async () => {
    try {
      // TODO: 替换为真实 API 调用
      const mockNodes: SemanticNode[] = [
        { id: '1', name: '人工智能', type: 'concept', properties: { 描述: '模拟人类智能的技术', 置信度: 0.95 } },
        { id: '2', name: '教育行业', type: 'domain', properties: { 描述: '教育相关领域', 规模: '万亿级' } },
        { id: '3', name: '技术应用', type: 'concept', properties: { 描述: '技术的实际应用', 应用场景: '在线教育' } },
        { id: '4', name: '挑战', type: 'concept', properties: { 描述: '面临的问题和挑战', 优先级: '高' } },
        { id: '5', name: '发展趋势', type: 'event', properties: { 描述: '未来发展方向', 时间范围: '2026-2030' } },
      ];
      const mockEdges: SemanticEdge[] = [
        { id: 'e1', source: '1', target: '2', name: '影响', type: 'related_to' },
        { id: 'e2', source: '2', target: '4', name: '面临', type: 'related_to' },
        { id: 'e3', source: '1', target: '3', name: '包括', type: 'includes' },
        { id: 'e4', source: '3', target: '5', name: '导致', type: 'causes' },
        { id: 'e5', source: '1', target: '5', name: '促进', type: 'related_to' },
      ];
      setSemanticNodes(mockNodes);
      setSemanticEdges(mockEdges);
    } catch (error) {
      console.error('加载语义网络失败', error);
      message.error('加载语义网络失败');
    }
  };

  // ─── 转换为通用 GraphNode/GraphEdge ───
  const graphNodes: GraphNode[] = semanticNodes.map((n) => ({
    id: n.id,
    label: n.name,
    type: n.type,
    properties: n.properties,
  }));

  const graphEdges: GraphEdge[] = semanticEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: e.type,
    label: e.name,
  }));

  const handleNodeClick = (node: GraphNode) => {
    const semanticNode = semanticNodes.find((n) => n.id === node.id);
    if (semanticNode) {
      setSelectedNode(semanticNode);
      onNodeClick?.(semanticNode);
    }
  };

  const currentVersionData = versions.find((v) => v.versionId === currentVersion);

  return (
    <div style={{ padding: 24 }}>
      <PageHeader title="本体语义网络" />

      {/* 版本选择器 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Text type="secondary">版本选择:</Text>
          <Select
            value={currentVersion}
            onChange={onVersionChange}
            options={versions.map((v) => ({
              label: `${v.versionId} - ${new Date(v.createdAt).toLocaleString('zh-CN')}`,
              value: v.versionId,
            }))}
            style={{ width: 200 }}
          />
          {currentVersionData && (
            <Tag color={currentVersionData.status === 'completed' ? 'green' : currentVersionData.status === 'building' ? 'blue' : 'red'}>
              {currentVersionData.status === 'completed' ? '已完成' : currentVersionData.status === 'building' ? '构建中' : '失败'}
            </Tag>
          )}
        </Space>
        <Space>
          <Button icon={<SearchOutlined />} type="text">搜索节点</Button>
          <Button icon={<FilterOutlined />} type="text">筛选</Button>
          <Button icon={<ReloadOutlined />} onClick={() => { loadGraphData(); onRefresh?.(); }}>刷新</Button>
        </Space>
      </div>

      {/* 图谱 — 使用 GraphCanvas + 固定样式映射 */}
      <GraphCanvas
        nodes={graphNodes}
        edges={graphEdges}
        nodeStyleMap={NODE_STYLE_MAP}
        edgeStyleMap={EDGE_STYLE_MAP}
        onNodeClick={handleNodeClick}
        onRefresh={() => { loadGraphData(); onRefresh?.(); }}
        legend={<Legend />}
        detailPanel={
          <NodeDetailDrawer
            node={selectedNode}
            edges={semanticEdges}
            allNodes={semanticNodes}
            open={!!selectedNode}
            onClose={() => setSelectedNode(null)}
            onEdit={onNodeEdit}
            onDelete={onNodeDelete}
          />
        }
      />
    </div>
  );
}

export default OntologySemanticNetwork;
