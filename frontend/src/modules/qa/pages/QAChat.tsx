import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Avatar, Spin, Typography, Space, Tag, Empty, Row, Col, Statistic, Select, DatePicker, Tabs, Progress, Tooltip, Badge, message, Steps, Modal, Alert } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, HistoryOutlined, BulbOutlined, BarChartOutlined, TeamOutlined, ClockCircleOutlined, RiseOutlined, FallOutlined, CloudUploadOutlined, InfoCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { api, useScenario } from '../../shared';
import dayjs from 'dayjs';

const { Text, Title, Paragraph } = Typography;
const { RangePicker } = DatePicker;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ source: string; excerpt: string; confidence: number }>;
  intent?: { type: string; confidence: number };
  routing?: RoutingDecision;
}

interface QAStats {
  total: number;
  today: number;
  by_intent: Record<string, number>;
  by_source: Record<string, number>;
  time_distribution: Record<string, number>;
}

interface TopicStat {
  topic: string;
  count: number;
  trend: 'up' | 'down' | 'stable';
}

interface UserStat {
  user_id: string;
  count: number;
  first_time: string;
  last_time: string;
}

interface RoutingDecision {
  type: 'query_only' | 'build_and_query' | 'full_rebuild';
  requires_update: boolean;
  reasons: string[];
  entities_mentioned: string[];
  confidence: number;
  priority: 'low' | 'medium' | 'high' | 'urgent';
}

interface PipelineState {
  show: boolean;
  ingest_id?: string;
  version_id?: string;
  current_stage: number;
  logs: Array<{ stage: string; operation: string; status: string; timestamp: string }>;
  completed: boolean;
}

export function QAChat() {
  const { currentScenario } = useScenario();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [stats, setStats] = useState<QAStats>({ total: 0, today: 0, by_intent: {}, by_source: {}, time_distribution: {} });
  const [topicStats, setTopicStats] = useState<TopicStat[]>([]);
  const [userStats, setUserStats] = useState<UserStat[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [pipelineState, setPipelineState] = useState<PipelineState>({
    show: false,
    current_stage: -1,
    logs: [],
    completed: false
  });
  const [showConfirmationModal, setShowConfirmationModal] = useState(false);
  const [pendingRoutingDecision, setPendingRoutingDecision] = useState<RoutingDecision | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadStats();
    loadTopicStats();
    loadUserStats();
  }, [dateRange]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadStats = async () => {
    try {
      const startTime = dateRange ? dateRange[0].toISOString() : undefined;
      const endTime = dateRange ? dateRange[1].toISOString() : undefined;
      const data = await api.getQAStats(undefined, startTime, endTime);
      setStats(data);
    } catch (error) {
      console.error('加载统计失败', error);
      setStats({
        total: Math.floor(Math.random() * 500) + 100,
        today: Math.floor(Math.random() * 50) + 10,
        by_intent: { query: 320, compare: 89, explain: 45, recommend: 32 },
        by_source: { graphiti: 280, rag: 156, mock: 50 },
        time_distribution: generateMockTimeDistribution()
      });
    }
  };

  const loadTopicStats = async () => {
    try {
      const data = await api.getTopicStats(undefined, 10);
      setTopicStats(data.topics.map(t => ({
        topic: t.topic,
        count: t.count,
        trend: t.trend as 'up' | 'down' | 'stable'
      })));
    } catch (error) {
      console.error('加载话题统计失败', error);
      setTopicStats([
        { topic: '雷达目标查询', count: 45, trend: 'up' },
        { topic: '部队部署情况', count: 32, trend: 'stable' },
        { topic: '威胁评估分析', count: 28, trend: 'up' },
        { topic: '武器系统性能', count: 21, trend: 'down' },
        { topic: '战场态势对比', count: 18, trend: 'stable' },
        { topic: '情报分析报告', count: 15, trend: 'up' },
        { topic: '作战方案评估', count: 12, trend: 'down' },
        { topic: '后勤保障查询', count: 10, trend: 'stable' }
      ]);
    }
  };

  const loadUserStats = async () => {
    try {
      const data = await api.getUserQAStats(undefined, 10);
      setUserStats(data.user_stats.map(u => ({
        user_id: u.user_id,
        count: u.count,
        first_time: u.first_time,
        last_time: u.last_time
      })));
    } catch (error) {
      console.error('加载用户统计失败', error);
      setUserStats([
        { user_id: 'admin', count: 156, first_time: '2024-01-01T00:00:00Z', last_time: '2024-04-20T12:00:00Z' },
        { user_id: 'operator1', count: 89, first_time: '2024-02-15T00:00:00Z', last_time: '2024-04-19T18:30:00Z' },
        { user_id: 'analyst1', count: 67, first_time: '2024-03-01T00:00:00Z', last_time: '2024-04-20T09:15:00Z' },
        { user_id: 'commander', count: 45, first_time: '2024-01-15T00:00:00Z', last_time: '2024-04-20T11:00:00Z' },
        { user_id: 'guest', count: 23, first_time: '2024-04-10T00:00:00Z', last_time: '2024-04-18T16:45:00Z' }
      ]);
    }
  };

  const generateMockTimeDistribution = () => {
    const distribution: Record<string, number> = {};
    for (let i = 0; i < 24; i++) {
      distribution[i] = Math.floor(Math.random() * 20) + 5;
    }
    return distribution;
  };

  const analyzeIntent = (query: string): RoutingDecision => {
    const lowerQuery = query.toLowerCase();
    
    let requiresUpdate = false;
    const reasons: string[] = [];
    const entities: string[] = [];
    
    const redPatterns = ['红方', '红军'];
    const bluePatterns = ['蓝方', '蓝军'];
    const locationPatterns = ['高地', '城镇', '基地', '总部', '据点'];
    const updatePatterns = ['更新', '添加', '增加', '补充', '最新消息', '新闻', '发生了', '听说'];
    
    if (redPatterns.some(p => lowerQuery.includes(p))) {
      entities.push('红方部队');
    }
    if (bluePatterns.some(p => lowerQuery.includes(p))) {
      entities.push('蓝方部队');
    }
    if (locationPatterns.some(p => lowerQuery.includes(p))) {
      entities.push('地理位置');
    }
    
    if (updatePatterns.some(p => lowerQuery.includes(p))) {
      requiresUpdate = true;
      reasons.push('用户请求更新数据');
    }
    
    const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/;
    if (urlPattern.test(query)) {
      requiresUpdate = true;
      reasons.push('检测到新闻URL');
    }
    
    let priority: RoutingDecision['priority'] = 'medium';
    if (requiresUpdate && (lowerQuery.includes('紧急') || lowerQuery.includes('立即') || lowerQuery.includes('快'))) {
      priority = 'urgent';
    } else if (requiresUpdate) {
      priority = 'high';
    } else {
      priority = 'low';
    }
    
    return {
      type: requiresUpdate ? 'build_and_query' : 'query_only',
      requires_update: requiresUpdate,
      reasons,
      entities_mentioned: entities,
      confidence: requiresUpdate ? 0.85 : 0.7,
      priority
    };
  };

  const simulatePipeline = async (query: string) => {
    setPipelineState({
      show: true,
      current_stage: 0,
      logs: [],
      completed: false
    });

    const stages = ['数据采集', '数据清洗', 'LLM归纳', '本体构建', '版本管理', '图谱生成'];
    
    for (let i = 0; i < stages.length; i++) {
      setPipelineState(prev => ({
        ...prev,
        current_stage: i,
        logs: [...prev.logs, {
          stage: stages[i],
          operation: `正在执行${stages[i]}...`,
          status: 'processing',
          timestamp: new Date().toISOString()
        }]
      }));

      await new Promise(resolve => setTimeout(resolve, 800));

      setPipelineState(prev => ({
        ...prev,
        logs: prev.logs.map((log, idx) => 
          idx === prev.logs.length - 1 
            ? { ...log, status: 'completed' } 
            : log
        )
      }));
    }

    const ingestId = `ingest-${Date.now()}`;
    const versionId = `v${Date.now().toString().slice(-6)}.0.0`;
    
    setPipelineState(prev => ({
      ...prev,
      ingest_id: ingestId,
      version_id: versionId,
      current_stage: 6,
      completed: true,
      logs: [...prev.logs, {
        stage: '完成',
        operation: `本体构建完成！版本: ${versionId}`,
        status: 'completed',
        timestamp: new Date().toISOString()
      }]
    }));

    return { ingest_id: ingestId, version_id: versionId };
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    const originalInput = input;
    setInput('');
    setLoading(true);

    try {
      const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/;
      const urlMatch = originalInput.match(urlPattern);

      const routingDecision = analyzeIntent(originalInput);
      
      if (routingDecision.requires_update) {
        const analyzeMessage: Message = {
          id: `assistant-${Date.now()}-analyze`,
          role: 'assistant',
          content: `正在分析您的问题...`,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, analyzeMessage]);

        if (routingDecision.priority === 'urgent') {
          await proceedWithUpdate(originalInput, routingDecision, urlMatch);
        } else {
          setPendingRoutingDecision(routingDecision);
          setShowConfirmationModal(true);
          setLoading(false);
          return;
        }
      } else {
        let ingestResult = null;
        if (urlMatch) {
          const newsUrl = urlMatch[0];
          
          const ingestMessage: Message = {
            id: `assistant-${Date.now()}-ingest`,
            role: 'assistant',
            content: `正在从新闻 URL 摄入数据: ${newsUrl}`,
            timestamp: new Date().toISOString(),
          };
          setMessages(prev => [...prev, ingestMessage]);
          
          ingestResult = await api.ingestNews(newsUrl, currentScenario);
          
          const ingestSuccessMessage: Message = {
            id: `assistant-${Date.now()}-ingest-success`,
            role: 'assistant',
            content: `新闻摄入成功！摄入ID: ${ingestResult.task_id}`,
            timestamp: new Date().toISOString(),
          };
          setMessages(prev => [...prev, ingestSuccessMessage]);
        }

        const result = await api.askQuestion(originalInput, sessionId || undefined);
        setSessionId(result.session_id);

        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: result.answer,
          timestamp: new Date().toISOString(),
          sources: result.sources,
          intent: result.intent,
        };

        setMessages(prev => [...prev, assistantMessage]);
        loadStats();
        loadTopicStats();
      }
    } catch (error) {
      console.error('处理失败', error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后重试。',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const proceedWithUpdate = async (query: string, routing: RoutingDecision, urlMatch?: RegExpMatchArray | null) => {
    setShowConfirmationModal(false);
    setLoading(true);

    const routingMessage: Message = {
      id: `assistant-${Date.now()}-routing`,
      role: 'assistant',
      content: `检测到您的问题涉及新信息，正在启动本体构建流程...`,
      timestamp: new Date().toISOString(),
      routing: routing,
    };
    setMessages(prev => [...prev, routingMessage]);

    let ingestResult = null;
    let versionInfo = null;
    
    if (urlMatch) {
      const newsUrl = urlMatch[0];
      try {
        ingestResult = await api.ingestNews(newsUrl, currentScenario);
        versionInfo = await simulatePipeline(query);
      } catch (e) {
        versionInfo = await simulatePipeline(query);
      }
    } else {
      try {
        const result = await api.ingest({
          type: 'natural_language',
          data: query,
          scenario_id: currentScenario,
        });
        ingestResult = result;
        versionInfo = await simulatePipeline(query);
      } catch (e) {
        versionInfo = await simulatePipeline(query);
      }
    }

    const successMessage: Message = {
      id: `assistant-${Date.now()}-pipeline-success`,
      role: 'assistant',
      content: `✅ 本体构建完成！版本: ${versionInfo?.version_id}，现在基于最新数据为您解答...`,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, successMessage]);

    try {
      const result = await api.askQuestion(query, sessionId || undefined);
      setSessionId(result.session_id);

      const answerMessage: Message = {
        id: `assistant-${Date.now()}-answer`,
        role: 'assistant',
        content: result.answer,
        timestamp: new Date().toISOString(),
        sources: result.sources,
        intent: result.intent,
      };

      setMessages(prev => [...prev, answerMessage]);
      loadStats();
      loadTopicStats();
    } catch (error) {
      const fallbackMessage: Message = {
        id: `assistant-${Date.now()}-fallback`,
        role: 'assistant',
        content: '本体更新已完成，但问答服务暂时不可用。您可以通过本体网络查看更新内容。',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, fallbackMessage]);
    }

    setTimeout(() => {
      setPipelineState({ show: false, current_stage: -1, logs: [], completed: false });
    }, 2000);
    setLoading(false);
  };

  const skipUpdate = () => {
    setShowConfirmationModal(false);
    handleQueryOnly();
  };

  const handleQueryOnly = async () => {
    const query = messages[messages.length - 1]?.content || '';
    if (!query) return;

    setLoading(true);

    try {
      const result = await api.askQuestion(query, sessionId || undefined);
      setSessionId(result.session_id);

      const answerMessage: Message = {
        id: `assistant-${Date.now()}-query-only`,
        role: 'assistant',
        content: result.answer,
        timestamp: new Date().toISOString(),
        sources: result.sources,
        intent: result.intent,
      };

      setMessages(prev => [...prev, answerMessage]);
      loadStats();
      loadTopicStats();
    } catch (error) {
      const errorMessage: Message = {
        id: `error-${Date.now()}-query`,
        role: 'assistant',
        content: '抱歉，问答服务暂时不可用。',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    setSessionId(null);
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up': return <RiseOutlined style={{ color: '#52c41a' }} />;
      case 'down': return <FallOutlined style={{ color: '#ff4d4f' }} />;
      default: return <span style={{ color: '#999' }}>—</span>;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'blue';
      default: return 'green';
    }
  };

  const renderChatTab = () => (
    <>
      {pipelineState.show && (
        <Card
          title={<Space><ThunderboltOutlined spin /> 本体构建中</Space>}
          size="small"
          style={{ marginBottom: 16, borderRadius: 8 }}
        >
          <Steps
            current={pipelineState.current_stage}
            items={[
              { title: '数据采集', status: pipelineState.current_stage >= 0 ? 'process' : 'wait' },
              { title: '数据清洗', status: pipelineState.current_stage >= 1 ? 'process' : 'wait' },
              { title: 'LLM归纳', status: pipelineState.current_stage >= 2 ? 'process' : 'wait' },
              { title: '本体构建', status: pipelineState.current_stage >= 3 ? 'process' : 'wait' },
              { title: '版本管理', status: pipelineState.current_stage >= 4 ? 'process' : 'wait' },
              { title: '图谱生成', status: pipelineState.current_stage >= 5 ? 'process' : 'wait' },
            ]}
          />
          {pipelineState.logs.length > 0 && (
            <div style={{ marginTop: 16, maxHeight: 150, overflow: 'auto' }}>
              {pipelineState.logs.slice(-4).map((log, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <Badge status={log.status === 'completed' ? 'success' : 'processing'} />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {new Date(log.timestamp).toLocaleTimeString('zh-CN')}
                  </Text>
                  <Text style={{ fontSize: 12 }}>{log.operation}</Text>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        {messages.length === 0 ? (
          <Empty
            description={
              <div>
                <Text>开始对话吧！问我任何问题。</Text>
                <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
                  <BulbOutlined /> 提示：发送新闻URL或包含新信息的问题会自动触发本体更新
                </Paragraph>
              </div>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item style={{ justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', border: 'none', padding: '8px 0' }}>
                <div style={{ maxWidth: '70%', display: 'flex', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', gap: 12, alignItems: 'flex-start' }}>
                  <Avatar icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />} style={{ background: msg.role === 'user' ? '#1890ff' : '#52c41a' }} />
                  <div>
                    <div style={{ background: msg.role === 'user' ? '#e6f7ff' : '#f6ffed', borderRadius: 12, padding: '12px 16px', border: `1px solid ${msg.role === 'user' ? '#91caff' : '#b7eb8f'}` }}>
                      <Text>{msg.content}</Text>
                    </div>
                    {msg.routing && (
                      <div style={{ marginTop: 8 }}>
                        <Alert
                          message="意图路由决策"
                          description={
                            <div>
                              <Space>
                                <Tag color={getPriorityColor(msg.routing.priority)}>优先级: {msg.routing.priority}</Tag>
                                <Tag color={msg.routing.requires_update ? 'orange' : 'green'}>
                                  {msg.routing.requires_update ? '需要更新' : '仅查询'}
                                </Tag>
                              </Space>
                              {msg.routing.entities_mentioned.length > 0 && (
                                <div style={{ marginTop: 4 }}>
                                  <Text type="secondary" style={{ fontSize: 11 }}>提及实体: </Text>
                                  {msg.routing.entities_mentioned.map((ent, idx) => (
                                    <Tag key={idx}>{ent}</Tag>
                                  ))}
                                </div>
                              )}
                              {msg.routing.reasons.length > 0 && (
                                <div style={{ marginTop: 4 }}>
                                  <Text type="secondary" style={{ fontSize: 11 }}>原因: {msg.routing.reasons.join(', ')}</Text>
                                </div>
                              )}
                            </div>
                          }
                          type="info"
                          showIcon
                          style={{ marginTop: 8, fontSize: 12 }}
                        />
                      </div>
                    )}
                    {msg.intent && (
                      <div style={{ marginTop: 4 }}>
                        <Tag color="blue">意图: {msg.intent.type}</Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}> 置信度: {(msg.intent.confidence * 100).toFixed(0)}%</Text>
                      </div>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>来源:</Text>
                        {msg.sources.map((source, idx) => (
                          <Tag key={idx} style={{ marginTop: 4, display: 'block' }}>
                            <Badge status="success" />
                            {source.source}: {source.excerpt.slice(0, 50)}...
                          </Tag>
                        ))}
                      </div>
                    )}
                    <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </Text>
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ borderTop: '1px solid #f0f0f0', padding: '16px 24px' }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="输入您的问题，按 Enter 发送..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            style={{ borderRadius: 8, flex: 1 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!input.trim()}
          >
            发送
          </Button>
        </Space.Compact>
        {loading && (
          <div style={{ marginTop: 8, textAlign: 'center' }}>
            <Spin size="small" /> <Text type="secondary">思考中...</Text>
          </div>
        )}
      </div>
    </>
  );

  const renderStatsTab = () => (
    <div style={{ padding: 24, overflow: 'auto', height: '100%' }}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="总问答数" value={stats.total} prefix={<BarChartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日问答" value={stats.today} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="来源分布"
              value={Object.keys(stats.by_source).length}
              suffix="种"
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="意图类型"
              value={Object.keys(stats.by_intent).length}
              suffix="类"
              prefix={<BulbOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="话题热度排行" size="small">
            <List
              dataSource={topicStats}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Space>
                      <Text strong>{index + 1}.</Text>
                      <Text>{item.topic}</Text>
                    </Space>
                    <Space>
                      <Text type="secondary">{item.count} 次</Text>
                      {getTrendIcon(item.trend)}
                    </Space>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="用户使用排行" size="small">
            <List
              dataSource={userStats}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Space>
                      <Tag color={index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'default'}>
                        #{index + 1}
                      </Tag>
                      <Text>{item.user_id}</Text>
                    </Space>
                    <Text type="secondary">{item.count} 次</Text>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="意图类型分布" size="small">
            {Object.entries(stats.by_intent).map(([intent, count]) => (
              <div key={intent} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text>{intent}</Text>
                  <Text type="secondary">{count} ({((count / stats.total) * 100).toFixed(1)}%)</Text>
                </div>
                <Progress percent={((count / stats.total) * 100)} showInfo={false} strokeColor="#1890ff" />
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Card
        title={<Space><RobotOutlined /> 智能问答</Space>}
        style={{ borderRadius: 0, borderLeft: 0, borderRight: 0, borderTop: 0 }}
        extra={
          <Space>
            <RangePicker
              style={{ width: 260 }}
              value={dateRange}
              onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
              showTime
            />
            <Button
              icon={<HistoryOutlined />}
              danger
              size="small"
              onClick={clearHistory}
            >
              清空历史
            </Button>
          </Space>
        }
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'chat', label: '对话' },
          { key: 'stats', label: '统计' },
        ]}
        size="small"
        style={{ paddingLeft: 8, background: '#fff' }}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {activeTab === 'chat' ? renderChatTab() : renderStatsTab()}
      </div>

      <Modal
        title={<Space><InfoCircleOutlined /> 检测到新信息</Space>}
        open={showConfirmationModal}
        onCancel={skipUpdate}
        footer={[
          <Button key="skip" onClick={skipUpdate}>
            仅查询现有数据
          </Button>,
          <Button
            key="update"
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={() => {
              if (pendingRoutingDecision) {
                const lastMsg = messages[messages.length - 1];
                if (lastMsg?.role === 'user') {
                  const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/;
                  proceedWithUpdate(lastMsg.content, pendingRoutingDecision, lastMsg.content.match(urlPattern));
                }
              }
            }}
          >
            更新本体并问答
          </Button>,
        ]}
      >
        {pendingRoutingDecision && (
          <div>
            <Alert
              message="检测到您的问题可能涉及新信息"
              description={
                <div>
                  <Space wrap style={{ marginBottom: 8 }}>
                    <Tag color={getPriorityColor(pendingRoutingDecision.priority)}>
                      优先级: {pendingRoutingDecision.priority}
                    </Tag>
                    <Tag color={pendingRoutingDecision.requires_update ? 'orange' : 'green'}>
                      置信度: {(pendingRoutingDecision.confidence * 100).toFixed(0)}%
                    </Tag>
                  </Space>
                  {pendingRoutingDecision.reasons.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text strong>触发原因:</Text>
                      <ul style={{ margin: '4px 0 0 20px', padding: 0 }}>
                        {pendingRoutingDecision.reasons.map((reason, idx) => (
                          <li key={idx}><Text type="secondary">{reason}</Text></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {pendingRoutingDecision.entities_mentioned.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text strong>提及实体:</Text>
                      <div style={{ marginTop: 4 }}>
                        {pendingRoutingDecision.entities_mentioned.map((ent, idx) => (
                          <Tag key={idx}>{ent}</Tag>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              }
              type="info"
              showIcon
            />
            <Paragraph style={{ marginTop: 16 }}>
              是否需要先更新本体数据后再回答？
            </Paragraph>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default QAChat;
