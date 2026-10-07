import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Alert, message } from 'antd';
import { gapApi, type GapStats } from '../services/gapApi';

export const GapStatsPage: React.FC = () => {
  const [s, setS] = useState<GapStats | null>(null);
  useEffect(() => {
    (async () => {
      try { setS(await gapApi.stats()); }
      catch (e) { message.error((e as Error).message || '加载统计失败'); }
    })();
  }, []);
  if (!s) return null;
  return (
    <div style={{ padding: 16 }}>
      {s.emit_failures > 0 && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message={`emitter 累计失败 ${s.emit_failures} 次（内存计数，重启归零）`} />)}
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="总缺口" value={s.total} /></Card></Col>
        <Col span={6}><Card><Statistic title="待处理(open)" value={s.by_status.open ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="已采纳" value={s.by_status.adopted ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="采纳率"
          value={s.adoption_rate == null ? '—' : `${(s.adoption_rate * 100).toFixed(1)}%`} /></Card></Col>
      </Row>
      <Card title="Top 热度" style={{ marginTop: 16 }}>
        <Table rowKey="id" pagination={false} dataSource={s.top_heat}
          columns={[
            { title: '说法', dataIndex: 'expression' },
            { title: '热度', dataIndex: 'heat' },
            { title: '状态', dataIndex: 'status' },
          ]} />
      </Card>
    </div>
  );
};
export default GapStatsPage;
