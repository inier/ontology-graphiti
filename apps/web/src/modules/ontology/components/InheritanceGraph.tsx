/**
 * InheritanceGraph — ObjectType 继承关系图（HierarchyGraph 配置化薄包装层）
 *
 * 使用 Cytoscape.js 引擎，dagre BT 布局
 * 保留：属性解析链 Drawer、创建边 Modal、左侧过滤栏
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Space, Typography, Tag, Slider, Checkbox, Drawer, Select, Input, Modal, message, List, Divider, Popconfirm } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { HierarchyGraph } from '@/modules/shared/modules/graph';
import type { GraphNode, GraphEdge, NodeStyleConfig, EdgeStyleConfig } from '@/modules/shared/modules/graph';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;

// ─── 类型 ───

interface ObjectTypeNode {
  id: string;
  name: string;
  /** 后端可选展示名；UI 缺省回退到 `name` */
  display_name?: string;
  parent_count: number;
  child_count: number;
  inherited_property_count: number;
  is_mixin: boolean;
  properties: PropertySourceRow[];
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

/**
 * 后端真实报文：`GET /api/ontology/inheritance/edges` 返回 `{edges, count}`，
 * 每条边形如 `{id, child_type_id, parent_type_id, depth, discriminator, created_at}`
 * （见 inheritance_service._edge_to_dict），**没有** `source` / `target` 字段，
 * 也没有聚合图端点 `GET /api/ontology/inheritance`——此前组件请求该端点恒 404，
 * 页面只能显示空图并弹「加载继承关系失败」。
 */
interface BackendEdge {
  id: string;
  child_type_id: string;
  parent_type_id: string;
  depth?: number;
  discriminator?: Record<string, unknown>;
  created_at?: string;
}

/** `GET /api/ontology/inheritance/mixins` 返回 `{mixins, count}`。 */
interface BackendMixin {
  id: string;
  name: string;
  description?: string;
  properties?: Array<{ name: string } | string>;
  target_type_ids?: string[];
}

/**
 * 单条属性来源（`ResolvedProperty.to_dict()`）。
 * `source` 取值：`self` / `parent:<type_id>` / `mixin:<mixin_id>`；
 * `depth` 0=自身，1=最近父类，2=再上一层……（**不是**跳数）。
 */
interface ResolvedPropertyDTO {
  property_name: string;
  source: string;
  depth: number;
  value?: unknown;
}

/**
 * `GET /api/ontology/inheritance/resolve/{type_id}` 真实报文
 * （见 inheritance_service.resolve_type）：
 * `{ type_id, properties: { <属性名>: ResolvedProperty[] }, count }`
 *
 * 注意 `properties` 是**字典**（属性名 → 解析链），不是数组，且**没有**
 * `resolution_chain` 字段——此前按 `{properties: [], resolution_chain: []}`
 * 解析，导致抽屉里「属性解析链」永远为空。
 */
interface ResolveResponse {
  type_id?: string;
  properties?: Record<string, ResolvedPropertyDTO[]> | ResolvedPropertyDTO[];
  count?: number;
}

/** 抽屉里的一行属性来源（已从字典拍平）。 */
interface PropertySourceRow {
  /** 属性名 */
  name: string;
  /** 原始来源串：self / parent:xxx / mixin:yyy */
  source: string;
  /** 继承深度：0=自身 */
  depth: number;
  /** 展示用的「来自哪个类型/Mixin」；`self` 时为空串，由 UI 用 i18n 文案兜底 */
  from: string;
}

/** `GET /api/ontology/object-types` 的最小可用字段。 */
interface ObjectTypeBrief {
  object_type_id: string;
  name: string;
  properties?: Array<{ name: string }>;
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

// ─── 报文归一化 ───

/**
 * 把 resolve 的 `properties` 字典拍平成行数组。
 *
 * 后端 `source` 形如 `parent:<type_id>` / `mixin:<mixin_id>`，此处只拆分出
 * 展示用的 `from`，不改写 `source` 原值（保留原始串便于排错）。
 * 同时兼容数组形态，避免后端将来改为列表时前端白屏。
 */
function flattenResolvedProperties(
  raw: ResolveResponse['properties'],
): PropertySourceRow[] {
  const rows: PropertySourceRow[] = [];
  const pushOne = (dto: ResolvedPropertyDTO, fallbackName?: string) => {
    const source = dto?.source ?? 'self';
    const sep = source.indexOf(':');
    rows.push({
      name: dto?.property_name || fallbackName || '',
      source,
      depth: typeof dto?.depth === 'number' ? dto.depth : 0,
      from: sep >= 0 ? source.slice(sep + 1) : '',
    });
  };

  if (Array.isArray(raw)) {
    raw.forEach((dto) => pushOne(dto));
    return rows;
  }
  for (const [name, chain] of Object.entries(raw ?? {})) {
    if (Array.isArray(chain) && chain.length > 0) {
      chain.forEach((dto) => pushOne(dto, name));
    } else {
      // 该属性没有任何解析结果（provider 未覆盖）：留一行自身来源，不静默丢弃。
      rows.push({ name, source: 'self', depth: 0, from: '' });
    }
  }
  return rows;
}

// ─── 组件 ───

export function InheritanceGraph() {
  const { t } = useI18n('ontology');
  const [data, setData] = useState<InheritanceResponse>({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState<ObjectTypeNode | null>(null);
  const [maxDepth, setMaxDepth] = useState(10);
  const [showOnlyWithChildren, setShowOnlyWithChildren] = useState(false);
  const [addEdgeModalOpen, setAddEdgeModalOpen] = useState(false);
  const [addEdgeForm] = Form.useForm();

  // ─── 加载数据 ───
  // 后端**没有**聚合图端点，故此处按真实契约并行取三份数据后在客户端组装：
  //   GET /api/ontology/object-types              → 节点（id/名称）
  //   GET /api/ontology/inheritance/edges         → 边（child_type_id → parent_type_id）
  //   GET /api/ontology/inheritance/mixins        → mixin 节点与挂接关系
  // 继承深度/属性解析链需按类型逐个 resolve，改为点击节点时懒加载（见 handleNodeClick），
  // 避免一次打开页面发 N 个请求。
  const loadData = useCallback(async () => {
    try {
      const [typesResp, edgesResp, mixinsResp] = await Promise.all([
        apiClient.get<ObjectTypeBrief[] | { object_types?: ObjectTypeBrief[] }>('/api/ontology/object-types'),
        apiClient.get<{ edges?: BackendEdge[] }>('/api/ontology/inheritance/edges'),
        apiClient.get<{ mixins?: BackendMixin[] }>('/api/ontology/inheritance/mixins').catch(() => ({ mixins: [] })),
      ]);
      // object-types 端点在不同版本下返回裸数组或 {object_types}，两种都兼容。
      const types: ObjectTypeBrief[] = Array.isArray(typesResp)
        ? typesResp
        : (typesResp?.object_types ?? []);
      const backendEdges: BackendEdge[] = edgesResp?.edges ?? [];
      const mixins: BackendMixin[] = mixinsResp?.mixins ?? [];

      const typeIds = new Set(types.map((o) => o.object_type_id));
      // 边里出现但类型列表未覆盖的 id 也要建节点，否则边会指向不存在的节点而被丢弃。
      for (const e of backendEdges) {
        if (e.child_type_id) typeIds.add(e.child_type_id);
        if (e.parent_type_id) typeIds.add(e.parent_type_id);
      }
      for (const m of mixins) typeIds.add(m.id);

      const mixinIds = new Set(mixins.map((m) => m.id));
      const nameOf = (id: string) =>
        types.find((o) => o.object_type_id === id)?.name
        || mixins.find((m) => m.id === id)?.name
        || id;

      const nodes: ObjectTypeNode[] = [...typeIds].map((id) => ({
        id,
        name: nameOf(id),
        parent_count: backendEdges.filter((e) => e.child_type_id === id).length,
        child_count: backendEdges.filter((e) => e.parent_type_id === id).length,
        // 继承属性数需逐类型 resolve 才能得到，这里不编造 0 以外的值；
        // 点击节点后由 resolve 结果回填（见 handleNodeClick）。
        inherited_property_count: 0,
        is_mixin: mixinIds.has(id),
        properties: [],
      }));

      const edges: InheritanceEdge[] = [
        ...backendEdges.map((e) => ({
          id: e.id,
          // 语义：子类型 extends 父类型，故 source=child、target=parent（dagre BT 自下而上）。
          source: e.child_type_id,
          target: e.parent_type_id,
          relation: 'inheritance' as const,
        })),
        // mixin 挂接：mixin.target_type_ids 中的类型 → mixin 节点
        ...mixins.flatMap((m) => (m.target_type_ids ?? []).map((tid) => ({
          id: `mixin:${m.id}:${tid}`,
          source: tid,
          target: m.id,
          relation: 'mixin' as const,
        }))),
      ];

      setData({ nodes, edges });
    } catch (error) {
      console.error('加载继承关系失败', error);
      message.error(t('加载失败'));
    }
  }, [t]);

  // 首屏拉取三份 TBox 数据。`loadData` 内部先 await 再 setState（没有同步 setState），
  // 本规则无法穿透 async 边界判断，故此处按仓库既有约定显式豁免，而不是用
  // `void (async () => { ... })()` 把调用包起来骗过静态检查。
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadData(); }, [loadData]);

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
      label: e.relation === 'inheritance' ? t('继承') : t('inheritanceGraph.mixin'),
    }));

  // ─── 节点点击 → 解析链 Drawer（懒加载 resolve，避免页面级 N+1） ───
  const handleNodeClick = useCallback(async (node: GraphNode) => {
    const base = data.nodes.find((n) => n.id === node.id);
    if (!base) return;
    setSelectedNode(base);
    // mixin 节点不参与类型解析链（它本身就是属性来源），跳过请求。
    if (base.is_mixin) return;
    try {
      const resolved = await apiClient.get<ResolveResponse>(
        `/api/ontology/inheritance/resolve/${encodeURIComponent(base.id)}`,
      );
      const rows = flattenResolvedProperties(resolved?.properties);
      const updated: ObjectTypeNode = {
        ...base,
        properties: rows,
        // 只有 depth=0 / source=self 是自身声明，其余（parent:/mixin:）都属继承而来。
        inherited_property_count: rows.filter((r) => r.depth > 0 || r.source !== 'self').length,
      };
      setSelectedNode(updated);
      // 回写节点数据，让图上 `I:` 计数同步刷新——否则标签会一直停在初始的 I:0。
      setData((prev) => ({
        ...prev,
        nodes: prev.nodes.map((n) => (n.id === updated.id ? updated : n)),
      }));
    } catch (error) {
      // 解析链是增强信息，取不到不影响主图；但要留下可排查的原因，不静默吞掉。
      console.error('解析继承链失败', base.id, error);
    }
  }, [data.nodes]);

  // ─── 创建边（POST /edges，字段名 child_type_id / parent_type_id） ───
  const handleAddEdge = useCallback(async () => {
    try {
      const values = await addEdgeForm.validateFields();
      if (values.relation === 'mixin') {
        // mixin 挂接走专用端点：/mixins/{mixin_id}/attach/{type_id}
        await apiClient.post(
          `/api/ontology/inheritance/mixins/${encodeURIComponent(values.target)}/attach/${encodeURIComponent(values.source)}`,
          {},
        );
      } else {
        await apiClient.post('/api/ontology/inheritance/edges', {
          child_type_id: values.source,
          parent_type_id: values.target,
        });
      }
      message.success(t('创建成功'));
      setAddEdgeModalOpen(false);
      addEdgeForm.resetFields();
      await loadData();
    } catch (error) {
      console.error('创建边失败', error);
      message.error(t('inheritanceGraph.createFailed'));
    }
  }, [addEdgeForm, loadData, t]);

  // ─── 删除边（DELETE /edges/{child_id}/{parent_id}，成对主键，不是 edgeId） ───
  const handleDeleteEdge = useCallback(async (childId: string, parentId: string) => {
    try {
      await apiClient.delete(
        `/api/ontology/inheritance/edges/${encodeURIComponent(childId)}/${encodeURIComponent(parentId)}`,
      );
      message.success(t('删除成功'));
      await loadData();
    } catch (error) {
      console.error('删除边失败', error);
      message.error(t('inheritanceGraph.deleteFailed'));
    }
  }, [loadData, t]);

  // ─── 解绑 Mixin（POST /mixins/{mixin_id}/detach/{type_id}） ───
  const handleDetachMixin = useCallback(async (mixinId: string, typeId: string) => {
    try {
      await apiClient.post(
        `/api/ontology/inheritance/mixins/${encodeURIComponent(mixinId)}/detach/${encodeURIComponent(typeId)}`,
        {},
      );
      message.success(t('inheritanceGraph.detachSuccess'));
      await loadData();
    } catch (error) {
      console.error('解绑 Mixin 失败', error);
      message.error(t('inheritanceGraph.detachFailed'));
    }
  }, [loadData, t]);

  /** 当前选中节点的父类型列表（本节点作为 child 的继承边）。 */
  const selectedParents = useMemo(() => {
    if (!selectedNode) return [];
    const nameOf = (id: string) => data.nodes.find((n) => n.id === id)?.name ?? id;
    return data.edges
      .filter((e) => e.relation === 'inheritance' && e.source === selectedNode.id)
      .map((e) => ({ parentId: e.target, parentName: nameOf(e.target) }));
  }, [data.edges, data.nodes, selectedNode]);

  /** 当前选中节点已挂接的 Mixin。 */
  const selectedMixins = useMemo(() => {
    if (!selectedNode) return [];
    return data.edges
      .filter((e) => e.relation === 'mixin' && e.source === selectedNode.id)
      .map((e) => ({ mixinId: e.target, mixinName: data.nodes.find((n) => n.id === e.target)?.name ?? e.target }));
  }, [data.edges, data.nodes, selectedNode]);

  /** 按深度上限裁剪属性来源：depth 0=自身，1=最近父类…… */
  const visibleProperties = useMemo(() => {
    if (!selectedNode) return [];
    return selectedNode.properties.filter((p) => p.depth <= maxDepth);
  }, [selectedNode, maxDepth]);

  // ─── 左侧过滤栏 ───
  const filterPanel = (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>{t('筛选')}</Title>
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">{t('最大深度')}</Text>
        <Slider min={1} max={10} value={maxDepth} onChange={setMaxDepth} />
        <Text type="secondary" style={{ fontSize: 12 }}>{t('inheritanceGraph.maxDepthHint')}</Text>
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

                {/* 父类型（可解绑继承边）——删除边此前只存在于代码里、UI 无入口，这里补齐。 */}
                <Divider titlePlacement="start" style={{ margin: '16px 0 8px' }}>{t('inheritanceGraph.parentsOf')}</Divider>
                {selectedParents.length === 0 ? (
                  <Text type="secondary">{t('inheritanceGraph.noParents')}</Text>
                ) : (
                  <List
                    size="small"
                    dataSource={selectedParents}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Popconfirm
                            key="remove"
                            title={`${t('删除')} ${item.parentName}?`}
                            onConfirm={() => { void handleDeleteEdge(selectedNode.id, item.parentId); }}
                          >
                            <Button size="small" danger type="link" icon={<DeleteOutlined />}>
                              {t('删除')}
                            </Button>
                          </Popconfirm>,
                        ]}
                      >
                        <Tag color="blue">{item.parentName}</Tag>
                      </List.Item>
                    )}
                  />
                )}

                {/* 已挂接 Mixin（可解绑） */}
                <Divider titlePlacement="start" style={{ margin: '16px 0 8px' }}>{t('inheritanceGraph.mixinsOf')}</Divider>
                {selectedMixins.length === 0 ? (
                  <Text type="secondary">{t('inheritanceGraph.noMixins')}</Text>
                ) : (
                  <List
                    size="small"
                    dataSource={selectedMixins}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Popconfirm
                            key="detach"
                            title={`${t('inheritanceGraph.detachMixin')} ${item.mixinName}?`}
                            onConfirm={() => { void handleDetachMixin(item.mixinId, selectedNode.id); }}
                          >
                            <Button size="small" danger type="link" icon={<DeleteOutlined />}>
                              {t('inheritanceGraph.detachMixin')}
                            </Button>
                          </Popconfirm>,
                        ]}
                      >
                        <Tag color="purple">{item.mixinName}</Tag>
                      </List.Item>
                    )}
                  />
                )}

                {/* 属性来源：由 resolve 的「属性名 → 解析链」字典拍平而来，按 maxDepth 裁剪。 */}
                <Divider titlePlacement="start" style={{ margin: '16px 0 8px' }}>{t('inheritanceGraph.propertySource')}</Divider>
                {visibleProperties.length === 0 ? (
                  <Text type="secondary">{t('inheritanceGraph.emptyProperties')}</Text>
                ) : (
                  <List
                    size="small"
                    dataSource={visibleProperties}
                    renderItem={(item) => (
                      <List.Item>
                        <Space size={4} wrap>
                          <Tag>{item.name}</Tag>
                          <Text type="secondary">{t('inheritanceGraph.from')}</Text>
                          <Tag color={item.depth === 0 ? 'green' : 'blue'}>
                            {item.depth === 0 ? t('inheritanceGraph.selfDeclared') : item.from}
                          </Tag>
                          <Tag color={item.depth === 0 ? 'green' : 'orange'}>
                            {t('inheritanceGraph.depth')} {item.depth}
                          </Tag>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
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
          <Form.Item name="target" label={t('目标')} rules={[{ required: true }]}>
            <Select options={data.nodes.map((n) => ({ label: n.display_name || n.name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="relation" label={t('关系类型')} rules={[{ required: true }]}>
            <Select options={[{ label: t('inheritanceGraph.inheritanceExtends'), value: 'inheritance' }, { label: t('inheritanceGraph.mixin'), value: 'mixin' }]} />
          </Form.Item>
          <Form.Item name="description" label={t('描述')}>
            <Input.TextArea />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default InheritanceGraph;
