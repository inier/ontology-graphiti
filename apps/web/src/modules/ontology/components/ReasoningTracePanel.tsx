/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, Input, Button, Space, Steps, Tag, Empty, Spin, Alert,
  Descriptions, Typography, Collapse,
} from 'antd';
import {
  ExperimentOutlined, PlayCircleOutlined, BranchesOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';

const { Text } = Typography;

/** 确定性推理结果（后端 /api/reasoning/deduce 返回） */
interface DeduceOutcome {
  source: 'deterministic' | 'llm_hybrid' | 'error';
  rows: unknown[][];
  confidence: number;
  explanation?: string;
  truncated: boolean;
  fallback_reason: string;
  metrics?: Record<string, unknown>;
}

/** rule_trace 单条轨迹（后端 trace_builder 输出） */
interface RuleTrace {
  goal: string;
  rule_id: string;
  rule_text: string;
  matched_rows: number;
  elapsed_ms: number;
  truncated: boolean;
  fired_at: string;
  bindings: Record<string, unknown>;
}

export interface ReasoningTracePanelProps {
  ontologyId?: string;
  workspaceId?: string;
}

const SOURCE_TAG: Record<string, { color: string; label: string }> = {
  deterministic: { color: 'green', label: '确定性推理' },
  llm_hybrid: { color: 'blue', label: 'LLM 降级' },
  error: { color: 'red', label: '推理错误' },
};

export function ReasoningTracePanel({
  ontologyId = '',
  workspaceId = 'default',
}: ReasoningTracePanelProps) {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [outcome, setOutcome] = useState<DeduceOutcome | null>(null);
  const [traces, setTraces] = useState<RuleTrace[]>([]);
  const [error, setError] = useState('');

  const runDeduce = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        goal: goal.trim(),
        ontology_id: ontologyId,
        workspace_id: workspaceId,
      });
      const result = await apiClient.post(`/api/reasoning/deduce?${params.toString()}`) as any;
      setOutcome(result as DeduceOutcome);
      // 后端 deduce 返回 rule_trace 时在此映射（若未返回，按 fallback_reason 构造空轨迹）
      const rawTraces: RuleTrace[] = (result as any)?.rule_trace || [];
      setTraces(rawTraces);
    } catch (e: any) {
      setError(e?.message || '推理请求失败');
      setOutcome(null);
      setTraces([]);
    } finally {
      setLoading(false);
    }
  }, [goal, ontologyId, workspaceId]);

  const sourceTag = outcome ? SOURCE_TAG[outcome.source] : null;

  return (
    <Card
      title={
        <Space>
          <ExperimentOutlined />
          确定性推理路径解释
        </Space>
      }
      extra={<Tag color="purple">ADR-075 · Datalog</Tag>}
    >
      <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
        <Input
          placeholder='推理目标，如 ancestor("a", X)'
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onPressEnter={runDeduce}
          prefix={<BranchesOutlined />}
        />
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={loading}
          onClick={runDeduce}
        >
          推理
        </Button>
      </Space.Compact>

      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      {outcome && (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="推理来源">
              {sourceTag && <Tag color={sourceTag.color}>{sourceTag.label}</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              <Text strong>{(outcome.confidence * 100).toFixed(1)}%</Text>
            </Descriptions.Item>
            <Descriptions.Item label="结果数">
              {outcome.rows.length}
              {outcome.truncated && <Tag color="orange" style={{ marginLeft: 8 }}>已截断</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="降级原因">
              {outcome.fallback_reason ? (
                <Text type="secondary">{outcome.fallback_reason}</Text>
              ) : (
                <Text type="secondary">-</Text>
              )}
            </Descriptions.Item>
          </Descriptions>

          {outcome.rows.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>推理结果：</Text>
              {outcome.rows.slice(0, 50).map((row, idx) => (
                <Tag key={idx} color="blue" style={{ margin: '4px 4px 0 0' }}>
                  {row.map((v) => String(v)).join(', ')}
                </Tag>
              ))}
            </div>
          )}

          {traces.length > 0 ? (
            <Collapse
              size="small"
              items={traces.map((trace, idx) => ({
                key: idx,
                label: (
                  <Space>
                    <Tag color="geekblue">{trace.rule_id || `规则 ${idx + 1}`}</Tag>
                    <Text>{trace.rule_text}</Text>
                    <Text type="secondary">
                      {trace.matched_rows} 行 · {trace.elapsed_ms.toFixed(1)}ms
                    </Text>
                  </Space>
                ),
                children: (
                  <Descriptions column={1} size="small" bordered>
                    <Descriptions.Item label="目标">{trace.goal}</Descriptions.Item>
                    <Descriptions.Item label="命中行数">{trace.matched_rows}</Descriptions.Item>
                    <Descriptions.Item label="耗时">{trace.elapsed_ms.toFixed(2)} ms</Descriptions.Item>
                    <Descriptions.Item label="触发时间">{trace.fired_at}</Descriptions.Item>
                    {Object.keys(trace.bindings || {}).length > 0 && (
                      <Descriptions.Item label="绑定">
                        {JSON.stringify(trace.bindings)}
                      </Descriptions.Item>
                    )}
                  </Descriptions>
                ),
              }))}
            />
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={loading ? '推理中...' : '推理完成后此处展示命中的规则轨迹 (rule_trace)'}
            />
          )}
        </>
      )}

      {!outcome && !loading && !error && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="输入推理目标并点击「推理」，查看 Datalog 确定性推理路径"
        />
      )}
      {loading && <Spin style={{ display: 'block', marginTop: 16 }} />}
    </Card>
  );
}

export default ReasoningTracePanel;
