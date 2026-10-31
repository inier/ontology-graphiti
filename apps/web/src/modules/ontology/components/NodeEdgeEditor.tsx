import { useState, useEffect, useCallback } from 'react';
import {
  Drawer, Descriptions, Input, Select, Button, Popconfirm,
  Tag, Divider, Space, message,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { EditOutlined, DeleteOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { useOntologyStore } from '../stores/ontologyStore';
import type { ObjectTypeDefinition, LinkTypeDefinition } from '../stores/ontologyStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ── Constants ──────────────────────────────────────────────────────── */

const CARDINALITY_OPTIONS = [
  { label: '1:1', value: 'ONE_TO_ONE' },
  { label: '1:N', value: 'ONE_TO_MANY' },
  { label: 'N:1', value: 'MANY_TO_ONE' },
  { label: 'N:N', value: 'MANY_TO_MANY' },
  { label: 'N:M', value: 'MANY_TO_MANY_ALT' },
];

/* ── Props ──────────────────────────────────────────────────────────── */

export interface NodeEdgeEditorProps {
  open: boolean;
  onClose: () => void;
  selectedNode?: Record<string, unknown>; // GraphNode data
  selectedEdge?: Record<string, unknown>; // GraphEdge data
  ontologyId: string;
  onUpdate?: () => void;
}

/* ── Component ──────────────────────────────────────────────────────── */

export function NodeEdgeEditor({
  open,
  onClose,
  selectedNode,
  selectedEdge,
  onUpdate,
}: NodeEdgeEditorProps) {
  const { t } = useI18n('ontology');
  const [form] = Form.useForm();

  const {
    objectTypes,
    linkTypes,
    updateObjectType,
    deleteObjectType,
    updateLinkType,
    deleteLinkType,
  } = useOntologyStore();

  // Determine if we are editing a node or an edge
  const isNode = !!selectedNode;
  const isEdge = !!selectedEdge && !selectedNode;

  // 当前选中对象的 id —— 编辑态与它绑定，选择变化时编辑态自动失效（派生，无需 effect 重置）
  const currentEntityId = String(selectedNode?.id ?? selectedEdge?.id ?? '');
  const [editingId, setEditingId] = useState<string | null>(null);
  const editing = editingId !== null && editingId === currentEntityId && currentEntityId !== '';
  const setEditing = (next: boolean) => setEditingId(next ? currentEntityId : null);

  // Find the full type definition from store
  const nodeTypeDef: ObjectTypeDefinition | undefined = isNode
    ? objectTypes.find((t) => t.type_id === (selectedNode as Record<string, unknown>)?.id)
    : undefined;

  const edgeTypeDef: LinkTypeDefinition | undefined = isEdge
    ? linkTypes.find((t) => t.link_id === (selectedEdge as Record<string, unknown>)?.id)
    : undefined;

  // Populate form when entering edit mode
  useEffect(() => {
    if (!editing) return;
    // 进入编辑态先清空上一轮残留字段，再按当前对象填充
    form.resetFields();
    if (nodeTypeDef) {
      form.setFieldsValue({
        name: nodeTypeDef.name,
        display_name: nodeTypeDef.display_name || '',
        description: nodeTypeDef.description || '',
        classification_level: nodeTypeDef.classification_level || 'U',
      });
    } else if (edgeTypeDef) {
      form.setFieldsValue({
        name: edgeTypeDef.name,
        display_name: edgeTypeDef.display_name || '',
        description: edgeTypeDef.description || '',
        source_type: edgeTypeDef.source_type || '',
        target_type: edgeTypeDef.target_type || '',
        cardinality: edgeTypeDef.cardinality || 'ONE_TO_MANY',
      });
    }
  }, [editing, nodeTypeDef, edgeTypeDef, form]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      if (nodeTypeDef) {
        await updateObjectType(nodeTypeDef.type_id, values);
        message.success(t('nodeEditor.objectTypeUpdated'));
      } else if (edgeTypeDef) {
        await updateLinkType(edgeTypeDef.link_id, values);
        message.success(t('nodeEditor.edgeTypeUpdated'));
      }
      setEditing(false);
      onUpdate?.();
    } catch { /* 忽略：失败时保持当前状态 */ 
      // validation error, do nothing
    }
  }, [nodeTypeDef, edgeTypeDef, updateObjectType, updateLinkType, form, onUpdate, t]);

  const handleDelete = useCallback(async () => {
    try {
      if (nodeTypeDef) {
        await deleteObjectType(nodeTypeDef.type_id);
        message.success(t('nodeEditor.objectTypeDeleted'));
      } else if (edgeTypeDef) {
        await deleteLinkType(edgeTypeDef.link_id);
        message.success(t('nodeEditor.edgeTypeDeleted'));
      }
      onClose();
      onUpdate?.();
    } catch {
      message.error(t('删除失败'));
    }
  }, [nodeTypeDef, edgeTypeDef, deleteObjectType, deleteLinkType, onClose, onUpdate, t]);

  const objTypeOpts = objectTypes.map((t) => ({
    label: t.display_name || t.name,
    value: t.type_id,
  }));

  // ── Render: Node details (ObjectTypeDefinition) ──────────────────

  const renderNodeView = () => {
    if (!nodeTypeDef) {
      return <div style={{ padding: 16, color: '#8c8c8c' }}>{t('nodeEditor.objectTypeNotFound')}</div>;
    }
    const props = (nodeTypeDef.properties as Array<Record<string, unknown>>) || [];
    return (
      <>
        <Descriptions column={1}>
          <Descriptions.Item label={t('节点ID')}>{nodeTypeDef.type_id}</Descriptions.Item>
          <Descriptions.Item label={t('名称')}>{nodeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label={t('显示名称')}>{nodeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('描述')}>{nodeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('分类')}>
            <Tag color={nodeTypeDef.classification_level === 'TS' ? 'red' : nodeTypeDef.classification_level === 'S' ? 'orange' : nodeTypeDef.classification_level === 'C' ? 'blue' : 'green'}>
              {nodeTypeDef.classification_level || 'U'}
            </Tag>
          </Descriptions.Item>
        </Descriptions>

        <Divider titlePlacement="left" style={{ fontSize: 13 }}>{t('属性列表', { count: props.length })}</Divider>
        {props.length === 0 ? (
          <div style={{ color: '#8c8c8c', fontSize: 12 }}>{t('nodeEditor.noProperties')}</div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {props.map((p, i) => (
              <Tag key={i} color="blue">
                {String(p.name || '?')}: {String(p.property_type || 'STRING')}
                {p.required ? ' *' : ''}
              </Tag>
            ))}
          </div>
        )}

        <Divider titlePlacement="left" style={{ fontSize: 13 }}>{t('关联关系')}</Divider>
        {(() => {
          const relatedLinks = linkTypes.filter(
            (l) => l.source_type === nodeTypeDef.type_id || l.target_type === nodeTypeDef.type_id,
          );
          if (relatedLinks.length === 0) {
            return <div style={{ color: '#8c8c8c', fontSize: 12 }}>{t('nodeEditor.noRelatedRelations')}</div>;
          }
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {relatedLinks.map((l) => (
                <div key={l.link_id} style={{ fontSize: 12 }}>
                  <Tag color="purple">{l.display_name || l.name}</Tag>
                  {l.source_type === nodeTypeDef.type_id ? '-> ' : '<- '}
                  {l.cardinality || ''}
                </div>
              ))}
            </div>
          );
        })()}
      </>
    );
  };

  // ── Render: Edge details (LinkTypeDefinition) ────────────────────

  const renderEdgeView = () => {
    if (!edgeTypeDef) {
      return <div style={{ padding: 16, color: '#8c8c8c' }}>{t('nodeEditor.edgeTypeNotFound')}</div>;
    }
    const sourceObj = objectTypes.find((t) => t.type_id === edgeTypeDef.source_type);
    const targetObj = objectTypes.find((t) => t.type_id === edgeTypeDef.target_type);
    return (
      <>
        <Descriptions column={1}>
          <Descriptions.Item label={t('节点ID')}>{edgeTypeDef.link_id}</Descriptions.Item>
          <Descriptions.Item label={t('名称')}>{edgeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label={t('显示名称')}>{edgeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('描述')}>{edgeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('源对象类型')}>
            {sourceObj ? (
              <Tag color="blue">{sourceObj.display_name || sourceObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.source_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('目标对象类型')}>
            {targetObj ? (
              <Tag color="green">{targetObj.display_name || targetObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.target_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('基数')}>
            <Tag color="orange">{edgeTypeDef.cardinality || '-'}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </>
    );
  };

  // ── Render: Node edit form ───────────────────────────────────────

  const renderNodeEdit = () => (
    <>
      <Form.Item name="name" label={t('名称')} rules={[{ required: true, message: t('必填') }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label={t('显示名称')}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label={t('描述')}>
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="classification_level" label={t('分类')} initialValue="U">
        <Select
          options={[
            { label: t('nodeEditor.classificationOptions.TS'), value: 'TS' },
            { label: t('nodeEditor.classificationOptions.S'), value: 'S' },
            { label: t('nodeEditor.classificationOptions.C'), value: 'C' },
            { label: t('nodeEditor.classificationOptions.U'), value: 'U' },
          ]}
        />
      </Form.Item>
    </>
  );

  // ── Render: Edge edit form ───────────────────────────────────────

  const renderEdgeEdit = () => (
    <>
      <Form.Item name="name" label={t('名称')} rules={[{ required: true, message: t('必填') }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label={t('显示名称')}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label={t('描述')}>
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="source_type" label={t('源对象类型')}>
        <Select options={objTypeOpts} allowClear placeholder={t('nodeEditor.selectSourceType')} />
      </Form.Item>
      <Form.Item name="target_type" label={t('目标对象类型')}>
        <Select options={objTypeOpts} allowClear placeholder={t('nodeEditor.selectTargetType')} />
      </Form.Item>
      <Form.Item name="cardinality" label={t('基数')}>
        <Select options={CARDINALITY_OPTIONS} />
      </Form.Item>
    </>
  );

  // ── Title ────────────────────────────────────────────────────────

  const title = isNode
    ? t('对象类型', { name: nodeTypeDef?.display_name || nodeTypeDef?.name || (selectedNode as Record<string, unknown>)?.name || '' })
    : isEdge
      ? t('nodeEditor.edgeTypeTitle', { name: edgeTypeDef?.display_name || edgeTypeDef?.name || (selectedEdge as Record<string, unknown>)?.type || '' })
      : t('节点详情');

  return (
    <Drawer
      title={title}
      placement="right"
      size="medium"
      open={open}
      onClose={onClose}
      extra={
        <Space>
          {editing ? (
            <>
              <Button
                type="primary"
                size="small"
                icon={<SaveOutlined />}
                onClick={handleSave}
              >
                {t('保存')}
              </Button>
              <Button
                size="small"
                icon={<CloseOutlined />}
                onClick={() => setEditing(false)}
              >
                {t('取消')}
              </Button>
            </>
          ) : (
            <>
              <Button
                type="primary"
                size="small"
                icon={<EditOutlined />}
                onClick={() => setEditing(true)}
                disabled={!nodeTypeDef && !edgeTypeDef}
              >
                {t('编辑')}
              </Button>
              <Popconfirm
                title={t('nodeEditor.deleteConfirmTitle')}
                description={t('nodeEditor.deleteConfirmDesc')}
                onConfirm={handleDelete}
                okText={t('确认')}
                cancelText={t('取消')}
              >
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  disabled={!nodeTypeDef && !edgeTypeDef}
                >
                  {t('删除')}
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      }
    >
      <Form form={form} layout="vertical" size="small">
        {editing
          ? (isNode ? renderNodeEdit() : renderEdgeEdit())
          : (isNode ? renderNodeView() : renderEdgeView())
        }
      </Form>
    </Drawer>
  );
}
