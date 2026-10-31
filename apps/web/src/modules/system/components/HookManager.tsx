/**
 * 钩子管理：/api/hooks 的管理界面。
 *
 * 契约（后端 odap/biz/integration/hook_system/api/routes.py）：
 *   GET    /api/hooks?hook_type=&page=&page_size=
 *          → {hooks: [{hook_id, name, hook_type, status, enabled}], page, page_size, total}
 *   POST   /api/hooks/register  → RegisterHookRequest{name, hook_type, script, description?, language?}
 *   DELETE /api/hooks/{hook_id} → 真正删除（本组件挂载时一并修复了后端 no-op 删除）
 *   POST   /api/hooks/{hook_id}/enable | /disable → {status, hook_id, enabled, hook_status}
 *
 * 三个必须对齐后端而非"看起来合理"的点：
 *   1. hook_type 只能是 HookType 枚举值，后端严格校验并 400；此前组件用的是
 *      event/data/validation/... 一组后端根本不存在的值。
 *   2. 后端没有 phase / priority 字段（既不在 RegisterHookRequest 里，也不在列表返回里），
 *      因此不做这两列——否则表格永远渲染 undefined。
 *   3. 状态枚举是 active/inactive/error；开关读的是服务端派生的 enabled，
 *      不能用 `checked={v !== false}` 猜（undefined 会被当成已启用）。
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import { Switch, Button, Modal, Select, Card, Tag, Space, message, Popconfirm, Form, Input } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ActionType } from '@ant-design/pro-components';
import type { ColumnsType } from 'antd/es/table';

interface HookRecord {
  hook_id: string;
  name: string;
  hook_type: string;
  status?: string;
  enabled?: boolean;
}

/** 与后端 HookType 枚举逐项对齐 */
const HOOK_TYPE_VALUES = [
  'pre_execute',
  'post_execute',
  'on_error',
  'on_timeout',
  'pre_commit',
  'post_commit',
] as const;

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  inactive: 'default',
  error: 'red',
};

export default function HookManager() {
  const { t } = useI18n('system');
  const actionRef = useRef<ActionType>(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [form] = Form.useForm();

  const typeLabel = useCallback(
    (value: string) => {
      switch (value) {
        case 'pre_execute':
          return t('执行前');
        case 'post_execute':
          return t('执行后');
        case 'on_error':
          return t('出错时');
        case 'on_timeout':
          return t('超时时');
        case 'pre_commit':
          return t('提交前');
        case 'post_commit':
          return t('提交后');
        default:
          return value;
      }
    },
    [t],
  );

  const statusLabel = useCallback(
    (value?: string) => {
      switch (value) {
        case 'active':
          return t('已启用');
        case 'inactive':
          return t('已禁用');
        case 'error':
          return t('异常');
        default:
          return value || '-';
      }
    },
    [t],
  );

  const HOOK_TYPE_OPTIONS = useMemo(
    () => HOOK_TYPE_VALUES.map((v) => ({ value: v, label: typeLabel(v) })),
    [typeLabel],
  );

  const fetchHooks = useCallback(async (): Promise<HookRecord[]> => {
    try {
      const params = new URLSearchParams({ page_size: '100' });
      if (typeFilter) params.set('hook_type', typeFilter);
      const data = await apiClient.get<{ hooks: HookRecord[]; total: number }>(`/api/hooks?${params.toString()}`);
      return data.hooks ?? [];
    } catch (e) {
      message.error(`${t('获取钩子列表失败')}: ${(e as Error).message}`);
      throw e;
    }
  }, [typeFilter, t]);

  const request = useMemo(() => wrapRequest(fetchHooks), [fetchHooks]);

  const handleTypeFilter = (value: string) => {
    setTypeFilter(value);
    setTimeout(() => actionRef.current?.reload(), 0);
  };

  const handleRegister = async (values: {
    name: string;
    hook_type: string;
    script: string;
    description?: string;
    language?: string;
  }) => {
    try {
      await apiClient.post('/api/hooks/register', values);
      message.success(t('钩子已注册'));
      setRegisterOpen(false);
      form.resetFields();
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('注册失败')}: ${(e as Error).message}`);
    }
  };

  const handleUnregister = async (hookId: string) => {
    try {
      await apiClient.delete(`/api/hooks/${encodeURIComponent(hookId)}`);
      message.success(t('钩子已注销'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('注销失败')}: ${(e as Error).message}`);
    }
  };

  const handleToggle = async (record: HookRecord, enabled: boolean) => {
    try {
      const endpoint = enabled ? 'enable' : 'disable';
      await apiClient.post(`/api/hooks/${encodeURIComponent(record.hook_id)}/${endpoint}`);
      message.success(enabled ? t('钩子已启用') : t('钩子已禁用'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('切换失败')}: ${(e as Error).message}`);
    }
  };

  const columns: ColumnsType<HookRecord> = [
    { title: t('名称'), dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: t('类型'),
      dataIndex: 'hook_type',
      key: 'hook_type',
      width: 120,
      render: (v: string) => <Tag color="blue">{typeLabel(v)}</Tag>,
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v?: string) => <Tag color={STATUS_COLORS[v || ''] || 'default'}>{statusLabel(v)}</Tag>,
    },
    {
      title: t('启用'),
      dataIndex: 'enabled',
      key: 'enabled',
      width: 90,
      render: (v: boolean | undefined, record) => (
        <Switch
          checked={v === true}
          size="small"
          aria-label={`${t('启用')} ${record.name}`}
          onChange={(checked) => void handleToggle(record, checked)}
        />
      ),
    },
    {
      title: t('操作'),
      key: 'actions',
      width: 100,
      render: (_: unknown, record) => (
        <Popconfirm title={t('确定注销此钩子？')} onConfirm={() => void handleUnregister(record.hook_id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>
            {t('移除')}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div data-testid="hook-manager">
      <Card
        title={t('钩子管理')}
        extra={
          <Space wrap>
            <Select
              value={typeFilter}
              onChange={handleTypeFilter}
              placeholder={t('按类型筛选')}
              style={{ width: 160 }}
              allowClear
              aria-label={t('按类型筛选')}
              options={[{ value: '', label: t('全部') }, ...HOOK_TYPE_OPTIONS]}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setRegisterOpen(true)}>
              {t('注册钩子')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          request={request}
          actionRef={actionRef}
          columns={columns}
          rowKey="hook_id"
          size="small"
          pagination={{ pageSize: 15 }}
        />
      </Card>

      <Modal
        title={t('注册钩子')}
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
          <Form.Item name="hook_type" label={t('类型')} rules={[{ required: true, message: t('请选择类型') }]}>
            <Select aria-label={t('类型')} options={HOOK_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="script" label={t('脚本')} rules={[{ required: true, message: t('请填写脚本') }]}>
            <Input.TextArea rows={4} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="language" label={t('语言')} initialValue="python">
            <Select
              options={[
                { value: 'python', label: 'Python' },
                { value: 'javascript', label: 'JavaScript' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label={t('描述')}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
