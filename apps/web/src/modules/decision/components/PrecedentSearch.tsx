/**
 * 先例参考卡片
 *
 * 本期新增两个可选 prop（uiux §6.2）：
 * - `initialQuery`：详情页传 `context_summary`，进入即预填
 * - `autoSearch`：进入即自动检索，用户不用再手打一遍
 *
 * 结果标签不再用 `OUTCOME_META.color`（antd 预设色名绕过 Token 体系，
 * 且 `lime` 与 `green` 肉眼不可分），改用 `DecisionStatusTag`。
 */
import React, { useEffect, useRef, useState } from 'react';
import { App, Button, Card, Empty, Input, List, Space, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { DecisionRecord } from '../types';
import { findSimilarDecisions } from '../services/decisionApi';
import { describeError } from '../services/decisionRequest';
import { DecisionStatusTag } from './DecisionStatusTag';

const { Text, Paragraph } = Typography;

interface Props {
  onSelectDecision?: (decisionId: string) => void;
  initialQuery?: string;
  autoSearch?: boolean;
}

export function PrecedentSearch({ onSelectDecision, initialQuery, autoSearch = false }: Props) {
  const { message } = App.useApp();
  const [query, setQuery] = useState(initialQuery ?? '');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<DecisionRecord[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const autoSearchedRef = useRef<string | null>(null);

  const runSearch = async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await findSimilarDecisions(text.trim(), 5);
      setResults(data);
    } catch (e) {
      setError(e);
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setQuery(initialQuery ?? '');
  }, [initialQuery]);

  useEffect(() => {
    if (!autoSearch || !initialQuery?.trim()) return;
    // 同一查询只自动检索一次，避免父组件重渲染导致反复请求
    if (autoSearchedRef.current === initialQuery) return;
    autoSearchedRef.current = initialQuery;
    void runSearch(initialQuery);
  }, [autoSearch, initialQuery]);

  return (
    <Card title="先例参考" size="small">
      <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
        <Input
          placeholder="描述当前决策场景，搜索历史先例…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={() => void runSearch(query)}
        />
        <Button
          type="primary"
          icon={<SearchOutlined style={{ fontSize: 16 }} />}
          loading={loading}
          onClick={() => {
            if (!query.trim()) {
              message.warning('请先填写决策场景描述');
              return;
            }
            void runSearch(query);
          }}
        >
          搜索
        </Button>
      </Space.Compact>

      {error ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<Text type="secondary">{`先例检索失败：${describeError(error)}`}</Text>}
        >
          <Button size="small" onClick={() => void runSearch(query)}>
            重试
          </Button>
        </Empty>
      ) : results === null ? (
        <Empty
          description={loading ? '正在检索相似历史决策…' : '搜索后展示相似历史决策'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : results.length === 0 ? (
        <Empty
          description={
            <Space orientation="vertical" size={4}>
              <Text strong>未找到相似先例</Text>
              <Text type="secondary">换个说法或缩短描述再试</Text>
            </Space>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <List
          size="small"
          dataSource={results}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer' }}
              onClick={() => onSelectDecision?.(item.decision_id)}
            >
              <List.Item.Meta
                title={
                  <Space size={8} wrap>
                    <Text strong>{item.recommended_option || item.decision_id}</Text>
                    <DecisionStatusTag status={item.status} outcome={item.outcome} />
                    <Text type="secondary" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {`置信度 ${Math.round((item.confidence ?? 0) * 100)}%`}
                    </Text>
                  </Space>
                }
                description={
                  <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ marginBottom: 0 }}>
                    {item.context_summary || '未填写场景描述'}
                  </Paragraph>
                }
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

export default PrecedentSearch;
