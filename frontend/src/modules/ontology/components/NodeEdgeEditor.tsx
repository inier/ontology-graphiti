import { useState, useEffect, useCallback } from 'react';
import {
  Drawer, Descriptions, Form, Input, Select, Button, Popconfirm,
  Tag, Divider, Space, message,
} from 'antd';
import { EditOutlined, DeleteOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { useOntologyStore } from '../stores/ontologyStore';
import type { ObjectTypeDefinition, LinkTypeDefinition } from '../stores/ontologyStore';

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
        message.success('对象类型已更新');
      } else if (edgeTypeDef) {
        await updateLinkType(edgeTypeDef.id, values);
        message.success('关系类型已更新');
      }
      setEditing(false);
      onUpdate?.();
    } catch {
      // validation error, do nothing
    }
  }, [nodeTypeDef, edgeTypeDef, updateObjectType, updateLinkType, form, onUpdate]);

  const handleDelete = useCallback(async () => {
    try {
      if (nodeTypeDef) {
        await deleteObjectType(nodeTypeDef.id);
        message.success('对象类型已删除');
      } else if (edgeTypeDef) {
        await deleteLinkType(edgeTypeDef.id);
        message.success('关系类型已删除');
      }
      onClose();
      onUpdate?.();
    } catch {
      message.error('删除失败');
    }
  }, [nodeTypeDef, edgeTypeDef, deleteObjectType, deleteLinkType, onClose, onUpdate]);

  const objTypeOpts = objectTypes.map((t) => ({
    label: t.display_name || t.name,
    value: t.id,
  }));

  // ── Render: Node details (ObjectTypeDefinition) ──────────────────

  const renderNodeView = () => {
    if (!nodeTypeDef) {
      return <div style={{ padding: 16, color: '#8c8c8c' }}>未找到对象类型定义</div>;
    }
    const props = (nodeTypeDef.properties as Array<Record<string, unknown>>) || [];
    return (
      <>
        <Descriptions column={1} size="small" variant="bordered">
          <Descriptions.Item label="ID">{nodeTypeDef.id}</Descriptions.Item>
          <Descriptions.Item label="名称">{nodeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label="显示名称">{nodeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="描述">{nodeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="密级">
            <Tag color={nodeTypeDef.classification_level === 'TS' ? 'red' : nodeTypeDef.classification_level === 'S' ? 'orange' : nodeTypeDef.classification_level === 'C' ? 'blue' : 'green'}>
              {nodeTypeDef.classification_level || 'U'}
            </Tag>
          </Descriptions.Item>
        </Descriptions>

        <Divider orientation="left" style={{ fontSize: 13 }}>属性列表 ({props.length})</Divider>
        {props.length === 0 ? (
          <div style={{ color: '#8c8c8c', fontSize: 12 }}>暂无属性</div>
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

        <Divider orientation="left" style={{ fontSize: 13 }}>关联关系</Divider>
        {(() => {
          const relatedLinks = linkTypes.filter(
            (l) => l.source_type === nodeTypeDef.id || l.target_type === nodeTypeDef.id,
          );
          if (relatedLinks.length === 0) {
            return <div style={{ color: '#8c8c8c', fontSize: 12 }}>暂无关联关系</div>;
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
      return <div style={{ padding: 16, color: '#8c8c8c' }}>未找到关系类型定义</div>;
    }
    const sourceObj = objectTypes.find((t) => t.id === edgeTypeDef.source_type);
    const targetObj = objectTypes.find((t) => t.id === edgeTypeDef.target_type);
    return (
      <>
        <Descriptions column={1} size="small" variant="bordered">
          <Descriptions.Item label="ID">{edgeTypeDef.id}</Descriptions.Item>
          <Descriptions.Item label="名称">{edgeTypeDef.name}</Descriptions.Item>
          <Descriptions.Item label="显示名称">{edgeTypeDef.display_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="描述">{edgeTypeDef.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="源对象类型">
            {sourceObj ? (
              <Tag color="blue">{sourceObj.display_name || sourceObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.source_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="目标对象类型">
            {targetObj ? (
              <Tag color="green">{targetObj.display_name || targetObj.name}</Tag>
            ) : (
              <Tag>{edgeTypeDef.target_type || '-'}</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="基数">
            <Tag color="orange">{edgeTypeDef.cardinality || '-'}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </>
    );
  };

  // ── Render: Node edit form ───────────────────────────────────────

  const renderNodeEdit = () => (
    <Form form={form} layout="vertical" size="small">
      <Form.Item name="name" label="名称" rules={[{ required: true, message: '必填' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label="显示名称">
        <Input />
      </Form.Item>
      <Form.Item name="description" label="描述">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="classification_level" label="密级" initialValue="U">
        <Select
          options={[
            { label: 'TS - 绝密', value: 'TS' },
            { label: 'S - 机密', value: 'S' },
            { label: 'C - 秘密', value: 'C' },
            { label: 'U - 公开', value: 'U' },
          ]}
        />
      </Form.Item>
    </Form>
  );

  // ── Render: Edge edit form ───────────────────────────────────────

  const renderEdgeEdit = () => (
    <Form form={form} layout="vertical" size="small">
      <Form.Item name="name" label="名称" rules={[{ required: true, message: '必填' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="display_name" label="显示名称">
        <Input />
      </Form.Item>
      <Form.Item name="description" label="描述">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item name="source_type" label="源对象类型">
        <Select options={objTypeOpts} allowClear placeholder="选择源对象类型" />
      </Form.Item>
      <Form.Item name="target_type" label="目标对象类型">
        <Select options={objTypeOpts} allowClear placeholder="选择目标对象类型" />
      </Form.Item>
      <Form.Item name="cardinality" label="基数">
        <Select options={CARDINALITY_OPTIONS} />
      </Form.Item>
    </Form>
  );

  // ── Title ────────────────────────────────────────────────────────

  const title = isNode
    ? `对象类型: ${nodeTypeDef?.display_name || nodeTypeDef?.name || (selectedNode as Record<string, unknown>)?.name || ''}`
    : isEdge
      ? `关系类型: ${edgeTypeDef?.display_name || edgeTypeDef?.name || (selectedEdge as Record<string, unknown>)?.type || ''}`
      : '详情';

  return (
    <Drawer
      title={title}
      placement="right"
      width={420}
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
                保存
              </Button>
              <Button
                size="small"
                icon={<CloseOutlined />}
                onClick={() => setEditing(false)}
              >
                取消
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
                编辑
              </Button>
              <Popconfirm
                title="确认删除？"
                description="删除后无法恢复，关联数据可能受影响"
                onConfirm={handleDelete}
                okText="确认"
                cancelText="取消"
              >
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  disabled={!nodeTypeDef && !edgeTypeDef}
                >
                  删除
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      }
    >
      {editing
        ? (isNode ? renderNodeEdit() : renderEdgeEdit())
        : (isNode ? renderNodeView() : renderEdgeView())
      }
    </Drawer>
  );
}
