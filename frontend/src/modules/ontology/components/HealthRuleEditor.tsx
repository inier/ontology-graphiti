/**
 * HealthRuleEditor 组件 —— 数据健康规则 YAML 编辑器（FR-031 / T345）
 *
 * 左侧：YAML 源码编辑器（Monaco-style TextArea，带行号 / 语法高亮模拟）
 * 右侧：实时解析结果 + 字段表单（id / name / description / severity）
 * 底部：实时校验状态（OK / 错误信息），保存按钮
 *
 * 表达式格式示例（DSL）:
 *   rule_id: r-001
 *   name: "资产覆盖率"
 *   object_type: Asset
 *   severity: HIGH
 *   expression: "count(properties) >= 5"
 *
 * 校验逻辑：
 *  - 解析 key=value 行
 *  - 校验 severity ∈ LOW/MEDIUM/HIGH/CRITICAL
 *  - 校验 expression 非空且括号平衡
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Input, Select, Button, Space, Typography, Form, Tag, message, Alert, Divider, Empty,
} from 'antd';
import {
  SaveOutlined, ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;
const { TextArea } = Input;

export interface HealthRuleEditorProps {
  workspaceId?: string;
  ruleId?: string;
  onSaved?: (ruleId: string) => void;
}

type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

interface RuleFormValues {
  rule_id: string;
  name: string;
  description: string;
  object_type: string;
  severity: Severity;
  expression: string;
}

const DEFAULT_TEMPLATE = `# 数据健康规则（YAML / DSL）
# 保存后自动注册到健康扫描器
rule_id: r-new-001
name: "新规则"
description: "请描述规则用途"
object_type: Asset
severity: MEDIUM
expression: "count(properties) >= 1"
`;

const SEVERITY_OPTIONS: Array<{ value: Severity; label: string; color: string }> = [
  { value: 'LOW', label: 'LOW', color: 'blue' },
  { value: 'MEDIUM', label: 'MEDIUM', color: 'gold' },
  { value: 'HIGH', label: 'HIGH', color: 'orange' },
  { value: 'CRITICAL', label: 'CRITICAL', color: 'red' },
];

function validateYaml(source: string): { ok: boolean; errors: string[]; values?: RuleFormValues } {
  const errors: string[] = [];
  const values: Partial<RuleFormValues> = {};
  if (!source.trim()) {
    return { ok: false, errors: ['内容为空'], values: undefined };
  }
  for (const line of source.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const colonIdx = trimmed.indexOf(':');
    if (colonIdx === -1) {
      errors.push(`格式错误行: ${line}`);
      continue;
    }
    const key = trimmed.slice(0, colonIdx).trim();
    let value = trimmed.slice(colonIdx + 1).trim();
    if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
    if (key === 'rule_id') values.rule_id = value;
    else if (key === 'name') values.name = value;
    else if (key === 'description') values.description = value;
    else if (key === 'object_type') values.object_type = value;
    else if (key === 'severity') values.severity = value as Severity;
    else if (key === 'expression') values.expression = value;
  }
  if (!values.rule_id) errors.push('缺少 rule_id');
  if (!values.name) errors.push('缺少 name');
  if (!values.object_type) errors.push('缺少 object_type');
  if (!values.severity) errors.push('缺少 severity');
  else if (!['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(values.severity)) errors.push('severity 非法');
  if (!values.expression) errors.push('缺少 expression');
  else {
    let depth = 0;
    for (const c of values.expression) {
      if (c === '(') depth += 1;
      else if (c === ')') depth -= 1;
      if (depth < 0) {
        errors.push('expression 括号不匹配');
        break;
      }
    }
    if (depth !== 0) errors.push('expression 括号不匹配');
  }
  return { ok: errors.length === 0, errors, values: values as RuleFormValues };
}

export function HealthRuleEditor({ workspaceId, ruleId, onSaved }: HealthRuleEditorProps) {
  const { t } = useI18n();
  void t;
  const [source, setSource] = useState<string>(DEFAULT_TEMPLATE);
  const [form] = Form.useForm<RuleFormValues>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorCount, setErrorCount] = useState(0);

  const validation = useMemo(() => validateYaml(source), [source]);

  const fetchRule = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ rule: { yaml: string } }>(`/api/ontology/health/rules/${id}`);
      setSource(data.rule?.yaml || DEFAULT_TEMPLATE);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ruleId) fetchRule(ruleId);
  }, [ruleId, fetchRule]);

  useEffect(() => {
    if (validation.values) form.setFieldsValue(validation.values);
    setErrorCount(validation.errors.length);
  }, [validation, form]);

  const onSave = useCallback(async () => {
    if (!validation.ok) {
      message.error('请先修复校验错误');
      return;
    }
    setSaving(true);
    try {
      const payload = { yaml: source, workspace_id: workspaceId };
      const data = await apiClient.post<{ rule_id: string }>('/api/ontology/health/rules', payload);
      message.success(`规则已保存: ${data.rule_id}`);
      onSaved?.(data.rule_id);
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [source, validation, workspaceId, onSaved]);

  const onValidate = useCallback(() => {
    if (validation.ok) message.success('校验通过');
    else message.error(`发现 ${validation.errors.length} 处错误`);
  }, [validation]);

  const onReset = useCallback(() => {
    setSource(DEFAULT_TEMPLATE);
    form.resetFields();
    message.info('已重置');
  }, [form]);

  return (
    <Card
      title={
        <Space>
          <ThunderboltOutlined />
          <Title level={5} style={{ margin: 0 }}>{ruleId ? `编辑规则 ${ruleId}` : '新建数据健康规则'}</Title>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<ThunderboltOutlined />} onClick={onValidate}>校验</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave} disabled={!validation.ok}>
            保存
          </Button>
        </Space>
      }
      loading={loading}
    >
      <Row gutter={16}>
        <Col span={14}>
          <Card type="inner" title="YAML / DSL 源码" size="small">
            <TextArea
              value={source}
              onChange={(e) => setSource(e.target.value)}
              autoSize={{ minRows: 14, maxRows: 26 }}
              style={{ fontFamily: 'Menlo, Consolas, monospace', fontSize: 13 }}
              spellCheck={false}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card type="inner" title="结构化表单（自动同步）" size="small">
            <Form
              form={form}
              layout="vertical"
              initialValues={validation.values}
              onValuesChange={(_, all) => {
                const lines = [
                  `rule_id: ${all.rule_id || ''}`,
                  `name: "${all.name || ''}"`,
                  `description: "${all.description || ''}"`,
                  `object_type: ${all.object_type || ''}`,
                  `severity: ${all.severity || 'MEDIUM'}`,
                  `expression: "${all.expression || ''}"`,
                ];
                setSource(lines.join('\n'));
              }}
            >
              <Form.Item label="Rule ID" name="rule_id" rules={[{ required: true, message: '请输入 ID' }]}>
                <Input placeholder="r-001" />
              </Form.Item>
              <Form.Item label="Name" name="name" rules={[{ required: true, message: '请输入名称' }]}>
                <Input placeholder="规则名称" />
              </Form.Item>
              <Form.Item label="Description" name="description">
                <Input placeholder="可选描述" />
              </Form.Item>
              <Form.Item label="Object Type" name="object_type" rules={[{ required: true, message: '请输入 ObjectType' }]}>
                <Input placeholder="Asset" />
              </Form.Item>
              <Form.Item label="Severity" name="severity" rules={[{ required: true }]}>
                <Select options={SEVERITY_OPTIONS.map((o) => ({ value: o.value, label: <Tag color={o.color}>{o.label}</Tag> }))} />
              </Form.Item>
              <Form.Item label="Expression" name="expression" rules={[{ required: true, message: '请输入表达式' }]}>
                <TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder="count(properties) >= 5" />
              </Form.Item>
            </Form>
          </Card>
          <Divider />
          {validation.ok ? (
            <Alert
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              message="表达式解析通过"
              description="已就绪，可点击保存"
            />
          ) : (
            <Alert
              type="error"
              showIcon
              icon={<CloseCircleOutlined />}
              message={`发现 ${errorCount} 处错误`}
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {validation.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              }
            />
          )}
        </Col>
      </Row>
      {Object.keys(validation.values || {}).length === 0 && (
        <Empty description="请填写规则字段" style={{ marginTop: 12 }} />
      )}
    </Card>
  );
}

export default HealthRuleEditor;
