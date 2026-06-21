import { useState, useEffect } from 'react';
import { Card, Button, Input, Modal, Form, message, Tag, Space, Popconfirm, Select, Switch, Descriptions, Avatar } from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, UserOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { fetchJson, API_BASE } from '@/modules/shared';
import { AdvancedTable } from '@/modules/shared';

const ROLE_OPTIONS = [
  { value: 'system_admin', label: '系统管理员', color: 'red' },
  { value: 'project_owner', label: '项目所有者', color: 'orange' },
  { value: 'team_leader', label: '团队负责人', color: 'blue' },
  { value: 'member', label: '成员', color: 'green' },
  { value: 'guest', label: '访客', color: 'default' },
  { value: 'admin', label: '管理员(旧)', color: 'red' },
  { value: 'commander', label: '负责人(旧)', color: 'orange' },
  { value: 'analyst', label: '分析师(旧)', color: 'blue' },
  { value: 'operator', label: '操作员(旧)', color: 'green' },
  { value: 'observer', label: '观察者(旧)', color: 'default' },
];

interface UserRecord {
  id: string;
  username: string;
  email: string;
  global_role: string;
  role_id: string;
  auth_provider: string;
  is_active: boolean;
}

export function UserManagement() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [viewingUser, setViewingUser] = useState<UserRecord | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await fetchJson<{ users: UserRecord[]; total: number }>(`${API_BASE}/api/auth/users`);
      setUsers(data.users || []);
    } catch {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      await fetchJson(`${API_BASE}/api/auth/users`, {
        method: 'POST',
        body: JSON.stringify(values),
      });
      message.success('用户创建成功');
      setModalOpen(false);
      createForm.resetFields();
      loadUsers();
    } catch (e: any) {
      if (e.message?.includes('409')) {
        message.error('用户名已存在');
      } else if (e.errorFields) {
        return;
      } else {
        message.error('创建失败: ' + (e.message || '未知错误'));
      }
    }
  };

  const handleUpdate = async () => {
    if (!editingUser) return;
    try {
      const values = await editForm.validateFields();
      const payload: Record<string, any> = {};
      if (values.email !== undefined) payload.email = values.email;
      if (values.global_role !== undefined) payload.global_role = values.global_role;
      if (values.is_active !== undefined) payload.is_active = values.is_active;
      if (values.password) payload.password = values.password;

      await fetchJson(`${API_BASE}/api/auth/users/${editingUser.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      message.success('用户更新成功');
      setEditModalOpen(false);
      setEditingUser(null);
      editForm.resetFields();
      loadUsers();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error('更新失败: ' + (e.message || '未知错误'));
    }
  };

  const handleDelete = async (userId: string) => {
    try {
      await fetchJson(`${API_BASE}/api/auth/users/${userId}`, { method: 'DELETE' });
      message.success('用户已删除');
      loadUsers();
    } catch (e: any) {
      message.error('删除失败: ' + (e.message || '未知错误'));
    }
  };

  const openEdit = (user: UserRecord) => {
    setEditingUser(user);
    editForm.setFieldsValue({
      email: user.email,
      global_role: user.global_role,
      is_active: user.is_active,
      password: '',
    });
    setEditModalOpen(true);
  };

  const getRoleLabel = (role: string) => ROLE_OPTIONS.find(r => r.value === role)?.label || role;
  const getRoleColor = (role: string) => ROLE_OPTIONS.find(r => r.value === role)?.color || 'default';

  const filteredUsers = users.filter(u =>
    u.username.toLowerCase().includes(searchText.toLowerCase()) ||
    u.email?.toLowerCase().includes(searchText.toLowerCase()) ||
    getRoleLabel(u.global_role).includes(searchText)
  );

  const columns = [
    {
      title: '用户',
      key: 'user',
      render: (_: any, record: UserRecord) => (
        <Space>
          <Avatar size="small" style={{ backgroundColor: record.is_active ? '#1677ff' : '#d9d9d9' }}>
            {record.username[0]?.toUpperCase()}
          </Avatar>
          <span>{record.username}</span>
        </Space>
      ),
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      render: (email: string) => email || '-',
    },
    {
      title: '角色',
      dataIndex: 'global_role',
      key: 'global_role',
      render: (role: string) => <Tag color={getRoleColor(role)}>{getRoleLabel(role)}</Tag>,
    },
    {
      title: '认证方式',
      dataIndex: 'auth_provider',
      key: 'auth_provider',
      render: (provider: string) => provider === 'local' ? '本地' : provider?.toUpperCase() || '-',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => active ? <Tag color="success">启用</Tag> : <Tag color="error">禁用</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: UserRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button type="link" size="small" onClick={() => { setViewingUser(record); setDetailOpen(true); }}>
            详情
          </Button>
          <Popconfirm
            title="确认删除该用户？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined />
            <span>用户管理</span>
          </Space>
        }
        extra={
          <Space>
            <Input
              placeholder="搜索用户名/邮箱"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ width: 220 }}
              allowClear
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => { createForm.resetFields(); setModalOpen(true); }}>
              新增用户
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          dataSource={filteredUsers}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: t => `共 ${t} 个用户` }}
        />
      </Card>

      <Modal
        title="新增用户"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); createForm.resetFields(); }}
        okText="创建"
        cancelText="取消"
        width={480}
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6位' }]}>
            <Input.Password placeholder="请输入密码" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱（可选）" />
          </Form.Item>
          <Form.Item name="global_role" label="角色" rules={[{ required: true, message: '请选择角色' }]} initialValue="guest">
            <Select options={ROLE_OPTIONS.map(r => ({ value: r.value, label: r.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户 - ${editingUser?.username || ''}`}
        open={editModalOpen}
        onOk={handleUpdate}
        onCancel={() => { setEditModalOpen(false); setEditingUser(null); editForm.resetFields(); }}
        okText="保存"
        cancelText="取消"
        width={480}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item name="global_role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={ROLE_OPTIONS.map(r => ({ value: r.value, label: r.label }))} />
          </Form.Item>
          <Form.Item name="is_active" label="启用状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item name="password" label="重置密码" extra="留空则不修改密码">
            <Input.Password placeholder="输入新密码以重置" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="用户详情"
        open={detailOpen}
        onCancel={() => { setDetailOpen(false); setViewingUser(null); }}
        footer={null}
        width={520}
      >
        {viewingUser && (
          <Descriptions column={1} variant="bordered" size="small" style={{ marginTop: 16 }}>
            <Descriptions.Item label="用户名">{viewingUser.username}</Descriptions.Item>
            <Descriptions.Item label="邮箱">{viewingUser.email || '-'}</Descriptions.Item>
            <Descriptions.Item label="角色">
              <Tag color={getRoleColor(viewingUser.global_role)}>{getRoleLabel(viewingUser.global_role)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="角色ID">{viewingUser.role_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="认证方式">{viewingUser.auth_provider === 'local' ? '本地认证' : viewingUser.auth_provider}</Descriptions.Item>
            <Descriptions.Item label="状态">{viewingUser.is_active ? '启用' : '禁用'}</Descriptions.Item>
            <Descriptions.Item label="用户ID">{viewingUser.id}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
