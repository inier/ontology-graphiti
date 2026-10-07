import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Descriptions, Timeline, Tag, Card, Spin, message, Typography } from 'antd';
import { gapApi, type GapItem } from '../services/gapApi';

export const GapDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [gap, setGap] = useState<GapItem | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      if (!id) { setLoading(false); return; }
      try { setGap(await gapApi.get(id)); }
      catch (e) { message.error((e as Error).message || '加载失败'); }
      finally { setLoading(false); }
    })();
  }, [id]);
  if (loading) return <Spin style={{ margin: 24 }} />;
  if (!gap) return <div style={{ padding: 24 }}>缺口不存在</div>;
  return (
    <div style={{ padding: 16 }}>
      <Card title={gap.expression} extra={<Tag>{gap.status}</Tag>}>
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
        {Object.entries(gap.source_counts_json || {}).map(([k, v]) => (
          <Tag key={k}>{k}: {v}</Tag>))}
      </Card>
      <Card title="occurrence 时间线（最近 50）" style={{ marginTop: 12 }}>
        <Timeline items={(gap.sources_json || []).map((s) => ({
          children: `${s.at} · ${s.source}${s.ref ? ' · ' + s.ref : ''}${s.detail ? ' · ' + s.detail : ''}`,
        }))} />
      </Card>
    </div>
  );
};
export default GapDetailPage;
