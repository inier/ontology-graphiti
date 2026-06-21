import { useState } from 'react';
import { Tabs, Card, Input, Button, Tag, Space, Form, message, Descriptions, List } from 'antd';
import { SearchOutlined, CompassOutlined, BulbOutlined, ToolOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useKnowledgeStore } from '../stores/knowledgeStore';
import { knowledgePageApi } from '../services/knowledgePageApi';
import { AdvancedTable } from '@/modules/shared';

const { TextArea } = Input;

export function KnowledgePage() {
  const {
    activeTab,
    navigationResults,
    synonyms,
    expansionRules,
    loading,
    error,
    setActiveTab,
    navigate,
    loadSynonyms,
    addSynonym,
    loadExpansionRules,
    addExpansionRule,
    clearError,
  } = useKnowledgeStore();

  const [navEntityId, setNavEntityId] = useState('');
  const [navDirection, setNavDirection] = useState('outbound');
  const [intentInput, setIntentInput] = useState('');
  const [intentResult, setIntentResult] = useState<Record<string, unknown> | null>(null);
  const [taskPlan, setTaskPlan] = useState<Record<string, unknown> | null>(null);
  const [synonymCanonical, setSynonymCanonical] = useState('');
  const [synonymValue, setSynonymValue] = useState('');
  const [rulePattern, setRulePattern] = useState('');
  const [ruleExpansion, setRuleExpansion] = useState('');

  const handleNavigate = async () => {
    if (!navEntityId) {
      message.warning('请输入实体ID');
      return;
    }
    await navigate(navEntityId, navDirection);
  };

  const handleParseIntent = async () => {
    if (!intentInput) {
      message.warning('请输入自然语言');
      return;
    }
    const result = await useKnowledgeStore.getState().parseIntent(intentInput);
    setIntentResult(result);
  };

  const handlePlanTasks = async () => {
    if (!intentResult) {
      message.warning('请先解析意图');
      return;
    }
    const result = await useKnowledgeStore.getState().planTasks(
      (intentResult as Record<string, unknown>).intent as string || 'query',
      (intentResult as Record<string, unknown>).entities as string[] || [],
      (intentResult as Record<string, unknown>).filters as Record<string, unknown> || {},
    );
    setTaskPlan(result);
  };

  const handleAddSynonym = async () => {
    if (!synonymCanonical || !synonymValue) {
      message.warning('请输入规范词和同义词');
      return;
    }
    await addSynonym(synonymCanonical, synonymValue);
    setSynonymCanonical('');
    setSynonymValue('');
    message.success('同义词已添加');
  };

  const handleAddExpansionRule = async () => {
    if (!rulePattern || !ruleExpansion) {
      message.warning('请输入模式和扩写');
      return;
    }
    await addExpansionRule(rulePattern, ruleExpansion);
    setRulePattern('');
    setRuleExpansion('');
    message.success('扩写规则已添加');
  };

  const synonymColumns = [
    { title: '规范词', dataIndex: 'canonical', key: 'canonical' },
    { title: '同义词', dataIndex: 'synonyms', key: 'synonyms', render: (syns: string[]) => syns?.map((s: string) => <Tag key={s}>{s}</Tag>) },
  ];

  const synonymData = Object.entries(synonyms).map(([canonical, syns]) => ({
    key: canonical,
    canonical,
    synonyms: syns,
  }));

  const expansionColumns = [
    { title: '模式', dataIndex: 'pattern', key: 'pattern' },
    { title: '扩写', dataIndex: 'expansion', key: 'expansion', render: (exp: string[]) => exp?.map((e: string) => <Tag key={e}>{e}</Tag>) },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card title="知识导航与语义层配置">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'navigation',
            label: <span><CompassOutlined /> 知识导航</span>,
            children: (
              <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                <Space>
                  <Input
                    placeholder="输入实体ID"
                    value={navEntityId}
                    onChange={(e) => setNavEntityId(e.target.value)}
                    style={{ width: 300 }}
                  />
                  <select
                    value={navDirection}
                    onChange={(e) => setNavDirection(e.target.value)}
                    style={{ padding: '4px 8px', borderRadius: 4 }}
                  >
                    <option value="outbound">出向</option>
                    <option value="inbound">入向</option>
                    <option value="both">双向</option>
                  </select>
                  <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={handleNavigate}>
                    导航
                  </Button>
                </Space>
                {navigationResults && (
                  <Descriptions title="导航结果" variant="bordered" size="small" column={1}>
                    <Descriptions.Item label="实体ID">{navigationResults.entity_id}</Descriptions.Item>
                    <Descriptions.Item label="导航路径">
                      {navigationResults.navigation_path?.map((p: string, i: number) => (
                        <Tag key={i}>{p}</Tag>
                      ))}
                    </Descriptions.Item>
                    <Descriptions.Item label="相关实体数">{navigationResults.related_entities?.length || 0}</Descriptions.Item>
                  </Descriptions>
                )}
              </Space>
            ),
          },
          {
            key: 'intent',
            label: <span><BulbOutlined /> 意图解析</span>,
            children: (
              <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                <TextArea
                  placeholder="输入自然语言查询..."
                  value={intentInput}
                  onChange={(e) => setIntentInput(e.target.value)}
                  rows={3}
                  style={{ width: '100%' }}
                />
                <Space>
                  <Button type="primary" icon={<SearchOutlined />} onClick={handleParseIntent}>
                    解析意图
                  </Button>
                  <Button icon={<ThunderboltOutlined />} onClick={handlePlanTasks} disabled={!intentResult}>
                    规划任务
                  </Button>
                </Space>
                {intentResult && (
                  <Descriptions title="解析结果" variant="bordered" size="small" column={2}>
                    <Descriptions.Item label="意图">{String(intentResult.intent || '')}</Descriptions.Item>
                    <Descriptions.Item label="置信度">{String(intentResult.confidence || '')}</Descriptions.Item>
                    <Descriptions.Item label="实体" span={2}>
                      {(intentResult.entities as string[])?.map((e: string, i: number) => <Tag key={i}>{e}</Tag>)}
                    </Descriptions.Item>
                  </Descriptions>
                )}
                {taskPlan && (
                  <Card title="任务规划" size="small">
                    <List
                      size="small"
                      dataSource={(taskPlan.tasks as Record<string, unknown>[]) || []}
                      renderItem={(task: Record<string, unknown>) => (
                        <List.Item>
                          <Space>
                            <Tag>步骤 {String(task.step)}</Tag>
                            <span>{String(task.description)}</span>
                            <Tag color="blue">{String(task.task_type)}</Tag>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </Card>
                )}
              </Space>
            ),
          },
          {
            key: 'semantic',
            label: <span><ToolOutlined /> 语义配置</span>,
            children: (
              <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                <Card title="同义词映射" size="small">
                  <Space style={{ marginBottom: 16 }}>
                    <Input placeholder="规范词" value={synonymCanonical} onChange={(e) => setSynonymCanonical(e.target.value)} style={{ width: 150 }} />
                    <Input placeholder="同义词" value={synonymValue} onChange={(e) => setSynonymValue(e.target.value)} style={{ width: 150 }} />
                    <Button type="primary" onClick={handleAddSynonym}>添加</Button>
                    <Button onClick={() => loadSynonyms()}>刷新</Button>
                  </Space>
                  <AdvancedTable columns={synonymColumns} dataSource={synonymData} size="small" pagination={false} />
                </Card>
                <Card title="扩写规则" size="small">
                  <Space style={{ marginBottom: 16 }}>
                    <Input placeholder="模式" value={rulePattern} onChange={(e) => setRulePattern(e.target.value)} style={{ width: 150 }} />
                    <Input placeholder="扩写" value={ruleExpansion} onChange={(e) => setRuleExpansion(e.target.value)} style={{ width: 150 }} />
                    <Button type="primary" onClick={handleAddExpansionRule}>添加</Button>
                    <Button onClick={() => loadExpansionRules()}>刷新</Button>
                  </Space>
                  <AdvancedTable columns={expansionColumns} dataSource={expansionRules.map((r, i) => ({ key: i, ...r }))} size="small" pagination={false} />
                </Card>
              </Space>
            ),
          },
        ]} />
        {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      </Card>
    </div>
  );
}
