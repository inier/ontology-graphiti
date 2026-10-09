import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Descriptions, Timeline, Tag, Card, Spin, message, Typography,
         Button, Alert, Space, Statistic } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { gapApi, gapRegressionApi, type GapItem, type ReplayReport } from '../services/gapApi';

const VERDICT_COLOR: Record<string, string> = {
  pass: 'green', fail: 'orange', error: 'red',
};

export const GapDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [gap, setGap] = useState<GapItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [report, setReport] = useState<ReplayReport | null>(null);

  useEffect(() => {
    (async () => {
      if (!id) { setLoading(false); return; }
      try { setGap(await gapApi.get(id)); }
      catch (e) { message.error((e as Error).message || '加载失败'); }
      finally { setLoading(false); }
    })();
  }, [id]);

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
        actions={[<Button key="replay" type="primary" ghost icon={<PlayCircleOutlined />}
          loading={replaying} onClick={runReplay}>
          构建回归集并配对回放
        </Button>]}>
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
          {gap.resolved_term_id && (
            <Descriptions.Item label="已解析术语">{gap.resolved_term_id}</Descriptions.Item>)}
          {gap.dismiss_reason && (
            <Descriptions.Item label="忽略原因">{gap.dismiss_reason}</Descriptions.Item>)}
        </Descriptions>
      </Card>
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
