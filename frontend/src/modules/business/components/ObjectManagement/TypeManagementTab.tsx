import { useState } from 'react';
import { Card, Button, Input, Table, Tag, Space, Popconfirm, Modal, Form, Switch, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ObjectType } from './types';

interface TypeManagementTabProps {
  objectTypes: ObjectType[];
  loading: boolean;
  onCreateType: () => void;
  onEditType: (record: ObjectType) => void;
  onDeleteType: (typeId: string) => void;
  onSubmitType: (values: any, editingType: ObjectType | null) => Promise<void>;
}

export function TypeManagementTab({
  objectTypes,
  loading,
  onCreateType,
  onEditType,
  onDeleteType,
  onSubmitType,
}: TypeManagementTabProps) {
  const [typeModalVisible, setTypeModalVisible] = useState(false);
  const [editingType, setEditingType] = useState<ObjectType | null>(null);
  const [typeForm] = Form.useForm();

  const handleCreate = () => {
    setEditingType(null);
    typeForm.resetFields();
    typeForm.setFieldsValue({ is_active: true });
    setTypeModalVisible(true);
  };

  const handleEdit = (record: ObjectType) => {
    setEditingType(record);
    typeForm.setFieldsValue({
      type_id: record.type_id,
      name: record.name,
      display_name: record.display_name,
      description: record.description,
      is_active: record.is_active,
      icon: record.icon,
      color: record.color,
    });
    setTypeModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await typeForm.validateFields();
      await onSubmitType(values, editingType);
      setTypeModalVisible(false);
    } catch {
      message.error('操作失败');
    }
  };

  const columns = [
    { title: '类型ID', dataIndex: 'type_id', key: 'type_id', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '显示名', dataIndex: 'display_name', key: 'display_name', width: 120 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '属性', key: 'properties', width: 80,
      render: (_: unknown, record: ObjectType) => <Tag>{record.properties?.length || 0}</Tag>,
    },
    {
      title: '链接', key: 'links', width: 80,
      render: (_: unknown, record: ObjectType) => <Tag>{record.links?.length || 0}</Tag>,
    },
    {
      title: '动作', key: 'actions', width: 80,
      render: (_: unknown, record: ObjectType) => <Tag>{record.actions?.length || 0}</Tag>,
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: ObjectType) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Popconfirm description="确认删除？" onConfirm={() => onDeleteType(record.type_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 16, fontWeight: 600 }}>对象类型定义</span>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建类型</Button>
      </div>
      <Table
        dataSource={objectTypes}
        columns={columns}
        rowKey="type_id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingType ? '编辑对象类型' : '新建对象类型'}
        open={typeModalVisible}
        onOk={handleSubmit}
        onCancel={() => setTypeModalVisible(false)}
        width={600}
      >
        <Form form={typeForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="display_name" label="显示名">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="type_id" label="类型ID" rules={editingType ? [] : [{ required: true, message: '请输入类型ID' }]}>
            <Input disabled={!!editingType} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
