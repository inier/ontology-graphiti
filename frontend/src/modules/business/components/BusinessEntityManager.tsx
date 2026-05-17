import { useState, useEffect } from 'react';
import {
  Card, Button, Input, Modal, Form, message, Tag, Space, Popconfirm,
  Empty, Divider, Descriptions, Drawer, Typography, Steps, Select,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined,
  EyeOutlined, CodeOutlined, FundOutlined,
} from '@ant-design/icons';
import type { BusinessEntity, BusinessEntityType, BusinessEntityFormData, FlowNode, RuleCondition } from '../types';
import { api as sharedApi } from '../../shared/services/api';
import { useOntologyVersion } from '../../shared/components/AppLayout';
import { processApi, ruleApi, logicApi, indicatorApi } from '../services/businessApi';

const { TextArea } = Input;
const { Title, Text } = Typography;

let cachedProcessOptions: {label: string; value: string}[] | null = null;
let cachedRuleOptions: {label: string; value: string}[] | null = null;
let cachedLogicOptions: {label: string; value: string}[] | null = null;
let cachedIndicatorOptions: {label: string; value: string}[] | null = null;
let cachedObjectTypeOptions: {label: string; value: string}[] | null = null;
let optionsLoading = false;
let optionsPromise: Promise<void> | null = null;

function clearOptionsCache() {
  cachedProcessOptions = null;
  cachedRuleOptions = null;
  cachedLogicOptions = null;
  cachedIndicatorOptions = null;
  cachedObjectTypeOptions = null;
  optionsPromise = null;
}

async function ensureOptionsLoaded(): Promise<{
  processOptions: {label: string; value: string}[];
  ruleOptions: {label: string; value: string}[];
  logicOptions: {label: string; value: string}[];
  indicatorOptions: {label: string; value: string}[];
  objectTypeOptions: {label: string; value: string}[];
}> {
  if (cachedProcessOptions && cachedRuleOptions && cachedLogicOptions && cachedIndicatorOptions) {
    return {
      processOptions: cachedProcessOptions,
      ruleOptions: cachedRuleOptions,
      logicOptions: cachedLogicOptions,
      indicatorOptions: cachedIndicatorOptions,
      objectTypeOptions: cachedObjectTypeOptions || [],
    };
  }

  if (optionsPromise) {
    await optionsPromise;
    return {
      processOptions: cachedProcessOptions || [],
      ruleOptions: cachedRuleOptions || [],
      logicOptions: cachedLogicOptions || [],
      indicatorOptions: cachedIndicatorOptions || [],
      objectTypeOptions: cachedObjectTypeOptions || [],
    };
  }

  optionsLoading = true;
  optionsPromise = (async () => {
    try {
      const result = await sharedApi.queryEntities({}, undefined);
      const typeSet = new Set<string>();
      (result.entities || []).forEach((e: any) => {
        const t = e.type || e.entity_type;
        if (t) typeSet.add(t);
      });
      const TYPE_LABELS: Record<string, string> = {
        Unit: '作战单元', Equipment: '装备', Location: '地点',
        Person: '人员', Organization: '组织', EventNode: '事件节点',
        Event: '事件', Document: '文档',
      };
      cachedObjectTypeOptions = Array.from(typeSet).map(t => ({ label: `${TYPE_LABELS[t] || t} (${t})`, value: t }));
    } catch (e) {
      console.warn('加载对象类型选项失败', e);
    }

    try {
      const processes = await processApi.list();
      cachedProcessOptions = processes.map((p: any) => ({ label: p.display_name || p.name, value: p.name }));
    } catch (e) { /* ignore */ }
    try {
      const rules = await ruleApi.list();
      cachedRuleOptions = rules.map((r: any) => ({ label: r.display_name || r.name, value: r.name }));
    } catch (e) { /* ignore */ }
    try {
      const logics = await logicApi.list();
      cachedLogicOptions = logics.map((l: any) => ({ label: l.display_name || l.name, value: l.name }));
    } catch (e) { /* ignore */ }
    try {
      const indicators = await indicatorApi.list();
      cachedIndicatorOptions = indicators.map((i: any) => ({ label: i.display_name || i.name, value: i.name }));
    } catch (e) { /* ignore */ }
  })();

  await optionsPromise;

  return {
    processOptions: cachedProcessOptions || [],
    ruleOptions: cachedRuleOptions || [],
    logicOptions: cachedLogicOptions || [],
    indicatorOptions: cachedIndicatorOptions || [],
    objectTypeOptions: cachedObjectTypeOptions || [],
  };
}

interface BusinessEntityManagerProps {
  entityType: BusinessEntityType;
  title: string;
  icon: React.ReactNode;
  tagColor: string;
  tagText: string;
  api: {
    list: (ontologyId?: string, versionId?: string) => Promise<any[]>;
    create: (data: any) => Promise<any>;
    update: (id: string, data: any) => Promise<any>;
    delete: (id: string) => Promise<void>;
    importYaml?: (yaml: string) => Promise<any[]>;
  };
  entityIdField: string;
  showFlowNodes?: boolean;
  showRuleConditions?: boolean;
  showLogicExpression?: boolean;
  showIndicatorConfig?: boolean;
}

export function BusinessEntityManager({
  entityType,
  title,
  tagColor,
  tagText,
  api,
  entityIdField,
  showFlowNodes,
  showRuleConditions,
  showLogicExpression,
  showIndicatorConfig,
}: BusinessEntityManagerProps) {
  const { currentOntologyId, currentVersionId } = useOntologyVersion();
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [yamlModalOpen, setYamlModalOpen] = useState(false);
  const [editingEntity, setEditingEntity] = useState<BusinessEntity | null>(null);
  const [viewingEntity, setViewingEntity] = useState<BusinessEntity | null>(null);
  const [form] = Form.useForm<BusinessEntityFormData>();
  const [yamlForm] = Form.useForm<{ yaml: string }>();
  const [flowNodes, setFlowNodes] = useState<FlowNode[]>([]);
  const [ruleConditions, setRuleConditions] = useState<RuleCondition[]>([]);
  const [objectTypeOptions, setObjectTypeOptions] = useState<{label: string; value: string}[]>([]);
  const [processOptions, setProcessOptions] = useState<{label: string; value: string}[]>([]);
  const [ruleOptions, setRuleOptions] = useState<{label: string; value: string}[]>([]);
  const [logicOptions, setLogicOptions] = useState<{label: string; value: string}[]>([]);
  const [indicatorOptions, setIndicatorOptions] = useState<{label: string; value: string}[]>([]);

  useEffect(() => {
    loadEntities();
    loadOptions();
  }, [currentOntologyId, currentVersionId]);

  const loadOptions = async () => {
    const opts = await ensureOptionsLoaded();
    setProcessOptions(opts.processOptions);
    setRuleOptions(opts.ruleOptions);
    setLogicOptions(opts.logicOptions);
    setIndicatorOptions(opts.indicatorOptions);
    setObjectTypeOptions(opts.objectTypeOptions);
  };

  const loadEntities = async () => {
    setLoading(true);
    try {
      const data = await api.list(currentOntologyId || undefined, currentVersionId || undefined);
      setEntities(data.map(item => ({ ...item, entity_type: entityType, id: item[entityIdField] })));
    } catch (e) {
      message.error(`加载${title}列表失败`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingEntity(null);
    form.resetFields();
    setFlowNodes([]);
    setRuleConditions([]);
    setModalOpen(true);
  };

  const handleEdit = (entity: BusinessEntity) => {
    setEditingEntity(entity);
    form.setFieldsValue({
      name: entity.name,
      display_name: entity.display_name,
      description: entity.description,
      related_objects: entity.related_objects,
      related_processes: (entity as any).related_processes || [],
      related_rules: (entity as any).related_rules || [],
      related_logics: (entity as any).related_logics || [],
      related_indicators: (entity as any).related_indicators || [],
      llm_description: entity.llm_description,
      logic_type: entity.logic_type,
      logic_expression: entity.logic_expression,
      indicator_type: entity.indicator_type,
      calculation_formula: entity.calculation_formula,
      unit: entity.unit,
    });
    setFlowNodes(entity.flow_nodes || []);
    setRuleConditions(entity.rule_conditions || []);
    setModalOpen(true);
  };

  const handleView = (entity: BusinessEntity) => {
    setViewingEntity(entity);
    setDetailOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(id);
      message.success('删除成功');
      clearOptionsCache();
      loadEntities();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleSave = async (values: BusinessEntityFormData) => {
    try {
      const payload = {
        ...values,
        ontology_id: currentOntologyId,
        version_id: currentVersionId,
        flow_nodes: showFlowNodes ? flowNodes : undefined,
        rule_conditions: showRuleConditions ? ruleConditions : undefined,
      };
      if (editingEntity) {
        await api.update(editingEntity.id, payload);
        message.success('更新成功');
      } else {
        await api.create(payload);
        message.success('创建成功');
      }
      clearOptionsCache();
      setModalOpen(false);
      loadEntities();
    } catch (e) {
      message.error('保存失败');
    }
  };

  const handleImportYaml = async () => {
    if (!api.importYaml) return;
    try {
      const values = yamlForm.getFieldsValue();
      await api.importYaml(values.yaml);
      message.success('导入成功');
      clearOptionsCache();
      setYamlModalOpen(false);
      loadEntities();
    } catch (e) {
      message.error('导入失败');
    }
  };

  const addFlowNode = () => {
    setFlowNodes(prev => [...prev, {
      node_id: `node_${Date.now()}`,
      name: '',
      order: prev.length + 1,
      type: 'task',
    }]);
  };

  const updateFlowNode = (index: number, field: keyof FlowNode, value: any) => {
    setFlowNodes(prev => prev.map((node, i) => i === index ? { ...node, [field]: value } : node));
  };

  const removeFlowNode = (index: number) => {
    setFlowNodes(prev => prev.filter((_, i) => i !== index).map((node, i) => ({ ...node, order: i + 1 })));
  };

  const addRuleCondition = () => {
    setRuleConditions(prev => [...prev, {
      condition_id: `cond_${Date.now()}`,
      trigger_event: '',
      requirement: '',
      order: prev.length + 1,
    }]);
  };

  const updateRuleCondition = (index: number, field: keyof RuleCondition, value: string) => {
    setRuleConditions(prev => prev.map((cond, i) => i === index ? { ...cond, [field]: value } : cond));
  };

  const removeRuleCondition = (index: number) => {
    setRuleConditions(prev => prev.filter((_, i) => i !== index).map((cond, i) => ({ ...cond, order: i + 1 })));
  };

  const filteredEntities = entities.filter(e =>
    e.name.toLowerCase().includes(searchText.toLowerCase()) ||
    e.display_name.toLowerCase().includes(searchText.toLowerCase()) ||
    e.description.toLowerCase().includes(searchText.toLowerCase())
  );

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Space>
          <Input.Search
            placeholder={`搜索${title}`}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{ width: 280 }}
            allowClear
            prefix={<SearchOutlined />}
          />
        </Space>
        <Space>
          {api.importYaml && (
            <Button icon={<CodeOutlined />} onClick={() => { yamlForm.resetFields(); setYamlModalOpen(true); }}>
              批量导入
            </Button>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建
          </Button>
        </Space>
      </div>

      {/* 实体卡片网格 */}
      {filteredEntities.length === 0 ? (
        <Empty description={`暂无${title}`} style={{ marginTop: 80 }} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>
          {filteredEntities.map(entity => (
            <Card
              key={entity.id}
              hoverable
              style={{ borderRadius: 8 }}
              bodyStyle={{ padding: 16 }}
              onClick={() => handleView(entity)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{entity.display_name}</div>
                  <Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>{entity.name}</Text>
                </div>
                <Tag color={tagColor}>{tagText}</Tag>
              </div>

              <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12, minHeight: 40 }}>
                {entity.description || '暂无描述'}
              </Text>

              {/* 流程节点预览 */}
              {showFlowNodes && entity.flow_nodes && entity.flow_nodes.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Steps
                    size="small"
                    direction="horizontal"
                    current={-1}
                    items={[
                      ...entity.flow_nodes.slice(0, 4).map(node => ({ title: node.name })),
                      ...(entity.flow_nodes.length > 4 ? [{ title: `+${entity.flow_nodes.length - 4}` }] : []),
                    ]}
                  />
                </div>
              )}

              {/* 规则条件预览 */}
              {showRuleConditions && entity.rule_conditions && entity.rule_conditions.length > 0 && (
                <div style={{ marginBottom: 12, padding: 8, background: '#f5f7fa', borderRadius: 4 }}>
                  {entity.rule_conditions.slice(0, 2).map((cond) => (
                    <div key={cond.condition_id} style={{ fontSize: 12, marginBottom: 4 }}>
                      <Tag color="red">当</Tag> {cond.trigger_event}
                      <Tag color="orange" style={{ marginLeft: 8 }}>必须</Tag> {cond.requirement}
                    </div>
                  ))}
                  {entity.rule_conditions.length > 2 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>+{entity.rule_conditions.length - 2} 个条件</Text>
                  )}
                </div>
              )}

              {/* 逻辑表达式预览 */}
              {showLogicExpression && entity.logic_expression && (
                <div style={{ marginBottom: 12, padding: 8, background: '#f6ffed', borderRadius: 4, fontFamily: 'monospace', fontSize: 12 }}>
                  <CodeOutlined style={{ marginRight: 4 }} />
                  {entity.logic_expression}
                </div>
              )}

              {/* 指标配置预览 */}
              {showIndicatorConfig && entity.calculation_formula && (
                <div style={{ marginBottom: 12, padding: 8, background: '#e6f7ff', borderRadius: 4, fontFamily: 'monospace', fontSize: 12 }}>
                  <FundOutlined style={{ marginRight: 4 }} />
                  {entity.calculation_formula}
                  {entity.unit && <Tag style={{ marginLeft: 8 }}>{entity.unit}</Tag>}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space size={4} wrap>
                  {entity.related_objects?.map(obj => (
                    <Tag key={obj}>{obj}</Tag>
                  ))}
                </Space>
                <Space>
                  <Button type="text" size="small" icon={<EyeOutlined />} onClick={(e) => { e.stopPropagation(); handleView(entity); }}>查看</Button>
                  <Button type="text" size="small" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); handleEdit(entity); }}>编辑</Button>
                  <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDelete(entity.id); }}>
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()}>删除</Button>
                  </Popconfirm>
                </Space>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editingEntity ? `编辑${title}` : `新建${title}`}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        width={640}
        destroyOnClose
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="唯一标识名称" rules={[{ required: true, message: '请输入唯一标识名称' }]}>
            <Input placeholder="请输入名称（英文、数字、下划线）" />
          </Form.Item>
          <Form.Item name="display_name" label="展示名称" rules={[{ required: true, message: '请输入展示名称' }]}>
            <Input placeholder="请输入展示名称" />
          </Form.Item>
          <Form.Item name="related_objects" label="关联对象">
            <Select
              mode="multiple"
              placeholder="请选择关联对象类型"
              options={objectTypeOptions}
              allowClear
              showSearch
              filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
            />
          </Form.Item>
          {entityType !== 'process' && (
            <Form.Item name="related_processes" label="关联业务过程">
              <Select
                mode="multiple"
                placeholder="请选择关联业务过程"
                options={processOptions}
                allowClear
                showSearch
                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
          )}
          {entityType !== 'rule' && (
            <Form.Item name="related_rules" label="关联业务规则">
              <Select
                mode="multiple"
                placeholder="请选择关联业务规则"
                options={ruleOptions}
                allowClear
                showSearch
                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
          )}
          {entityType !== 'logic' && (
            <Form.Item name="related_logics" label="关联业务逻辑">
              <Select
                mode="multiple"
                placeholder="请选择关联业务逻辑"
                options={logicOptions}
                allowClear
                showSearch
                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
          )}
          {entityType !== 'indicator' && (
            <Form.Item name="related_indicators" label="关联业务指标">
              <Select
                mode="multiple"
                placeholder="请选择关联业务指标"
                options={indicatorOptions}
                allowClear
                showSearch
                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
          )}
          <Form.Item name="llm_description" label="核心逻辑（LLM Description）" rules={[{ required: true }]}>
            <TextArea placeholder="请输入核心逻辑描述" rows={6} />
          </Form.Item>

          {/* 流程节点编辑 */}
          {showFlowNodes && (
            <>
              <Divider>流程节点</Divider>
              {flowNodes.map((node, index) => (
                <div key={node.node_id} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, minWidth: 24 }}>{index + 1}.</span>
                  <Input
                    value={node.name}
                    onChange={e => updateFlowNode(index, 'name', e.target.value)}
                    placeholder="节点名称"
                    style={{ flex: 1 }}
                  />
                  <Button type="text" danger onClick={() => removeFlowNode(index)}>删除</Button>
                </div>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={addFlowNode} style={{ marginTop: 8 }}>
                添加节点
              </Button>
            </>
          )}

          {/* 规则条件编辑 */}
          {showRuleConditions && (
            <>
              <Divider>规则条件</Divider>
              {ruleConditions.map((cond, index) => (
                <div key={cond.condition_id} style={{ marginBottom: 12, padding: 12, background: '#f5f7fa', borderRadius: 4 }}>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                    <Tag color="red">当</Tag>
                    <Input
                      value={cond.trigger_event}
                      onChange={e => updateRuleCondition(index, 'trigger_event', e.target.value)}
                      placeholder="触发事件"
                      style={{ flex: 1 }}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Tag color="orange">必须</Tag>
                    <Input
                      value={cond.requirement}
                      onChange={e => updateRuleCondition(index, 'requirement', e.target.value)}
                      placeholder="要求条件"
                      style={{ flex: 1 }}
                    />
                    <Button type="text" danger onClick={() => removeRuleCondition(index)}>删除</Button>
                  </div>
                </div>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={addRuleCondition} style={{ marginTop: 8 }}>
                添加条件
              </Button>
            </>
          )}

          {/* 逻辑表达式编辑 */}
          {showLogicExpression && (
            <>
              <Divider>逻辑配置</Divider>
              <Form.Item name="logic_type" label="逻辑类型">
                <Select placeholder="请选择逻辑类型" options={[
                  { label: '过滤 (filter)', value: 'filter' },
                  { label: '转换 (transform)', value: 'transform' },
                  { label: '验证 (validate)', value: 'validate' },
                  { label: '计算 (compute)', value: 'compute' },
                ]} allowClear />
              </Form.Item>
              <Form.Item name="logic_expression" label="逻辑表达式">
                <TextArea placeholder="请输入逻辑表达式" rows={3} style={{ fontFamily: 'monospace' }} />
              </Form.Item>
            </>
          )}

          {/* 指标配置编辑 */}
          {showIndicatorConfig && (
            <>
              <Divider>指标配置</Divider>
              <Form.Item name="indicator_type" label="指标类型" rules={[{ required: true, message: '请选择指标类型' }]}>
                <Select placeholder="请选择指标类型" options={[
                  { label: '关键绩效指标 (KPI)', value: 'kpi' },
                  { label: '度量指标 (metric)', value: 'metric' },
                  { label: '维度 (dimension)', value: 'dimension' },
                ]} allowClear />
              </Form.Item>
              <Form.Item name="calculation_formula" label="计算公式" rules={[{ required: true, message: '请输入计算公式' }]}>
                <TextArea placeholder="请输入计算公式" rows={3} style={{ fontFamily: 'monospace' }} />
              </Form.Item>
              <Form.Item name="unit" label="单位">
                <Input placeholder="请输入单位，如：元、次、%" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* YAML 批量导入弹窗 */}
      <Modal
        title={`YAML 批量定义 - ${title}`}
        open={yamlModalOpen}
        onCancel={() => setYamlModalOpen(false)}
        onOk={handleImportYaml}
        width={600}
      >
        <Form form={yamlForm} layout="vertical">
          <Form.Item name="yaml" rules={[{ required: true }]}>
            <TextArea placeholder="请输入 YAML 定义..." rows={16} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情抽屉 */}
      <Drawer
        title="详情"
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={560}
      >
        {viewingEntity && (
          <div>
            <Tag color={tagColor} style={{ marginBottom: 16 }}>{tagText}</Tag>
            <Title level={4} style={{ marginTop: 0 }}>{viewingEntity.display_name}</Title>
            <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: 12 }}>{viewingEntity.name}</Text>

            <Divider />

            <Descriptions column={1} size="small">
              <Descriptions.Item label="关联对象">
                <Space wrap>
                  {viewingEntity.related_objects?.map(obj => <Tag key={obj} color="blue">{obj}</Tag>)}
                  {(!viewingEntity.related_objects || viewingEntity.related_objects.length === 0) && <Text type="secondary">无</Text>}
                </Space>
              </Descriptions.Item>
              {entityType !== 'process' && (
                <Descriptions.Item label="关联业务过程">
                  <Space wrap>
                    {(viewingEntity as any).related_processes?.map((p: string) => <Tag key={p} color="green">{p}</Tag>)}
                    {(!(viewingEntity as any).related_processes || (viewingEntity as any).related_processes?.length === 0) && <Text type="secondary">无</Text>}
                  </Space>
                </Descriptions.Item>
              )}
              {entityType !== 'rule' && (
                <Descriptions.Item label="关联业务规则">
                  <Space wrap>
                    {(viewingEntity as any).related_rules?.map((r: string) => <Tag key={r} color="orange">{r}</Tag>)}
                    {(!(viewingEntity as any).related_rules || (viewingEntity as any).related_rules?.length === 0) && <Text type="secondary">无</Text>}
                  </Space>
                </Descriptions.Item>
              )}
              {entityType !== 'logic' && (
                <Descriptions.Item label="关联业务逻辑">
                  <Space wrap>
                    {(viewingEntity as any).related_logics?.map((l: string) => <Tag key={l} color="purple">{l}</Tag>)}
                    {(!(viewingEntity as any).related_logics || (viewingEntity as any).related_logics?.length === 0) && <Text type="secondary">无</Text>}
                  </Space>
                </Descriptions.Item>
              )}
              {entityType !== 'indicator' && (
                <Descriptions.Item label="关联业务指标">
                  <Space wrap>
                    {(viewingEntity as any).related_indicators?.map((i: string) => <Tag key={i} color="cyan">{i}</Tag>)}
                    {(!(viewingEntity as any).related_indicators || (viewingEntity as any).related_indicators?.length === 0) && <Text type="secondary">无</Text>}
                  </Space>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* 流程节点详情 */}
            {showFlowNodes && viewingEntity.flow_nodes && viewingEntity.flow_nodes.length > 0 && (
              <>
                <Divider>流程节点</Divider>
                <Steps
                  direction="vertical"
                  size="small"
                  current={-1}
                  items={viewingEntity.flow_nodes.map(node => ({
                    title: node.name,
                    description: node.description,
                  }))}
                />
              </>
            )}

            {/* 规则条件详情 */}
            {showRuleConditions && viewingEntity.rule_conditions && viewingEntity.rule_conditions.length > 0 && (
              <>
                <Divider>规则条件</Divider>
                {viewingEntity.rule_conditions.map((cond) => (
                  <div key={cond.condition_id} style={{ marginBottom: 12, padding: 12, background: '#f5f7fa', borderRadius: 4 }}>
                    <div style={{ marginBottom: 4 }}>
                      <Tag color="red">当</Tag> <Text>{cond.trigger_event}</Text>
                    </div>
                    <div>
                      <Tag color="orange">必须</Tag> <Text>{cond.requirement}</Text>
                    </div>
                  </div>
                ))}
              </>
            )}

            {/* 逻辑表达式详情 */}
            {showLogicExpression && viewingEntity.logic_expression && (
              <>
                <Divider>逻辑配置</Divider>
                <div style={{ padding: 12, background: '#f6ffed', borderRadius: 4, fontFamily: 'monospace', fontSize: 13 }}>
                  <div style={{ marginBottom: 8 }}><Tag>类型</Tag> {viewingEntity.logic_type}</div>
                  <div><Tag>表达式</Tag> {viewingEntity.logic_expression}</div>
                </div>
              </>
            )}

            {/* 指标详情 */}
            {showIndicatorConfig && viewingEntity.calculation_formula && (
              <>
                <Divider>指标配置</Divider>
                <div style={{ padding: 12, background: '#e6f7ff', borderRadius: 4, fontSize: 13 }}>
                  <div style={{ marginBottom: 8 }}><Tag>指标类型</Tag> {viewingEntity.indicator_type}</div>
                  <div style={{ marginBottom: 8 }}><Tag>计算公式</Tag> <span style={{ fontFamily: 'monospace' }}>{viewingEntity.calculation_formula}</span></div>
                  {viewingEntity.unit && <div><Tag>单位</Tag> {viewingEntity.unit}</div>}
                </div>
              </>
            )}

            <Divider>核心逻辑</Divider>
            <div style={{ padding: 12, background: '#f5f7fa', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
              {viewingEntity.llm_description}
            </div>

            <Divider />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button icon={<CodeOutlined />}>查看 YAML 代码</Button>
              <Popconfirm title="确认删除？" onConfirm={() => handleDelete(viewingEntity.id)}>
                <Button danger icon={<DeleteOutlined />}>删除</Button>
              </Popconfirm>
              <Button type="primary" icon={<EditOutlined />} onClick={() => { setDetailOpen(false); handleEdit(viewingEntity); }}>
                编辑
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
