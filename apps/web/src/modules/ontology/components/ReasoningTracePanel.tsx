/**
 * ReasoningTracePanel —— 确定性推理路径解释（ADR-075 · Datalog）
 *
 * 契约（后端 `odap/biz/core/ontology/reasoning/api/routes.py`）：
 *   POST /api/reasoning/deduce?goal=&ontology_id=&workspace_id=[&entity_type_ids=&bindings=]
 *   → `HybridOutcome.to_dict()`：source / rows / confidence / explanation /
 *     truncated / fallback_reason（+ rule_trace / metrics）
 *
 * 挂载点：本体设计器「推理追踪」页签 —— 规则就是在设计器里编的，编完即可就地验证命中路径。
 *
 * 修复记录：
 *   - 全文中文硬编码、零 i18n → 改为中文即键；
 *   - `Alert message`（AntD 6 已弃用）→ `title`；
 *   - `rows` 可能是元组/对象，渲染前统一转字符串，避免 object 直接进 JSX；
 *   - `rule_trace` 缺省时给出解释性空态，而不是让人误以为「没命中」。
 */
import { useCallback, useState } from 'react';
import {
  Card, Input, Button, Space, Tag, Empty, Spin, Alert,
  Descriptions, Typography, Collapse,
} from 'antd';
import {
  ExperimentOutlined, PlayCircleOutlined, BranchesOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface DeduceOutcome {
  source: 'deterministic' | 'llm_hybrid' | 'error';
  rows: unknown[][];
  confidence: number;
  explanation?: string;
  truncated: boolean;
  fallback_reason: string;
  metrics?: Record<string, unknown>;
}

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

const SOURCE_META: Record<string, { color: string; label: string }> = {
  deterministic: { color: 'green', label: '确定性推理' },
  llm_hybrid: { color: 'blue', label: 'LLM 降级' },
  error: { color: 'red', label: '推理错误' },
};

function cellText(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function ReasoningTracePanel({
  ontologyId = '',
  workspaceId = 'default',
}: ReasoningTracePanelProps) {
  const { t } = useI18n('ontology');
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [outcome, setOutcome] = useState<DeduceOutcome | null>(null);
  const [traces, setTraces] = useState<RuleTrace[]>([]);
  const [error, setError] = useState('');

  const runDeduce = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError('');
    setOutcome(null);
    setTraces([]);
    try {
      const params = new URLSearchParams({
        goal: goal.trim(),
        ontology_id: ontologyId,
        workspace_id: workspaceId,
      });
      const result = await apiClient.post<DeduceOutcome & { rule_trace?: RuleTrace[] }>(
        `/api/reasoning/deduce?${params.toString()}`,
      );
      setOutcome(result);
      setTraces(result.rule_trace ?? []);
    } catch (e) {
      // 失败原因原样暴露：推理失败可能是规则语法错、图库超时或 ontology_id 缺失，
      // 统一成「推理失败」会让人无从排查。
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [goal, ontologyId, workspaceId]);

  const sourceMeta = outcome ? SOURCE_META[outcome.source] : null;

  return (
    <Card
      title={
        <Space>
          <ExperimentOutlined />
          {t('确定性推理路径解释')}
        </Space>
      }
      extra={<Tag color="purple">ADR-075 · Datalog</Tag>}
    >
      <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
        <Input
          aria-label={t('推理目标')}
          placeholder={t('推理目标，如 ancestor("a", X)')}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onPressEnter={() => void runDeduce()}
          prefix={<BranchesOutlined />}
        />
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={loading}
          disabled={!goal.trim() || !ontologyId}
          onClick={() => void runDeduce()}
        >
          {t('推理')}
        </Button>
      </Space.Compact>

      {!ontologyId && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          title={t('请先选择本体，推理需要 ontology_id')}
        />
      )}
      {error && <Alert type="error" showIcon title={t('推理请求失败')} description={error} style={{ marginBottom: 16 }} />}

      {outcome && (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t('推理来源')}>
              {sourceMeta && <Tag color={sourceMeta.color}>{t(sourceMeta.label)}</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label={t('置信度')}>
              <Text strong>{(outcome.confidence * 100).toFixed(1)}%</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('结果数')}>
              {outcome.rows.length}
              {outcome.truncated && <Tag color="orange" style={{ marginLeft: 8 }}>{t('已截断')}</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label={t('降级原因')}>
              <Text type="secondary">{outcome.fallback_reason || '—'}</Text>
            </Descriptions.Item>
          </Descriptions>

          {outcome.rows.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>{t('推理结果：')}</Text>
              {outcome.rows.slice(0, 50).map((row, idx) => (
                <Tag key={idx} color="blue" style={{ margin: '4px 4px 0 0' }}>
                  {row.map(cellText).join(', ')}
                </Tag>
              ))}
              {outcome.rows.length > 50 && (
                <Text type="secondary">{t('（仅显示前 50 条）')}</Text>
              )}
            </div>
          )}

          {traces.length > 0 ? (
            <Collapse
              size="small"
              items={traces.map((trace, idx) => ({
                key: idx,
                label: (
                  <Space wrap>
                    <Tag color="geekblue">{trace.rule_id || t('规则 {{n}}', { n: idx + 1 })}</Tag>
                    <Text>{trace.rule_text}</Text>
                    <Text type="secondary">
                      {t('{{rows}} 行 · {{ms}}ms', { rows: trace.matched_rows, ms: trace.elapsed_ms.toFixed(1) })}
                    </Text>
                  </Space>
                ),
                children: (
                  <Descriptions column={1} size="small" bordered>
                    <Descriptions.Item label={t('目标')}>{trace.goal}</Descriptions.Item>
                    <Descriptions.Item label={t('命中行数')}>{trace.matched_rows}</Descriptions.Item>
                    <Descriptions.Item label={t('耗时')}>{trace.elapsed_ms.toFixed(2)} ms</Descriptions.Item>
                    <Descriptions.Item label={t('触发时间')}>{trace.fired_at}</Descriptions.Item>
                    {Object.keys(trace.bindings || {}).length > 0 && (
                      <Descriptions.Item label={t('绑定')}>
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
              description={
                outcome.source === 'error'
                  ? t('推理引擎报错，未产生规则轨迹')
                  : t('本次推理未返回规则轨迹（rule_trace 缺省）')
              }
            />
          )}
        </>
      )}

      {!outcome && !loading && !error && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t('输入推理目标并点击「推理」，查看 Datalog 确定性推理路径')}
        />
      )}
      {loading && <Spin style={{ display: 'block', marginTop: 16 }} />}
    </Card>
  );
}

export default ReasoningTracePanel;
