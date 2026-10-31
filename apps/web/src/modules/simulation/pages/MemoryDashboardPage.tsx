/**
 * MemoryDashboardPage — 本体记忆看板页面（Iter 4 / P3）
 *
 * 顶部统计卡片 + 中部操作按钮（执行衰减/遗忘）+ 底部记忆列表表格。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Card, Row, Col, Table, Tag, Button, Space, Statistic, message, Empty, Spin, Popconfirm,
} from 'antd';
import type { TableColumnsType } from 'antd';
import {
  ReloadOutlined, ThunderboltOutlined, RestOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ── Types ──────────────────────────────────────────────────────────── */

interface MemoryStats {
  total?: number;
  active?: number;
  decayed?: number;
  archived?: number;
}

interface MemoryItem {
  memory_id: string;
  memory_type: string;
  status: string;
  summary?: string;
  importance?: number;
  keywords?: string[];
  source_scenario_id?: string;
  created_at: string;
}

type TFunc = (key: string) => string;

/* ── Constants ──────────────────────────────────────────────────────── */

const MEMORY_TYPE_COLORS: Record<string, string> = {
  episodic: 'blue',
  semantic: 'green',
  procedural: 'orange',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  decayed: 'orange',
  archived: 'default',
  consolidated: 'cyan',
};

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

function buildColumns(t: TFunc): TableColumnsType<MemoryItem> {
  return [
    {
      title: t('类型'), dataIndex: 'memory_type', key: 'memory_type', width: 100,
      render: (v: string) => <Tag color={MEMORY_TYPE_COLORS[v] || 'default'}>{v || '-'}</Tag>,
    },
    {
      title: t('状态'), dataIndex: 'status', key: 'status', width: 110,
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v || '-'}</Tag>,
    },
    {
      title: t('摘要'), dataIndex: 'summary', key: 'summary', ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: t('重要性'), dataIndex: 'importance', key: 'importance', width: 80, align: 'center',
      render: (v: number) => v ?? '-',
    },
    {
      title: t('关键词'), dataIndex: 'keywords', key: 'keywords', width: 200,
      render: (v: string[]) => (v?.length ? <Space wrap size={[4, 4]}>{v.map((k, i) => <Tag key={i}>{k}</Tag>)}</Space> : '-'),
    },
    {
      title: t('场景'), dataIndex: 'source_scenario_id', key: 'source_scenario_id', width: 140, ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: t('创建时间'), dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
  ];
}

/* ── Custom Hook ────────────────────────────────────────────────────── */

function useMemoryDashboard(t: TFunc) {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [operating, setOperating] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/ontology-memory/statistics');
      setStats(extractData<MemoryStats>(res));
    } catch (e) {
      console.error('Failed to fetch memory statistics:', e);
    }
  }, []);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/api/ontology-memory/memories?page=1&page_size=100');
      setMemories(extractList<MemoryItem>(res, 'memories'));
    } catch (e) {
      console.error('Failed to fetch memories:', e);
      message.error(`${t('加载失败')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
        void (async () => {
      fetchStats();
    })();
        void (async () => {
      fetchMemories();
    })();
  }, [fetchStats, fetchMemories]);

  const handleDecay = useCallback(async () => {
    setOperating(true);
    try {
      await apiClient.post('/api/ontology-memory/memories/decay');
      message.success(t('衰减更新已完成'));
      await Promise.all([fetchStats(), fetchMemories()]);
    } catch (e) {
      console.error('Decay operation failed:', e);
      message.error(`${t('操作失败')}: ${(e as Error).message}`);
    } finally {
      setOperating(false);
    }
  }, [fetchStats, fetchMemories, t]);

  const handleForget = useCallback(async () => {
    setOperating(true);
    try {
      await apiClient.post('/api/ontology-memory/memories/forget');
      message.success(t('遗忘操作已完成'));
      await Promise.all([fetchStats(), fetchMemories()]);
    } catch (e) {
      console.error('Forget operation failed:', e);
      message.error(`${t('操作失败')}: ${(e as Error).message}`);
    } finally {
      setOperating(false);
    }
  }, [fetchStats, fetchMemories, t]);

  return {
    stats, memories, loading, operating, fetchMemories, handleDecay, handleForget,
  };
}

/* ── Stats Cards Renderer ───────────────────────────────────────────── */

function StatsCards(props: { stats: MemoryStats | null; t: TFunc }) {
  const { stats, t } = props;
  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={6}>
        <Card><Statistic title={t('总记忆数')} value={stats?.total ?? 0} prefix={<DatabaseOutlined />} /></Card>
      </Col>
      <Col span={6}>
        <Card><Statistic title={t('活跃记忆')} value={stats?.active ?? 0} styles={{ content: { color: '#3f8600' } }} /></Card>
      </Col>
      <Col span={6}>
        <Card><Statistic title={t('衰减记忆')} value={stats?.decayed ?? 0} styles={{ content: { color: '#fa8c16' } }} /></Card>
      </Col>
      <Col span={6}>
        <Card><Statistic title={t('已归档')} value={stats?.archived ?? 0} /></Card>
      </Col>
    </Row>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */

export function MemoryDashboardPage() {
  const { t } = useI18n('simulation');
  const vm = useMemoryDashboard(t);
  const columns = buildColumns(t);

  return (
    <div style={{ padding: 16 }}>
      <StatsCards stats={vm.stats} t={t} />

      <Card
        title={t('记忆管理')}
        extra={
          <Space>
            <Popconfirm title={t('确认执行衰减更新？')} onConfirm={vm.handleDecay}>
              <Button icon={<ThunderboltOutlined />} loading={vm.operating}>{t('执行衰减')}</Button>
            </Popconfirm>
            <Popconfirm title={t('确认执行遗忘操作？')} onConfirm={vm.handleForget}>
              <Button danger icon={<RestOutlined />} loading={vm.operating}>{t('执行遗忘')}</Button>
            </Popconfirm>
            <Button icon={<ReloadOutlined />} onClick={vm.fetchMemories} loading={vm.loading}>{t('刷新')}</Button>
          </Space>
        }
      >
        <Spin spinning={vm.loading}>
          <Table<MemoryItem>
            rowKey="memory_id"
            columns={columns}
            dataSource={vm.memories}
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true }}
            locale={{ emptyText: <Empty description={t('暂无记忆')} /> }}
          />
        </Spin>
      </Card>
    </div>
  );
}
