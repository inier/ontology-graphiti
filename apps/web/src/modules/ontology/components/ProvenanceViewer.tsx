/**
 * ProvenanceViewer —— 抽取溯源（实体 → 源文档 / 切片 / 模板 / 置信度）
 *
 * 真实契约（`odap/biz/core/ontology/extraction/api/routes.py`）：
 *   GET /api/extraction/provenance/{entity_id}
 *       → { status: "ok", provenance: <extraction_provenance 表的一行> }
 *   GET /api/extraction/provenance/by-source/{doc_id}
 *       → { status: "ok", entities: [...] }
 *
 * 表结构（`hyper_extract/impl/provenance_tracker.py` 的 CREATE TABLE）：
 *   provenance_id / entity_id / entity_type / session_id / source_doc_id /
 *   vector_chunk_id / doc_fragment_id / extraction_method / he_template_version /
 *   source_template / confidence_score / timestamp
 *
 * 旧实现的三处问题（挂上去就是错的，所以重写）：
 *  1. 读 `confidence`，真实列名是 `confidence_score` —— 置信度永远不显示；
 *  2. 读 `source_doc_name`，后端根本没有这个字段（只有 source_doc_id）；
 *  3. `useState(() => { if (visible) load() })` 把 useState 当 effect 用 ——
 *     初始化函数只在首次渲染跑一次，抽屉后续打开**完全不加载数据**；
 *     另外「查看原文」按钮只弹一句「待实现」，而知识库没有文档详情路由。
 *
 * 现在的「同源实体」按钮是真功能：走 `/provenance/by-source/{doc_id}`
 * 反查同一份文档还抽出了哪些实体 —— 这是溯源最有用的一个视角。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Descriptions, Drawer, Empty, Space, Table, Tag, Typography,
} from 'antd';
import {
  ClockCircleOutlined, ExperimentOutlined, FileSearchOutlined,
  PartitionOutlined, TagOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

export interface ProvenanceViewerProps {
  entityId: string;
  entityType?: string;
  visible: boolean;
  onClose: () => void;
}

/** 与 extraction_provenance 表逐列对应，不做任何重命名 */
interface ProvenanceRecord {
  provenance_id?: string;
  entity_id: string;
  entity_type?: string;
  session_id?: string;
  source_doc_id: string;
  vector_chunk_id?: string | null;
  doc_fragment_id?: string | null;
  extraction_method?: string;
  he_template_version?: string | null;
  source_template?: string | null;
  confidence_score?: number | null;
  timestamp: string;
}

interface SiblingEntity {
  entity_id: string;
  entity_type?: string;
  extraction_method?: string;
  confidence_score?: number | null;
}

function reasonOf(e: unknown): { notFound: boolean; message: string } {
  const err = e as { status?: number; message?: string; detail?: string };
  const notFound = err?.status === 404;
  const message = err?.detail || (err?.status && err?.message ? `HTTP ${err.status}：${err.message}` : err?.message) || String(e);
  return { notFound, message };
}

export function ProvenanceViewer({ entityId, entityType, visible, onClose }: ProvenanceViewerProps) {
  const { t } = useI18n('ontology');

  const [loadToken, setLoadToken] = useState(0);
  const [doneToken, setDoneToken] = useState(-1);
  const [record, setRecord] = useState<ProvenanceRecord | null>(null);
  const [error, setError] = useState<{ token: number; message: string } | null>(null);
  const [notFound, setNotFound] = useState<{ token: number; value: boolean } | null>(null);

  const [siblings, setSiblings] = useState<SiblingEntity[]>([]);
  const [siblingsLoading, setSiblingsLoading] = useState(false);

  // 只在抽屉真正打开且 entityId 有效时请求；loading 由 token 差推导，
  // effect 同步体里不写 state（react-hooks/set-state-in-effect）
  useEffect(() => {
    if (!visible || !entityId) return;
    const token = loadToken;
    let ignore = false;
    void apiClient
      .get<{ status?: string; provenance?: ProvenanceRecord }>(`/api/extraction/provenance/${entityId}`)
      .then((res) => {
        if (ignore) return;
        setRecord(res?.provenance ?? null);
        setError(null);
        setNotFound({ token, value: !res?.provenance });
      })
      .catch((e) => {
        if (ignore) return;
        const { notFound: nf, message } = reasonOf(e);
        setRecord(null);
        setNotFound({ token, value: nf });
        setError({ token, message });
      })
      .finally(() => {
        if (!ignore) setDoneToken(token);
      });
    return () => {
      ignore = true;
    };
  }, [visible, entityId, loadToken]);

  const loading = visible && doneToken !== loadToken;
  const errorMsg = error?.token === loadToken ? error.message : '';
  const isNotFound = notFound?.token === loadToken && notFound.value;

  const loadSiblings = useCallback(async () => {
    if (!record?.source_doc_id) return;
    setSiblingsLoading(true);
    try {
      const res = await apiClient.get<{ entities?: SiblingEntity[] }>(
        `/api/extraction/provenance/by-source/${record.source_doc_id}`,
      );
      setSiblings(res?.entities ?? []);
    } catch (e) {
      setSiblings([]);
      setError({ token: loadToken, message: reasonOf(e).message });
    } finally {
      setSiblingsLoading(false);
    }
  }, [record, loadToken]);

  const close = useCallback(() => {
    setSiblings([]);
    onClose();
  }, [onClose]);

  const confidence = record?.confidence_score;

  return (
    <Drawer
      title={
        <Space>
          <FileSearchOutlined />
          {t('抽取溯源')}
        </Space>
      }
      open={visible}
      onClose={close}
      size="default"
    >
      {errorMsg ? (
        <Alert
          type="warning"
          showIcon
          title={t('溯源信息不可用')}
          description={errorMsg}
          action={
            <Button size="small" onClick={() => setLoadToken((n) => n + 1)}>
              {t('重试')}
            </Button>
          }
          style={{ marginBottom: 12 }}
        />
      ) : null}

      {loading ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('加载中…')} />
      ) : record ? (
        <>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label={t('实体 ID')}>
              <Text copyable code>{record.entity_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('实体类型')}>
              <Tag color="blue">{record.entity_type || entityType || '-'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={<Space><FileSearchOutlined />{t('来源文档')}</Space>}>
              <Space orientation="vertical" size={2}>
                <Text copyable code>{record.source_doc_id}</Text>
                <Button
                  type="link"
                  size="small"
                  style={{ padding: 0 }}
                  icon={<PartitionOutlined />}
                  loading={siblingsLoading}
                  onClick={() => void loadSiblings()}
                >
                  {t('查看同源实体')}
                </Button>
              </Space>
            </Descriptions.Item>
            {record.session_id ? (
              <Descriptions.Item label={t('抽取会话')}>
                <Text copyable code>{record.session_id}</Text>
              </Descriptions.Item>
            ) : null}
            {record.vector_chunk_id ? (
              <Descriptions.Item label={t('向量切片 ID')}>
                <Text copyable code>{record.vector_chunk_id}</Text>
              </Descriptions.Item>
            ) : null}
            {record.doc_fragment_id ? (
              <Descriptions.Item label={t('文档碎片 ID')}>
                <Text copyable code>{record.doc_fragment_id}</Text>
              </Descriptions.Item>
            ) : null}
            <Descriptions.Item label={<Space><ExperimentOutlined />{t('提取方法')}</Space>}>
              <Tag color="green">{record.extraction_method || '-'}</Tag>
            </Descriptions.Item>
            {record.source_template ? (
              <Descriptions.Item label={t('来源模板')}>
                <Tag>{record.source_template}</Tag>
              </Descriptions.Item>
            ) : null}
            {record.he_template_version ? (
              <Descriptions.Item label={<Space><TagOutlined />{t('HE 模板版本')}</Space>}>
                {record.he_template_version}
              </Descriptions.Item>
            ) : null}
            {typeof confidence === 'number' ? (
              <Descriptions.Item label={t('置信度')}>
                <Tag color={confidence >= 0.8 ? 'green' : confidence >= 0.5 ? 'orange' : 'red'}>
                  {(confidence * 100).toFixed(1)}%
                </Tag>
              </Descriptions.Item>
            ) : null}
            <Descriptions.Item label={<Space><ClockCircleOutlined />{t('提取时间')}</Space>}>
              {record.timestamp}
            </Descriptions.Item>
          </Descriptions>

          {siblings.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <Text strong>{t('同源实体（{{n}}）', { n: siblings.length })}</Text>
              <Table
                rowKey="entity_id"
                size="small"
                style={{ marginTop: 8 }}
                dataSource={siblings}
                pagination={{ pageSize: 10, size: 'small' }}
                columns={[
                  { title: t('实体 ID'), dataIndex: 'entity_id', key: 'entity_id', ellipsis: true },
                  { title: t('类型'), dataIndex: 'entity_type', key: 'entity_type', width: 110 },
                  { title: t('方法'), dataIndex: 'extraction_method', key: 'extraction_method', width: 110 },
                  {
                    title: t('置信度'),
                    dataIndex: 'confidence_score',
                    key: 'confidence_score',
                    width: 90,
                    render: (v: number | null | undefined) =>
                      typeof v === 'number' ? `${(v * 100).toFixed(0)}%` : '-',
                  },
                ]}
              />
            </div>
          ) : null}
        </>
      ) : (
        <Empty
          description={
            isNotFound
              ? t('该实体没有溯源记录（抽取时可能未开启溯源追踪）')
              : t('暂无溯源信息')
          }
        />
      )}
    </Drawer>
  );
}

export default ProvenanceViewer;
