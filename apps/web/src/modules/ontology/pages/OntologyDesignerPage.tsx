import { useState, useEffect, useCallback, useMemo } from 'react';

import {

  Row, Col, Card, Input, Tag, Popconfirm, Empty, Spin,

  Modal, Form, Select as AntSelect, Tabs, Button as AntButton,

  message, Divider, Drawer, Space,

} from 'antd';

import {

  PlusOutlined, DeleteOutlined, SearchOutlined,

  SwapOutlined, CheckCircleOutlined, ApartmentOutlined,

  HistoryOutlined, ReloadOutlined, DatabaseOutlined, MessageOutlined,

  RobotOutlined,

} from '@ant-design/icons';

import { PageHeader } from '@/modules/shared/components/PageHeader';

import { useWorkspace } from '@/modules/shared/components/LayoutContexts';

import { useOntologyStore } from '../stores/ontologyStore';

import { useI18n } from '@/modules/shared/hooks/useI18n';

import type { ObjectTypeDefinition } from '../stores/ontologyStore';

import { OntologySelector } from '../components/OntologySelector';

import type { OntologyItem } from '../components/OntologySelector';

import { DesignMethodSelector } from '../components/DesignMethodSelector';

import type { DesignMethod } from '../components/DesignMethodSelector';

import { GraphCanvas } from '@/modules/shared/modules/graph/components/GraphCanvas';

import { VersionHistoryPanel } from '../components/VersionHistoryPanel';

import { VersionDiffView } from '../components/VersionDiffView';

import { ontologyApi } from '../services/ontologyApi';

import type { GraphNode, GraphEdge } from '@/modules/shared/modules/graph';

import { NodeEdgeEditor } from '../components/NodeEdgeEditor';

import { DatabaseExtractor } from '../components/DatabaseExtractor';

import { NLExtractor } from '../components/NLExtractor';

import { PageTourWrapper, ontologyDesignerTourSteps, PAGE_IDS } from '@/modules/guide';

import { AIChatPanel } from '@/modules/ai-assistant';


/* ── Constants ──────────────────────────────────────────────────────── */



const PROPERTY_TYPE_OPTIONS = ['STRING', 'INTEGER', 'FLOAT', 'BOOLEAN', 'DATETIME', 'GEOPOINT', 'JSON', 'REFERENCE']

  .map((t) => ({ label: t, value: t }));

const OBJ_TYPE_OPTS = (objectTypes: ObjectTypeDefinition[]) =>

  objectTypes.map((t) => ({ label: t.display_name || t.name, value: t.type_id }));



/* ── TypeDefList — reusable left panel ──────────────────────────────── */



interface TypeDefListProps<T extends { name: string; display_name?: string; description?: string }> {

  items: T[]; selectedId: string | null; onSelect: (id: string) => void; onDelete: (id: string) => void;

  getId: (item: T) => string;

  extra?: (item: T) => React.ReactNode; searchPlaceholder?: string;

}



function TypeDefList<T extends { name: string; display_name?: string; description?: string }>({
  items, selectedId, onSelect, onDelete, getId, extra, searchPlaceholder,
}: TypeDefListProps<T>) {

  const { t } = useI18n('ontology');
  const [search, setSearch] = useState('');

  const resolvedPlaceholder = searchPlaceholder ?? t('搜索...');

  const filtered = useMemo(() => {

    if (!search) return items;

    const lower = search.toLowerCase();

    return items.filter((t) => t.name.toLowerCase().includes(lower) || (t.display_name || '').toLowerCase().includes(lower));

  }, [items, search]);



  return (

    <Card title={null} size="small" style={{ height: '100%' }} styles={{ body: { padding: 0 } }}>

      <div style={{ padding: '8px 12px' }}>

        <Input prefix={<SearchOutlined />} placeholder={resolvedPlaceholder} value={search}

          onChange={(e) => setSearch(e.target.value)} allowClear size="small" />

      </div>

      {filtered.length === 0 ? (

        <Empty description={t('暂无数据')} image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: '24px 0' }} />

      ) : (

        <div style={{ overflow: 'auto' }}>

          {filtered.map((item, idx) => {

            const itemId = getId(item);

            return (

              <div

                key={itemId ?? idx}

                onClick={() => onSelect(itemId)}

                style={{

                  padding: '8px 12px', cursor: 'pointer',

                  background: selectedId === itemId ? '#e6f7ff' : 'transparent',

                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',

                  borderBottom: '1px solid #f0f0f0',

                }}

              >

                <div style={{ flex: 1, minWidth: 0 }}>

                  <div style={{ fontWeight: 500 }}>{item.display_name || item.name}{extra?.(item)}</div>

                  {item.description && item.description !== item.name && (

                    <div style={{ fontSize: 12, color: '#999', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.description}</div>

                  )}

                </div>

                <Popconfirm title={t('确认删除？')} onConfirm={(e) => e?.stopPropagation()}>

                  <AntButton type="text" danger size="small" icon={<DeleteOutlined />}

                    onClick={(e) => { e?.stopPropagation(); onDelete(itemId); }} />

                </Popconfirm>

              </div>

            );

          })}

        </div>

      )}

    </Card>

  );

}



/* ── ObjectTypeEditor — full form with properties & links ──────────── */



interface ObjectTypeEditorProps {

  item: ObjectTypeDefinition | null; objectTypes: ObjectTypeDefinition[];

  onSave: (typeId: string, data: Record<string, unknown>) => void;

}



function ObjectTypeEditor({ item, objectTypes, onSave }: ObjectTypeEditorProps) {

  const { t } = useI18n('ontology');
  const [form] = Form.useForm();

  const CLASSIFICATION_OPTIONS = [
    { label: `TS - ${t('绝密')}`, value: 'TS' }, { label: `S - ${t('机密')}`, value: 'S' },
    { label: `C - ${t('秘密')}`, value: 'C' }, { label: `U - ${t('公开')}`, value: 'U' },
  ];

  const CARDINALITY_OPTIONS = [
    { label: '1:1', value: 'ONE_TO_ONE' }, { label: '1:N', value: 'ONE_TO_MANY' },
    { label: 'N:1', value: 'MANY_TO_ONE' }, { label: 'N:N', value: 'MANY_TO_MANY' },
    { label: 'N:M', value: 'MANY_TO_MANY_ALT' },
  ];

  const LINK_TYPE_OPTIONS = [
    { label: t('关联'), value: 'ASSOCIATION' },
    { label: t('组合'), value: 'COMPOSITION' },
    { label: t('依赖'), value: 'DEPENDENCY' },
    { label: t('继承'), value: 'INHERITANCE' },
  ];

  const [properties, setProperties] = useState<Array<Record<string, unknown>>>([]);

  const [links, setLinks] = useState<Array<Record<string, unknown>>>([]);



  useEffect(() => {

    if (item) {

      form.setFieldsValue({ name: item.name, display_name: item.display_name || '', description: item.description || '', classification_level: item.classification_level || 'U' });

      setProperties((item.properties as Array<Record<string, unknown>>) || []);

      setLinks([]);

    } else { form.resetFields(); setProperties([]); setLinks([]); }

  }, [item, form]);



  if (!item) return <Card><Form form={form} layout="vertical"><Empty description={t('请选择一个对象类型')} /></Form></Card>;



  const handleSave = async () => { const v = await form.validateFields(); onSave(item.type_id, { ...v, properties, links }); };

  const addProp = () => setProperties((p) => [...p, { name: '', property_type: 'STRING', required: false }]);

  const rmProp = (i: number) => setProperties((p) => p.filter((_, j) => j !== i));

  const updProp = (i: number, k: string, v: unknown) => setProperties((p) => p.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  const addLink = () => setLinks((p) => [...p, { name: '', target_type: '', cardinality: 'ONE_TO_MANY', link_type: 'ASSOCIATION' }]);

  const rmLink = (i: number) => setLinks((p) => p.filter((_, j) => j !== i));

  const updLink = (i: number, k: string, v: unknown) => setLinks((p) => p.map((x, j) => (j === i ? { ...x, [k]: v } : x)));



  return (

    <Card title={item.display_name || item.name} extra={<AntButton type="primary" onClick={handleSave}>{t('保存')}</AntButton>}
      style={{ height: '100%', overflow: 'auto' }}>

      <Form form={form} layout="vertical">

        <Row gutter={16}>

          <Col span={8}><Form.Item name="name" label={t('名称')} rules={[{ required: true, message: t('名称') + ' ' + t('entityType.required') }]}><Input /></Form.Item></Col>

          <Col span={8}><Form.Item name="display_name" label={t('显示名称')}><Input /></Form.Item></Col>

          <Col span={8}><Form.Item name="classification_level" label={t('密级')} initialValue="U"><AntSelect options={CLASSIFICATION_OPTIONS} /></Form.Item></Col>

        </Row>

        <Form.Item name="description" label={t('描述')}><Input.TextArea rows={2} /></Form.Item>

      </Form>

      <Divider titlePlacement="left">{t('属性列表')}</Divider>

      {properties.map((prop, idx) => (

        <Row key={idx} gutter={8} style={{ marginBottom: 8 }} align="middle">

          <Col span={5}><Input placeholder={t('属性名')} value={prop.name as string} onChange={(e) => updProp(idx, 'name', e.target.value)} size="small" /></Col>

          <Col span={4}><AntSelect placeholder={t('数据类型')} value={prop.property_type as string} onChange={(v) => updProp(idx, 'property_type', v)} options={PROPERTY_TYPE_OPTIONS} size="small" style={{ width: '100%' }} /></Col>

          <Col span={3}><AntSelect placeholder={t('必填')} value={prop.required ? 'true' : 'false'} onChange={(v) => updProp(idx, 'required', v === 'true')} options={[{ label: t('必填'), value: 'true' }, { label: 'Optional', value: 'false' }]} size="small" style={{ width: '100%' }} /></Col>

          <Col span={5}><Input placeholder={t('默认值')} value={(prop.default_value as string) || ''} onChange={(e) => updProp(idx, 'default_value', e.target.value)} size="small" /></Col>

          <Col span={1}><AntButton type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => rmProp(idx)} /></Col>

        </Row>

      ))}

      <AntButton type="dashed" icon={<PlusOutlined />} onClick={addProp} size="small" style={{ width: '100%' }}>{t('新增属性')}</AntButton>

      <Divider titlePlacement="left">{t('关系列表')}</Divider>

      {links.map((link, idx) => (

        <Row key={idx} gutter={8} style={{ marginBottom: 8 }} align="middle">

          <Col span={4}><Input placeholder={t('关系名')} value={link.name as string} onChange={(e) => updLink(idx, 'name', e.target.value)} size="small" /></Col>

          <Col span={5}><AntSelect placeholder={t('目标对象类型')} value={link.target_type as string || undefined} onChange={(v) => updLink(idx, 'target_type', v)} options={OBJ_TYPE_OPTS(objectTypes)} size="small" style={{ width: '100%' }} /></Col>

          <Col span={4}><AntSelect placeholder={t('基数')} value={link.cardinality as string} onChange={(v) => updLink(idx, 'cardinality', v)} options={CARDINALITY_OPTIONS} size="small" style={{ width: '100%' }} /></Col>

          <Col span={4}><AntSelect placeholder={t('关系类型')} value={link.link_type as string} onChange={(v) => updLink(idx, 'link_type', v)} options={LINK_TYPE_OPTIONS} size="small" style={{ width: '100%' }} /></Col>

          <Col span={1}><AntButton type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => rmLink(idx)} /></Col>

        </Row>

      ))}

      <AntButton type="dashed" icon={<PlusOutlined />} onClick={addLink} size="small" style={{ width: '100%' }}>{t('新增关系')}</AntButton>

    </Card>

  );

}



/* ── SimpleTypeDefEditor — for business types ──────────────────────── */



interface SimpleTypeDefEditorProps {

  item: { name: string; display_name?: string; description?: string; [key: string]: unknown } | null;

  getId: (item: NonNullable<SimpleTypeDefEditorProps['item']>) => string;

  title: string; extraFields?: React.ReactNode;

  onSave: (typeId: string, data: Record<string, unknown>) => void;

}



function SimpleTypeDefEditor({ item, getId, title, extraFields, onSave }: SimpleTypeDefEditorProps) {

  const { t } = useI18n('ontology');
  const [form] = Form.useForm();

  useEffect(() => {

    if (item) form.setFieldsValue({ name: item.name, display_name: item.display_name || '', description: item.description || '' });

    else form.resetFields();

  }, [item, form]);



  if (!item) return <Card><Form form={form} layout="vertical"><Empty description={t('manual.selectType', { type: title })} /></Form></Card>;

  const handleSave = async () => { const v = await form.validateFields(); onSave(getId(item), v); };



  return (

    <Card title={`${title}: ${item.display_name || item.name}`} extra={<AntButton type="primary" onClick={handleSave}>{t('保存')}</AntButton>}
      style={{ height: '100%', overflow: 'auto' }}>

      <Form form={form} layout="vertical">

        <Row gutter={16}>

          <Col span={12}><Form.Item name="name" label={t('名称')} rules={[{ required: true, message: t('名称') + ' ' + t('entityType.required') }]}><Input /></Form.Item></Col>

          <Col span={12}><Form.Item name="display_name" label={t('显示名称')}><Input /></Form.Item></Col>

        </Row>

        <Form.Item name="description" label={t('描述')}><Input.TextArea rows={2} /></Form.Item>

        {extraFields}

      </Form>

    </Card>

  );

}



/* ── Main Page Component ───────────────────────────────────────────── */



export function OntologyDesignerPage() {

  const { currentWorkspace } = useWorkspace();

  const { t } = useI18n('ontology');

  const CLASSIFICATION_OPTIONS = [

    { label: `TS - ${t('绝密')}`, value: 'TS' }, { label: `S - ${t('机密')}`, value: 'S' },

    { label: `C - ${t('秘密')}`, value: 'C' }, { label: `U - ${t('公开')}`, value: 'U' },

  ];

  const CARDINALITY_OPTIONS = [

    { label: '1:1', value: 'ONE_TO_ONE' }, { label: '1:N', value: 'ONE_TO_MANY' },

    { label: 'N:1', value: 'MANY_TO_ONE' }, { label: 'N:N', value: 'MANY_TO_MANY' },

    { label: 'N:M', value: 'MANY_TO_MANY_ALT' },

  ];

  const LINK_TYPE_OPTIONS = [

    { label: t('关联'), value: 'ASSOCIATION' },

    { label: t('组合'), value: 'COMPOSITION' },

    { label: t('依赖'), value: 'DEPENDENCY' },

    { label: t('继承'), value: 'INHERITANCE' },

  ];

  const {

    currentOntology, objectTypes, linkTypes, actionTypes,

    processTypes, ruleTypes, functionTypes, indicatorTypes,

    loading, error, selectOntology, createOntology,

    createObjectType, updateObjectType, deleteObjectType,

    createLinkType, updateLinkType, deleteLinkType,

    createActionType, updateActionType, deleteActionType,

    createProcessType, updateProcessType, deleteProcessType,

    createRuleType, updateRuleType, deleteRuleType,

    createFunctionType, updateFunctionType, deleteFunctionType,

    createIndicatorType, updateIndicatorType, deleteIndicatorType,

    commitVersion, loadGraph, clearCurrentOntology,

  } = useOntologyStore();



  const [selectorOpen, setSelectorOpen] = useState(false);

  const [selectorCreate, setSelectorCreate] = useState(false);

  const [designMethod, setDesignMethod] = useState<DesignMethod | null>(null);

  const [activeTab, setActiveTab] = useState('object');

  const [selectedIdMap, setSelectedIdMap] = useState<Record<string, string | null>>({});

  const [commitModalOpen, setCommitModalOpen] = useState(false);

  const [commitForm] = Form.useForm();



  // ── Version history state ──────────────────────────────────────────

  const [versionDrawerOpen, setVersionDrawerOpen] = useState(false);

  const [diffModalOpen, setDiffModalOpen] = useState(false);

  const [diffData, setDiffData] = useState<Record<string, unknown> | null>(null);

  const [diffVersionA, setDiffVersionA] = useState('');

  // ── AI Assistant state ──────────────────────────────────────────
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false);

  const [diffVersionB, setDiffVersionB] = useState('');

  const [diffLoading, setDiffLoading] = useState(false);



  // Graph editor state

  const [editorVisible, setEditorVisible] = useState(false);

  const [editorNode, setEditorNode] = useState<GraphNode | undefined>();

  const [editorEdge, setEditorEdge] = useState<GraphEdge | undefined>();



  useEffect(() => { if (!currentOntology) { setSelectorOpen(true); setSelectorCreate(false); } }, [currentOntology]);

  // 工作空间切换时，如果当前本体不属于新工作空间，清空选择

  useEffect(() => {

    if (currentWorkspace && currentOntology && currentOntology.workspace_id && currentOntology.workspace_id !== currentWorkspace) {

      clearCurrentOntology();

      setSelectorOpen(true);

      setSelectorCreate(false);

    }

  }, [currentWorkspace]);



  // 本体已有类型数据时，直接进入手工设计视图（查看已有内容）

  useEffect(() => {

    if (currentOntology && !designMethod) {

      const hasTypes = objectTypes.length > 0 || linkTypes.length > 0 || actionTypes.length > 0

        || processTypes.length > 0 || ruleTypes.length > 0 || functionTypes.length > 0 || indicatorTypes.length > 0;

      if (hasTypes) {

        setDesignMethod('manual');

      }

    }

  }, [currentOntology, objectTypes, linkTypes, actionTypes, processTypes, ruleTypes, functionTypes, indicatorTypes, designMethod]);



  const handleOntologySelect = useCallback(async (item: OntologyItem) => {

    setSelectorOpen(false);

    await selectOntology(item.ontology_id);

    // 选择本体后不重置 designMethod，由 useEffect 根据类型数据自动决定

    setSelectedIdMap({});

  }, [selectOntology]);



  const handleCommit = useCallback(async () => {

    try {

      const values = await commitForm.validateFields();

      await commitVersion(values.changelog);

      message.success(t('版本提交成功'));

      setCommitModalOpen(false);

      commitForm.resetFields();

    } catch { /* validation */ }

  }, [commitVersion, commitForm]);



  // ── Version diff handler ──────────────────────────────────────────

  const handleDiff = useCallback(async (versionIdA: string, versionIdB: string) => {

    if (!currentOntology) return;

    setDiffLoading(true);

    setDiffVersionA(versionIdA);

    setDiffVersionB(versionIdB);

    try {

      const result = await ontologyApi.schemaVersions.diff(currentOntology.ontology_id, versionIdA, versionIdB);

      setDiffData(result as Record<string, unknown>);

      setDiffModalOpen(true);

    } catch (e) {

      message.error(t('manual.versionCompareFailed', { msg: (e as Error).message }));

    } finally {

      setDiffLoading(false);

    }

  }, [currentOntology]);



  // ── Version rollback handler ──────────────────────────────────────

  const handleRollback = useCallback(async (_versionId: string) => {

    // Reload all type definitions after rollback

    if (!currentOntology) return;

    await selectOntology(currentOntology.ontology_id);

  }, [currentOntology, selectOntology]);



  const handleGraphNodeClick = useCallback((node: GraphNode) => {

    setEditorNode(node);

    setEditorEdge(undefined);

    setEditorVisible(true);

  }, []);



  const handleGraphEdgeClick = useCallback((edge: GraphEdge) => {

    setEditorEdge(edge);

    setEditorNode(undefined);

    setEditorVisible(true);

  }, []);



  const handleEditorClose = useCallback(() => {

    setEditorVisible(false);

    setEditorNode(undefined);

    setEditorEdge(undefined);

  }, []);



  const handleEditorUpdate = useCallback(() => {

    if (currentOntology) loadGraph();

  }, [currentOntology, loadGraph]);



  const getSel = (tab: string) => selectedIdMap[tab] ?? null;

  const setSel = (tab: string, id: string | null) => setSelectedIdMap((p) => ({ ...p, [tab]: id }));



  const creators: Record<string, (d: unknown) => Promise<void>> = {

    object: createObjectType, link: createLinkType, action: createActionType,

    process: createProcessType, rule: createRuleType, function: createFunctionType, indicator: createIndicatorType,

  };

  const updaters: Record<string, (id: string, d: unknown) => Promise<void>> = {

    object: updateObjectType, link: updateLinkType, action: updateActionType,

    process: updateProcessType, rule: updateRuleType, function: updateFunctionType, indicator: updateIndicatorType,

  };

  const deleters: Record<string, (id: string) => Promise<void>> = {

    object: deleteObjectType, link: deleteLinkType, action: deleteActionType,

    process: deleteProcessType, rule: deleteRuleType, function: deleteFunctionType, indicator: deleteIndicatorType,

  };



  const handleCreate = useCallback(async (tab: string) => {

    await creators[tab]?.({ name: `new_${tab}_${Date.now()}`, display_name: '', description: '' });

  }, [creators]);



  const handleUpdate = useCallback(async (tab: string, typeId: string, data: Record<string, unknown>) => {

    await updaters[tab]?.(typeId, data);

    message.success(t('保存成功'));

  }, [updaters]);



  const handleDelete = useCallback(async (tab: string, typeId: string) => {

    await deleters[tab]?.(typeId);

    message.success(t('删除成功'));

    if (getSel(tab) === typeId) setSel(tab, null);

  }, [deleters, selectedIdMap]);



  const graphNodes = useMemo(() => objectTypes.map((t) => ({ id: t.type_id, label: t.display_name || t.name, type: 'ObjectType' })), [objectTypes]);

  const graphEdges = useMemo(() => {

    const edges: Array<{ id: string; source: string; target: string; type: string }> = [];

    linkTypes.forEach((l) => { if (l.source_type && l.target_type) edges.push({ id: l.link_id, source: l.source_type, target: l.target_type, type: l.name }); });

    return edges;

  }, [linkTypes]);



  useEffect(() => { if (activeTab === 'graph' && currentOntology) loadGraph(); }, [activeTab, currentOntology, loadGraph]);



  const selObj = objectTypes.find((t) => t.type_id === getSel('object')) || null;

  const selLink = linkTypes.find((t) => t.link_id === getSel('link')) || null;

  const selAction = actionTypes.find((t) => t.action_type_id === getSel('action')) || null;

  const selProcess = processTypes.find((t) => t.process_type_id === getSel('process')) || null;

  const selRule = ruleTypes.find((t) => t.rule_type_id === getSel('rule')) || null;

  const selFunc = functionTypes.find((t) => t.function_type_id === getSel('function')) || null;

  const selInd = indicatorTypes.find((t) => t.indicator_type_id === getSel('indicator')) || null;



  const twoPanel = (tab: string, items: Array<{ name: string; display_name?: string; description?: string; [key: string]: unknown }>, editor: React.ReactNode, getId: (item: typeof items[0]) => string) => (

    <div style={{ height: 'calc(100vh - 200px)', overflow: 'hidden' }}>

      <Row gutter={16} style={{ height: '100%' }}>

        <Col span={6} style={{ height: '100%', overflow: 'auto' }}>

          <div style={{ marginBottom: 8 }}><AntButton type="primary" icon={<PlusOutlined />} block size="small" onClick={() => handleCreate(tab)} data-tour="ontology-add-type-btn">{t('新增')}</AntButton></div>

          <div data-tour="ontology-type-list">

          <TypeDefList items={items} selectedId={getSel(tab)} onSelect={(id) => setSel(tab, id)} onDelete={(id) => handleDelete(tab, id)} getId={getId} />

          </div>

        </Col>

        <Col span={18} style={{ height: '100%', overflow: 'auto' }} data-tour="ontology-editor-panel">{editor}</Col>

      </Row>

    </div>

  );



  const switchOntology = () => { setSelectorCreate(false); setSelectorOpen(true); setDesignMethod(null); };



  // ── Step 1: No ontology selected

  if (!currentOntology) {

    return (

      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

        <PageHeader title={t('本体设计器')} actions={
          <Space>
            <AntButton icon={<SwapOutlined />} onClick={() => { setSelectorCreate(false); setSelectorOpen(true); }}>{t('切换本体')}</AntButton>
            <AntButton type="primary" icon={<PlusOutlined />} onClick={() => { setSelectorCreate(true); setSelectorOpen(true); }}>{t('新建本体')}</AntButton>
          </Space>
        } />

        <OntologySelector open={selectorOpen} onClose={() => setSelectorOpen(false)} onSelect={handleOntologySelect} workspaceId={currentWorkspace || undefined} initialCreate={selectorCreate} />

      </div>

    );

  }



  // ── Step 2: Ontology selected, no design method

  if (!designMethod) {

    return (

      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

        <PageHeader title={t('本体设计器')} actions={<AntButton icon={<SwapOutlined />} onClick={() => setSelectorOpen(true)}>{t('切换本体')}</AntButton>} />

        <DesignMethodSelector onSelect={setDesignMethod} ontologyName={currentOntology.name} />

        <OntologySelector open={selectorOpen} onClose={() => setSelectorOpen(false)} onSelect={handleOntologySelect} workspaceId={currentWorkspace || undefined} initialCreate={selectorCreate} />

      </div>

    );

  }



  // ── Step 3a/3b: Extractor components

  if (designMethod === 'database') {

    return (

      <>

        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

          <PageHeader title={t('本体设计器 — 数据库抽取')} actions={<AntButton icon={<SwapOutlined />} onClick={switchOntology}>{t('切换本体')}</AntButton>} />

          <div style={{ flex: 1, overflow: 'auto', padding: '0 24px' }}>

            <DatabaseExtractor ontologyId={currentOntology.ontology_id} onImportComplete={() => { selectOntology(currentOntology.ontology_id); }} />

          </div>

        </div>

        <OntologySelector open={selectorOpen} onClose={() => setSelectorOpen(false)} onSelect={handleOntologySelect} workspaceId={currentWorkspace || undefined} initialCreate={selectorCreate} />

      </>

    );

  }



  if (designMethod === 'natural_language') {

    return (

      <>

        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

          <PageHeader title={t('本体设计器 — 自然语言提取')} actions={<AntButton icon={<SwapOutlined />} onClick={switchOntology}>{t('切换本体')}</AntButton>} />

          <div style={{ flex: 1, overflow: 'auto', padding: '0 24px' }}>

            <NLExtractor ontologyId={currentOntology.ontology_id} onImportComplete={() => { selectOntology(currentOntology.ontology_id); }} />

          </div>

        </div>

        <OntologySelector open={selectorOpen} onClose={() => setSelectorOpen(false)} onSelect={handleOntologySelect} workspaceId={currentWorkspace || undefined} initialCreate={selectorCreate} />

      </>

    );

  }



  // ── Step 3c: Manual design interface

  const objOpts = OBJ_TYPE_OPTS(objectTypes);

  return (

    <PageTourWrapper pageId={PAGE_IDS.ONTOLOGY_DESIGNER} steps={ontologyDesignerTourSteps}>

    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

      <PageHeader title={t('本体设计器 — {{name}}', { name: currentOntology.name })}

        actions={

          <>

            <Tag color="blue">{currentOntology.status === 'ACTIVE' ? t('活跃') : t('草稿')}</Tag>

            <AntButton icon={<DatabaseOutlined />} onClick={() => setDesignMethod('database')}>{t('数据库抽取')}</AntButton>

            <AntButton icon={<MessageOutlined />} onClick={() => setDesignMethod('natural_language')}>{t('自然语言提取')}</AntButton>

            <AntButton icon={<HistoryOutlined />} onClick={() => setVersionDrawerOpen(true)}>{t('版本历史')}</AntButton>

            <AntButton icon={<SwapOutlined />} onClick={switchOntology}>{t('切换本体')}</AntButton>

            <AntButton icon={<RobotOutlined />} onClick={() => setAiDrawerOpen(true)}
              style={{ background: 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))', color: '#fff', border: 'none' }}>
              {t('AI 助手')}
            </AntButton>

            <AntButton type="primary" icon={<CheckCircleOutlined />} onClick={() => setCommitModalOpen(true)}>{t('提交版本')}</AntButton>

          </>

        }

      />

      {error && <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>}

      <Spin spinning={loading} style={{ width: '100%' }}>

      <Tabs activeKey={activeTab} onChange={setActiveTab} style={{ flex: 1, overflow: 'hidden' }} items={[

        { key: 'object', label: t('对象类型'), children: twoPanel('object', objectTypes, <ObjectTypeEditor item={selObj} objectTypes={objectTypes} onSave={(id, d) => handleUpdate('object', id, d)} />, (t: ObjectTypeDefinition) => t.type_id) },

        { key: 'link', label: t('关系类型'), children: twoPanel('link', linkTypes,

          <SimpleTypeDefEditor item={selLink} getId={(i) => (i as LinkTypeDefinition).link_id} title={t('关系类型')} extraFields={<>

            <Row gutter={16}>

              <Col span={12}><Form.Item name="source_type" label={t('源对象类型')}><AntSelect options={objOpts} /></Form.Item></Col>

              <Col span={12}><Form.Item name="target_type" label={t('目标对象类型')}><AntSelect options={objOpts} /></Form.Item></Col>

            </Row>

            <Row gutter={16}>

              <Col span={12}><Form.Item name="cardinality" label={t('基数')}><AntSelect options={CARDINALITY_OPTIONS} /></Form.Item></Col>

              <Col span={12}><Form.Item name="link_type" label={t('关系类型')}><AntSelect options={LINK_TYPE_OPTIONS} /></Form.Item></Col>

            </Row>

          </>} onSave={(id, d) => handleUpdate('link', id, d)} />, (t: LinkTypeDefinition) => t.link_id) },

        { key: 'action', label: t('动作类型'), children: twoPanel('action', actionTypes,

          <SimpleTypeDefEditor item={selAction} getId={(i) => (i as ActionTypeDefinition).action_type_id} title={t('动作类型')} extraFields={
            <Row gutter={16}>
              <Col span={12}><Form.Item name="target_object_type" label={t('目标对象类型')}><AntSelect options={objOpts} /></Form.Item></Col>
              <Col span={12}><Form.Item name="confirmation_required" label={t('需要确认')} initialValue={true}><AntSelect options={[{ label: t('接受 (Tab)'), value: true }, { label: t('忽略'), value: false }]} /></Form.Item></Col>
            </Row>
          } onSave={(id, d) => handleUpdate('action', id, d)} />, (t: ActionTypeDefinition) => t.action_type_id) },

        { key: 'process', label: t('业务过程'), children: twoPanel('process', processTypes,

          <SimpleTypeDefEditor item={selProcess} getId={(i) => (i as ProcessTypeDefinition).process_type_id} title={t('业务过程')} extraFields={
            <Form.Item name="related_object_types" label={t('关联对象类型')}><AntSelect mode="multiple" options={objOpts} /></Form.Item>
          } onSave={(id, d) => handleUpdate('process', id, d)} />, (t: ProcessTypeDefinition) => t.process_type_id) },

        { key: 'rule', label: t('规则'), children: twoPanel('rule', ruleTypes,

          <SimpleTypeDefEditor item={selRule} getId={(i) => (i as RuleTypeDefinition).rule_type_id} title={t('规则')} extraFields={<>
            <Row gutter={16}>
              <Col span={12}><Form.Item name="condition" label={t('触发条件')}><Input.TextArea rows={2} /></Form.Item></Col>
              <Col span={12}><Form.Item name="action" label={t('约束动作')}><Input.TextArea rows={2} /></Form.Item></Col>
            </Row>
            <Form.Item name="related_object_types" label={t('关联对象类型')}><AntSelect mode="multiple" options={objOpts} /></Form.Item>
          </>} onSave={(id, d) => handleUpdate('rule', id, d)} />, (t: RuleTypeDefinition) => t.rule_type_id) },

        { key: 'function', label: t('逻辑函数'), children: twoPanel('function', functionTypes,

          <SimpleTypeDefEditor item={selFunc} getId={(i) => (i as FunctionTypeDefinition).function_type_id} title={t('逻辑函数')} extraFields={<>
            <Row gutter={16}>
              <Col span={12}><Form.Item name="logic_types" label={t('逻辑类型')}><AntSelect mode="multiple" options={['filter', 'transform', 'validate', 'compute'].map((t) => ({ label: t, value: t }))} /></Form.Item></Col>
              <Col span={12}><Form.Item name="return_type" label={t('返回类型')}><AntSelect options={PROPERTY_TYPE_OPTIONS} /></Form.Item></Col>
            </Row>
            <Form.Item name="related_object_types" label={t('关联对象类型')}><AntSelect mode="multiple" options={objOpts} /></Form.Item>
          </>} onSave={(id, d) => handleUpdate('function', id, d)} />, (t: FunctionTypeDefinition) => t.function_type_id) },

        { key: 'indicator', label: t('指标'), children: twoPanel('indicator', indicatorTypes,

          <SimpleTypeDefEditor item={selInd} getId={(i) => (i as IndicatorTypeDefinition).indicator_type_id} title={t('指标')} extraFields={<>
            <Row gutter={16}>
              <Col span={8}><Form.Item name="indicator_types" label={t('指标类型')}><AntSelect mode="multiple" options={['kpi', 'metric', 'dimension'].map((t) => ({ label: t, value: t }))} /></Form.Item></Col>
              <Col span={8}><Form.Item name="formula" label={t('计算公式')}><Input /></Form.Item></Col>
              <Col span={8}><Form.Item name="unit" label={t('单位')}><Input /></Form.Item></Col>
            </Row>
            <Form.Item name="related_object_types" label={t('关联对象类型')}><AntSelect mode="multiple" options={objOpts} /></Form.Item>
          </>} onSave={(id, d) => handleUpdate('indicator', id, d)} />, (t: IndicatorTypeDefinition) => t.indicator_type_id) },

        { key: 'graph', label: t('图谱'), icon: <ApartmentOutlined />, children: (

          <div>

            {graphNodes.length > 0 ? (

              <>

                <GraphCanvas

                  nodes={graphNodes}

                  edges={graphEdges}

                  onRefresh={() => loadGraph()}

                  onNodeClick={handleGraphNodeClick}

                  onEdgeClick={handleGraphEdgeClick}

                />

              </>

            )

              : <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Empty description={t('暂无图谱数据，请先定义对象类型和关系类型')} /></Card>}

          </div>

        ) },

      ]} />

      </Spin>

      <OntologySelector open={selectorOpen} onClose={() => setSelectorOpen(false)} onSelect={handleOntologySelect} workspaceId={currentWorkspace || undefined} initialCreate={selectorCreate} />

      <NodeEdgeEditor

        open={editorVisible}

        onClose={handleEditorClose}

        selectedNode={editorNode as unknown as Record<string, unknown> | undefined}

        selectedEdge={editorEdge as unknown as Record<string, unknown> | undefined}

        ontologyId={currentOntology?.ontology_id || ''}

        onUpdate={handleEditorUpdate}

      />

      <Modal title={t('提交版本')} open={commitModalOpen} onOk={handleCommit} onCancel={() => { setCommitModalOpen(false); commitForm.resetFields(); }} okText={t('提交')} cancelText={t('取消')}>

        <Form form={commitForm} layout="vertical">

          <Form.Item name="changelog" label={t('变更日志')} rules={[{ required: true, message: t('请输入变更说明') }]}>

            <Input.TextArea rows={4} placeholder={t('描述本次版本变更内容...')} />

          </Form.Item>

        </Form>

      </Modal>



      {/* ── Version History Drawer ──────────────────────────────────── */}

      <Drawer

        title={t('版本历史')}

        placement="right"

        open={versionDrawerOpen}

        onClose={() => setVersionDrawerOpen(false)}

        styles={{ body: { paddingTop: 12 } }}

      >

        <Spin spinning={diffLoading} style={{ width: '100%' }}>

        <VersionHistoryPanel

          ontologyId={currentOntology.ontology_id}

          onRollback={handleRollback}

          onDiff={handleDiff}

        />

        </Spin>

      </Drawer>



      {/* ── Version Diff Modal ──────────────────────────────────────── */}

      <Modal

        title={t('版本差异对比')}

        open={diffModalOpen}

        onCancel={() => { setDiffModalOpen(false); setDiffData(null); }}

        footer={null}

        width={800}

        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}

      >

        <VersionDiffView

          diffData={diffData}

          versionA={diffVersionA}

          versionB={diffVersionB}

        />

      </Modal>

      {/* ── AI Assistant Drawer ──────────────────────────────────────── */}
      <Drawer
        title={null}
        placement="right"
        width={420}
        open={aiDrawerOpen}
        onClose={() => setAiDrawerOpen(false)}
        styles={{ body: { padding: 0, height: '100%' } }}
      >
        <AIChatPanel
          ontologyId={currentOntology.ontology_id}
          workspaceId={currentWorkspace}
          context={{
            object_type: selObj?.name,
            page: 'ontology_designer',
            selected_types: objectTypes.map(t => t.name),
          }}
          onOntologyChanged={() => {
            // AI 执行写操作后，重新加载本体数据
            selectOntology(currentOntology.ontology_id).then(() => {
              message.success(t('保存成功'));
            }).catch(() => {
              message.warning(t('刷新失败，请手动刷新页面'));
            });
          }}
        />
      </Drawer>

    </div>

    </PageTourWrapper>

  );

}

