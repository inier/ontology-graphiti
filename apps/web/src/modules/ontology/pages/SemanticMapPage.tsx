/**
 * SemanticMapPage — 语义映射图谱页面（Iter 4 / P3）
 *
 * 以卡片列表展示语义映射，支持查看图谱（JSON）、重新生成、删除操作。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Card, Row, Col, Tag, Button, Space, message, Empty,
  Modal, Spin, Popconfirm, Descriptions, Typography,
} from 'antd';
import {
  ReloadOutlined, EyeOutlined, DeleteOutlined, ApartmentOutlined, NodeIndexOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

/* ── Types ──────────────────────────────────────────────────────────── */

interface SemanticMap {
  map_id: string;
  name: string;
  description?: string;
  ontology_id: string;
  scenario_id?: string;
  node_count?: number;
  edge_count?: number;
  created_at: string;
}

interface GraphModalState {
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

/* ── Custom Hook ────────────────────────────────────────────────────── */

function useSemanticMap(t: TFunc) {
  const [maps, setMaps] = useState<SemanticMap[]>([]);
  const [loading, setLoading] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [graphModal, setGraphModal] = useState<GraphModalState>({ open: false, data: null, name: '' });

  const fetchMaps = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/api/semantic-map?limit=100');
      setMaps(extractList<SemanticMap>(res, 'maps'));
    } catch (e) {
      console.error('Failed to fetch semantic maps:', e);
      message.error(`${t('加载失败')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {   void (async () => {
    fetchMaps();
  })(); }, [fetchMaps]);

  const handleViewGraph = useCallback(async (id: string, name: string) => {
    try {
      const res = await apiClient.get(`/api/semantic-map/${id}/graph`);
      setGraphModal({ open: true, data: res, name });
    } catch (e) {
      console.error('Failed to fetch graph:', e);
      message.error(`${t('获取图谱失败')}: ${(e as Error).message}`);
    }
  }, [t]);

  const handleRegenerate = useCallback(async (id: string) => {
    setRegeneratingId(id);
    try {
      await apiClient.post(`/api/semantic-map/${id}/regenerate`);
      message.success(t('重新生成已启动'));
      await fetchMaps();
    } catch (e) {
      console.error('Regenerate failed:', e);
      message.error(`${t('重新生成失败')}: ${(e as Error).message}`);
    } finally {
      setRegeneratingId(null);
    }
  }, [fetchMaps, t]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await apiClient.delete(`/api/semantic-map/${id}`);
      message.success(t('已删除'));
      await fetchMaps();
    } catch (e) {
      console.error('Delete failed:', e);
      message.error(`${t('删除失败')}: ${(e as Error).message}`);
    }
  }, [fetchMaps, t]);

  return {
    maps, loading, regeneratingId, graphModal, setGraphModal,
    fetchMaps, handleViewGraph, handleRegenerate, handleDelete,
  };
}

/* ── Card Renderer ──────────────────────────────────────────────────── */

function MapCard(props: { map: SemanticMap; vm: ReturnType<typeof useSemanticMap>; t: TFunc }) {
  const { map, vm, t } = props;
  return (
    <Card
      size="small"
      hoverable
      title={<Space><ApartmentOutlined /><Text strong>{map.name}</Text></Space>}
      actions={[
        <Button
          key="graph" type="link" size="small" icon={<EyeOutlined />}
          onClick={() => vm.handleViewGraph(map.map_id, map.name)}
        >
          {t('查看图谱')}
        </Button>,
        <Button
          key="regen" type="link" size="small" icon={<ReloadOutlined />}
          loading={vm.regeneratingId === map.map_id}
          onClick={() => vm.handleRegenerate(map.map_id)}
        >
          {t('重新生成')}
        </Button>,
        <Popconfirm
          key="del"
          title={t('确认删除此映射？')}
          onConfirm={() => vm.handleDelete(map.map_id)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>{t('删除')}</Button>
        </Popconfirm>,
      ]}
    >
      <Descriptions size="small" column={1} colon={false}>
        <Descriptions.Item label={t('描述')}>{map.description || '-'}</Descriptions.Item>
        <Descriptions.Item label={t('本体ID')}>
          <Text code>{map.ontology_id || '-'}</Text>
        </Descriptions.Item>
        {map.scenario_id && (
          <Descriptions.Item label={t('场景ID')}>
            <Text code>{map.scenario_id}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>
      <Space style={{ marginTop: 8 }}>
        <Tag icon={<NodeIndexOutlined />} color="blue">{t('节点')}: {map.node_count ?? '-'}</Tag>
        <Tag color="geekblue">{t('边')}: {map.edge_count ?? '-'}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {map.created_at ? new Date(map.created_at).toLocaleString('zh-CN') : '-'}
        </Text>
      </Space>
    </Card>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */

export function SemanticMapPage() {
  const { t } = useI18n('ontology');
  const vm = useSemanticMap(t);

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ApartmentOutlined /><span>{t('语义映射图谱')}</span></Space>}
        extra={<Button icon={<ReloadOutlined />} onClick={vm.fetchMaps} loading={vm.loading}>{t('刷新')}</Button>}
      >
        <Spin spinning={vm.loading}>
          {vm.maps.length === 0 && !vm.loading ? (
            <Empty description={t('暂无语义映射')} />
          ) : (
            <Row gutter={[12, 12]}>
              {vm.maps.map((m) => (
                <Col key={m.map_id} xs={24} sm={12} lg={8} xl={6}>
                  <MapCard map={m} vm={vm} t={t} />
                </Col>
              ))}
            </Row>
          )}
        </Spin>
      </Card>

      <Modal
        title={`${t('图谱详情')} - ${vm.graphModal.name}`}
        open={vm.graphModal.open}
        onCancel={() => vm.setGraphModal({ open: false, data: null, name: '' })}
        footer={null}
        width={720}
        destroyOnHidden
      >
        <pre style={{ maxHeight: 480, overflow: 'auto', fontSize: 12, background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
          {vm.graphModal.data ? JSON.stringify(vm.graphModal.data, null, 2) : ''}
        </pre>
      </Modal>
    </div>
  );
}
