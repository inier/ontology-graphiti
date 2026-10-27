/**
 * 决策台账表 —— **纯表格组件**（可复用：台账页 + Agent Tab 内嵌）
 *
 * 拆两层的理由（uiux §3.5 / §11 第 11 条）：Agent 页决策 Tab 要嵌同一张表，
 * 写成页面就复用不了。筛选区由外层 `DecisionFilterBar` 负责，本组件只吃 `filters`。
 *
 * 行点击 → **整页跳转详情**（不用抽屉）：详情含 420px 因果链图 + 三段列表 + 10 项
 * Descriptions，抽屉里必然出现双层滚动，且详情本身是导航中枢（可继续跳转）。
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { App, Button, Empty, Space, Typography } from 'antd';
import { CloseCircleOutlined, PartitionOutlined, ReloadOutlined } from '@ant-design/icons';
import { AdvancedTable } from '@/modules/shared';
import type { DecisionFilters, DecisionRecord } from '../types';
import { listDecisionLedger } from '../services/decisionApi';
import { describeError } from '../services/decisionRequest';
import { buildLedgerColumns } from './ledgerColumns';
import { buildLedgerQuery, hasActiveFilters } from '../utils/ledgerQuery';
import type { LedgerSort, SortOrder } from '../utils/ledgerQuery';

const { Text } = Typography;

interface Props {
  filters: DecisionFilters;
  onOpenDetail: (decisionId: string) => void;
  /** Agent Tab 内嵌：传入后按 agent_id 收窄（隐藏参数，不做可见筛选器） */
  agentId?: string;
  /** 内嵌语境标签里的 Agent 展示名（缺省退回 agent_id） */
  agentName?: string;
  /** 内嵌模式：列宽自适应、固定 10 条/页 */
  embedded?: boolean;
  /** 外部触发刷新（如批量裁决后） */
  refreshToken?: number;
  /** 上报当前总数，供页面显示计数（用 ref 保存，避免回调身份变化引起重取） */
  onTotalChange?: (total: number, estimate: boolean) => void;
  onFilterReset?: () => void;
  /** 内嵌模式「查看全部」链接 */
  onViewAll?: () => void;
}

interface LedgerState {
  items: DecisionRecord[];
  total: number;
  estimate: boolean;
  hasMore: boolean;
}

const EMPTY_STATE: LedgerState = { items: [], total: 0, estimate: false, hasMore: false };

export function DecisionLedgerTable({
  filters,
  onOpenDetail,
  agentId,
  agentName,
  embedded = false,
  refreshToken = 0,
  onTotalChange,
  onFilterReset,
  onViewAll,
}: Props) {
  const { message } = App.useApp();
  const [state, setState] = useState<LedgerState>(EMPTY_STATE);
  const [loading, setLoading] = useState(true);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(embedded ? 10 : 20);
  const [sort, setSort] = useState<{ field: LedgerSort; order: SortOrder }>({
    field: 'created_at',
    order: 'desc',
  });
  const requestSeq = useRef(0);
  const totalCallbackRef = useRef(onTotalChange);
  useEffect(() => {
    totalCallbackRef.current = onTotalChange;
  }, [onTotalChange]);

  const filterKey = useMemo(() => JSON.stringify({ filters, agentId }), [filters, agentId]);

  // 筛选变更 → 重置到第 1 页（照 AuditLog 既有范式）
  useEffect(() => {
    setPage(1);
  }, [filterKey]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    try {
      const params = buildLedgerQuery(filters, {
        page,
        pageSize,
        sort: sort.field,
        order: sort.order,
        agentId,
      });
      const data = await listDecisionLedger(params);
      if (seq !== requestSeq.current) return; // 竞态：丢弃过期响应
      setState({
        items: data.items ?? [],
        total: data.total ?? 0,
        estimate: Boolean(data.total_is_estimate),
        hasMore: Boolean(data.has_more),
      });
      setError(null);
      totalCallbackRef.current?.(data.total ?? 0, Boolean(data.total_is_estimate));
    } catch (e) {
      if (seq !== requestSeq.current) return;
      setError(e);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
        setLoadedOnce(true);
      }
    }
  }, [filters, page, pageSize, sort, agentId]);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const columns = useMemo(
    () =>
      buildLedgerColumns({
        onOpenDetail,
        onCopyId: (id) => {
          void navigator.clipboard?.writeText(id);
          message.success('已复制决策 ID');
        },
      }),
    [onOpenDetail, message],
  );

  const handleTableChange = useCallback((_pagination: unknown, _filters: unknown, sorter: unknown) => {
    const s = sorter as { field?: string; order?: 'ascend' | 'descend' | null };
    if (!s?.order) {
      setSort({ field: 'created_at', order: 'desc' });
      return;
    }
    // 白名单：只有契约 sort enum 里的可排序列才认，其余一律回落默认排序
    const field: LedgerSort = s.field === 'confidence' ? 'confidence' : 'created_at';
    setSort({ field, order: s.order === 'ascend' ? 'asc' : 'desc' });
  }, []);

  const filtered = hasActiveFilters(filters);

  const emptyNode = loading ? null : filtered ? (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <Space orientation="vertical" size={4}>
          <Text strong>当前筛选条件下没有决策</Text>
          <Text type="secondary">清除筛选可以查看当前工作空间的全部决策</Text>
        </Space>
      }
    >
      <Button onClick={onFilterReset ?? (() => setPage(1))}>清除筛选</Button>
    </Empty>
  ) : (
    <Empty
      image={<PartitionOutlined style={{ fontSize: 24, color: 'var(--odap-color-text-tertiary)' }} />}
      description={
        <Space orientation="vertical" size={4}>
          <Text strong>当前工作空间还没有决策记录</Text>
          <Text type="secondary">从问答发起一次决策，它会自动出现在这里</Text>
        </Space>
      }
    >
      <Button type="primary" href="/qa">
        去问答发起第一个决策
      </Button>
    </Empty>
  );

  if (error && !loading) {
    return (
      <div
        role="alert"
        style={{
          border: '1px solid var(--odap-color-border)',
          borderRadius: 'var(--odap-radius-md)',
          padding: 'var(--odap-spacing-xl)',
          background: 'var(--odap-color-bg-primary)',
          textAlign: 'center',
        }}
      >
        <CloseCircleOutlined
          style={{ fontSize: 24, color: 'var(--odap-color-error)', marginBottom: 8 }}
        />
        <div style={{ marginBottom: 4 }}>
          <Text strong>决策台账加载失败</Text>
        </div>
        {/* 必须暴露具体原因：HTTP 状态 + 后端 detail，不许笼统「加载失败」 */}
        <Text type="secondary">{describeError(error)}</Text>
        <div style={{ marginTop: 12 }}>
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>
            重试
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {embedded && agentId && (
        // 过滤条件对用户隐藏，但「过滤这个事实」必须可见（uiux §4.3）
        <Space size={8} style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-sm)' }}>
            {`当前仅显示 ${agentName || agentId} 产生的决策`}
          </Text>
          {onViewAll && (
            <Button type="link" size="small" onClick={onViewAll}>
              查看全部
            </Button>
          )}
        </Space>
      )}
      <div style={{ opacity: loading && loadedOnce ? 0.6 : 1 }}>
        <AdvancedTable<DecisionRecord>
          rowKey="decision_id"
          columns={columns}
          dataSource={state.items}
          loading={loading}
          scroll={embedded ? { x: 900 } : { x: 1580 }}
          pagination={{
            current: page,
            pageSize,
            total: state.total,
            showQuickJump: false,
            showSizeChanger: !embedded,
            showTotal: () =>
              state.estimate
                ? `约 ${state.total} 条（估算）`
                : filtered
                  ? `已筛选出 ${state.total} 条`
                  : `共 ${state.total} 条`,
            onChange: (nextPage: number, nextSize: number) => {
              setPage(nextPage);
              setPageSize(nextSize);
            },
          }}
          onChange={handleTableChange}
          locale={{ emptyText: emptyNode }}
          onRow={(record) => ({
            onClick: () => onOpenDetail(record.decision_id),
            style: { cursor: 'pointer' },
          })}
        />
      </div>
    </div>
  );
}

export default DecisionLedgerTable;
