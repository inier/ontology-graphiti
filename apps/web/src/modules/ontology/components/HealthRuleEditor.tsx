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
  Card, Row, Col, Input, Select, Button, Space, Typography, Tag, message, Alert, Divider, Empty,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
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

export function HealthRuleEditor({ workspaceId, ruleId, onSaved }: HealthRuleEditorProps) {
  const { t } = useI18n('ontology');
  const [source, setSource] = useState<string>('');
  const [form] = Form.useForm<RuleFormValues>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorCount, setErrorCount] = useState(0);

  const DEFAULT_TEMPLATE = useMemo(
    () => `# 数据健康规则（YAML / DSL）
# 保存后自动注册到健康扫描器
rule_id: r-new-001
name: "新规则"
description: "请描述规则用途"
object_type: Asset
severity: MEDIUM
expression: "count(properties) >= 1"
`,
    [],
  );

  const SEVERITY_OPTIONS: Array<{ value: Severity; label: string; color: string }> = useMemo(() => [
    { value: 'LOW', label: 'LOW', color: 'blue' },
    { value: 'MEDIUM', label: 'MEDIUM', color: 'gold' },
    { value: 'HIGH', label: 'HIGH', color: 'orange' },
    { value: 'CRITICAL', label: 'CRITICAL', color: 'red' },
  ], []);

  const validateYaml = useCallback((src: string): { ok: boolean; errors: string[]; values?: RuleFormValues } => {
    const errors: string[] = [];
    const values: Partial<RuleFormValues> = {};
    if (!src.trim()) {
      return { ok: false, errors: [t('healthRule.yamlErrorEmpty')], values: undefined };
    }
    for (const line of src.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const colonIdx = trimmed.indexOf(':');
      if (colonIdx === -1) {
        errors.push(t('healthRule.yamlErrorLine', { line }));
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
    if (!values.rule_id) errors.push(t('healthRule.yamlErrorMissingRuleId'));
    if (!values.name) errors.push(t('healthRule.yamlErrorMissingName'));
    if (!values.object_type) errors.push(t('healthRule.yamlErrorMissingObjectType'));
    if (!values.severity) errors.push(t('healthRule.yamlErrorMissingSeverity'));
    else if (!['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(values.severity)) errors.push(t('healthRule.yamlErrorInvalidSeverity'));
    if (!values.expression) errors.push(t('healthRule.yamlErrorMissingExpression'));
    else {
      let depth = 0;
      for (const c of values.expression) {
        if (c === '(') depth += 1;
        else if (c === ')') depth -= 1;
        if (depth < 0) {
          errors.push(t('healthRule.yamlErrorParentheses'));
          break;
        }
      }
      if (depth !== 0) errors.push(t('healthRule.yamlErrorParentheses'));
    }
    return { ok: errors.length === 0, errors, values: values as RuleFormValues };
  }, [t]);

  const validation = useMemo(() => validateYaml(source), [source, validateYaml]);

  const fetchRule = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ rule: { yaml: string } }>(`/api/ontology/health/rules/${id}`);
      setSource(data.rule?.yaml || DEFAULT_TEMPLATE);
    } catch (e) {
      message.error(t('healthRule.loadFailed', { msg: (e as Error).message }));
    } finally {
      setLoading(false);
    }
  }, [t, DEFAULT_TEMPLATE]);

  useEffect(() => {
    if (!source) setSource(DEFAULT_TEMPLATE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      message.error(t('healthRule.fixErrorsFirst'));
      return;
    }
    setSaving(true);
    try {
      const payload = { yaml: source, workspace_id: workspaceId };
      const data = await apiClient.post<{ rule_id: string }>('/api/ontology/health/rules', payload);
      message.success(t('healthRule.saved', { id: data.rule_id }));
      onSaved?.(data.rule_id);
    } catch (e) {
      message.error(t('healthRule.saveFailed', { msg: (e as Error).message }));
    } finally {
      setSaving(false);
    }
  }, [source, validation, workspaceId, onSaved, t]);

  const onValidate = useCallback(() => {
    if (validation.ok) message.success(t('healthRule.validatePass'));
    else message.error(t('healthRule.errorsFound', { count: validation.errors.length }));
  }, [validation, t]);

  const onReset = useCallback(() => {
    setSource(DEFAULT_TEMPLATE);
    form.resetFields();
    message.info(t('healthRule.resetSuccess'));
  }, [form, t, DEFAULT_TEMPLATE]);

  return (
    <Card
      title={
        <Space>
          <ThunderboltOutlined />
          <Title level={5} style={{ margin: 0 }}>{ruleId ? t('healthRule.editRule', { id: ruleId }) : t('healthRule.newHealthRule')}</Title>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset}>{t('healthRule.reset')}</Button>
          <Button icon={<ThunderboltOutlined />} onClick={onValidate}>{t('healthRule.validate')}</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave} disabled={!validation.ok}>
            {t('healthRule.save')}
          </Button>
        </Space>
      }
      loading={loading}
    >
      <Row gutter={16}>
        <Col span={14}>
          <Card type="inner" title={t('healthRule.yamlSource')} size="small">
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
          <Card type="inner" title={t('healthRule.structuredForm')} size="small">
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
              <Form.Item label={t('healthRule.ruleIdLabel')} name="rule_id" rules={[{ required: true, message: t('healthRule.ruleIdRequired') }]}>
                <Input placeholder={t('healthRule.ruleIdPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('healthRule.nameLabel')} name="name" rules={[{ required: true, message: t('healthRule.nameRequired') }]}>
                <Input placeholder={t('healthRule.namePlaceholder')} />
              </Form.Item>
              <Form.Item label={t('healthRule.descriptionLabel')} name="description">
                <Input placeholder={t('healthRule.descriptionPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('healthRule.objectTypeLabel')} name="object_type" rules={[{ required: true, message: t('healthRule.objectTypeRequired') }]}>
                <Input placeholder={t('healthRule.objectTypePlaceholder')} />
              </Form.Item>
              <Form.Item label={t('healthRule.severityLabel')} name="severity" rules={[{ required: true }]}>
                <Select options={SEVERITY_OPTIONS.map((o) => ({ value: o.value, label: <Tag color={o.color}>{o.label}</Tag> }))} />
              </Form.Item>
              <Form.Item label={t('healthRule.expressionLabel')} name="expression" rules={[{ required: true, message: t('healthRule.expressionRequired') }]}>
                <TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder={t('healthRule.expressionPlaceholder')} />
              </Form.Item>
            </Form>
          </Card>
          <Divider />
          {validation.ok ? (
            <Alert
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              title={t('healthRule.parsePass')}
              description={t('healthRule.parsePassDesc')}
            />
          ) : (
            <Alert
              type="error"
              showIcon
              icon={<CloseCircleOutlined />}
              title={t('healthRule.errorsFoundCount', { count: errorCount })}
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
        <Empty description={t('healthRule.fillFields')} style={{ marginTop: 12 }} />
      )}
    </Card>
  );
}

export default HealthRuleEditor;
