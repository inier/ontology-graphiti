import { useState } from 'react';
import { Card, Input, Button, Timeline, Table, Tag, Space, Spin, Typography, Tabs, Descriptions } from 'antd';
import { SendOutlined, ThunderboltOutlined, BranchesOutlined } from '@ant-design/icons';
import { useAgentStore } from '../stores/agentStore';
import type { DecisionStep } from '../services/agentApi';

const { Title, Text } = Typography;

const PHASE_COLORS: Record<string, string> = {
  observe: 'blue',
  orient: 'cyan',
  decide: 'orange',
  act: 'green',
};

export function AgentPage() {
  const [intent, setIntent] = useState('');
  const { lastDispatch, currentChain, decisions, loading, error, dispatch, getDecisionChain, loadDecisions } = useAgentStore();
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);

  const handleDispatch = async () => {
    if (!intent.trim()) return;
    await dispatch(intent.trim());
    setIntent('');
  };

  const handleViewChain = async (decisionId: string) => {
    setSelectedDecisionId(decisionId);
    await getDecisionChain(decisionId);
  };

  const handleLoadDecisions = async () => {
    await loadDecisions(undefined, 1, 20);
  };

  const decisionColumns = [
    { title: 'ID', dataIndex: 'decision_id', key: 'id', ellipsis: true },
    { title: 'Task', dataIndex: 'task_id', key: 'task', ellipsis: true },
    { title: 'Steps', dataIndex: 'steps_count', key: 'steps' },
    { title: 'Created', dataIndex: 'created_at', key: 'created', ellipsis: true },
    {
      title: 'Action',
      key: 'action',
      render: (_: unknown, record: { decision_id: string }) => (
        <Button size="small" type="link" onClick={() => handleViewChain(record.decision_id)}>
          View Chain
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>Agent Dispatch Center</Title>

      <Tabs
        items={[
          {
            key: 'dispatch',
            label: 'Dispatch',
            icon: <ThunderboltOutlined />,
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <Card title="Intent Dispatch">
                  <Space.Compact style={{ width: '100%' }}>
                    <Input
                      size="large"
                      placeholder="Enter intent, e.g. Analyze B-area threats"
                      value={intent}
                      onChange={(e) => setIntent(e.target.value)}
                      onPressEnter={handleDispatch}
                    />
                    <Button type="primary" size="large" icon={<SendOutlined />} onClick={handleDispatch} loading={loading}>
                      Dispatch
                    </Button>
                  </Space.Compact>

                  {error && <Text type="danger">{error}</Text>}

                  {lastDispatch && (
                    <Descriptions bordered size="small" style={{ marginTop: 16 }} column={2}>
                      <Descriptions.Item label="Task ID">{lastDispatch.task_id}</Descriptions.Item>
                      <Descriptions.Item label="Assigned Agent">
                        <Tag color="blue">{lastDispatch.assigned_agent}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Confidence">{(lastDispatch.confidence * 100).toFixed(1)}%</Descriptions.Item>
                      <Descriptions.Item label="Source">{lastDispatch.routing_source}</Descriptions.Item>
                      <Descriptions.Item label="Status">
                        <Tag color="green">{lastDispatch.status}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Plan Steps">{lastDispatch.plan.length}</Descriptions.Item>
                    </Descriptions>
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: 'decisions',
            label: 'Decisions',
            icon: <BranchesOutlined />,
            children: (
              <Card
                title="Decision Records"
                extra={<Button onClick={handleLoadDecisions} loading={loading}>Refresh</Button>}
              >
                <Table
                  dataSource={decisions.decisions}
                  columns={decisionColumns}
                  rowKey="decision_id"
                  size="small"
                  pagination={{ pageSize: 10 }}
                />
              </Card>
            ),
          },
          {
            key: 'chain',
            label: 'Decision Chain',
            children: currentChain ? (
              <Card title={`Decision Chain: ${currentChain.decision_id}`}>
                <Timeline
                  items={currentChain.steps.map((step: DecisionStep) => ({
                    color: PHASE_COLORS[step.phase] || 'gray',
                    children: (
                      <div>
                        <Tag color={PHASE_COLORS[step.phase]}>{step.phase.toUpperCase()}</Tag>
                        <Text>{step.description}</Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: 12 }}>{step.timestamp}</Text>
                      </div>
                    ),
                  }))}
                />
                {currentChain.reasoning && (
                  <Card size="small" title="Reasoning" style={{ marginTop: 16 }}>
                    <Text>{currentChain.reasoning}</Text>
                  </Card>
                )}
              </Card>
            ) : (
              <Card>
                <Text type="secondary">Select a decision to view its chain.</Text>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
