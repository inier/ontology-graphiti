/**
 * 查询结果列表 - 展示检索结果和回答
 */
import React from 'react';
import { Empty, Spin, Typography, Divider, Space, Tag, Progress, Tabs } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { FileSearchOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { OverlaySpin } from '@/modules/shared/components/OverlaySpin';
import { RetrievalResultCard } from './RetrievalResultCard';
import type { QueryResponse, NLSearchResponse, SourceReference, RetrievalResult } from '../services/nlQueryApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Paragraph } = Typography;

interface QueryResultListProps {
  queryResult?: QueryResponse | null;
  searchResult?: NLSearchResponse | null;
  loading?: boolean;
  error?: string | null;
}

export function QueryResultList({ queryResult, searchResult, loading, error }: QueryResultListProps) {
  const { t } = useI18n('qa');

  if (error) {
    return (
      <Card size="small" style={{ margin: 12 }}>
        <Text type="danger">{error}</Text>
      </Card>
    );
  }

  const hasQueryResult = queryResult && queryResult.answer;
  const hasSearchResult = searchResult && searchResult.results.length > 0;

  if (!hasQueryResult && !hasSearchResult) {
    return (
      <OverlaySpin spinning={!!loading} tip={t('result.searching')}>
        <div style={{ padding: 40 }}>
          <Empty
            image={<FileSearchOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
            description={t('result.empty')}
          />
        </div>
      </OverlaySpin>
    );
  }

  // 支柱贡献度
  const renderPillarContributions = (contributions: Record<string, number>) => {
    const total = Object.values(contributions).reduce((a, b) => a + b, 0) || 1;
    return (
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        {Object.entries(contributions).map(([pillar, value]) => {
          const pct = Math.round((value / total) * 100);
          const color = pillar === 'bm25' ? '#1890ff' : pillar === 'vector' ? '#52c41a' : '#fa8c16';
          return (
            <div key={pillar} style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text style={{ fontSize: 11, color }}>{pillar.toUpperCase()}</Text>
                <Text style={{ fontSize: 11, color: '#999' }}>{pct}%</Text>
              </div>
              <Progress percent={pct} showInfo={false} strokeColor={color} size="small" />
            </div>
          );
        })}
      </div>
    );
  };

  // 完整查询结果
  if (hasQueryResult) {
    const items = [
      {
        key: 'answer',
        label: (
          <Space>
            <CheckCircleOutlined />
            <span>{t('result.answer')}</span>
          </Space>
        ),
        children: (
          <div>
            {renderPillarContributions(queryResult!.pillar_contributions)}
            <Paragraph style={{ fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
              {queryResult!.answer}
            </Paragraph>
            <Divider style={{ margin: '12px 0' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('result.queryTime', { time: queryResult!.total_time_ms.toFixed(0), count: queryResult!.sources.length })}
            </Text>
          </div>
        ),
      },
      {
        key: 'sources',
        label: t('result.sourcesLabel', { count: queryResult!.sources.length }),
        children: (
          <div>
            {queryResult!.sources.map((s: SourceReference, i: number) => (
              <RetrievalResultCard key={s.doc_id || i} result={s} rank={i + 1} />
            ))}
          </div>
        ),
      },
    ];

    return (
      <div style={{ padding: '12px 16px' }}>
        <Tabs items={items} size="small" />
      </div>
    );
  }

  // 纯检索结果
  if (hasSearchResult) {
    return (
      <div style={{ padding: '12px 16px' }}>
        <div style={{ marginBottom: 8 }}>
          <Space>
            <Text strong>{t('result.searchResults')}</Text>
            <Tag>{t('result.resultCount', { count: searchResult!.total })}</Tag>
          </Space>
        </div>
        {renderPillarContributions(searchResult!.pillar_scores)}
        {searchResult!.results.map((r: RetrievalResult, i: number) => (
          <RetrievalResultCard key={r.doc_id || i} result={r} rank={i + 1} />
        ))}
      </div>
    );
  }

  return null;
}
