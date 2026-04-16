import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Button, Space, message } from 'antd';
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import type { Scenario, Stats } from '../types';

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, scenariosData] = await Promise.all([
        api.getStats(),
        api.listScenarios(),
      ]);
      setStats(statsData);
      setScenarios(Array.isArray(scenariosData) ? scenariosData : []);
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const columns = [
    {
      title: 'ID',
      dataIndex: 'scenario_id',
      key: 'id',
      render: (id: string) => <Tag>{id?.substring(0, 8) || 'N/A'}</Tag>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => name || '未命名',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created',
      render: (date: string) => date ? new Date(date).toLocaleString() : 'N/A',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Scenario) => (
        <Button type="link" onClick={() => message.info(`查看场景: ${record.name}`)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Row gutter={16}>
          <Col span={6}>
            <Card>
              <Statistic
                title="摄入数量"
                value={stats?.pipeline?.ingest_count ?? 0}
                loading={loading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="错误数量"
                value={stats?.pipeline?.error_count ?? 0}
                loading={loading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="版本数量"
                value={stats?.pipeline?.version_count ?? 0}
                loading={loading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="场景数量"
                value={stats?.scenarios ?? 0}
                loading={loading}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title="场景列表"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={loadData}>
                刷新
              </Button>
              <Button type="primary" icon={<PlusOutlined />}>
                新建场景
              </Button>
            </Space>
          }
        >
          <Table
            columns={columns}
            dataSource={scenarios}
            rowKey="scenario_id"
            loading={loading}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      </Space>
    </div>
  );
}
