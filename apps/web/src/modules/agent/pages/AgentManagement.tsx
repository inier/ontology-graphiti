import { useState, useEffect } from 'react';

import { Card, Button, Input, Modal, Form, message, Avatar, Tag, Space, Popconfirm, Select, Divider, Descriptions, Row, Col, Typography, Tooltip, Spin } from 'antd';

import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, EyeOutlined, RobotOutlined, MoreOutlined } from '@ant-design/icons';

import { agentApi } from '../services/agentApi';

import { api } from '@/modules/shared/services/api';

import { processApi, ruleApi, logicApi, indicatorApi } from '@/modules/business/services/businessApi';

import { knowledgeApi } from '@/modules/knowledge/services/knowledgeApi';

import { useScenario, useWorkspace } from '@/modules/shared/components/LayoutContexts';

import type { Agent, AgentFormData } from '../types';
import { useI18n } from '@/modules/shared/hooks/useI18n';



const { Paragraph } = Typography;



const AVATAR_OPTIONS = [

  'https://api.dicebear.com/7.x/shapes/svg?seed=agent1&backgroundColor=c0aede',

  'https://api.dicebear.com/7.x/shapes/svg?seed=agent2&backgroundColor=d1d4f9',

  'https://api.dicebear.com/7.x/shapes/svg?seed=agent3&backgroundColor=b6e3f4',

  'https://api.dicebear.com/7.x/shapes/svg?seed=agent4&backgroundColor=ffd5dc',

  'https://api.dicebear.com/7.x/shapes/svg?seed=agent5&backgroundColor=ffdfbf',

  'https://api.dicebear.com/7.x/identicon/svg?seed=analyst&backgroundColor=c0aede',

  'https://api.dicebear.com/7.x/identicon/svg?seed=director&backgroundColor=b6e3f4',

  'https://api.dicebear.com/7.x/identicon/svg?seed=operator&backgroundColor=d1d4f9',

  'https://api.dicebear.com/7.x/identicon/svg?seed=scout&backgroundColor=ffd5dc',

  'https://api.dicebear.com/7.x/identicon/svg?seed=advisor&backgroundColor=ffdfbf',

  'https://api.dicebear.com/7.x/initials/svg?seed=AI&backgroundColor=1890ff',

  'https://api.dicebear.com/7.x/initials/svg?seed=QA&backgroundColor=722ed1',

  'https://api.dicebear.com/7.x/initials/svg?seed=OP&backgroundColor=13c2c2',

  'https://api.dicebear.com/7.x/initials/svg?seed=DT&backgroundColor=eb2f96',

  'https://api.dicebear.com/7.x/initials/svg?seed=KV&backgroundColor=fa8c16',

];



interface RefOption {

  id: string;

  name: string;

}



export function AgentManagement() {

  const { currentScenario } = useScenario();

  const { currentWorkspace } = useWorkspace();
  const { t } = useI18n();

  const [agents, setAgents] = useState<Agent[]>([]);

  const [loading, setLoading] = useState(false);

  const [searchText, setSearchText] = useState('');

  const [modalOpen, setModalOpen] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);

  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  const [viewingAgent, setViewingAgent] = useState<Agent | null>(null);

  const [form] = Form.useForm<AgentFormData>();

  const [selectedAvatar, setSelectedAvatar] = useState(AVATAR_OPTIONS[0]);



  const [entityOptions, setEntityOptions] = useState<RefOption[]>([]);

  const [processOptions, setProcessOptions] = useState<RefOption[]>([]);

  const [ruleOptions, setRuleOptions] = useState<RefOption[]>([]);

  const [businessLogicOptions, setBusinessLogicOptions] = useState<RefOption[]>([]);

  const [indicatorOptions, setIndicatorOptions] = useState<RefOption[]>([]);

  const [skillOptions, setSkillOptions] = useState<RefOption[]>([]);

  const [knowledgeBaseOptions, setKnowledgeBaseOptions] = useState<RefOption[]>([]);

  const [roleOptions, setRoleOptions] = useState<RefOption[]>([]);

  const [workspaceOptions, setWorkspaceOptions] = useState<RefOption[]>([]);

  const [workspaceFilter, setWorkspaceFilter] = useState<string | undefined>(undefined);



  useEffect(() => {

    loadAgents();

    loadRefOptions();

  }, []);



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

      message.error(t('加载智能体列表失败'));

    } finally {

      setLoading(false);

    }

  };



  const loadEntityOptions = async () => {

    try {

      const schema = await api.getOntologySchema();

      const entityTypes = schema?.entity_types || {};

      const options = Object.keys(entityTypes).map(key => ({ id: key, name: key }));

      if (options.length > 0) {

        setEntityOptions(options);

        return;

      }

    } catch (e) {

      console.warn('getOntologySchema 加载实体类型失败', e);

    }

    try {

      const result = await api.queryEntities({}, currentWorkspace || undefined);

      const typeSet = new Set<string>();

      (result.entities || []).forEach((e: any) => {

        const t = e.type || e.entity_type;

        if (t) typeSet.add(t);

      });

      if (typeSet.size > 0) {

        setEntityOptions(Array.from(typeSet).map(t => ({ id: t, name: t })));

      }

    } catch (e) {

      console.warn('queryEntities 加载实体类型失败', e);

    }

  };



  const loadRefOptions = async () => {

    try {

      const [

        processes,

        rules,

        businessLogics,

        indicators,

        skills,

        knowledgeBases,

        roles,

        workspaces,

      ] = await Promise.all([

        processApi.list().catch(() => []).then(items =>

          items.map((p: any) => ({ id: p.process_id || p.name, name: p.display_name || p.name }))

        ),

        ruleApi.list().catch(() => []).then(items =>

          items.map((r: any) => ({ id: r.rule_id || r.name, name: r.display_name || r.name }))

        ),

        logicApi.list().catch(() => []).then(items =>

          items.map((l: any) => ({ id: l.logic_id || l.name, name: l.display_name || l.name }))

        ),

        indicatorApi.list().catch(() => []).then(items =>

          items.map((i: any) => ({ id: i.indicator_id || i.name, name: i.display_name || i.name }))

        ),

        api.listSkills().catch(() => ({ skills: [] })).then(r =>

          r.skills.map((s: any) => ({ id: s.skill_id || s.name, name: s.name }))

        ),

        knowledgeApi.listKnowledgeBases().catch(() => []).then(items =>

          items.map((k: any) => ({ id: k.kb_id, name: k.name }))

        ),

        api.listRoles().catch(() => []).then((r: any) => {

          const roles = Array.isArray(r) ? r : (r.roles || []);

          return roles.map((role: any) => ({ id: role.role_id || role.id, name: role.name }));

        }),

        api.listWorkspaces().catch(() => []).then(items =>

          items.map((w: any) => ({ id: w.workspace_id || w.id, name: w.name }))

        ),

      ]);



      setProcessOptions(processes);

      setRuleOptions(rules);

      setBusinessLogicOptions(businessLogics);

      setIndicatorOptions(indicators);

      setSkillOptions(skills);

      setKnowledgeBaseOptions(knowledgeBases);

      setRoleOptions(roles);

      setWorkspaceOptions(workspaces);

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

    setModalOpen(true);

    if (agent.avatar && AVATAR_OPTIONS.includes(agent.avatar)) {

      setSelectedAvatar(agent.avatar);

    } else if (agent.avatar) {

      setSelectedAvatar(agent.avatar);

    } else {

      setSelectedAvatar(AVATAR_OPTIONS[0]);

    }

    setTimeout(() => {

      form.setFieldsValue({

        name: agent.name,

        display_name: agent.display_name,

        avatar: agent.avatar,

        description: agent.description,

        main_object: agent.main_object,

        related_objects: agent.related_objects,

        related_processes: agent.related_processes,

        related_rules: agent.related_rules,

        related_business_logic: agent.related_business_logic,

        related_indicators: agent.related_indicators,

        related_skills: agent.related_skills,

        related_knowledge_bases: agent.related_knowledge_bases,

        allowed_roles: agent.allowed_roles,

        workspace_id: agent.workspace_id || undefined,

      });

    }, 0);

  };



  const handleView = (agent: Agent) => {

    setViewingAgent(agent);

    setDetailOpen(true);

  };



  const handleDelete = async (id: string) => {

    try {

      await agentApi.deleteAgent(id);

      message.success(t('删除成功'));

      loadAgents();

    } catch (e) {

      message.error(t('删除失败'));

    }

  };



  const handleSave = async (values: AgentFormData) => {

    try {

      const payload: AgentFormData = { ...values, avatar: selectedAvatar, workspace_id: values.workspace_id ?? '' };

      if (editingAgent) {

        await agentApi.updateAgent(editingAgent.agent_id, payload);

        message.success(t('更新成功'));

      } else {

        await agentApi.createAgent(payload);

        message.success(t('创建成功'));

      }

      setModalOpen(false);

      loadAgents();

    } catch (e: any) {

      console.error('保存智能体失败:', e);

      message.error(t('保存失败: {{message}}', { message: e?.message || t('未知错误') }));

    }

  };



  const filteredAgents = agents.filter(a => {

    const matchSearch = a.name.toLowerCase().includes(searchText.toLowerCase()) ||

      a.display_name.toLowerCase().includes(searchText.toLowerCase());

    const matchWorkspace = !workspaceFilter ||

      (workspaceFilter === '__all__' ? !a.workspace_id : a.workspace_id === workspaceFilter);

    return matchSearch && matchWorkspace;

  });



  const getWorkspaceName = (id: string, agent: Agent) => {

    const ws = workspaceOptions.find(w => w.id === id);

    return ws ? ws.name : (agent.resolved_names?.workspace_name || id);

  };



  const getRoleName = (id: string, agent: Agent) => {

    const role = roleOptions.find(r => r.id === id);

    return role ? role.name : (agent.resolved_names?.role_names?.[id] || id);

  };



  const resolveName = (id: string, agent: Agent, category: keyof import('../types').ResolvedNames) => {
    const rn = agent.resolved_names;
    if (rn) {
      const map = rn[category];
      if (map && typeof map === 'object' && id in map) return (map as Record<string, string>)[id];
    }
    if (category === 'skill_names') {
      const sk = skillOptions.find(s => s.id === id);
      if (sk) return sk.name;
    }
    if (category === 'object_names') {
      const o = entityOptions.find(e => e.id === id);
      if (o) return o.name;
    }
    return id;
  };

  const resolveMainObject = (agent: Agent) => {
    if (!agent.main_object) return '';
    const rn = agent.resolved_names;
    if (rn?.object_names && agent.main_object in rn.object_names) {
      return rn.object_names[agent.main_object];
    }
    const found = entityOptions.find(o => o.id === agent.main_object);
    if (found) return found.name;
    return agent.main_object;
  };



  return (

    <div style={{ padding: 0 }}>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>

        <Space>

          <Input.Search

            placeholder={t('搜索智能体')}

            value={searchText}

            onChange={e => setSearchText(e.target.value)}

            style={{ width: 260 }}

            allowClear

            prefix={<SearchOutlined />}

          />

          <Select

            placeholder={t('按工作空间过滤')}

            value={workspaceFilter}

            onChange={v => setWorkspaceFilter(v)}

            style={{ width: 180 }}

            allowClear

            options={[

              { value: '__all__', label: t('全部空间（未绑定）') },

              ...workspaceOptions.map(w => ({ value: w.id, label: w.name })),

            ]}

          />

        </Space>

        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>

          {t('新建智能体')}

        </Button>

      </div>



      {loading ? (

        <div style={{ textAlign: 'center', padding: 60 }}><Spin /></div>

      ) : filteredAgents.length === 0 ? (

        <div style={{ textAlign: 'center', padding: 60 }}>

          <RobotOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />

          <div style={{ color: '#8c8c8c' }}>{t('暂无智能体')}</div>

        </div>

      ) : (

        <Row gutter={[16, 16]}>

          {filteredAgents.map(agent => (

            <Col key={agent.agent_id} xs={24} sm={12} md={8} lg={6}>

              <Card

                hoverable

                style={{ borderRadius: 12, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}

                styles={{ body: { padding: 20 } }}

                actions={[

                  <Tooltip key="view" title={t('查看')}><EyeOutlined onClick={() => handleView(agent)} /></Tooltip>,

                  <Tooltip key="edit" title={t('编辑')}><EditOutlined onClick={() => handleEdit(agent)} /></Tooltip>,

                  <Popconfirm key="del" title={t('确认删除？')} onConfirm={() => handleDelete(agent.agent_id)}>

                    <DeleteOutlined style={{ color: '#ff4d4f' }} />

                  </Popconfirm>,

                ]}

              >

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>

                  <Avatar src={agent.avatar} size={72} style={{ border: '2px solid #f0f0f0', flexShrink: 0 }} />

                  <div style={{ textAlign: 'center', width: '100%' }}>

                    <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 2 }}>{agent.display_name}</div>

                    <div style={{ fontSize: 12, color: '#bfbfbf' }}>{agent.name}</div>

                  </div>

                  {agent.main_object && (() => {
                    const name = resolveMainObject(agent);
                    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(agent.main_object);
                    const resolved = name !== agent.main_object;
                    const label = resolved ? name : (isUuid ? t('已删除: {{id}}...', { id: agent.main_object.slice(0, 8) }) : name);
                    return (
                      <Tag color={resolved ? 'blue' : 'default'} style={{ margin: 0, color: resolved ? undefined : '#bfbfbf' }} title={agent.main_object}>
                        {t('主对象: {{name}}', { name: label })}
                      </Tag>
                    );
                  })()}

                  {agent.workspace_id ? (

                    <Tag color="gold" style={{ margin: 0 }}>{getWorkspaceName(agent.workspace_id, agent)}</Tag>

                  ) : (

                    <Tag style={{ margin: 0 }}>{t('全部空间')}</Tag>

                  )}

                  <Paragraph

                    style={{ fontSize: 13, color: '#8c8c8c', textAlign: 'center', margin: 0, lineHeight: 1.5, minHeight: 40 }}

                    ellipsis={{ rows: 2 }}

                  >

                    {agent.description || t('暂无描述')}

                  </Paragraph>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center', width: '100%' }}>

                    {(agent.related_skills || []).slice(0, 3).map(sk => {
                      const name = resolveName(sk, agent, 'skill_names');
                      const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sk);
                      const resolved = name !== sk;
                      if (resolved) {
                        return <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{name}</Tag>;
                      }
                      if (isUuid) {
                        return <Tag key={sk} color="default" style={{ fontSize: 11, color: '#bfbfbf' }} title={sk}>{t('已删除: {{id}}...', { id: sk.slice(0, 8) })}</Tag>;
                      }
                      return <Tag key={sk} color="purple" style={{ fontSize: 11 }}>{sk}</Tag>;
                    })}

                    {(agent.related_skills || []).length > 3 && (

                      <Tag style={{ fontSize: 11 }}>+{agent.related_skills.length - 3}</Tag>

                    )}

                  </div>

                  {(agent.allowed_roles || []).length > 0 && (

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center', width: '100%' }}>

                      {agent.allowed_roles.slice(0, 3).map(r => (

                        <Tag key={r} color="geekblue" style={{ fontSize: 11 }}>{getRoleName(r, agent)}</Tag>

                      ))}

                      {agent.allowed_roles.length > 3 && (

                        <Tag style={{ fontSize: 11 }}>+{agent.allowed_roles.length - 3}</Tag>

                      )}

                    </div>

                  )}

                </div>

              </Card>

            </Col>

          ))}

        </Row>

      )}



      <Modal

        title={editingAgent ? t('编辑智能体') : t('新建智能体')}

        open={modalOpen}

        onCancel={() => setModalOpen(false)}

        onOk={() => form.submit()}

        width={720}

        destroyOnHidden

        okText={t('保存')}

        cancelText={t('取消')}

      >

        <Form form={form} layout="vertical" onFinish={handleSave} initialValues={{

          related_objects: [],

          related_processes: [],

          related_rules: [],

          related_business_logic: [],

          related_indicators: [],

          related_skills: [],

          related_knowledge_bases: [],

          allowed_roles: [],

        }}>

          <Form.Item

            name="name"

            label={t('智能体名称')}

            rules={[{ required: true, message: t('请输入智能体名称') }]}

          >

            <Input placeholder={t('仅支持英文和下划线')} maxLength={20} showCount />

          </Form.Item>



          <Form.Item

            name="display_name"

            label={t('前台展示名称')}

            rules={[{ required: true, message: t('请输入前台展示名称') }]}

          >

            <Input placeholder={t('请输入前台展示名称')} maxLength={20} showCount />

          </Form.Item>



          <Form.Item label={t('形象')} required>

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



          <Form.Item name="description" label={t('描述')}>

            <Input.TextArea

              placeholder={t('此运营对象所服务的具体业务场景、核心目标和用户群体等描述')}

              maxLength={1000}

              showCount

              rows={3}

            />

          </Form.Item>



          <Divider>{t('对象关联')}</Divider>



          <Form.Item

            name="main_object"

            label={t('主对象')}

            rules={[{ required: true, message: t('请选择主对象') }]}

          >

            <Select

              placeholder={t('请选择主对象')}

              options={entityOptions.map(v => ({ value: v.id, label: v.name }))}

              showSearch

              optionFilterProp="label"

              notFoundContent={t('暂无实体类型，请先构建本体图谱')}

            />

          </Form.Item>



          <Form.Item name="related_objects" label={t('关联对象类型')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联对象类型')}

              options={entityOptions.map(v => ({ value: v.id, label: v.name }))}

              showSearch

              optionFilterProp="label"

              notFoundContent={t('暂无实体类型，请先构建本体图谱')}

            />

          </Form.Item>



          <Divider>{t('业务关联')}</Divider>



          <Form.Item name="related_processes" label={t('关联业务过程')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联的业务过程')}

              options={processOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="related_rules" label={t('关联业务规则')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联的业务规则')}

              options={ruleOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="related_business_logic" label={t('关联业务逻辑')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联的业务逻辑')}

              options={businessLogicOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="related_indicators" label={t('关联指标')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联的指标')}

              options={indicatorOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="related_skills" label={t('可用技能')}>

            <Select

              mode="multiple"

              placeholder={t('请选择可用技能')}

              options={skillOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="related_knowledge_bases" label={t('关联知识库')}>

            <Select

              mode="multiple"

              placeholder={t('请选择关联的知识库')}

              options={knowledgeBaseOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Divider>{t('权限配置')}</Divider>



          <Form.Item

            name="allowed_roles"

            label={t('可见角色（哪些角色可以看到和使用此智能体）')}

            rules={[{ required: true, message: t('请至少选择一个可见角色') }]}

          >

            <Select

              mode="multiple"

              placeholder={t('请选择可见角色')}

              options={roleOptions.map(o => ({ value: o.id, label: o.name }))}

              showSearch

              optionFilterProp="label"

            />

          </Form.Item>



          <Form.Item name="workspace_id" label={t('工作空间')}>

            <Select

              placeholder={t('不选则表示全部空间')}

              options={workspaceOptions.map(w => ({ value: w.id, label: w.name }))}

              showSearch

              optionFilterProp="label"

              allowClear

            />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('智能体详情')}

        open={detailOpen}

        onCancel={() => setDetailOpen(false)}

        footer={[

          <Button key="close" onClick={() => setDetailOpen(false)}>{t('关闭')}</Button>,

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

            <Descriptions column={1}>

              <Descriptions.Item label={t('主对象')}>

                <Tag color="blue">{resolveMainObject(viewingAgent)}</Tag>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联对象')}>

                <Space wrap>

                  {(viewingAgent.related_objects || []).map(o => <Tag key={o}>{resolveName(o, viewingAgent, 'object_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联业务过程')}>

                <Space wrap>

                  {(viewingAgent.related_processes || []).map(o => <Tag key={o} color="green">{resolveName(o, viewingAgent, 'process_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联业务规则')}>

                <Space wrap>

                  {(viewingAgent.related_rules || []).map(o => <Tag key={o} color="orange">{resolveName(o, viewingAgent, 'rule_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联业务逻辑')}>

                <Space wrap>

                  {(viewingAgent.related_business_logic || []).map(o => <Tag key={o} color="cyan">{resolveName(o, viewingAgent, 'logic_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联指标')}>

                <Space wrap>

                  {(viewingAgent.related_indicators || []).map(o => <Tag key={o} color="volcano">{resolveName(o, viewingAgent, 'indicator_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('可用技能')}>

                <Space wrap>

                  {(viewingAgent.related_skills || []).map(o => {
                    const name = resolveName(o, viewingAgent, 'skill_names');
                    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(o);
                    const resolved = name !== o;
                    if (resolved) return <Tag key={o} color="purple">{name}</Tag>;
                    if (isUuid) return <Tag key={o} color="default" style={{ color: '#bfbfbf' }} title={o}>{t('已删除: {{id}}...', { id: o.slice(0, 8) })}</Tag>;
                    return <Tag key={o} color="purple">{o}</Tag>;
                  })}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('关联知识库')}>

                <Space wrap>

                  {(viewingAgent.related_knowledge_bases || []).map(o => <Tag key={o} color="geekblue">{resolveName(o, viewingAgent, 'knowledge_base_names')}</Tag>)}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('可见角色')}>

                <Space wrap>

                  {(viewingAgent.allowed_roles || []).map(o => {

                    const role = roleOptions.find(r => r.id === o);

                    return <Tag key={o} color="magenta">{role ? role.name : (viewingAgent.resolved_names?.role_names?.[o] || o.slice(0, 8))}</Tag>;

                  })}

                </Space>

              </Descriptions.Item>

              <Descriptions.Item label={t('工作空间')}>

                {viewingAgent.workspace_id

                  ? (() => {

                      const ws = workspaceOptions.find(w => w.id === viewingAgent.workspace_id);

                      return <Tag color="gold">{ws ? ws.name : (viewingAgent.resolved_names?.workspace_name || viewingAgent.workspace_id.slice(0, 8))}</Tag>;

                    })()

                  : <Tag>{t('全部空间')}</Tag>

                }

              </Descriptions.Item>

              <Descriptions.Item label={t('描述')}>{viewingAgent.description || '—'}</Descriptions.Item>

            </Descriptions>

          </div>

        )}

      </Modal>

    </div>

  );

}

