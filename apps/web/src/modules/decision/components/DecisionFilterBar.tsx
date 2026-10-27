/**
 * 台账筛选区（外置在表格上方，因为 AdvancedTable 已 `search={false}`）
 *
 * 契约驱动的「不渲染」清单（渲染一个点了没反应的筛选器，比不渲染更伤信任）：
 * - 「仅看证据不完整」→ 契约无 `evidence_incomplete`，已降 P1 → **不渲染，也不留灰色占位**
 * - 「按 Agent 过滤」→ 契约有 `agent_id` 但它是内部收窄维度，不做可见控件（由 `agentId` prop 注入）
 * - 结果多选依赖 `status[]` + `outcome[]`，契约已支持（api-spec `:49-70`）→ 可渲染
 * - 置信度区间用 `min_confidence` / `max_confidence` → 可渲染
 */
import React, { useEffect, useRef, useState } from 'react';
import { DatePicker, Input, Segmented, Select, Space, Typography } from 'antd';
import { CalendarOutlined, FilterOutlined, SearchOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { DecisionEntrySource, DecisionFilters } from '../types';
import { ENTRY_SOURCE_OPTIONS, RESULT_FILTER_OPTIONS } from '../types';

const { RangePicker } = DatePicker;
const { Text } = Typography;

interface Props {
  value: DecisionFilters;
  onChange: (next: DecisionFilters) => void;
  /** Agent Tab 内嵌时收窄：只保留时间范围 / 结果 / 关键词 */
  compact?: boolean;
}

const CONFIDENCE_OPTIONS = [
  { label: '不限', value: 'all' },
  { label: '低 <60%', value: 'low' },
  { label: '中 60–80%', value: 'medium' },
  { label: '高 >80%', value: 'high' },
];

const RANGE_PRESETS = [
  { label: '今天', value: [dayjs().startOf('day'), dayjs()] as [Dayjs, Dayjs] },
  { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs()] as [Dayjs, Dayjs] },
  { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs()] as [Dayjs, Dayjs] },
];

export function DecisionFilterBar({ value, onChange, compact = false }: Props) {
  const [keyword, setKeyword] = useState(value.q ?? '');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setKeyword(value.q ?? '');
  }, [value.q]);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const handleKeywordChange = (next: string) => {
    setKeyword(next);
    if (timerRef.current) clearTimeout(timerRef.current);
    // 300ms 防抖，避免每次按键都打接口
    timerRef.current = setTimeout(() => onChange({ ...value, q: next || undefined }), 300);
  };

  const range: [Dayjs, Dayjs] | null =
    value.createdFrom && value.createdTo ? [dayjs(value.createdFrom), dayjs(value.createdTo)] : null;

  return (
    <Space size={12} wrap align="center" style={{ marginBottom: 12 }}>
      <FilterOutlined style={{ fontSize: 20, color: 'var(--odap-color-text-secondary)' }} />

      <RangePicker
        value={range}
        allowClear
        presets={RANGE_PRESETS}
        suffixIcon={<CalendarOutlined style={{ fontSize: 16 }} />}
        style={{ width: 240 }}
        aria-label="创建时间范围"
        onChange={(dates) => {
          const from = dates?.[0]?.toISOString();
          const to = dates?.[1]?.toISOString();
          onChange({ ...value, createdFrom: from, createdTo: to });
        }}
      />

      <Select
        mode="multiple"
        allowClear
        placeholder="执行结果"
        aria-label="执行结果"
        style={{ minWidth: 200 }}
        maxTagCount="responsive"
        value={value.results}
        options={RESULT_FILTER_OPTIONS}
        onChange={(results: string[]) => onChange({ ...value, results })}
      />

      {!compact && (
        <Select
          allowClear
          placeholder="来源入口"
          aria-label="来源入口"
          style={{ minWidth: 180 }}
          value={value.entrySource}
          options={ENTRY_SOURCE_OPTIONS}
          onChange={(entrySource?: DecisionEntrySource) => onChange({ ...value, entrySource })}
        />
      )}

      {!compact && (
        <Segmented
          aria-label="置信度区间"
          value={value.confidenceBand}
          options={CONFIDENCE_OPTIONS}
          onChange={(band) =>
            onChange({ ...value, confidenceBand: band as DecisionFilters['confidenceBand'] })
          }
        />
      )}

      <Input
        allowClear
        placeholder="搜索问题或推荐方案"
        aria-label="关键词"
        prefix={<SearchOutlined style={{ fontSize: 16 }} />}
        // 置信度控件在 narrow 场景不在时，把关键词撑宽而不是留空洞
        style={{ width: compact ? 240 : 280 }}
        value={keyword}
        onChange={(e) => handleKeywordChange(e.target.value)}
      />

      <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
        关键词只匹配问题与推荐方案，不搜推理全文
      </Text>
    </Space>
  );
}

export default DecisionFilterBar;
