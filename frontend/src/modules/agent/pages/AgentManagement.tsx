import { useState, useEffect } from 'react';
import { Card, Button, Input, Modal, Form, message, Avatar, Tag, Space, Table, Popconfirm, Select, Divider, Descriptions } from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { agentApi } from '../services/agentApi';
import { api } from '../../shared/services/api';
import { processApi, ruleApi, logicApi, indicatorApi } from '../../business/services/businessApi';
import { knowledgeApi } from '../../knowledge/services/knowledgeApi';
import { useScenario } from '../../shared/components/AppLayout';
import type { Agent, AgentFormData } from '../types';

const AVATAR_OPTIONS = Array.from({ length: 10 }, (_, i) =>
  `https://api.dicebear.com/7.x/avataaars/svg?seed=${i + 1}`
);

interface RefOption {
  id: string;
  name: string;
}

export function AgentManagement() {
  const { currentScenario } = useScenario();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [viewingAgent, setViewingAgent] = useState<Agent | null>(null);
  const [form] = Form.useForm<AgentFormData>();
  const [selectedAvatar, setSelectedAvatar] = useState(AVATAR_OPTIONS[0]);

  // 关联选项 - 从本体版本配置获取
  const [entityOptions, setEntityOptions] = useState<RefOption[]>([]);
  const [businessLogicOptions, setBusinessLogicOptions] = useState<RefOption[]>([]);
  const [indicatorOptions, setIndicatorOptions] = useState<RefOption[]>([]);
  const [skillOptions, setSkillOptions] = useState<RefOption[]>([]);
  const [knowledgeBaseOptions, setKnowledgeBaseOptions] = useState<RefOption[]>([]);
  const [roleOptions, setRoleOptions] = useState<RefOption[]>([]);

  useEffect(() => {
    loadAgents();
    loadRefOptions();
  }, []);

  // 当场景变化时重新加载关联选项
  useEffect(() => {
    if (currentScenario) {
      loadEntityOptions();
    }
  }, [currentScenario]);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await agentApi.listAgents();
      setAgents(data);
    } catch (e) {
      message.error('加载智能体列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 从当前本体版本获取实体类型
  const loadEntityOptions = async () => {
    if (!currentScenario) return;
    try {
      // 通过 buildGraph API 获取当前场景的实体类型
      const result = await api.buildGraph('', currentScenario);
      if (result.entities) {
        const options = result.entities
          .filter((e: any) => e.type === 'EntityType' || e.type === 'entity_type')
          .map((e: any) => ({
            id: e.id || e.name,
            name: e.name || e.id,
          }));
        // 如果没有专门的实体类型，使用所有实体的类型去重
        if (options.length === 0) {
          const typeSet = new Set<string>();
          result.entities.forEach((e: any) => {
            if (e.type) typeSet.add(e.type);
          });
          typeSet.forEach(type => {
            options.push({ id: type, name: type });
          });
        }
        setEntityOptions(options);
      }
    } catch (e) {
      console.warn('加载实体类型失败', e);
      // 降级：尝试从 entities API 获取
      try {
        const entities = await api.getEntities(currentScenario);
        const typeSet = new Map<string, string>();
        entities.forEach((e: any) => {
          if (e.type && !typeSet.has(e.type)) {
            typeSet.set(e.type, e.type);
          }
        });
        setEntityOptions(Array.from(typeSet.entries()).map(([id, name]) => ({ id, name })));
      } catch (e2) {
        console.warn('降级加载实体类型失败', e2);
      }
    }
  };

  const loadRefOptions = async () => {
    try {
      // 并行加载所有关联选项
      const [
        businessLogics,
        indicators,
        skills,
        knowledgeBases,
        roles,
      ] = await Promise.all([
        // 业务逻辑：包含业务过程、规则、逻辑
        Promise.all([
          processApi.list().catch(() => []),
          ruleApi.list().catch(() => []),
          logicApi.list().catch(() => []),
        ]).then(([ps, rs, ls]) => [
          ...ps.map(p => ({ id: p.process_id, name: p.display_name || p.name })),
          ...rs.map(r => ({ id: r.rule_id, name: r.display_name || r.name })),
          ...ls.map(l => ({ id: l.logic_id, name: l.display_name || l.name })),
        ]),
        // 指标
        indicatorApi.list().catch(() => []).then(items =>
          items.map(i => ({ id: i.indicator_id, name: i.display_name || i.name }))
        ),
        // 技能
        api.listSkills().catch(() => ({ skills: [] })).then(r =>
          r.skills.map((s: any) => ({ id: s.skill_id || s.name, name: s.name }))
        ),
        // 知识库
        knowledgeApi.listKnowledgeBases().catch(() => []).then(items =>
          items.map(k => ({ id: k.kb_id, name: k.name }))
        ),
        // 角色
        api.listRoles().catch(() => ({ roles: [] })).then(r =>
          r.roles.map((role: any) => ({ id: role.role_id, name: role.name }))
        ),
      ]);

      setBusinessLogicOptions(businessLogics);
      setIndicatorOptions(indicators);
      setSkillOptions(skills);
      setKnowledgeBaseOptions(knowledgeBases);
      setRoleOptions(roles);
    } catch (e) {
      console.warn('加载关联选项失败', e);
    }
  };

  const handleCreate = () => {
    setEditingAgent(null);
    form.resetFields();
    setSelectedAvatar(AVATAR_OPTIONS[0]);
    setModalOpen(true);
  };

  const handleEdit = (agent: Agent) => {
    setEditingAgent(agent);
    form.setFieldsValue({
      name: agent.name,
      display_name: agent.display_name,
      avatar: agent.avatar,
      description: agent.description,
      main_object: agent.main_object,
      related_objects: agent.related_objects,
      related_business_logic: agent.related_business_logic,
      related_indicators: agent.related_indicators,
      related_skills: agent.related_skills,
      related_knowledge_bases: agent.related_knowledge_bases,
      allowed_roles: agent.allowed_roles,
    });
    setSelectedAvatar(agent.avatar);
    setModalOpen(true);
  };

  const handleView = (agent: Agent) => {
    setViewingAgent(agent);
    setDetailOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await agentApi.deleteAgent(id);
      message.success('删除成功');
      loadAgents();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleSave = async (values: AgentFormData) => {
    try {
      const payload = { ...values, avatar: selectedAvatar };
      if (editingAgent) {
        await agentApi.updateAgent(editingAgent.agent_id, payload);
        message.success('更新成功');
      } else {
        await agentApi.createAgent(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      loadAgents();
    } catch (e) {
      message.error('保存失败');
    }
  };

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(searchText.toLowerCase()) ||
    a.display_name.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: '头像',
      dataIndex: 'avatar',
      width: 70,
      render: (url: string) => <Avatar src={url} size={40} />,
    },
    {
      title: '名称',
      dataIndex: 'display_name',
      render: (_: string, record: Agent) => (
        <div>
          <div style={{ fontWeight: 600 }}>{record.display_name}</div>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>{record.name}</div>
        </div>
      ),
    },
    {
      title: '主对象',
      dataIndex: 'main_object',
      width: 100,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '关联业务逻辑',
      dataIndex: 'related_business_logic',
      width: 120,
      render: (items: string[]) => (
        <Space size={4} wrap>
          {items.slice(0, 2).map(o => <Tag key={o} color="cyan">{o}</Tag>)}
          {items.length > 2 && <Tag>+{items.length - 2}</Tag>}
        </Space>
      ),
    },
    {
      title: '关联指标',
      dataIndex: 'related_indicators',
      width: 100,
      render: (items: string[]) => (
        <Space size={4} wrap>
          {items.slice(0, 2).map(o => <Tag key={o} color="orange">{o}</Tag>)}
          {items.length > 2 && <Tag>+{items.length - 2}</Tag>}
        </Space>
      ),
    },
    {
      title: '可用技能',
      dataIndex: 'related_skills',
      width: 100,
      render: (items: string[]) => (
        <Space size={4} wrap>
          {items.slice(0, 2).map(o => <Tag key={o} color="purple">{o}</Tag>)}
          {items.length > 2 && <Tag>+{items.length - 2}</Tag>}
        </Space>
      ),
    },
    {
      title: '可见角色',
      dataIndex: 'allowed_roles',
      width: 100,
      render: (items: string[]) => (
        <Space size={4} wrap>
          {items.slice(0, 2).map(o => <Tag key={o} color="green">{o}</Tag>)}
          {items.length > 2 && <Tag>+{items.length - 2}</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      width: 140,
      fixed: 'right' as const,
      render: (_: unknown, record: Agent) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => handleView(record)} title="查看" />
          <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} title="编辑" />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.agent_id)}>
            <Button type="text" danger icon={<DeleteOutlined />} title="删除" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="智能体管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新建智能体
        </Button>
      }
    >
      <Input.Search
        placeholder="搜索智能体名称或展示名"
        value={searchText}
        onChange={e => setSearchText(e.target.value)}
        style={{ width: 320, marginBottom: 16 }}
        allowClear
        prefix={<SearchOutlined />}
      />
      <Table
        dataSource={filteredAgents}
        columns={columns}
        rowKey="agent_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1000 }}
      />

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editingAgent ? '编辑智能体' : '新建智能体'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        width={720}
        destroyOnClose
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="name"
            label="智能体名称"
            rules={[{ required: true, message: '请输入智能体名称' }]}
          >
            <Input placeholder="仅支持英文和下划线" maxLength={20} showCount />
          </Form.Item>

          <Form.Item
            name="display_name"
            label="前台展示名称"
            rules={[{ required: true, message: '请输入前台展示名称' }]}
          >
            <Input placeholder="请输入前台展示名称" maxLength={20} showCount />
          </Form.Item>

          <Form.Item label="形象" required>
            <Space size={12} wrap>
              {AVATAR_OPTIONS.map(url => (
                <div
                  key={url}
                  onClick={() => setSelectedAvatar(url)}
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    border: selectedAvatar === url ? '2px solid #1890ff' : '2px solid transparent',
                    padding: 2,
                  }}
                >
                  <img src={url} style={{ width: '100%', height: '100%', borderRadius: '50%' }} />
                </div>
              ))}
            </Space>
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea
              placeholder="此运营对象所服务的具体业务场景、核心目标和用户群体等描述"
              maxLength={1000}
              showCount
              rows={3}
            />
          </Form.Item>

          <Divider>对象关联</Divider>

          <Form.Item
            name="main_object"
            label="主对象"
            rules={[{ required: true, message: '请选择主对象' }]}
          >
            <Select
              placeholder="请选择主对象"
              options={entityOptions.map(v => ({ value: v.id, label: v.name }))}
              showSearch
              optionFilterProp="label"
              notFoundContent={currentScenario ? '暂无实体类型' : '请先选择场景'}
            />
          </Form.Item>

          <Form.Item name="related_objects" label="关联对象类型">
            <Select
              mode="multiple"
              placeholder="请选择关联对象类型"
              options={entityOptions.map(v => ({ value: v.id, label: v.name }))}
              showSearch
              optionFilterProp="label"
              notFoundContent={currentScenario ? '暂无实体类型' : '请先选择场景'}
            />
          </Form.Item>

          <Divider>业务关联</Divider>

          <Form.Item name="related_business_logic" label="关联业务逻辑">
            <Select
              mode="multiple"
              placeholder="请选择关联的业务逻辑"
              options={businessLogicOptions.map(o => ({ value: o.id, label: o.name }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item name="related_indicators" label="关联指标（分析视图）">
            <Select
              mode="multiple"
              placeholder="请选择关联的指标"
              options={indicatorOptions.map(o => ({ value: o.id, label: o.name }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item name="related_skills" label="可用技能">
            <Select
              mode="multiple"
              placeholder="请选择可用技能"
              options={skillOptions.map(o => ({ value: o.id, label: o.name }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item name="related_knowledge_bases" label="关联知识库">
            <Select
              mode="multiple"
              placeholder="请选择关联的知识库"
              options={knowledgeBaseOptions.map(o => ({ value: o.id, label: o.name }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Divider>权限配置</Divider>

          <Form.Item
            name="allowed_roles"
            label="可见角色（哪些角色可以看到和使用此智能体）"
            rules={[{ required: true, message: '请至少选择一个可见角色' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择可见角色"
              options={roleOptions.map(o => ({ value: o.id, label: o.name }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title="智能体详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={[
          <Button key="close" onClick={() => setDetailOpen(false)}>关闭</Button>,
        ]}
        width={600}
      >
        {viewingAgent && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
              <Avatar src={viewingAgent.avatar} size={64} />
              <div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{viewingAgent.display_name}</div>
                <div style={{ color: '#8c8c8c' }}>{viewingAgent.name}</div>
              </div>
            </div>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="主对象">
                <Tag color="blue">{viewingAgent.main_object}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="关联对象">
                <Space wrap>
                  {viewingAgent.related_objects.map(o => <Tag key={o}>{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="关联业务逻辑">
                <Space wrap>
                  {viewingAgent.related_business_logic.map(o => <Tag key={o} color="cyan">{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="关联指标">
                <Space wrap>
                  {viewingAgent.related_indicators.map(o => <Tag key={o} color="orange">{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="可用技能">
                <Space wrap>
                  {viewingAgent.related_skills.map(o => <Tag key={o} color="purple">{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="关联知识库">
                <Space wrap>
                  {viewingAgent.related_knowledge_bases.map(o => <Tag key={o} color="geekblue">{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="可见角色">
                <Space wrap>
                  {viewingAgent.allowed_roles.map(o => <Tag key={o} color="green">{o}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="描述">{viewingAgent.description || '—'}</Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>
    </Card>
  );
}
