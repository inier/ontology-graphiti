import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Empty, Typography } from 'antd';
import { QAPage } from '@/modules/qa/pages/QAPage';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

export function AgentChat() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { t } = useI18n();

  if (!agentId) {
    return (
      <Empty description={t('缺少智能体ID')} style={{ marginTop: 120 }}>
        <Button type="primary" onClick={() => navigate('/my-agents')}>
          {t('返回智能体列表')}
        </Button>
      </Empty>
    );
  }

  return <QAPage agentId={agentId} />;
}
