/**
 * StorageBrowser —— 对象存储浏览（bucket / 对象 / 元数据 / 预签名 / 删除）
 *
 * 为什么需要这个组件：
 *   `/settings/storage` 此前只挂了「MinIO Console iframe」+「关于」两个页签。
 *   iframe 依赖后端 /minio-console/ 反向代理与容器内 Console UI，代理不通就是一
 *   片空白；而真正结构化的 7 个端点（`/api/minio-admin/*`，后端
 *   platform/minio_admin/api/routes.py 全部实现且已在 router_registry 注册）
 *   以及前端 service（minio-admin/services/minioAdminApi.ts，7 个方法全写好）
 *   都没有任何 UI 消费 —— 功能在、线也接了、就是没人用。
 *
 * 契约对齐（逐条核过 routes.py）：
 *   GET    /api/minio-admin/status                    → { available, endpoint, sdk_installed, detail }
 *   GET    /api/minio-admin/buckets                   → MinIOBucket[]（**直接返回数组**，不是 {buckets}）
 *   GET    /api/minio-admin/objects?bucket&prefix&page&page_size → { items, total, page, page_size, total_pages }
 *   GET    /api/minio-admin/objects/metadata?bucket&key
 *   GET    /api/minio-admin/objects/presigned-url?bucket&key&expires_hours
 *   DELETE /api/minio-admin/objects?bucket&key
 *   GET    /api/minio-admin/stats
 *
 * 权限：后端对非管理员在 /objects 上直接 403（"仅管理员可访问对象存储管理"），
 *      所以这里对 403 单独给提示，而不是笼统报「加载失败」。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Card, Col, Descriptions, Drawer, Empty, Popconfirm, Row, Space, Table, Tag, Typography, message,
} from 'antd';
import {
  DeleteOutlined, FileOutlined, FolderOutlined, InfoCircleOutlined, LinkOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  minioAdminApi,
  type MinIOBucket,
  type MinIOObject,
  type MinIOObjectList,
  type MinIOObjectMetadata,
  type MinIOStorageStats,
} from '../services/minioAdminApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface MinIOStatus {
  available: boolean;
  endpoint?: string;
  sdk_installed?: boolean;
  detail?: string;
}

/** 后端 403 会明确说明原因，这里优先把它透出来，而不是盖成「加载失败」 */
function reasonOf(e: unknown): string {
  const err = e as { status?: number; message?: string; detail?: string };
  if (err?.status === 403) return err.detail || '仅管理员可访问对象存储管理';
  if (err?.detail) return err.detail;
  if (err?.status && err?.message) return `HTTP ${err.status}：${err.message}`;
  return err?.message ?? String(e);
}

export function StorageBrowser() {
  const { t } = useI18n();

  // ── 概览（status + buckets + stats 一起刷）──
  const [reloadToken, setReloadToken] = useState(0);
  const [loadedToken, setLoadedToken] = useState(-1);
  const [status, setStatus] = useState<MinIOStatus | null>(null);
  const [buckets, setBuckets] = useState<MinIOBucket[]>([]);
  const [stats, setStats] = useState<MinIOStorageStats | null>(null);
  // 错误与「产生它的那次请求 token」绑定：换 token 即自动失效，
  // 这样不必在 effect 同步体里 setState(空串) 清错（会触发 set-state-in-effect）
  const [overviewError, setOverviewError] = useState<{ token: number; message: string } | null>(null);

  // ── 当前选中桶与对象列表 ──
  const [bucket, setBucket] = useState<string>('');
  const [prefix, setPrefix] = useState<string>('');
  const [page, setPage] = useState(1);
  const [objectPage, setObjectPage] = useState<MinIOObjectList | null>(null);
  const [objectsToken, setObjectsToken] = useState(0);
  const [objectsDone, setObjectsDone] = useState(-1);
  const [objectsError, setObjectsError] = useState<{ token: number; message: string } | null>(null);

  const [metaOpen, setMetaOpen] = useState(false);
  const [meta, setMeta] = useState<MinIOObjectMetadata | null>(null);

  // effect 里只发请求，状态一律写进 .then/.catch —— 同步体写 state 会触发
  // react-hooks/set-state-in-effect，且会让 loading 推导失真
  useEffect(() => {
    const token = reloadToken;
    let ignore = false;
    void Promise.allSettled([
      minioAdminApi.getStatus(),
      minioAdminApi.listBuckets(),
      minioAdminApi.getStorageStats(),
    ]).then(([statusRes, bucketRes, statsRes]) => {
      if (ignore) return;
      if (statusRes.status === 'fulfilled') {
        setStatus(statusRes.value);
        setOverviewError(null);
      } else {
        setStatus(null);
        setOverviewError({ token, message: reasonOf(statusRes.reason) });
      }
      if (bucketRes.status === 'fulfilled') {
        setBuckets(bucketRes.value ?? []);
        // 首次加载自动选中第一个桶，省掉一次点击
        setBucket((prev) => prev || bucketRes.value?.[0]?.name || '');
      } else {
        setBuckets([]);
      }
      if (statsRes.status === 'fulfilled') setStats(statsRes.value);
      setLoadedToken(token);
    });
    return () => {
      ignore = true;
    };
  }, [reloadToken]);

  useEffect(() => {
    if (!bucket) return;
    const token = objectsToken;
    let ignore = false;
    void minioAdminApi
      .listObjects(bucket, prefix || undefined, page, 50)
      .then((data) => {
        if (!ignore) {
          setObjectPage(data);
          setObjectsError(null);
        }
      })
      .catch((e) => {
        if (!ignore) {
          setObjectPage(null);
          setObjectsError({ token, message: reasonOf(e) });
        }
      })
      .finally(() => {
        if (!ignore) setObjectsDone(token);
      });
    return () => {
      ignore = true;
    };
  }, [bucket, prefix, page, objectsToken]);

  const overviewLoading = loadedToken !== reloadToken;
  const objectsLoading = objectsDone !== objectsToken;

  const reload = useCallback(() => {
    setReloadToken((v) => v + 1);
    setObjectsToken((v) => v + 1);
  }, []);

  const selectBucket = useCallback((name: string) => {
    setBucket(name);
    setPrefix('');
    setPage(1);
    // 换桶要重发：objectsToken 递增保证 loading 由「已完成 token ≠ 当前 token」推导
    setObjectsToken((v) => v + 1);
  }, []);

  const enterDir = useCallback((name: string) => {
    setPrefix(name);
    setPage(1);
    setObjectsToken((v) => v + 1);
  }, []);

  const goUp = useCallback(() => {
    const trimmed = prefix.replace(/\/$/, '');
    const idx = trimmed.lastIndexOf('/');
    setPrefix(idx >= 0 ? `${trimmed.slice(0, idx + 1)}` : '');
    setPage(1);
    setObjectsToken((v) => v + 1);
  }, [prefix]);

  const showMetadata = useCallback(async (row: MinIOObject) => {
    try {
      const data = await minioAdminApi.getObjectMetadata(bucket, row.name);
      setMeta(data);
      setMetaOpen(true);
    } catch (e) {
      message.error(`${t('读取元数据失败')}：${reasonOf(e)}`);
    }
  }, [bucket, t]);

  const copyPresigned = useCallback(async (row: MinIOObject) => {
    try {
      const { url, expires_seconds } = await minioAdminApi.getPresignedUrl(bucket, row.name, 1);
      await navigator.clipboard.writeText(url);
      message.success(t('下载链接已复制，{{h}} 小时内有效', { h: Math.round(expires_seconds / 3600) }));
    } catch (e) {
      message.error(`${t('生成下载链接失败')}：${reasonOf(e)}`);
    }
  }, [bucket, t]);

  const removeObject = useCallback(async (row: MinIOObject) => {
    try {
      await minioAdminApi.deleteObject(bucket, row.name);
      message.success(t('已删除 {{name}}', { name: row.display_name }));
      setObjectsToken((v) => v + 1);
      setReloadToken((v) => v + 1);
    } catch (e) {
      message.error(`${t('删除失败')}：${reasonOf(e)}`);
    }
  }, [bucket, t]);

  const unavailable = status !== null && !status.available;
  // 只有「产生该错误的 token 仍是当前 token」才展示，换桶/换页/刷新后自动消失
  const overviewErrorMsg = overviewError?.token === reloadToken ? overviewError.message : '';
  const objectsErrorMsg = objectsError?.token === objectsToken ? objectsError.message : '';

  return (
    <Card
      title={
        <Space>
          <span>{t('存储浏览')}</span>
          {status ? (
            <Tag color={status.available ? 'green' : 'red'}>
              {status.available ? t('已连接') : t('未连接')}
            </Tag>
          ) : null}
          {status?.endpoint ? (
            <Text type="secondary" style={{ fontSize: 12 }}>{status.endpoint}</Text>
          ) : null}
        </Space>
      }
      extra={
        <Button icon={<ReloadOutlined />} loading={overviewLoading} onClick={reload}>
          {t('刷新')}
        </Button>
      }
    >
      {overviewErrorMsg ? (
        <Alert
          type="error"
          showIcon
          title={t('对象存储不可用')}
          description={overviewErrorMsg}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {unavailable ? (
        <Alert
          type="warning"
          showIcon
          title={t('MinIO 未就绪')}
          description={status?.detail || t('请确认 MinIO 容器已启动（podman ps graphiti-minio）且 S3 凭证配置正确。')}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {stats ? (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card size="small">
              <Text type="secondary">{t('存储桶')}</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{stats.total_buckets}</div>
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small">
              <Text type="secondary">{t('对象总数')}</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{stats.total_objects}</div>
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small">
              <Text type="secondary">{t('占用空间')}</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{stats.total_size_display}</div>
            </Card>
          </Col>
        </Row>
      ) : null}

      <Row gutter={16}>
        <Col span={7}>
          <Card size="small" title={t('存储桶')} styles={{ body: { padding: 0 } }}>
            {buckets.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={overviewLoading ? t('加载中…') : t('没有可访问的存储桶')}
                style={{ padding: 16 }}
              />
            ) : (
              <Table
                rowKey="name"
                size="small"
                showHeader={false}
                pagination={false}
                dataSource={buckets}
                rowClassName={(r) => (r.name === bucket ? 'ant-table-row-selected' : '')}
                onRow={(r) => ({ onClick: () => selectBucket(r.name) })}
                columns={[
                  {
                    title: t('名称'),
                    dataIndex: 'display_name',
                    key: 'display_name',
                    render: (v: string, r: MinIOBucket) => (
                      <div>
                        <div style={{ fontWeight: r.name === bucket ? 600 : 400 }}>{v || r.name}</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {r.object_count} {t('个对象')} · {r.total_size_display}
                        </Text>
                      </div>
                    ),
                  },
                ]}
              />
            )}
          </Card>
        </Col>

        <Col span={17}>
          <Card
            size="small"
            title={
              <Space size={4}>
                <span>{bucket || t('未选择存储桶')}</span>
                {prefix ? (
                  <>
                    <Text type="secondary">/{prefix}</Text>
                    <Button size="small" type="link" onClick={goUp}>{t('返回上级')}</Button>
                  </>
                ) : null}
              </Space>
            }
          >
            {objectsErrorMsg ? (
              <Alert type="warning" showIcon title={t('对象列表不可用')} description={objectsErrorMsg} />
            ) : (
              <Table
                rowKey="name"
                size="small"
                loading={objectsLoading}
                dataSource={objectPage?.items ?? []}
                locale={{ emptyText: objectsLoading ? t('加载中…') : t('该路径下没有对象') }}
                pagination={{
                  current: objectPage?.page ?? page,
                  pageSize: objectPage?.page_size ?? 50,
                  total: objectPage?.total ?? 0,
                  showSizeChanger: false,
                  onChange: (p) => {
                    setPage(p);
                    setObjectsToken((v) => v + 1);
                  },
                }}
                columns={[
                  {
                    title: t('名称'),
                    dataIndex: 'display_name',
                    key: 'display_name',
                    ellipsis: true,
                    render: (v: string, r: MinIOObject) =>
                      r.is_dir ? (
                        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => enterDir(r.name)}>
                          <FolderOutlined /> {v}
                        </Button>
                      ) : (
                        <span>
                          <FileOutlined /> {v}
                        </span>
                      ),
                  },
                  { title: t('大小'), dataIndex: 'size_display', key: 'size_display', width: 100 },
                  { title: t('类型'), dataIndex: 'content_type', key: 'content_type', width: 160, ellipsis: true },
                  {
                    title: t('修改时间'),
                    dataIndex: 'last_modified',
                    key: 'last_modified',
                    width: 180,
                    render: (v: string) => v || '-',
                  },
                  {
                    title: t('操作'),
                    key: 'actions',
                    width: 150,
                    render: (_: unknown, r: MinIOObject) =>
                      r.is_dir ? null : (
                        <Space size={0}>
                          <Button
                            size="small"
                            type="text"
                            icon={<InfoCircleOutlined />}
                            title={t('元数据')}
                            onClick={() => void showMetadata(r)}
                          />
                          <Button
                            size="small"
                            type="text"
                            icon={<LinkOutlined />}
                            title={t('复制下载链接')}
                            onClick={() => void copyPresigned(r)}
                          />
                          <Popconfirm
                            title={t('删除对象？')}
                            description={r.name}
                            onConfirm={() => void removeObject(r)}
                          >
                            <Button size="small" type="text" danger icon={<DeleteOutlined />} title={t('删除')} />
                          </Popconfirm>
                        </Space>
                      ),
                  },
                ]}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Drawer
        title={t('对象元数据')}
        open={metaOpen}
        onClose={() => setMetaOpen(false)}
        size="default"
      >
        {meta ? (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label={t('存储桶')}>{meta.bucket}</Descriptions.Item>
            <Descriptions.Item label={t('对象键')}>{meta.key}</Descriptions.Item>
            <Descriptions.Item label={t('大小')}>{meta.size_display}</Descriptions.Item>
            <Descriptions.Item label={t('类型')}>{meta.content_type || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('修改时间')}>{meta.last_modified || '-'}</Descriptions.Item>
            <Descriptions.Item label="ETag">{meta.etag || '-'}</Descriptions.Item>
            {Object.entries(meta.metadata ?? {}).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
            ))}
          </Descriptions>
        ) : (
          <Empty description={t('没有元数据')} />
        )}
      </Drawer>
    </Card>
  );
}

export default StorageBrowser;
