import { useState, useEffect } from 'react';
import { Card, Empty, Avatar, Tag, Spin, Row, Col, Typography, Button } from 'antd';
import { RobotOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { agentApi } from '../services/agentApi';
import type { Agent } from '../types';
import { useAuthStore } from '../../shared/stores/authStore';
import { useWorkspace } from '../../shared/components/AppLayout';

const { Paragraph } = Typography;

export function MyAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const { user } = useAuthStore();
  const { currentWorkspace } = useWorkspace();
  const navigate = useNavigate();

  useEffect(() => {
    loadAgents();
  }, [user?.role_id, currentWorkspace]);

  const loadAgents = async () => {
    const roleId = user?.role_id;
    if (!roleId) return;
    setLoading(true);
    try {
      const data = await agentApi.listAgentsByRole(roleId, currentWorkspace);
      setAgents(data);
    } catch (e) {
      try {
        const allData = await agentApi.listAgents({ roleId, workspaceId: currentWorkspace });
        setAgents(allData);
      } catch (_) {
        setAgents([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleView = (agent: Agent) => {
    navigate(`/agent-chat/${agent.agent_id}`);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '80vh', gap: 24 }}>
        <RobotOutlined style={{ fontSize: 64, color: '#1890ff', opacity: 0.6 }} />
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>暂无可用智能体</h1>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>我的数字员工</h2>
        <p style={{ margin: '4px 0 0', color: '#8c8c8c', fontSize: 14 }}>
          当前角色下共 {agents.length} 个可用数字员工，点击进入专属问答
        </p>
      </div>

      <Row gutter={[20, 20]}>
        {agents.map(agent => (
          <Col key={agent.agent_id} xs={24} sm={12} md={8} lg={6}>
            <Card
              hoverable
              style={{ borderRadius: 12, height: '100%', cursor: 'pointer' }}
              styles={{ body: { padding: 20, display: 'flex', flexDirection: 'column', height: '100%' } }}
              onClick={() => handleView(agent)}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, flex: 1 }}>
                <Avatar src={agent.avatar} size={72} style={{ border: '2px solid #f0f0f0', flexShrink: 0 }} />
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{agent.display_name}</div>
                </div>
                <Paragraph
                  style={{ fontSize: 13, color: '#8c8c8c', textAlign: 'center', margin: 0, lineHeight: 1.5, minHeight: 40 }}
                  ellipsis={{ rows: 2 }}
                >
                  {agent.description || '暂无描述'}
                </Paragraph>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center' }}>
                  {agent.related_skills.slice(0, 3).map(sk => (
                    <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{agent.ref_labels?.[sk] || sk}</Tag>
                  ))}
                  {agent.related_skills.length > 3 && (
                    <Tag style={{ fontSize: 11 }}>+{agent.related_skills.length - 3}</Tag>
                  )}
                </div>
                <Button
                  type="primary"
                  style={{ width: '100%', marginTop: 'auto' }}
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={(e) => { e.stopPropagation(); handleView(agent); }}
                >
                  查看
                </Button>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
