import { useState, useCallback, useMemo } from 'react';
import {
  Tabs, Card, Button, Modal, Tag, Space, Input, Select,
  Empty, Descriptions, Alert, Popconfirm, message, Row, Col, Divider,
  Badge, Tooltip, Radio,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, CheckCircleOutlined,
  SearchOutlined, SaveOutlined, CloudUploadOutlined, ExperimentOutlined,
  DatabaseOutlined, ApartmentOutlined, SafetyOutlined,
  HistoryOutlined, ReloadOutlined, SendOutlined,
} from '@ant-design/icons';
import { useRegistryStore } from '../stores/registryStore';
import type { ConsistencyResult } from '../stores/registryStore';
import { useOntologyStore } from '../stores/ontologyStore';
import type {
  ObjectTypeDefinition, LinkTypeDefinition, ActionTypeDefinition,
} from '../stores/ontologyStore';
import { OntologySelector } from '../components/OntologySelector';
import type { OntologyItem } from '../components/OntologySelector';
import { PageHeader } from '@/modules/shared/components/PageHeader';
import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { OverlaySpin } from '@/modules/shared/components/OverlaySpin';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared/components/AdvancedTable';

/* ── Constants ──────────────────────────────────────────────────────── */

const useClassificationOptions = (t: (k: string) => string) => [
  { label: `TS - ${t('classification.TS')}`, value: 'TS' },
  { label: `S - ${t('classification.S')}`, value: 'S' },
  { label: `C - ${t('classification.C')}`, value: 'C' },
  { label: `U - ${t('classification.U')}`, value: 'U' },
];

const CARDINALITY_OPTIONS = [
  { label: '1:1', value: '1:1' },
  { label: '1:N', value: '1:N' },
  { label: 'N:1', value: 'N:1' },
  { label: 'N:N', value: 'N:N' },
  { label: 'N:M', value: 'N:M' },
];

const useLinkTypeOptions = (t: (k: string) => string) => [
  { label: t('relation.linkTypes.association'), value: 'association' },
  { label: t('relation.linkTypes.composition'), value: 'composition' },
  { label: t('relation.linkTypes.dependency'), value: 'dependency' },
  { label: t('relation.linkTypes.inheritance'), value: 'inheritance' },
];

const useSourceTypeOptions = (t: (k: string) => string) => [
  { label: t('unified.sourceNaturalLanguage'), value: 'natural_language' },
  { label: t('unified.sourceManual'), value: 'manual' },
  { label: t('unified.sourceJson'), value: 'json' },
  { label: t('unified.sourceNews'), value: 'news' },
  { label: t('unified.sourceRandom'), value: 'random' },
];

const STATUS_COLORS: Record<string, string> = {
  draft: 'default', active: 'green', archived: 'orange', deprecated: 'red',
};

/* ── Tab 1: Modeling Management ─────────────────────────────────────── */

function ModelingTab() {
  const { t } = useI18n('ontology');
  const registry = useRegistryStore();
  const ontologyStore = useOntologyStore();
  const [subTab, setSubTab] = useState('object');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ObjectTypeDefinition | LinkTypeDefinition | ActionTypeDefinition | null>(null);
  const [form] = Form.useForm();
  const [changelog, setChangelog] = useState('');
  const CLASSIFICATION_OPTIONS = useClassificationOptions(t);
  const LINK_TYPE_OPTIONS = useLinkTypeOptions(t);

  /* -- Object Type columns -- */
  const objColumns = [
    { title: t('unified.name'), dataIndex: 'name', key: 'name', ellipsis: true },
    { title: t('unified.displayName'), dataIndex: 'display_name', key: 'display_name', ellipsis: true, render: (v: string) => v || '-' },
    { title: t('unified.description'), dataIndex: 'description', key: 'description', ellipsis: true, render: (v: string) => v || '-' },
    {
      title: t('unified.classification'), dataIndex: 'classification_level', key: 'classification_level', width: 80,
      render: (v: string) => v ? <Tag color={v === 'TS' ? 'red' : v === 'S' ? 'orange' : v === 'C' ? 'blue' : 'green'}>{v}</Tag> : '-',
    },
    {
      title: t('unified.propsCount'), key: 'props_count', width: 80, align: 'center' as const,
      render: (_: unknown, r: ObjectTypeDefinition) => r.properties?.length ?? 0,
    },
    {
      title: t('unified.actions'), key: 'action', width: 120,
      render: (_: unknown, r: ObjectTypeDefinition) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r, 'object')}>{t('unified.edit')}</Button>
          <Popconfirm title={t('unified.confirmDeleteObjectType')} onConfirm={() => handleDeleteObjectType(r.type_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>{t('unified.delete')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  /* -- Link Type columns -- */
  const linkColumns = [
    { title: t('unified.name'), dataIndex: 'name', key: 'name', ellipsis: true },
    { title: t('unified.sourceType'), dataIndex: 'source_type', key: 'source_type', width: 120, render: (v: string) => v || '-' },
    { title: t('unified.targetType'), dataIndex: 'target_type', key: 'target_type', width: 120, render: (v: string) => v || '-' },
    { title: t('unified.cardinality'), dataIndex: 'cardinality', key: 'cardinality', width: 80, render: (v: string) => v || '-' },
    { title: t('unified.linkTypeCol2'), dataIndex: 'link_type', key: 'link_type', width: 100, render: (v: string) => v || '-' },
    {
      title: t('unified.actions'), key: 'action', width: 120,
      render: (_: unknown, r: LinkTypeDefinition) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r, 'link')}>{t('unified.edit')}</Button>
          <Popconfirm title={t('unified.confirmDeleteLinkType')} onConfirm={() => handleDeleteLinkType(r.link_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>{t('unified.delete')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  /* -- Action Type columns -- */
  const actionColumns = [
    { title: t('unified.name'), dataIndex: 'name', key: 'name', ellipsis: true },
    { title: t('unified.displayName'), dataIndex: 'display_name', key: 'display_name', ellipsis: true, render: (v: string) => v || '-' },
    { title: t('unified.description'), dataIndex: 'description', key: 'description', ellipsis: true, render: (v: string) => v || '-' },
    {
      title: t('unified.actions'), key: 'action', width: 120,
      render: (_: unknown, r: ActionTypeDefinition) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r, 'action')}>{t('unified.edit')}</Button>
          <Popconfirm title={t('unified.confirmDeleteActionType')} onConfirm={() => handleDeleteActionType(r.action_type_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>{t('unified.delete')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  /* -- CRUD handlers -- */
  const handleEdit = (record: ObjectTypeDefinition | LinkTypeDefinition | ActionTypeDefinition, type: string) => {
    setEditingRecord(record);
    setSubTab(type);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleCreate = () => {
    setEditingRecord(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();
      if (subTab === 'object') {
        if (editingRecord) {
          await registry.updateObjectType((editingRecord as ObjectTypeDefinition).type_id, values);
          message.success(t('unified.objectTypeUpdated'));
        } else {
          await registry.createObjectType(values);
          message.success(t('unified.objectTypeCreated'));
        }
      } else if (subTab === 'link') {
        if (editingRecord) {
          await registry.updateLinkType((editingRecord as LinkTypeDefinition).link_id, values);
          message.success(t('unified.linkTypeUpdated'));
        } else {
          await registry.createLinkType(values);
          message.success(t('unified.linkTypeCreated'));
        }
      } else if (subTab === 'action') {
        if (editingRecord) {
          await registry.updateActionType((editingRecord as ActionTypeDefinition).action_type_id, values);
          message.success(t('unified.actionTypeUpdated'));
        } else {
          await registry.createActionType(values);
          message.success(t('unified.actionTypeCreated'));
        }
      }
      setModalOpen(false);
      form.resetFields();
      setEditingRecord(null);
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'errorFields' in e) return;
      message.error(`${t('unified.operationFailed')}: ${(e as Error).message}`);
    }
  };

  const handleDeleteObjectType = async (typeId: string) => {
    try { await registry.deleteObjectType(typeId); message.success(t('unified.deleted')); }
    catch (e) { message.error(`${t('unified.deleteFailed')}: ${(e as Error).message}`); }
  };

  const handleDeleteLinkType = async (linkId: string) => {
    try { await registry.deleteLinkType(linkId); message.success(t('unified.deleted')); }
    catch (e) { message.error(`${t('unified.deleteFailed')}: ${(e as Error).message}`); }
  };

  const handleDeleteActionType = async (actionTypeId: string) => {
    try { await registry.deleteActionType(actionTypeId); message.success(t('unified.deleted')); }
    catch (e) { message.error(`${t('unified.deleteFailed')}: ${(e as Error).message}`); }
  };

  const handleCommit = async () => {
    if (!changelog.trim()) { message.warning(t('unified.inputChangelogWarn')); return; }
    try {
      await registry.commitVersion(changelog);
      message.success(t('unified.versionCommitted'));
      setChangelog('');
    } catch (e) { message.error(`${t('unified.commitFailed')}: ${(e as Error).message}`); }
  };

  /* -- Modal form fields per sub-tab -- */
  const renderModalForm = () => {
    if (subTab === 'object') {
      return (
        <>
          <Form.Item name="name" label={t('unified.name')} rules={[{ required: true, message: t('unified.nameRequired') }]}>
            <Input />
          </Form.Item>
          <Form.Item name="display_name" label={t('unified.displayName')}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('unified.description')}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="classification_level" label={t('unified.classification')}>
            <Select options={CLASSIFICATION_OPTIONS} placeholder={t('unified.selectClassification')} allowClear />
          </Form.Item>
        </>
      );
    }
    if (subTab === 'link') {
      return (
        <>
          <Form.Item name="name" label={t('unified.name')} rules={[{ required: true, message: t('unified.nameRequired') }]}>
            <Input />
          </Form.Item>
          <Form.Item name="source_type" label={t('unified.sourceType')}>
            <Select options={ontologyStore.objectTypes.map((tt) => ({ label: tt.display_name || tt.name, value: tt.type_id }))} allowClear placeholder={t('unified.selectSourceType')} />
          </Form.Item>
          <Form.Item name="target_type" label={t('unified.targetType')}>
            <Select options={ontologyStore.objectTypes.map((tt) => ({ label: tt.display_name || tt.name, value: tt.type_id }))} allowClear placeholder={t('unified.selectTargetType')} />
          </Form.Item>
          <Form.Item name="cardinality" label={t('unified.cardinality')}>
            <Select options={CARDINALITY_OPTIONS} allowClear placeholder={t('unified.selectCardinality')} />
          </Form.Item>
          <Form.Item name="link_type" label={t('unified.linkTypeCol2')}>
            <Select options={LINK_TYPE_OPTIONS} allowClear placeholder={t('unified.selectLinkType')} />
          </Form.Item>
        </>
      );
    }
    // action
    return (
      <>
        <Form.Item name="name" label={t('unified.name')} rules={[{ required: true, message: t('unified.nameRequired') }]}>
          <Input />
        </Form.Item>
        <Form.Item name="display_name" label={t('unified.displayName')}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label={t('unified.description')}>
          <Input.TextArea rows={2} />
        </Form.Item>
      </>
    );
  };

  const tabTitle = subTab === 'object' ? t('unified.objType') : subTab === 'link' ? t('unified.linkTypeCol') : t('unified.actionTypeCol');

  return (
    <div>
    <Tabs activeKey={subTab} onChange={(k) => setSubTab(k)} type="card" items={[
      {
        key: 'object', label: <span><ApartmentOutlined /> {t('unified.objType')} <Badge count={registry.objectTypes.length} size="small" /></span>,
        children: (
          <Card size="small" title={t('unified.objectTypeTitle')} extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreate}>{t('unified.new')}</Button>}>
            <AdvancedTable rowKey="type_id" columns={objColumns} dataSource={registry.objectTypes} size="small" pagination={false} locale={{ emptyText: t('unified.noObjectTypes') }} />
          </Card>
        ),
      },
      {
        key: 'link', label: <span><HistoryOutlined /> {t('unified.linkTypeCol')} <Badge count={registry.linkTypes.length} size="small" /></span>,
        children: (
          <Card size="small" title={t('unified.linkTypeTitle')} extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreate}>{t('unified.new')}</Button>}>
            <AdvancedTable rowKey="link_id" columns={linkColumns} dataSource={registry.linkTypes} size="small" pagination={false} locale={{ emptyText: t('unified.noLinkTypes') }} />
          </Card>
        ),
      },
      {
        key: 'action', label: <span><ExperimentOutlined /> {t('unified.actionTypeCol')} <Badge count={registry.actionTypes.length} size="small" /></span>,
        children: (
          <Card size="small" title={t('unified.actionTypeTitle')} extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreate}>{t('unified.new')}</Button>}>
            <AdvancedTable rowKey="action_type_id" columns={actionColumns} dataSource={registry.actionTypes} size="small" pagination={false} locale={{ emptyText: t('unified.noActionTypes') }} />
          </Card>
        ),
      },
      {
        key: 'version', label: <span><SaveOutlined /> {t('unified.versionMgmt')}</span>,
        children: (
          <Card size="small" title={t('unified.versionSubmit')}>
            <Space.Compact style={{ width: '100%' }}>
              <Input.TextArea value={changelog} onChange={(e) => setChangelog(e.target.value)} placeholder={t('unified.inputChangelog')} rows={2} style={{ flex: 1 }} />
              <Button type="primary" icon={<SaveOutlined />} onClick={handleCommit} loading={registry.loading} style={{ alignSelf: 'flex-end' }}>{t('unified.commitVersion')}</Button>
            </Space.Compact>
            <Divider />
            <AdvancedTable
              rowKey="version_id" size="small" pagination={false}
              dataSource={ontologyStore.schemaVersions}
              locale={{ emptyText: t('unified.noVersionRecords') }}
              columns={[
                { title: t('unified.versionNumber'), dataIndex: 'version_number', key: 'version_number', width: 80 },
                { title: t('unified.changelog'), dataIndex: 'changelog', key: 'changelog', ellipsis: true },
                { title: t('unified.status'), dataIndex: 'status', key: 'status', width: 80, render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag> },
                { title: t('unified.createdAt'), dataIndex: 'created_at', key: 'created_at', width: 170, render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
              ]}
            />
          </Card>
        ),
      },
    ]} />

    <Modal
      title={editingRecord ? `${t('unified.edit')}${tabTitle}` : `${t('unified.new')}${tabTitle}`}
      open={modalOpen}
      onOk={handleModalOk}
      onCancel={() => { setModalOpen(false); form.resetFields(); setEditingRecord(null); }}
      destroyOnHidden
      width={520}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        {renderModalForm()}
      </Form>
    </Modal>
  </div>
  );
}

/* ── Tab 2: Semantic Layer Management ───────────────────────────────── */

function SemanticLayerTab() {
  const { t } = useI18n('ontology');
  const registry = useRegistryStore();
  const ontologyStore = useOntologyStore();
  const [validating, setValidating] = useState(false);
  const [omsObjTypes, setOmsObjTypes] = useState<{ id: string; name: string; display_name?: string }[]>([]);
  const [omsActTypes, setOmsActTypes] = useState<{ id: string; name: string; display_name?: string }[]>([]);
  const [loadingOms, setLoadingOms] = useState(false);

  const consistencyResult: ConsistencyResult | null = registry.consistencyResult;

  const handleValidate = useCallback(async () => {
    setValidating(true);
    try {
      await registry.validateConsistency();
      message.success(t('unified.consistencyPass'));
    } catch (e) {
      message.error(`${t('unified.validateFailed')}: ${(e as Error).message}`);
    } finally {
      setValidating(false);
    }
  }, [registry, t]);

  const loadOmsData = useCallback(async () => {
    setLoadingOms(true);
    try {
      const { registryApi } = await import('../services/registryApi');
      const [objs, acts] = await Promise.all([
        registryApi.oms.listObjectTypes(),
        registryApi.oms.listActionTypes(),
      ]);
      setOmsObjTypes(Array.isArray(objs) ? objs : []);
      setOmsActTypes(Array.isArray(acts) ? acts : []);
    } catch (e) {
      message.error(`${t('unified.loadOmsDataFailed')}: ${(e as Error).message}`);
    } finally {
      setLoadingOms(false);
    }
  }, [t]);

  /* -- Business asset cards -- */
  const assetSections = useMemo(() => [
    { title: t('unified.businessRule'), icon: <SafetyOutlined />, items: ontologyStore.ruleTypes, idKey: 'rule_type_id' as const },
    { title: t('unified.logicFunction'), icon: <ExperimentOutlined />, items: ontologyStore.functionTypes, idKey: 'function_type_id' as const },
    { title: t('unified.indicatorType'), icon: <DatabaseOutlined />, items: ontologyStore.indicatorTypes, idKey: 'indicator_type_id' as const },
    { title: t('unified.businessProcess'), icon: <HistoryOutlined />, items: ontologyStore.processTypes, idKey: 'process_type_id' as const },
  ], [ontologyStore.ruleTypes, ontologyStore.functionTypes, ontologyStore.indicatorTypes, ontologyStore.processTypes, t]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Consistency Validation */}
      <Card size="small" title={t('unified.consistencyValidate')} extra={
        <Button type="primary" size="small" icon={<CheckCircleOutlined />} onClick={handleValidate} loading={validating}>{t('unified.validateNow')}</Button>
      }>
        {consistencyResult ? (
          consistencyResult.valid ? (
            <Alert type="success" title={t('unified.consistencyPass')} description={t('unified.consistencyPassDesc')} showIcon />
          ) : (
            <Alert type="error" title={t('unified.consistencyFail')} showIcon description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {consistencyResult.issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            } />
          )
        ) : (
          <Empty description={t('unified.clickToValidate')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
        {consistencyResult && consistencyResult.warnings.length > 0 && (
          <Alert type="warning" style={{ marginTop: 8 }} title={t('unified.warning')} showIcon description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {consistencyResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          } />
        )}
      </Card>

      {/* OMS Cache Status */}
      <Card size="small" title={t('unified.omsCacheStatus')} extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={loadOmsData} loading={loadingOms}>{t('unified.refresh')}</Button>
      }>
        <Row gutter={16}>
          <Col span={12}>
            <Descriptions column={1} size="small" title={<span><ApartmentOutlined /> {t('unified.objectTypesCount', { count: omsObjTypes.length })}</span>}>
              {omsObjTypes.length === 0 ? (
                <Descriptions.Item label={t('unified.state')}>{t('unified.noCacheData')}</Descriptions.Item>
              ) : (
                omsObjTypes.slice(0, 5).map((tt) => (
                  <Descriptions.Item key={tt.id} label={tt.name}>{tt.display_name || '-'}</Descriptions.Item>
                ))
              )}
              {omsObjTypes.length > 5 && <Descriptions.Item label="...">{t('unified.total', { count: omsObjTypes.length })}</Descriptions.Item>}
            </Descriptions>
          </Col>
          <Col span={12}>
            <Descriptions column={1} size="small" title={<span><ExperimentOutlined /> {t('unified.actionTypesCount', { count: omsActTypes.length })}</span>}>
              {omsActTypes.length === 0 ? (
                <Descriptions.Item label={t('unified.state')}>{t('unified.noCacheData')}</Descriptions.Item>
              ) : (
                omsActTypes.slice(0, 5).map((tt) => (
                  <Descriptions.Item key={tt.id} label={tt.name}>{tt.display_name || '-'}</Descriptions.Item>
                ))
              )}
              {omsActTypes.length > 5 && <Descriptions.Item label="...">{t('unified.total', { count: omsActTypes.length })}</Descriptions.Item>}
            </Descriptions>
          </Col>
        </Row>
      </Card>

      {/* Business Asset Associations */}
      <Card size="small" title={t('unified.businessAssetLinks')}>
        <Row gutter={[12, 12]}>
          {assetSections.map((sec) => (
            <Col key={sec.title} xs={24} sm={12} md={6}>
              <Card size="small" type="inner" title={<span>{sec.icon} {sec.title}</span>}
                extra={<Badge count={sec.items.length} style={{ backgroundColor: sec.items.length > 0 ? '#1677ff' : '#d9d9d9' }} />}
              >
                {sec.items.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('unified.noItems')} />
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>
                    {sec.items.slice(0, 5).map((item: Record<string, unknown>) => (
                      <li key={String(item[sec.idKey])}>{(item as { name: string; display_name?: string }).display_name || (item as { name: string }).name}</li>
                    ))}
                    {sec.items.length > 5 && <li>...{t('unified.total', { count: sec.items.length })}</li>}
                  </ul>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
}

/* ── Tab 3: Extraction Management ───────────────────────────────────── */

function ExtractionTab() {
  const { t } = useI18n('ontology');
  const registry = useRegistryStore();
  const [mode, setMode] = useState<'constrained' | 'exploratory'>('constrained');
  const [inputData, setInputData] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [draftTypes, setDraftTypes] = useState<Record<string, unknown>[]>([]);

  const handleExtract = useCallback(async () => {
    if (!inputData.trim()) { message.warning(t('unified.inputDataWarn')); return; }
    setExtracting(true);
    try {
      // Placeholder: actual extraction API call
      // In constrained mode, validate against existing types
      // In exploratory mode, generate draft type definitions
      if (mode === 'exploratory') {
        // Simulate draft type generation
        setDraftTypes([{ name: 'extracted_type_1', status: 'draft' }]);
      }
      message.success(t('unified.extractComplete'));
    } catch (e) {
      message.error(`${t('unified.extractFailed')}: ${(e as Error).message}`);
    } finally {
      setExtracting(false);
    }
  }, [inputData, mode, t]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Mode Selection */}
      <Card size="small" title={t('unified.extractMode')}>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} optionType="button" buttonStyle="solid">
          <Radio.Button value="constrained">{t('unified.constrainedExtract')}</Radio.Button>
          <Radio.Button value="exploratory">{t('unified.exploratoryExtract')}</Radio.Button>
        </Radio.Group>
        <div style={{ marginTop: 12 }}>
          {mode === 'constrained' ? (
            <Alert type="info" title={t('unified.constrainedExtractInfo')} showIcon />
          ) : (
            <Alert type="info" title={t('unified.exploratoryExtractInfo')} showIcon />
          )}
        </div>
      </Card>

      {/* Extraction Operation */}
      <Card size="small" title={t('unified.extractOperation')}>
        {mode === 'constrained' && registry.objectTypes.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{t('unified.ontologyTypeContext')}</div>
            <Space wrap>
              {registry.objectTypes.map((tt) => (
                <Tag key={tt.type_id} color="blue">{tt.display_name || tt.name}</Tag>
              ))}
            </Space>
          </div>
        )}
        <Input.TextArea
          value={inputData}
          onChange={(e) => setInputData(e.target.value)}
          placeholder={t('unified.inputDataPlaceholder')}
          rows={6}
          style={{ marginBottom: 12 }}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={handleExtract} loading={extracting} block>
          {t('unified.startExtract')}
        </Button>
      </Card>

      {/* Draft Types Review (exploratory mode only) */}
      {mode === 'exploratory' && draftTypes.length > 0 && (
        <Card size="small" title={t('unified.draftTypesForReview')}>
          <AdvancedTable
            rowKey="name" size="small" pagination={false}
            dataSource={draftTypes}
            columns={[
              { title: t('unified.name'), dataIndex: 'name', key: 'name' },
              { title: t('unified.status'), dataIndex: 'status', key: 'status', render: (v: string) => <Tag>{v}</Tag> },
              {
                title: t('unified.actions'), key: 'action', width: 100,
                render: () => (
                  <Space size={4}>
                    <Button type="link" size="small">{t('unified.confirm')}</Button>
                    <Button type="link" size="small" danger>{t('unified.reject')}</Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* Extraction History Placeholder */}
      <Card size="small" title={t('unified.extractHistory')}>
        <Empty description={t('unified.noExtractHistory')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    </div>
  );
}

/* ── Tab 4: Ingest Management ───────────────────────────────────────── */

function IngestTab() {
  const { t } = useI18n('ontology');
  const registry = useRegistryStore();
  const ontologyStore = useOntologyStore();
  const [extractionMode, setExtractionMode] = useState<'constrained' | 'exploratory'>('constrained');
  const [sourceType, setSourceType] = useState('natural_language');
  const [ingestText, setIngestText] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; errors?: string[]; warnings?: string[] } | null>(null);
  const [ingestHistory, setIngestHistory] = useState<Record<string, unknown>[]>([]);
  const SOURCE_TYPE_OPTIONS = useSourceTypeOptions(t);

  const ontologyId = registry.currentOntologyId;

  const handleIngest = useCallback(async () => {
    if (!ingestText.trim()) { message.warning(t('unified.ingestDataWarn')); return; }
    if (!ontologyId) { message.warning(t('unified.selectOntologyWarn')); return; }
    setIngesting(true);
    try {
      const { apiClient } = await import('@/modules/shared/services/apiClient');
      const { API_BASE } = await import('@/config');
      const result = await apiClient.post(`${API_BASE}/api/ingest/unified`, {
        source_type: sourceType,
        text: ingestText,
        ontology_id: ontologyId,
        extraction_mode: extractionMode,
        workspace_id: ontologyStore.currentOntology?.workspace_id,
        scenario_id: ontologyStore.currentOntology?.scenario_id,
      });
      message.success(t('unified.ingestComplete'));
      setIngestHistory((prev) => [{ ...result, _key: Date.now() }, ...prev].slice(0, 10));
      setIngestText('');
    } catch (e) {
      message.error(`${t('unified.ingestFailed')}: ${(e as Error).message}`);
    } finally {
      setIngesting(false);
    }
  }, [ingestText, ontologyId, sourceType, extractionMode, ontologyStore.currentOntology, t]);

  const handleValidate = useCallback(async () => {
    if (!ontologyId) { message.warning(t('unified.selectOntologyWarn')); return; }
    try {
      const { registryApi } = await import('../services/registryApi');
      const result = await registryApi.validateIngest(ontologyId);
      setValidationResult(result);
      message.success(t('unified.contractValidateComplete'));
    } catch (e) {
      message.error(`${t('unified.validationFailed')}: ${(e as Error).message}`);
    }
  }, [ontologyId, t]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Ingest Configuration */}
      <Card size="small" title={t('unified.ingestConfig')}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label={t('unified.boundOntology')}>
            {ontologyStore.currentOntology ? (
              <Space>
                <Tag color="blue">{ontologyStore.currentOntology.name}</Tag>
                <Tag>{ontologyStore.currentOntology.status}</Tag>
                {ontologyStore.currentOntology.current_version && <Tag color="green">v{ontologyStore.currentOntology.current_version}</Tag>}
              </Space>
            ) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label={t('unified.extractModeCol')}>
            <Radio.Group value={extractionMode} onChange={(e) => setExtractionMode(e.target.value)} size="small" optionType="button" buttonStyle="solid">
              <Radio.Button value="constrained">{t('unified.constrained')}</Radio.Button>
              <Radio.Button value="exploratory">{t('unified.exploratory')}</Radio.Button>
            </Radio.Group>
          </Descriptions.Item>
          <Descriptions.Item label={t('unified.dataSourceType')} span={2}>
            <Select value={sourceType} onChange={setSourceType} options={SOURCE_TYPE_OPTIONS} style={{ width: 200 }} />
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Ingest Operation */}
      <Card size="small" title={t('unified.ingestOperation')}>
        <Input.TextArea
          value={ingestText}
          onChange={(e) => setIngestText(e.target.value)}
          placeholder={sourceType === 'json' ? t('unified.jsonDataPlaceholder') : sourceType === 'natural_language' ? t('unified.nlTextPlaceholder') : t('unified.dataPlaceholder')}
          rows={6}
          style={{ marginBottom: 12 }}
        />
        <Button type="primary" icon={<CloudUploadOutlined />} onClick={handleIngest} loading={ingesting} block>
          {t('unified.startIngest')}
        </Button>
      </Card>

      {/* Ingest Contract Validation */}
      <Card size="small" title={t('unified.ingestContract')} extra={
        <Button size="small" icon={<SafetyOutlined />} onClick={handleValidate}>{t('unified.validateContract')}</Button>
      }>
        {validationResult ? (
          validationResult.valid ? (
            <Alert type="success" title={t('unified.contractPass')} showIcon />
          ) : (
            <Alert type="error" title={t('unified.contractFail')} showIcon description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {validationResult.errors?.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            } />
          )
        ) : (
          <Empty description={t('unified.clickToValidateContract')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
        {validationResult && validationResult.warnings && validationResult.warnings.length > 0 && (
          <Alert type="warning" style={{ marginTop: 8 }} title={t('unified.warning')} showIcon description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {validationResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          } />
        )}
      </Card>

      {/* Ingest History */}
      <Card size="small" title={t('unified.ingestHistory')}>
        {ingestHistory.length === 0 ? (
          <Empty description={t('unified.noIngestRecords')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <AdvancedTable
            rowKey="_key" size="small" pagination={false}
            dataSource={ingestHistory}
            columns={[
              { title: t('unified.source'), dataIndex: 'source', key: 'source', render: (v: string) => v || sourceType },
              { title: t('unified.status'), dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'completed' ? 'green' : v === 'failed' ? 'red' : 'processing'}>{v || 'unknown'}</Tag> },
              { title: t('unified.recordCount'), dataIndex: 'record_count', key: 'record_count', width: 80, render: (v: number) => v ?? '-' },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

/* ── Main Page Component ────────────────────────────────────────────── */

export function UnifiedManagementPage() {
  const { t } = useI18n('ontology');
  const { currentWorkspace } = useWorkspace();
  const registry = useRegistryStore();
  const ontologyStore = useOntologyStore();
  const [selectorOpen, setSelectorOpen] = useState(false);

  const handleSelectOntology = useCallback(async (item: OntologyItem) => {
    setSelectorOpen(false);
    try {
      await registry.selectOntology(item.ontology_id);
      await ontologyStore.selectOntology(item.ontology_id);
      message.success(t('unified.ontologySelected', { name: item.name }));
    } catch (e) {
      message.error(`${t('unified.loadOntologyFailed')}: ${(e as Error).message}`);
    }
  }, [registry, ontologyStore, t]);

  const currentOntology = ontologyStore.currentOntology;
  const hasOntology = !!registry.currentOntologyId;

  return (
    <div style={{ padding: '0 0 24px' }}>
      <PageHeader
        title={t('unified.title')}
        actions={
          <Button type="primary" icon={<SearchOutlined />} onClick={() => setSelectorOpen(true)}>
            {hasOntology ? t('unified.switchOntology') : t('unified.selectOntology')}
          </Button>
        }
      />

      {/* Ontology info bar */}
      {hasOntology && currentOntology && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={24} align="middle">
            <Col>
              <Space>
                <span style={{ fontWeight: 600, fontSize: 16 }}>{currentOntology.name}</span>
                <Tag color={STATUS_COLORS[currentOntology.status] || 'default'}>{currentOntology.status}</Tag>
                {currentOntology.current_version && <Tag color="green">v{currentOntology.current_version}</Tag>}
              </Space>
            </Col>
            <Col>
              <span style={{ color: '#888', fontSize: 12 }}>{currentOntology.description}</span>
            </Col>
            <Col flex="auto" />
            <Col>
              <Space size={16}>
                <Tooltip title={t('unified.objType')}><Badge count={registry.objectTypes.length} size="small"><ApartmentOutlined style={{ fontSize: 18 }} /></Badge></Tooltip>
                <Tooltip title={t('unified.linkTypeCol')}><Badge count={registry.linkTypes.length} size="small"><HistoryOutlined style={{ fontSize: 18 }} /></Badge></Tooltip>
                <Tooltip title={t('unified.actionTypeCol')}><Badge count={registry.actionTypes.length} size="small"><ExperimentOutlined style={{ fontSize: 18 }} /></Badge></Tooltip>
              </Space>
            </Col>
          </Row>
        </Card>
      )}

      {/* No ontology selected */}
      {!hasOntology && (
        <Card>
          <Empty description={t('unified.selectOntologyFirst')} image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => setSelectorOpen(true)}>{t('unified.selectOntology')}</Button>
          </Empty>
        </Card>
      )}

      {/* Main Tabs */}
      {hasOntology && (
        <OverlaySpin spinning={registry.loading} tip={t('unified.loading')}>
          <Tabs
            defaultActiveKey="modeling"
            type="line"
            items={[
              {
                key: 'modeling',
                label: <span><ApartmentOutlined /> {t('unified.tabModeling')}</span>,
                children: <ModelingTab />,
              },
              {
                key: 'semantic',
                label: <span><SafetyOutlined /> {t('unified.tabSemantic')}</span>,
                children: <SemanticLayerTab />,
              },
              {
                key: 'extraction',
                label: <span><ExperimentOutlined /> {t('unified.tabExtraction')}</span>,
                children: <ExtractionTab />,
              },
              {
                key: 'ingest',
                label: <span><CloudUploadOutlined /> {t('unified.tabIngest')}</span>,
                children: <IngestTab />,
              },
            ]}
          />
        </OverlaySpin>
      )}

      {/* Ontology Selector Modal */}
      <OntologySelector
        open={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        onSelect={handleSelectOntology}
        workspaceId={currentWorkspace || undefined}
      />
    </div>
  );
}

export default UnifiedManagementPage;
