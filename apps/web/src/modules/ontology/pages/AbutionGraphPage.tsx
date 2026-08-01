/**
 * AbutionGraphPage — Abution 跨维度图谱快照管理页面（Iter 4 / P3）
 *
 * 展示 Abution 图快照列表，支持查看详情、跨维度分析、删除操作。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Card, Table, Tag, Button, Space, message, Empty,
  Modal, Spin, Popconfirm, Descriptions,
} from 'antd';
import type { TableColumnsType } from 'antd';
import {
  ReloadOutlined, EyeOutlined, BarChartOutlined, DeleteOutlined, ApartmentOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ── Types ──────────────────────────────────────────────────────────── */

interface AbutionSnapshot {
  snapshot_id: string;
  name: string;
  temporal_node_count?: number;
  pattern_node_count?: number;
  force_node_count?: number;
  action_node_count?: number;
  created_at: string;
  description?: string;
  [key: string]: unknown;
}

interface ModalState {
  open: boolean;
  data: unknown;
  name: string;
}

type TFunc = (key: string) => string;

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

/* ── Column Builder ─────────────────────────────────────────────────── */

interface SnapshotHandlers {
  onViewDetail: (id: string, name: string) => void;
  onAnalyze: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

function buildColumns(h: SnapshotHandlers, t: TFunc): TableColumnsType<AbutionSnapshot> {
  return [
    { title: t('名称'), dataIndex: 'name', key: 'name', ellipsis: true },
    { title: t('时间节点'), dataIndex: 'temporal_node_count', key: 'temporal_node_count', width: 100, align: 'center', render: (v: number) => v ?? '-' },
    { title: t('模式节点'), dataIndex: 'pattern_node_count', key: 'pattern_node_count', width: 100, align: 'center', render: (v: number) => v ?? '-' },
    { title: t('力节点'), dataIndex: 'force_node_count', key: 'force_node_count', width: 100, align: 'center', render: (v: number) => v ?? '-' },
    { title: t('行动节点'), dataIndex: 'action_node_count', key: 'action_node_count', width: 100, align: 'center', render: (v: number) => v ?? '-' },
    {
      title: t('创建时间'), dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: t('操作'), key: 'action', width: 220,
      render: (_: unknown, r: AbutionSnapshot) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => h.onViewDetail(r.snapshot_id, r.name)}>
            {t('详情')}
          </Button>
          <Button type="link" size="small" icon={<BarChartOutlined />} onClick={() => h.onAnalyze(r.snapshot_id, r.name)}>
            {t('跨维度分析')}
          </Button>
          <Popconfirm title={t('确认删除此快照？')} onConfirm={() => h.onDelete(r.snapshot_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>{t('删除')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}

/* ── Custom Hook ────────────────────────────────────────────────────── */

function useAbutionGraph(t: TFunc) {
  const [snapshots, setSnapshots] = useState<AbutionSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [detailModal, setDetailModal] = useState<ModalState>({ open: false, data: null, name: '' });
  const [analysisModal, setAnalysisModal] = useState<ModalState>({ open: false, data: null, name: '' });

  const fetchSnapshots = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/api/ontology/abution-graph?limit=100');
      setSnapshots(extractList<AbutionSnapshot>(res, 'snapshots'));
    } catch (e) {
      console.error('Failed to fetch abution graph snapshots:', e);
      message.error(`${t('加载失败')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchSnapshots(); }, [fetchSnapshots]);

  const handleViewDetail = useCallback(async (id: string, name: string) => {
    try {
      const res = await apiClient.get(`/api/ontology/abution-graph/${id}`);
      setDetailModal({ open: true, data: res, name });
    } catch (e) {
      console.error('Failed to fetch snapshot detail:', e);
      message.error(`${t('获取详情失败')}: ${(e as Error).message}`);
    }
  }, [t]);

  const handleAnalyze = useCallback(async (id: string, name: string) => {
    setAnalyzingId(id);
    try {
      const res = await apiClient.post(`/api/ontology/abution-graph/${id}/analyze`);
      setAnalysisModal({ open: true, data: res, name });
    } catch (e) {
      console.error('Cross-dimension analysis failed:', e);
      message.error(`${t('分析失败')}: ${(e as Error).message}`);
    } finally {
      setAnalyzingId(null);
    }
  }, [t]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await apiClient.delete(`/api/ontology/abution-graph/${id}`);
      message.success(t('已删除'));
      await fetchSnapshots();
    } catch (e) {
      console.error('Delete failed:', e);
      message.error(`${t('删除失败')}: ${(e as Error).message}`);
    }
  }, [fetchSnapshots, t]);

  return {
    snapshots, loading, analyzingId, detailModal, setDetailModal, analysisModal, setAnalysisModal,
    fetchSnapshots, handleViewDetail, handleAnalyze, handleDelete,
  };
}

/* ── Detail Modal Renderer ──────────────────────────────────────────── */

function renderDetailContent(data: unknown, t: TFunc) {
  const snap = data as Record<string, unknown> | null;
  if (!snap || typeof snap !== 'object') return null;
  const fields: Array<[string, string]> = [
    ['snapshot_id', String(snap.snapshot_id ?? '-')],
    ['name', String(snap.name ?? '-')],
    ['temporal_node_count', String(snap.temporal_node_count ?? '-')],
    ['pattern_node_count', String(snap.pattern_node_count ?? '-')],
    ['force_node_count', String(snap.force_node_count ?? '-')],
    ['action_node_count', String(snap.action_node_count ?? '-')],
    ['created_at', snap.created_at ? new Date(snap.created_at as string).toLocaleString('zh-CN') : '-'],
  ];
  const labels: Record<string, string> = {
    snapshot_id: 'ID', name: t('名称'), temporal_node_count: t('时间节点'),
    pattern_node_count: t('模式节点'), force_node_count: t('力节点'),
    action_node_count: t('行动节点'), created_at: t('创建时间'),
  };
  return (
    <Descriptions size="small" column={1} bordered>
      {fields.map(([key, val]) => (
        <Descriptions.Item key={key} label={labels[key] || key}>{val}</Descriptions.Item>
      ))}
    </Descriptions>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */

export function AbutionGraphPage() {
  const { t } = useI18n('ontology');
  const vm = useAbutionGraph(t);
  const columns = buildColumns(
    { onViewDetail: vm.handleViewDetail, onAnalyze: vm.handleAnalyze, onDelete: vm.handleDelete },
    t,
  );

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ApartmentOutlined /><span>{t('Abution 图谱快照')}</span></Space>}
        extra={<Button icon={<ReloadOutlined />} onClick={vm.fetchSnapshots} loading={vm.loading}>{t('刷新')}</Button>}
      >
        <Spin spinning={vm.loading}>
          <Table<AbutionSnapshot>
            rowKey="snapshot_id"
            columns={columns}
            dataSource={vm.snapshots}
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true }}
            locale={{ emptyText: <Empty description={t('暂无快照')} /> }}
          />
        </Spin>
      </Card>

      <Modal
        title={`${t('快照详情')} - ${vm.detailModal.name}`}
        open={vm.detailModal.open}
        onCancel={() => vm.setDetailModal({ open: false, data: null, name: '' })}
        footer={null}
        width={600}
        destroyOnHidden
      >
        {renderDetailContent(vm.detailModal.data, t)}
      </Modal>

      <Modal
        title={`${t('跨维度分析')} - ${vm.analysisModal.name}`}
        open={vm.analysisModal.open}
        onCancel={() => vm.setAnalysisModal({ open: false, data: null, name: '' })}
        footer={null}
        width={720}
        destroyOnHidden
      >
        <pre style={{ maxHeight: 480, overflow: 'auto', fontSize: 12, background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
          {vm.analysisModal.data ? JSON.stringify(vm.analysisModal.data, null, 2) : ''}
        </pre>
      </Modal>
    </div>
  );
}
