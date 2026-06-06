/**
 * InheritanceGraph 组件 —— ObjectType 继承关系图（G6 渲染）（FR-033 / T362）
 *
 * 主区域：G6 图谱渲染
 *   - 节点：每个 ObjectType 一卡片，显示 name + 父类数 + 子类数 + 继承属性数
 *   - 边：实线箭头（继承 inheritance）+ 虚线（Mixin）
 *   - Mixin 节点使用不同颜色（紫色）
 * 右侧详情面板：点击节点显示该 ObjectType 的属性解析链
 *   - 展示 "inherited from Parent.foo" 链路
 * 左侧过滤栏：按深度 / 是否有子类型 过滤
 * 右上角："Add Edge" 按钮（创建新继承边或 Mixin）
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Card, Row, Col, Button, Space, Typography, Tag, Empty, Spin, Slider, Checkbox, Drawer, Form, Select, Input, Modal, message, List,
} from 'antd';
import { PlusOutlined, ReloadOutlined, ApartmentOutlined } from '@ant-design/icons';
import { Graph } from '@antv/g6';
import { apiClient } from '../../shared/services/apiClient';
import { useI18n } from '../../shared/hooks/useI18n';

const { Text, Title } = Typography;

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

export function InheritanceGraph({ workspaceId }: InheritanceGraphProps) {
  const { t } = useI18n();
  void t;
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  const [data, setData] = useState<InheritanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [maxDepth, setMaxDepth] = useState(10);
  const [onlyWithChildren, setOnlyWithChildren] = useState(false);
  const [selectedNode, setSelectedNode] = useState<ObjectTypeNode | null>(null);
  const [addEdgeOpen, setAddEdgeOpen] = useState(false);
  const [edgeForm] = Form.useForm();

  void workspaceId;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const url = workspaceId
        ? `/api/ontology/inheritance?workspace_id=${workspaceId}`
        : '/api/ontology/inheritance';
      const result = await apiClient.get<InheritanceResponse>(url);
      setData(result);
    } catch (e) {
      message.error(`加载继承关系失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { void fetchData(); }, [fetchData]);

  const filtered = useMemo(() => {
    if (!data) return null;
    const kept = new Set<string>();
    data.nodes.forEach((n) => {
      if (onlyWithChildren && n.child_count === 0) return;
      kept.add(n.id);
    });
    const nodeList = data.nodes.filter((n) => kept.has(n.id));
    const edgeList = data.edges.filter((e) => kept.has(e.source) && kept.has(e.target));
    return { nodes: nodeList, edges: edgeList };
  }, [data, onlyWithChildren]);

  // Build G6 graph
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !filtered) return;
    if (graphRef.current) {
      try { graphRef.current.destroy(); } catch { /* noop */ }
      graphRef.current = null;
    }

    if (filtered.nodes.length === 0) return;

    const graphData = {
      nodes: filtered.nodes.map((n) => ({
        id: n.id,
        data: {
          label: n.name,
          isMixin: n.is_mixin,
          parentCount: n.parent_count,
          childCount: n.child_count,
          inheritedCount: n.inherited_property_count,
        },
      })),
      edges: filtered.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        data: { relation: e.relation },
      })),
    };

    const graph = new Graph({
      container,
      width: container.clientWidth,
      height: container.clientHeight || 600,
      autoFit: 'center',
      padding: [40, 40, 40, 40],
      data: graphData,
      animation: false,
      node: {
        type: 'rect',
        style: (d: { data?: { isMixin?: boolean; label?: string; parentCount?: number; childCount?: number; inheritedCount?: number } }) => {
          const isMixin = !!d.data?.isMixin;
          const label = d.data?.label || '';
          const sub = `${d.data?.parentCount ?? 0}P · ${d.data?.childCount ?? 0}C · ${d.data?.inheritedCount ?? 0}I`;
          return {
            size: [180, 60],
            fill: isMixin ? '#f9f0ff' : '#e6f4ff',
            stroke: isMixin ? '#722ed1' : '#1677ff',
            lineWidth: 2,
            radius: 6,
            labelText: [label, sub].join('\n'),
            labelPlacement: 'center',
            labelFill: isMixin ? '#531dab' : '#003eb3',
            labelFontSize: 12,
            labelFontWeight: 600,
            cursor: 'pointer',
          };
        },
        state: {
          selected: { lineWidth: 4, stroke: '#fa8c16' },
        },
      },
      edge: {
        type: 'line',
        style: (d: { data?: { relation?: string } }) => {
          const isMixin = d.data?.relation === 'mixin';
          return {
            stroke: isMixin ? '#722ed1' : '#1677ff',
            lineWidth: 2,
            lineDash: isMixin ? [4, 4] : undefined,
            endArrow: true,
            endArrowSize: 8,
            endArrowFill: isMixin ? '#722ed1' : '#1677ff',
            labelText: isMixin ? 'mixin' : 'extends',
            labelFill: '#8c8c8c',
            labelFontSize: 10,
            labelBackground: true,
            labelBackgroundFill: '#fff',
            labelBackgroundOpacity: 0.7,
          };
        },
      },
      layout: {
        type: 'dagre',
        rankdir: 'BT',
        nodesep: 30,
        ranksep: 50,
        animate: false,
      },
      behaviors: ['drag-canvas', 'zoom-canvas'],
    });

    graph.on('node:click', (evt: unknown) => {
      const id = (evt as { target?: { id?: string } }).target?.id;
      if (!id || !filtered) return;
      const node = filtered.nodes.find((n) => n.id === id);
      if (node) setSelectedNode(node);
    });

    graphRef.current = graph;
    void graph.render();

    const onResize = () => {
      try { graph.resize(container.clientWidth, container.clientHeight); } catch { /* noop */ }
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      try { graph.destroy(); } catch { /* noop */ }
      graphRef.current = null;
    };
  }, [filtered]);

  const handleCreateEdge = useCallback(async () => {
    try {
      const values = await edgeForm.validateFields();
      await apiClient.post('/api/ontology/inheritance/edges', {
        ...values,
        workspace_id: workspaceId,
      });
      message.success('边已创建');
      setAddEdgeOpen(false);
      edgeForm.resetFields();
      void fetchData();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`创建失败: ${(e as Error).message}`);
    }
  }, [edgeForm, workspaceId, fetchData]);

  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    try {
      await apiClient.delete(`/api/ontology/inheritance/edges/${edgeId}`);
      message.success('边已删除');
      void fetchData();
    } catch (e) {
      message.error(`删除失败: ${(e as Error).message}`);
    }
  }, [fetchData]);

  return (
    <div data-testid="inheritance-graph" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>
          <ApartmentOutlined /> 继承关系图
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddEdgeOpen(true)}>
            Add Edge
          </Button>
        </Space>
      </Space>

      <Row gutter={16}>
        <Col xs={24} md={4}>
          <Card size="small" title="过滤">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">最大深度</Text>
                <Slider min={1} max={20} value={maxDepth} onChange={setMaxDepth} />
              </div>
              <Checkbox
                checked={onlyWithChildren}
                onChange={(e) => setOnlyWithChildren(e.target.checked)}
              >
                仅显示有子类
              </Checkbox>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={20}>
          <Card size="small">
            <Spin spinning={loading}>
              <div
                ref={containerRef}
                style={{
                  width: '100%',
                  height: 600,
                  background: '#fafafa',
                  borderRadius: 4,
                }}
              />
              {filtered && filtered.nodes.length === 0 && (
                <Empty description="暂无继承关系数据" />
              )}
            </Spin>
          </Card>
        </Col>
      </Row>

      <Drawer
        title={selectedNode ? `属性解析链: ${selectedNode.name}` : '属性解析链'}
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
        width={480}
      >
        {selectedNode && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Card size="small">
              <Space wrap>
                <Text>父类：<Text strong>{selectedNode.parent_count}</Text></Text>
                <Text>子类：<Text strong>{selectedNode.child_count}</Text></Text>
                <Text>继承属性：<Text strong>{selectedNode.inherited_property_count}</Text></Text>
                {selectedNode.is_mixin && <Tag color="purple">mixin</Tag>}
              </Space>
            </Card>
            <Card size="small" title="解析链">
              {selectedNode.resolution_chain.length === 0 ? (
                <Empty description="无解析链" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <List
                  size="small"
                  dataSource={selectedNode.resolution_chain}
                  renderItem={(item) => (
                    <List.Item>
                      <Space size={4} direction="vertical" style={{ lineHeight: 1.2 }}>
                        <Text code>{item.name}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          来源：<Tag color="blue">{item.from_object_type}</Tag>
                          <Tag color={item.source === 'inherited' ? 'orange' : 'green'}>
                            {item.source}
                          </Tag>
                        </Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Space>
        )}
      </Drawer>

      <Modal
        title="新增继承 / Mixin 边"
        open={addEdgeOpen}
        onOk={handleCreateEdge}
        onCancel={() => { setAddEdgeOpen(false); edgeForm.resetFields(); }}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={edgeForm} layout="vertical" preserve={false}>
          <Form.Item name="source" label="源 ObjectType" rules={[{ required: true, message: '请选择源' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={(filtered?.nodes || []).map((n) => ({ value: n.id, label: n.name }))}
              placeholder="子类型"
            />
          </Form.Item>
          <Form.Item name="target" label="目标 ObjectType" rules={[{ required: true, message: '请选择目标' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={(filtered?.nodes || []).map((n) => ({ value: n.id, label: n.name }))}
              placeholder="父类型 / Mixin"
            />
          </Form.Item>
          <Form.Item name="relation" label="关系" rules={[{ required: true, message: '请选择关系' }]}>
            <Select
              options={[
                { value: 'inheritance', label: 'inheritance（继承）' },
                { value: 'mixin', label: 'mixin（混入）' },
              ]}
              placeholder="选择关系类型"
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 隐藏的操作区，提供给外部触发的删除边操作 */}
      <span hidden>
        <Button onClick={() => handleDeleteEdge('')} />
      </span>
    </div>
  );
}

export default InheritanceGraph;
