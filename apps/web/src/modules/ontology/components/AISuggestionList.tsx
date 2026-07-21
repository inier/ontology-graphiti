/**
 * T073 AISuggestionList — AI 建议列表组件
 *
 * 功能：
 * - 显示 pending/accepted/rejected 状态的 AI 建议
 * - 支持接受/拒绝/编辑操作
 * - 按状态过滤
 * - 实时刷新
 *
 * 使用场景：
 * - ObjectTypeEditor 属性列表下方
 * - 独立的"AI 建议"标签页
 */

import { useState, useEffect, useCallback } from 'react';
import {
  List,
  Tag,
  Button,
  Empty,
  Spin,
  Segmented,
  Tooltip,
  message,
  Popconfirm,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import type { AISuggestion } from '../services/ontologyApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export interface AISuggestionListProps {
  /** 本体 ID */
  ontologyId: string;
  /** 建议被接受时的回调 */
  onAccept?: (suggestion: AISuggestion) => void;
  /** 建议被拒绝时的回调 */
  onReject?: (suggestion: AISuggestion, reason?: string) => void;
  /** 自动刷新间隔（ms），0 表示不自动刷新 */
  autoRefreshMs?: number;
  /** 最大高度 */
  maxHeight?: number;
}

type StatusFilter = 'all' | 'pending' | 'accepted' | 'rejected';

export function AISuggestionList({
  ontologyId,
  onAccept,
  onReject,
  autoRefreshMs = 0,
  maxHeight = 400,
}: AISuggestionListProps) {
  const { t } = useI18n('ontology');
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending');

  const loadSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const result = await ontologyApi.aiAssistant.listSuggestions({
        ontologyId,
        status: statusFilter === 'all' ? undefined : statusFilter,
      });
      setSuggestions(result.suggestions || []);
    } catch (err) {
      // 静默失败
      console.error('[AISuggestionList] failed to load:', err);
    } finally {
      setLoading(false);
    }
  }, [ontologyId, statusFilter]);

  // 数据加载：依赖 loadSuggestions（随 ontologyId/statusFilter 变化）
  // 异步 fetch 内部 setState 属于标准数据获取模式，非同步级联渲染
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    void loadSuggestions();
  }, [loadSuggestions]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // 自动刷新
  useEffect(() => {
    if (autoRefreshMs <= 0) return;
    const timer = setInterval(() => {
      void loadSuggestions();
    }, autoRefreshMs);
    return () => clearInterval(timer);
  }, [autoRefreshMs, loadSuggestions]);

  const handleAccept = useCallback(
    async (suggestionId: string) => {
      try {
        const result = await ontologyApi.aiAssistant.acceptSuggestion(suggestionId);
        message.success(t('建议已接受'));
        onAccept?.(result.suggestion);
        // 更新本地列表
        setSuggestions((prev) =>
          prev.map((s) =>
            s.suggestion_id === suggestionId
              ? { ...s, status: 'accepted', resolved_at: new Date().toISOString() }
              : s,
          ),
        );
      } catch (err) {
        message.error(t('aiSuggestion.acceptFailed', { error: err instanceof Error ? err.message : String(err) }));
      }
    },
    [onAccept],
  );

  const handleReject = useCallback(
    async (suggestionId: string) => {
      try {
        const result = await ontologyApi.aiAssistant.rejectSuggestion(suggestionId, '用户拒绝');
        message.success(t('建议已拒绝'));
        onReject?.(result.suggestion, '用户拒绝');
        // 更新本地列表
        setSuggestions((prev) =>
          prev.map((s) =>
            s.suggestion_id === suggestionId
              ? {
                  ...s,
                  status: 'rejected',
                  rejection_reason: '用户拒绝',
                  resolved_at: new Date().toISOString(),
                }
              : s,
          ),
        );
      } catch (err) {
        message.error(t('aiSuggestion.rejectFailed', { error: err instanceof Error ? err.message : String(err) }));
      }
    },
    [onReject],
  );

  const statusTag = (status: string) => {
    switch (status) {
      case 'pending':
        return (
          <Tag icon={<ClockCircleOutlined />} color="processing">
            {t('待处理')}
          </Tag>
        );
      case 'accepted':
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            {t('已接受')}
          </Tag>
        );
      case 'rejected':
        return (
          <Tag icon={<StopOutlined />} color="default">
            {t('已拒绝')}
          </Tag>
        );
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const categoryLabel = (category: string): string => {
    return t(`aiSuggestion.types.${category}`, category);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', maxHeight }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Segmented
          size="small"
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as StatusFilter)}
          options={[
            { label: t('待处理'), value: 'pending' },
            { label: t('已接受'), value: 'accepted' },
            { label: t('已拒绝'), value: 'rejected' },
            { label: t('common.message.all', '全部'), value: 'all' },
          ]}
        />
        <Tooltip title={t('common.button.refresh')}>
          <Button
            size="small"
            type="text"
            icon={<ReloadOutlined />}
            onClick={loadSuggestions}
            loading={loading}
          />
        </Tooltip>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading && suggestions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin />
          </div>
        ) : suggestions.length === 0 ? (
          <Empty
            description={t('aiSuggestion.noSuggestions', '暂无建议')}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ padding: '24px 0' }}
          />
        ) : (
          <List
            size="small"
            dataSource={suggestions}
            renderItem={(suggestion) => (
              <List.Item
                actions={
                  suggestion.status === 'pending'
                    ? [
                        <Popconfirm
                          key="reject"
                          title={t('aiSuggestion.confirmReject', '确认拒绝此建议？')}
                          onConfirm={() => handleReject(suggestion.suggestion_id)}
                        >
                          <Button size="small" danger icon={<CloseOutlined />}>
                            {t('aiSuggestion.reject', '拒绝')}
                          </Button>
                        </Popconfirm>,
                        <Button
                          key="accept"
                          size="small"
                          type="primary"
                          icon={<CheckOutlined />}
                          onClick={() => handleAccept(suggestion.suggestion_id)}
                        >
                          {t('aiSuggestion.accept', '接受')}
                        </Button>,
                      ]
                    : undefined
                }
              >
                <List.Item.Meta
                  title={
                    <span>
                      <Tag color="purple">{categoryLabel(suggestion.suggestion_category)}</Tag>
                      {statusTag(suggestion.status)}
                      {suggestion.confidence > 0 && (
                        <Tag style={{ fontSize: 10 }}>
                          {Math.round(suggestion.confidence * 100)}%
                        </Tag>
                      )}
                    </span>
                  }
                  description={
                    <div style={{ fontSize: 12 }}>
                      <pre
                        style={{
                          margin: '4px 0',
                          padding: 4,
                          background: '#fafafa',
                          borderRadius: 2,
                          fontSize: 11,
                          maxHeight: 60,
                          overflow: 'auto',
                        }}
                      >
                        {JSON.stringify(suggestion.content, null, 2)}
                      </pre>
                      {suggestion.rejection_reason && (
                        <div style={{ color: '#999' }}>
                          {t('aiSuggestion.rejectReason', '拒绝原因')}: {suggestion.rejection_reason}
                        </div>
                      )}
                      <div style={{ color: '#ccc', fontSize: 10 }}>
                        {new Date(suggestion.created_at).toLocaleString()}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );
}
