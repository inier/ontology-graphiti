import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Empty, Typography } from 'antd';
import { QAPage } from '../../qa/pages/QAPage';

const { Text } = Typography;

export function AgentChat() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();

  if (!agentId) {
    return (
      <Empty description="缺少智能体ID" style={{ marginTop: 120 }}>
        <Button type="primary" onClick={() => navigate('/my-agents')}>
          返回智能体列表
        </Button>
      </Empty>
    );
  }

  return <QAPage agentId={agentId} />;
}
