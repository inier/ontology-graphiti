/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useMemo, useCallback } from 'react';
import {
  Card, Tabs, Table, Tag, Space, Button, Alert, Radio,
  Modal, Form, Input, Checkbox, message, Statistic, Row, Col,
} from 'antd';
import {
  CheckCircleOutlined, ExclamationCircleOutlined,
  EditOutlined, DeleteOutlined, ImportOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';

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

export interface ExtractionPreviewProps {
  sessionId: string;
  result: ExtractionResult;
  conflicts: ExtractionConflict[];
  ontologyId: string;
  onImportComplete?: () => void;
}

type MergeStrategy = 'skip' | 'overwrite' | 'rename';

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

  // Reset form when item changes
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
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function ExtractionPreview({
  sessionId, result, conflicts, ontologyId, onImportComplete,
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

  const [editItem, setEditItem] = useState<EditableItem | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTabKey, setEditTabKey] = useState<string>('object');
  const [importing, setImporting] = useState(false);

  // Local mutable copies of result data
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
  const stats = useMemo(() => ({
    objectTypes: localData.object.length,
    linkTypes: localData.link.length,
    actionTypes: localData.action.length,
    ruleTypes: localData.rule.length,
    processTypes: localData.process.length,
    functionTypes: localData.function.length,
    indicatorTypes: localData.indicator.length,
  }), [localData]);

  // ── Selection helpers ────────────────────────────────────────────
  const toggleSelect = (tabKey: string, name: string) => {
    setSelectedMap((prev) => {
      const list = prev[tabKey] || [];
      return {
        ...prev,
        [tabKey]: list.includes(name) ? list.filter((n) => n !== name) : [...list, name],
      };
    });
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
    try {
      await ontologyApi.extraction.confirm(sessionId, {
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
        data: localData,
      });
      message.success('导入成功');
      onImportComplete?.();
    } catch (e) {
      message.error(`导入失败: ${(e as Error).message}`);
    } finally {
      setImporting(false);
    }
  };

  // ── Tab items ────────────────────────────────────────────────────
  const tabItems = [
    {
      key: 'object',
      label: `对象类型 (${stats.objectTypes})`,
      children: (
        <Table
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
      label: `关系类型 (${stats.linkTypes})`,
      children: (
        <Table
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
      label: `动作类型 (${stats.actionTypes})`,
      children: (
        <Table
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
      label: `规则类型 (${stats.ruleTypes})`,
      children: (
        <Table
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
      label: `流程类型 (${stats.processTypes})`,
      children: (
        <Table
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
      label: `函数类型 (${stats.functionTypes})`,
      children: (
        <Table
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
      label: `指标类型 (${stats.indicatorTypes})`,
      children: (
        <Table
          rowKey="name"
          size="small"
          dataSource={localData.indicator}
          columns={makeColumns(selectedMap.indicator || [], (n) => toggleSelect('indicator', n), handleEdit('indicator'), handleDelete('indicator'))}
          pagination={false}
        />
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Summary ──────────────────────────────────────────────── */}
      <Card size="small">
        <Row gutter={16}>
          <Col span={3}><Statistic title="对象类型" value={stats.objectTypes} prefix={<CheckCircleOutlined style={{ color: '#1677ff' }} />} /></Col>
          <Col span={3}><Statistic title="关系类型" value={stats.linkTypes} prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />} /></Col>
          <Col span={3}><Statistic title="动作类型" value={stats.actionTypes} prefix={<CheckCircleOutlined style={{ color: '#722ed1' }} />} /></Col>
          <Col span={3}><Statistic title="规则类型" value={stats.ruleTypes} prefix={<CheckCircleOutlined style={{ color: '#fa8c16' }} />} /></Col>
          <Col span={3}><Statistic title="流程类型" value={stats.processTypes} prefix={<CheckCircleOutlined style={{ color: '#13c2c2' }} />} /></Col>
          <Col span={3}><Statistic title="函数类型" value={stats.functionTypes} prefix={<CheckCircleOutlined style={{ color: '#eb2f96' }} />} /></Col>
          <Col span={3}><Statistic title="指标类型" value={stats.indicatorTypes} prefix={<CheckCircleOutlined style={{ color: '#f5222d' }} />} /></Col>
        </Row>
      </Card>

      {/* ── Conflicts Alert ──────────────────────────────────────── */}
      {conflicts.length > 0 && (
        <Alert
          type="warning"
          showIcon
          icon={<ExclamationCircleOutlined />}
          message={`检测到 ${conflicts.length} 个冲突`}
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

      {/* ── Type Tabs ────────────────────────────────────────────── */}
      <Card size="small" styles={{ body: { padding: '0 16px 16px' } }}>
        <Tabs items={tabItems} />
      </Card>

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
