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

const PROPERTY_TYPE_OPTIONS = ['STRING', 'INTEGER', 'FLOAT', 'BOOLEAN', 'DATETIME', 'GEOPOINT', 'JSON', 'REFERENCE']
  .map((t) => ({ label: t, value: t }));

/* ── Props ──────────────────────────────────────────────────────────── */

export interface NodeEdgeEditorProps {
  visible: boolean;
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
  ontologyId,
  onUpdate,
}: NodeEdgeEditorProps) {
  const { t } = useI18n('ontology');
  const [editing, setEditing] = useState(false);
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

  // Find the full type definition from store
  const nodeTypeDef: ObjectTypeDefinition | undefined = isNode
    ? objectTypes.find((t) => t.id === (selectedNode as Record<string, unknown>)?.id)
    : undefined;

  const edgeTypeDef: LinkTypeDefinition | undefined = isEdge
    ? linkTypes.find((t) => t.id === (selectedEdge as Record<string, unknown>)?.id)
    : undefined;

  // Reset editing state when selection changes
  useEffect(() => {
    setEditing(false);
    form.resetFields();
  }, [selectedNode, selectedEdge, form]);

  // Populate form when entering edit mode
  useEffect(() => {
    if (!editing) return;
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
        await updateObjectType(nodeTypeDef.id, values);
        message.success(t('nodeEditor.objectTypeUpdated'));
      } else if (edgeTypeDef) {
        await updateLinkType(edgeTypeDef.id, values);
        message.success(t('nodeEditor.edgeTypeUpdated'));
      }
      setEditing(false);
      onUpdate?.();
    } catch {
      // validation error, do nothing
    }
  }, [nodeTypeDef, edgeTypeDef, updateObjectType, updateLinkType, form, onUpdate, t]);

  const handleDelete = useCallback(async () => {
    try {
      if (nodeTypeDef) {
        await deleteObjectType(nodeTypeDef.id);
        message.success(t('nodeEditor.objectTypeDeleted'));
      } else if (edgeTypeDef) {
        await deleteLinkType(edgeTypeDef.id);
        message.success(t('nodeEditor.edgeTypeDeleted'));
      }
      onClose();
      onUpdate?.();
    } catch {
      message.error(t('nodeEditor.deleteFailed'));
    }
  }, [nodeTypeDef, edgeTypeDef, deleteObjectType, deleteLinkType, onClose, onUpdate, t]);

  const objTypeOpts = objectTypes.map((t) => ({
    label: t.display_name || t.name,
    value: t.id,
  }));

  // ── Render: Node details (ObjectTypeDefinition) ──────────────────

  const renderNodeView = () => {
    if (!nodeTypeDef) {
      return <div style={{ padding: 16, color: '#8c8c8c' }}>{t('nodeEditor.objectTypeNotFound')}</div>;
    }
    const props = (nodeTypeDef.properties as Array<Record<string, unknown>>) || [];
    return (
      <>
        <Descriptions column={1} size="small" variant="bordered">
          <Descriptions.Item label={t('nodeEditor.nodeId')}>{nodeTypeDef.id}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.name')}>{nodeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.displayName')}>{nodeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.description')}>{nodeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.classification')}>
            <Tag color={nodeTypeDef.classification_level === 'TS' ? 'red' : nodeTypeDef.classification_level === 'S' ? 'orange' : nodeTypeDef.classification_level === 'C' ? 'blue' : 'green'}>
              {nodeTypeDef.classification_level || 'U'}
            </Tag>
          </Descriptions.Item>
        </Descriptions>

        <Divider orientation="left" style={{ fontSize: 13 }}>{t('nodeEditor.propertiesList', { count: props.length })}</Divider>
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

        <Divider orientation="left" style={{ fontSize: 13 }}>{t('nodeEditor.relatedRelations')}</Divider>
        {(() => {
          const relatedLinks = linkTypes.filter(
            (l) => l.source_type === nodeTypeDef.id || l.target_type === nodeTypeDef.id,
          );
          if (relatedLinks.length === 0) {
            return <div style={{ color: '#8c8c8c', fontSize: 12 }}>{t('nodeEditor.noRelatedRelations')}</div>;
          }
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {relatedLinks.map((l) => (
                <div key={l.id} style={{ fontSize: 12 }}>
                  <Tag color="purple">{l.display_name || l.name}</Tag>
                  {l.source_type === nodeTypeDef.id ? '-> ' : '<- '}
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
    const sourceObj = objectTypes.find((t) => t.id === edgeTypeDef.source_type);
    const targetObj = objectTypes.find((t) => t.id === edgeTypeDef.target_type);
    return (
      <>
        <Descriptions column={1} size="small" variant="bordered">
          <Descriptions.Item label={t('nodeEditor.nodeId')}>{edgeTypeDef.id}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.name')}>{edgeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.displayName')}>{edgeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.description')}>{edgeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.sourceObjectType')}>
            {sourceObj ? (
              <Tag color="blue">{sourceObj.display_name || sourceObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.source_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.targetObjectType')}>
            {targetObj ? (
              <Tag color="green">{targetObj.display_name || targetObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.target_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('nodeEditor.cardinality')}>
            <Tag color="orange">{edgeTypeDef.cardinality || '-'}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </>
    );
  };

  // ── Render: Node edit form ───────────────────────────────────────

  const renderNodeEdit = () => (
    <>
      <Form.Item name="name" label={t('nodeEditor.name')} rules={[{ required: true, message: t('nodeEditor.required') }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label={t('nodeEditor.displayName')}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label={t('nodeEditor.description')}>
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="classification_level" label={t('nodeEditor.classification')} initialValue="U">
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
      <Form.Item name="name" label={t('nodeEditor.name')} rules={[{ required: true, message: t('nodeEditor.required') }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label={t('nodeEditor.displayName')}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label={t('nodeEditor.description')}>
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="source_type" label={t('nodeEditor.sourceObjectType')}>
        <Select options={objTypeOpts} allowClear placeholder={t('nodeEditor.selectSourceType')} />
      </Form.Item>
      <Form.Item name="target_type" label={t('nodeEditor.targetObjectType')}>
        <Select options={objTypeOpts} allowClear placeholder={t('nodeEditor.selectTargetType')} />
      </Form.Item>
      <Form.Item name="cardinality" label={t('nodeEditor.cardinality')}>
        <Select options={CARDINALITY_OPTIONS} />
      </Form.Item>
    </>
  );

  // ── Title ────────────────────────────────────────────────────────

  const title = isNode
    ? t('nodeEditor.objectTypeTitle', { name: nodeTypeDef?.display_name || nodeTypeDef?.name || (selectedNode as Record<string, unknown>)?.name || '' })
    : isEdge
      ? t('nodeEditor.edgeTypeTitle', { name: edgeTypeDef?.display_name || edgeTypeDef?.name || (selectedEdge as Record<string, unknown>)?.type || '' })
      : t('nodeEditor.nodeDetail');

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
                {t('nodeEditor.save')}
              </Button>
              <Button
                size="small"
                icon={<CloseOutlined />}
                onClick={() => setEditing(false)}
              >
                {t('nodeEditor.cancel')}
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
                {t('nodeEditor.edit')}
              </Button>
              <Popconfirm
                title={t('nodeEditor.deleteConfirmTitle')}
                description={t('nodeEditor.deleteConfirmDesc')}
                onConfirm={handleDelete}
                okText={t('nodeEditor.confirm')}
                cancelText={t('nodeEditor.cancel')}
              >
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  disabled={!nodeTypeDef && !edgeTypeDef}
                >
                  {t('nodeEditor.delete')}
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
