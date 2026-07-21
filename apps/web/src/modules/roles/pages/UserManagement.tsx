import { useState, useEffect } from 'react';
import { Card, Button, Input, Modal, Form, message, Tag, Space, Popconfirm, Select, Switch, Descriptions, Avatar } from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, UserOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { fetchJson, API_BASE } from '@/modules/shared';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

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
  const { t } = useI18n();
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

  const ROLE_OPTIONS = [
    { value: 'system_admin', label: t('系统管理员'), color: 'red' },
    { value: 'project_owner', label: t('项目所有者'), color: 'orange' },
    { value: 'team_leader', label: t('团队负责人'), color: 'blue' },
    { value: 'member', label: t('成员'), color: 'green' },
    { value: 'guest', label: t('访客'), color: 'default' },
    { value: 'admin', label: `${t('管理员')}(${t('旧')})`, color: 'red' },
    { value: 'commander', label: `${t('负责人')}(${t('旧')})`, color: 'orange' },
    { value: 'analyst', label: `${t('分析师')}(${t('旧')})`, color: 'blue' },
    { value: 'operator', label: `${t('操作员')}(${t('旧')})`, color: 'green' },
    { value: 'observer', label: `${t('观察者')}(${t('旧')})`, color: 'default' },
  ];

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await fetchJson<{ users: UserRecord[]; total: number }>(`${API_BASE}/api/auth/users`);
      setUsers(data.users || []);
    } catch {
      message.error(t('加载用户列表失败'));
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
      message.success(t('用户创建成功'));
      setModalOpen(false);
      createForm.resetFields();
      loadUsers();
    } catch (e: any) {
      if (e.message?.includes('409')) {
        message.error(t('用户名已存在'));
      } else if (e.errorFields) {
        return;
      } else {
        message.error(t('创建失败') + ': ' + (e.message || t('未知错误')));
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
      message.success(t('用户更新成功'));
      setEditModalOpen(false);
      setEditingUser(null);
      editForm.resetFields();
      loadUsers();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error(t('更新失败') + ': ' + (e.message || t('未知错误')));
    }
  };

  const handleDelete = async (userId: string) => {
    try {
      await fetchJson(`${API_BASE}/api/auth/users/${userId}`, { method: 'DELETE' });
      message.success(t('用户已删除'));
      loadUsers();
    } catch (e: any) {
      message.error(t('删除失败') + ': ' + (e.message || t('未知错误')));
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
    String(getRoleLabel(u.global_role)).includes(searchText)
  );

  const columns = [
    {
      title: t('用户'),
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
      title: t('邮箱'),
      dataIndex: 'email',
      key: 'email',
      render: (email: string) => email || '-',
    },
    {
      title: t('角色'),
      dataIndex: 'global_role',
      key: 'global_role',
      render: (role: string) => <Tag color={getRoleColor(role)}>{getRoleLabel(role)}</Tag>,
    },
    {
      title: t('认证方式'),
      dataIndex: 'auth_provider',
      key: 'auth_provider',
      render: (provider: string) => provider === 'local' ? t('本地') : provider?.toUpperCase() || '-',
    },
    {
      title: t('状态'),
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => active ? <Tag color="success">{t('启用')}</Tag> : <Tag color="error">{t('禁用')}</Tag>,
    },
    {
      title: t('操作'),
      key: 'actions',
      render: (_: any, record: UserRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            {t('编辑')}
          </Button>
          <Button type="link" size="small" onClick={() => { setViewingUser(record); setDetailOpen(true); }}>
            {t('详情')}
          </Button>
          <Popconfirm
            title={t('确认删除该用户？')}
            onConfirm={() => handleDelete(record.id)}
            okText={t('删除')}
            cancelText={t('取消')}
            okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              {t('删除')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined />
            <span>{t('用户管理')}</span>
          </Space>
        }
        extra={
          <Space>
            <Input
              placeholder={t('搜索用户名/邮箱')}
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ width: 220 }}
              allowClear
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => { createForm.resetFields(); setModalOpen(true); }}>
              {t('新增用户')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          dataSource={filteredUsers}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total: number) => t('共 {{n}} 个用户', { n: total }) }}
        />
      </Card>

      <Modal
        title={t('新增用户')}
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); createForm.resetFields(); }}
        okText={t('创建')}
        cancelText={t('取消')}
        width={480}
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="username" label={t('用户名')} rules={[{ required: true, message: t('请输入用户名') }]}>
            <Input prefix={<UserOutlined />} placeholder={t('请输入用户名')} />
          </Form.Item>
          <Form.Item name="password" label={t('密码')} rules={[{ required: true, message: t('请输入密码') }, { min: 6, message: t('密码至少6位') }]}>
            <Input.Password placeholder={t('请输入密码')} />
          </Form.Item>
          <Form.Item name="email" label={t('邮箱')}>
            <Input placeholder={t('请输入邮箱（可选）')} />
          </Form.Item>
          <Form.Item name="global_role" label={t('角色')} rules={[{ required: true, message: t('请选择角色') }]} initialValue="guest">
            <Select options={ROLE_OPTIONS.map(r => ({ value: r.value, label: r.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`${t('编辑用户')} - ${editingUser?.username || ''}`}
        open={editModalOpen}
        onOk={handleUpdate}
        onCancel={() => { setEditModalOpen(false); setEditingUser(null); editForm.resetFields(); }}
        okText={t('保存')}
        cancelText={t('取消')}
        width={480}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="email" label={t('邮箱')}>
            <Input placeholder={t('请输入邮箱')} />
          </Form.Item>
          <Form.Item name="global_role" label={t('角色')} rules={[{ required: true, message: t('请选择角色') }]}>
            <Select options={ROLE_OPTIONS.map(r => ({ value: r.value, label: r.label }))} />
          </Form.Item>
          <Form.Item name="is_active" label={t('启用状态')} valuePropName="checked">
            <Switch checkedChildren={t('启用')} unCheckedChildren={t('禁用')} />
          </Form.Item>
          <Form.Item name="password" label={t('重置密码')} extra={t('留空则不修改密码')}>
            <Input.Password placeholder={t('输入新密码以重置')} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('用户详情')}
        open={detailOpen}
        onCancel={() => { setDetailOpen(false); setViewingUser(null); }}
        footer={null}
        width={520}
      >
        {viewingUser && (
          <Descriptions column={1} style={{ marginTop: 16 }}>
            <Descriptions.Item label={t('用户名')}>{viewingUser.username}</Descriptions.Item>
            <Descriptions.Item label={t('邮箱')}>{viewingUser.email || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('角色')}>
              <Tag color={getRoleColor(viewingUser.global_role)}>{getRoleLabel(viewingUser.global_role)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('角色ID')}>{viewingUser.role_id || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('认证方式')}>{viewingUser.auth_provider === 'local' ? t('本地认证') : viewingUser.auth_provider}</Descriptions.Item>
            <Descriptions.Item label={t('状态')}>{viewingUser.is_active ? t('启用') : t('禁用')}</Descriptions.Item>
            <Descriptions.Item label={t('用户ID')}>{viewingUser.id}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
