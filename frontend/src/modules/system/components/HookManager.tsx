import { useState, useEffect } from 'react';
import { Switch, Button, Modal, Select, Card, Tag, Space, message, Popconfirm, Form, Input } from 'antd';
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { AdvancedTable } from '@/modules/shared';

interface HookRecord {
  hook_id: string;
  name: string;
  hook_type: string;
  script: string;
  description: string;
  language: string;
  phase: string;
  priority: number;
  enabled?: boolean;
}

const PHASE_COLORS: Record<string, string> = {
  pre: 'blue',
  post: 'green',
};

const TYPE_COLORS: Record<string, string> = {
  event: 'cyan',
  data: 'purple',
  validation: 'orange',
  transformation: 'geekblue',
  notification: 'magenta',
  custom: 'default',
};

const HOOK_TYPE_OPTIONS = [
  { value: 'event', label: 'Event' },
  { value: 'data', label: 'Data' },
  { value: 'validation', label: 'Validation' },
  { value: 'transformation', label: 'Transformation' },
  { value: 'notification', label: 'Notification' },
  { value: 'custom', label: 'Custom' },
];

const PHASE_OPTIONS = [
  { value: 'pre', label: 'Pre' },
  { value: 'post', label: 'Post' },
];

export default function HookManager() {
  const [hooks, setHooks] = useState<HookRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [typeFilter, setTypeFilter] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadHooks();
  }, []);

  const loadHooks = async (hookType?: string) => {
    setLoading(true);
    try {
      const qs = hookType ? `?hook_type=${encodeURIComponent(hookType)}` : '';
      const data = await apiClient.get<{ hooks: HookRecord[]; total: number }>(`/api/hooks${qs}`);
      setHooks(data.hooks || []);
    } catch {
      setHooks([]);
    } finally {
      setLoading(false);
    }
  };

  const handleTypeFilter = (value: string) => {
    setTypeFilter(value);
    loadHooks(value || undefined);
  };

  const handleRegister = async (values: { name: string; hook_type: string; script: string; description: string; language: string; phase: string; priority: number }) => {
    try {
      await apiClient.post('/api/hooks/register', values);
      message.success('Hook registered');
      setRegisterOpen(false);
      form.resetFields();
      loadHooks(typeFilter || undefined);
    } catch (e) {
      message.error(`Register failed: ${(e as Error).message}`);
    }
  };

  const handleUnregister = async (hookId: string) => {
    try {
      await apiClient.delete(`/api/hooks/${hookId}`);
      message.success('Hook unregistered');
      loadHooks(typeFilter || undefined);
    } catch (e) {
      message.error(`Unregister failed: ${(e as Error).message}`);
    }
  };

  const handleToggle = async (hookId: string, enabled: boolean) => {
    try {
      const endpoint = enabled ? 'enable' : 'disable';
      await apiClient.post(`/api/hooks/${hookId}/${endpoint}`);
      message.success(`Hook ${enabled ? 'enabled' : 'disabled'}`);
      loadHooks(typeFilter || undefined);
    } catch (e) {
      message.error(`Toggle failed: ${(e as Error).message}`);
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: 'Type',
      dataIndex: 'hook_type',
      key: 'hook_type',
      width: 110,
      render: (v: string) => <Tag color={TYPE_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: 'Phase',
      dataIndex: 'phase',
      key: 'phase',
      width: 80,
      render: (v: string) => <Tag color={PHASE_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: HookRecord, b: HookRecord) => a.priority - b.priority,
    },
    {
      title: 'Language',
      dataIndex: 'language',
      key: 'language',
      width: 90,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: 'Enabled',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (v: boolean, record: HookRecord) => (
        <Switch
          checked={v !== false}
          size="small"
          onChange={(checked) => handleToggle(record.hook_id, checked)}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: HookRecord) => (
        <Popconfirm description="Unregister this hook?" onConfirm={() => handleUnregister(record.hook_id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>
            Remove
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="Hook Manager"
        extra={
          <Space>
            <Select
              value={typeFilter}
              onChange={handleTypeFilter}
              placeholder="Filter by type"
              style={{ width: 150 }}
              allowClear
              options={[{ value: '', label: 'All' }, ...HOOK_TYPE_OPTIONS]}
            />
            <Button icon={<ReloadOutlined />} onClick={() => loadHooks(typeFilter || undefined)}>
              Refresh
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setRegisterOpen(true)}>
              Register
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          dataSource={hooks}
          columns={columns}
          rowKey="hook_id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 15 }}
        />
      </Card>

      <Modal
        title="Register Hook"
        open={registerOpen}
        onCancel={() => { setRegisterOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="hook_type" label="Type" rules={[{ required: true }]}>
            <Select options={HOOK_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="phase" label="Phase" initialValue="post">
            <Select options={PHASE_OPTIONS} />
          </Form.Item>
          <Form.Item name="priority" label="Priority" initialValue={100}>
            <Input type="number" />
          </Form.Item>
          <Form.Item name="script" label="Script" rules={[{ required: true }]}>
            <Input.TextArea rows={4} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="language" label="Language" initialValue="python">
            <Select options={[
              { value: 'python', label: 'Python' },
              { value: 'javascript', label: 'JavaScript' },
            ]} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
