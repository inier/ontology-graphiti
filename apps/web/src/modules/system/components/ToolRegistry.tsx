/**
 * 工具注册表：/api/tools 的完整管理界面。
 *
 * 契约（后端 odap/biz/platform/tool_registry/api/routes.py）：
 *   GET    /api/tools?category=      → {status, tools[], count}
 *   POST   /api/tools/register       → ToolRegisterRequest
 *   DELETE /api/tools/{tool_id}      → {status, tool_id}
 *   POST   /api/tools/discover       → {status, tools[], count}（语义检索）
 *   POST   /api/tools/{tool_id}/invoke → {status, tool_id, result, error}
 *
 * 注意：列表接口只返回工具的名称/类型/分类/危险等级等元数据；
 * 调用结果必须走 invoke，不要把"调用成功"当成"列表已刷新"。
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import { Button, Modal, Input, Select, Card, Tag, Space, Typography, message, Popconfirm, Form, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, SearchOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ActionType } from '@ant-design/pro-components';
import type { ColumnsType } from 'antd/es/table';

const { Text } = Typography;

interface ToolRecord {
  tool_id?: string;
  name: string;
  description?: string;
  tool_type?: string;
  category?: string;
  version?: string;
  danger_level?: string;
  capabilities?: string[];
  semantic_tags?: string[];
  status?: string;
}

/** 后端 ToolInvokeRequest 的响应形状 */
interface InvokeResponse {
  status?: string;
  tool_id?: string;
  result?: unknown;
  error?: string | null;
}

const DANGER_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
};

const TOOL_TYPE_OPTIONS = [
  { value: 'function', label: 'function' },
  { value: 'api', label: 'api' },
  { value: 'script', label: 'script' },
];

export default function ToolRegistry() {
  const { t } = useI18n('system');
  const actionRef = useRef<ActionType>(null);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [invokeOpen, setInvokeOpen] = useState(false);
  const [invokeTool, setInvokeTool] = useState<ToolRecord | null>(null);
  const [discoverQuery, setDiscoverQuery] = useState('');
  const [invokeParams, setInvokeParams] = useState('');
  /**
   * 语义发现结果。此前组件把它丢掉了——只弹一句"发现 N 个工具"然后 reload 全量列表，
   * 用户看不到任何发现结果。现在用 state 持有并置为表格数据源。
   */
  const [discovered, setDiscovered] = useState<ToolRecord[] | null>(null);
  const [form] = Form.useForm();

  const CATEGORY_OPTIONS = useMemo(
    () => [
      { value: '', label: t('全部') },
      { value: 'general', label: t('通用') },
      { value: 'data', label: t('数据') },
      { value: 'integration', label: t('集成') },
      { value: 'action', label: t('动作') },
      { value: 'query', label: t('查询') },
      { value: 'transform', label: t('转换') },
    ],
    [t],
  );

  const DANGER_OPTIONS = useMemo(
    () => [
      { value: 'low', label: t('低') },
      { value: 'medium', label: t('中') },
      { value: 'high', label: t('高') },
    ],
    [t],
  );

  const fetchTools = useCallback(async (): Promise<ToolRecord[]> => {
    try {
      const qs = categoryFilter ? `?category=${encodeURIComponent(categoryFilter)}` : '';
      const data = await apiClient.get<{ tools: ToolRecord[]; count: number }>(`/api/tools${qs}`);
      return data.tools ?? [];
    } catch (e) {
      // wrapRequest 会吞掉异常，这里先把原因暴露给用户，再让它继续降级为空表
      message.error(`${t('获取工具列表失败')}: ${(e as Error).message}`);
      throw e;
    }
  }, [categoryFilter, t]);

  const request = useMemo(
    () => wrapRequest(async () => discovered ?? fetchTools()),
    [discovered, fetchTools],
  );

  const handleCategoryChange = (value: string) => {
    setCategoryFilter(value);
    setDiscovered(null);
    setTimeout(() => actionRef.current?.reload(), 0);
  };

  const handleRegister = async (values: ToolRecord) => {
    try {
      await apiClient.post('/api/tools/register', values);
      message.success(t('工具已注册'));
      setRegisterOpen(false);
      form.resetFields();
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('注册失败')}: ${(e as Error).message}`);
    }
  };

  const handleUnregister = async (toolId: string) => {
    try {
      await apiClient.delete(`/api/tools/${encodeURIComponent(toolId)}`);
      message.success(t('工具已注销'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('注销失败')}: ${(e as Error).message}`);
    }
  };

  const handleDiscover = async () => {
    if (!discoverQuery.trim()) {
      setDiscovered(null);
      actionRef.current?.reload();
      return;
    }
    try {
      const data = await apiClient.post<{ tools: ToolRecord[]; count: number }>('/api/tools/discover', {
        query: discoverQuery,
        top_k: 10,
      });
      const tools = data.tools ?? [];
      setDiscovered(tools);
      actionRef.current?.reload();
      if (tools.length === 0) message.info(t('未找到匹配的工具'));
      else message.success(t('语义发现命中 {{n}} 个工具', { n: tools.length }));
    } catch (e) {
      message.error(`${t('语义发现失败')}: ${(e as Error).message}`);
    }
  };

  const handleInvoke = async () => {
    if (!invokeTool) return;
    let params: Record<string, unknown> = {};
    if (invokeParams.trim()) {
      try {
        params = JSON.parse(invokeParams) as Record<string, unknown>;
      } catch {
        message.error(t('参数必须是合法的 JSON'));
        return;
      }
    }
    const toolId = invokeTool.tool_id || invokeTool.name;
    try {
      const res = await apiClient.post<InvokeResponse>(
        `/api/tools/${encodeURIComponent(toolId)}/invoke`,
        { params },
      );
      if (res?.status === 'error') {
        message.error(`${t('调用失败')}: ${res.error ?? 'unknown'}`);
        return;
      }
      message.success(t('工具调用成功'));
      Modal.info({
        title: t('调用结果'),
        content: (
          <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12 }}>
            {JSON.stringify(res?.result ?? res, null, 2)}
          </pre>
        ),
        width: 600,
      });
      setInvokeOpen(false);
      setInvokeParams('');
      setInvokeTool(null);
    } catch (e) {
      message.error(`${t('调用失败')}: ${(e as Error).message}`);
    }
  };

  const columns: ColumnsType<ToolRecord> = [
    { title: t('名称'), dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: t('类型'),
      dataIndex: 'tool_type',
      key: 'tool_type',
      width: 100,
      render: (v?: string) => (v ? <Tag>{v}</Tag> : '-'),
    },
    {
      title: t('分类'),
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v?: string) => (v ? <Tag color="blue">{v}</Tag> : '-'),
    },
    {
      title: t('危险等级'),
      dataIndex: 'danger_level',
      key: 'danger_level',
      width: 100,
      render: (v?: string) => {
        const level = v || 'low';
        return <Tag color={DANGER_COLORS[level] || 'default'}>{t(level === 'low' ? '低' : level === 'medium' ? '中' : level === 'high' ? '高' : '低')}</Tag>;
      },
    },
    { title: t('描述'), dataIndex: 'description', key: 'description', ellipsis: true, render: (v?: string) => v || '-' },
    {
      title: t('操作'),
      key: 'actions',
      width: 180,
      render: (_: unknown, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => {
              setInvokeTool(record);
              setInvokeOpen(true);
            }}
          >
            {t('调用')}
          </Button>
          <Popconfirm
            title={t('确定注销此工具？')}
            onConfirm={() => void handleUnregister(record.tool_id || record.name)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('移除')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="tool-registry">
      {discovered !== null && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          title={t('当前显示语义发现结果（{{n}} 个）', { n: discovered.length })}
          action={
            <Button
              size="small"
              onClick={() => {
                setDiscovered(null);
                setDiscoverQuery('');
                actionRef.current?.reload();
              }}
            >
              {t('返回全部工具')}
            </Button>
          }
        />
      )}
      <Card
        title={t('工具注册表')}
        extra={
          <Space wrap>
            <Select
              value={categoryFilter}
              onChange={handleCategoryChange}
              options={CATEGORY_OPTIONS}
              style={{ width: 140 }}
              aria-label={t('分类')}
            />
            <Input.Search
              placeholder={t('语义检索工具...')}
              value={discoverQuery}
              onChange={(e) => setDiscoverQuery(e.target.value)}
              onSearch={() => void handleDiscover()}
              style={{ width: 220 }}
            />
            <Button icon={<SearchOutlined />} onClick={() => void handleDiscover()}>
              {t('语义发现')}
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setRegisterOpen(true)}>
              {t('注册工具')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          request={request}
          actionRef={actionRef}
          columns={columns}
          rowKey={(record) => record.tool_id || record.name}
          size="small"
          pagination={{ pageSize: 15 }}
        />
      </Card>

      <Modal
        title={t('注册工具')}
        open={registerOpen}
        onCancel={() => {
          setRegisterOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={handleRegister}>
          <Form.Item name="name" label={t('名称')} rules={[{ required: true, message: t('请填写名称') }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('描述')}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="tool_type" label={t('类型')} initialValue="function" rules={[{ required: true }]}>
            <Select options={TOOL_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="category" label={t('分类')} initialValue="general">
            <Select options={CATEGORY_OPTIONS.filter((o) => o.value)} />
          </Form.Item>
          <Form.Item name="danger_level" label={t('危险等级')} initialValue="low">
            <Select options={DANGER_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`${t('调用')}: ${invokeTool?.name || ''}`}
        open={invokeOpen}
        onCancel={() => {
          setInvokeOpen(false);
          setInvokeParams('');
          setInvokeTool(null);
        }}
        onOk={() => void handleInvoke()}
      >
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          {invokeTool?.description && <Text type="secondary">{invokeTool.description}</Text>}
          <Text type="secondary">{t('参数（JSON，可留空）')}</Text>
          <Input.TextArea
            aria-label={t('参数（JSON，可留空）')}
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
