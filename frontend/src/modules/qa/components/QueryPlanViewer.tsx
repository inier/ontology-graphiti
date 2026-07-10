/**
 * 查询计划可视化 - 展示五阶段管线的理解和计划
 */
import React from 'react';
import { Tag, Space, Typography, Collapse } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  BulbOutlined,
  ScheduleOutlined,
  FormOutlined,
} from '@ant-design/icons';
import type { QueryUnderstanding, QueryPlan, SubQuery } from '../services/nlQueryApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Paragraph } = Typography;

const PILLAR_COLORS: Record<string, string> = {
  bm25: '#1890ff',
  vector: '#52c41a',
  graph: '#fa8c16',
};

interface QueryPlanViewerProps {
  understanding?: QueryUnderstanding;
  plan?: QueryPlan;
  explanation?: string;
  loading?: boolean;
}

function getIntentLabel(intent: string, t: (key: string) => string): { label: string; color: string } {
  switch (intent) {
    case 'keyword_lookup': return { label: t('plan.intentKeyword'), color: 'blue' };
    case 'semantic_search': return { label: t('plan.intentSemantic'), color: 'green' };
    case 'graph_traverse': return { label: t('plan.intentGraph'), color: 'orange' };
    case 'complex_analysis': return { label: t('plan.intentComplex'), color: 'purple' };
    case 'temporal_query': return { label: t('plan.intentTemporal'), color: 'cyan' };
    case 'action': return { label: t('plan.intentAction'), color: 'red' };
    default: return { label: intent, color: 'default' };
  }
}

export function QueryPlanViewer({ understanding, plan, explanation, loading }: QueryPlanViewerProps) {
  const { t } = useI18n('qa');

  if (!understanding && !plan && !explanation) {
    return null;
  }

  const intentInfo = understanding ? getIntentLabel(understanding.intent, t) : null;

  const renderSubQuery = (sq: SubQuery, idx: number) => (
    <div
      key={idx}
      style={{
        padding: '6px 10px',
        marginBottom: 4,
        borderRadius: 6,
        borderLeft: `3px solid ${PILLAR_COLORS[sq.pillar] || '#999'}`,
        background: '#fafafa',
      }}
    >
      <Space size={6}>
        <Tag color={sq.pillar === 'bm25' ? 'blue' : sq.pillar === 'vector' ? 'green' : 'orange'} style={{ margin: 0 }}>
          {sq.pillar.toUpperCase()}
        </Tag>
        <Text style={{ fontSize: 12 }}>{sq.query}</Text>
        {sq.mode && <Tag style={{ fontSize: 11 }}>{sq.mode}</Tag>}
      </Space>
    </div>
  );

  const items = [
    {
      key: 'understanding',
      label: (
        <Space>
          <BulbOutlined />
          <span>{t('plan.understanding')}</span>
          {intentInfo && <Tag color={intentInfo.color}>{intentInfo.label}</Tag>}
          {understanding?.needs_clarification && <Tag color="warning">{t('plan.needsClarification')}</Tag>}
        </Space>
      ),
      children: understanding ? (
        <Descriptions column={1}>
          <Descriptions.Item label={t('plan.originalQuery')}>{understanding.original_query}</Descriptions.Item>
          <Descriptions.Item label={t('plan.intent')}>
            <Tag color={intentInfo?.color}>{intentInfo?.label}</Tag>
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              {t('plan.confidence', { value: (understanding.confidence * 100).toFixed(0) })}
            </Text>
          </Descriptions.Item>
          {understanding.extracted_entities.length > 0 && (
            <Descriptions.Item label={t('plan.extractedEntities')}>
              {understanding.extracted_entities.map((e, i) => (
                <Tag key={i} color="processing" style={{ marginBottom: 2 }}>{e}</Tag>
              ))}
            </Descriptions.Item>
          )}
          {understanding.rewritten_queries.length > 0 && (
            <Descriptions.Item label={t('plan.rewrittenQueries')}>
              {understanding.rewritten_queries.map((q, i) => (
                <div key={i} style={{ fontSize: 12, color: '#666', marginBottom: 2 }}>{q}</div>
              ))}
            </Descriptions.Item>
          )}
          {understanding.needs_clarification && (
            <Descriptions.Item label={t('plan.clarificationReason')}>
              <Text type="warning">{understanding.clarification_reason}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      ) : (
        <Text type="secondary">{t('plan.noUnderstanding')}</Text>
      ),
    },
    {
      key: 'plan',
      label: (
        <Space>
          <ScheduleOutlined />
          <span>{t('plan.plan')}</span>
          {plan && (
            <Tag color="geekblue">{plan.fusion_strategy.toUpperCase()}</Tag>
          )}
        </Space>
      ),
      children: plan ? (
        <div>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('plan.selectedPillars')} {plan.pillars.map((p) => (
                <Tag key={p} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'} style={{ fontSize: 11 }}>
                  {p.toUpperCase()}
                </Tag>
              ))}
              <span style={{ marginLeft: 8 }}>{t('plan.topK', { value: plan.top_k })}</span>
            </Text>
          </div>
          {plan.sub_queries.map(renderSubQuery)}
        </div>
      ) : (
        <Text type="secondary">{t('plan.noPlan')}</Text>
      ),
    },
    ...(explanation ? [{
      key: 'explanation',
      label: (
        <Space>
          <FormOutlined />
          <span>{t('plan.explanation')}</span>
        </Space>
      ),
      children: <Paragraph style={{ fontSize: 13, margin: 0 }}>{explanation}</Paragraph>,
    }] : []),
  ];

  return (
    <Card
      size="small"
      title={t('plan.title')}
      loading={loading}
      style={{ marginBottom: 12 }}
    >
      <Collapse items={items} defaultActiveKey={['understanding', 'plan']} />
    </Card>
  );
}
