import { useState, useEffect } from 'react';
import { Tabs, Card, Descriptions, Tag, Progress, Space, Typography, Spin, Empty, Input, Button } from 'antd';
import { BulbOutlined, CompassOutlined, AimOutlined, SearchOutlined } from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';
import { useI18n } from '../../shared/hooks/useI18n';
import ReasoningPath from './ReasoningPath';

const { Text } = Typography;

interface IntentResult {
  intent_id?: string;
  primary_intent?: string;
  confidence: number;
  entities: string[];
  attributes: Record<string, unknown>;
  alternative_intents: string[];
}

interface ExplanationResult {
  explanation_id?: string;
  decision_id: string;
  query: string;
  answer: string;
  confidence: number;
  reasoning_chain: Record<string, unknown>[];
  sources: string[];
}

interface RoleViewResult {
  view_id?: string;
  role: string;
  name?: string;
  description?: string;
  capabilities: string[];
  layout_config: Record<string, unknown>;
  filters: Record<string, unknown>;
}

interface CognitionPanelProps {
  workspaceId: string;
  scenarioId: string;
}

const ROLE_TABS = [
  { key: 'commander', label: 'Commander', icon: <AimOutlined /> },
  { key: 'intelligence', label: 'Intelligence', icon: <CompassOutlined /> },
  { key: 'operations', label: 'Operations', icon: <BulbOutlined /> },
];

const CONFIDENCE_COLOR = (v: number) =>
  v >= 0.8 ? '#52c41a' : v >= 0.5 ? '#faad14' : '#ff4d4f';

export default function CognitionPanel({ workspaceId, scenarioId }: CognitionPanelProps) {
  const { t } = useI18n('agent');
  const [activeRole, setActiveRole] = useState('commander');
  const [intentResult, setIntentResult] = useState<IntentResult | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResult | null>(null);
  const [roleView, setRoleView] = useState<RoleViewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputText, setInputText] = useState('');
  const [decisionId, setDecisionId] = useState('');

  useEffect(() => {
    loadRoleView(activeRole);
  }, [activeRole]);

  const loadRoleView = async (role: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<RoleViewResult>(`/api/cognition/role-view?role=${role}`);
      setRoleView(data);
    } catch {
      setRoleView(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRecognizeIntent = async () => {
    if (!inputText.trim()) return;
    setLoading(true);
    try {
      const data = await apiClient.post<IntentResult>('/api/cognition/recognize-intent', {
        input_text: inputText,
        role: activeRole,
      });
      setIntentResult(data);
    } catch {
      setIntentResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleExplain = async () => {
    if (!decisionId.trim()) return;
    setLoading(true);
    try {
      const data = await apiClient.post<ExplanationResult>('/api/cognition/explain', {
        decision_id: decisionId,
        context: { workspace_id: workspaceId, scenario_id: scenarioId },
      });
      setExplanation(data);
    } catch {
      setExplanation(null);
    } finally {
      setLoading(false);
    }
  };

  const renderIntentSection = () => (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space>
        <Input
          placeholder="Enter text for intent recognition..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          style={{ width: 400 }}
          onPressEnter={handleRecognizeIntent}
        />
        <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={handleRecognizeIntent}>
          Recognize
        </Button>
      </Space>
      {!intentResult ? (
        <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="Intent Type">
              <Tag color="blue">{intentResult.primary_intent || 'unknown'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Confidence">
              <Progress
                percent={Math.round(intentResult.confidence * 100)}
                size="small"
                strokeColor={CONFIDENCE_COLOR(intentResult.confidence)}
              />
            </Descriptions.Item>
            <Descriptions.Item label="Entities" span={2}>
              {intentResult.entities.length > 0
                ? intentResult.entities.map((e) => <Tag key={e}>{e}</Tag>)
                : <Text type="secondary">—</Text>}
            </Descriptions.Item>
            <Descriptions.Item label="Alternative Intents" span={2}>
              {intentResult.alternative_intents.length > 0
                ? intentResult.alternative_intents.map((i) => <Tag key={i} color="default">{i}</Tag>)
                : <Text type="secondary">—</Text>}
            </Descriptions.Item>
          </Descriptions>
          {intentResult.attributes && Object.keys(intentResult.attributes).length > 0 && (
            <Card title="Parameters" size="small">
              {Object.entries(intentResult.attributes).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 4 }}>
                  <Text strong>{key}:</Text> <Text>{String(value)}</Text>
                </div>
              ))}
            </Card>
          )}
        </Space>
      )}
    </Space>
  );

  const renderReasoningSection = () => (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space>
        <Input
          placeholder="Enter decision ID for explanation..."
          value={decisionId}
          onChange={(e) => setDecisionId(e.target.value)}
          style={{ width: 400 }}
          onPressEnter={handleExplain}
        />
        <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={handleExplain}>
          Explain
        </Button>
      </Space>
      {!explanation ? (
        <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="Query">{explanation.query}</Descriptions.Item>
            <Descriptions.Item label="Confidence">
              <Progress
                percent={Math.round(explanation.confidence * 100)}
                size="small"
                strokeColor={CONFIDENCE_COLOR(explanation.confidence)}
              />
            </Descriptions.Item>
            <Descriptions.Item label="Answer" span={2}>{explanation.answer}</Descriptions.Item>
          </Descriptions>
          {explanation.reasoning_chain.length > 0 && (
            <ReasoningPath
              path={explanation.reasoning_chain.map((step, idx) => ({
                id: String(idx),
                title: (step as Record<string, unknown>).title as string || `Step ${idx + 1}`,
                description: (step as Record<string, unknown>).description as string || '',
                status: ((step as Record<string, unknown>).status as 'error' | 'wait' | 'process' | 'finish') || 'finish',
              }))}
              onNodeClick={(node) => {
                console.info('Node clicked:', node);
              }}
            />
          )}
          {explanation.sources.length > 0 && (
            <Card title="Sources" size="small">
              {explanation.sources.map((s, i) => <Tag key={i} color="geekblue">{s}</Tag>)}
            </Card>
          )}
        </Space>
      )}
    </Space>
  );

  const renderRoleViewSection = () => {
    if (!roleView) {
      return <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Descriptions bordered size="small" column={1}>
        <Descriptions.Item label="Role">
          <Tag color="purple">{roleView.role}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Name">{roleView.name || '—'}</Descriptions.Item>
        <Descriptions.Item label="Description">{roleView.description || '—'}</Descriptions.Item>
        <Descriptions.Item label="Capabilities">
          {roleView.capabilities.length > 0
            ? roleView.capabilities.map((c) => <Tag key={c} color="cyan">{c}</Tag>)
            : <Text type="secondary">—</Text>}
        </Descriptions.Item>
      </Descriptions>
    );
  };

  const tabItems = [
    {
      key: 'intent',
      label: (
        <span><BulbOutlined /> Intent Recognition</span>
      ),
      children: renderIntentSection(),
    },
    {
      key: 'reasoning',
      label: (
        <span><CompassOutlined /> Reasoning Chain</span>
      ),
      children: renderReasoningSection(),
    },
    {
      key: 'role-view',
      label: (
        <span><AimOutlined /> Role View</span>
      ),
      children: renderRoleViewSection(),
    },
  ];

  return (
    <Spin spinning={loading}>
      <Card
        title="Cognition Engine"
        size="small"
        extra={
          <Space>
            {ROLE_TABS.map((tab) => (
              <Tag
                key={tab.key}
                color={activeRole === tab.key ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setActiveRole(tab.key)}
              >
                {tab.icon} {tab.label}
              </Tag>
            ))}
          </Space>
        }
      >
        <Tabs
          activeKey={activeRole === 'commander' ? 'intent' : activeRole === 'intelligence' ? 'reasoning' : 'role-view'}
          items={tabItems}
          onChange={(key) => {
            if (key === 'intent') setActiveRole('commander');
            else if (key === 'reasoning') setActiveRole('intelligence');
            else setActiveRole('operations');
          }}
        />
      </Card>
    </Spin>
  );
}
