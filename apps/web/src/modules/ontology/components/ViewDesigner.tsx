/**
 * ViewDesigner 组件 —— 视图设计器（FR-036 / T413）
 *
 * 可视化三栏布局：
 *   - 左侧：ObjectType 树（选择数据源）
 *   - 中间：当前视图的"字段"+"过滤"+"排序"+"限制"+"权限"配置
 *   - 右侧：实时预览查询结果
 *
 * 两种模式：
 *   - `viewId` 有值 → 编辑既有视图，保存走 PUT /api/ontology/views/{id}
 *   - `viewId` 为空 → 新建视图，保存走 POST /api/ontology/views
 *     （此前组件把 viewId 定为必填，只能改不能建，"新建视图"入口等于不存在）
 *
 * 契约要点：
 *   - 后端 `CreateViewRequest` 必填 name/base_type_id/role，filters 在请求边界
 *     接受规则数组并归一成 `{field: {op: value}}`，因此这里直接提交数组。
 *   - 预览必须针对一个已存在的视图 id 执行（`POST /views/{id}/query`），
 *     新建模式下未保存前没有 id，故预览按钮禁用并给出说明，而不是发一个必然 404 的请求。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tree, Input, Select, Button, Space, Tabs, Tag, Empty, Spin, message,
  Typography, Alert, InputNumber, Switch, Divider, Tooltip,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, DeleteOutlined, SaveOutlined, PlayCircleOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons';
import { viewApi, type ExtendedObjectView, type ViewPermission } from '../services/viewApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;

export interface ViewDesignerProps {
  /** 为空表示新建 */
  viewId?: string;
  onSaved?: (view: ExtendedObjectView) => void;
  onClose?: () => void;
}

interface ObjectTypeNode {
  object_type_id: string;
  name: string;
  properties: Array<{ name: string; data_type: string }>;
}

interface ViewField {
  field: string;
  label?: string;
  visible: boolean;
}

interface FilterRule { field: string; op: '=' | '!=' | '>' | '<' | 'contains'; value: string; }
interface SortRule { field: string; direction: 'asc' | 'desc'; }

export function ViewDesigner({ viewId, onSaved, onClose }: ViewDesignerProps) {
  const { t } = useI18n('ontology');
  const isCreate = !viewId;
  const [view, setView] = useState<ExtendedObjectView | null>(null);
  const [draftName, setDraftName] = useState('');
  const [saving, setSaving] = useState(false);
  const [objectTypes, setObjectTypes] = useState<ObjectTypeNode[]>([]);
  const [selectedObjectType, setSelectedObjectType] = useState<string | undefined>();
  const [fields, setFields] = useState<ViewField[]>([]);
  const [filters, setFilters] = useState<FilterRule[]>([]);
  const [sorts, setSorts] = useState<SortRule[]>([]);
  const [limit, setLimit] = useState<number>(100);
  const [permissions, setPermissions] = useState<ViewPermission[]>([]);
  const [previewRows, setPreviewRows] = useState<Array<Record<string, unknown>>>([]);
  const [previewing, setPreviewing] = useState(false);

  /**
   * 请求函数只做 I/O、不写状态。
   * 在 effect 里直接调用「内部会 setState 的函数」会在渲染阶段同步写状态，
   * 触发级联渲染（react-hooks/set-state-in-effect）；因此状态一律落到 promise
   * 回调里，并用 ignore 标记丢弃过期响应（切换视图 / 卸载后不再回写）。
   */
  const requestObjectTypes = useCallback(() => viewApi.listObjectTypes(), []);
  const requestView = useCallback((id: string) => viewApi.getView(id), []);

  const applyView = useCallback((data: ExtendedObjectView) => {
    setView(data);
    setDraftName(data.name);
    setSelectedObjectType(data.base_type_id);
    setFields(data.fields || []);
    setFilters(data.filters || []);
    setSorts(data.sorts || []);
    setLimit(data.limit || 100);
    setPermissions(data.permissions || []);
  }, []);

  // 详情加载中由「已加载的视图 id ≠ 当前 viewId」推导，不在 effect 里同步 setLoading(true)。
  // 新建模式（无 viewId）永远不加载，恒为 false。
  const [loadedViewId, setLoadedViewId] = useState<string | null>(null);
  const loading = !isCreate && loadedViewId !== viewId;

  useEffect(() => {
    let ignore = false;
    requestObjectTypes()
      .then((data) => { if (!ignore) setObjectTypes(data); })
      .catch((e: Error) => { if (!ignore) message.error(`${t('加载对象类型失败')}: ${e.message}`); });
    return () => { ignore = true; };
  }, [requestObjectTypes, t]);

  useEffect(() => {
    if (!viewId) return undefined;
    let ignore = false;
    requestView(viewId)
      .then((data) => { if (!ignore) applyView(data); })
      .catch((e: Error) => { if (!ignore) message.error(`${t('加载视图失败')}: ${e.message}`); })
      .finally(() => {
        // 失败也要落 id，否则 spinner 永久转
        if (!ignore) setLoadedViewId(viewId);
      });
    return () => { ignore = true; };
  }, [viewId, requestView, applyView, t]);  const treeData: DataNode[] = useMemo(
    () => objectTypes.map((o) => ({
      key: o.object_type_id,
      title: o.name,
      children: o.properties.map((p) => ({ key: `${o.object_type_id}.${p.name}`, title: `${p.name} (${p.data_type})`, isLeaf: true })),
    })),
    [objectTypes],
  );

  const candidates = useMemo(() => {
    const ot = objectTypes.find((o) => o.object_type_id === selectedObjectType);
    return ot ? ot.properties.map((p) => p.name) : [];
  }, [objectTypes, selectedObjectType]);

  const onAddField = useCallback((fieldName: string) => {
    setFields((prev) => {
      if (prev.some((f) => f.field === fieldName)) {
        message.warning(t('字段已存在'));
        return prev;
      }
      return [...prev, { field: fieldName, visible: true, label: fieldName }];
    });
  }, [t]);

  const onRemoveField = useCallback((field: string) => {
    setFields((prev) => prev.filter((f) => f.field !== field));
  }, []);

  const onAddFilter = useCallback(() => {
    setFilters((prev) => [...prev, { field: candidates[0] || '', op: '=', value: '' }]);
  }, [candidates]);

  const onAddSort = useCallback(() => {
    setSorts((prev) => [...prev, { field: candidates[0] || '', direction: 'asc' }]);
  }, [candidates]);

  const onPreview = useCallback(async () => {
    if (!view) return;
    setPreviewing(true);
    try {
      const data = await viewApi.queryView(view.id, { fields, filters, sorts, limit });
      setPreviewRows(data.rows || []);
    } catch (e) {
      message.error(`${t('查询失败')}: ${(e as Error).message}`);
    } finally {
      setPreviewing(false);
    }
  }, [view, fields, filters, sorts, limit, t]);

  const onSave = useCallback(async () => {
    const name = (draftName || view?.name || '').trim();
    if (!name) {
      message.warning(t('请填写视图名称'));
      return;
    }
    if (!selectedObjectType) {
      message.warning(t('请选择数据源类型'));
      return;
    }
    const projected = fields.filter((f) => f.visible).map((f) => f.field);
    const sortOrder = sorts.map((s) => ({ [s.field]: s.direction }));
    setSaving(true);
    try {
      if (view) {
        const updated = await viewApi.updateView(view.id, {
          name,
          base_type_id: selectedObjectType,
          fields,
          filters,
          sorts,
          limit,
          // permissions 不在本接口维护：见权限页签，权限走
          // POST /api/ontology/views/{id}/permissions（OPA role + redaction rules）
        });
        setView(updated);
        message.success(t('视图已保存'));
        onSaved?.(updated);
      } else {
        const createdRaw = await viewApi.create({
          name,
          base_type_id: selectedObjectType,
          // 视图归属角色：后端必填。设计器不越权代填，默认 viewer，
          // 交付给 permissions 接口再绑定更细的 OPA role。
          role: 'viewer',
          projected_properties: projected,
          filters,
          row_limit: limit,
          sort_order: sortOrder,
        });
        // create 返回原始报文，用 getView 拿统一后的扩展形态
        const created = await viewApi.getView(createdRaw.id);
        setView(created);
        message.success(t('视图已创建'));
        onSaved?.(created);
      }
    } catch (e) {
      message.error(`${t('保存失败')}: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [draftName, view, selectedObjectType, fields, filters, sorts, limit, onSaved, t]);

  const previewColumns: ColumnsType<Record<string, unknown>> = useMemo(
    () => fields.filter((f) => f.visible).map((f) => ({
      title: f.label || f.field,
      dataIndex: f.field,
      key: f.field,
      ellipsis: true,
    })),
    [fields],
  );

  return (
    <Card
      data-testid="view-designer"
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>
            {view ? t('视图设计器 — {{name}}', { name: view.name }) : t('新建视图')}
          </Title>
          {selectedObjectType && <Tag color="blue">{selectedObjectType}</Tag>}
        </Space>
      }
      extra={
        <Space>
          <Tooltip title={view ? undefined : t('保存后才能测试查询')}>
            <Button icon={<PlayCircleOutlined />} loading={previewing} disabled={!view} onClick={() => void onPreview()}>
              {t('测试查询')}
            </Button>
          </Tooltip>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void onSave()}>
            {t('保存')}
          </Button>
          {onClose && <Button onClick={onClose}>{t('关闭')}</Button>}
        </Space>
      }
      loading={loading}
    >
      {isCreate && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          title={t('新建视图：先选择数据源类型，再点击左侧字段加入视图，最后保存')}
        />
      )}
      <Row gutter={16}>
        <Col span={6}>
          <Card type="inner" title={t('对象类型树')} size="small">
            {treeData.length === 0 ? <Spin /> : (
              <Tree
                treeData={treeData}
                defaultExpandAll
                onSelect={(keys) => {
                  if (keys.length === 0) return;
                  const first = String(keys[0]);
                  if (first.includes('.')) {
                    onAddField(first.split('.')[1]);
                  } else {
                    setSelectedObjectType(first);
                  }
                }}
              />
            )}
            <Divider />
            <Alert type="info" showIcon title={t('点击字段添加到视图，点击对象类型切换数据源')} />
          </Card>
        </Col>
        <Col span={12}>
          <Card type="inner" title={t('视图配置')} size="small">
            <Space orientation="vertical" style={{ width: '100%' }} size="small">
              <Space style={{ width: '100%' }}>
                <Text>{t('视图名称')}</Text>
                <Input
                  aria-label={t('视图名称')}
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  placeholder={t('例如：订单明细视图')}
                  style={{ width: 280 }}
                />
              </Space>
              <Tabs
                defaultActiveKey="fields"
                items={[
                  {
                    key: 'fields', label: t('字段 ({{n}})', { n: fields.length }),
                    children: fields.length === 0 ? <Empty description={t('从左侧选择字段')} /> : (
                      <AdvancedTable
                        rowKey="field" size="small" pagination={false}
                        dataSource={fields.map((f) => ({ ...f, key: f.field }))}
                        columns={[
                          { title: t('字段'), dataIndex: 'field' },
                          { title: t('显示名'), dataIndex: 'label', render: (v: string, r: ViewField) => <Input aria-label={`${t('显示名')} ${r.field}`} size="small" value={v} onChange={(e) => setFields((p) => p.map((x) => x.field === r.field ? { ...x, label: e.target.value } : x))} /> },
                          { title: t('可见'), dataIndex: 'visible', width: 70, render: (v: boolean, r: ViewField) => <Switch size="small" checked={v} onChange={(c) => setFields((p) => p.map((x) => x.field === r.field ? { ...x, visible: c } : x))} /> },
                          { title: t('操作'), width: 70, render: (_: unknown, r: ViewField) => <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onRemoveField(r.field)} /> },
                        ]}
                      />
                    ),
                  },
                  {
                    key: 'filters', label: t('过滤 ({{n}})', { n: filters.length }),
                    children: (
                      <Space orientation="vertical" style={{ width: '100%' }}>
                        {filters.map((f, i) => (
                          <Space key={`${f.field}-${i}`}>
                            <Select size="small" style={{ width: 140 }} value={f.field} aria-label={t('过滤字段')} options={candidates.map((c) => ({ value: c, label: c }))} onChange={(v) => setFilters((p) => p.map((x, j) => j === i ? { ...x, field: v } : x))} />
                            <Select size="small" style={{ width: 90 }} value={f.op} aria-label={t('过滤算子')} options={['=', '!=', '>', '<', 'contains'].map((o) => ({ value: o, label: o }))} onChange={(v) => setFilters((p) => p.map((x, j) => j === i ? { ...x, op: v as FilterRule['op'] } : x))} />
                            <Input size="small" style={{ width: 160 }} aria-label={t('过滤值')} value={f.value} onChange={(e) => setFilters((p) => p.map((x, j) => j === i ? { ...x, value: e.target.value } : x))} />
                            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setFilters((p) => p.filter((_, j) => j !== i))} />
                          </Space>
                        ))}
                        <Button size="small" icon={<PlusOutlined />} onClick={onAddFilter}>{t('添加过滤')}</Button>
                      </Space>
                    ),
                  },
                  {
                    key: 'sorts', label: t('排序 ({{n}})', { n: sorts.length }),
                    children: (
                      <Space orientation="vertical" style={{ width: '100%' }}>
                        {sorts.map((s, i) => (
                          <Space key={`${s.field}-${i}`}>
                            <Select size="small" style={{ width: 160 }} value={s.field} aria-label={t('排序字段')} options={candidates.map((c) => ({ value: c, label: c }))} onChange={(v) => setSorts((p) => p.map((x, j) => j === i ? { ...x, field: v } : x))} />
                            <Select size="small" style={{ width: 90 }} value={s.direction} aria-label={t('排序方向')} options={[{ value: 'asc', label: 'ASC' }, { value: 'desc', label: 'DESC' }]} onChange={(v) => setSorts((p) => p.map((x, j) => j === i ? { ...x, direction: v as 'asc' | 'desc' } : x))} />
                            <Button size="small" icon={<ArrowUpOutlined />} onClick={() => setSorts((p) => { const a = [...p]; if (i > 0) [a[i - 1], a[i]] = [a[i], a[i - 1]]; return a; })} />
                            <Button size="small" icon={<ArrowDownOutlined />} onClick={() => setSorts((p) => { const a = [...p]; if (i < a.length - 1) [a[i + 1], a[i]] = [a[i], a[i + 1]]; return a; })} />
                            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setSorts((p) => p.filter((_, j) => j !== i))} />
                          </Space>
                        ))}
                        <Button size="small" icon={<PlusOutlined />} onClick={onAddSort}>{t('添加排序')}</Button>
                      </Space>
                    ),
                  },
                  {
                    key: 'limit', label: t('行数上限'),
                    children: (
                      <Space>
                        <Text>{t('行数限制')}</Text>
                        <InputNumber min={1} max={10000} value={limit} onChange={(v) => setLimit(v || 100)} aria-label={t('行数限制')} />
                      </Space>
                    ),
                  },
                  {
                    key: 'permissions', label: t('权限 ({{n}})', { n: permissions.length }),
                    children: (
                      <Alert
                        type="info"
                        showIcon
                        title={t('权限基于 OPA，绑定角色与脱敏规则')}
                        description={t('由 POST /api/ontology/views/{id}/permissions 维护')}
                      />
                    ),
                  },
                ]}
              />
            </Space>
          </Card>
        </Col>
        <Col span={6}>
          <Card type="inner" title={t('实时预览')} size="small">
            <Spin spinning={previewing}>
              {previewRows.length === 0 ? <Empty description={t('点击测试查询')} /> : (
                <AdvancedTable size="small" pagination={false} scroll={{ x: 'max-content' }} dataSource={previewRows.map((r, i) => ({ ...r, key: i }))} columns={previewColumns} />
              )}
            </Spin>
            <Divider />
            <Text type="secondary">{t('命中行数：{{n}}', { n: previewRows.length })}</Text>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}

export default ViewDesigner;
