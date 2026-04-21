import { useState, useEffect } from 'react';
import { Card, Row, Col, Button, Space, Typography } from 'antd';
import { PlusOutlined, ImportOutlined, SyncOutlined, HistoryOutlined } from '@ant-design/icons';
import { StatCard } from '../modules/shared';
import { api } from '../modules/shared/services/api';
import type { Scenario, Stats } from '../modules/shared/types';

const { Title, Text } = Typography;

export function Dashboard() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [stats, setStats] = useState<Stats>({
    total_scenarios: 0,
    total_entities: 0,
    total_events: 0,
    total_versions: 0,
    recent_activities: [],
    pipeline: {
      ingest_count: 0,
      error_count: 0,
      version_count: 0,
      latest_version: '',
    },
    scenarios: 0,
    ws_clients: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [scenariosData, statsData] = await Promise.all([
        api.listScenarios(),
        api.getStats(),
      ]);
      setScenarios(scenariosData);
      setStats(statsData);
    } catch (error) {
      console.error('加载数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateScenario = () => {
    console.log('创建场景');
  };

  const handleImportScenario = () => {
    console.log('导入场景');
  };

  const handleSyncAll = () => {
    console.log('同步所有场景');
  };

  const handleViewHistory = () => {
    console.log('查看历史');
  };

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={[16, 16]}>
        <Col span={18}>
          <Title level={3}>场景管理</Title>
        </Col>
        <Col span={6} style={{ textAlign: 'right' }}>
          <Space>
            <Button type="default" icon={<HistoryOutlined />} onClick={handleViewHistory}>
              历史版本
            </Button>
            <Button type="default" icon={<ImportOutlined />} onClick={handleImportScenario}>
              导入场景
            </Button>
            <Button type="default" icon={<SyncOutlined />} onClick={handleSyncAll}>
              同步到图数据库
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateScenario}>
              创建场景
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={6}>
          <StatCard title="实体数量" value={0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="关系数量" value={0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="版本数量" value={stats.pipeline?.version_count || 0} loading={loading} />
        </Col>
        <Col span={6}>
          <StatCard title="摄入文档" value={stats.pipeline?.ingest_count || 0} loading={loading} />
        </Col>
      </Row>

      <Card title="场景列表" style={{ marginTop: 16 }}>
        {scenarios.map((scenario) => (
          <Card
            key={scenario.scenario_id}
            style={{ marginBottom: 16, borderLeft: '4px solid #1890ff' }}
            extra={
              <Space>
                <Button size="small" type="link">查看</Button>
                <Button size="small" type="link">编辑</Button>
                <Button size="small" danger type="link">删除</Button>
              </Space>
            }
          >
            <Row>
              <Col span={16}>
                <Text strong>{scenario.name}</Text>
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  创建于 {new Date(scenario.created_at).toLocaleString()}
                </Text>
                <div style={{ marginTop: 8 }}>{scenario.description}</div>
              </Col>
              <Col span={8} style={{ textAlign: 'right' }}>
                <Text type="secondary">
                  实体: {scenario.entity_count || 0} | 文档: {scenario.doc_count || 0}
                </Text>
              </Col>
            </Row>
          </Card>
        ))}
      </Card>
    </div>
  );
}