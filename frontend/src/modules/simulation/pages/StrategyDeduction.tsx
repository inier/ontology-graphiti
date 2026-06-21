import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Button, Modal, Form, Input, Select, Tag,
  Descriptions, Statistic, Progress, Tabs, Space, message, Popconfirm,
  Empty, Tooltip, Row, Col, Badge, Divider, Alert, Spin,
} from 'antd';
import {
  PlusOutlined, ThunderboltOutlined, PlayCircleOutlined,
  CompressOutlined, DeleteOutlined, EditOutlined, ReloadOutlined,
  CheckCircleOutlined, WarningOutlined,
  ExperimentOutlined, SafetyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import { AdvancedTable } from '@/modules/shared';

interface ApiResponse {
  [key: string]: unknown;
}

interface SimulationCondition {
  condition_id: string;
  name: string;
  condition_type: string;
  description: string;
  source_rule_id: string | null;
  source_constraint_id: string | null;
  expression: string | Record<string, unknown>;
  parameters: Record<string, unknown>;
  value: unknown;
  min_value: number | null;
  max_value: number | null;
  allowed_values: unknown[];
  is_active: boolean;
}

interface ChainStep {
  step_id: string;
  step_order: number;
  action_type_id: string;
  target_object_id: string;
  target_object_type: string;
  parameters: Record<string, unknown>;
  conditions: SimulationCondition[];
  description: string;
}

interface ExecutionChain {
  chain_id: string;
  name: string;
  description: string;
  steps: ChainStep[];
  conditions: SimulationCondition[];
  status: string;
  tags: string[];
}

interface MetricImpact {
  metric_name: string;
  before: unknown;
  after: unknown;
  delta: number | null;
  unit: string;
  confidence: number;
}

interface RuleViolation {
  rule_id: string;
  rule_type: string;
  description: string;
  severity: string;
  violated_condition: string;
}

interface ChainResult {
  chain_id: string;
  status: string;
  metric_impacts: MetricImpact[];
  risk_level: string;
  risk_score: number;
  rule_violations: RuleViolation[];
  recommendation: string;
  confidence: number;
  projected_state: Record<string, unknown>;
}

interface DeductionScenario {
  scenario_id: string;
  name: string;
  description: string;
  target_object_id: string;
  target_object_type: string;
  baseline_metrics: Record<string, unknown>;
  available_conditions: SimulationCondition[];
  chains: ExecutionChain[];
  results: ChainResult[];
  status: string;
  best_chain_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface ScenarioListItem {
  scenario_id: string;
  name: string;
  description: string;
  target_object_id: string;
  target_object_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const ACTION_TYPES = [
  { value: 'adjust_parameter', label: '调整参数' },
  { value: 'apply_policy', label: '应用策略' },
  { value: 'trigger_event', label: '触发事件' },
  { value: 'modify_relation', label: '修改关系' },
  { value: 'add_constraint', label: '添加约束' },
  { value: 'remove_constraint', label: '移除约束' },
];

const OBJECT_TYPES = [
  { value: 'entity', label: '实体' },
  { value: 'relation', label: '关系' },
  { value: 'attribute', label: '属性' },
  { value: 'policy', label: '策略' },
  { value: 'event', label: '事件' },
];

const CONDITION_TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  rule_based: { color: 'blue', label: '规则条件' },
  constraint_based: { color: 'orange', label: '约束条件' },
  custom: { color: 'green', label: '自定义条件' },
};

const CHAIN_STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  simulating: 'processing',
  completed: 'green',
  failed: 'red',
};

const SCENARIO_STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  configuring: 'blue',
  running: 'processing',
  completed: 'green',
  failed: 'red',
};

const RISK_LEVEL_CONFIG: Record<string, { color: string; percent: number }> = {
  low: { color: '#52c41a', percent: 30 },
  medium: { color: '#faad14', percent: 60 },
  high: { color: '#ff4d4f', percent: 85 },
  critical: { color: '#cf1322', percent: 100 },
};

const StrategyDeduction: React.FC = () => {
  const [scenarioList, setScenarioList] = useState<ScenarioListItem[]>([]);
  const [scenarioTotal, setScenarioTotal] = useState(0);
  const [scenarioPage, setScenarioPage] = useState(1);
  const [scenarioPageSize, setScenarioPageSize] = useState(20);
  const [selectedScenario, setSelectedScenario] = useState<DeductionScenario | null>(null);
  const [loading, setLoading] = useState(false);
  const [scenarioModalOpen, setScenarioModalOpen] = useState(false);
  const [chainModalOpen, setChainModalOpen] = useState(false);
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [editingChain, setEditingChain] = useState<ExecutionChain | null>(null);
  const [editingConditionValues, setEditingConditionValues] = useState<Record<string, unknown>>({});
  const [chainSteps, setChainSteps] = useState<ChainStep[]>([]);
  const [chainConditions, setChainConditions] = useState<SimulationCondition[]>([]);
  const [activeTab, setActiveTab] = useState('config');
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null);

  const [scenarioForm] = Form.useForm();
  const [chainForm] = Form.useForm();

  const fetchScenarioList = useCallback(async (page = scenarioPage, pageSize = scenarioPageSize) => {
    try {
      const data = await fetchJson<ApiResponse>(
        `${API_BASE}/api/simulation/deduction/scenarios?page=${page}&page_size=${pageSize}`
      );
      setScenarioList((data.scenarios || []) as ScenarioListItem[]);
      setScenarioTotal((data.total as number) || 0);
      setScenarioPage((data.page as number) || page);
      setScenarioPageSize((data.page_size as number) || pageSize);
    } catch (error) {
      console.error('获取推演场景列表失败', error);
      setScenarioList([]);
    }
  }, [scenarioPage, scenarioPageSize]);

  const fetchScenarioDetail = useCallback(async (scenarioId: string): Promise<DeductionScenario | null> => {
    try {
      const data = await fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}`);
      return data as unknown as DeductionScenario;
    } catch (error) {
      console.error('获取场景详情失败', error);
      return null;
    }
  }, []);

  useEffect(() => {
    fetchScenarioList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelectScenario = async (item: ScenarioListItem) => {
    setLoading(true);
    try {
      const detail = await fetchScenarioDetail(item.scenario_id);
      if (detail) {
        setSelectedScenario(detail);
        const editMap: Record<string, unknown> = {};
        detail.available_conditions.forEach(c => {
          editMap[c.condition_id] = c.value;
        });
        detail.chains.forEach(chain => {
          chain.conditions.forEach(c => {
            editMap[c.condition_id] = c.value;
          });
        });
        setEditingConditionValues(editMap);
        setActiveTab('config');
      }
    } finally {
      setLoading(false);
    }
  };

  const refreshSelectedScenario = async () => {
    if (!selectedScenario) return;
    const detail = await fetchScenarioDetail(selectedScenario.scenario_id);
    if (detail) {
      setSelectedScenario(detail);
      const editMap: Record<string, unknown> = {};
      detail.available_conditions.forEach(c => {
        editMap[c.condition_id] = c.value;
      });
      detail.chains.forEach(chain => {
        chain.conditions.forEach(c => {
          editMap[c.condition_id] = c.value;
        });
      });
      setEditingConditionValues(editMap);
    }
  };

  const handleCreateScenario = async (values: Record<string, unknown>) => {
    try {
      setLoading(true);
      await fetchJson(`${API_BASE}/api/simulation/deduction/scenarios`, {
        method: 'POST',
        body: JSON.stringify({
          name: values.name,
          description: values.description,
          target_object_id: values.target_object_id,
          target_object_type: values.target_object_type,
        }),
      });
      message.success('场景创建成功');
      setScenarioModalOpen(false);
      scenarioForm.resetFields();
      fetchScenarioList();
    } catch (error) {
      message.error(`场景创建失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteScenario = async (scenarioId: string) => {
    try {
      await fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}`, {
        method: 'DELETE',
      });
      message.success('场景已删除');
      if (selectedScenario?.scenario_id === scenarioId) {
        setSelectedScenario(null);
      }
      fetchScenarioList();
    } catch (error) {
      message.error(`删除失败: ${error}`);
    }
  };

  const handleLoadOntologyConditions = async () => {
    if (!selectedScenario) return;
    try {
      setLoading(true);
      const data = await fetchJson<ApiResponse>(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/conditions`,
        { method: 'POST' }
      );
      message.success(`已加载 ${data.total || 0} 条本体条件`);
      await refreshSelectedScenario();
    } catch (error) {
      message.error(`加载条件失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateConditionValue = async (conditionId: string, value: unknown) => {
    if (!selectedScenario) return;
    try {
      await fetchJson(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/conditions/${conditionId}`,
        {
          method: 'PUT',
          body: JSON.stringify({ value }),
        }
      );
      message.success('条件值已更新');
      await refreshSelectedScenario();
    } catch (error) {
      message.error(`更新失败: ${error}`);
    }
  };

  const handleAddChain = () => {
    setEditingChain(null);
    setChainSteps([]);
    setChainConditions([]);
    chainForm.resetFields();
    setChainModalOpen(true);
  };

  const handleEditChain = (chain: ExecutionChain) => {
    setEditingChain(chain);
    setChainSteps([...chain.steps]);
    setChainConditions([...chain.conditions]);
    chainForm.setFieldsValue({
      name: chain.name,
      description: chain.description,
    });
    setChainModalOpen(true);
  };

  const handleSaveChain = async (values: Record<string, unknown>) => {
    if (!selectedScenario) return;
    try {
      setLoading(true);
      const payload = {
        name: values.name,
        description: values.description,
        steps: chainSteps.map((s, idx) => ({
          step_id: s.step_id,
          step_order: idx,
          action_type_id: s.action_type_id,
          target_object_id: s.target_object_id,
          target_object_type: s.target_object_type,
          parameters: s.parameters,
          conditions: s.conditions,
          description: s.description,
        })),
        conditions: chainConditions.map(c => ({
          condition_id: c.condition_id,
          name: c.name,
          condition_type: c.condition_type,
          description: c.description,
          value: c.value,
          is_active: c.is_active,
          parameters: c.parameters,
          expression: c.expression,
        })),
      };
      if (editingChain) {
        await fetchJson(
          `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/chains/${editingChain.chain_id}`,
          {
            method: 'PUT',
            body: JSON.stringify(payload),
          }
        );
        message.success('执行链已更新');
      } else {
        await fetchJson(
          `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/chains`,
          {
            method: 'POST',
            body: JSON.stringify(payload),
          }
        );
        message.success('执行链已创建');
      }
      setChainModalOpen(false);
      chainForm.resetFields();
      setChainSteps([]);
      setChainConditions([]);
      setEditingChain(null);
      await refreshSelectedScenario();
    } catch (error) {
      message.error(`保存失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChain = async (chainId: string) => {
    if (!selectedScenario) return;
    try {
      await fetchJson(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/chains/${chainId}`,
        { method: 'DELETE' }
      );
      message.success('执行链已删除');
      await refreshSelectedScenario();
    } catch (error) {
      message.error(`删除失败: ${error}`);
    }
  };

  const handleAddStep = () => {
    const newStep: ChainStep = {
      step_id: `step_${Date.now()}`,
      step_order: chainSteps.length,
      action_type_id: '',
      target_object_id: '',
      target_object_type: '',
      parameters: {},
      conditions: [],
      description: '',
    };
    setChainSteps(prev => [...prev, newStep]);
  };

  const handleRemoveStep = (stepId: string) => {
    setChainSteps(prev => prev.filter(s => s.step_id !== stepId));
  };

  const handleStepChange = (stepId: string, field: keyof ChainStep, value: unknown) => {
    setChainSteps(prev =>
      prev.map(s => (s.step_id === stepId ? { ...s, [field]: value } : s))
    );
  };

  const handleSimulateChain = async (chainId: string) => {
    if (!selectedScenario) return;
    try {
      setLoading(true);
      await fetchJson(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/chains/${chainId}/simulate`,
        { method: 'POST' }
      );
      message.success('推演完成');
      await refreshSelectedScenario();
      setActiveTab('results');
    } catch (error) {
      message.error(`推演失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulateAll = async () => {
    if (!selectedScenario) return;
    try {
      setLoading(true);
      await fetchJson(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/simulate-all`,
        { method: 'POST' }
      );
      message.success('全部推演完成');
      await refreshSelectedScenario();
      setActiveTab('results');
    } catch (error) {
      message.error(`推演失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!selectedScenario) return;
    const chainIds = selectedScenario.chains.map(c => c.chain_id);
    if (chainIds.length < 2) {
      message.warning('至少需要 2 条执行链才能对比');
      return;
    }
    try {
      setLoading(true);
      const data = await fetchJson<ApiResponse>(
        `${API_BASE}/api/simulation/deduction/scenarios/${selectedScenario.scenario_id}/compare`,
        {
          method: 'POST',
          body: JSON.stringify({ chain_ids: chainIds }),
        }
      );
      setCompareResult(data);
      setCompareModalOpen(true);
    } catch (error) {
      message.error(`对比失败: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (level: string) => RISK_LEVEL_CONFIG[level]?.color || '#d9d9d9';

  const getChainName = (chainId: string) => {
    if (!selectedScenario) return chainId;
    const chain = selectedScenario.chains.find(c => c.chain_id === chainId);
    return chain?.name || chainId;
  };

  const scenarioColumns: ColumnsType<ScenarioListItem> = [
    {
      title: '场景名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (name: string, record: ScenarioListItem) => (
        <Button
          type={selectedScenario?.scenario_id === record.scenario_id ? 'primary' : 'link'}
          size="small"
          onClick={() => handleSelectScenario(record)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '目标类型',
      dataIndex: 'target_object_type',
      key: 'target_object_type',
      width: 90,
      render: (type: string) => <Tag>{type || '-'}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={SCENARIO_STATUS_COLORS[status] || 'default'}>{status}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_: unknown, record: ScenarioListItem) => (
        <Popconfirm
          title="确认删除此场景？"
          onConfirm={() => handleDeleteScenario(record.scenario_id)}
          okText="删除"
          cancelText="取消"
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const conditionColumns: ColumnsType<SimulationCondition> = [
    {
      title: '条件名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'condition_type',
      key: 'condition_type',
      width: 100,
      render: (type: string) => {
        const cfg = CONDITION_TYPE_CONFIG[type];
        return cfg ? <Tag color={cfg.color}>{cfg.label}</Tag> : <Tag>{type}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '当前值',
      dataIndex: 'value',
      key: 'value',
      width: 180,
      render: (value: unknown, record: SimulationCondition) => {
        const editingValue = editingConditionValues[record.condition_id];
        const displayValue = editingValue !== undefined ? editingValue : value;
        const strValue = displayValue != null ? String(displayValue) : '';
        return (
          <Input
            size="small"
            value={strValue}
            onChange={e =>
              setEditingConditionValues(prev => ({ ...prev, [record.condition_id]: e.target.value }))
            }
            onPressEnter={() => {
              const newVal = editingConditionValues[record.condition_id];
              if (newVal !== value) {
                handleUpdateConditionValue(record.condition_id, newVal);
              }
            }}
            onBlur={() => {
              const newVal = editingConditionValues[record.condition_id];
              if (newVal !== value) {
                handleUpdateConditionValue(record.condition_id, newVal);
              }
            }}
            suffix={
              record.min_value != null || record.max_value != null
                ? <span style={{ color: '#999', fontSize: 11 }}>
                    {record.min_value != null && record.max_value != null
                      ? `${record.min_value}~${record.max_value}`
                      : record.min_value != null
                        ? `≥${record.min_value}`
                        : `≤${record.max_value}`}
                  </span>
                : undefined
            }
          />
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 60,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_: unknown, record: SimulationCondition) => (
        <Tooltip title="重置为原始值">
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => {
              setEditingConditionValues(prev => ({ ...prev, [record.condition_id]: record.value }));
            }}
          />
        </Tooltip>
      ),
    },
  ];

  const chainColumns: ColumnsType<ExecutionChain> = [
    {
      title: '链路名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
      ellipsis: true,
    },
    {
      title: '步骤数',
      key: 'step_count',
      width: 70,
      render: (_: unknown, record: ExecutionChain) => (
        <Badge count={record.steps.length} showZero color="blue" />
      ),
    },
    {
      title: '条件数',
      key: 'condition_count',
      width: 70,
      render: (_: unknown, record: ExecutionChain) => (
        <Badge count={record.conditions.length} showZero color="orange" />
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={CHAIN_STATUS_COLORS[status] || 'default'}>{status}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: ExecutionChain) => (
        <Space size="small">
          <Tooltip title="推演">
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={loading}
              onClick={() => handleSimulateChain(record.chain_id)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEditChain(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此执行链？"
            onConfirm={() => handleDeleteChain(record.chain_id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const resultColumns: ColumnsType<ChainResult> = [
    {
      title: '链路名称',
      dataIndex: 'chain_id',
      key: 'chain_id',
      width: 140,
      ellipsis: true,
      render: (chainId: string) => (
        <Space>
          {selectedScenario?.best_chain_id === chainId && (
            <Tag color="gold" icon={<CheckCircleOutlined />}>最优</Tag>
          )}
          {getChainName(chainId)}
        </Space>
      ),
    },
    {
      title: '风险评分',
      dataIndex: 'risk_score',
      key: 'risk_score',
      width: 120,
      sorter: (a: ChainResult, b: ChainResult) => a.risk_score - b.risk_score,
      render: (score: number) => (
        <Progress
          percent={Math.round(score)}
          size="small"
          strokeColor={score < 30 ? '#52c41a' : score < 60 ? '#faad14' : '#ff4d4f'}
          format={p => `${p}`}
        />
      ),
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 100,
      render: (level: string) => (
        <Tag color={getRiskColor(level)}>{level.toUpperCase()}</Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (confidence: number) => (
        <Statistic
          value={confidence * 100}
          precision={1}
          suffix="%"
          styles={{ content: { fontSize: 14 } }}
        />
      ),
    },
    {
      title: '规则违反',
      key: 'violations',
      width: 80,
      render: (_: unknown, record: ChainResult) => (
        <Badge
          count={record.rule_violations.length}
          showZero
          style={{ backgroundColor: record.rule_violations.length > 0 ? '#ff4d4f' : '#52c41a' }}
        />
      ),
    },
    {
      title: '指标变化',
      key: 'metrics',
      render: (_: unknown, record: ChainResult) => (
        <Space orientation="vertical" size={2}>
          {record.metric_impacts.slice(0, 3).map((m, idx) => (
            <span key={idx} style={{ fontSize: 12 }}>
              {m.metric_name}:{' '}
              <span style={{ color: (m.delta ?? 0) >= 0 ? '#52c41a' : '#ff4d4f' }}>
                {(m.delta ?? 0) >= 0 ? '+' : ''}{(m.delta ?? 0).toFixed(3)}
              </span>
              {m.unit && <span style={{ color: '#999' }}> {m.unit}</span>}
            </span>
          ))}
          {record.metric_impacts.length > 3 && (
            <span style={{ fontSize: 12, color: '#999' }}>+{record.metric_impacts.length - 3} 更多</span>
          )}
        </Space>
      ),
    },
    {
      title: '推荐',
      dataIndex: 'recommendation',
      key: 'recommendation',
      ellipsis: true,
      width: 200,
      render: (text: string) => (
        <Tooltip title={text}>
          <span style={{ fontSize: 12 }}>{text}</span>
        </Tooltip>
      ),
    },
  ];

  const renderScenarioList = () => (
    <Card
      title="推演场景"
      size="small"
      extra={
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => setScenarioModalOpen(true)}
        >
          新建场景
        </Button>
      }
    >
      <AdvancedTable
        dataSource={scenarioList}
        columns={scenarioColumns}
        rowKey="scenario_id"
        size="small"
        pagination={{
          current: scenarioPage,
          pageSize: scenarioPageSize,
          total: scenarioTotal,
          size: 'small',
          onChange: (page, pageSize) => fetchScenarioList(page, pageSize),
          showTotal: t => `共 ${t} 条`,
        }}
        locale={{ emptyText: <Empty description="暂无推演场景" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
      />
    </Card>
  );

  const renderScenarioConfig = () => {
    if (!selectedScenario) {
      return (
        <Card>
          <Empty description="请先选择一个推演场景" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      );
    }

    const allConditions = selectedScenario.available_conditions;

    return (
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Card title="场景信息" size="small">
          <Descriptions size="small" column={2} variant="bordered">
            <Descriptions.Item label="场景名称">{selectedScenario.name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={SCENARIO_STATUS_COLORS[selectedScenario.status] || 'default'}>
                {selectedScenario.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="目标对象">{selectedScenario.target_object_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="目标类型">
              <Tag>{selectedScenario.target_object_type || '-'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>
              {selectedScenario.description || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {selectedScenario.created_at || '-'}
            </Descriptions.Item>
          </Descriptions>
          {Object.keys(selectedScenario.baseline_metrics).length > 0 && (
            <>
              <Divider titlePlacement="left" style={{ fontSize: 13, margin: '12px 0 8px' }}>基线指标</Divider>
              <Row gutter={[16, 8]}>
                {Object.entries(selectedScenario.baseline_metrics)
                  .filter(([k]) => k !== 'target_id' && k !== 'target_type')
                  .map(([key, val]) => (
                    <Col span={6} key={key}>
                      <Statistic title={key} value={val as number} styles={{ content: { fontSize: 14 } }} />
                    </Col>
                  ))}
              </Row>
            </>
          )}
        </Card>

        <Card
          title="本体条件"
          size="small"
          extra={
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={handleLoadOntologyConditions}
              loading={loading}
            >
              加载本体条件
            </Button>
          }
        >
          <AdvancedTable
            dataSource={allConditions}
            columns={conditionColumns}
            rowKey="condition_id"
            size="small"
            pagination={allConditions.length > 10 ? { pageSize: 10, size: 'small' } : false}
            locale={{ emptyText: <Empty description={'点击「加载本体条件」从 OMS 获取'} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        </Card>

        <Card
          title="执行链路"
          size="small"
          extra={
            <Space size="small">
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={handleAddChain}
              >
                添加执行链
              </Button>
              <Button
                size="small"
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleSimulateAll}
                loading={loading}
                disabled={selectedScenario.chains.length === 0}
              >
                全部推演
              </Button>
            </Space>
          }
        >
          <AdvancedTable
            dataSource={selectedScenario.chains}
            columns={chainColumns}
            rowKey="chain_id"
            size="small"
            pagination={false}
            locale={{ emptyText: <Empty description={'暂无执行链，点击「添加执行链」创建'} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        </Card>
      </Space>
    );
  };

  const renderDeductionResults = () => {
    if (!selectedScenario) {
      return (
        <Card>
          <Empty description="请先选择场景并执行推演" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      );
    }

    const results = selectedScenario.results;

    if (results.length === 0) {
      return (
        <Card>
          <Empty description="暂无推演结果，请先执行推演" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      );
    }

    const bestChainId = selectedScenario.best_chain_id;
    const optimalResult = bestChainId
      ? results.find(r => r.chain_id === bestChainId)
      : results.reduce(
          (best, r) => (r.risk_score < best.risk_score ? r : best),
          results[0]
        );

    return (
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Card title="最优链路推荐" size="small">
          {optimalResult && (
            <>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="推荐链路"
                    value={getChainName(optimalResult.chain_id)}
                    styles={{ content: { fontSize: 16 } }}
                    prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="风险评分"
                    value={optimalResult.risk_score}
                    precision={1}
                    suffix="/ 100"
                    styles={{ content: { color: getRiskColor(optimalResult.risk_level) } }}
                  />
                </Col>
                <Col span={8}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ marginBottom: 4, color: '#999', fontSize: 14 }}>风险等级</div>
                    <Progress
                      type="circle"
                      percent={Math.round(optimalResult.risk_score)}
                      size={60}
                      strokeColor={getRiskColor(optimalResult.risk_level)}
                      format={() => (
                        <span style={{ fontSize: 14 }}>{optimalResult.risk_level.toUpperCase()}</span>
                      )}
                    />
                  </div>
                </Col>
              </Row>
              {optimalResult.recommendation && (
                <Alert
                  style={{ marginTop: 12 }}
                  type={optimalResult.risk_level === 'low' ? 'success' : optimalResult.risk_level === 'critical' ? 'error' : 'warning'}
                  showIcon
                  icon={<WarningOutlined />}
                  message="推演建议"
                  description={optimalResult.recommendation}
                />
              )}
              {optimalResult.rule_violations.length > 0 && (
                <Alert
                  style={{ marginTop: 8 }}
                  type="warning"
                  showIcon
                  icon={<WarningOutlined />}
                  message={`最优链路仍有 ${optimalResult.rule_violations.length} 条规则违反`}
                  description={
                    <ul style={{ margin: '4px 0 0 0', paddingLeft: 20 }}>
                      {optimalResult.rule_violations.slice(0, 3).map((v, idx) => (
                        <li key={idx}>
                          <Tag color={v.severity === 'critical' ? 'red' : v.severity === 'high' ? 'orange' : 'blue'}>
                            {v.severity}
                          </Tag>
                          {v.rule_type}: {v.description}
                        </li>
                      ))}
                      {optimalResult.rule_violations.length > 3 && (
                        <li style={{ color: '#999' }}>...还有 {optimalResult.rule_violations.length - 3} 条</li>
                      )}
                    </ul>
                  }
                />
              )}
            </>
          )}
        </Card>

        <Card
          title="推演结果对比"
          size="small"
          extra={
            <Button
              size="small"
              icon={<CompressOutlined />}
              onClick={handleCompare}
              disabled={results.length < 2}
            >
              详细对比
            </Button>
          }
        >
          <AdvancedTable
            dataSource={results}
            columns={resultColumns}
            rowKey="chain_id"
            size="small"
            pagination={false}
          />
        </Card>

        <Card title="风险评估总览" size="small">
          <Row gutter={[16, 16]}>
            {results.map(result => (
              <Col span={Math.max(6, 24 / results.length)} key={result.chain_id}>
                <Card size="small" type="inner" title={getChainName(result.chain_id)}>
                  <Space orientation="vertical" style={{ width: '100%' }}>
                    <Progress
                      percent={Math.round(result.risk_score)}
                      strokeColor={getRiskColor(result.risk_level)}
                      format={p => `风险 ${p}`}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Statistic
                        title="置信度"
                        value={result.confidence * 100}
                        precision={1}
                        suffix="%"
                        styles={{ content: { fontSize: 14 } }}
                      />
                      <Statistic
                        title="违反"
                        value={result.rule_violations.length}
                        styles={{ content: { fontSize: 14, color: result.rule_violations.length > 0 ? '#ff4d4f' : '#52c41a' } }}
                        prefix={result.rule_violations.length > 0 ? <WarningOutlined /> : <SafetyOutlined />}
                      />
                    </div>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      </Space>
    );
  };

  const renderCompareModal = () => {
    if (!compareResult) return null;

    const comparison = (compareResult.comparison || []) as Array<Record<string, unknown>>;
    const compareResults = (compareResult.results || []) as ChainResult[];
    const bestChainId = compareResult.best_chain_id as string | null;

    const compareData = comparison.map(item => {
      const row: Record<string, unknown> = { metric_name: item.metric_name };
      const values = item.values as Record<string, number>;
      compareResults.forEach(r => {
        const delta = values?.[r.chain_id];
        row[`${r.chain_id}_delta`] = delta;
      });
      return row;
    });

    const compareColumns: ColumnsType<Record<string, unknown>> = [
      {
        title: '指标',
        dataIndex: 'metric_name',
        key: 'metric_name',
        fixed: 'left',
        width: 120,
      },
      ...compareResults.map(r => ({
        title: getChainName(r.chain_id),
        children: [
          {
            title: '变化量',
            dataIndex: `${r.chain_id}_delta`,
            key: `${r.chain_id}_delta`,
            width: 100,
            render: (v: unknown) => {
              if (v == null) return '-';
              const num = typeof v === 'number' ? v : parseFloat(String(v));
              return (
                <span style={{ color: num >= 0 ? '#52c41a' : '#ff4d4f' }}>
                  {num >= 0 ? '+' : ''}{num.toFixed(3)}
                </span>
              );
            },
          },
        ],
      })),
    ];

    return (
      <Modal
        title="链路对比详情"
        open={compareModalOpen}
        onCancel={() => {
          setCompareModalOpen(false);
          setCompareResult(null);
        }}
        width={Math.min(1200, 400 + compareResults.length * 200)}
        footer={null}
      >
        <AdvancedTable
          dataSource={compareData}
          columns={compareColumns}
          rowKey="metric_name"
          size="small"
          scroll={{ x: 400 + compareResults.length * 200 }}
          pagination={false}
        />
        <Divider />
        <Card size="small" title="风险对比">
          <Row gutter={16}>
            {compareResults.map(r => (
              <Col span={Math.max(6, 24 / compareResults.length)} key={r.chain_id}>
                <Statistic
                  title={getChainName(r.chain_id)}
                  value={r.risk_score}
                  precision={1}
                  suffix={
                    <Tag color={getRiskColor(r.risk_level)} style={{ marginLeft: 8 }}>
                      {r.risk_level.toUpperCase()}
                    </Tag>
                  }
                  styles={{ content: { color: getRiskColor(r.risk_level) } }}
                />
                {bestChainId === r.chain_id && (
                  <Tag color="gold" style={{ marginTop: 4 }}>最优</Tag>
                )}
              </Col>
            ))}
          </Row>
        </Card>
      </Modal>
    );
  };

  const renderScenarioModal = () => (
    <Modal
      title="新建推演场景"
      open={scenarioModalOpen}
      onCancel={() => {
        setScenarioModalOpen(false);
        scenarioForm.resetFields();
      }}
      onOk={() => scenarioForm.submit()}
      confirmLoading={loading}
    >
      <Form form={scenarioForm} layout="vertical" onFinish={handleCreateScenario}>
        <Form.Item
          name="name"
          label="场景名称"
          rules={[{ required: true, message: '请输入场景名称' }]}
        >
          <Input placeholder="输入场景名称" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={3} placeholder="输入场景描述" />
        </Form.Item>
        <Form.Item
          name="target_object_id"
          label="目标对象 ID"
          rules={[{ required: true, message: '请输入目标对象 ID' }]}
        >
          <Input placeholder="输入目标对象 ID" />
        </Form.Item>
        <Form.Item
          name="target_object_type"
          label="目标对象类型"
          rules={[{ required: true, message: '请选择目标对象类型' }]}
        >
          <Select placeholder="选择目标对象类型" options={OBJECT_TYPES} />
        </Form.Item>
      </Form>
    </Modal>
  );

  const renderChainModal = () => (
    <Modal
      title={editingChain ? '编辑执行链' : '新建执行链'}
      open={chainModalOpen}
      onCancel={() => {
        setChainModalOpen(false);
        chainForm.resetFields();
        setChainSteps([]);
        setChainConditions([]);
        setEditingChain(null);
      }}
      onOk={() => chainForm.submit()}
      confirmLoading={loading}
      width={720}
    >
      <Form form={chainForm} layout="vertical" onFinish={handleSaveChain}>
        <Form.Item
          name="name"
          label="链路名称"
          rules={[{ required: true, message: '请输入链路名称' }]}
        >
          <Input placeholder="输入链路名称" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="输入链路描述" />
        </Form.Item>
      </Form>

      <Divider titlePlacement="left" style={{ fontSize: 14 }}>执行步骤</Divider>

      <Space orientation="vertical" style={{ width: '100%' }}>
        {chainSteps.map((step, idx) => (
          <Card key={step.step_id} size="small" type="inner" title={`步骤 ${idx + 1}`}>
            <Row gutter={8}>
              <Col span={7}>
                <Select
                  size="small"
                  value={step.action_type_id || undefined}
                  onChange={v => handleStepChange(step.step_id, 'action_type_id', v)}
                  options={ACTION_TYPES}
                  style={{ width: '100%' }}
                  placeholder="动作类型"
                />
              </Col>
              <Col span={7}>
                <Input
                  size="small"
                  value={step.target_object_id}
                  onChange={e => handleStepChange(step.step_id, 'target_object_id', e.target.value)}
                  placeholder="目标对象 ID"
                />
              </Col>
              <Col span={6}>
                <Select
                  size="small"
                  value={step.target_object_type || undefined}
                  onChange={v => handleStepChange(step.step_id, 'target_object_type', v)}
                  options={OBJECT_TYPES}
                  style={{ width: '100%' }}
                  placeholder="目标类型"
                />
              </Col>
              <Col span={4}>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemoveStep(step.step_id)}
                />
              </Col>
            </Row>
            <Input
              size="small"
              style={{ marginTop: 8 }}
              placeholder="步骤描述（可选）"
              value={step.description}
              onChange={e => handleStepChange(step.step_id, 'description', e.target.value)}
            />
            <Input
              size="small"
              style={{ marginTop: 4 }}
              placeholder="参数 (JSON 格式，可选)"
              value={Object.keys(step.parameters).length > 0 ? JSON.stringify(step.parameters) : ''}
              onChange={e => {
                try {
                  const parsed = e.target.value ? JSON.parse(e.target.value) : {};
                  handleStepChange(step.step_id, 'parameters', parsed);
                } catch {
                  // ignore parse errors during typing
                }
              }}
            />
          </Card>
        ))}
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={handleAddStep}
        >
          添加步骤
        </Button>
      </Space>
    </Modal>
  );

  return (
    <Spin spinning={loading} description="推演进行中...">
      <Row gutter={16}>
        <Col span={6}>
          {renderScenarioList()}
        </Col>
        <Col span={18}>
          {selectedScenario && (
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={[
                {
                  key: 'config',
                  label: (
                    <span>
                      <ExperimentOutlined />
                      场景配置
                    </span>
                  ),
                  children: renderScenarioConfig(),
                },
                {
                  key: 'results',
                  label: (
                    <span>
                      <SafetyOutlined />
                      推演结果
                      {selectedScenario.results.length > 0 && (
                        <Badge count={selectedScenario.results.length} size="small" style={{ marginLeft: 6 }} />
                      )}
                    </span>
                  ),
                  children: renderDeductionResults(),
                },
              ]}
            />
          )}
          {!selectedScenario && (
            <Card>
              <Empty
                description="请从左侧选择一个推演场景开始"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </Card>
          )}
        </Col>
      </Row>

      {renderScenarioModal()}
      {renderChainModal()}
      {renderCompareModal()}
    </Spin>
  );
};

export default StrategyDeduction;
