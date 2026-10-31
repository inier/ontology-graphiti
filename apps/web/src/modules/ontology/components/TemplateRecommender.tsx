/**
 * TemplateRecommender —— HE 抽取模板推荐（三级回退：本体生成 → 预设模板 → 联网生成）
 *
 * 真实契约（`odap/biz/core/ontology/extraction/api/routes.py`）：
 *   POST /api/extraction/templates/recommend
 *        body: { text, ontology_id }            ← 没有 top_k，后端不读
 *        resp: { status, templates: candidate[], assessment }
 *              assessment = { best_score, threshold, needs_custom, settled_used }
 *   POST /api/extraction/templates/generate-web-search
 *        body: { text, ontology_id }
 *        resp: { status, template }             ← template 可能为 null，带 message
 *
 * candidate 的真实字段（`TemplateEngine.assess()` 组装）：
 *   { name, template_path, description, source: 'preset', score, trial_result }
 *   trial_result = { entity_count, relation_count, field_coverage, type_diversity, types_found }
 *   score ∈ [0, 1]（threshold 默认 0.5）
 *
 * 旧实现的三处问题（挂上去会错，所以重写）：
 *  1. 读 `match_score`，真实字段是 `score` → 星级永远不显示；
 *  2. 读 `id`，候选里没有 `id`（唯一标识是 `name`）→ `selectedId === undefined`
 *     恒成立，**所有项会同时显示为选中**；
 *  3. 读 `domain` / `applicable_scenarios`，候选里没有这两个键；反过来
 *     `trial_result`（试抽取证据：实体数/关系数/字段覆盖/类型多样性）却没展示，
 *     用户看不到「为什么推荐它」。
 */
import { useCallback, useState } from 'react';
import {
  Alert, Button, Card, Empty, Space, Tag, Typography, message,
} from 'antd';
import { CheckCircleOutlined, GlobalOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Paragraph } = Typography;

export interface TemplateTrialResult {
  entity_count?: number;
  relation_count?: number;
  field_coverage?: number;
  type_diversity?: number;
  types_found?: string[];
}

export interface HETemplate {
  /** 候选的唯一标识就是 name —— 后端没有 id 字段 */
  name: string;
  template_path?: string;
  description?: string;
  source?: string;
  /** 综合得分 [0, 1] */
  score?: number;
  trial_result?: TemplateTrialResult;
  /** 联网生成失败回退时后端会带上这个标记 */
  degradation_flag?: string;
  [key: string]: unknown;
}

export interface TemplateRecommenderProps {
  ontologyId?: string;
  /** 待抽取的描述文本，作为推荐的输入 */
  text?: string;
  onSelect?: (template: HETemplate) => void;
}

export function TemplateRecommender({ ontologyId = '', text, onSelect }: TemplateRecommenderProps) {
  const { t } = useI18n('ontology');
  const [candidates, setCandidates] = useState<HETemplate[]>([]);
  const [assessment, setAssessment] = useState<{ best_score?: number; threshold?: number; needs_custom?: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [selectedName, setSelectedName] = useState('');
  const [degraded, setDegraded] = useState(false);

  const recommend = useCallback(async () => {
    if (!text?.trim()) {
      message.warning(t('请先输入描述文本'));
      return;
    }
    setLoading(true);
    try {
      // 不再传 top_k：后端 assess() 用的是配置项 he.template_top_k，请求体里的 top_k 不会被读
      const res = await ontologyApi.extraction.recommendTemplates<HETemplate>({
        text: text.trim(),
        ontology_id: ontologyId,
      });
      setCandidates(Array.isArray(res.templates) ? res.templates : []);
      setAssessment(res.assessment ?? null);
      setDegraded(false);
    } catch (e) {
      setCandidates([]);
      setAssessment(null);
      message.error(`${t('模板推荐失败')}：${reasonOf(e)}`);
    } finally {
      setLoading(false);
    }
  }, [text, ontologyId, t]);

  const generateByWebSearch = useCallback(async () => {
    if (!text?.trim()) {
      message.warning(t('请先输入描述文本'));
      return;
    }
    setSearching(true);
    try {
      const res = await ontologyApi.extraction.generateTemplateWebSearch<HETemplate>({
        text: text.trim(),
        ontology_id: ontologyId,
      });
      const template = res.template;
      if (!template) {
        message.warning(t('联网生成未返回模板'));
        return;
      }
      // 后端生成失败时会回退成 fallback 模板并带 degradation_flag
      const isDegraded = Boolean(template.degradation_flag);
      setDegraded(isDegraded);
      setCandidates((prev) => [...prev, template]);
      if (isDegraded) {
        message.warning(t('联网生成失败，已回退为预设模板'));
      } else {
        message.success(t('联网生成模板成功'));
      }
    } catch (e) {
      message.error(`${t('联网生成失败')}：${reasonOf(e)}`);
    } finally {
      setSearching(false);
    }
  }, [text, ontologyId, t]);

  const select = useCallback((template: HETemplate) => {
    setSelectedName(template.name);
    onSelect?.(template);
  }, [onSelect]);

  const needsCustom = assessment?.needs_custom === true;
  const bestScore = assessment?.best_score;
  const threshold = assessment?.threshold;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Alert
        type="info"
        showIcon
        title={t('模板推荐')}
        description={t('按描述推荐最匹配的抽取模板，三级回退：本体定义生成 → 预设模板 → 联网搜索生成。得分为 0~1，低于阈值的候选建议改用联网生成。')}
      />

      {needsCustom ? (
        <Alert
          type="warning"
          showIcon
          title={t('没有候选达到阈值')}
          description={t('最高分 {{best}}，阈值 {{threshold}} —— 建议点击「联网搜索生成」让模型针对该描述生成专用模板。', {
            best: typeof bestScore === 'number' ? bestScore.toFixed(3) : '-',
            threshold: typeof threshold === 'number' ? threshold.toFixed(2) : '-',
          })}
        />
      ) : null}

      {degraded ? (
        <Alert
          type="warning"
          showIcon
          title={t('自定义生成失败')}
          description={t('后端 generate_custom 未成功，已回退为预设模板（degradation_flag=custom_generation_failed）。')}
        />
      ) : null}

      {candidates.length === 0 ? (
        <Empty
          description={loading ? t('推荐中…') : t('暂无推荐模板，请输入描述文本后点击「推荐模板」')}
        />
      ) : (
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {candidates.map((c) => {
            const active = c.name === selectedName;
            const trial = c.trial_result ?? {};
            const scorePercent = typeof c.score === 'number' ? Math.round(c.score * 100) : null;
            return (
              <Card
                key={c.name}
                size="small"
                hoverable
                onClick={() => select(c)}
                style={{
                  cursor: 'pointer',
                  borderColor: active ? '#1677ff' : undefined,
                  background: active ? '#e6f4ff' : undefined,
                }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space wrap>
                    <Text strong>{c.name}</Text>
                    {scorePercent !== null ? (
                      <Tag color={scorePercent >= 80 ? 'green' : scorePercent >= 50 ? 'orange' : 'red'}>
                        {t('得分 {{n}}', { n: (c.score as number).toFixed(3) })}
                      </Tag>
                    ) : null}
                    {c.source ? <Tag color="blue">{c.source}</Tag> : null}
                    {c.template_path ? <Text type="secondary" style={{ fontSize: 12 }}>{c.template_path}</Text> : null}
                    {active ? <CheckCircleOutlined style={{ color: '#1677ff' }} /> : null}
                  </Space>

                  {c.description ? (
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }} ellipsis={{ rows: 2 }}>
                      {c.description}
                    </Paragraph>
                  ) : null}

                  {trial.entity_count !== undefined || trial.relation_count !== undefined ? (
                    <Space wrap size={12}>
                      <Text style={{ fontSize: 12 }}>{t('试抽取实体 {{n}}', { n: trial.entity_count ?? 0 })}</Text>
                      <Text style={{ fontSize: 12 }}>{t('关系 {{n}}', { n: trial.relation_count ?? 0 })}</Text>
                      {typeof trial.field_coverage === 'number' ? (
                        <Text style={{ fontSize: 12 }}>{t('字段覆盖 {{v}}', { v: `${Math.round(trial.field_coverage * 100)}%` })}</Text>
                      ) : null}
                      {typeof trial.type_diversity === 'number' ? (
                        <Text style={{ fontSize: 12 }}>{t('类型多样性 {{v}}', { v: `${Math.round(trial.type_diversity * 100)}%` })}</Text>
                      ) : null}
                      {(trial.types_found ?? []).slice(0, 6).map((ty) => (
                        <Tag key={ty} style={{ marginInlineEnd: 0 }}>{ty}</Tag>
                      ))}
                    </Space>
                  ) : null}
                </Space>
              </Card>
            );
          })}
        </Space>
      )}

      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button
            icon={<ThunderboltOutlined />}
            onClick={() => void recommend()}
            loading={loading}
            disabled={!text?.trim()}
          >
            {t('推荐模板')}
          </Button>
          <Button
            icon={<GlobalOutlined />}
            onClick={() => void generateByWebSearch()}
            loading={searching}
            disabled={!text?.trim()}
          >
            {t('联网搜索生成')}
          </Button>
        </Space>
      </div>
    </div>
  );
}

function reasonOf(e: unknown): string {
  const err = e as { status?: number; message?: string; detail?: string };
  if (err?.detail) return err.detail;
  if (err?.status && err?.message) return `HTTP ${err.status}：${err.message}`;
  return err?.message ?? String(e);
}

export default TemplateRecommender;
