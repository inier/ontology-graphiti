import { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Tag, Empty } from 'antd';
import { StatCard } from '../components/StatCard';
import { api } from '../services/api';
import type { Scenario, Stats, PipelineStats } from '../types';

export function Dashboard() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [scenarioCount, setScenarioCount] = useState(0);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const statsData: Stats = await api.getStats();
        const scenariosData = await api.listScenarios();
        setStats(statsData.pipeline);
        setScenarioCount(statsData.scenarios ?? 0);
        setScenarios(Array.isArray(scenariosData) ? scenariosData : []);
      } catch (error) {
        console.error('加载数据失败', error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const columns = [
    {
      title: 'ID',
      dataIndex: 'scenario_id',
      key: 'id',
      render: (id: string) => <Tag color="blue">{id?.substring(0, 8) || 'N/A'}</Tag>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => name || '未命名场景',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created',
      render: (date: string) => (date ? new Date(date).toLocaleString('zh-CN') : 'N/A'),
    },
  ];

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <StatCard title="摄入数量" value={stats?.ingest_count ?? 0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="错误数量" value={stats?.error_count ?? 0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="版本数量" value={stats?.version_count ?? 0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="场景数量" value={scenarioCount} loading={loading} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={16}>
          <Card title="本体图谱预览" style={{ borderRadius: 8 }}>
            <div
              style={{
                height: 320,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: 18,
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🔗</div>
                <div>本体图谱预览区域</div>
                <div style={{ fontSize: 12, marginTop: 8, opacity: 0.8 }}>
                  点击进入本体图谱页面查看详情
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="最新事件" style={{ borderRadius: 8 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div
                style={{
                  padding: 12,
                  background: '#fff2f0',
                  borderLeft: '3px solid #ff4d4f',
                  borderRadius: 4,
                }}
              >
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>10:30</div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>红方装甲营发起进攻</div>
              </div>
              <div
                style={{
                  padding: 12,
                  background: '#f0f5ff',
                  borderLeft: '3px solid #1890ff',
                  borderRadius: 4,
                }}
              >
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>10:15</div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>蓝方增援部队到达</div>
              </div>
              <div
                style={{
                  padding: 12,
                  background: '#fff7e6',
                  borderLeft: '3px solid #faad14',
                  borderRadius: 4,
                }}
              >
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>09:45</div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>双方在B区形成对峙</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="场景列表" style={{ borderRadius: 8 }}>
            {scenarios.length > 0 ? (
              <Table
                columns={columns}
                dataSource={scenarios}
                rowKey="scenario_id"
                loading={loading}
                pagination={{ pageSize: 5 }}
              />
            ) : (
              <Empty description="暂无场景数据" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
