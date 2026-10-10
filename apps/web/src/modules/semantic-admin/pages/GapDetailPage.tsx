import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Timeline, Tag, Card, Spin, message, Typography,
         Button, Alert, Space, Statistic, Dropdown } from 'antd';
import { PlayCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { gapApi, gapRegressionApi, type GapItem, type ReplayReport,
         type RoutePreview, type PromoteResult } from '../services/gapApi';

const VERDICT_COLOR: Record<string, string> = {
  pass: 'green', fail: 'orange', error: 'red',
};

/** 路由层展示（ADR-090）：layer → 中文产物名。 */
const LAYER_LABEL: Record<string, string> = {
  content: 'USL 候选（术语）',
  schema: '结构变更提案（ChangeProposal）',
  tool: '路由工单（工程债）',
};

export const GapDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [gap, setGap] = useState<GapItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [report, setReport] = useState<ReplayReport | null>(null);
  const [preview, setPreview] = useState<RoutePreview | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [result, setResult] = useState<PromoteResult | null>(null);

  const reload = useCallback(async () => {
    if (!id) return;
    setGap(await gapApi.get(id));
  }, [id]);

  useEffect(() => {
    (async () => {
      if (!id) { setLoading(false); return; }
      try {
        const [g, pv] = await Promise.all([gapApi.get(id), gapApi.routePreview(id)]);
        setGap(g);
        setPreview(pv);
      } catch (e) { message.error((e as Error).message || '加载失败'); }
      finally { setLoading(false); }
    })();
  }, [id]);

  const runPromote = async (forceLayer?: 'content' | 'schema' | 'tool') => {
    if (!gap) return;
    setPromoting(true);
    try {
      const r = await gapApi.promote(gap.id,
        forceLayer ? { force_layer: forceLayer } : {});
      setResult(r);
      message.success(`已路由到：${LAYER_LABEL[r.layer || ''] || r.routed_to}`);
      await reload();
      setPreview(await gapApi.routePreview(gap.id));
    } catch (e) {
      message.error((e as Error).message || 'promote 失败');
    } finally { setPromoting(false); }
  };

  const runReplay = async () => {
    if (!gap) return;
    setReplaying(true);
    try {
      // 构建该 scope 回归集（缺口即"曾经答不上的问题"）→ 立即配对回放。
      // 报告只作人工裁决证据（ADR-088：门控归人不归模型，不自动接受）。
      const [ws, domain] = gap.scope_key.split('::');
      const built = await gapRegressionApi.build({
        workspace_id: ws !== '-' ? ws : undefined,
        domain_id: domain !== '-' ? domain : undefined,
      });
      const r = await gapRegressionApi.replay(built.set_id);
      setReport(r.report);
      message.info(`回放完成：verdict=${r.report.verdict}，修复 ${r.report.fixed_count} 例`);
    } catch (e) {
      // 错误信息暴露具体失败原因（不写笼统"回放失败"）
      message.error((e as Error).message || '配对回放失败');
    } finally { setReplaying(false); }
  };

  if (loading) return <Spin style={{ margin: 24 }} />;
  if (!gap) return <div style={{ padding: 24 }}>缺口不存在</div>;
  return (
    <div style={{ padding: 16 }}>
      <Card title={gap.expression} extra={<Tag>{gap.status}</Tag>}
        actions={[
          <Dropdown key="promote" menu={{
            items: [
              { key: 'auto', label: '按归因自动路由' },
              { key: 'content', label: '强制 → USL 候选' },
              { key: 'schema', label: '强制 → 结构提案' },
              { key: 'tool', label: '强制 → 路由工单' },
            ],
            onClick: ({ key }) => void runPromote(
              key === 'auto' ? undefined : (key as 'content' | 'schema' | 'tool')),
          }}>
            <Button type="primary" icon={<RocketOutlined />} loading={promoting}
              disabled={gap.status === 'promoted'}>
              Promote（按 layer 路由）
            </Button>
          </Dropdown>,
          <Button key="replay" type="primary" ghost icon={<PlayCircleOutlined />}
            loading={replaying} onClick={runReplay}>
            构建回归集并配对回放
          </Button>,
        ]}>
        <Descriptions column={2}>
          <Descriptions.Item label="热度">{gap.heat}</Descriptions.Item>
          <Descriptions.Item label="scope">{gap.scope_key}</Descriptions.Item>
          <Descriptions.Item label="首次">{gap.first_seen}</Descriptions.Item>
          <Descriptions.Item label="最近">{gap.last_seen}</Descriptions.Item>
          {gap.promoted_candidate_id && (
            <Descriptions.Item label="候选 ID">
              {/* 无 /semantic-admin/candidates/:id 深链路由（CandidatesPage 为单路由主从，
                  用内部 activeCandidate 状态），故仅展示 ID，不做死链跳转 */}
              <Typography.Text copyable code>{gap.promoted_candidate_id}</Typography.Text>
            </Descriptions.Item>)}
          {gap.promoted_proposal_id && (
            <Descriptions.Item label="结构提案 ID">
              <Typography.Text copyable code>{gap.promoted_proposal_id}</Typography.Text>
            </Descriptions.Item>)}
          {gap.promoted_ticket_id && (
            <Descriptions.Item label="路由工单">
              <a onClick={() => navigate(`/semantic-admin/routing-tickets/${gap.promoted_ticket_id}`)}>
                查看工单
              </a>
            </Descriptions.Item>)}
          {gap.resolved_term_id && (
            <Descriptions.Item label="已解析术语">{gap.resolved_term_id}</Descriptions.Item>)}
          {gap.dismiss_reason && (
            <Descriptions.Item label="忽略原因">{gap.dismiss_reason}</Descriptions.Item>)}
        </Descriptions>
      </Card>
      {preview && (
        <Card title="路由预览（无副作用）" style={{ marginTop: 12 }}>
          <Space wrap>
            <Tag color="geekblue">layer: {preview.layer}</Tag>
            <Tag>routed_to: {preview.routed_to}</Tag>
            <Tag>target_kind: {preview.target_kind}</Tag>
            {preview.already_promoted && <Tag color="green">已 promote</Tag>}
          </Space>
          {preview.layer === 'schema' && preview.changes?.length ? (
            <Alert type="info" showIcon style={{ marginTop: 8 }}
              message={`将生成 ${preview.changes.length} 条 RFC 6902 变更`}
              description={<pre>
                {preview.changes.map((c) => `${c.op} ${c.path}`).join('\n')}
              </pre>} />
          ) : null}
          {preview.layer === 'tool' && (
            <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
              目标检索引擎：{preview.engine || 'unknown_engine'}（无则落 unknown，不造数）
            </Typography.Paragraph>)}
        </Card>
      )}
      {result && (
        <Card title="Promote 结果" style={{ marginTop: 12 }}>
          <Space wrap>
            <Tag color="green">{LAYER_LABEL[result.layer || ''] || result.routed_to}</Tag>
            {result.candidate_id && (
              <Typography.Text copyable code>候选 {result.candidate_id}</Typography.Text>)}
            {result.proposal_id && (
              <Typography.Text copyable code>提案 {result.proposal_id}</Typography.Text>)}
            {result.ticket_id && (
              <a onClick={() => navigate(`/semantic-admin/routing-tickets/${result.ticket_id}`)}>
                打开工单 {result.ticket_id}
              </a>)}
          </Space>
          {result.layer === 'schema' && (
            <Alert type="warning" showIcon style={{ marginTop: 8 }}
              message="结构提案已创建为 draft，需人工审批后才会变更本体（门控归人）。" />)}
          {result.layer === 'tool' && (
            <Alert type="info" showIcon style={{ marginTop: 8 }}
              message={`工单优先级 ${result.priority}（${result.ticket_status}），按 SLA 跟踪至闭环。`} />)}
        </Card>
      )}
      <Card title="来源计数" style={{ marginTop: 12 }}>
        <Space wrap>
          {Object.entries(gap.source_counts_json || {}).map(([k, v]) => (
            <Tag key={k}>{k}: {v}</Tag>))}
          {Object.entries(gap.attribution_counts_json || {}).map(([k, v]) => (
            <Tag key={k} color="geekblue">归因 {k}: {v}</Tag>))}
        </Space>
      </Card>
      {report && (
        <Card title="配对回放报告（证据，人工裁决用）"
          extra={<Tag color={VERDICT_COLOR[report.verdict]}>{report.verdict}</Tag>}
          style={{ marginTop: 12 }}>
          {report.warning && (
            <Alert type="warning" showIcon style={{ marginBottom: 12 }}
              message={report.warning} />)}
          {report.error_detail && (
            <Alert type="error" showIcon style={{ marginBottom: 12 }}
              message="回放执行失败" description={report.error_detail} />)}
          <Space size={32}>
            <Statistic title="修复 (fixed)" value={report.fixed_count}
              valueStyle={{ color: '#3f8600' }} />
            <Statistic title="回归 (regressed)" value={report.regressed_count}
              valueStyle={{ color: '#cf1322' }} />
            <Statistic title="未变 (unchanged)" value={report.unchanged_count} />
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            模型指纹: {report.model_id || '(空)'} · prompt: {report.prompt_version} ·
            通过标准: 回归 0 且修复 ≥1
          </Typography.Paragraph>
        </Card>
      )}
      <Card title="occurrence 时间线（最近 50）" style={{ marginTop: 12 }}>
        <Timeline items={(gap.sources_json || []).map((s) => ({
          children: `${s.at} · ${s.source}${s.ref ? ' · ' + s.ref : ''}${s.detail ? ' · ' + s.detail : ''}`
            + (s.attribution ? ` · 归因:${s.attribution.layer}`
              + (s.attribution.target_kind ? `/${s.attribution.target_kind}` : '') : ''),
        }))} />
      </Card>
    </div>
  );
};
export default GapDetailPage;
