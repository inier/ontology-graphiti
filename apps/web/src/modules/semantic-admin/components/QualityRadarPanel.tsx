import React, { useEffect, useMemo, useState } from 'react';
import {
  Card,
  Collapse,
  Tag,
  Empty,
  Spin,
  Alert,
  Progress,
  Space,
  Typography,
  Badge,
  Button,
  Modal,
  Form,
  Input,
  Select,
} from 'antd';
import type { CollapseProps } from 'antd';
import {
  WarningOutlined, CheckCircleTwoTone, CloseCircleTwoTone,
  EditOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import type { QualityReport, SubMetric } from '../types';
import { QUALITY_TIER_COLOR } from '../types';
import { getQualityReport } from '../services/qualityApi';
import { modifyCandidate, type CandidatePatch } from '../services/pipelineApi';
import type { Candidate } from '../services/pipelineApi';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const GATE_TITLES: Record<'gate1' | 'gate2' | 'gate3', { title: string; count: number; weight: string }> = {
  gate1: { title: 'Gate 1 · 句法/结构一致性闸', count: 7, weight: 'ω=0.35' },
  gate2: { title: 'Gate 2 · 语义一致性闸', count: 4, weight: 'ω=0.40' },
  gate3: { title: 'Gate 3 · 领域质量闸', count: 5, weight: 'ω=0.25' },
};

const TERM_TYPE_OPTIONS = ['对象类型', '关系类型', '属性', '动作类型', '过程类型', '规则类型'];

interface Props {
  candidateId?: string;
  candidate?: Candidate | null;
  inlineReport?: QualityReport | null;
  forceEvaluate?: boolean;
  canWrite?: boolean;
  onLoaded?: (report: QualityReport) => void;
  onModified?: () => void;
}

const submetricToLabel = (s: SubMetric): string => {
  const map: Record<string, string> = {
    // G1 × 7
    g1_name_valid: 'G1.1 名称合规',
    g1_en_pascal: 'G1.2 PascalCase',
    g1_semtype_enum: 'G1.3 语义类型枚举',
    g1_syn_count: 'G1.4 同义词规模',
    g1_syn_dedup: 'G1.5 同义词去重',
    g1_no_circ_include: 'G1.6 无环包含',
    g1_usl_dup_check: 'G1.7 USL 去重',
    // G2 × 4
    g2_disjoint_check: 'G2.1 不相交对',
    g2_cardinality: 'G2.2 基数约束',
    g2_isa_acyclic: 'G2.3 is_a 无环',
    g2_llm_judge: 'G2.4 LLM 判定',
    // G3 × 5
    g3_property_density: 'G3.1 属性密度',
    g3_doc_hits: 'G3.2 语料命中',
    g3_syn_richness: 'G3.3 同义词丰富度',
    g3_usl_novelty: 'G3.4 USL 新颖度',
    g3_hierarchy_contrib: 'G3.5 层级贡献',
  };
  return map[s.submetric] ?? s.submetric;
};

const passBadge = (s: SubMetric) => {
  if (s.score >= 0.95) return <CheckCircleTwoTone twoToneColor="#52c41a" />;
  if (s.score >= 0.5) return <Badge status="warning" />;
  return <CloseCircleTwoTone twoToneColor="#ff4d4f" />;
};

const MetricCard: React.FC<{ metric: SubMetric }> = ({ metric }) => {
  const pct = Math.round(Math.max(0, Math.min(1, metric.score ?? 0)) * 100);
  const statusColor: 'success' | 'active' | 'exception' | 'normal' =
    pct >= 85 ? 'success' : pct >= 50 ? 'active' : 'exception';
  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderRadius: 8 }}
      title={
        <Space>
          {passBadge(metric)}
          <Text strong>{submetricToLabel(metric)}</Text>
          <Tag style={{ marginLeft: 4 }}>{metric.submetric}</Tag>
        </Space>
      }
      extra={<Text type={pct >= 85 ? 'success' : pct >= 50 ? undefined : 'danger'}>{pct}%</Text>}
    >
      <Progress percent={pct} size="small" status={statusColor} showInfo={false} />
      <Paragraph
        type="secondary"
        style={{ fontSize: 12, margin: '6px 0 0', lineHeight: 1.5 }}
        ellipsis={{ rows: 2, expandable: true, symbol: '更多' }}
      >
        {metric.reason || metric.rule_name || '—'}
      </Paragraph>
    </Card>
  );
};

const QualityRadarPanel: React.FC<Props> = ({
  candidateId, candidate, inlineReport, forceEvaluate,
  canWrite, onLoaded, onModified,
}) => {
  const [report, setReport] = useState<QualityReport | null>(inlineReport ?? null);
  const [loading, setLoading] = useState<boolean>(false);
  const [err, setErr] = useState<string>('');
  const chartRef = React.useRef<HTMLDivElement>(null);
  const chartInstance = React.useRef<echarts.ECharts | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);
  const [modifyForm] = Form.useForm<CandidatePatch>();
  const [submitting, setSubmitting] = useState(false);
  const [forceKey, setForceKey] = useState(0);

  useEffect(() => {
    setReport(inlineReport ?? null);
    setErr('');
    const cid = candidateId ?? candidate?.id;
    if ((inlineReport && !forceEvaluate) || !cid) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const r = await getQualityReport(cid, !!forceEvaluate || forceKey > 0);
        if (!alive) return;
        setReport(r);
        onLoaded?.(r);
      } catch (e) {
        if (!alive) return;
        setErr((e as Error).message || String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [candidateId, candidate?.id, inlineReport, forceEvaluate, onLoaded, forceKey]);

  const radarData = useMemo(() => {
    if (!report) return null;
    const g = report.submetrics;
    const all: SubMetric[] = [...(g.gate1 ?? []), ...(g.gate2 ?? []), ...(g.gate3 ?? [])];
    const labels = all.map(submetricToLabel);
    const scores = all.map((s) => Number((s.score ?? 0).toFixed(3)));
    return { labels, scores, total: report.total_score };
  }, [report]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
      const onResize = () => chartInstance.current?.resize();
      window.addEventListener('resize', onResize);
      return () => {
        window.removeEventListener('resize', onResize);
        chartInstance.current?.dispose();
        chartInstance.current = null;
      };
    }
    if (!radarData) return;
    const tierColor = QUALITY_TIER_COLOR[report?.tier ?? 'VERY_LOW'] || '#f5222d';
    chartInstance.current.setOption({
      tooltip: {},
      radar: {
        indicator: radarData.labels.map((name) => ({ name, max: 1 })),
        shape: 'polygon',
        splitNumber: 4,
        axisName: { fontSize: 10, color: '#595959' },
      },
      series: [
        {
          type: 'radar',
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: tierColor, width: 2 },
          areaStyle: { color: tierColor, opacity: 0.18 },
          itemStyle: { color: tierColor },
          data: [
            {
              value: radarData.scores,
              name: `Total ${(radarData.total * 100).toFixed(1)}%`,
            },
          ],
        },
      ],
    });
  }, [radarData, report?.tier]);

  useEffect(() => {
    const t = setTimeout(() => chartInstance.current?.resize(), 50);
    return () => clearTimeout(t);
  }, [report]);

  const collapseItems: CollapseProps['items'] = (['gate1', 'gate2', 'gate3'] as const).map((g) => {
    const cfg = GATE_TITLES[g];
    const items = (report?.submetrics[g] ?? []) as SubMetric[];
    return {
      key: g,
      label: (
        <Space>
          <Text strong>{cfg.title}</Text>
          <Tag color="blue">{cfg.weight}</Tag>
          <Tag color={items.length >= cfg.count ? 'green' : 'orange'}>
            {items.length}/{cfg.count}
          </Tag>
          {report && g === 'gate1' && (
            <Tag color={report.gate1_score >= 0.85 ? 'green' : report.gate1_score >= 0.5 ? 'gold' : 'red'}>
              G1 {(report.gate1_score * 100).toFixed(1)}%
            </Tag>
          )}
          {report && g === 'gate2' && (
            <Tag color={report.gate2_score >= 0.85 ? 'green' : report.gate2_score >= 0.5 ? 'gold' : 'red'}>
              G2 {(report.gate2_score * 100).toFixed(1)}%
            </Tag>
          )}
          {report && g === 'gate3' && (
            <Tag color={report.gate3_score >= 0.85 ? 'green' : report.gate3_score >= 0.5 ? 'gold' : 'red'}>
              G3 {(report.gate3_score * 100).toFixed(1)}%
            </Tag>
          )}
        </Space>
      ),
      children:
        items.length === 0 ? (
          <Empty description="暂无可展示子指标" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          items.map((m) => <MetricCard key={m.submetric} metric={m} />)
        ),
    };
  });

  if (!candidateId && !inlineReport && !candidate) {
    return (
      <Empty
        style={{ marginTop: 48 }}
        description="选择一条候选查看质量雷达"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  const openModify = () => {
    modifyForm.setFieldsValue({
      term: candidate?.canonical,
      canonical_label: (candidate as any)?.canonical_label,
      term_type: candidate?.semantic_type,
      synonyms: candidate?.synonyms ?? [],
      definition: candidate?.definition,
      domain_id: candidate?.domain_id,
    });
    setModifyOpen(true);
  };

  const submitModify = async () => {
    const cid = candidateId ?? candidate?.id;
    if (!cid) return;
    const values = await modifyForm.validateFields();
    setSubmitting(true);
    try {
      const body: CandidatePatch = {};
      if (values.term !== undefined) body.term = values.term;
      if (values.canonical_label !== undefined) body.canonical_label = values.canonical_label;
      if (values.term_type !== undefined) body.term_type = values.term_type;
      if (values.synonyms !== undefined) body.synonyms = values.synonyms;
      if (values.definition !== undefined) body.definition = values.definition;
      if (values.domain_id !== undefined) body.domain_id = values.domain_id;
      const { updated_fields } = await modifyCandidate(cid, body);
      Modal.success({
        title: 'Modify succeeded',
        content: `Updated fields: ${updated_fields.join(', ') || '—'}，正在强制重新评估 16 子指标...`,
        okText: 'OK',
      });
      setModifyOpen(false);
      setForceKey((k) => k + 1);
      onModified?.();
    } catch (e) {
      Modal.error({
        title: 'Modify failed',
        content: (e as Error).message || String(e),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Spin spinning={loading} tip="评估质量闸 16 子指标中...">
      {err ? (
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          message="质量报告加载失败"
          description={err}
        />
      ) : null}

      {report?.recommend_auto_skip ? (
        <Alert
          style={{ marginBottom: 12 }}
          type="success"
          showIcon
          icon={<ThunderboltOutlined style={{ color: '#52c41a' }} />}
          message={
            <Space>
              <Text strong style={{ color: '#389e0d' }}>Auto-Skip L2 · 质量 ≥ 0.90 自动跳过终审</Text>
              <Tag color="green">总分 {(report.total_score * 100).toFixed(1)}</Tag>
              <Tag color="geekblue">{report.overall}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                L1 审核员通过后，直接进入 APPROVED，无需 L2 Admin 复核
              </Text>
            </Space>
          }
        />
      ) : null}

      {report ? (
        <>
          <Card
            size="small"
            style={{ marginBottom: 12, borderRadius: 8 }}
            title={
              <Space>
                <Tag color={QUALITY_TIER_COLOR[report.tier]} style={{ fontSize: 14, padding: '2px 12px' }}>
                  TIER · {report.tier}
                </Tag>
                <Tag color={report.overall === 'PASS' ? 'green' : report.overall === 'REVIEW' ? 'gold' : 'red'}>
                  {report.overall}
                </Tag>
                {report.recommend_auto_skip ? (
                  <Tag color="geekblue" icon={<CheckCircleTwoTone twoToneColor="#2f54eb" />}>
                    ≥ 0.9 Auto-Skip L2
                  </Tag>
                ) : null}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {report.generated_at}
                </Text>
              </Space>
            }
            extra={
              <Space>
                <Button
                  type="link"
                  icon={<EditOutlined />}
                  disabled={!canWrite}
                  onClick={openModify}
                >
                  Modify
                </Button>
                <Text strong style={{ fontSize: 16, color: QUALITY_TIER_COLOR[report.tier] }}>
                  {(report.total_score * 100).toFixed(1)}
                </Text>
                <Text type="secondary">/ 100</Text>
              </Space>
            }
          >
            <Space size="large" wrap style={{ marginBottom: 4 }}>
              <Progress
                type="circle"
                size={96}
                percent={Math.round(report.gate1_score * 100)}
                format={(p) => `G1 ${p}%`}
                status={report.gate1_score >= 0.85 ? 'success' : report.gate1_score >= 0.5 ? 'active' : 'exception'}
              />
              <Progress
                type="circle"
                size={96}
                percent={Math.round(report.gate2_score * 100)}
                format={(p) => `G2 ${p}%`}
                status={report.gate2_score >= 0.85 ? 'success' : report.gate2_score >= 0.5 ? 'active' : 'exception'}
              />
              <Progress
                type="circle"
                size={96}
                percent={Math.round(report.gate3_score * 100)}
                format={(p) => `G3 ${p}%`}
                status={report.gate3_score >= 0.85 ? 'success' : report.gate3_score >= 0.5 ? 'active' : 'exception'}
              />
            </Space>
            <div ref={chartRef} style={{ width: '100%', height: 360 }} />
          </Card>

          <Collapse items={collapseItems} defaultActiveKey={['gate1', 'gate2', 'gate3']} ghost />
        </>
      ) : (
        <Empty description="等待质量评估结果..." />
      )}

      <Modal
        title={<Space><EditOutlined /> Modify Candidate · B5 PATCH /candidates/{candidateId || candidate?.id}</Space>}
        open={modifyOpen}
        onCancel={() => setModifyOpen(false)}
        onOk={submitModify}
        confirmLoading={submitting}
        okText="保存并重新评估"
        cancelText="取消"
        width={640}
      >
        <Form
          form={modifyForm}
          layout="vertical"
          preserve={false}
          initialValues={{ synonyms: [], term_type: '对象类型' }}
        >
          <Form.Item name="term" label="术语/标准名 (term / canonical)" rules={[{ required: true }]}>
            <Input placeholder="例如：蜀汉" maxLength={40} />
          </Form.Item>
          <Form.Item name="canonical_label" label="规范标签 (canonical_label)">
            <Input placeholder="可选，默认同 term" />
          </Form.Item>
          <Form.Item name="term_type" label="语义类型 (term_type)">
            <Select options={TERM_TYPE_OPTIONS.map((t) => ({ label: t, value: t }))} />
          </Form.Item>
          <Form.Item name="synonyms" label="同义词列表 (synonyms)">
            <Select mode="tags" placeholder="按回车添加同义词，例如刘玄德,玄德,皇叔" />
          </Form.Item>
          <Form.Item name="domain_id" label="领域 ID (domain_id)">
            <Input placeholder="例如：ThreeKingdoms" />
          </Form.Item>
          <Form.Item name="definition" label="定义 / 释义 (definition)">
            <TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder="例如：三国时期蜀汉开国皇帝刘备的称号..." />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

export default QualityRadarPanel;
