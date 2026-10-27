/**
 * 决策台账页（`/decisions/ledger`）—— 页面壳
 *
 * 只做装配：视图切换 + 筛选区 + 表格。
 * 表格本体在 `components/DecisionLedgerTable`（Agent Tab 要复用同一个表，不能写成页面）。
 * 不新增一级菜单：菜单由后端 `menu_config` seed 驱动，视图切换走路由内 Segmented。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Breadcrumb, Button, Input, Segmented, Space, Typography } from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { SearchOutlined } from '@ant-design/icons';
import type { DecisionFilters } from '../types';
import { DecisionFilterBar } from '../components/DecisionFilterBar';
import { DecisionLedgerTable } from '../components/DecisionLedgerTable';
import {
  defaultFilters,
  filtersToSearchParams,
  searchParamsToFilters,
} from '../utils/ledgerQuery';

const { Text } = Typography;

export default function DecisionLedgerPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<DecisionFilters>(() => {
    const fromUrl = searchParamsToFilters(searchParams);
    if (fromUrl.createdFrom || fromUrl.createdTo || fromUrl.results.length) return fromUrl;
    // 默认近 30 天：不提供「全部时间」以保护性能（PRD §10 容量要求）
    const now = new Date();
    const from = new Date(now.getTime() - 29 * 24 * 3600 * 1000);
    return { ...defaultFilters(), createdFrom: from.toISOString(), createdTo: now.toISOString() };
  });
  const [refreshToken, setRefreshToken] = useState(0);
  const [total, setTotal] = useState<{ value: number; estimate: boolean }>({ value: 0, estimate: false });
  const [idJump, setIdJump] = useState('');

  // 筛选同步到 URL query：刷新/分享仍可复现视图（不只靠 KeepAlive 内存缓存）
  // 比较序列化结果后再写，避免 searchParams 身份变化引起重复导航
  useEffect(() => {
    const next = filtersToSearchParams(filters).toString();
    if (next === searchParams.toString()) return;
    setSearchParams(next, { replace: true });
  }, [filters, searchParams, setSearchParams]);

  const openDetail = useCallback(
    (decisionId: string) => navigate(`/decisions/detail/${decisionId}`),
    [navigate],
  );

  const viewOptions = useMemo(
    () => [
      { label: '待决策队列', value: '/decisions/queue' },
      { label: '决策台账', value: '/decisions/ledger' },
    ],
    [],
  );

  return (
    <div style={{ padding: 'var(--odap-spacing-md)' }}>
      <Breadcrumb
        items={[{ title: '决策智能' }, { title: '决策台账' }]}
        style={{ marginBottom: 'var(--odap-spacing-sm)' }}
      />

      <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Segmented
          value="/decisions/ledger"
          options={viewOptions}
          onChange={(value) => navigate(String(value))}
        />
        {/* 保留 ID 直接打开的降级入口，但不作为页面主视觉（本体工程师调试用） */}
        <Space.Compact style={{ width: 320 }}>
          <Input
            value={idJump}
            placeholder="按决策 ID 直接打开（dec_xxxxxxxxxxxx）"
            onChange={(e) => setIdJump(e.target.value)}
            onPressEnter={() => idJump.trim() && openDetail(idJump.trim())}
          />
          <Button
            icon={<SearchOutlined style={{ fontSize: 16 }} />}
            onClick={() => idJump.trim() && openDetail(idJump.trim())}
          >
            打开
          </Button>
        </Space.Compact>
      </Space>

      <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
        <DecisionFilterBar value={filters} onChange={setFilters} />
      </Space>

      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-sm)' }}>
          {total.estimate ? `约 ${total.value} 条（估算）` : `共 ${total.value} 条`}
        </Text>
      </div>

      <DecisionLedgerTable
        filters={filters}
        onOpenDetail={openDetail}
        refreshToken={refreshToken}
        onTotalChange={(value, estimate) => setTotal({ value, estimate })}
        onFilterReset={() => setFilters(defaultFilters())}
      />

      <div style={{ marginTop: 12 }}>
        <Button size="small" onClick={() => setRefreshToken((n) => n + 1)}>
          刷新台账
        </Button>
      </div>
    </div>
  );
}
