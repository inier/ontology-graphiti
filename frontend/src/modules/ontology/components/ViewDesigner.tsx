/**
 * ViewDesigner 组件 —— 视图设计器（FR-036 / T413）
 *
 * 可视化三栏布局：
 *   - 左侧：ObjectType 树（选择数据源）
 *   - 中间：当前视图的"字段"+"过滤"+"排序"+"限制"+"权限"配置
 *   - 右侧：实时预览查询结果
 *
 * 顶部操作：保存 / 测试查询 / 删除
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tree, Form, Input, Select, Button, Space, Tabs, Tag, Empty, Spin, Drawer, message, Typography, Alert, InputNumber, Switch, Checkbox, Divider,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, DeleteOutlined, SaveOutlined, ReloadOutlined, PlayCircleOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons';
import { viewApi, type ObjectView, type ViewPermission } from '../services/viewApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;

export interface ViewDesignerProps {
  viewId: string;
  onSaved?: (view: ObjectView) => void;
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
  const { t } = useI18n();
  void t;
  const [view, setView] = useState<ObjectView | null>(null);
  const [loading, setLoading] = useState(false);
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

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await viewApi.listObjectTypes();
      setObjectTypes(data);
    } catch (e) {
      message.error(`加载 ObjectType 失败: ${(e as Error).message}`);
    }
  }, []);

  const fetchView = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const data = await viewApi.getView(id);
      setView(data);
      setSelectedObjectType(data.object_type_id);
      setFields(data.fields || []);
      setFilters(data.filters || []);
      setSorts(data.sorts || []);
      setLimit(data.limit || 100);
      setPermissions(data.permissions || []);
    } catch (e) {
      message.error(`加载视图失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchObjectTypes(); }, [fetchObjectTypes]);
  useEffect(() => { fetchView(viewId); }, [viewId, fetchView]);

  const treeData: DataNode[] = useMemo(
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
    if (fields.find((f) => f.field === fieldName)) {
      message.warning('字段已存在');
      return;
    }
    setFields((prev) => [...prev, { field: fieldName, visible: true, label: fieldName }]);
  }, [fields]);

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
      const data = await viewApi.queryView(view.id, {
        fields,
        filters,
        sorts,
        limit,
      });
      setPreviewRows(data.rows || []);
    } catch (e) {
      message.error(`查询失败: ${(e as Error).message}`);
    } finally {
      setPreviewing(false);
    }
  }, [view, fields, filters, sorts, limit]);

  const onSave = useCallback(async () => {
    if (!view) return;
    setSaving(true);
    try {
      const updated = await viewApi.updateView(view.id, {
        object_type_id: selectedObjectType,
        fields,
        filters,
        sorts,
        limit,
        permissions,
      });
      setView(updated);
      message.success('视图已保存');
      onSaved?.(updated);
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [view, selectedObjectType, fields, filters, sorts, limit, permissions, onSaved]);

  const previewColumns: ColumnsType<Record<string, unknown>> = useMemo(() => {
    return fields.filter((f) => f.visible).map((f) => ({
      title: f.label || f.field,
      dataIndex: f.field,
      key: f.field,
      ellipsis: true,
    }));
  }, [fields]);

  return (
    <Card
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>视图设计器 — {view?.name || viewId}</Title>
          {selectedObjectType && <Tag color="blue">{selectedObjectType}</Tag>}
        </Space>
      }
      extra={
        <Space>
          <Button icon={<PlayCircleOutlined />} loading={previewing} onClick={onPreview}>测试查询</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>保存</Button>
          {onClose && <Button onClick={onClose}>关闭</Button>}
        </Space>
      }
      loading={loading}
    >
      <Row gutter={16}>
        <Col span={6}>
          <Card type="inner" title="ObjectType 树" size="small">
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
            <Alert type="info" showIcon message="点击字段添加到视图，点击 ObjectType 切换数据源" />
          </Card>
        </Col>
        <Col span={12}>
          <Card type="inner" title="视图配置" size="small">
            <Tabs
              defaultActiveKey="fields"
              items={[
                {
                  key: 'fields', label: `字段 (${fields.length})`,
                  children: fields.length === 0 ? <Empty description="从左侧选择字段" /> : (
                    <AdvancedTable
                      rowKey="field" size="small" pagination={false}
                      dataSource={fields.map((f) => ({ ...f, key: f.field }))}
                      columns={[
                        { title: '字段', dataIndex: 'field' },
                        { title: '显示名', dataIndex: 'label', render: (v: string, r: ViewField) => <Input size="small" value={v} onChange={(e) => setFields((p) => p.map((x) => x.field === r.field ? { ...x, label: e.target.value } : x))} /> },
                        { title: '可见', dataIndex: 'visible', width: 70, render: (v: boolean, r: ViewField) => <Switch size="small" checked={v} onChange={(c) => setFields((p) => p.map((x) => x.field === r.field ? { ...x, visible: c } : x))} /> },
                        { title: '操作', width: 70, render: (_: unknown, r: ViewField) => <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onRemoveField(r.field)} /> },
                      ]}
                    />
                  ),
                },
                {
                  key: 'filters', label: `过滤 (${filters.length})`,
                  children: (
                    <Space orientation="vertical" style={{ width: '100%' }}>
                      {filters.map((f, i) => (
                        <Space key={i}>
                          <Select size="small" style={{ width: 140 }} value={f.field} options={candidates.map((c) => ({ value: c, label: c }))} onChange={(v) => setFilters((p) => p.map((x, j) => j === i ? { ...x, field: v } : x))} />
                          <Select size="small" style={{ width: 90 }} value={f.op} options={['=', '!=', '>', '<', 'contains'].map((o) => ({ value: o, label: o }))} onChange={(v) => setFilters((p) => p.map((x, j) => j === i ? { ...x, op: v as FilterRule['op'] } : x))} />
                          <Input size="small" style={{ width: 160 }} value={f.value} onChange={(e) => setFilters((p) => p.map((x, j) => j === i ? { ...x, value: e.target.value } : x))} />
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setFilters((p) => p.filter((_, j) => j !== i))} />
                        </Space>
                      ))}
                      <Button size="small" icon={<PlusOutlined />} onClick={onAddFilter}>添加过滤</Button>
                    </Space>
                  ),
                },
                {
                  key: 'sorts', label: `排序 (${sorts.length})`,
                  children: (
                    <Space orientation="vertical" style={{ width: '100%' }}>
                      {sorts.map((s, i) => (
                        <Space key={i}>
                          <Select size="small" style={{ width: 160 }} value={s.field} options={candidates.map((c) => ({ value: c, label: c }))} onChange={(v) => setSorts((p) => p.map((x, j) => j === i ? { ...x, field: v } : x))} />
                          <Select size="small" style={{ width: 90 }} value={s.direction} options={[{ value: 'asc', label: 'ASC' }, { value: 'desc', label: 'DESC' }]} onChange={(v) => setSorts((p) => p.map((x, j) => j === i ? { ...x, direction: v as 'asc' | 'desc' } : x))} />
                          <Button size="small" icon={<ArrowUpOutlined />} onClick={() => setSorts((p) => { const a = [...p]; if (i > 0) [a[i-1], a[i]] = [a[i], a[i-1]]; return a; })} />
                          <Button size="small" icon={<ArrowDownOutlined />} onClick={() => setSorts((p) => { const a = [...p]; if (i < a.length - 1) [a[i+1], a[i]] = [a[i], a[i+1]]; return a; })} />
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setSorts((p) => p.filter((_, j) => j !== i))} />
                        </Space>
                      ))}
                      <Button size="small" icon={<PlusOutlined />} onClick={onAddSort}>添加排序</Button>
                    </Space>
                  ),
                },
                {
                  key: 'limit', label: 'Limit',
                  children: (
                    <Space>
                      <Text>行数限制:</Text>
                      <InputNumber min={1} max={10000} value={limit} onChange={(v) => setLimit(v || 100)} />
                    </Space>
                  ),
                },
                {
                  key: 'permissions', label: `权限 (${permissions.length})`,
                  children: (
                    <Alert type="info" showIcon message="权限基于 OPA，绑定 role + redaction rules" description="后端 POST /api/ontology/views/{id}/permissions 维护" />
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card type="inner" title="实时预览" size="small">
            <Spin spinning={previewing}>
              {previewRows.length === 0 ? <Empty description="点击'测试查询'" /> : (
                <AdvancedTable size="small" pagination={false} scroll={{ x: 'max-content' }} dataSource={previewRows.map((r, i) => ({ ...r, key: i }))} columns={previewColumns} />
              )}
            </Spin>
            <Divider />
            <Space>
              <Text type="secondary">命中行数: {previewRows.length}</Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}

export default ViewDesigner;
