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
  Card, Row, Col, Select, Input, Button, Space, Typography, Tag, Empty, Spin, Drawer, Descriptions, Switch, Modal, Form, message, List, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, ApartmentOutlined, FileTextOutlined, DragOutlined, AimOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { goalApi, type Goal, type GoalStatus, type ChangeProposal, type GoalLineage } from '../services/goalApi';
import { useI18n } from '../../shared/hooks/useI18n';
import { useWorkspaceStore } from '../../workspace/stores/workspaceStore';

const { Text, Title } = Typography;
const { Search } = Input;
const { TextArea } = Input;

interface KanbanColumn {
  status: GoalStatus;
  title: string;
  color: string;
  bg: string;
}

const COLUMNS: KanbanColumn[] = [
  { status: 'proposed', title: 'Proposed', color: '#d48806', bg: '#fffbe6' },
  { status: 'approved', title: 'Approved', color: '#1677ff', bg: '#e6f4ff' },
  { status: 'in-progress', title: 'In Progress', color: '#52c41a', bg: '#f6ffed' },
  { status: 'achieved', title: 'Achieved', color: '#722ed1', bg: '#f9f0ff' },
  { status: 'abandoned', title: 'Abandoned', color: '#8c8c8c', bg: '#fafafa' },
];

interface CreateFormValues {
  title: string;
  business_objective: string;
  description?: string;
  parent_goal_id?: string;
  tags?: string;
}

export function GoalKanban() {
  const { t } = useI18n();
  void t;
  const { workspaces, currentWorkspace, loadWorkspaces } = useWorkspaceStore();

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
      message.error(`加载 Goal 失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

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
      message.warning('请先选择 Workspace');
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
      message.success('Goal 已创建');
      setCreateOpen(false);
      void fetchGoals(workspaceId);
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`创建失败: ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }, [createForm, workspaceId, fetchGoals]);

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
      message.success(`已切换到 ${targetStatus}`);
    } catch (e) {
      message.error(`状态切换失败: ${(e as Error).message}`);
    }
  }, [draggingGoalId, goals]);

  const fetchLineage = useCallback(async (goalId: string) => {
    setLineageLoading(true);
    try {
      const data = await goalApi.getLineage(goalId);
      setLineage(data);
    } catch (e) {
      message.error(`加载血缘失败: ${(e as Error).message}`);
    } finally {
      setLineageLoading(false);
    }
  }, []);

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
  }, [timelineMode, goals]);

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
                <AimOutlined /> Goal 看板
              </Title>
              <Select
                placeholder="选择 Workspace"
                style={{ minWidth: 200 }}
                value={workspaceId}
                onChange={(v) => setWorkspaceId(v)}
                options={workspaces.map((w) => ({ value: w.workspace_id, label: w.name }))}
                allowClear
              />
              <Search
                placeholder="搜索 Goal"
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
                <Text type="secondary">时间线</Text>
                <Switch checked={timelineMode} onChange={setTimelineMode} />
              </Space>
              <Button icon={<ReloadOutlined />} onClick={handleRefresh}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={handleNewGoal}>
                New Goal
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        {!workspaceId ? (
          <Empty description="请先选择一个 Workspace" />
        ) : timelineMode ? (
          <Card size="small" title="Goal 时间线 (Gantt)">
            <div ref={timelineRef} style={{ width: '100%', height: 500 }} />
            {goals.length === 0 && <Empty description="暂无数据" />}
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
                        <Empty description="拖动卡片到此处" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Space direction="vertical" style={{ width: '100%' }} size={6}>
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
                              bodyStyle={{ padding: 8 }}
                            >
                              <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                                  <Text strong style={{ fontSize: 13 }}>{g.title}</Text>
                                  <DragOutlined style={{ color: '#999' }} />
                                </Space>
                                <Text type="secondary" style={{ fontSize: 11 }} ellipsis>
                                  {g.business_objective}
                                </Text>
                                <Space wrap size={4} style={{ fontSize: 11 }}>
                                  <Text type="secondary" style={{ fontSize: 11 }}>by {g.created_by}</Text>
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
        title={selectedGoal ? selectedGoal.title : 'Goal 详情'}
        open={!!selectedGoal}
        onClose={() => setSelectedGoal(null)}
        width={560}
      >
        {selectedGoal && (
          <Spin spinning={lineageLoading || proposalsLoading}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Card size="small">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="标题">{selectedGoal.title}</Descriptions.Item>
                  <Descriptions.Item label="业务目标">{selectedGoal.business_objective}</Descriptions.Item>
                  <Descriptions.Item label="描述">{selectedGoal.description || '-'}</Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={COLUMNS.find((c) => c.status === selectedGoal.status)?.color || 'default'}>
                      {selectedGoal.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Workspace">{selectedGoal.workspace_id}</Descriptions.Item>
                  <Descriptions.Item label="创建者">{selectedGoal.created_by}</Descriptions.Item>
                  <Descriptions.Item label="标签">
                    {(selectedGoal.tags || []).map((tag) => <Tag key={tag}>{tag}</Tag>)}
                  </Descriptions.Item>
                  <Descriptions.Item label="创建时间">
                    {new Date(selectedGoal.created_at).toLocaleString()}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              {selectedGoal.rationale && (
                <Card size="small" title="Rationale (LLM)">
                  <Text>{selectedGoal.rationale}</Text>
                </Card>
              )}

              <Card size="small" title="关联 ChangeProposal">
                {goalProposals.length === 0 ? (
                  <Empty description="暂无提案" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <List
                    size="small"
                    dataSource={goalProposals}
                    renderItem={(p) => (
                      <List.Item>
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Space>
                            <FileTextOutlined />
                            <Text strong>{p.title}</Text>
                            <Tag color="blue">{p.status}</Tag>
                          </Space>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            by {p.proposed_by} · {new Date(p.created_at).toLocaleString()}
                          </Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>

              <Card size="small" title={
                <Space>
                  <ApartmentOutlined /> Lineage（血缘）
                </Space>
              }>
                {lineage ? (
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {lineage.ancestors.length > 0 && (
                      <div>
                        <Text type="secondary">祖先：</Text>
                        <Space wrap>
                          {lineage.ancestors.map((g) => (
                            <Tag key={g.id} color="blue">{g.title}</Tag>
                          ))}
                        </Space>
                      </div>
                    )}
                    {lineage.children.length > 0 && (
                      <div>
                        <Text type="secondary">子：</Text>
                        <Space wrap>
                          {lineage.children.map((g) => (
                            <Tag key={g.id} color="green">{g.title}</Tag>
                          ))}
                        </Space>
                      </div>
                    )}
                    {lineage.proposals.length > 0 && (
                      <div>
                        <Text type="secondary">提案：</Text>
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
                      <Text type="secondary">无血缘关联</Text>
                    )}
                  </Space>
                ) : (
                  <Empty description="暂无血缘" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Space>
          </Spin>
        )}
      </Drawer>

      <Modal
        title="New Goal"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Form<CreateFormValues> form={createForm} layout="vertical">
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="目标标题" />
          </Form.Item>
          <Form.Item
            name="business_objective"
            label="业务目标"
            rules={[{ required: true, message: '请输入业务目标' }]}
          >
            <TextArea rows={2} placeholder="业务层面要达成的结果" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="可选" />
          </Form.Item>
          <Form.Item name="parent_goal_id" label="父 Goal ID（可选）">
            <Input placeholder="可选的父 Goal ID" />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="tag1, tag2" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default GoalKanban;
