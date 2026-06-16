/**
 * InheritanceGraph — ObjectType 继承关系图（HierarchyGraph 配置化薄包装层）
 *
 * 使用 Cytoscape.js 引擎，dagre BT 布局
 * 保留：属性解析链 Drawer、创建边 Modal、左侧过滤栏
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Space, Typography, Tag, Slider, Checkbox, Drawer, Form, Select, Input, Modal, message, List, Descriptions } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { HierarchyGraph } from '@/modules/shared/modules/graph';
import type { GraphNode, GraphEdge, NodeStyleConfig, EdgeStyleConfig } from '@/modules/shared/modules/graph';
import { apiClient } from '@/modules/shared/services/apiClient';

const { Text, Title } = Typography;

// ─── 类型 ───

export interface InheritanceGraphProps {
  workspaceId?: string;
}

interface ObjectTypeNode {
  id: string;
  name: string;
  parent_count: number;
  child_count: number;
  inherited_property_count: number;
  is_mixin: boolean;
  properties: Array<{ name: string; source?: string }>;
  resolution_chain: Array<{ name: string; source: string; from_object_type: string }>;
}

interface InheritanceEdge {
  id: string;
  source: string;
  target: string;
  relation: 'inheritance' | 'mixin';
}

interface InheritanceResponse {
  nodes: ObjectTypeNode[];
  edges: InheritanceEdge[];
}

// ─── 样式映射 ───

const NODE_STYLE_MAP: Record<string, NodeStyleConfig> = {
  objecttype: { fill: '#e6f7ff', stroke: '#1890ff', shape: 'rectangle', size: 60 },
  mixin: { fill: '#f9f0ff', stroke: '#722ed1', shape: 'rectangle', size: 60 },
};

const EDGE_STYLE_MAP: Record<string, EdgeStyleConfig> = {
  inheritance: { stroke: '#1890ff', width: 2, lineDash: [], arrow: true },
  mixin: { stroke: '#722ed1', width: 1.5, lineDash: [4, 3], arrow: true },
};

// ─── 组件 ───

export function InheritanceGraph({ workspaceId }: InheritanceGraphProps) {
  const [data, setData] = useState<InheritanceResponse>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<ObjectTypeNode | null>(null);
  const [maxDepth, setMaxDepth] = useState(10);
  const [showOnlyWithChildren, setShowOnlyWithChildren] = useState(false);
  const [addEdgeModalOpen, setAddEdgeModalOpen] = useState(false);
  const [addEdgeForm] = Form.useForm();

  // ─── 加载数据 ───
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (workspaceId) params.set('workspaceId', workspaceId);
      const resp = await apiClient.get<InheritanceResponse>(`/api/ontology/inheritance?${params.toString()}`);
      setData(resp);
    } catch (error) {
      console.error('加载继承关系失败', error);
      message.error('加载继承关系失败');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { loadData(); }, [loadData]);

  // ─── 过滤 ───
  const filteredNodes = useMemo(() => {
    let result = data.nodes;
    if (showOnlyWithChildren) result = result.filter((n) => n.child_count > 0);
    return result;
  }, [data.nodes, showOnlyWithChildren]);

  // ─── 转换为通用 GraphNode/GraphEdge ───
  const graphNodes: GraphNode[] = filteredNodes.map((n) => ({
    id: n.id,
    label: `${n.name}\nP:${n.parent_count} C:${n.child_count} I:${n.inherited_property_count}`,
    type: n.is_mixin ? 'mixin' : 'objecttype',
    properties: { ...n },
  }));

  const graphEdges: GraphEdge[] = data.edges
    .filter((e) => filteredNodes.some((n) => n.id === e.source) && filteredNodes.some((n) => n.id === e.target))
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.relation,
      label: e.relation === 'inheritance' ? 'extends' : 'mixin',
    }));

  // ─── 节点点击 → 解析链 Drawer ───
  const handleNodeClick = useCallback((node: GraphNode) => {
    const otn = data.nodes.find((n) => n.id === node.id);
    if (otn) setSelectedNode(otn);
  }, [data.nodes]);

  // ─── 创建边 ───
  const handleAddEdge = useCallback(async () => {
    try {
      const values = await addEdgeForm.validateFields();
      await apiClient.post('/api/ontology/inheritance/edge', values);
      message.success('创建成功');
      setAddEdgeModalOpen(false);
      addEdgeForm.resetFields();
      loadData();
    } catch (error) {
      console.error('创建边失败', error);
    }
  }, [addEdgeForm, loadData]);

  // ─── 删除边 ───
  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    try {
      await apiClient.delete(`/api/ontology/inheritance/edge/${edgeId}`);
      message.success('删除成功');
      loadData();
    } catch (error) {
      console.error('删除边失败', error);
    }
  }, [loadData]);

  // ─── 左侧过滤栏 ───
  const filterPanel = (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>过滤</Title>
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">最大深度</Text>
        <Slider min={1} max={10} value={maxDepth} onChange={setMaxDepth} />
      </div>
      <Checkbox
        checked={showOnlyWithChildren}
        onChange={(e) => setShowOnlyWithChildren(e.target.checked)}
      >
        仅显示有子类
      </Checkbox>
    </div>
  );

  // ─── 工具栏扩展 ───
  const toolbarExtra = (
    <Button size="small" icon={<PlusOutlined />} onClick={() => setAddEdgeModalOpen(true)}>
      Add Edge
    </Button>
  );

  return (
    <>
      <HierarchyGraph
        title="ObjectType 继承关系"
        nodes={graphNodes}
        edges={graphEdges}
        nodeStyleMap={NODE_STYLE_MAP}
        edgeStyleMap={EDGE_STYLE_MAP}
        dagreRankDir="BT"
        defaultLayout="dagre"
        onNodeClick={handleNodeClick}
        onRefresh={loadData}
        filterPanel={filterPanel}
        toolbarExtra={toolbarExtra}
        detailPanel={
          <Drawer
            title={selectedNode ? <Space><Tag color={selectedNode.is_mixin ? 'purple' : 'blue'}>{selectedNode.is_mixin ? 'Mixin' : 'ObjectType'}</Tag><Text strong>{selectedNode.name}</Text></Space> : null}
            placement="right"
            open={!!selectedNode}
            onClose={() => setSelectedNode(null)}
            width={400}
          >
            {selectedNode && (
              <>
                <Descriptions column={1} size="small" variant="bordered">
                  <Descriptions.Item label="父类数">{selectedNode.parent_count}</Descriptions.Item>
                  <Descriptions.Item label="子类数">{selectedNode.child_count}</Descriptions.Item>
                  <Descriptions.Item label="继承属性数">{selectedNode.inherited_property_count}</Descriptions.Item>
                </Descriptions>
                <div style={{ marginTop: 16 }}>
                  <Text strong>属性解析链</Text>
                  <List
                    size="small"
                    dataSource={selectedNode.resolution_chain}
                    renderItem={(item) => (
                      <List.Item>
                        <Space>
                          <Tag>{item.name}</Tag>
                          <Text type="secondary">from</Text>
                          <Tag color="blue">{item.from_object_type}</Tag>
                          <Tag color={item.source === 'inherited' ? 'orange' : 'green'}>{item.source}</Tag>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>
              </>
            )}
          </Drawer>
        }
      />

      {/* 创建边 Modal */}
      <Modal
        title="创建继承/Mixin 边"
        open={addEdgeModalOpen}
        onOk={handleAddEdge}
        onCancel={() => { setAddEdgeModalOpen(false); addEdgeForm.resetFields(); }}
      >
        <Form form={addEdgeForm} layout="vertical">
          <Form.Item name="source" label="Source" rules={[{ required: true }]}>
            <Select options={data.nodes.map((n) => ({ label: n.name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="target" label="Target" rules={[{ required: true }]}>
            <Select options={data.nodes.map((n) => ({ label: n.name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="relation" label="关系类型" rules={[{ required: true }]}>
            <Select options={[{ label: '继承 (extends)', value: 'inheritance' }, { label: 'Mixin', value: 'mixin' }]} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default InheritanceGraph;
