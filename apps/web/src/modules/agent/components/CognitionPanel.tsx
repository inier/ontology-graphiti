/**
 * CognitionPanel —— 认知引擎工作台。
 *
 * 三块能力（对应后端 odap/biz/core/cognition）：
 *   1. 意图识别：POST /api/cognition/recognize-intent {input_text, role}
 *   2. 解释链：  POST /api/cognition/explain {decision_id, context}
 *   3. 角色视图：GET  /api/cognition/role-view?role=
 *
 * 修复记录：
 *   - 三个页签此前被"焊死"在三个角色上（activeKey 由 activeRole 推导、onChange 反过来改角色），
 *     导致想看解释链必须先切到 intelligence 角色。现在角色只作为**请求参数**，
 *     页签是独立的功能维度。
 *   - 角色取值此前是 director / intelligence / operations，但 RoleViewManager 只登记了
 *     commander / intelligence / operator —— director 与 operations 恒返回空视图。
 *   - 三处 `catch { setX(null) }` 把失败吞掉，界面只会显示"暂无数据"，
 *     无法区分"还没查"和"查挂了"。现在把错误原因显示出来。
 */
import { useCallback, useEffect, useState } from 'react';
import { Tabs, Tag, Progress, Space, Typography, Spin, Empty, Input, Button, Select, Alert } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { BulbOutlined, CompassOutlined, AimOutlined, SearchOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
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

/** 与后端 RoleViewManager 登记的视图一一对应（commander / intelligence / operator） */
const ROLE_OPTIONS = [
  { value: 'commander', labelKey: '指挥员' },
  { value: 'intelligence', labelKey: '情报员' },
  { value: 'operator', labelKey: '操作员' },
] as const;

const CONFIDENCE_COLOR = (v: number) =>
  v >= 0.8 ? '#52c41a' : v >= 0.5 ? '#faad14' : '#ff4d4f';

export default function CognitionPanel({ workspaceId, scenarioId }: CognitionPanelProps) {
  const { t } = useI18n('agent');
  const [activeRole, setActiveRole] = useState<string>('commander');
  const [activeTab, setActiveTab] = useState('intent');
  const [intentResult, setIntentResult] = useState<IntentResult | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResult | null>(null);
  const [roleView, setRoleView] = useState<RoleViewResult | null>(null);
  // 角色视图的「加载中」由「已完成的角色 ≠ 当前角色」推导，而不是在 effect 里同步
  // setLoading(true)——那属于 effect 内同步 setState，会触发级联渲染
  // （react-hooks/set-state-in-effect）。推导出来的值在切角色的那一刻就已经是 true，
  // 视觉上反而比先渲染一帧空视图更准。
  const [loadedRole, setLoadedRole] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [decisionId, setDecisionId] = useState('');
  const roleLoading = loadedRole !== activeRole;

  /** 只做 I/O、不写状态：状态落到 effect 里的 promise 回调，避免同步 setState 级联渲染 */
  const requestRoleView = useCallback(
    (role: string) =>
      apiClient.get<RoleViewResult>(`/api/cognition/role-view?role=${encodeURIComponent(role)}`),
    [],
  );

  useEffect(() => {
    let ignore = false;
    requestRoleView(activeRole)
      .then((data) => {
        if (ignore) return;
        setRoleView(data);
        setError(null);
      })
      .catch((e: Error) => {
        if (ignore) return;
        setRoleView(null);
        setError(`${t('加载角色视图失败')}: ${e.message}`);
      })
      .finally(() => {
        // 失败也要落标记，否则 roleLoading 永远为 true、spinner 永久转
        if (!ignore) setLoadedRole(activeRole);
      });
    return () => { ignore = true; };
  }, [activeRole, requestRoleView, t]);

  const handleRecognizeIntent = async () => {
    if (!inputText.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const data = await apiClient.post<IntentResult>('/api/cognition/recognize-intent', {
        input_text: inputText,
        role: activeRole,
      });
      setIntentResult(data);
    } catch (e) {
      setIntentResult(null);
      setError(`${t('意图识别失败')}: ${(e as Error).message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExplain = async () => {
    if (!decisionId.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const data = await apiClient.post<ExplanationResult>('/api/cognition/explain', {
        decision_id: decisionId,
        context: { workspace_id: workspaceId, scenario_id: scenarioId },
      });
      setExplanation(data);
    } catch (e) {
      setExplanation(null);
      setError(`${t('解释生成失败')}: ${(e as Error).message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const renderIntentSection = () => (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Space>
        <Input
          aria-label={t('待识别文本')}
          placeholder={t('输入要识别意图的文本...')}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          style={{ width: 400 }}
          onPressEnter={() => void handleRecognizeIntent()}
        />
        <Button type="primary" icon={<SearchOutlined />} loading={actionLoading} onClick={() => void handleRecognizeIntent()}>
          {t('识别意图')}
        </Button>
      </Space>
      {!intentResult ? (
        <Empty description={t('暂无数据')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={2}>
            <Descriptions.Item label={t('意图类型')}>
              <Tag color="blue">{intentResult.primary_intent || t('未知')}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('置信度')}>
              <Progress
                percent={Math.round(intentResult.confidence * 100)}
                size="small"
                strokeColor={CONFIDENCE_COLOR(intentResult.confidence)}
              />
            </Descriptions.Item>
            <Descriptions.Item label={t('识别到的实体')} span={2}>
              {intentResult.entities.length > 0
                ? intentResult.entities.map((e) => <Tag key={e}>{e}</Tag>)
                : <Text type="secondary">—</Text>}
            </Descriptions.Item>
            <Descriptions.Item label={t('候选意图')} span={2}>
              {intentResult.alternative_intents.length > 0
                ? intentResult.alternative_intents.map((i) => <Tag key={i} color="default">{i}</Tag>)
                : <Text type="secondary">—</Text>}
            </Descriptions.Item>
          </Descriptions>
          {intentResult.attributes && Object.keys(intentResult.attributes).length > 0 && (
            <Card title={t('槽位参数')} size="small">
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
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Space>
        <Input
          aria-label={t('决策 ID')}
          placeholder={t('输入决策 ID 以生成解释...')}
          value={decisionId}
          onChange={(e) => setDecisionId(e.target.value)}
          style={{ width: 400 }}
          onPressEnter={() => void handleExplain()}
        />
        <Button type="primary" icon={<SearchOutlined />} loading={actionLoading} onClick={() => void handleExplain()}>
          {t('生成解释')}
        </Button>
      </Space>
      {!explanation ? (
        <Empty description={t('暂无数据')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={2}>
            <Descriptions.Item label={t('原始问题')}>{explanation.query}</Descriptions.Item>
            <Descriptions.Item label={t('置信度')}>
              <Progress
                percent={Math.round(explanation.confidence * 100)}
                size="small"
                strokeColor={CONFIDENCE_COLOR(explanation.confidence)}
              />
            </Descriptions.Item>
            <Descriptions.Item label={t('答案')} span={2}>{explanation.answer}</Descriptions.Item>
          </Descriptions>
          {explanation.reasoning_chain.length > 0 && (
            <ReasoningPath
              path={explanation.reasoning_chain.map((step, idx) => ({
                id: String(idx),
                title: ((step as Record<string, unknown>).title as string) || t('第 {{n}} 步', { n: idx + 1 }),
                description: ((step as Record<string, unknown>).description as string) || '',
                status: ((step as Record<string, unknown>).status as 'error' | 'wait' | 'process' | 'finish') || 'finish',
              }))}
            />
          )}
          {explanation.sources.length > 0 && (
            <Card title={t('证据来源')} size="small">
              {explanation.sources.map((s, i) => <Tag key={`${s}-${i}`} color="geekblue">{s}</Tag>)}
            </Card>
          )}
        </Space>
      )}
    </Space>
  );

  const renderRoleViewSection = () => {
    if (!roleView) {
      return <Empty description={t('暂无数据')} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Descriptions column={1}>
        <Descriptions.Item label={t('角色')}>
          <Tag color="purple">{roleView.role}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t('名称')}>{roleView.name || '—'}</Descriptions.Item>
        <Descriptions.Item label={t('描述')}>{roleView.description || '—'}</Descriptions.Item>
        <Descriptions.Item label={t('能力')}>
          {roleView.capabilities.length > 0
            ? roleView.capabilities.map((c) => <Tag key={c} color="cyan">{c}</Tag>)
            : <Text type="secondary">—</Text>}
        </Descriptions.Item>
      </Descriptions>
    );
  };

  const tabItems = [
    { key: 'intent', label: <span><BulbOutlined /> {t('意图识别')}</span>, children: renderIntentSection() },
    { key: 'reasoning', label: <span><CompassOutlined /> {t('解释链')}</span>, children: renderReasoningSection() },
    { key: 'role-view', label: <span><AimOutlined /> {t('角色视图')}</span>, children: renderRoleViewSection() },
  ];

  return (
    <Spin spinning={roleLoading || actionLoading}>
      <Card
        title={t('认知引擎')}
        size="small"
        extra={
          <Space>
            <Text type="secondary">{t('当前角色')}</Text>
            <Select
              aria-label={t('当前角色')}
              value={activeRole}
              onChange={setActiveRole}
              style={{ width: 140 }}
              options={ROLE_OPTIONS.map((o) => ({ value: o.value, label: t(o.labelKey) }))}
            />
          </Space>
        }
      >
        {error && (
          <Alert
            type="error"
            showIcon
            title={t('认知引擎调用失败')}
            description={error}
            style={{ marginBottom: 12 }}
          />
        )}
        <Tabs activeKey={activeTab} items={tabItems} onChange={setActiveTab} />
      </Card>
    </Spin>
  );
}
