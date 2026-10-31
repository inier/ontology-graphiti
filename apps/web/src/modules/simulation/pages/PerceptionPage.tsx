/**
 * PerceptionPage — 感知系统管理页面（Iter 4 / P3）
 *
 * 顶部状态卡片 + 中部手动输入区域 + 底部观察者列表表格。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Table, Tag, Button, Space, Statistic, Select,
  Input, message, Empty, Spin,
} from 'antd';
import type { TableColumnsType } from 'antd';
import {
  ReloadOutlined, SendOutlined, EyeOutlined, InboxOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ── Types ──────────────────────────────────────────────────────────── */

interface PerceptionStatus {
  queue_length?: number;
  processed_count?: number;
  active_observers?: number;
}

interface Observer {
  name: string;
  enabled: boolean;
  type?: string;
}

type TFunc = (key: string) => string;

/* ── Constants ──────────────────────────────────────────────────────── */

const SOURCE_TYPE_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: 'JSON', value: 'json' },
  { label: '事件', value: 'event' },
  { label: '传感器', value: 'sensor' },
];

/* ── Helpers ────────────────────────────────────────────────────────── */

function extractList<T>(res: unknown, ...keys: string[]): T[] {
  let data: unknown = res;
  if (data && typeof data === 'object' && 'status' in data && 'data' in data) {
    data = (data as { data: unknown }).data;
  }
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    for (const k of [...keys, 'items', 'data']) {
      if (Array.isArray(obj[k])) return obj[k] as T[];
    }
  }
  return [];
}

function extractData<T>(res: unknown): T {
  if (res && typeof res === 'object' && 'status' in res && 'data' in res) {
    return (res as { data: T }).data;
  }
  return res as T;
}

/* ── Column Builder ─────────────────────────────────────────────────── */

interface ObserverHandlers {
  onToggle: (name: string, enabled: boolean) => void;
  togglingName: string | null;
}

function buildColumns(h: ObserverHandlers, t: TFunc): TableColumnsType<Observer> {
  return [
    { title: t('名称'), dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: t('状态'), dataIndex: 'enabled', key: 'enabled', width: 100,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? t('启用') : t('禁用')}</Tag>,
    },
    {
      title: t('类型'), dataIndex: 'type', key: 'type', width: 120,
      render: (v: string) => v ? <Tag>{v}</Tag> : '-',
    },
    {
      title: t('操作'), key: 'action', width: 100,
      render: (_: unknown, r: Observer) => (
        <Button
          type="link"
          size="small"
          loading={h.togglingName === r.name}
          onClick={() => h.onToggle(r.name, !r.enabled)}
        >
          {r.enabled ? t('禁用') : t('启用')}
        </Button>
      ),
    },
  ];
}

/* ── Custom Hook ────────────────────────────────────────────────────── */

function usePerception(t: TFunc) {
  const [status, setStatus] = useState<PerceptionStatus | null>(null);
  const [observers, setObservers] = useState<Observer[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [togglingName, setTogglingName] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [sourceType, setSourceType] = useState('text');

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/perception/status');
      setStatus(extractData<PerceptionStatus>(res));
    } catch (e) {
      console.error('Failed to fetch perception status:', e);
    }
  }, []);

  const fetchObservers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/api/perception/observers');
      setObservers(extractList<Observer>(res, 'observers'));
    } catch (e) {
      console.error('Failed to fetch observers:', e);
      message.error(`${t('加载失败')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
        void (async () => {
      fetchStatus();
    })();
        void (async () => {
      fetchObservers();
    })();
  }, [fetchStatus, fetchObservers]);

  const handleToggle = useCallback(async (name: string, enabled: boolean) => {
    setTogglingName(name);
    try {
      await apiClient.post(`/api/perception/observers/${name}/toggle`, { enabled });
      message.success(enabled ? t('已启用') : t('已禁用'));
      await Promise.all([fetchStatus(), fetchObservers()]);
    } catch (e) {
      console.error('Toggle observer failed:', e);
      message.error(`${t('操作失败')}: ${(e as Error).message}`);
    } finally {
      setTogglingName(null);
    }
  }, [fetchStatus, fetchObservers, t]);

  const handleSubmit = useCallback(async () => {
    if (!inputText.trim()) {
      message.warning(t('请输入内容'));
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post('/api/perception/ingest/manual', {
        content: inputText,
        source_type: sourceType,
        metadata: {},
      });
      message.success(t('提交成功'));
      setInputText('');
      await fetchStatus();
    } catch (e) {
      console.error('Manual ingest failed:', e);
      message.error(`${t('提交失败')}: ${(e as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  }, [inputText, sourceType, fetchStatus, t]);

  return {
    status, observers, loading, submitting, togglingName,
    inputText, setInputText, sourceType, setSourceType,
    fetchObservers, handleToggle, handleSubmit,
  };
}

/* ── Status Cards Renderer ──────────────────────────────────────────── */

function StatusCards(props: { status: PerceptionStatus | null; t: TFunc }) {
  const { status, t } = props;
  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={8}>
        <Card><Statistic title={t('队列长度')} value={status?.queue_length ?? 0} prefix={<InboxOutlined />} /></Card>
      </Col>
      <Col span={8}>
        <Card><Statistic title={t('已处理数')} value={status?.processed_count ?? 0} prefix={<EyeOutlined />} /></Card>
      </Col>
      <Col span={8}>
        <Card><Statistic title={t('活跃观察者')} value={status?.active_observers ?? 0} styles={{ content: { color: '#1677ff' } }} /></Card>
      </Col>
    </Row>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */

export function PerceptionPage() {
  const { t } = useI18n('simulation');
  const sourceTypeOptions = useMemo(
    () => SOURCE_TYPE_OPTIONS.map((opt) => ({ ...opt, label: t(opt.label) })),
    [t],  
  );
  const vm = usePerception(t);
  const columns = buildColumns(
    { onToggle: vm.handleToggle, togglingName: vm.togglingName },
    t,
  );

  return (
    <div style={{ padding: 16 }}>
      <StatusCards status={vm.status} t={t} />

      <Card title={t('手动输入')} size="small" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%', marginBottom: 8 }}>
          <Select
            value={vm.sourceType}
            onChange={vm.setSourceType}
            options={sourceTypeOptions}
            style={{ width: 140 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={vm.submitting}
            onClick={vm.handleSubmit}
          >
            {t('提交')}
          </Button>
        </Space.Compact>
        <Input.TextArea
          value={vm.inputText}
          onChange={(e) => vm.setInputText(e.target.value)}
          placeholder={t('请输入要手动注入的感知内容…')}
          rows={4}
        />
      </Card>

      <Card
        title={t('观察者列表')}
        extra={<Button icon={<ReloadOutlined />} onClick={vm.fetchObservers} loading={vm.loading}>{t('刷新')}</Button>}
      >
        <Spin spinning={vm.loading}>
          <Table<Observer>
            rowKey="name"
            columns={columns}
            dataSource={vm.observers}
            size="small"
            pagination={false}
            locale={{ emptyText: <Empty description={t('暂无观察者')} /> }}
          />
        </Spin>
      </Card>
    </div>
  );
}
