import { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, Select, Tag, Space, message, Popconfirm } from 'antd';
import { PlusOutlined, SearchOutlined, DeleteOutlined, SwapOutlined } from '@ant-design/icons';
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/skill`;

interface SkillRecord {
  skill_id: string;
  name: string;
  description: string;
  type: string;
  status: string;
  category: string;
  current_version: string;
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  active: 'green',
  inactive: 'orange',
  deprecated: 'red',
  archived: 'gray',
};

const LIFECYCLE_OPTIONS: Record<string, string[]> = {
  draft: ['active', 'archived'],
  active: ['inactive', 'deprecated'],
  inactive: ['active', 'deprecated', 'archived'],
  deprecated: ['archived'],
  archived: [],
};

export function SkillManager() {
  const [skills, setSkills] = useState<SkillRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [form] = Form.useForm();

  useEffect(() => {
    loadSkills();
  }, []);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const data = await fetchJson<{ skills: SkillRecord[]; total: number }>(`${BASE}/skills?page_size=100`);
      setSkills(data.skills || []);
    } catch {
      message.error('Failed to load skills');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: { name: string; skill_type: string; description: string; category: string }) => {
    try {
      const qs = new URLSearchParams({
        name: values.name,
        skill_type: values.skill_type,
        description: values.description || '',
        category: values.category || 'general',
      });
      await fetchJson(`${BASE}/register`, {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(qs)),
      });
      message.success('Skill registered');
      setRegisterOpen(false);
      form.resetFields();
      loadSkills();
    } catch {
      message.error('Failed to register skill');
    }
  };

  const handleUnregister = async (skillId: string) => {
    try {
      await fetchJson(`${BASE}/${skillId}`, { method: 'DELETE' });
      message.success('Skill archived');
      loadSkills();
    } catch {
      message.error('Failed to unregister skill');
    }
  };

  const handleDiscover = async () => {
    if (!searchQuery.trim()) {
      loadSkills();
      return;
    }
    setLoading(true);
    try {
      const data = await fetchJson<{ skills: SkillRecord[]; count: number }>(`${BASE}/discover?q=${encodeURIComponent(searchQuery)}`);
      setSkills(data.skills || []);
    } catch {
      message.error('Discovery failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLifecycleTransition = async (skillId: string, targetStatus: string) => {
    try {
      await fetchJson(`${BASE}/${skillId}/lifecycle?target_status=${targetStatus}`, {
        method: 'PUT',
      });
      message.success(`Transitioned to ${targetStatus}`);
      loadSkills();
    } catch {
      message.error('Lifecycle transition failed');
    }
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Type', dataIndex: 'type', key: 'type' },
    { title: 'Category', dataIndex: 'category', key: 'category' },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>,
    },
    { title: 'Version', dataIndex: 'current_version', key: 'version' },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: SkillRecord) => (
        <Space>
          {(LIFECYCLE_OPTIONS[record.status] || []).map((target) => (
            <Button
              key={target}
              size="small"
              icon={<SwapOutlined />}
              onClick={() => handleLifecycleTransition(record.skill_id, target)}
            >
              {target}
            </Button>
          ))}
          {record.status !== 'archived' && (
            <Popconfirm description="Archive this skill?" onConfirm={() => handleUnregister(record.skill_id)}>
              <Button size="small" danger icon={<DeleteOutlined />}>
                Archive
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="Skill Manager"
        extra={
          <Space>
            <Input.Search
              placeholder="Search skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onSearch={handleDiscover}
              style={{ width: 250 }}
            />
            <Button icon={<SearchOutlined />} onClick={handleDiscover}>
              Discover
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setRegisterOpen(true)}>
              Register
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={skills}
          columns={columns}
          rowKey="skill_id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 15 }}
        />
      </Card>

      <Modal
        title="Register Skill"
        open={registerOpen}
        onCancel={() => setRegisterOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="skill_type" label="Type" rules={[{ required: true }]}>
            <Select options={[
              { value: 'action', label: 'Action' },
              { value: 'query', label: 'Query' },
              { value: 'transform', label: 'Transform' },
              { value: 'integration', label: 'Integration' },
            ]} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="category" label="Category">
            <Input placeholder="general" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
