/**
 * ComputedPropertyEditor 组件 —— 计算属性编辑器（FR-035 / T400）
 *
 * 三段式布局：
 *   - 顶部：ObjectType + Property Name + Return Type
 *   - 中部：表达式编辑器（多行 TextArea）+ 实时依赖解析（AST-like）
 *   - 右侧：依赖列表 + 已选/未选字段候选
 *   - 底部：测试按钮（基于示例数据求值）+ 错误展示 + 保存
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Form, Input, Select, Button, Space, Typography, Tag, Alert, List, Switch, message, Empty, Spin,
} from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;
const { TextArea } = Input;

export interface ComputedPropertyEditorProps {
  workspaceId?: string;
  propertyId?: string;
  onSaved?: (propertyId: string) => void;
}

interface ComputedFormValues {
  name: string;
  object_type_id: string;
  return_type: 'number' | 'string' | 'boolean' | 'date';
  expression: string;
  materialized: boolean;
  description?: string;
}

interface ObjectTypeSummary {
  object_type_id: string;
  name: string;
  properties: Array<{ name: string; data_type: string }>;
}

function extractDependencies(expr: string, candidates: string[]): string[] {
  const found = new Set<string>();
  for (const c of candidates) {
    const re = new RegExp(`\\b${c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
    if (re.test(expr)) found.add(c);
  }
  return Array.from(found);
}

export function ComputedPropertyEditor({ workspaceId, propertyId, onSaved }: ComputedPropertyEditorProps) {
  const { t } = useI18n();
  void t;
  const [form] = Form.useForm<ComputedFormValues>();
  const [objectTypes, setObjectTypes] = useState<ObjectTypeSummary[]>([]);
  const [objectTypeId, setObjectTypeId] = useState<string | undefined>();
  const [expression, setExpression] = useState<string>('count(properties)');
  const [testResult, setTestResult] = useState<{ value: unknown; duration_ms: number } | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await apiClient.get<{ object_types: ObjectTypeSummary[] }>('/api/ontology/object-types');
      setObjectTypes(data.object_types || []);
    } catch (e) {
      message.error(`加载 ObjectType 失败: ${(e as Error).message}`);
    }
  }, []);

  const fetchProperty = useCallback(async (id: string) => {
    try {
      const data = await apiClient.get<{ property: ComputedFormValues & { id: string } }>(`/api/ontology/computed/${id}`);
      const p = data.property;
      form.setFieldsValue({
        name: p.name,
        object_type_id: p.object_type_id,
        return_type: p.return_type,
        expression: p.expression,
        materialized: p.materialized,
        description: p.description,
      });
      setObjectTypeId(p.object_type_id);
      setExpression(p.expression);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    }
  }, [form]);

  useEffect(() => { fetchObjectTypes(); }, [fetchObjectTypes]);
  useEffect(() => { if (propertyId) fetchProperty(propertyId); }, [propertyId, fetchProperty]);

  const candidateProps = useMemo(() => {
    const ot = objectTypes.find((o) => o.object_type_id === objectTypeId);
    return ot ? ot.properties.map((p) => p.name) : [];
  }, [objectTypeId, objectTypes]);

  const deps = useMemo(() => extractDependencies(expression, candidateProps), [expression, candidateProps]);

  const onTest = useCallback(async () => {
    setTesting(true);
    setError(null);
    try {
      const data = await apiClient.post<{ value: unknown; duration_ms: number }>(
        '/api/ontology/computed/test',
        { expression, object_type_id: objectTypeId, workspace_id: workspaceId },
      );
      setTestResult(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTesting(false);
    }
  }, [expression, objectTypeId, workspaceId]);

  const onSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = { ...values, workspace_id: workspaceId, dependencies: deps };
      const data = await apiClient.post<{ property_id: string }>('/api/ontology/computed', payload);
      message.success(`已保存: ${data.property_id}`);
      onSaved?.(data.property_id);
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) {
        message.error('请检查必填字段');
      } else {
        message.error(`保存失败: ${(e as Error).message}`);
      }
    } finally {
      setSaving(false);
    }
  }, [form, deps, workspaceId, onSaved]);

  const onReset = useCallback(() => {
    form.resetFields();
    setExpression('count(properties)');
    setObjectTypeId(undefined);
    setTestResult(null);
    setError(null);
  }, [form]);

  return (
    <Card
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>{propertyId ? `编辑计算属性 ${propertyId}` : '新建计算属性'}</Title>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<PlayCircleOutlined />} loading={testing} onClick={onTest}>测试</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>保存</Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" initialValues={{ return_type: 'number', materialized: false }}>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item label="ObjectType" name="object_type_id" rules={[{ required: true }]}>
              <Select
                placeholder="选择 ObjectType"
                options={objectTypes.map((o) => ({ value: o.object_type_id, label: o.name }))}
                onChange={(v) => setObjectTypeId(v)}
                showSearch
                optionFilterProp="label"
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="Property Name" name="name" rules={[{ required: true, pattern: /^[a-z_][a-z0-9_]*$/, message: '小写字母+下划线' }]}>
              <Input placeholder="total_amount" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="Return Type" name="return_type" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: 'number', label: 'Number' },
                  { value: 'string', label: 'String' },
                  { value: 'boolean', label: 'Boolean' },
                  { value: 'date', label: 'Date' },
                ]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={14}>
            <Form.Item label="Expression" name="expression" rules={[{ required: true }]}>
              <TextArea
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                autoSize={{ minRows: 6, maxRows: 14 }}
                style={{ fontFamily: 'Menlo, Consolas, monospace', fontSize: 13 }}
                placeholder="count(properties) * unit_price"
              />
            </Form.Item>
            <Form.Item label="Materialized" name="materialized" valuePropName="checked">
              <Switch checkedChildren="ON" unCheckedChildren="OFF" />
            </Form.Item>
            <Form.Item label="Description" name="description">
              <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="可选说明" />
            </Form.Item>
          </Col>
          <Col span={10}>
            <Card type="inner" title="依赖字段（AST 解析）" size="small">
              {candidateProps.length === 0 ? (
                <Empty description="请先选择 ObjectType" />
              ) : (
                <List
                  size="small"
                  dataSource={candidateProps}
                  renderItem={(p) => {
                    const used = deps.includes(p);
                    return (
                      <List.Item style={{ padding: '6px 0' }}>
                        <Space>
                          <Tag color={used ? 'green' : 'default'}>{used ? <CheckCircleOutlined /> : <CloseCircleOutlined />}</Tag>
                          <Text code>{p}</Text>
                        </Space>
                      </List.Item>
                    );
                  }}
                />
              )}
              {deps.length > 0 && (
                <Alert
                  style={{ marginTop: 8 }}
                  type="success"
                  showIcon
                  message={`已解析 ${deps.length} 个依赖`}
                  description={deps.join(', ')}
                />
              )}
            </Card>
          </Col>
        </Row>
      </Form>

      <Card type="inner" title="测试结果" size="small" style={{ marginTop: 12 }}>
        <Spin spinning={testing}>
          {error ? (
            <Alert type="error" showIcon message="求值失败" description={error} />
          ) : testResult ? (
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Text>结果: <Text code>{JSON.stringify(testResult.value)}</Text></Text>
              <Text type="secondary">耗时: {testResult.duration_ms} ms</Text>
            </Space>
          ) : (
            <Empty description="点击'测试'按钮以执行表达式" />
          )}
        </Spin>
      </Card>
    </Card>
  );
}

export default ComputedPropertyEditor;
