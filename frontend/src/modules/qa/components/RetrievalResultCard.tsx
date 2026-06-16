/**
 * 检索结果卡片 - 展示单条检索结果，标记支柱来源
 */
import React from 'react';
import { Card, Tag, Space, Typography, Tooltip } from 'antd';
import {
  SearchOutlined,
  ApiOutlined,
  BranchesOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { RetrievalResult, SourceReference } from '../services/nlQueryApi';

const { Text, Paragraph } = Typography;

const PILLAR_STYLE: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  bm25: { icon: <SearchOutlined />, color: 'blue', label: 'BM25' },
  vector: { icon: <ApiOutlined />, color: 'green', label: 'Vector' },
  graph: { icon: <BranchesOutlined />, color: 'orange', label: 'Graph' },
};

interface RetrievalResultCardProps {
  result: RetrievalResult | SourceReference;
  rank?: number;
  showEntities?: boolean;
}

export function RetrievalResultCard({ result, rank, showEntities = true }: RetrievalResultCardProps) {
  const pillar = PILLAR_STYLE[result.pillar] || { icon: <LinkOutlined />, color: 'default', label: result.pillar };
  const isRetrievalResult = 'entities' in result;

  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderLeft: `3px solid ${pillar.color === 'blue' ? '#1890ff' : pillar.color === 'green' ? '#52c41a' : '#fa8c16'}` }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 标题行 */}
          <Space size={6} style={{ marginBottom: 4 }}>
            {rank !== undefined && (
              <Text type="secondary" style={{ fontSize: 11 }}>#{rank}</Text>
            )}
            <Tag icon={pillar.icon} color={pillar.color} style={{ margin: 0, fontSize: 11 }}>
              {pillar.label}
            </Tag>
            <Tag style={{ margin: 0, fontSize: 11 }}>{result.source}</Tag>
            <Tooltip title={`置信度: ${(result.score * 100).toFixed(1)}%`}>
              <Text style={{ fontSize: 11, color: result.score > 0.7 ? '#52c41a' : result.score > 0.4 ? '#faad14' : '#999' }}>
                {(result.score * 100).toFixed(1)}%
              </Text>
            </Tooltip>
          </Space>

          {/* 内容 */}
          <Paragraph
            style={{ margin: 0, fontSize: 13, lineHeight: 1.6 }}
            ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
          >
            {result.content}
          </Paragraph>

          {/* 实体/关系标签 */}
          {showEntities && isRetrievalResult && (result as RetrievalResult).entities.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {(result as RetrievalResult).entities.slice(0, 5).map((e, i) => (
                <Tag key={i} style={{ fontSize: 11, marginBottom: 2 }} color="processing">{e}</Tag>
              ))}
              {(result as RetrievalResult).entities.length > 5 && (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  +{(result as RetrievalResult).entities.length - 5} 更多
                </Text>
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
