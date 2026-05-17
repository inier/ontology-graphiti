import { Button, Select, Input, Dropdown, Space, Tooltip, Switch } from 'antd';
import { ReloadOutlined, FilterOutlined } from '@ant-design/icons';
import { LAYOUT_OPTIONS } from './constants';
import type { LayoutType } from './constants';

interface GraphToolbarProps {
  onRefresh?: () => void;
  layout: LayoutType;
  onLayoutChange: (layout: LayoutType) => void;
  searchText: string;
  onSearchChange: (text: string) => void;
  filterType: string;
  onFilterChange: (type: string) => void;
  entityTypes: string[];
  versions?: Array<{ version_id: string; created_at: string; entity_count: number; relation_count: number; commit_message?: string; event_count?: number }>;
  currentVersion?: string;
  onVersionChange?: (versionId: string) => void;
  versionsLoading?: boolean;
  showAudit: boolean;
  onShowAuditChange: (val: boolean) => void;
}

export function GraphToolbar({
  onRefresh,
  layout,
  onLayoutChange,
  searchText,
  onSearchChange,
  filterType,
  onFilterChange,
  entityTypes,
  versions,
  currentVersion,
  onVersionChange,
  versionsLoading,
  showAudit,
  onShowAuditChange,
}: GraphToolbarProps) {
  const filterItems = [
    { key: 'all', label: '显示全部', onClick: () => onFilterChange('all') },
    ...entityTypes.map((t) => ({
      key: t,
      label: t,
      onClick: () => onFilterChange(t),
    })),
  ];

  return (
    <Space wrap>
      <Dropdown menu={{ items: filterItems }}>
        <Button icon={<FilterOutlined />}>
          {filterType === 'all' ? '筛选' : `类型: ${filterType}`}
        </Button>
      </Dropdown>

      <Select
        value={layout}
        onChange={onLayoutChange}
        options={[...LAYOUT_OPTIONS]}
        style={{ width: 100 }}
      />

      <Input.Search
        placeholder="搜索实体"
        value={searchText}
        onChange={(e) => onSearchChange(e.target.value)}
        style={{ width: 160 }}
        allowClear
      />

      {versions && onVersionChange && (
        <Select
          value={currentVersion}
          onChange={onVersionChange}
          options={[
            { value: 'latest', label: '最新版本' },
            ...versions.map((v) => {
              const date = v.created_at
                ? new Date(v.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
                : '';
              const msg = v.commit_message || v.version_id.slice(0, 8);
              const counts = `${v.entity_count || 0}E/${v.relation_count || 0}R`;
              return {
                value: v.version_id,
                label: `${msg} (${date}) [${counts}]`,
              };
            }),
          ]}
          style={{ width: 200 }}
          size="small"
          loading={versionsLoading}
          placeholder="本体版本"
        />
      )}

      <Tooltip title={showAudit ? '隐藏审计实体' : '显示审计实体'}>
        <Space size={4} style={{ cursor: 'pointer' }} onClick={() => onShowAuditChange(!showAudit)}>
          <Switch size="small" checked={showAudit} onChange={onShowAuditChange} />
          <span style={{ fontSize: 12, color: '#666' }}>审计</span>
        </Space>
      </Tooltip>

      <Button icon={<ReloadOutlined />} onClick={() => onRefresh?.()}>
        刷新
      </Button>
    </Space>
  );
}