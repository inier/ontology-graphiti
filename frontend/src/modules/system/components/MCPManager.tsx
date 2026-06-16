import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Modal, Input, Card, Tag, Badge, Space, Typography, message, Popconfirm, Form } from 'antd';
import {
  PlusOutlined, DeleteOutlined,
  ThunderboltOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface MCPServer {
  server_id: string;
  name: string;
  url: string;
  status: 'connected' | 'disconnected' | 'error';
  tools_count: number;
  description: string;
  last_ping?: string;
}

interface MCPTool {
  tool_id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

const STATUS_BADGE: Record<string, 'success' | 'error' | 'default' | 'processing'> = {
  connected: 'success',
  disconnected: 'default',
  error: 'error',
};

function MCPManager() {
  const { t } = useI18n('system');
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [invokeOpen, setInvokeOpen] = useState(false);
  const [invokeTool, setInvokeTool] = useState<MCPTool | null>(null);
  const [invokeParams, setInvokeParams] = useState('');
  const [selectedServerTools, setSelectedServerTools] = useState<MCPTool[]>([]);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchServers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ servers: MCPServer[] }>('/api/mcp/servers');
      setServers(data.servers || []);
    } catch {
      setServers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  const handleRegister = async (values: Record<string, unknown>) => {
    try {
      await apiClient.post('/api/mcp/servers/register', values);
      message.success(t('mcp.registered', 'MCP server registered'));
      setRegisterOpen(false);
      form.resetFields();
      fetchServers();
    } catch (e) {
      message.error(`${t('mcp.registerFailed', 'Registration failed')}: ${(e as Error).message}`);
    }
  };

  const handleUnregister = async (serverId: string) => {
    try {
      await apiClient.delete(`/api/mcp/servers/${serverId}`);
      message.success(t('mcp.unregistered', 'MCP server unregistered'));
      fetchServers();
    } catch (e) {
      message.error(`${t('mcp.unregisterFailed', 'Unregister failed')}: ${(e as Error).message}`);
    }
  };

  const handleListTools = async (serverId: string) => {
    try {
      const data = await apiClient.get<{ tools: MCPTool[] }>(`/api/mcp/servers/${serverId}/tools`);
      setSelectedServerTools(data.tools || []);
      setToolsOpen(true);
    } catch (e) {
      message.error(`${t('mcp.toolsFailed', 'Failed to list tools')}: ${(e as Error).message}`);
    }
  };

  const handleInvokeTool = async () => {
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
      const result = await apiClient.post(`/api/mcp/tools/${invokeTool.tool_id}/invoke`, { params });
      message.success(t('mcp.invoked', 'Tool invoked successfully'));
      Modal.info({
        title: t('mcp.invokeResult', 'Invocation Result'),
        content: <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12 }}>{JSON.stringify(result, null, 2)}</pre>,
        width: 600,
      });
      setInvokeOpen(false);
      setInvokeParams('');
      setInvokeTool(null);
    } catch (e) {
      message.error(`${t('mcp.invokeFailed', 'Invocation failed')}: ${(e as Error).message}`);
    }
  };

  const columns = [
    {
      title: t('mcp.name', 'Name'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t('mcp.url', 'URL'),
      dataIndex: 'url',
      key: 'url',
      ellipsis: true,
      render: (url: string) => <Text copyable style={{ fontSize: 12 }}>{url}</Text>,
    },
    {
      title: t('mcp.status', 'Status'),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => (
        <Badge status={STATUS_BADGE[status] || 'default'} text={
          <Tag color={status === 'connected' ? 'green' : status === 'error' ? 'red' : 'default'}>
            {status}
          </Tag>
        } />
      ),
    },
    {
      title: t('mcp.tools', 'Tools'),
      dataIndex: 'tools_count',
      key: 'tools_count',
      width: 80,
      render: (count: number) => <Badge count={count} showZero color="blue" />,
    },
    {
      title: t('mcp.lastPing', 'Last Ping'),
      dataIndex: 'last_ping',
      key: 'last_ping',
      width: 140,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: t('mcp.actions', 'Actions'),
      key: 'actions',
      width: 200,
      render: (_: unknown, record: MCPServer) => (
        <Space size="small">
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => handleListTools(record.server_id)}
          >
            {t('mcp.tools', 'Tools')}
          </Button>
          <Popconfirm
            title={t('mcp.unregisterConfirm', 'Unregister this server?')}
            onConfirm={() => handleUnregister(record.server_id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('mcp.remove', 'Remove')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const toolColumns = [
    {
      title: t('mcp.toolName', 'Tool Name'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t('mcp.toolDesc', 'Description'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: t('mcp.toolActions', 'Actions'),
      key: 'actions',
      width: 100,
      render: (_: unknown, record: MCPTool) => (
        <Button
          size="small"
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={() => {
            setInvokeTool(record);
            setInvokeParams('');
            setInvokeOpen(true);
          }}
        >
          {t('mcp.invoke', 'Invoke')}
        </Button>
      ),
    },
  ];

  return (
    <Card
      title={t('mcp.title', 'MCP Server Manager')}
      extra={
        <Space>
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchServers}>
            {t('common.refresh', 'Refresh')}
          </Button>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setRegisterOpen(true)}>
            {t('mcp.register', 'Register Server')}
          </Button>
        </Space>
      }
    >
      <Table
        dataSource={servers}
        columns={columns}
        rowKey="server_id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={t('mcp.registerTitle', 'Register MCP Server')}
        open={registerOpen}
        onCancel={() => { setRegisterOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="name" label={t('mcp.name', 'Name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label={t('mcp.url', 'URL')} rules={[{ required: true }]}>
            <Input placeholder="http://localhost:8080/mcp" />
          </Form.Item>
          <Form.Item name="description" label={t('mcp.description', 'Description')}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('mcp.toolsTitle', 'Server Tools')}
        open={toolsOpen}
        onCancel={() => { setToolsOpen(false); setSelectedServerTools([]); }}
        footer={null}
        width={640}
      >
        <Table
          dataSource={selectedServerTools}
          columns={toolColumns}
          rowKey="tool_id"
          size="small"
          pagination={false}
        />
      </Modal>

      <Modal
        title={`${t('mcp.invoke', 'Invoke')}: ${invokeTool?.name || ''}`}
        open={invokeOpen}
        onCancel={() => { setInvokeOpen(false); setInvokeParams(''); setInvokeTool(null); }}
        onOk={handleInvokeTool}
      >
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          {invokeTool?.description && <Text type="secondary">{invokeTool.description}</Text>}
          <Input.TextArea
            placeholder='{"key": "value"}'
            value={invokeParams}
            onChange={e => setInvokeParams(e.target.value)}
            rows={6}
            style={{ fontFamily: 'monospace' }}
          />
        </Space>
      </Modal>
    </Card>
  );
}

export default MCPManager;
