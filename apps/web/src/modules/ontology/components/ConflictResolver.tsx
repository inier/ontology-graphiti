/**
 * ConflictResolver 组件 —— 多源冲突解决前端（L3 组织组件）
 *
 * 用途：
 *   1. 调用 POST /api/ontology/conflict/detect 检测多源数据中的实体字段冲突
 *   2. 展示冲突列表（entity_id / field_name / 候选值对比）
 *   3. 用户选择策略（first_wins / last_wins / llm_judge / manual）
 *   4. 调用 POST /api/ontology/conflict/resolve 解决冲突
 *   5. 展示 chosen source/value + rationale
 *
 * 后端契约参考 SC-01 / T320。后端测试 21 个用例（commit c6a4d16）。
 *
 * Props: 无（自包含演示组件；mock 数据用于快速验证）。
 *
 * 使用：
 *   import ConflictResolver from '@/modules/ontology/components/ConflictResolver';
 *   <ConflictResolver />
 */
import { useState, useCallback, useMemo } from 'react';
import {
  Card, Button, Tag, Space, Alert, Typography, message,
  Radio, Divider, Empty, Tooltip, Input, Tabs,
} from 'antd';
import {
  ScanOutlined, ThunderboltOutlined, CheckCircleOutlined,
  ClockCircleOutlined, RobotOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { STRATEGY_OPTIONS } from './types';
import {
  type ConflictStrategy,
  type ConflictRecord,
  type ConflictSource,
  type ConflictCandidate,
  type DetectConflictsResponse,
  type ResolveConflictResponse,
  type ListConflictsResponse,
  type ResolveConflictRequest,
} from './types';

const { Text, Title, Paragraph } = Typography;

const API_BASE = '/api/ontology/conflict';

// ----------- 默认 mock 数据（演示用，可在 UI 中编辑修改） -----------
const DEFAULT_MOCK_SOURCES: ConflictSource[] = [
  {
    source_id: 'src1_crm',
    entities: [
      { id: 'e1', type: 'Customer', fields: { email: 'alice@example.com', name: 'Alice', phone: '13800000001' } },
    ],
  },
  {
    source_id: 'src2_billing',
    entities: [
      { id: 'e1', type: 'Customer', fields: { email: 'alice@another.com', name: 'Alice', phone: '13800000001' } },
    ],
  },
  {
    source_id: 'src3_form',
    entities: [
      { id: 'e1', type: 'Customer', fields: { email: 'alice@example.com', name: 'Alice W', phone: '13800000002' } },
    ],
  },
];

const STATUS_META: Record<string, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  resolved: { color: 'success', icon: <CheckCircleOutlined /> },
  awaiting_human: { color: 'warning', icon: <ClockCircleOutlined /> },
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'conflict.status.pending',
  resolved: 'conflict.status.resolved',
  awaiting_human: 'conflict.status.awaitingHuman',
};

export default function ConflictResolver() {
  const { t } = useI18n('ontology');

  const formatValue = (v: unknown): string => {
    if (v === null || v === undefined) return t('(空)');
    if (typeof v === 'string') return v;
    return JSON.stringify(v);
  };
  // 冲突列表
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  // 当前选中的冲突 ID
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // 策略
  const [strategy, setStrategy] = useState<ConflictStrategy>('first_wins');
  // 最近一次解决结果
  const [lastResult, setLastResult] = useState<ResolveConflictResponse | null>(null);

  // 加载/请求态
  const [detecting, setDetecting] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [judging, setJudging] = useState(false);
  const [loadingPending, setLoadingPending] = useState(false);

  // mock 源（JSON 编辑）
  const [mockSourcesText, setMockSourcesText] = useState<string>(
    JSON.stringify(DEFAULT_MOCK_SOURCES, null, 2),
  );

  // 当前冲突
  const selected = useMemo<ConflictRecord | null>(
    () => conflicts.find((c) => c.id === selectedId) ?? null,
    [conflicts, selectedId],
  );

  // --------- 调用 /detect ---------
  const handleDetect = useCallback(async () => {
    let sources: ConflictSource[];
    try {
      sources = JSON.parse(mockSourcesText);
      if (!Array.isArray(sources)) {
        throw new Error(t('sources 必须是数组'));
      }
    } catch (e) {
      message.error(t('conflict.mockParseFailed', { msg: (e as Error).message }));
      return;
    }

    setDetecting(true);
    setLastResult(null);
    try {
      const data = await apiClient.post<DetectConflictsResponse>(
        `${API_BASE}/detect`,
        { sources },
      );
      setConflicts(data.conflicts || []);
      setSelectedId((data.conflicts?.[0]?.id) ?? null);
      if ((data.conflicts?.length ?? 0) === 0) {
        message.success(t('暂无冲突'));
      } else {
        message.success(t('conflict.conflictsDetected', { count: data.count }));
      }
    } catch (e) {
      message.error(t('conflict.detectFailed', { msg: (e as Error).message }));
    } finally {
      setDetecting(false);
    }
  }, [mockSourcesText]);

  // --------- 加载待处理冲突 ---------
  const handleLoadPending = useCallback(async () => {
    setLoadingPending(true);
    try {
      const data = await apiClient.get<ListConflictsResponse>(
        `${API_BASE}/conflicts?status=pending`,
      );
      setConflicts(data.conflicts || []);
      setSelectedId((data.conflicts?.[0]?.id) ?? null);
      message.success(t('conflict.loadedPending', { count: data.count }));
    } catch (e) {
      message.error(t('conflict.loadFailed', { msg: (e as Error).message }));
    } finally {
      setLoadingPending(false);
    }
  }, []);

  // --------- 通用 /resolve ---------
  const doResolve = useCallback(
    async (conflict: ConflictRecord, chosenStrategy: ConflictStrategy) => {
      const payload: ResolveConflictRequest = {
        conflict,
        strategy: chosenStrategy,
        context: {},
      };
      return apiClient.post<ResolveConflictResponse>(`${API_BASE}/resolve`, payload);
    },
    [],
  );

  // --------- 解决（按所选策略） ---------
  const handleResolve = useCallback(async () => {
    if (!selected) {
      message.warning(t('请先选择一条冲突'));
      return;
    }
    if (selected.status !== 'pending') {
      message.warning(t('该冲突已处理'));
      return;
    }
    setResolving(true);
    setLastResult(null);
    try {
      const result = await doResolve(selected, strategy);
      setLastResult(result);
      // 同步更新本地列表
      setConflicts((prev) =>
        prev.map((c) =>
          c.id === result.conflict_id
            ? {
                ...c,
                status: result.status,
                strategy: result.strategy_used,
                chosen: result.chosen,
                rationale: result.rationale,
              }
            : c,
        ),
      );
      message.success(t('conflict.resolved', { status: t(STATUS_LABELS[result.status] || result.status) }));
    } catch (e) {
      message.error(t('conflict.resolveFailed', { msg: (e as Error).message }));
    } finally {
      setResolving(false);
    }
  }, [selected, strategy, doResolve]);

  // --------- LLM 判断（独立入口） ---------
  const handleLLMJudge = useCallback(async () => {
    if (!selected) {
      message.warning(t('请先选择一条冲突'));
      return;
    }
    setJudging(true);
    setLastResult(null);
    try {
      const result = await doResolve(selected, 'llm_judge');
      setLastResult(result);
      setConflicts((prev) =>
        prev.map((c) =>
          c.id === result.conflict_id
            ? {
                ...c,
                status: result.status,
                strategy: 'llm_judge',
                chosen: result.chosen,
                rationale: result.rationale,
              }
            : c,
        ),
      );
      message.success(t('LLM 仲裁完成'));
    } catch (e) {
      message.error(t('conflict.llmJudgeFailed', { msg: (e as Error).message }));
    } finally {
      setJudging(false);
    }
  }, [selected, doResolve]);

  // --------- 列表列 ---------
  const columns = [
    {
      title: t('冲突 ID'),
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (v: string) => <Text code style={{ fontSize: 12 }}>{v.slice(0, 8)}…</Text>,
    },
    { title: t('实体'), dataIndex: 'entity_id', key: 'entity_id', width: 100 },
    { title: t('类型'), dataIndex: 'entity_type', key: 'entity_type', width: 110 },
    {
      title: t('字段'),
      dataIndex: 'field_name',
      key: 'field_name',
      width: 120,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: t('冲突类型'),
      dataIndex: 'conflict_type',
      key: 'conflict_type',
      width: 110,
      render: (v: string) => <Tag color="purple">{v}</Tag>,
    },
    {
      title: t('候选数'),
      dataIndex: 'candidates',
      key: 'candidates',
      width: 80,
      render: (cs: ConflictCandidate[]) => cs?.length ?? 0,
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (s: string) => {
        const meta = STATUS_META[s] ?? { color: 'default', icon: null };
        return (
          <Tag color={meta.color} icon={meta.icon as React.ReactElement}>
            {t(STATUS_LABELS[s] || s)}
          </Tag>
        );
      },
    },
  ];

  // --------- 候选值对比表 ---------
  const candidateColumns = [
    {
      title: t('数据源'),
      dataIndex: 'source_id',
      key: 'source_id',
      render: (v: string) => <Tag color="cyan">{v}</Tag>,
    },
    {
      title: t('候选值'),
      dataIndex: 'value',
      key: 'value',
      render: (v: unknown) => (
        <Text strong style={{ fontFamily: 'monospace' }}>{formatValue(v)}</Text>
      ),
    },
    {
      title: t('置信度'),
      dataIndex: 'confidence',
      key: 'confidence',
      width: 110,
      render: (v: number) => `${(v * 100).toFixed(0)}%`,
    },
    {
      title: t('观测时间'),
      dataIndex: 'observed_at',
      key: 'observed_at',
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
  ];

  return (
    <div data-testid="conflict-resolver" style={{ padding: 16 }}>
      <Title level={3} style={{ marginTop: 0 }}>
        <ThunderboltOutlined /> {t('多源冲突解决')}
      </Title>
      <Paragraph type="secondary">
        {t('检测来自多个数据源的实体字段冲突，并按策略（first_wins / last_wins / llm_judge / manual）解决。')}
      </Paragraph>

      <Tabs
        defaultActiveKey="detect"
        items={[
          {
            key: 'detect',
            label: t('检测冲突'),
            children: (
              <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                <Card
                  title={t('多源数据（演示用 mock）')}
                  size="small"
                  extra={
                    <Space>
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        onClick={() => setMockSourcesText(JSON.stringify(DEFAULT_MOCK_SOURCES, null, 2))}
                      >
                        {t('重置')}
                      </Button>
                    </Space>
                  }
                >
                  <Input.TextArea
                    rows={10}
                    value={mockSourcesText}
                    onChange={(e) => setMockSourcesText(e.target.value)}
                    spellCheck={false}
                    style={{ fontFamily: 'monospace', fontSize: 12 }}
                  />
                </Card>

                <Space>
                  <Button
                    type="primary"
                    icon={<ScanOutlined />}
                    onClick={handleDetect}
                    loading={detecting}
                  >
                    {t('检测冲突')}
                  </Button>
                  <Button
                    icon={<ClockCircleOutlined />}
                    onClick={handleLoadPending}
                    loading={loadingPending}
                  >
                    {t('加载后端待处理列表')}
                  </Button>
                </Space>

                {conflicts.length === 0 ? (
                  <Empty description={t('暂无冲突')} />
                ) : (
                  <Card title={t('conflict.list', { count: conflicts.length })} size="small">
                    <AdvancedTable<ConflictRecord>
                      rowKey="id"
                      size="small"
                      dataSource={conflicts}
                      columns={columns}
                      pagination={false}
                      rowClassName={(r) => (r.id === selectedId ? 'ant-table-row-selected' : '')}
                      onRow={(record) => ({
                        onClick: () => setSelectedId(record.id),
                        style: { cursor: 'pointer' },
                      })}
                    />
                  </Card>
                )}
              </Space>
            ),
          },
          {
            key: 'resolve',
            label: t('解决冲突'),
            children: selected ? (
              <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                <Card
                  title={
                    <Space>
                      <Text>{t('冲突详情')}</Text>
                      <Tag color={STATUS_META[selected.status]?.color}>
                        {t(STATUS_LABELS[selected.status] || selected.status)}
                      </Tag>
                    </Space>
                  }
                  size="small"
                >
                  <Space wrap>
                    <Text>{t('实体')}：<Text strong>{selected.entity_id}</Text></Text>
                    <Text>{t('类型')}：<Tag>{selected.entity_type}</Tag></Text>
                    <Text>{t('字段')}：<Tag color="blue">{selected.field_name}</Tag></Text>
                    <Text>{t('冲突类型')}：<Tag color="purple">{selected.conflict_type}</Tag></Text>
                    <Text>{t('检测时间')}：<Text type="secondary">{new Date(selected.detected_at).toLocaleString()}</Text></Text>
                  </Space>

                  <Divider style={{ margin: '12px 0' }} />

                  <Title level={5}>{t('候选值对比')}</Title>
                  <AdvancedTable<ConflictCandidate>
                    rowKey={(r) => `${r.source_id}-${r.observed_at}`}
                    size="small"
                    dataSource={selected.candidates}
                    columns={candidateColumns}
                    pagination={false}
                  />
                </Card>

                <Card title={t('选择策略')} size="small">
                  <Radio.Group
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value as ConflictStrategy)}
                    disabled={selected.status !== 'pending'}
                  >
                    <Space orientation="vertical">
                      {STRATEGY_OPTIONS.map((opt) => (
                        <Radio key={opt.value} value={opt.value}>
                          <Space>
                            <Text strong>{opt.label}</Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {opt.description}
                            </Text>
                          </Space>
                        </Radio>
                      ))}
                    </Space>
                  </Radio.Group>
                </Card>

                <Space>
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={handleResolve}
                    loading={resolving}
                    disabled={selected.status !== 'pending'}
                  >
                    {t('解决冲突')}
                  </Button>
                  <Tooltip title={t('使用后端 LLM 仲裁，独立于当前策略选择')}>
                    <Button
                      icon={<RobotOutlined />}
                      onClick={handleLLMJudge}
                      loading={judging}
                      disabled={selected.status !== 'pending'}
                    >
                      {t('LLM 判断')}
                    </Button>
                  </Tooltip>
                </Space>

                {lastResult && (
                  <Alert
                    type={lastResult.status === 'resolved' ? 'success' : 'warning'}
                    showIcon
                    title={
                      <Space>
                        <CheckCircleOutlined />
                        <Text strong>
                          {lastResult.status === 'resolved' ? t('冲突已解决') : t('已标记为等待人工')}
                        </Text>
                        <Tag color="blue">strategy={lastResult.strategy_used}</Tag>
                        <Text type="secondary">{t('conflict.duration', { ms: (lastResult.duration_ms ?? 0).toFixed(2) })}</Text>
                      </Space>
                    }
                    description={
                      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                        {lastResult.chosen ? (
                          <Space>
                            <Text>{t('chosen')}：</Text>
                            <Tag color="cyan">{lastResult.chosen.source_id}</Tag>
                            <Text strong style={{ fontFamily: 'monospace' }}>
                              {formatValue(lastResult.chosen.value)}
                            </Text>
                            <Text type="secondary">
                              confidence={(lastResult.chosen.confidence * 100).toFixed(0)}%
                            </Text>
                          </Space>
                        ) : (
                          <Text type="secondary">{t('conflict.noChosen', { status: lastResult.status })}</Text>
                        )}
                        {lastResult.rationale && (
                          <Text>
                            <Text type="secondary">{t('rationale')}：</Text>
                            {lastResult.rationale}
                          </Text>
                        )}
                      </Space>
                    }
                  />
                )}
              </Space>
            ) : (
              <Empty description={t('请先在「检测冲突」标签页中检测并选择一条冲突')} />
            ),
          },
        ]}
      />
    </div>
  );
}
