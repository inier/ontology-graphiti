import { useState, useEffect } from 'react';
import { Table, Card, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, message, Row, Col, Statistic, Checkbox } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  listRoles,
  getRole,
  createRole,
  updateRole,
  deleteRole,
  listPermissions
} from '../services/rolesApi';
import type { Role, RoleCreate, RoleUpdate, Permission } from '../types';

const { Option } = Select;
const { TextArea } = Input;

export function RoleManager() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [form] = Form.useForm();
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rolesData, permissionsData] = await Promise.all([
        listRoles(),
        listPermissions()
      ]);
      setRoles(rolesData);
      setPermissions(permissionsData);
    } catch (error) {
      console.error('加载数据失败', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingRole(null);
    setSelectedPermissions([]);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    const permissionIds = role.permissions.map(p => p.id);
    setSelectedPermissions(permissionIds);
    form.setFieldsValue({
      name: role.name,
      description: role.description,
      role_type: role.role_type
    });
    setModalVisible(true);
  };

  const handleDelete = async (roleId: string) => {
    try {
      await deleteRole(roleId);
      message.success('删除成功');
      loadData();
    } catch (error) {
      console.error('删除失败', error);
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const roleData: RoleCreate | RoleUpdate = {
        ...values,
        permissions: selectedPermissions
      };

      if (editingRole) {
        await updateRole(editingRole.id, roleData as RoleUpdate);
        message.success('更新成功');
      } else {
        await createRole(roleData as RoleCreate);
        message.success('创建成功');
      }

      setModalVisible(false);
      loadData();
    } catch (error) {
      console.error('操作失败', error);
      message.error('操作失败');
    }
  };

  const handlePermissionChange = (checkedValues: string[]) => {
    setSelectedPermissions(checkedValues);
  };

  const getRoleTypeColor = (roleType: string) => {
    switch (roleType) {
      case 'system_admin':
        return 'red';
      case 'project_owner':
        return 'orange';
      case 'team_leader':
        return 'blue';
      case 'member':
        return 'green';
      case 'guest':
        return 'gray';
      default:
        return 'default';
    }
  };

  const getRoleTypeLabel = (roleType: string) => {
    switch (roleType) {
      case 'system_admin':
        return '系统管理员';
      case 'project_owner':
        return '项目所有者';
      case 'team_leader':
        return '团队领导';
      case 'member':
        return '成员';
      case 'guest':
        return '访客';
      default:
        return roleType;
    }
  };

  const getPermissionScopeLabel = (scope: string) => {
    switch (scope) {
      case 'system':
        return '系统';
      case 'project':
        return '项目';
      case 'resource':
        return '资源';
      case 'data':
        return '数据';
      default:
        return scope;
    }
  };

  const columns = [
    {
      title: '角色名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '角色类型',
      dataIndex: 'role_type',
      key: 'role_type',
      width: 120,
      render: (roleType: string) => (
        <Tag color={getRoleTypeColor(roleType)}>
          {getRoleTypeLabel(roleType)}
        </Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '权限数量',
      dataIndex: 'permissions',
      key: 'permissions',
      width: 100,
      render: (permissions: Permission[]) => permissions.length,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (createdAt: string) => new Date(createdAt).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: Role) => (
        <Space size="middle">
          <Button
            type="primary"
            icon={<EditOutlined />}
            size="small"
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个角色吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              size="small"
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="角色管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新增角色
          </Button>
        }
      >
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic title="角色总数" value={roles.length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="权限总数" value={permissions.length} />
            </Card>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={roles}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title={editingRole ? '编辑角色' : '新增角色'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="角色名称"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="请输入角色名称" />
          </Form.Item>

          <Form.Item
            name="description"
            label="角色描述"
            rules={[{ required: true, message: '请输入角色描述' }]}
          >
            <TextArea
              rows={3}
              placeholder="请输入角色描述"
            />
          </Form.Item>

          <Form.Item
            name="role_type"
            label="角色类型"
            rules={[{ required: true, message: '请选择角色类型' }]}
          >
            <Select placeholder="请选择角色类型">
              <Option value="system_admin">系统管理员</Option>
              <Option value="project_owner">项目所有者</Option>
              <Option value="team_leader">团队领导</Option>
              <Option value="member">成员</Option>
              <Option value="guest">访客</Option>
            </Select>
          </Form.Item>

          <Form.Item label="权限">
            <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #f0f0f0', padding: 16, borderRadius: 4 }}>
              <Checkbox.Group
                options={permissions.map(permission => ({
                  label: (
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <span>{permission.name}</span>
                      <Tag>{getPermissionScopeLabel(permission.scope)}</Tag>
                    </div>
                  ),
                  value: permission.id,
                }))}
                value={selectedPermissions}
                onChange={handlePermissionChange}
              />
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}