import { useState } from 'react';
import { Card, Input, Button, Timeline, Tag, Space, Spin, Typography, Tabs, Descriptions, Tooltip } from 'antd';
import { SendOutlined, ThunderboltOutlined, BranchesOutlined } from '@ant-design/icons';
import { useAgentStore } from '../stores/agentStore';
import type { DecisionStep } from '../services/agentApi';
import { AdvancedTable } from '@/modules/shared';

const { Title, Text } = Typography;

/** 截断 UUID 显示，保留前 8 位 */
const shortId = (id: string) => id.length > 12 ? id.slice(0, 8) : id;

/** 格式化 ISO 时间戳为可读格式 */
const formatTime = (ts: string) => {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return ts;
  }
};

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
    {
      title: 'ID',
      dataIndex: 'decision_id',
      key: 'id',
      width: 100,
      render: (id: string) => <Tooltip title={id}>{shortId(id)}</Tooltip>,
    },
    {
      title: 'Task',
      dataIndex: 'task_id',
      key: 'task',
      width: 100,
      render: (id: string) => <Tooltip title={id}>{shortId(id)}</Tooltip>,
    },
    { title: 'Steps', dataIndex: 'steps_count', key: 'steps' },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created',
      render: (ts: string) => formatTime(ts),
    },
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
              <Space orientation="vertical" style={{ width: '100%' }} size="large">
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
                    <Descriptions variant="bordered" size="small" style={{ marginTop: 16 }} column={2}>
                      <Descriptions.Item label="Task ID"><Tooltip title={lastDispatch.task_id}>{shortId(lastDispatch.task_id)}</Tooltip></Descriptions.Item>
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
                <AdvancedTable
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
              <Card title={<span>Decision Chain: <Tooltip title={currentChain.decision_id}>{shortId(currentChain.decision_id)}</Tooltip></span>}>
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
