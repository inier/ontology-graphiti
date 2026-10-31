import { useState, useEffect } from 'react';

import {

  Card, Button, Input, Modal, Form, message, Tag, Space, Popconfirm,

  Empty, Divider, Descriptions, Drawer, Typography, Steps, Select,

} from 'antd';

import {

  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined,

  EyeOutlined, CodeOutlined, FundOutlined,

} from '@ant-design/icons';

import { useI18n } from '@/modules/shared/hooks/useI18n';

import type { BusinessEntity, BusinessEntityType, BusinessEntityFormData, FlowNode, RuleCondition } from '../types';

import { api as sharedApi } from '@/modules/shared/services/api';

import { useOntologyVersion } from '@/modules/shared/components/LayoutContexts';

import { processApi, ruleApi, logicApi, indicatorApi, processTypeDefinitions, ruleTypeDefinitions, functionTypeDefinitions, indicatorTypeDefinitions } from '../services/businessApi';



const { TextArea } = Input;

const { Title, Text } = Typography;



/** 后端 `*-type-definitions` 返回行：四种实体类型共用 `type_id` / `name` / `display_name` */
interface TypeDefinitionRow {

  type_id?: string;

  name?: string;

  display_name?: string;

}

/**
 * 后端业务实体行里的反向关联数组。
 *
 * 这四个字段没有进 `business/types.ts` 的正式契约（`BusinessEntity` 只声明本体字段），
 * 但详情抽屉按 `entityType` 互斥展示它们，故在此以可选字段承载：缺省即渲染「无」。
 */
interface BusinessEntityRelations {

  related_processes?: string[];

  related_rules?: string[];

  related_logics?: string[];

  related_indicators?: string[];

}

/** 列表行 = 本体字段 + 反向关联 */
type BusinessEntityRow = BusinessEntity & BusinessEntityRelations;

/** 表单值 = 表单字段 + 反向关联（编辑回填需要） */
type BusinessEntityFormValues = BusinessEntityFormData & BusinessEntityRelations;

function asRecord(value: unknown): Record<string, unknown> | undefined {

  return value !== null && typeof value === 'object' && !Array.isArray(value)

    ? (value as Record<string, unknown>)

    : undefined;

}

function asString(value: unknown): string {

  return typeof value === 'string' ? value : '';

}

function asStringList(value: unknown): string[] {

  return Array.isArray(value)

    ? value.filter((item): item is string => typeof item === 'string')

    : [];

}

function asStatus(value: unknown): BusinessEntity['status'] {

  return value === 'published' || value === 'deprecated' ? value : 'draft';

}

function asFlowNodes(value: unknown): FlowNode[] | undefined {

  if (!Array.isArray(value)) return undefined;

  return value.flatMap((raw): FlowNode[] => {

    const record = asRecord(raw);

    if (!record) return [];

    const nodeType = record.type;

    const type: FlowNode['type'] =

      nodeType === 'start' || nodeType === 'task' || nodeType === 'decision' || nodeType === 'end'

        ? nodeType

        : 'task';

    return [{

      node_id: asString(record.node_id),

      name: asString(record.name),

      order: typeof record.order === 'number' ? record.order : 0,

      type,

      description: asString(record.description) || undefined,

    }];

  });

}

function asRuleConditions(value: unknown): RuleCondition[] | undefined {

  if (!Array.isArray(value)) return undefined;

  return value.flatMap((raw): RuleCondition[] => {

    const record = asRecord(raw);

    if (!record) return [];

    return [{

      condition_id: asString(record.condition_id),

      trigger_event: asString(record.trigger_event),

      requirement: asString(record.requirement),

      order: typeof record.order === 'number' ? record.order : 0,

    }];

  });

}

/**
 * 把后端任意业务实体行归一成 `BusinessEntityRow`。
 *
 * 各实体类型的列表端点主键名不同（`process_id` / `rule_id` / `logic_id` / `indicator_id`），
 * 由 `entityIdField` 指定；同时补齐 `BusinessEntity` 要求但后端行可能缺省的展示字段。
 */
function toBusinessEntityRow(

  raw: unknown,

  entityIdField: string,

  entityType: BusinessEntityType,

): BusinessEntityRow {

  const record = asRecord(raw) ?? {};

  return {

    id: asString(record[entityIdField]) || asString(record.id) || asString(record.name),

    name: asString(record.name),

    display_name: asString(record.display_name) || asString(record.name),

    description: asString(record.description),

    related_objects: asStringList(record.related_objects),

    llm_description: asString(record.llm_description),

    entity_type: entityType,

    // 列表卡片与详情都不展示 status：后端缺省时给 'draft' 只为满足 BusinessEntity 必填约束
    status: asStatus(record.status),

    created_by: asString(record.created_by),

    created_at: asString(record.created_at),

    updated_at: asString(record.updated_at),

    yaml_definition: asString(record.yaml_definition) || undefined,

    schema_type_id: asString(record.schema_type_id) || undefined,

    flow_nodes: asFlowNodes(record.flow_nodes),

    rule_conditions: asRuleConditions(record.rule_conditions),

    logic_type: asString(record.logic_type) || undefined,

    logic_expression: asString(record.logic_expression) || undefined,

    indicator_type: asString(record.indicator_type) || undefined,

    calculation_formula: asString(record.calculation_formula) || undefined,

    unit: asString(record.unit) || undefined,

    related_processes: asStringList(record.related_processes),

    related_rules: asStringList(record.related_rules),

    related_logics: asStringList(record.related_logics),

    related_indicators: asStringList(record.related_indicators),

  };

}



let cachedProcessOptions: {label: string; value: string}[] | null = null;

let cachedRuleOptions: {label: string; value: string}[] | null = null;

let cachedLogicOptions: {label: string; value: string}[] | null = null;

let cachedIndicatorOptions: {label: string; value: string}[] | null = null;

let cachedObjectTypeOptions: {label: string; value: string}[] | null = null;

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




  optionsPromise = (async () => {

    try {

      const result = await sharedApi.queryEntities({}, undefined);

      const typeSet = new Set<string>();

      (result.entities || []).forEach((e) => {

        const t = e.type;

        if (t) typeSet.add(t);

      });

      const TYPE_LABELS: Record<string, string> = {

        Unit: '组织单元', Equipment: '装备', Location: '地点',

        Person: '人员', Organization: '组织', EventNode: '事件节点',

        Event: '事件', Document: '文档',

      };

      cachedObjectTypeOptions = Array.from(typeSet).map(t => ({ label: `${TYPE_LABELS[t] || t} (${t})`, value: t }));

    } catch (e) {

      console.warn('加载对象类型选项失败', e);

    }



    try {

      const processes = await processApi.list();

      cachedProcessOptions = processes.map((p) => ({ label: p.display_name || p.name, value: p.name }));

    } catch { /* 忽略：失败时保持当前状态 */  /* ignore */ }

    try {

      const rules = await ruleApi.list();

      cachedRuleOptions = rules.map((r) => ({ label: r.display_name || r.name, value: r.name }));

    } catch { /* 忽略：失败时保持当前状态 */  /* ignore */ }

    try {

      const logics = await logicApi.list();

      cachedLogicOptions = logics.map((l) => ({ label: l.display_name || l.name, value: l.name }));

    } catch { /* 忽略：失败时保持当前状态 */  /* ignore */ }

    try {

      const indicators = await indicatorApi.list();

      cachedIndicatorOptions = indicators.map((i) => ({ label: i.display_name || i.name, value: i.name }));

    } catch { /* 忽略：失败时保持当前状态 */  /* ignore */ }

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

  /**
   * 各业务实体类型的 CRUD 端点。
   *
   * 用函数简写（method）签名而非函数属性：`strictFunctionTypes` 只对函数属性启用逆变检查，
   * 各类型的具体载荷（`BusinessProcessFormData` 等）与 `BusinessEntityFormData` 并不互相兼容，
   * 函数属性签名会让四处调用方全部报类型错误。
   * 返回 `unknown` 是为了让各端点各自的具体行类型都可赋值进来，行数据统一由
   * `toBusinessEntityRow` 归一。
   */
  api: {

    list(ontologyId?: string, versionId?: string): Promise<unknown[]>;

    create(data: BusinessEntityFormData): Promise<unknown>;

    update(id: string, data: BusinessEntityFormData): Promise<unknown>;

    delete(id: string): Promise<void>;

    importYaml?(yaml: string): Promise<unknown[]>;

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

  const { t } = useI18n('business');

  const { currentOntologyId, currentVersionId } = useOntologyVersion();

  const [entities, setEntities] = useState<BusinessEntityRow[]>([]);

  const [, setLoading] = useState(false);

  const [searchText, setSearchText] = useState('');

  const [modalOpen, setModalOpen] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);

  const [yamlModalOpen, setYamlModalOpen] = useState(false);

  const [yamlViewOpen, setYamlViewOpen] = useState(false);

  const [yamlViewContent, setYamlViewContent] = useState('');

  const [editingEntity, setEditingEntity] = useState<BusinessEntityRow | null>(null);

  const [viewingEntity, setViewingEntity] = useState<BusinessEntityRow | null>(null);

  const [form] = Form.useForm<BusinessEntityFormValues>();

  const [yamlForm] = Form.useForm<{ yaml: string }>();

  const [flowNodes, setFlowNodes] = useState<FlowNode[]>([]);

  const [ruleConditions, setRuleConditions] = useState<RuleCondition[]>([]);

  const [objectTypeOptions, setObjectTypeOptions] = useState<{label: string; value: string}[]>([]);

  const [processOptions, setProcessOptions] = useState<{label: string; value: string}[]>([]);

  const [ruleOptions, setRuleOptions] = useState<{label: string; value: string}[]>([]);

  const [logicOptions, setLogicOptions] = useState<{label: string; value: string}[]>([]);

  const [indicatorOptions, setIndicatorOptions] = useState<{label: string; value: string}[]>([]);

  const [typeDefinitions, setTypeDefinitions] = useState<TypeDefinitionRow[]>([]);

  const [typeDefinitionOptions, setTypeDefinitionOptions] = useState<{label: string; value: string}[]>([]);



  



  const loadTypeDefinitions = async () => {

    if (!currentOntologyId) {

      setTypeDefinitions([]);

      setTypeDefinitionOptions([]);

      return;

    }

    try {

      // `*-type-definitions` 端点在 apiClient 里未声明返回类型（`get<T = any>`），按 unknown 收窄
      let result: unknown;

      switch (entityType) {

        case 'process':

          result = await processTypeDefinitions.list(currentOntologyId);

          break;

        case 'rule':

          result = await ruleTypeDefinitions.list(currentOntologyId);

          break;

        case 'logic':

          result = await functionTypeDefinitions.list(currentOntologyId);

          break;

        case 'indicator':

          result = await indicatorTypeDefinitions.list(currentOntologyId);

          break;

      }

      const items: TypeDefinitionRow[] = Array.isArray(result)
        ? result.filter((row): row is TypeDefinitionRow => row !== null && typeof row === 'object')
        : [];

      setTypeDefinitions(items);

      setTypeDefinitionOptions(items.map((td) => ({

        label: td.display_name || td.name || td.type_id || '',

        value: td.type_id || '',

      })));

    } catch {

      setTypeDefinitions([]);

      setTypeDefinitionOptions([]);

    }

  };



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

      setEntities(data.map((item) => toBusinessEntityRow(item, entityIdField, entityType)));

    } catch {

      message.error(t('加载{{title}}列表失败', { title }));

    } finally {

      setLoading(false);

    }

  };

  useEffect(() => {

        void (async () => {
      loadEntities();
    })();

        void (async () => {
      loadOptions();
    })();

        void (async () => {
      loadTypeDefinitions();
    })();

  }, [currentOntologyId, currentVersionId]);



  const handleCreate = () => {

    setEditingEntity(null);

    form.resetFields();

    setFlowNodes([]);

    setRuleConditions([]);

    setModalOpen(true);

  };



  const handleEdit = (entity: BusinessEntityRow) => {

    setEditingEntity(entity);

    form.setFieldsValue({

      name: entity.name,

      display_name: entity.display_name,

      description: entity.description,

      related_objects: entity.related_objects,

      related_processes: entity.related_processes || [],

      related_rules: entity.related_rules || [],

      related_logics: entity.related_logics || [],

      related_indicators: entity.related_indicators || [],

      llm_description: entity.llm_description,

      logic_type: entity.logic_type,

      logic_expression: entity.logic_expression,

      indicator_type: entity.indicator_type,

      calculation_formula: entity.calculation_formula,

      unit: entity.unit,

      schema_type_id: entity.schema_type_id,

    });

    setFlowNodes(entity.flow_nodes || []);

    setRuleConditions(entity.rule_conditions || []);

    setModalOpen(true);

  };



  const handleView = (entity: BusinessEntityRow) => {

    setViewingEntity(entity);

    setDetailOpen(true);

  };



  const handleDelete = async (id: string) => {

    try {

      await api.delete(id);

      message.success(t('删除成功'));

      clearOptionsCache();

      loadEntities();

    } catch {

      message.error(t('删除失败'));

    }

  };



  const handleSave = async (values: BusinessEntityFormValues) => {

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

        message.success(t('更新成功'));

      } else {

        await api.create(payload);

        message.success(t('创建成功'));

      }

      clearOptionsCache();

      setModalOpen(false);

      loadEntities();

    } catch {

      message.error(t('保存失败'));

    }

  };



  const handleImportYaml = async () => {

    if (!api.importYaml) return;

    try {

      const values = yamlForm.getFieldsValue();

      await api.importYaml(values.yaml);

      message.success(t('导入成功'));

      clearOptionsCache();

      setYamlModalOpen(false);

      loadEntities();

    } catch {

      message.error(t('导入失败'));

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



  const updateFlowNode = (index: number, field: keyof FlowNode, value: FlowNode[keyof FlowNode]) => {

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

            placeholder={t('搜索{{title}}', { title })}

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

              {t('批量导入')}

            </Button>

          )}

          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>

            {t('新建')}

          </Button>

        </Space>

      </div>



      {/* 实体卡片网格 */}

      {filteredEntities.length === 0 ? (

        <Empty description={t('暂无{{title}}', { title })} style={{ marginTop: 80 }} />

      ) : (

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>

          {filteredEntities.map(entity => (

            <Card

              key={entity.id}

              hoverable

              style={{ borderRadius: 8 }}

              styles={{ body: { padding: 16 } }}

              onClick={() => handleView(entity)}

            >

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>

                <div>

                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{entity.display_name}</div>

                  <Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>{entity.name}</Text>

                </div>

                <Space size={4}>

                  {entity.schema_type_id && (() => {

                    const matched = typeDefinitions.find((td) => td.type_id === entity.schema_type_id);

                    return matched ? <Tag color="geekblue">{matched.display_name || matched.name}</Tag> : <Tag>{entity.schema_type_id}</Tag>;

                  })()}

                  <Tag color={tagColor}>{tagText}</Tag>

                </Space>

              </div>



              <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12, minHeight: 40 }}>

                {entity.description || t('暂无描述')}

              </Text>



              {/* 流程节点预览 */}

              {showFlowNodes && entity.flow_nodes && entity.flow_nodes.length > 0 && (

                <div style={{ marginBottom: 12 }}>

                  <Steps

                    size="small"

                    orientation="horizontal"

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

                      <Tag color="red">{t('当')}</Tag> {cond.trigger_event}

                      <Tag color="orange" style={{ marginLeft: 8 }}>{t('必须')}</Tag> {cond.requirement}

                    </div>

                  ))}

                  {entity.rule_conditions.length > 2 && (

                    <Text type="secondary" style={{ fontSize: 12 }}>{t('+{{count}} 个条件', { count: entity.rule_conditions.length - 2 })}</Text>

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

                  <Button type="text" size="small" icon={<EyeOutlined />} onClick={(e) => { e.stopPropagation(); handleView(entity); }}>{t('查看')}</Button>

                  <Button type="text" size="small" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); handleEdit(entity); }}>{t('编辑')}</Button>

                  <Popconfirm title={t('确认删除？')} onConfirm={(e) => { e?.stopPropagation(); handleDelete(entity.id); }}>

                    <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()}>{t('删除')}</Button>

                  </Popconfirm>

                </Space>

              </div>

            </Card>

          ))}

        </div>

      )}



      {/* 新建/编辑弹窗 */}

      <Modal

        title={editingEntity ? t('编辑{{title}}', { title }) : t('新建{{title}}', { title })}

        open={modalOpen}

        onCancel={() => setModalOpen(false)}

        onOk={() => form.submit()}

        width={640}

        destroyOnHidden

        okText={t('保存')}

        cancelText={t('取消')}

      >

        <Form form={form} layout="vertical" onFinish={handleSave}>

          <Form.Item name="name" label={t('唯一标识名称')} rules={[{ required: true, message: t('请输入唯一标识名称') }]}>

            <Input placeholder={t('请输入名称（英文、数字、下划线）')} />

          </Form.Item>

          <Form.Item name="display_name" label={t('展示名称')} rules={[{ required: true, message: t('请输入展示名称') }]}>

            <Input placeholder={t('请输入展示名称')} />

          </Form.Item>

          <Form.Item name="schema_type_id" label={t('类型定义')}>

            <Select placeholder={t('选择类型定义（可选）')} allowClear options={typeDefinitionOptions} showSearch filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())} />

          </Form.Item>

          <Form.Item name="related_objects" label={t('关联对象')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联对象类型')}

              options={objectTypeOptions}

              allowClear

              showSearch

              filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}

            />

          </Form.Item>

          {entityType !== 'process' && (

            <Form.Item name="related_processes" label={t('关联业务过程')}>

              <Select

                mode="multiple"

                placeholder={t('请选择关联业务过程')}

                options={processOptions}

                allowClear

                showSearch

                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}

              />

            </Form.Item>

          )}

          {entityType !== 'rule' && (

            <Form.Item name="related_rules" label={t('关联业务规则')}>

              <Select

                mode="multiple"

                placeholder={t('请选择关联业务规则')}

                options={ruleOptions}

                allowClear

                showSearch

                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}

              />

            </Form.Item>

          )}

          {entityType !== 'logic' && (

            <Form.Item name="related_logics" label={t('关联业务逻辑')}>

              <Select

                mode="multiple"

                placeholder={t('请选择关联业务逻辑')}

                options={logicOptions}

                allowClear

                showSearch

                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}

              />

            </Form.Item>

          )}

          {entityType !== 'indicator' && (

            <Form.Item name="related_indicators" label={t('关联业务指标')}>

              <Select

                mode="multiple"

                placeholder={t('请选择关联业务指标')}

                options={indicatorOptions}

                allowClear

                showSearch

                filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}

              />

            </Form.Item>

          )}

          <Form.Item name="llm_description" label={t('核心逻辑（LLM Description）')} rules={[{ required: true }]}>

            <TextArea placeholder={t('请输入核心逻辑描述')} rows={6} />

          </Form.Item>



          {/* 流程节点编辑 */}

          {showFlowNodes && (

            <>

              <Divider>{t('流程节点')}</Divider>

              {flowNodes.map((node, index) => (

                <div key={node.node_id} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>

                  <span style={{ fontWeight: 600, minWidth: 24 }}>{index + 1}.</span>

                  <Input

                    value={node.name}

                    onChange={e => updateFlowNode(index, 'name', e.target.value)}

                    placeholder={t('节点名称')}

                    style={{ flex: 1 }}

                  />

                  <Button type="text" danger onClick={() => removeFlowNode(index)}>{t('删除')}</Button>

                </div>

              ))}

              <Button type="dashed" block icon={<PlusOutlined />} onClick={addFlowNode} style={{ marginTop: 8 }}>

                {t('添加节点')}

              </Button>

            </>

          )}



          {/* 规则条件编辑 */}

          {showRuleConditions && (

            <>

              <Divider>{t('规则条件')}</Divider>

              {ruleConditions.map((cond, index) => (

                <div key={cond.condition_id} style={{ marginBottom: 12, padding: 12, background: '#f5f7fa', borderRadius: 4 }}>

                  <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>

                    <Tag color="red">{t('当')}</Tag>

                    <Input

                      value={cond.trigger_event}

                      onChange={e => updateRuleCondition(index, 'trigger_event', e.target.value)}

                      placeholder={t('触发事件')}

                      style={{ flex: 1 }}

                    />

                  </div>

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>

                    <Tag color="orange">{t('必须')}</Tag>

                    <Input

                      value={cond.requirement}

                      onChange={e => updateRuleCondition(index, 'requirement', e.target.value)}

                      placeholder={t('要求条件')}

                      style={{ flex: 1 }}

                    />

                    <Button type="text" danger onClick={() => removeRuleCondition(index)}>{t('删除')}</Button>

                  </div>

                </div>

              ))}

              <Button type="dashed" block icon={<PlusOutlined />} onClick={addRuleCondition} style={{ marginTop: 8 }}>

                {t('添加条件')}

              </Button>

            </>

          )}



          {/* 逻辑表达式编辑 */}

          {showLogicExpression && (

            <>

              <Divider>{t('逻辑配置')}</Divider>

              <Form.Item name="logic_type" label={t('逻辑类型')}>

                <Select placeholder={t('请选择逻辑类型')} options={[

                  { label: t('过滤 (filter)'), value: 'filter' },

                  { label: t('转换 (transform)'), value: 'transform' },

                  { label: t('验证 (validate)'), value: 'validate' },

                  { label: t('计算 (compute)'), value: 'compute' },

                ]} allowClear />

              </Form.Item>

              <Form.Item name="logic_expression" label={t('逻辑表达式')}>

                <TextArea placeholder={t('请输入逻辑表达式')} rows={3} style={{ fontFamily: 'monospace' }} />

              </Form.Item>

            </>

          )}



          {/* 指标配置编辑 */}

          {showIndicatorConfig && (

            <>

              <Divider>{t('指标配置')}</Divider>

              <Form.Item name="indicator_type" label={t('指标类型')} rules={[{ required: true, message: t('请选择指标类型') }]}>

                <Select placeholder={t('请选择指标类型')} options={[

                  { label: t('关键绩效指标 (KPI)'), value: 'kpi' },

                  { label: t('度量指标 (metric)'), value: 'metric' },

                  { label: t('维度 (dimension)'), value: 'dimension' },

                ]} allowClear />

              </Form.Item>

              <Form.Item name="calculation_formula" label={t('计算公式')} rules={[{ required: true, message: t('请输入计算公式') }]}>

                <TextArea placeholder={t('请输入计算公式')} rows={3} style={{ fontFamily: 'monospace' }} />

              </Form.Item>

              <Form.Item name="unit" label={t('单位')}>

                <Input placeholder={t('请输入单位，如：元、次、%')} />

              </Form.Item>

            </>

          )}

        </Form>

      </Modal>



      {/* YAML 批量导入弹窗 */}

      <Modal

        title={t('YAML 批量定义 - {{title}}', { title })}

        open={yamlModalOpen}

        onCancel={() => setYamlModalOpen(false)}

        onOk={handleImportYaml}

        width={600}

      >

        <Form form={yamlForm} layout="vertical">

          <Form.Item name="yaml" rules={[{ required: true }]}>

            <TextArea placeholder={t('请输入 YAML 定义...')} rows={16} style={{ fontFamily: 'monospace' }} />

          </Form.Item>

        </Form>

      </Modal>



      {/* 详情抽屉 */}

      <Drawer

        title={t('详情')}

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



            <Descriptions column={1}>

              {viewingEntity.schema_type_id && (

                <Descriptions.Item label={t('类型定义')}>

                  {(() => {

                    const matched = typeDefinitions.find((td) => td.type_id === viewingEntity.schema_type_id);

                    return matched ? <Tag color="geekblue">{matched.display_name || matched.name}</Tag> : <Tag>{viewingEntity.schema_type_id}</Tag>;

                  })()}

                </Descriptions.Item>

              )}

              <Descriptions.Item label={t('关联对象')}>

                <Space wrap>

                  {viewingEntity.related_objects?.map(obj => <Tag key={obj} color="blue">{obj}</Tag>)}

                  {(!viewingEntity.related_objects || viewingEntity.related_objects.length === 0) && <Text type="secondary">{t('无')}</Text>}

                </Space>

              </Descriptions.Item>

              {entityType !== 'process' && (

                <Descriptions.Item label={t('关联业务过程')}>

                  <Space wrap>

                    {viewingEntity.related_processes?.map((p) => <Tag key={p} color="green">{p}</Tag>)}

                    {(!viewingEntity.related_processes || viewingEntity.related_processes?.length === 0) && <Text type="secondary">{t('无')}</Text>}

                  </Space>

                </Descriptions.Item>

              )}

              {entityType !== 'rule' && (

                <Descriptions.Item label={t('关联业务规则')}>

                  <Space wrap>

                    {viewingEntity.related_rules?.map((r) => <Tag key={r} color="orange">{r}</Tag>)}

                    {(!viewingEntity.related_rules || viewingEntity.related_rules?.length === 0) && <Text type="secondary">{t('无')}</Text>}

                  </Space>

                </Descriptions.Item>

              )}

              {entityType !== 'logic' && (

                <Descriptions.Item label={t('关联业务逻辑')}>

                  <Space wrap>

                    {viewingEntity.related_logics?.map((l) => <Tag key={l} color="purple">{l}</Tag>)}

                    {(!viewingEntity.related_logics || viewingEntity.related_logics?.length === 0) && <Text type="secondary">{t('无')}</Text>}

                  </Space>

                </Descriptions.Item>

              )}

              {entityType !== 'indicator' && (

                <Descriptions.Item label={t('关联业务指标')}>

                  <Space wrap>

                    {viewingEntity.related_indicators?.map((i) => <Tag key={i} color="cyan">{i}</Tag>)}

                    {(!viewingEntity.related_indicators || viewingEntity.related_indicators?.length === 0) && <Text type="secondary">{t('无')}</Text>}

                  </Space>

                </Descriptions.Item>

              )}

            </Descriptions>



            {/* 流程节点详情 */}

            {showFlowNodes && viewingEntity.flow_nodes && viewingEntity.flow_nodes.length > 0 && (

              <>

                <Divider>{t('流程节点')}</Divider>

                <Steps

                  orientation="vertical"

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

                <Divider>{t('规则条件')}</Divider>

                {viewingEntity.rule_conditions.map((cond) => (

                  <div key={cond.condition_id} style={{ marginBottom: 12, padding: 12, background: '#f5f7fa', borderRadius: 4 }}>

                    <div style={{ marginBottom: 4 }}>

                      <Tag color="red">{t('当')}</Tag> <Text>{cond.trigger_event}</Text>

                    </div>

                    <div>

                      <Tag color="orange">{t('必须')}</Tag> <Text>{cond.requirement}</Text>

                    </div>

                  </div>

                ))}

              </>

            )}



            {/* 逻辑表达式详情 */}

            {showLogicExpression && viewingEntity.logic_expression && (

              <>

                <Divider>{t('逻辑配置')}</Divider>

                <div style={{ padding: 12, background: '#f6ffed', borderRadius: 4, fontFamily: 'monospace', fontSize: 13 }}>

                  <div style={{ marginBottom: 8 }}><Tag>{t('类型')}</Tag> {viewingEntity.logic_type}</div>

                  <div><Tag>{t('表达式')}</Tag> {viewingEntity.logic_expression}</div>

                </div>

              </>

            )}



            {/* 指标详情 */}

            {showIndicatorConfig && viewingEntity.calculation_formula && (

              <>

                <Divider>{t('指标配置')}</Divider>

                <div style={{ padding: 12, background: '#e6f7ff', borderRadius: 4, fontSize: 13 }}>

                  <div style={{ marginBottom: 8 }}><Tag>{t('指标类型')}</Tag> {viewingEntity.indicator_type}</div>

                  <div style={{ marginBottom: 8 }}><Tag>{t('计算公式')}</Tag> <span style={{ fontFamily: 'monospace' }}>{viewingEntity.calculation_formula}</span></div>

                  {viewingEntity.unit && <div><Tag>{t('单位')}</Tag> {viewingEntity.unit}</div>}

                </div>

              </>

            )}



            <Divider>{t('核心逻辑')}</Divider>

            <div style={{ padding: 12, background: '#f5f7fa', borderRadius: 4, whiteSpace: 'pre-wrap' }}>

              {viewingEntity.llm_description}

            </div>



            <Divider />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>

              <Button icon={<CodeOutlined />} onClick={() => { setYamlViewContent(viewingEntity.yaml_definition || ''); setYamlViewOpen(true); }}>{t('查看 YAML 代码')}</Button>

              <Popconfirm title={t('确认删除？')} onConfirm={() => handleDelete(viewingEntity.id)}>

                <Button danger icon={<DeleteOutlined />}>{t('删除')}</Button>

              </Popconfirm>

              <Button type="primary" icon={<EditOutlined />} onClick={() => { setDetailOpen(false); handleEdit(viewingEntity); }}>

                {t('编辑')}

              </Button>

            </div>

          </div>

        )}

      </Drawer>



      <Modal

        title={t('YAML 定义')}

        open={yamlViewOpen}

        onCancel={() => setYamlViewOpen(false)}

        footer={<Button onClick={() => setYamlViewOpen(false)}>{t('关闭')}</Button>}

        width={640}

      >

        {yamlViewContent ? (

          <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, fontSize: 13, fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxHeight: 480, overflow: 'auto' }}>

            {yamlViewContent}

          </pre>

        ) : (

          <div style={{ textAlign: 'center', color: '#8c8c8c', padding: 40 }}>{t('暂无 YAML 定义')}</div>

        )}

      </Modal>

    </div>

  );

}

