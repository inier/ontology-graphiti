/**
 * GoalKanban 页面 —— Goal 状态看板（拖拽切换状态）（FR-037 / T428）
 *
 * 顶部：搜索框 + Workspace 筛选 + "New Goal" 按钮
 * 主区域：5 列看板布局
 *   - Proposed (黄) | Approved (蓝) | In Progress (绿) | Achieved (紫) | Abandoned (灰)
 *   - 每张卡片显示：title、business_objective 摘要、created_by、tag
 *   - 跨列拖动触发状态机 transition
 * 右侧详情 Drawer：完整 Goal 信息 + rationale + 关联的 ChangeProposal 列表 + Lineage 链接
 * 时间线视图：顶部 Switch 切换 → ECharts Gantt 展示所有 Goal 的时间线
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Card, Row, Col, Select, Input, Button, Space, Typography, Tag, Empty, Spin, Drawer, Descriptions, Switch, Modal, message, List, Tooltip,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  PlusOutlined, ReloadOutlined, ApartmentOutlined, FileTextOutlined, DragOutlined, AimOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { goalApi, type Goal, type GoalStatus, type ChangeProposal, type GoalLineage } from '../services/goalApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { useWorkspaceStore } from '@/modules/workspace/stores/workspaceStore';

const { Text, Title } = Typography;
const { Search } = Input;
const { TextArea } = Input;

interface KanbanColumn {
  status: GoalStatus;
  titleKey: string;
  color: string;
  bg: string;
}

const COLUMN_DEFS: KanbanColumn[] = [
  { status: 'proposed', titleKey: 'column.proposed', color: '#d48806', bg: '#fffbe6' },
  { status: 'approved', titleKey: 'column.approved', color: '#1677ff', bg: '#e6f4ff' },
  { status: 'in-progress', titleKey: 'column.inProgress', color: '#52c41a', bg: '#f6ffed' },
  { status: 'achieved', titleKey: 'column.achieved', color: '#722ed1', bg: '#f9f0ff' },
  { status: 'abandoned', titleKey: 'column.abandoned', color: '#8c8c8c', bg: '#fafafa' },
];

interface CreateFormValues {
  title: string;
  business_objective: string;
  description?: string;
  parent_goal_id?: string;
  tags?: string;
}

export function GoalKanban() {
  const { t } = useI18n('ontology');
  const { workspaces, currentWorkspace, loadWorkspaces } = useWorkspaceStore();

  const COLUMNS: KanbanColumn[] = useMemo(
    () => COLUMN_DEFS.map((c) => ({ ...c, title: t(c.titleKey) })),
    [t],
  );

  const [workspaceId, setWorkspaceId] = useState<string | undefined>(currentWorkspace?.workspace_id);
  const [searchText, setSearchText] = useState('');
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<CreateFormValues>();
  const [creating, setCreating] = useState(false);

  const [selectedGoal, setSelectedGoal] = useState<Goal | null>(null);
  const [lineage, setLineage] = useState<GoalLineage | null>(null);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [goalProposals, setGoalProposals] = useState<ChangeProposal[]>([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);

  const [timelineMode, setTimelineMode] = useState(false);
  const timelineRef = useRef<HTMLDivElement>(null);
  const timelineChart = useRef<echarts.ECharts | null>(null);

  // Drag state
  const [draggingGoalId, setDraggingGoalId] = useState<string | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<GoalStatus | null>(null);

  useEffect(() => {
    if (workspaces.length === 0) void loadWorkspaces();
  }, [workspaces.length, loadWorkspaces]);

  useEffect(() => {
    if (!workspaceId && currentWorkspace) {
      setWorkspaceId(currentWorkspace.workspace_id);
    }
  }, [workspaceId, currentWorkspace]);

  const fetchGoals = useCallback(async (wsId: string) => {
    setLoading(true);
    try {
      const data = await goalApi.list({ workspace_id: wsId, page_size: 200 });
      setGoals(data.goals || []);
    } catch (e) {
      message.error(`${t('goal.loadFailed')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (workspaceId) void fetchGoals(workspaceId);
  }, [workspaceId, fetchGoals]);

  const goalsByColumn = useMemo(() => {
    const map: Record<GoalStatus, Goal[]> = {
      proposed: [],
      approved: [],
      rejected: [],
      'in-progress': [],
      achieved: [],
      abandoned: [],
    };
    goals.forEach((g) => {
      const status = g.status as GoalStatus;
      if (!map[status]) map[status] = [];
      map[status].push(g);
    });
    // 搜索过滤
    if (searchText) {
      const kw = searchText.toLowerCase();
      (Object.keys(map) as GoalStatus[]).forEach((k) => {
        map[k] = map[k].filter(
          (g) => g.title.toLowerCase().includes(kw) || g.business_objective.toLowerCase().includes(kw),
        );
      });
    }
    return map;
  }, [goals, searchText]);

  const handleNewGoal = useCallback(() => {
    createForm.resetFields();
    setCreateOpen(true);
  }, [createForm]);

  const handleCreate = useCallback(async () => {
    if (!workspaceId) {
      message.warning(t('goal.selectWorkspaceWarn'));
      return;
    }
    try {
      const values = await createForm.validateFields();
      setCreating(true);
      const user = (() => {
        try { return JSON.parse(localStorage.getItem('user') || '{}')?.username || 'system'; } catch { return 'system'; }
      })();
      const tags = values.tags ? values.tags.split(',').map((s) => s.trim()).filter(Boolean) : [];
      await goalApi.create({
        title: values.title,
        business_objective: values.business_objective,
        description: values.description || '',
        workspace_id: workspaceId,
        created_by: user,
        parent_goal_id: values.parent_goal_id || undefined,
        tags,
      });
      message.success(t('goal.createSuccess'));
      setCreateOpen(false);
      void fetchGoals(workspaceId);
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`${t('goal.createFailed')}: ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }, [createForm, workspaceId, fetchGoals, t]);

  const handleDragStart = useCallback((goalId: string) => (e: React.DragEvent) => {
    setDraggingGoalId(goalId);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', goalId);
  }, []);

  const handleDragOver = useCallback((status: GoalStatus) => (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverColumn(status);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverColumn(null);
  }, []);

  const handleDrop = useCallback(async (targetStatus: GoalStatus) => {
    setDragOverColumn(null);
    if (!draggingGoalId) return;
    const goal = goals.find((g) => g.id === draggingGoalId);
    if (!goal) return;
    if (goal.status === targetStatus) {
      setDraggingGoalId(null);
      return;
    }
    setDraggingGoalId(null);
    try {
      const updated = await goalApi.transition(goal.id, targetStatus);
      setGoals((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
      message.success(t('goal.switchedTo', { status: targetStatus }));
    } catch (e) {
      message.error(`${t('goal.transitionFailed')}: ${(e as Error).message}`);
    }
  }, [draggingGoalId, goals, t]);

  const fetchLineage = useCallback(async (goalId: string) => {
    setLineageLoading(true);
    try {
      const data = await goalApi.getLineage(goalId);
      setLineage(data);
    } catch (e) {
      message.error(`${t('goal.lineageFailed')}: ${(e as Error).message}`);
    } finally {
      setLineageLoading(false);
    }
  }, [t]);

  const fetchProposals = useCallback(async (goalId: string) => {
    setProposalsLoading(true);
    try {
      const data = await goalApi.listProposals(goalId);
      setGoalProposals(data.proposals || []);
    } catch {
      setGoalProposals([]);
    } finally {
      setProposalsLoading(false);
    }
  }, []);

  const openGoalDetail = useCallback(async (goal: Goal) => {
    setSelectedGoal(goal);
    setLineage(null);
    setGoalProposals([]);
    void fetchLineage(goal.id);
    void fetchProposals(goal.id);
  }, [fetchLineage, fetchProposals]);

  // Timeline (Gantt) chart
  useEffect(() => {
    if (!timelineMode || !timelineRef.current) return;
    if (timelineChart.current) {
      try { timelineChart.current.dispose(); } catch { /* noop */ }
    }
    timelineChart.current = echarts.init(timelineRef.current);
    const items = goals.map((g, idx) => ({
      name: g.title,
      value: [
        idx,
        new Date(g.created_at).getTime(),
        new Date(g.updated_at).getTime() + 86400000,
        g.status,
        g,
      ],
      itemStyle: { color: COLUMNS.find((c) => c.status === g.status)?.color || '#999' },
    }));
    timelineChart.current.setOption({
      tooltip: {
        formatter: (p: { value: [number, number, number, string, Goal] }) => {
          const g = p.value[4];
          return `<b>${g.title}</b><br/>${g.status}<br/>${new Date(g.created_at).toLocaleDateString()} ~ ${new Date(g.updated_at).toLocaleDateString()}`;
        },
      },
      grid: { left: 200, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'time' },
      yAxis: {
        type: 'category',
        data: goals.map((g) => g.title),
        inverse: true,
        axisLabel: { fontSize: 11 },
      },
      series: [
        {
          type: 'custom',
          renderItem: (_params: unknown, api: { value: (idx: number) => number; coord: (vals: number[]) => [number, number]; size: (vals: number[]) => [number, number] }) => {
            const idx = api.value(0);
            const start = api.coord([api.value(1), idx]);
            const end = api.coord([api.value(2), idx]);
            const height = api.size([0, 1])[1] * 0.6;
            return {
              type: 'rect',
              shape: {
                x: start[0],
                y: start[1] - height / 2,
                width: Math.max(2, end[0] - start[0]),
                height,
                r: 2,
              },
              style: { fill: '#1677ff' },
            };
          },
          encode: { x: [1, 2], y: 0 },
          data: items,
        },
      ],
    });
    const onResize = () => timelineChart.current?.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      timelineChart.current?.dispose();
      timelineChart.current = null;
    };
  }, [timelineMode, goals, COLUMNS]);

  const handleRefresh = useCallback(() => {
    if (workspaceId) void fetchGoals(workspaceId);
  }, [workspaceId, fetchGoals]);

  return (
    <div data-testid="goal-kanban" style={{ padding: 16 }}>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row gutter={8} align="middle" justify="space-between">
          <Col xs={24} md={16}>
            <Space wrap>
              <Title level={4} style={{ margin: 0 }}>
                <AimOutlined /> {t('goal.kanban')}
              </Title>
              <Select
                placeholder={t('goal.selectWorkspace')}
                style={{ minWidth: 200 }}
                value={workspaceId}
                onChange={(v) => setWorkspaceId(v)}
                options={workspaces.map((w) => ({ value: w.workspace_id, label: w.name }))}
                allowClear
              />
              <Search
                placeholder={t('goal.searchGoal')}
                allowClear
                style={{ width: 200 }}
                onChange={(e) => setSearchText(e.target.value)}
                onSearch={setSearchText}
              />
            </Space>
          </Col>
          <Col xs={24} md={8} style={{ textAlign: 'right' }}>
            <Space>
              <Space size={4}>
                <Text type="secondary">{t('goal.timeline')}</Text>
                <Switch checked={timelineMode} onChange={setTimelineMode} />
              </Space>
              <Button icon={<ReloadOutlined />} onClick={handleRefresh}>{t('goal.refresh')}</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={handleNewGoal}>
                {t('goal.newGoalBtn')}
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        {!workspaceId ? (
          <Empty description={t('goal.selectWorkspaceFirst')} />
        ) : timelineMode ? (
          <Card size="small" title={t('goal.ganttTitle')}>
            <div ref={timelineRef} style={{ width: '100%', height: 500 }} />
            {goals.length === 0 && <Empty description={t('goal.noData')} />}
          </Card>
        ) : (
          <Row gutter={8}>
            {COLUMNS.map((col) => {
              const list = goalsByColumn[col.status] || [];
              const isOver = dragOverColumn === col.status;
              return (
                <Col xs={24} sm={12} md={8} lg={Math.floor(24 / COLUMNS.length)} key={col.status} style={{ flex: 1 }}>
                  <div
                    onDragOver={handleDragOver(col.status)}
                    onDragLeave={handleDragLeave}
                    onDrop={() => void handleDrop(col.status)}
                    style={{ minHeight: 200 }}
                  >
                    <Card
                      size="small"
                      title={
                        <Space>
                          <span style={{ color: col.color, fontWeight: 600 }}>{col.title}</span>
                          <Tag color={col.color}>{list.length}</Tag>
                        </Space>
                      }
                      style={{
                        background: isOver ? col.bg : undefined,
                        borderColor: isOver ? col.color : undefined,
                        minHeight: 200,
                      }}
                    >
                      {list.length === 0 ? (
                        <Empty description={t('goal.dropHere')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Space orientation="vertical" style={{ width: '100%' }} size={6}>
                          {list.map((g) => (
                            <Card
                              key={g.id}
                              size="small"
                              draggable
                              onDragStart={handleDragStart(g.id)}
                              onClick={() => void openGoalDetail(g)}
                              style={{
                                cursor: 'grab',
                                borderLeft: `3px solid ${col.color}`,
                                background: '#fff',
                                opacity: draggingGoalId === g.id ? 0.5 : 1,
                              }}
                              styles={{ body: { padding: 8 } }}
                            >
                              <Space orientation="vertical" size={2} style={{ width: '100%' }}>
                                <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                                  <Text strong style={{ fontSize: 13 }}>{g.title}</Text>
                                  <DragOutlined style={{ color: '#999' }} />
                                </Space>
                                <Text type="secondary" style={{ fontSize: 11 }} ellipsis>
                                  {g.business_objective}
                                </Text>
                                <Space wrap size={4} style={{ fontSize: 11 }}>
                                  <Text type="secondary" style={{ fontSize: 11 }}>{t('goal.by', { user: g.created_by })}</Text>
                                  {(g.tags || []).slice(0, 2).map((tag) => (
                                    <Tag key={tag} style={{ fontSize: 10, padding: '0 4px', margin: 0 }}>{tag}</Tag>
                                  ))}
                                </Space>
                              </Space>
                            </Card>
                          ))}
                        </Space>
                      )}
                    </Card>
                  </div>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>

      <Drawer
        title={selectedGoal ? selectedGoal.title : t('goal.goalDetail')}
        open={!!selectedGoal}
        onClose={() => setSelectedGoal(null)}
        width={560}
      >
        {selectedGoal && (
          <Spin spinning={lineageLoading || proposalsLoading}>
            <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
              <Card size="small">
                <Descriptions column={1}>
                  <Descriptions.Item label={t('goal.labelTitle')}>{selectedGoal.title}</Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelBusinessObjective')}>{selectedGoal.business_objective}</Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelDescription')}>{selectedGoal.description || '-'}</Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelStatus')}>
                    <Tag color={COLUMNS.find((c) => c.status === selectedGoal.status)?.color || 'default'}>
                      {selectedGoal.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelWorkspace')}>{selectedGoal.workspace_id}</Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelCreatedBy')}>{selectedGoal.created_by}</Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelTags')}>
                    {(selectedGoal.tags || []).map((tag) => <Tag key={tag}>{tag}</Tag>)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('goal.labelCreatedAt')}>
                    {new Date(selectedGoal.created_at).toLocaleString()}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              {selectedGoal.rationale && (
                <Card size="small" title={t('goal.rationaleTitle')}>
                  <Text>{selectedGoal.rationale}</Text>
                </Card>
              )}

              <Card size="small" title={t('goal.relatedProposals')}>
                {goalProposals.length === 0 ? (
                  <Empty description={t('goal.noProposals')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <List
                    size="small"
                    dataSource={goalProposals}
                    renderItem={(p) => (
                      <List.Item>
                        <Space orientation="vertical" size={2} style={{ width: '100%' }}>
                          <Space>
                            <FileTextOutlined />
                            <Text strong>{p.title}</Text>
                            <Tag color="blue">{p.status}</Tag>
                          </Space>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('goal.by', { user: p.proposed_by })} · {new Date(p.created_at).toLocaleString()}
                          </Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>

              <Card size="small" title={
                <Space>
                  <ApartmentOutlined /> {t('goal.lineageTitle')}
                </Space>
              }>
                {lineage ? (
                  <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                    {lineage.ancestors.length > 0 && (
                      <div>
                        <Text type="secondary">{t('goal.ancestors')}</Text>
                        <Space wrap>
                          {lineage.ancestors.map((g) => (
                            <Tag key={g.id} color="blue">{g.title}</Tag>
                          ))}
                        </Space>
                      </div>
                    )}
                    {lineage.children.length > 0 && (
                      <div>
                        <Text type="secondary">{t('goal.children')}</Text>
                        <Space wrap>
                          {lineage.children.map((g) => (
                            <Tag key={g.id} color="green">{g.title}</Tag>
                          ))}
                        </Space>
                      </div>
                    )}
                    {lineage.proposals.length > 0 && (
                      <div>
                        <Text type="secondary">{t('goal.proposal')}</Text>
                        <Space wrap>
                          {lineage.proposals.map((p) => (
                            <Tooltip key={p.id} title={p.title}>
                              <Tag color="purple">{p.title}</Tag>
                            </Tooltip>
                          ))}
                        </Space>
                      </div>
                    )}
                    {lineage.ancestors.length === 0 && lineage.children.length === 0 && lineage.proposals.length === 0 && (
                      <Text type="secondary">{t('goal.noLineage')}</Text>
                    )}
                  </Space>
                ) : (
                  <Empty description={t('goal.lineageEmpty')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Space>
          </Spin>
        )}
      </Drawer>

      <Modal
        title={t('goal.createTitle')}
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={creating}
        okText={t('goal.createOk')}
        cancelText={t('goal.createCancel')}
        destroyOnHidden
      >
        <Form<CreateFormValues> form={createForm} layout="vertical">
          <Form.Item
            name="title"
            label={t('goal.labelTitle')}
            rules={[{ required: true, message: t('goal.titleRequired') }]}
          >
            <Input placeholder={t('goal.titlePlaceholder')} />
          </Form.Item>
          <Form.Item
            name="business_objective"
            label={t('goal.labelBusinessObjective')}
            rules={[{ required: true, message: t('goal.businessObjectiveRequired') }]}
          >
            <TextArea rows={2} placeholder={t('goal.businessObjectivePlaceholder')} />
          </Form.Item>
          <Form.Item name="description" label={t('goal.labelDescription')}>
            <TextArea rows={2} placeholder={t('goal.descriptionOptional')} />
          </Form.Item>
          <Form.Item name="parent_goal_id" label={t('goal.parentGoalIdOptional')}>
            <Input placeholder={t('goal.parentGoalIdPlaceholder')} />
          </Form.Item>
          <Form.Item name="tags" label={`${t('goal.labelTags')}（逗号分隔）`}>
            <Input placeholder={t('goal.tagsPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default GoalKanban;
