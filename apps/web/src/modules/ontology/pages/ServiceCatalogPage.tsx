/**
 * ServiceCatalogPage — 服务目录管理页面（Iter 4 / P3）
 *
 * 展示本体服务化目录列表，支持按 service_type / status 筛选，
 * 并提供健康检查、废弃、退役操作。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Card, Table, Tag, Button, Space, Select, message, Empty,
  Modal, Spin, Popconfirm,
} from 'antd';
import type { TableColumnsType } from 'antd';
import {
  ReloadOutlined, HeartOutlined, StopOutlined, PoweroffOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ── Types ──────────────────────────────────────────────────────────── */

interface CatalogService {
  catalog_id: string;
  service_name: string;
  service_type: string;
  status: string;
  source_ontology_id: string;
  created_at: string;
  description?: string;
}

interface HealthModalState {
  open: boolean;
  data: unknown;
  name: string;
}

type TFunc = (key: string) => string;

/* ── Constants ──────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  deprecated: 'orange',
  retired: 'red',
};

const SERVICE_TYPE_OPTIONS = [
  { label: 'REST', value: 'rest' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'MCP', value: 'mcp' },
  { label: 'gRPC', value: 'grpc' },
];

const STATUS_OPTIONS = [
  { label: '活跃', value: 'active' },
  { label: '已废弃', value: 'deprecated' },
  { label: '已退役', value: 'retired' },
];

/* ── Helpers ────────────────────────────────────────────────────────── */

/** 从 API 响应中提取列表数据，兼容 {status, data} 包裹和 {items} 对象。 */
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

interface CatalogHandlers {
  onHealthCheck: (id: string, name: string) => void;
  onDeprecate: (id: string) => void;
  onRetire: (id: string) => void;
}

function buildColumns(h: CatalogHandlers, t: TFunc): TableColumnsType<CatalogService> {
  return [
    { title: t('服务名称'), dataIndex: 'service_name', key: 'service_name', ellipsis: true },
    { title: t('类型'), dataIndex: 'service_type', key: 'service_type', width: 100, render: (v: string) => <Tag>{v || '-'}</Tag> },
    {
      title: t('状态'), dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v || '-'}</Tag>,
    },
    { title: t('源本体'), dataIndex: 'source_ontology_id', key: 'source_ontology_id', width: 160, ellipsis: true, render: (v: string) => v || '-' },
    {
      title: t('创建时间'), dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: t('操作'), key: 'action', width: 250,
      render: (_: unknown, r: CatalogService) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<HeartOutlined />} onClick={() => h.onHealthCheck(r.catalog_id, r.service_name)}>
            {t('健康检查')}
          </Button>
          <Popconfirm title={t('确认废弃此服务？')} onConfirm={() => h.onDeprecate(r.catalog_id)}>
            <Button type="link" size="small" icon={<StopOutlined />} disabled={r.status !== 'active'}>
              {t('废弃')}
            </Button>
          </Popconfirm>
          <Popconfirm title={t('确认退役此服务？')} onConfirm={() => h.onRetire(r.catalog_id)}>
            <Button type="link" size="small" danger icon={<PoweroffOutlined />} disabled={r.status === 'retired'}>
              {t('退役')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}

/* ── Custom Hook ────────────────────────────────────────────────────── */

function useServiceCatalog(t: TFunc) {
  const [services, setServices] = useState<CatalogService[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState<string | undefined>();
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [healthModal, setHealthModal] = useState<HealthModalState>({ open: false, data: null, name: '' });

  const fetchCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterType) params.set('service_type', filterType);
      if (filterStatus) params.set('status', filterStatus);
      const res = await apiClient.get(`/api/ontology/servitization/catalog?${params}`);
      setServices(extractList<CatalogService>(res, 'services'));
    } catch (e) {
      console.error('Failed to fetch service catalog:', e);
      message.error(`${t('加载失败')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus, t]);

  useEffect(() => { fetchCatalog(); }, [fetchCatalog]);

  const handleHealthCheck = useCallback(async (id: string, name: string) => {
    try {
      const res = await apiClient.get(`/api/ontology/servitization/catalog/${id}/health`);
      setHealthModal({ open: true, data: res, name });
    } catch (e) {
      console.error('Health check failed:', e);
      message.error(`${t('健康检查失败')}: ${(e as Error).message}`);
    }
  }, [t]);

  const handleDeprecate = useCallback(async (id: string) => {
    try {
      await apiClient.post(`/api/ontology/servitization/catalog/${id}/deprecate`);
      message.success(t('已废弃'));
      await fetchCatalog();
    } catch (e) {
      console.error('Deprecate failed:', e);
      message.error(`${t('操作失败')}: ${(e as Error).message}`);
    }
  }, [fetchCatalog, t]);

  const handleRetire = useCallback(async (id: string) => {
    try {
      await apiClient.post(`/api/ontology/servitization/catalog/${id}/retire`);
      message.success(t('已退役'));
      await fetchCatalog();
    } catch (e) {
      console.error('Retire failed:', e);
      message.error(`${t('操作失败')}: ${(e as Error).message}`);
    }
  }, [fetchCatalog, t]);

  return {
    services, loading, filterType, filterStatus, setFilterType, setFilterStatus,
    healthModal, setHealthModal, fetchCatalog, handleHealthCheck, handleDeprecate, handleRetire,
  };
}

/* ── Component ──────────────────────────────────────────────────────── */

export function ServiceCatalogPage() {
  const { t } = useI18n('ontology');
  const vm = useServiceCatalog(t);
  const columns = buildColumns(
    { onHealthCheck: vm.handleHealthCheck, onDeprecate: vm.handleDeprecate, onRetire: vm.handleRetire },
    t,
  );

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={t('服务目录')}
        extra={<Button icon={<ReloadOutlined />} onClick={vm.fetchCatalog} loading={vm.loading}>{t('刷新')}</Button>}
      >
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder={t('服务类型')}
            allowClear
            style={{ width: 160 }}
            options={SERVICE_TYPE_OPTIONS}
            value={vm.filterType}
            onChange={(v) => vm.setFilterType(v ?? undefined)}
          />
          <Select
            placeholder={t('状态')}
            allowClear
            style={{ width: 140 }}
            options={STATUS_OPTIONS}
            value={vm.filterStatus}
            onChange={(v) => vm.setFilterStatus(v ?? undefined)}
          />
        </Space>
        <Spin spinning={vm.loading}>
          <Table<CatalogService>
            rowKey="catalog_id"
            columns={columns}
            dataSource={vm.services}
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true }}
            locale={{ emptyText: <Empty description={t('暂无服务')} /> }}
          />
        </Spin>
      </Card>

      <Modal
        title={`${t('健康检查')} - ${vm.healthModal.name}`}
        open={vm.healthModal.open}
        onCancel={() => vm.setHealthModal({ open: false, data: null, name: '' })}
        footer={null}
        width={600}
        destroyOnHidden
      >
        <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12, background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
          {vm.healthModal.data ? JSON.stringify(vm.healthModal.data, null, 2) : ''}
        </pre>
      </Modal>
    </div>
  );
}
