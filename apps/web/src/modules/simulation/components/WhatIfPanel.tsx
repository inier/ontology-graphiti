/**
 * WhatIfPanel —— 假设推演（参数变体 → 指标敏感度）
 *
 * 契约（`odap/biz/simulation/simulation_sandbox/api/parallel_routes.py`）：
 *   POST /api/simulation/what-if
 *   body: { base_scenario: { action_type_id?, target_object_id?, target_object_type?, parameters? },
 *           param_variations: [ { <param>: <value> }, ... ] }
 *   resp: { run_id, status, base_scenario, total_variations,
 *           results: [{ scenario_id, status, metric_changes[], risk_assessment,
 *                       recommendation, confidence, variation }],
 *           sensitivity_analysis: { <metric>: [{ variation, delta }] }, completed_at }
 *
 * 旧实现的三处硬伤（挂上去必然出错，所以这里整体重写）：
 *  1. 只发 `param_variations`，**不发 `base_scenario`** —— 后端拿到空 base，
 *     所有场景的 action_type_id / target_object_id 都是空串，仿真等于在跑一个空壳；
 *  2. 发 `sandbox_id` / `scenario_id` —— 后端这两个键根本不读，纯噪声；
 *  3. 读 `sensitivity_analysis[x].impact` 与 `.direction` —— 后端只返回 `variation` / `delta`，
 *     对 `undefined` 调 `.toFixed()` 会直接抛 TypeError。
 */
import { useCallback, useMemo, useState } from 'react';
import {
  Button, Card, Col, Empty, Form, Input, InputNumber, Row, Space, Table, Tag, Typography, message,
} from 'antd';
import { ExperimentOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;

interface ParamVariationRow {
  key: string;
  value: number;
}

interface WhatIfResult {
  scenario_id: string;
  status: string;
  metric_changes: Array<{ metric_name: string; before?: unknown; after?: unknown; delta?: number | null }>;
  risk_assessment: Record<string, unknown>;
  recommendation: string;
  confidence: number;
  variation: Record<string, number>;
}

interface WhatIfResponse {
  run_id: string;
  status: string;
  total_variations: number;
  results: WhatIfResult[];
  sensitivity_analysis: Record<string, Array<{ variation: Record<string, number>; delta: number }>>;
  completed_at: string;
}

interface SensitivityRow {
  metric: string;
  variation: string;
  delta: number;
}

export interface WhatIfPanelProps {
  /** 基础场景（可选）：不填则以空场景跑，敏感度仍可算但缺少动作上下文 */
  defaultActionTypeId?: string;
  defaultTargetObjectId?: string;
  defaultTargetObjectType?: string;
}

function reasonOf(e: unknown): string {
  const err = e as { message?: string; status?: number; detail?: string };
  if (err?.detail) return err.detail;
  if (err?.status && err?.message) return `HTTP ${err.status}：${err.message}`;
  return err?.message ?? String(e);
}

export function WhatIfPanel({
  defaultActionTypeId = '',
  defaultTargetObjectId = '',
  defaultTargetObjectType = '',
}: WhatIfPanelProps) {
  const { t } = useI18n('simulation');
  const [baseForm] = Form.useForm<{
    action_type_id: string;
    target_object_id: string;
    target_object_type: string;
    parameters: string;
  }>();
  const [rows, setRows] = useState<ParamVariationRow[]>([{ key: '', value: 0 }]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WhatIfResponse | null>(null);

  const run = useCallback(async () => {
    const base = await baseForm.validateFields();
    const valid = rows.filter((r) => r.key.trim());
    if (valid.length === 0) {
      message.warning(t('至少填写一个参数变体'));
      return;
    }
    let parameters: Record<string, unknown> = {};
    if (base.parameters?.trim()) {
      try {
        parameters = JSON.parse(base.parameters);
      } catch (e) {
        message.error(`${t('基础场景参数不是合法 JSON')}：${reasonOf(e)}`);
        return;
      }
    }

    setLoading(true);
    try {
      const data = await apiClient.post<WhatIfResponse>('/api/simulation/what-if', {
        base_scenario: {
          action_type_id: base.action_type_id || '',
          target_object_id: base.target_object_id || '',
          target_object_type: base.target_object_type || '',
          parameters,
        },
        param_variations: valid.map((r) => ({ [r.key]: r.value })),
      });
      setResult(data);
      message.success(t('推演完成：{{n}} 个变体', { n: data.total_variations }));
    } catch (e) {
      message.error(`${t('推演失败')}：${reasonOf(e)}`);
    } finally {
      setLoading(false);
    }
  }, [baseForm, rows, t]);

  /** 后端返回的是 { metric: [{ variation, delta }] }，摊平成表格行 */
  const sensitivityRows = useMemo<SensitivityRow[]>(() => {
    if (!result?.sensitivity_analysis) return [];
    return Object.entries(result.sensitivity_analysis).flatMap(([metric, items]) =>
      (items ?? []).map((item) => ({
        metric,
        variation: Object.entries(item.variation ?? {})
          .map(([k, v]) => `${k}=${v}`)
          .join(', '),
        delta: item.delta,
      })),
    );
  }, [result]);

  return (
    <Row gutter={16}>
      <Col span={9}>
        <Card
          title={
            <Space>
              <ExperimentOutlined />
              <Title level={5} style={{ margin: 0 }}>{t('基础场景与参数变体')}</Title>
            </Space>
          }
          extra={
            <Button type="primary" loading={loading} onClick={() => void run()}>
              {t('开始推演')}
            </Button>
          }
        >
          <Form form={baseForm} layout="vertical" size="small">
            <Form.Item
              label={t('动作类型 ID')}
              name="action_type_id"
              initialValue={defaultActionTypeId}
              extra={t('留空则按空场景推演，敏感度仍可计算')}
            >
              <Input placeholder="action_type_id" />
            </Form.Item>
            <Form.Item label={t('目标对象类型')} name="target_object_type" initialValue={defaultTargetObjectType}>
              <Input placeholder="ObjectType" />
            </Form.Item>
            <Form.Item label={t('目标对象 ID')} name="target_object_id" initialValue={defaultTargetObjectId}>
              <Input placeholder="instance_id" />
            </Form.Item>
            <Form.Item label={t('基础参数（JSON）')} name="parameters" initialValue="{}">
              <Input.TextArea rows={3} spellCheck={false} />
            </Form.Item>
          </Form>

          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('每个变体会与基础参数合并后单独仿真一次，用于观察指标随参数变化的敏感度')}
          </Text>

          <div style={{ marginTop: 12 }}>
            {rows.map((row, index) => (
              <Space key={index} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Input
                  placeholder={t('参数名')}
                  value={row.key}
                  onChange={(e) =>
                    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, key: e.target.value } : r)))
                  }
                  style={{ width: 150 }}
                />
                <InputNumber
                  placeholder={t('取值')}
                  value={row.value}
                  onChange={(v) =>
                    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, value: v ?? 0 } : r)))
                  }
                  style={{ width: 110 }}
                />
                <Button
                  type="text"
                  danger
                  icon={<MinusCircleOutlined />}
                  disabled={rows.length === 1}
                  onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                />
              </Space>
            ))}
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              block
              onClick={() => setRows((prev) => [...prev, { key: '', value: 0 }])}
            >
              {t('添加变体')}
            </Button>
          </div>
        </Card>
      </Col>

      <Col span={15}>
        <Card
          title={t('推演结果')}
          extra={
            result ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('运行 ID')}：{result.run_id} · {result.completed_at}
              </Text>
            ) : null
          }
        >
          {!result ? (
            <Empty description={t('尚未推演：填写左侧参数变体后点击「开始推演」')} />
          ) : (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div>
                <Text strong>{t('指标敏感度')}</Text>
                {sensitivityRows.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={t('本次推演没有产生指标变化（通常是基础场景缺少动作上下文）')}
                  />
                ) : (
                  <Table
                    rowKey={(r) => `${r.metric}-${r.variation}`}
                    size="small"
                    style={{ marginTop: 8 }}
                    dataSource={sensitivityRows}
                    pagination={false}
                    columns={[
                      { title: t('指标'), dataIndex: 'metric', key: 'metric' },
                      { title: t('变体'), dataIndex: 'variation', key: 'variation' },
                      {
                        title: t('变化量'),
                        dataIndex: 'delta',
                        key: 'delta',
                        render: (v: number) => (
                          <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
                            {v >= 0 ? '+' : ''}
                            {(Number.isFinite(v) ? v : 0).toFixed(4)}
                          </Text>
                        ),
                      },
                    ]}
                  />
                )}
              </div>

              <div>
                <Text strong>{t('逐变体结论')}</Text>
                <Table
                  rowKey="scenario_id"
                  size="small"
                  style={{ marginTop: 8 }}
                  dataSource={result.results ?? []}
                  pagination={false}
                  columns={[
                    { title: t('变体'), dataIndex: 'scenario_id', key: 'scenario_id', width: 120 },
                    {
                      title: t('参数'),
                      dataIndex: 'variation',
                      key: 'variation',
                      render: (v: Record<string, number>) =>
                        Object.entries(v ?? {}).map(([k, val]) => (
                          <Tag key={k}>{`${k}=${val}`}</Tag>
                        )),
                    },
                    {
                      title: t('状态'),
                      dataIndex: 'status',
                      key: 'status',
                      width: 100,
                      render: (v: string) => (
                        <Tag color={v === 'completed' || v === 'success' ? 'green' : 'orange'}>{v}</Tag>
                      ),
                    },
                    {
                      title: t('置信度'),
                      dataIndex: 'confidence',
                      key: 'confidence',
                      width: 100,
                      render: (v: number) => (typeof v === 'number' ? `${Math.round(v * 100)}%` : '-'),
                    },
                    {
                      title: t('建议'),
                      dataIndex: 'recommendation',
                      key: 'recommendation',
                      ellipsis: true,
                      render: (v: string) => v || '-',
                    },
                  ]}
                />
              </div>
            </Space>
          )}
        </Card>
      </Col>
    </Row>
  );
}

export default WhatIfPanel;
