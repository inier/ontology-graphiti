/**
 * 先例参考卡片（ADR-076 §8 前端块 2）
 * 输入当前决策场景 → find_similar_decisions → 卡片列表（含结果标签与置信度）
 */
import React, { useState } from 'react';
import { App, Button, Card, Empty, Input, List, Space, Tag, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { DecisionRecord } from '../types';
import { OUTCOME_META } from '../types';
import { findSimilarDecisions } from '../services/decisionApi';

const { Text, Paragraph } = Typography;

interface Props {
  onSelectDecision?: (decisionId: string) => void;
}

export function PrecedentSearch({ onSelectDecision }: Props) {
  const { message } = App.useApp();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<DecisionRecord[] | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) {
      message.warning('请输入决策场景描述');
      return;
    }
    setLoading(true);
    try {
      const data = await findSimilarDecisions(query.trim(), 5);
      setResults(data);
    } catch (e: any) {
      message.error(`先例搜索失败: ${e?.message || e}`);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="先例参考" size="small">
      <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
        <Input
          placeholder="描述当前决策场景，搜索历史先例…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={handleSearch}
        />
        <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={handleSearch}>
          搜索
        </Button>
      </Space.Compact>

      {results === null ? (
        <Empty description="搜索后展示相似历史决策" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : results.length === 0 ? (
        <Empty description="未找到相似先例" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={results}
          renderItem={(item) => {
            const meta = OUTCOME_META[item.outcome] || OUTCOME_META.pending;
            return (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectDecision?.(item.decision_id)}
              >
                <List.Item.Meta
                  title={
                    <Space size={8} wrap>
                      <Text strong>{item.recommended_option || item.decision_id}</Text>
                      <Tag color={meta.color}>{meta.label}</Tag>
                      <Tag>{`置信度 ${(item.confidence * 100).toFixed(0)}%`}</Tag>
                    </Space>
                  }
                  description={
                    <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ marginBottom: 0 }}>
                      {item.context_summary || item.reasoning || '（无摘要）'}
                    </Paragraph>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}
