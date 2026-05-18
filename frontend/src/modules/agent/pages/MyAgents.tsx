import { useState, useEffect } from 'react';
import { Card, Button, Input, Empty, Avatar, Tag, message, Spin } from 'antd';
import { SearchOutlined, MessageOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { agentApi } from '../services/agentApi';
import type { Agent } from '../types';

export function MyAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();

  // 当前用户角色（从 localStorage 或 context 获取，这里模拟）
  const currentRoleId = localStorage.getItem('currentRoleId') || localStorage.getItem('role') || 'user';

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    try {
      // 按角色过滤获取智能体
      const data = await agentApi.listAgentsByRole(currentRoleId);
      setAgents(data);
    } catch (e) {
      // 降级：如果按角色查询失败，获取全部
      try {
        const allData = await agentApi.listAgents();
        setAgents(allData);
      } catch (_) {
        message.error('加载智能体列表失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(searchText.toLowerCase()) ||
    a.display_name.toLowerCase().includes(searchText.toLowerCase())
  );

  const handleChat = (agent: Agent) => {
    navigate(`/agent-chat/${agent.agent_id}`);
  };

  const handleAdmin = () => {
    navigate('/admin');
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
        <div style={{ display: 'flex', gap: 8 }}>
          {['https://api.dicebear.com/7.x/avataaars/svg?seed=1',
            'https://api.dicebear.com/7.x/avataaars/svg?seed=2',
            'https://api.dicebear.com/7.x/avataaars/svg?seed=3',
            'https://api.dicebear.com/7.x/avataaars/svg?seed=4',
            'https://api.dicebear.com/7.x/avataaars/svg?seed=5',
            'https://api.dicebear.com/7.x/avataaars/svg?seed=6',
          ].map((url, i) => (
            <Avatar key={i} src={url} size={40} style={{ opacity: 0.5 + i * 0.08 }} />
          ))}
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 700, margin: 0 }}>ODAP 智能体</h1>
        <p style={{ fontSize: 16, color: '#8c8c8c', margin: 0 }}>
          联系管理员为你分配工作角色，即刻拥有自己的专属企业级工作搭子！
        </p>
        <Button type="primary" icon={<SettingOutlined />} onClick={handleAdmin}>
          管理后台
        </Button>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>数字员工</h2>
          <p style={{ margin: '4px 0 0', color: '#8c8c8c', fontSize: 14 }}>
            当前组织共创建了 {agents.length} 个数字员工
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Input.Search
            placeholder="搜索数字员工"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{ width: 240 }}
            allowClear
            prefix={<SearchOutlined />}
          />
          <Button icon={<SettingOutlined />} onClick={handleAdmin}>
            管理后台
          </Button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20 }}>
        {filteredAgents.map(agent => (
          <Card
            key={agent.agent_id}
            hoverable
            style={{ borderRadius: 12, overflow: 'hidden' }}
            styles={{ body: { padding: 20 } }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <Avatar src={agent.avatar} size={72} style={{ border: '2px solid #f0f0f0' }} />
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 16, fontWeight: 600 }}>{agent.display_name}</div>
                <Tag color="blue" style={{ marginTop: 4, fontSize: 11 }}>主对象: {agent.main_object}</Tag>
              </div>
              <p style={{ fontSize: 13, color: '#8c8c8c', textAlign: 'center', margin: 0, lineHeight: 1.5, minHeight: 40 }}>
                {agent.description || '暂无描述'}
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center' }}>
                {agent.related_skills.slice(0, 3).map(sk => (
                  <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{sk}</Tag>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 8, width: '100%', marginTop: 8 }}>
                <Button style={{ flex: 1 }} size="small">授权管理</Button>
                <Button type="primary" style={{ flex: 1 }} size="small" icon={<MessageOutlined />} onClick={() => handleChat(agent)}>
                  语义图谱
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {filteredAgents.length === 0 && (
        <Empty description="未找到匹配的智能体" style={{ marginTop: 60 }} />
      )}
    </div>
  );
}
