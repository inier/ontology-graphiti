/**
 * HealthDashboardPage —— 本体数据质量健康度（规则 / 扫描 / 报告）
 *
 * 契约来源（全部经后端 `odap/biz/core/ontology/health/api/routes.py` 核对）：
 *   GET    /api/ontology/health/rules?enabled_only&target_type_id&severity
 *          → { rules: HealthRule[], count }
 *   POST   /api/ontology/health/rules       body: CreateHealthRuleRequest
 *   PUT    /api/ontology/health/rules/{id}  body: UpdateHealthRuleRequest（字段全可选）
 *   DELETE /api/ontology/health/rules/{id}
 *   POST   /api/ontology/health/scan        body: { rule_id?: string } → ScanResponse
 *          → { scanned_count, pass_count, warn_count, fail_count, reports[] }
 *   GET    /api/ontology/health/reports?status&severity&target_type_id&limit&offset
 *          → { reports: HealthReport[], count, total, limit, offset }
 *
 * 与旧实现的三处关键差异（旧实现是契约虚构，必然失败）：
 *  1. 规则主键是 `id`，不是 `rule_id`；
 *  2. 规则本身**不带** `status` / `failure_count` / `last_checked_at`——状态在「报告」维度，
 *     旧实现把报告字段挂到规则上，表格永远空白；
 *  3. 没有 `POST /rules/{id}/scan` 与 `GET /rules/{id}/violations`：单规则扫描走
 *     `POST /scan {rule_id}`，违规明细走 `GET /reports?rule_id=...`（报告列表按 rule_id 过滤在前端完成）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Button, Card, Col, Drawer, Empty, Form, Input, Popconfirm, Row, Select,
  Space, Spin, Statistic, Switch, Table, Tabs, Tag, Typography, message,
} from 'antd';
import {
  CheckCircleTwoTone, CloseCircleTwoTone, MinusCircleTwoTone, PlusOutlined,
  ReloadOutlined, ThunderboltOutlined, WarningTwoTone,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;

type ReportStatus = 'PASS' | 'FAIL' | 'WARN' | 'SKIP';

/** 后端 HealthRuleResponse */
interface HealthRule {
  id: string;
  target_type_id: string;
  name: string;
  description: string;
  rule_type: string;
  check_expression: Record<string, unknown>;
  severity: string;
  schedule: string;
  notification_channel: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** 后端 HealthReportResponse */
interface HealthReport {
  id: string;
  rule_id: string;
  instance_id: string;
  target_type_id: string;
  status: string;
  severity: string;
  message: string;
  details: Record<string, unknown>;
  scanned_at: string;
}

interface ScanResponse {
  scanned_count: number;
  pass_count: number;
  warn_count: number;
  fail_count: number;
  rule_id?: string | null;
  reports: HealthReport[];
}

interface RuleFormValues {
  name: string;
  target_type_id: string;
  description?: string;
  rule_type: string;
  severity: string;
  schedule?: string;
  check_expression: string;
  enabled: boolean;
}

const SEVERITIES = ['info', 'warning', 'error', 'critical'] as const;

const STATUS_META: Record<ReportStatus, { icon: React.ReactNode; color: string }> = {
  PASS: { icon: <CheckCircleTwoTone twoToneColor="#52c41a" />, color: 'success' },
  FAIL: { icon: <CloseCircleTwoTone twoToneColor="#f5222d" />, color: 'error' },
  WARN: { icon: <WarningTwoTone twoToneColor="#faad14" />, color: 'warning' },
  SKIP: { icon: <MinusCircleTwoTone />, color: 'default' },
};

/** 把后端的报错原样暴露出来：静默失败比报错更难排查 */
function reasonOf(e: unknown): string {
  const err = e as { message?: string; status?: number; detail?: string };
  if (err?.detail) return err.detail;
  if (err?.status && err?.message) return `HTTP ${err.status}：${err.message}`;
  return err?.message ?? String(e);
}

export function HealthDashboardPage() {
  const { t } = useI18n('ontology');

  const [rules, setRules] = useState<HealthRule[]>([]);
  const [reports, setReports] = useState<HealthReport[]>([]);
  const [objectTypes, setObjectTypes] = useState<Array<{ type_id: string; name: string }>>([]);

  // 加载态用「已完成请求的 token ≠ 当前 token」推导，避免在 effect 内同步写 state
  const [reloadToken, setReloadToken] = useState(0);
  const [doneToken, setDoneToken] = useState(-1);
  const loading = doneToken !== reloadToken;

  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string>('');

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<RuleFormValues>();

  /* ── 拉取规则 + 报告 + 对象类型（三者互不阻塞） ── */
  useEffect(() => {
    const token = reloadToken;
    let ignore = false;
    Promise.all([
      apiClient.get<{ rules: HealthRule[] }>('/api/ontology/health/rules'),
      apiClient.get<{ reports: HealthReport[] }>('/api/ontology/health/reports?limit=200'),
      apiClient
        .get<Array<{ type_id: string; name: string }>>('/api/ontology/oms/object-types')
        .catch(() => [] as Array<{ type_id: string; name: string }>),
    ])
      .then(([ruleRes, reportRes, typeRes]) => {
        if (ignore) return;
        setRules(ruleRes.rules ?? []);
        setReports(reportRes.reports ?? []);
        setObjectTypes(Array.isArray(typeRes) ? typeRes : []);
        setError('');
      })
      .catch((e) => {
        if (!ignore) setError(reasonOf(e));
      })
      .finally(() => {
        if (!ignore) setDoneToken(token);
      });
    return () => {
      ignore = true;
    };
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  /* ── 扫描：单规则或全部 ── */
  const runScan = useCallback(
    async (ruleId?: string) => {
      setScanning(true);
      try {
        const res = await apiClient.post<ScanResponse>(
          '/api/ontology/health/scan',
          ruleId ? { rule_id: ruleId } : {},
        );
        setLastScan(res);
        message.success(
          t('扫描完成：共 {{total}} 项，通过 {{pass}}，告警 {{warn}}，失败 {{fail}}', {
            total: res.scanned_count,
            pass: res.pass_count,
            warn: res.warn_count,
            fail: res.fail_count,
          }),
        );
        reload();
      } catch (e) {
        message.error(`${t('扫描失败')}：${reasonOf(e)}`);
      } finally {
        setScanning(false);
      }
    },
    [reload, t],
  );

  /* ── 规则 CRUD ── */
  const openCreate = useCallback(() => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      rule_type: 'not_null',
      severity: 'warning',
      enabled: true,
      check_expression: '{}',
    });
    setEditorOpen(true);
  }, [form]);

  const openEdit = useCallback(
    (rule: HealthRule) => {
      setEditingId(rule.id);
      form.setFieldsValue({
        name: rule.name,
        target_type_id: rule.target_type_id,
        description: rule.description,
        rule_type: rule.rule_type,
        severity: rule.severity,
        schedule: rule.schedule,
        check_expression: JSON.stringify(rule.check_expression ?? {}, null, 2),
        enabled: rule.enabled,
      });
      setEditorOpen(true);
    },
    [form],
  );

  const submit = useCallback(async () => {
    const values = await form.validateFields();
    let expression: Record<string, unknown>;
    try {
      expression = JSON.parse(values.check_expression || '{}');
    } catch (e) {
      message.error(`${t('检查表达式不是合法 JSON')}：${reasonOf(e)}`);
      return;
    }
    const payload = {
      name: values.name,
      target_type_id: values.target_type_id,
      description: values.description ?? '',
      rule_type: values.rule_type,
      severity: values.severity,
      schedule: values.schedule ?? '',
      check_expression: expression,
      enabled: values.enabled,
    };
    setSaving(true);
    try {
      if (editingId) {
        await apiClient.put(`/api/ontology/health/rules/${editingId}`, payload);
        message.success(t('规则已更新'));
      } else {
        await apiClient.post('/api/ontology/health/rules', payload);
        message.success(t('规则已创建'));
      }
      setEditorOpen(false);
      reload();
    } catch (e) {
      message.error(`${t('保存失败')}：${reasonOf(e)}`);
    } finally {
      setSaving(false);
    }
  }, [form, editingId, reload, t]);

  const removeRule = useCallback(
    async (id: string) => {
      try {
        await apiClient.delete(`/api/ontology/health/rules/${id}`);
        message.success(t('规则已删除'));
        reload();
      } catch (e) {
        message.error(`${t('删除失败')}：${reasonOf(e)}`);
      }
    },
    [reload, t],
  );

  const toggleRule = useCallback(
    async (rule: HealthRule, enabled: boolean) => {
      try {
        await apiClient.put(`/api/ontology/health/rules/${rule.id}`, { enabled });
        setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, enabled } : r)));
      } catch (e) {
        message.error(`${t('状态更新失败')}：${reasonOf(e)}`);
      }
    },
    [t],
  );

  /* ── KPI：规则维度 + 报告维度分开算，不混用 ── */
  const kpi = useMemo(() => {
    const enabled = rules.filter((r) => r.enabled).length;
    const fail = reports.filter((r) => r.status === 'FAIL').length;
    const pass = reports.filter((r) => r.status === 'PASS').length;
    const checked = reports.length;
    return {
      total: rules.length,
      enabled,
      checked,
      passRate: checked > 0 ? Math.round((pass / checked) * 100) : 0,
      fail,
      lastScanAt: reports.map((r) => r.scanned_at).sort().slice(-1)[0] ?? '-',
    };
  }, [rules, reports]);

  const ruleColumns = [
    { title: t('规则名'), dataIndex: 'name', key: 'name' },
    {
      title: t('目标类型'),
      dataIndex: 'target_type_id',
      key: 'target_type_id',
      render: (v: string) => <Text code>{v}</Text>,
    },
    { title: t('规则类型'), dataIndex: 'rule_type', key: 'rule_type', render: (v: string) => <Tag>{v}</Tag> },
    {
      title: t('严重度'),
      dataIndex: 'severity',
      key: 'severity',
      render: (v: string) => {
        const color = v === 'critical' || v === 'error' ? 'red' : v === 'warning' ? 'orange' : 'blue';
        return <Tag color={color}>{v}</Tag>;
      },
    },
    {
      title: t('启用'),
      dataIndex: 'enabled',
      key: 'enabled',
      render: (v: boolean, rule: HealthRule) => (
        <Switch size="small" checked={v} onChange={(checked) => void toggleRule(rule, checked)} />
      ),
    },
    {
      title: t('操作'),
      key: 'actions',
      render: (_: unknown, rule: HealthRule) => (
        <Space size={4}>
          <Button size="small" onClick={() => openEdit(rule)}>{t('编辑')}</Button>
          <Button size="small" loading={scanning} onClick={() => void runScan(rule.id)}>
            {t('扫描此规则')}
          </Button>
          <Popconfirm title={t('确认删除该规则？')} onConfirm={() => void removeRule(rule.id)}>
            <Button size="small" danger>{t('删除')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const reportColumns = [
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      render: (s: ReportStatus) => {
        const meta = STATUS_META[s] ?? STATUS_META.SKIP;
        return (
          <Space>
            {meta.icon}
            <Text>{s}</Text>
          </Space>
        );
      },
    },
    { title: t('规则'), dataIndex: 'rule_id', key: 'rule_id', render: (v: string) => <Text code>{v}</Text> },
    { title: t('实例'), dataIndex: 'instance_id', key: 'instance_id', render: (v: string) => <Text code>{v}</Text> },
    { title: t('目标类型'), dataIndex: 'target_type_id', key: 'target_type_id' },
    { title: t('严重度'), dataIndex: 'severity', key: 'severity', render: (v: string) => <Tag>{v}</Tag> },
    { title: t('说明'), dataIndex: 'message', key: 'message', ellipsis: true },
    { title: t('扫描时间'), dataIndex: 'scanned_at', key: 'scanned_at', width: 200 },
  ];

  const typeOptions = objectTypes.map((o) => ({ label: `${o.name}（${o.type_id}）`, value: o.type_id }));

  return (
    <div>
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>{t('本体质量健康度')}</Title>
            <Text type="secondary">{t('规则定义「什么算不合格」，扫描产出「哪些实例不合格」')}</Text>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={reload}>{t('刷新')}</Button>
            <Button icon={<PlusOutlined />} onClick={openCreate}>{t('新建规则')}</Button>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={scanning}
              onClick={() => void runScan()}
            >
              {t('运行扫描')}
            </Button>
          </Space>
        }
      >
        {error && (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
            title={t('加载健康度数据失败')}
            description={error}
            action={<Button size="small" onClick={reload}>{t('重试')}</Button>}
          />
        )}

        {lastScan && (
          <Alert
            type={lastScan.fail_count > 0 ? 'warning' : 'success'}
            showIcon
            style={{ marginBottom: 16 }}
            title={t('最近一次扫描')}
            description={t(
              '扫描 {{total}} 项：通过 {{pass}}，告警 {{warn}}，失败 {{fail}}',
              {
                total: lastScan.scanned_count,
                pass: lastScan.pass_count,
                warn: lastScan.warn_count,
                fail: lastScan.fail_count,
              },
            )}
          />
        )}

        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}><Card><Statistic title={t('规则总数')} value={kpi.total} /></Card></Col>
          <Col span={6}><Card><Statistic title={t('启用中')} value={kpi.enabled} /></Card></Col>
          <Col span={6}>
            <Card>
              <Statistic
                title={t('检查通过率')}
                value={kpi.passRate}
                suffix="%"
                styles={{ content: { color: kpi.passRate >= 90 ? '#3f8600' : '#faad14' } }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title={t('失败项')}
                value={kpi.fail}
                styles={{ content: { color: kpi.fail > 0 ? '#cf1322' : '#3f8600' } }}
              />
            </Card>
          </Col>
        </Row>

        <Spin spinning={loading}>
          <Tabs
            defaultActiveKey="rules"
            items={[
              {
                key: 'rules',
                label: `${t('规则')}（${rules.length}）`,
                children: rules.length === 0 ? (
                  <Empty description={t('还没有健康规则：先建一条「非空」或「取值域」规则，再运行扫描')} />
                ) : (
                  <Table rowKey="id" dataSource={rules} columns={ruleColumns} pagination={false} size="middle" />
                ),
              },
              {
                key: 'reports',
                label: `${t('扫描报告')}（${reports.length}）`,
                children: reports.length === 0 ? (
                  <Empty description={t('暂无扫描报告：运行一次扫描后会在此列出逐实例检查结果')} />
                ) : (
                  <Table
                    rowKey="id"
                    dataSource={reports}
                    columns={reportColumns}
                    size="middle"
                    pagination={{ pageSize: 20, showSizeChanger: true }}
                  />
                ),
              },
            ]}
          />
        </Spin>

        <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
          {t('最后扫描时间')}：{kpi.lastScanAt}
        </Text>
      </Card>

      <Drawer
        title={editingId ? t('编辑健康规则') : t('新建健康规则')}
        size="large"
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setEditorOpen(false)}>{t('取消')}</Button>
            <Button type="primary" loading={saving} onClick={() => void submit()}>{t('保存')}</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item label={t('规则名')} name="name" rules={[{ required: true, message: t('请填写规则名') }]}>
            <Input placeholder={t('例如：客户必须有手机号')} />
          </Form.Item>
          <Form.Item
            label={t('目标类型')}
            name="target_type_id"
            rules={[{ required: true, message: t('请选择目标对象类型') }]}
            extra={
              typeOptions.length === 0
                ? t('未能加载对象类型列表，可直接填写 type_id')
                : undefined
            }
          >
            {typeOptions.length > 0 ? (
              <Select options={typeOptions} showSearch optionFilterProp="label" />
            ) : (
              <Input placeholder="ObjectType.type_id" />
            )}
          </Form.Item>
          <Form.Item label={t('规则类型')} name="rule_type" rules={[{ required: true }]}>
            <Select
              options={['not_null', 'unique', 'range', 'regex', 'enum', 'custom'].map((v) => ({ label: v, value: v }))}
            />
          </Form.Item>
          <Form.Item label={t('严重度')} name="severity" rules={[{ required: true }]}>
            <Select options={SEVERITIES.map((v) => ({ label: v, value: v }))} />
          </Form.Item>
          <Form.Item
            label={t('检查表达式（JSON）')}
            name="check_expression"
            rules={[{ required: true, message: t('请填写检查表达式') }]}
            extra={t('例如 {"field": "phone", "pattern": "^1\\d{10}$"}；保存前会校验 JSON 合法性')}
          >
            <Input.TextArea rows={6} spellCheck={false} />
          </Form.Item>
          <Form.Item label={t('调度')} name="schedule" extra={t('留空表示仅手动触发')}>
            <Input placeholder={t('例如：0 2 * * *')} />
          </Form.Item>
          <Form.Item label={t('启用')} name="enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label={t('描述')} name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}

export default HealthDashboardPage;
