import { useState, useEffect } from 'react';

import { Card, Avatar, Tag, Row, Col, Typography, Button, message } from 'antd';

import { RobotOutlined, EyeOutlined, MessageOutlined } from '@ant-design/icons';

import { useNavigate } from 'react-router-dom';

import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';

import { agentApi } from '../services/agentApi';
import { api } from '@/modules/shared/services/api';
import type { Agent } from '../types';

import { useAuthStore } from '@/modules/shared/stores/authStore';

import { useWorkspace } from '@/modules/shared/components/LayoutContexts';

import { EmptyState } from '@/modules/shared/components/organisms';



const { Paragraph } = Typography;



export function MyAgents() {

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [skillMap, setSkillMap] = useState<Record<string, string>>({});

  const { user } = useAuthStore();

  const { currentWorkspace } = useWorkspace();

  const navigate = useNavigate();

  const { show: showGlobalLoading, hide: hideGlobalLoading } = useGlobalLoading();



  useEffect(() => {
    if (!user) return;
    loadSkills();
    loadAgents();
  }, [user, currentWorkspace]);


  const loadSkills = async () => {
    try {
      const res = await api.get<{ skills: Array<{ skill_id: string; name: string }> }>('/api/skill/skills?page_size=200');
      const map: Record<string, string> = {};
      for (const s of res.skills || []) {
        if (s.skill_id) map[s.skill_id] = s.name;
      }
      setSkillMap(map);
    } catch (_) {
    }
  };


  const loadAgents = async () => {
    const roleId = user?.role_id;

    setLoading(true);
    showGlobalLoading('加载智能体列表...');

    try {
      let data: Agent[] = [];

      if (roleId) {
        try {
          data = await agentApi.listAgentsByRole(roleId, currentWorkspace);
        } catch (_) {
          try {
            data = await agentApi.listAgents({ roleId, workspaceId: currentWorkspace });
          } catch (__) {
            data = [];
          }
        }
      } else {
        try {
          data = await agentApi.listAgents({ workspaceId: currentWorkspace });
        } catch (_) {
          data = [];
        }
      }

      if (data.length === 0 && currentWorkspace) {
        try {
          data = await agentApi.listAgents({});
        } catch (_) {
          data = [];
        }
      }

      setAgents(data);
    } finally {
      setLoading(false);
      hideGlobalLoading();
    }
  };



  const handleView = (agent: Agent) => {

    navigate(`/agent-chat/${agent.agent_id}`);

  };



  if (loading) {

    return <div style={{ minHeight: 300 }} />;

  }



  if (agents.length === 0) {

    return (

      <EmptyState

        icon={<RobotOutlined />}

        title="暂无可用智能体"

        description="当前角色下没有可用的数字员工，您可以创建新的智能体或加载示例数据"

        actionLabel="创建智能体"

        onAction={() => navigate('/agent-management')}

        showSampleData

        onLoadSampleData={async () => {

          if (!currentWorkspace) { message.warning('请先选择工作空间'); return; }

          try {

            const { api } = await import('@/modules/shared/services/api');

            await api.generateSampleData(currentWorkspace);

            message.success('示例数据已加载');

            loadAgents();

          } catch (e) { message.error('加载示例数据失败'); }

        }}

      />

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
              style={{ borderRadius: 12, height: '100%', cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
              styles={{ body: { padding: 20 } }}
              onClick={() => handleView(agent)}
              actions={[
                <Button
                  key="view"
                  type="link"
                  icon={<EyeOutlined />}
                  onClick={(e) => { e.stopPropagation(); handleView(agent); }}
                >
                  查看
                </Button>,
                <Button
                  key="chat"
                  type="link"
                  icon={<MessageOutlined />}
                  onClick={(e) => { e.stopPropagation(); handleView(agent); }}
                >
                  对话
                </Button>,
              ]}
            >

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>

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

                  {agent.related_skills.slice(0, 3).map(sk => {
                    const resolvedName = agent.resolved_names?.skill_names?.[sk] || skillMap[sk];
                    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sk);
                    if (resolvedName) {
                      return <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{resolvedName}</Tag>;
                    }
                    if (isUuid) {
                      return <Tag key={sk} color="default" style={{ fontSize: 11, color: '#bfbfbf' }} title={sk}>已删除: {sk.slice(0, 8)}...</Tag>;
                    }
                    return <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{sk}</Tag>;
                  })}

                  {agent.related_skills.length > 3 && (

                    <Tag style={{ fontSize: 11 }}>+{agent.related_skills.length - 3}</Tag>

                  )}

                </div>

              </div>

            </Card>

          </Col>

        ))}

      </Row>

    </div>

  );

}

