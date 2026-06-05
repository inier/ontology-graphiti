import { useState, useEffect } from 'react';
import { Table, Button, Modal, Input, Select, Card, Tag, Space, Typography, message, Popconfirm, Form } from 'antd';
import { PlusOutlined, DeleteOutlined, SearchOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';

const { Text } = Typography;

interface ToolRecord {
  tool_id?: string;
  name: string;
  description: string;
  tool_type: string;
  category: string;
  version: string;
  danger_level: string;
  capabilities: string[];
  semantic_tags: string[];
  status?: string;
}

const CATEGORY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'general', label: 'General' },
  { value: 'data', label: 'Data' },
  { value: 'integration', label: 'Integration' },
  { value: 'action', label: 'Action' },
  { value: 'query', label: 'Query' },
  { value: 'transform', label: 'Transform' },
];

const DANGER_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
};

export default function ToolRegistry() {
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [invokeOpen, setInvokeOpen] = useState(false);
  const [invokeTool, setInvokeTool] = useState<ToolRecord | null>(null);
  const [discoverQuery, setDiscoverQuery] = useState('');
  const [invokeParams, setInvokeParams] = useState('');
  const [form] = Form.useForm();

  useEffect(() => {
    loadTools();
  }, []);

  const loadTools = async (category?: string) => {
    setLoading(true);
    try {
      const qs = category ? `?category=${encodeURIComponent(category)}` : '';
      const data = await apiClient.get<{ tools: ToolRecord[]; count: number }>(`/api/tools${qs}`);
      setTools(data.tools || []);
    } catch {
      message.error('Failed to load tools');
      setTools([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryChange = (value: string) => {
    setCategoryFilter(value);
    loadTools(value || undefined);
  };

  const handleRegister = async (values: ToolRecord) => {
    try {
      await apiClient.post('/api/tools/register', values);
      message.success('Tool registered');
      setRegisterOpen(false);
      form.resetFields();
      loadTools(categoryFilter || undefined);
    } catch (e) {
      message.error(`Register failed: ${(e as Error).message}`);
    }
  };

  const handleUnregister = async (toolId: string) => {
    try {
      await apiClient.delete(`/api/tools/${toolId}`);
      message.success('Tool unregistered');
      loadTools(categoryFilter || undefined);
    } catch (e) {
      message.error(`Unregister failed: ${(e as Error).message}`);
    }
  };

  const handleDiscover = async () => {
    if (!discoverQuery.trim()) {
      loadTools(categoryFilter || undefined);
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.post<{ tools: ToolRecord[]; count: number }>('/api/tools/discover', {
        query: discoverQuery,
        top_k: 10,
      });
      setTools(data.tools || []);
    } catch (e) {
      message.error(`Discovery failed: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleInvoke = async () => {
    if (!invokeTool) return;
    let params: Record<string, unknown> = {};
    if (invokeParams.trim()) {
      try {
        params = JSON.parse(invokeParams);
      } catch {
        message.error('Invalid JSON parameters');
        return;
      }
    }
    try {
      const result = await apiClient.post(`/api/tools/${invokeTool.tool_id || invokeTool.name}/invoke`, {
        params,
      });
      message.success('Tool invoked successfully');
      Modal.info({
        title: 'Invocation Result',
        content: <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12 }}>{JSON.stringify(result, null, 2)}</pre>,
        width: 600,
      });
      setInvokeOpen(false);
      setInvokeParams('');
      setInvokeTool(null);
    } catch (e) {
      message.error(`Invocation failed: ${(e as Error).message}`);
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
      dataIndex: 'tool_type',
      key: 'tool_type',
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: 'Danger',
      dataIndex: 'danger_level',
      key: 'danger_level',
      width: 80,
      render: (v: string) => <Tag color={DANGER_COLORS[v] || 'default'}>{v || 'low'}</Tag>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: ToolRecord) => (
        <Space size="small">
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => {
              setInvokeTool(record);
              setInvokeOpen(true);
            }}
          >
            Invoke
          </Button>
          <Popconfirm title="Unregister this tool?" onConfirm={() => handleUnregister(record.tool_id || record.name)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              Remove
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="Tool Registry"
        extra={
          <Space>
            <Select
              value={categoryFilter}
              onChange={handleCategoryChange}
              options={CATEGORY_OPTIONS}
              style={{ width: 140 }}
            />
            <Input.Search
              placeholder="Semantic discovery..."
              value={discoverQuery}
              onChange={(e) => setDiscoverQuery(e.target.value)}
              onSearch={handleDiscover}
              style={{ width: 220 }}
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
          dataSource={tools}
          columns={columns}
          rowKey={(record) => record.tool_id || record.name}
          loading={loading}
          size="small"
          pagination={{ pageSize: 15 }}
        />
      </Card>

      <Modal
        title="Register Tool"
        open={registerOpen}
        onCancel={() => { setRegisterOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="tool_type" label="Type" rules={[{ required: true }]}>
            <Select options={[
              { value: 'function', label: 'Function' },
              { value: 'api', label: 'API' },
              { value: 'script', label: 'Script' },
            ]} />
          </Form.Item>
          <Form.Item name="category" label="Category">
            <Select options={CATEGORY_OPTIONS.filter((o) => o.value)} />
          </Form.Item>
          <Form.Item name="danger_level" label="Danger Level">
            <Select options={[
              { value: 'low', label: 'Low' },
              { value: 'medium', label: 'Medium' },
              { value: 'high', label: 'High' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Invoke: ${invokeTool?.name || ''}`}
        open={invokeOpen}
        onCancel={() => { setInvokeOpen(false); setInvokeParams(''); setInvokeTool(null); }}
        onOk={handleInvoke}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {invokeTool?.description && <Text type="secondary">{invokeTool.description}</Text>}
          <Input.TextArea
            placeholder='{"key": "value"}'
            value={invokeParams}
            onChange={(e) => setInvokeParams(e.target.value)}
            rows={6}
            style={{ fontFamily: 'monospace' }}
          />
        </Space>
      </Modal>
    </div>
  );
}
