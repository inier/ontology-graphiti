/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useMemo, useCallback } from 'react';
import {
  Card, Tabs, Tag, Space, Button, Alert, Radio,
  Modal, Form, Input, Checkbox, message, Statistic, Row, Col, Table,
} from 'antd';
import {
  CheckCircleOutlined, ExclamationCircleOutlined,
  EditOutlined, DeleteOutlined, ImportOutlined,
  LinkOutlined, SearchOutlined, LoadingOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import { AdvancedTable } from '@/modules/shared';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ExtractionResult {
  object_types?: any[];
  link_types?: any[];
  action_types?: any[];
  rule_types?: any[];
  process_types?: any[];
  function_types?: any[];
  indicator_types?: any[];
}

export interface ExtractionConflict {
  type: string;
  name: string;
  existing_name?: string;
  field?: string;
  message?: string;
}

export interface ExtractionEntity {
  id: string;
  name: string;
  type: string;
  attributes: Record<string, unknown>;
}

export interface ExtractionRelation {
  id: string;
  name: string;
  source_id: string;
  target_id: string;
  attributes: Record<string, unknown>;
}

export interface ExtractionPreviewProps {
  sessionId: string;
  result: ExtractionResult;
  conflicts: ExtractionConflict[];
  ontologyId: string;
  onImportComplete?: () => void;
  entities?: ExtractionEntity[];
  relations?: ExtractionRelation[];
  onViewProvenance?: (entityId: string) => void;
}

type MergeStrategy = 'skip' | 'overwrite' | 'rename';

type ChannelStatus = 'pending' | 'running' | 'success' | 'failed';

interface ChannelProgress {
  channelA: ChannelStatus;
  channelB: ChannelStatus;
}

interface EditableItem {
  name: string;
  display_name: string;
  description: string;
  [key: string]: any;
}

/* ------------------------------------------------------------------ */
/*  Column factory for type tables                                     */
/* ------------------------------------------------------------------ */

function makeColumns<T extends EditableItem>(
  selectedKeys: string[],
  onToggle: (name: string) => void,
  onEdit: (item: T) => void,
  onDelete: (name: string) => void,
) {
  return [
    {
      title: '',
      dataIndex: 'name',
      width: 48,
      render: (name: string) => (
        <Checkbox checked={selectedKeys.includes(name)} onChange={() => onToggle(name)} />
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 180,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      width: 180,
      render: (v: string) => v || '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '操作',
      width: 100,
      render: (_: unknown, record: T) => (
        <Space size={4}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(record)} />
          <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(record.name)} />
        </Space>
      ),
    },
  ];
}

/* ------------------------------------------------------------------ */
/*  Edit Modal                                                         */
/* ------------------------------------------------------------------ */

function EditItemModal({
  open, item, onClose, onSave,
}: {
  open: boolean;
  item: EditableItem | null;
  onClose: () => void;
  onSave: (updated: EditableItem) => void;
}) {
  const [form] = Form.useForm();

  const handleOpen = useCallback(() => {
    if (item) {
      form.setFieldsValue({
        name: item.name,
        display_name: item.display_name || '',
        description: item.description || '',
      });
    }
  }, [item, form]);

  useMemo(() => { if (open) handleOpen(); }, [open, handleOpen]);

  if (!item) return null;

  const handleOk = async () => {
    const values = await form.validateFields();
    onSave({ ...item, ...values });
    onClose();
  };

  return (
    <Modal
      title="编辑类型定义"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="保存"
      cancelText="取消"
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '名称必填' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="display_name" label="显示名称">
          <Input />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/*  Instance layer: Entity columns                                     */
/* ------------------------------------------------------------------ */

function makeEntityColumns(
  selectedEntityIds: string[],
  onToggleEntity: (id: string) => void,
  onViewProvenance?: (entityId: string) => void,
) {
  return [
    {
      title: '',
      dataIndex: 'id',
      width: 48,
      render: (id: string) => (
        <Checkbox checked={selectedEntityIds.includes(id)} onChange={() => onToggleEntity(id)} />
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 180,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 140,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
    {
      title: '属性',
      dataIndex: 'attributes',
      ellipsis: true,
      render: (v: Record<string, unknown>) => {
        const json = JSON.stringify(v);
        return (
          <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
            {json.length > 120 ? json.slice(0, 120) + '…' : json}
          </span>
        );
      },
    },
    {
      title: '操作',
      width: 64,
      render: (_: unknown, record: ExtractionEntity) =>
        onViewProvenance ? (
          <Button
            type="text"
            size="small"
            icon={<SearchOutlined />}
            title="溯源"
            onClick={() => onViewProvenance(record.id)}
          />
        ) : null,
    },
  ];
}

/* ------------------------------------------------------------------ */
/*  Instance layer: Relation columns                                   */
/* ------------------------------------------------------------------ */

function makeRelationColumns(
  selectedRelationIds: string[],
  onToggleRelation: (id: string) => void,
  onViewProvenance?: (entityId: string) => void,
) {
  return [
    {
      title: '',
      dataIndex: 'id',
      width: 48,
      render: (id: string) => (
        <Checkbox checked={selectedRelationIds.includes(id)} onChange={() => onToggleRelation(id)} />
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 180,
      render: (v: string) => <Tag color="green">{v}</Tag>,
    },
    {
      title: '源实体',
      dataIndex: 'source_id',
      width: 160,
      render: (v: string) => <Tag color="orange">{v}</Tag>,
    },
    {
      title: '目标实体',
      dataIndex: 'target_id',
      width: 160,
      render: (v: string) => <Tag color="purple">{v}</Tag>,
    },
    {
      title: '属性',
      dataIndex: 'attributes',
      ellipsis: true,
      render: (v: Record<string, unknown>) => {
        const json = JSON.stringify(v);
        return (
          <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
            {json.length > 120 ? json.slice(0, 120) + '…' : json}
          </span>
        );
      },
    },
    {
      title: '操作',
      width: 64,
      render: (_: unknown, record: ExtractionRelation) =>
        onViewProvenance ? (
          <Button
            type="text"
            size="small"
            icon={<SearchOutlined />}
            title="溯源"
            onClick={() => onViewProvenance(record.id)}
          />
        ) : null,
    },
  ];
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function ExtractionPreview({
  sessionId, result, conflicts, ontologyId, onImportComplete,
  entities, relations, onViewProvenance,
}: ExtractionPreviewProps) {
  const [mergeStrategy, setMergeStrategy] = useState<MergeStrategy>('skip');
  const [selectedMap, setSelectedMap] = useState<Record<string, string[]>>({
    object: result.object_types?.map((t: any) => t.name) || [],
    link: result.link_types?.map((t: any) => t.name) || [],
    action: result.action_types?.map((t: any) => t.name) || [],
    rule: result.rule_types?.map((t: any) => t.name) || [],
    process: result.process_types?.map((t: any) => t.name) || [],
    function: result.function_types?.map((t: any) => t.name) || [],
    indicator: result.indicator_types?.map((t: any) => t.name) || [],
  });

  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>(
    entities?.map((e) => e.id) || [],
  );
  const [selectedRelationIds, setSelectedRelationIds] = useState<string[]>(
    relations?.map((r) => r.id) || [],
  );

  const [editItem, setEditItem] = useState<EditableItem | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTabKey, setEditTabKey] = useState<string>('object');
  const [importing, setImporting] = useState(false);
  const [channelProgress, setChannelProgress] = useState<ChannelProgress | null>(null);

  const [localData, setLocalData] = useState<Record<string, any[]>>({
    object: result.object_types || [],
    link: result.link_types || [],
    action: result.action_types || [],
    rule: result.rule_types || [],
    process: result.process_types || [],
    function: result.function_types || [],
    indicator: result.indicator_types || [],
  });

  // ── Summary stats ────────────────────────────────────────────────
  const schemaStats = useMemo(() => ({
    objectTypes: localData.object.length,
    linkTypes: localData.link.length,
    actionTypes: localData.action.length,
    ruleTypes: localData.rule.length,
    processTypes: localData.process.length,
    functionTypes: localData.function.length,
    indicatorTypes: localData.indicator.length,
  }), [localData]);

  const totalSchemaTypes = useMemo(
    () => Object.values(schemaStats).reduce((a, b) => a + b, 0),
    [schemaStats],
  );

  const entityCount = entities?.length ?? 0;
  const relationCount = relations?.length ?? 0;

  // ── Selection helpers (schema) ───────────────────────────────────
  const toggleSelect = (tabKey: string, name: string) => {
    setSelectedMap((prev) => {
      const list = prev[tabKey] || [];
      return {
        ...prev,
        [tabKey]: list.includes(name) ? list.filter((n) => n !== name) : [...list, name],
      };
    });
  };

  // ── Selection helpers (instance) ─────────────────────────────────
  const toggleEntitySelect = (id: string) => {
    setSelectedEntityIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const toggleRelationSelect = (id: string) => {
    setSelectedRelationIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  // ── Edit helpers ─────────────────────────────────────────────────
  const handleEdit = (tabKey: string) => (item: EditableItem) => {
    setEditTabKey(tabKey);
    setEditItem(item);
    setEditModalOpen(true);
  };

  const handleEditSave = (updated: EditableItem) => {
    setLocalData((prev) => ({
      ...prev,
      [editTabKey]: prev[editTabKey].map((it) =>
        it.name === updated.name ? { ...it, ...updated } : it,
      ),
    }));
  };

  // ── Delete helpers ───────────────────────────────────────────────
  const handleDelete = (tabKey: string) => (name: string) => {
    setLocalData((prev) => ({
      ...prev,
      [editTabKey]: prev[tabKey].filter((it) => it.name !== name),
    }));
    setSelectedMap((prev) => ({
      ...prev,
      [tabKey]: (prev[tabKey] || []).filter((n) => n !== name),
    }));
  };

  // ── Confirm import ───────────────────────────────────────────────
  const handleConfirm = async () => {
    setImporting(true);
    setChannelProgress({ channelA: 'running', channelB: 'running' });
    try {
      const res = await ontologyApi.extraction.confirm(sessionId, {
        ontology_id: ontologyId,
        merge_strategy: mergeStrategy,
        selected: {
          object_types: selectedMap.object || [],
          link_types: selectedMap.link || [],
          action_types: selectedMap.action || [],
          rule_types: selectedMap.rule || [],
          process_types: selectedMap.process || [],
          function_types: selectedMap.function || [],
          indicator_types: selectedMap.indicator || [],
        },
        data: {
          object_types: localData.object || [],
          link_types: localData.link || [],
          action_types: localData.action || [],
          rule_types: localData.rule || [],
          process_types: localData.process || [],
          function_types: localData.function || [],
          indicator_types: localData.indicator || [],
        },
      }) as Record<string, any>;

      const aStatus: ChannelStatus =
        res.channel_a_status === 'failed' ? 'failed' : 'success';
      const bStatus: ChannelStatus =
        res.channel_b_status === 'failed' ? 'failed' : 'success';

      setChannelProgress({ channelA: aStatus, channelB: bStatus });

      if (bStatus === 'failed') {
        message.warning('索引写入失败，数据已保存但搜索功能可能延迟');
      } else {
        message.success('导入成功');
      }

      onImportComplete?.();
    } catch (e) {
      setChannelProgress({ channelA: 'failed', channelB: 'failed' });
      message.error(`导入失败: ${(e as Error).message}`);
    } finally {
      setImporting(false);
    }
  };

  // ── Schema tab items (7 type categories) ─────────────────────────
  const schemaTabItems = [
    {
      key: 'object',
      label: `对象类型 (${schemaStats.objectTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.object}
          columns={makeColumns(selectedMap.object || [], (n) => toggleSelect('object', n), handleEdit('object'), handleDelete('object'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'link',
      label: `关系类型 (${schemaStats.linkTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.link}
          columns={makeColumns(selectedMap.link || [], (n) => toggleSelect('link', n), handleEdit('link'), handleDelete('link'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'action',
      label: `动作类型 (${schemaStats.actionTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.action}
          columns={makeColumns(selectedMap.action || [], (n) => toggleSelect('action', n), handleEdit('action'), handleDelete('action'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'rule',
      label: `规则类型 (${schemaStats.ruleTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.rule}
          columns={makeColumns(selectedMap.rule || [], (n) => toggleSelect('rule', n), handleEdit('rule'), handleDelete('rule'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'process',
      label: `流程类型 (${schemaStats.processTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.process}
          columns={makeColumns(selectedMap.process || [], (n) => toggleSelect('process', n), handleEdit('process'), handleDelete('process'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'function',
      label: `函数类型 (${schemaStats.functionTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.function}
          columns={makeColumns(selectedMap.function || [], (n) => toggleSelect('function', n), handleEdit('function'), handleDelete('function'))}
          pagination={false}
        />
      ),
    },
    {
      key: 'indicator',
      label: `指标类型 (${schemaStats.indicatorTypes})`,
      children: (
        <AdvancedTable
          rowKey="name"
          size="small"
          dataSource={localData.indicator}
          columns={makeColumns(selectedMap.indicator || [], (n) => toggleSelect('indicator', n), handleEdit('indicator'), handleDelete('indicator'))}
          pagination={false}
        />
      ),
    },
  ];

  // ── Instance tab content ─────────────────────────────────────────
  const instanceContent = (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Card size="small" title={<><LinkOutlined /> 实体</>} styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          size="small"
          dataSource={entities || []}
          columns={makeEntityColumns(selectedEntityIds, toggleEntitySelect, onViewProvenance)}
          pagination={entities && entities.length > 10 ? { pageSize: 10 } : false}
          locale={{ emptyText: '暂无实体数据' }}
        />
      </Card>
      <Card size="small" title={<><LinkOutlined /> 关系</>} styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          size="small"
          dataSource={relations || []}
          columns={makeRelationColumns(selectedRelationIds, toggleRelationSelect, onViewProvenance)}
          pagination={relations && relations.length > 10 ? { pageSize: 10 } : false}
          locale={{ emptyText: '暂无关系数据' }}
        />
      </Card>
    </Space>
  );

  // ── Top-level dual-layer tabs ────────────────────────────────────
  const topLevelTabItems = [
    {
      key: 'schema',
      label: `Schema 层 (${totalSchemaTypes})`,
      children: (
        <Card size="small" styles={{ body: { padding: '0 16px 16px' } }}>
          <Tabs items={schemaTabItems} />
        </Card>
      ),
    },
    {
      key: 'instance',
      label: `Instance 层 (${entityCount} + ${relationCount})`,
      children: instanceContent,
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Summary ──────────────────────────────────────────────── */}
      <Card size="small">
        <Row gutter={16}>
          <Col span={3}><Statistic title="对象类型" value={schemaStats.objectTypes} prefix={<CheckCircleOutlined style={{ color: '#1677ff' }} />} /></Col>
          <Col span={3}><Statistic title="关系类型" value={schemaStats.linkTypes} prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />} /></Col>
          <Col span={3}><Statistic title="动作类型" value={schemaStats.actionTypes} prefix={<CheckCircleOutlined style={{ color: '#722ed1' }} />} /></Col>
          <Col span={3}><Statistic title="规则类型" value={schemaStats.ruleTypes} prefix={<CheckCircleOutlined style={{ color: '#fa8c16' }} />} /></Col>
          <Col span={3}><Statistic title="流程类型" value={schemaStats.processTypes} prefix={<CheckCircleOutlined style={{ color: '#13c2c2' }} />} /></Col>
          <Col span={3}><Statistic title="函数类型" value={schemaStats.functionTypes} prefix={<CheckCircleOutlined style={{ color: '#eb2f96' }} />} /></Col>
          <Col span={3}><Statistic title="指标类型" value={schemaStats.indicatorTypes} prefix={<CheckCircleOutlined style={{ color: '#f5222d' }} />} /></Col>
          <Col span={3}><Statistic title="实体" value={entityCount} prefix={<LinkOutlined style={{ color: '#1677ff' }} />} /></Col>
        </Row>
        <div style={{ marginTop: 8, color: 'rgba(0,0,0,0.45)', fontSize: 13 }}>
          Schema 层: {totalSchemaTypes} 个类型定义 | Instance 层: {entityCount} 个实体 + {relationCount} 个关系
        </div>
      </Card>

      {/* ── Conflicts Alert ──────────────────────────────────────── */}
      {conflicts.length > 0 && (
        <Alert
          type="warning"
          showIcon
          icon={<ExclamationCircleOutlined />}
          title={`检测到 ${conflicts.length} 个冲突`}
          description={
            <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              {conflicts.map((c, i) => (
                <li key={i}>
                  <Tag color="orange">{c.type}</Tag> {c.name}
                  {c.existing_name && ` (已有: ${c.existing_name})`}
                  {c.message && ` - ${c.message}`}
                </li>
              ))}
            </ul>
          }
        />
      )}

      {/* ── Merge Strategy ───────────────────────────────────────── */}
      <Card size="small" title="合并策略">
        <Radio.Group value={mergeStrategy} onChange={(e) => setMergeStrategy(e.target.value)}>
          <Space orientation="vertical">
            <Radio value="skip">跳过 - 保留已有定义，忽略冲突项</Radio>
            <Radio value="overwrite">覆盖 - 用新定义替换已有定义</Radio>
            <Radio value="rename">重命名 - 为冲突项自动生成新名称</Radio>
          </Space>
        </Radio.Group>
      </Card>

      {/* ── Dual-layer Tabs: Schema + Instance ───────────────────── */}
      <Tabs
        items={topLevelTabItems}
        type="card"
        size="large"
      />

      {/* ── Confirm Button ───────────────────────────────────────── */}
      <div style={{ textAlign: 'right' }}>
        <Button
          type="primary"
          icon={<ImportOutlined />}
          onClick={handleConfirm}
          loading={importing}
          size="large"
        >
          确认导入
        </Button>
      </div>

      {/* ── Dual-Channel Progress ────────────────────────────────── */}
      {channelProgress && (
        <Card size="small" title="导入进度">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {channelProgress.channelA === 'running' && <LoadingOutlined spin style={{ color: '#1677ff' }} />}
              {channelProgress.channelA === 'success' && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
              {channelProgress.channelA === 'failed' && <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
              <span>通道 A: 写入实体属性{channelProgress.channelA === 'running' ? '...' : ''}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {channelProgress.channelB === 'running' && <LoadingOutlined spin style={{ color: '#1677ff' }} />}
              {channelProgress.channelB === 'success' && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
              {channelProgress.channelB === 'failed' && <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
              <span>通道 B: 写入双时态索引{channelProgress.channelB === 'running' ? '...' : ''}</span>
            </div>
          </div>
          {channelProgress.channelB === 'failed' && (
            <Alert
              type="warning"
              showIcon
              message="索引写入失败，数据已保存但搜索功能可能延迟"
              style={{ marginTop: 12 }}
            />
          )}
        </Card>
      )}

      {/* ── Edit Modal ───────────────────────────────────────────── */}
      <EditItemModal
        open={editModalOpen}
        item={editItem}
        onClose={() => { setEditModalOpen(false); setEditItem(null); }}
        onSave={handleEditSave}
      />
    </div>
  );
}

export default ExtractionPreview;
