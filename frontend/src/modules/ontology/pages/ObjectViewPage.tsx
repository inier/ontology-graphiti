/**
 * ObjectViewPage 页面 —— 对象视图查询页面（FR-036 / T414）
 *
 * L5 页面：
 *   - 左侧：视图列表（按 ObjectType 分组）
 *   - 右侧：当前选中视图的查询结果
 *   - 顶部：搜索 / 导出按钮（受 OPA 权限控制）
 *   - 底部：当前用户对该视图的权限提示
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, List, Tag, Button, Space, Input, Empty, Spin, message, Typography, Statistic, Alert, Modal, Tooltip, Divider,
} from 'antd';
import {
  ReloadOutlined, SearchOutlined, DownloadOutlined, EyeOutlined, LockOutlined, UnlockOutlined, PlusOutlined,
} from '@ant-design/icons';
import { viewApi, type ObjectView, type ViewPermission } from '../services/viewApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Title, Text } = Typography;

export interface ObjectViewPageProps {
  workspaceId?: string;
  onCreateView?: () => void;
}

export function ObjectViewPage({ workspaceId, onCreateView }: ObjectViewPageProps) {
  const { t } = useI18n();
  void t;
  const [views, setViews] = useState<ObjectView[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [querying, setQuerying] = useState(false);
  const [userPerm, setUserPerm] = useState<ViewPermission | null>(null);
  const [exporting, setExporting] = useState(false);

  const fetchViews = useCallback(async () => {
    setLoading(true);
    try {
      const data = await viewApi.listViews({ workspace_id: workspaceId });
      setViews(data);
      if (data.length > 0 && !selectedId) setSelectedId(data[0].id);
    } catch (e) {
      message.error(`加载视图列表失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, selectedId]);

  const fetchUserPermission = useCallback(async (viewId: string) => {
    try {
      const perm = await viewApi.getMyPermission(viewId);
      setUserPerm(perm);
    } catch {
      setUserPerm(null);
    }
  }, []);

  const runQuery = useCallback(async (viewId: string) => {
    setQuerying(true);
    try {
      const data = await viewApi.queryView(viewId, {});
      setRows(data.rows || []);
    } catch (e) {
      message.error(`查询失败: ${(e as Error).message}`);
    } finally {
      setQuerying(false);
    }
  }, []);

  useEffect(() => { fetchViews(); }, [fetchViews]);
  useEffect(() => { if (selectedId) { fetchUserPermission(selectedId); runQuery(selectedId); } }, [selectedId, fetchUserPermission, runQuery]);

  const filteredViews = useMemo(() => {
    if (!searchText) return views;
    const s = searchText.toLowerCase();
    return views.filter((v) => v.name.toLowerCase().includes(s) || v.object_type_name.toLowerCase().includes(s));
  }, [views, searchText]);

  const grouped = useMemo(() => {
    const map = new Map<string, ObjectView[]>();
    for (const v of filteredViews) {
      const k = v.object_type_name || '未分类';
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(v);
    }
    return Array.from(map.entries());
  }, [filteredViews]);

  const currentView = useMemo(() => views.find((v) => v.id === selectedId), [views, selectedId]);

  const onExport = useCallback(async (format: 'csv' | 'json') => {
    if (!currentView) return;
    if (!userPerm?.can_export) {
      Modal.warning({ title: '权限不足', content: '当前角色无权导出此视图' });
      return;
    }
    setExporting(true);
    try {
      const blob = await viewApi.exportView(currentView.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentView.name}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      message.success(`已导出 ${format.toUpperCase()}`);
    } catch (e) {
      message.error(`导出失败: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  }, [currentView, userPerm]);

  const tableColumns = useMemo(() => {
    if (!currentView) return [];
    return currentView.fields.filter((f) => f.visible).map((f) => ({
      title: f.label || f.field,
      dataIndex: f.field,
      key: f.field,
      ellipsis: true,
    }));
  }, [currentView]);

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>对象视图查询</Title>
            <Tag color="blue">{workspaceId || 'default'}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Input prefix={<SearchOutlined />} placeholder="搜索视图..." value={searchText} onChange={(e) => setSearchText(e.target.value)} style={{ width: 220 }} />
            <Button icon={<ReloadOutlined />} onClick={fetchViews}>刷新</Button>
            {onCreateView && <Button type="primary" icon={<PlusOutlined />} onClick={onCreateView}>新建视图</Button>}
          </Space>
        }
      >
        <Row gutter={16}>
          <Col span={7}>
            <Card type="inner" title={`视图列表 (${filteredViews.length})`} size="small">
              <Spin spinning={loading}>
                {grouped.length === 0 ? <Empty description="无视图" /> : (
                  <List
                    size="small"
                    dataSource={grouped}
                    renderItem={([objectType, list]) => (
                      <List.Item style={{ display: 'block', padding: 0 }}>
                        <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                          <Tag color="purple">{objectType}</Tag>
                        </Divider>
                        {list.map((v) => (
                          <List.Item
                            key={v.id}
                            style={{ padding: '8px 12px', cursor: 'pointer', background: v.id === selectedId ? '#e6f4ff' : undefined }}
                            onClick={() => setSelectedId(v.id)}
                            actions={[<EyeOutlined key="view" />]}
                          >
                            <Space>
                              <Text strong={v.id === selectedId}>{v.name}</Text>
                              {v.id === selectedId && <Tag color="blue">当前</Tag>}
                            </Space>
                          </List.Item>
                        ))}
                      </List.Item>
                    )}
                  />
                )}
              </Spin>
            </Card>
          </Col>
          <Col span={17}>
            <Card
              type="inner"
              title={currentView ? `查询结果: ${currentView.name}` : '请选择视图'}
              size="small"
              extra={
                currentView && (
                  <Space>
                    {userPerm ? (
                      <Tag icon={<UnlockOutlined />} color="green">可访问</Tag>
                    ) : (
                      <Tag icon={<LockOutlined />} color="red">受限</Tag>
                    )}
                    <Tooltip title={userPerm?.can_export ? '导出为 CSV' : '无导出权限'}>
                      <Button size="small" icon={<DownloadOutlined />} loading={exporting} disabled={!userPerm?.can_export} onClick={() => onExport('csv')}>CSV</Button>
                    </Tooltip>
                    <Tooltip title={userPerm?.can_export ? '导出为 JSON' : '无导出权限'}>
                      <Button size="small" icon={<DownloadOutlined />} loading={exporting} disabled={!userPerm?.can_export} onClick={() => onExport('json')}>JSON</Button>
                    </Tooltip>
                  </Space>
                )
              }
            >
              {currentView ? (
                <Space orientation="vertical" style={{ width: '100%' }}>
                  <Row gutter={16}>
                    <Col span={8}><Statistic title="总行数" value={rows.length} /></Col>
                    <Col span={8}><Statistic title="可见字段" value={currentView.fields.filter((f) => f.visible).length} /></Col>
                    <Col span={8}><Statistic title="Limit" value={currentView.limit} /></Col>
                  </Row>
                  {userPerm?.redaction_rules && userPerm.redaction_rules.length > 0 && (
                    <Alert
                      type="warning"
                      showIcon
                      message="字段脱敏规则已生效"
                      description={`当前角色对 ${userPerm.redaction_rules.length} 个字段应用了脱敏`}
                    />
                  )}
                  <Spin spinning={querying}>
                    {rows.length === 0 ? <Empty description="无数据" /> : (
                      <AdvancedTable
                        size="small"
                        rowKey={(_, i) => String(i)}
                        dataSource={rows}
                        columns={tableColumns}
                        pagination={{ pageSize: 20, showSizeChanger: true }}
                        scroll={{ x: 'max-content' }}
                      />
                    )}
                  </Spin>
                </Space>
              ) : (
                <Empty description="从左侧选择一个视图" />
              )}
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
}

export default ObjectViewPage;
