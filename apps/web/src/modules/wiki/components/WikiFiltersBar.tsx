/**
 * 列表筛选器 + 视图切换（表/卡双视图，SPEC §7 Wiki 列表页）
 */
import { Button, Input, Segmented, Select, Tooltip } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import type { WikiEntryStatus } from '../services/wikiTypes';
import type { WikiFilters } from '../stores/wikiStore';
import { WIKI_STATUS_OPTIONS } from './wikiStatusMeta';

export type WikiViewMode = 'table' | 'card';

export interface WikiFiltersProps {
  filters: WikiFilters;
  view: WikiViewMode;
  onChange: (patch: Partial<WikiFilters>) => void;
  onViewChange: (view: WikiViewMode) => void;
  onRefresh: () => void;
  disabled?: boolean;
}

export function WikiFiltersBar({
  filters,
  view,
  onChange,
  onViewChange,
  onRefresh,
  disabled = false,
}: WikiFiltersProps) {
  return (
    <div className="wiki-toolbar">
      <Input
        allowClear
        value={filters.keyword}
        onChange={(e) => onChange({ keyword: e.target.value })}
        placeholder="搜索标题，如：退货率 / 语义缺口"
        prefix={<Icon role="search" size={16} />}
        style={{ width: 260 }}
        aria-label="按标题搜索 Wiki 条目"
      />

      <Select
        value={filters.status}
        onChange={(value: WikiEntryStatus | 'all') => onChange({ status: value })}
        options={WIKI_STATUS_OPTIONS}
        style={{ width: 140 }}
        aria-label="按状态筛选"
      />

      <Input
        allowClear
        value={filters.owner}
        onChange={(e) => onChange({ owner: e.target.value })}
        placeholder="owner_id，如 u-arch-zhang"
        prefix={<Icon role="owner" size={16} />}
        style={{ width: 220 }}
        aria-label="按 owner 筛选"
      />

      <Input
        allowClear
        value={filters.tag}
        onChange={(e) => onChange({ tag: e.target.value })}
        placeholder="标签，如 指标口径"
        prefix={<Icon role="tag" size={16} />}
        style={{ width: 180 }}
        aria-label="按标签筛选"
      />

      <span className="wiki-toolbar__spacer" />

      <Segmented
        value={view}
        onChange={(value) => onViewChange(value as WikiViewMode)}
        options={[
          { value: 'table', label: '表格', icon: <Icon role="viewTable" size={16} /> },
          { value: 'card', label: '卡片', icon: <Icon role="viewCard" size={16} /> },
        ]}
      />

      <Tooltip title="重新拉取列表">
        <Button onClick={onRefresh} disabled={disabled} icon={<Icon role="retry" size={16} />}>
          刷新
        </Button>
      </Tooltip>
    </div>
  );
}
