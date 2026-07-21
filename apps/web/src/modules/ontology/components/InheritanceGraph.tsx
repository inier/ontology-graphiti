/**
 * InheritanceGraph — ObjectType 继承关系图（HierarchyGraph 配置化薄包装层）
 *
 * 使用 Cytoscape.js 引擎，dagre BT 布局
 * 保留：属性解析链 Drawer、创建边 Modal、左侧过滤栏
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Space, Typography, Tag, Slider, Checkbox, Drawer, Select, Input, Modal, message, List } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { PlusOutlined } from '@ant-design/icons';
import { HierarchyGraph } from '@/modules/shared/modules/graph';
import type { GraphNode, GraphEdge, NodeStyleConfig, EdgeStyleConfig } from '@/modules/shared/modules/graph';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

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
  const { t } = useI18n('ontology');
  const [data, setData] = useState<InheritanceResponse>({ nodes: [], edges: [] });
  const [, setLoading] = useState(true);
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
      message.error(t('inheritanceGraph.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, t]);

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
      label: e.relation === 'inheritance' ? t('inheritanceGraph.extends') : t('inheritanceGraph.mixin'),
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
      message.success(t('inheritanceGraph.createSuccess'));
      setAddEdgeModalOpen(false);
      addEdgeForm.resetFields();
      loadData();
    } catch (error) {
      console.error('创建边失败', error);
    }
  }, [addEdgeForm, loadData, t]);

  // ─── 删除边 ───
  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    try {
      await apiClient.delete(`/api/ontology/inheritance/edge/${edgeId}`);
      message.success(t('inheritanceGraph.deleteSuccess'));
      loadData();
    } catch (error) {
      console.error('删除边失败', error);
    }
  }, [loadData, t]);

  // ─── 左侧过滤栏 ───
  const filterPanel = (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>{t('inheritanceGraph.filter')}</Title>
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">{t('inheritanceGraph.maxDepth')}</Text>
        <Slider min={1} max={10} value={maxDepth} onChange={setMaxDepth} />
      </div>
      <Checkbox
        checked={showOnlyWithChildren}
        onChange={(e) => setShowOnlyWithChildren(e.target.checked)}
      >
        {t('inheritanceGraph.onlyWithChildren')}
      </Checkbox>
    </div>
  );

  // ─── 工具栏扩展 ───
  const toolbarExtra = (
    <Button size="small" icon={<PlusOutlined />} onClick={() => setAddEdgeModalOpen(true)}>
      {t('inheritanceGraph.addEdge')}
    </Button>
  );

  void loading; void ReloadOutlined; void handleDeleteEdge; void edgeLabel; void mixinLabel;

  return (
    <>
      <HierarchyGraph
        title={t('inheritanceGraph.title')}
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
            title={selectedNode ? <Space><Tag color={selectedNode.is_mixin ? 'purple' : 'blue'}>{selectedNode.is_mixin ? t('inheritanceGraph.mixin') : t('inheritanceGraph.title')}</Tag><Text strong>{selectedNode.name}</Text></Space> : null}
            placement="right"
            open={!!selectedNode}
            onClose={() => setSelectedNode(null)}
            width={400}
          >
            {selectedNode && (
              <>
                <Descriptions column={1}>
                  <Descriptions.Item label={t('inheritanceGraph.parentCount')}>{selectedNode.parent_count}</Descriptions.Item>
                  <Descriptions.Item label={t('inheritanceGraph.childCount')}>{selectedNode.child_count}</Descriptions.Item>
                  <Descriptions.Item label={t('inheritanceGraph.inheritedPropertyCount')}>{selectedNode.inherited_property_count}</Descriptions.Item>
                </Descriptions>
                <div style={{ marginTop: 16 }}>
                  <Text strong>{t('inheritanceGraph.resolutionChain')}</Text>
                  <List
                    size="small"
                    dataSource={selectedNode.resolution_chain}
                    renderItem={(item) => (
                      <List.Item>
                        <Space>
                          <Tag>{item.name}</Tag>
                          <Text type="secondary">{t('inheritanceGraph.from')}</Text>
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
        title={t('inheritanceGraph.createEdgeTitle')}
        open={addEdgeModalOpen}
        onOk={handleAddEdge}
        onCancel={() => { setAddEdgeModalOpen(false); addEdgeForm.resetFields(); }}
      >
        <Form form={addEdgeForm} layout="vertical">
          <Form.Item name="source" label={t('inheritanceGraph.source')} rules={[{ required: true }]}>
            <Select options={data.nodes.map((n) => ({ label: n.display_name || n.name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="target" label={t('inheritanceGraph.target')} rules={[{ required: true }]}>
            <Select options={data.nodes.map((n) => ({ label: n.display_name || n.name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="relation" label={t('inheritanceGraph.relationType')} rules={[{ required: true }]}>
            <Select options={[{ label: t('inheritanceGraph.inheritanceExtends'), value: 'inheritance' }, { label: t('inheritanceGraph.mixin'), value: 'mixin' }]} />
          </Form.Item>
          <Form.Item name="description" label={t('inheritanceGraph.description')}>
            <Input.TextArea />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default InheritanceGraph;
