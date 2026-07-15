import { useMemo } from 'react';
import { Tag, Collapse, Empty, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AdvancedTable } from '@/modules/shared';

export interface VersionDiffViewProps {
  diffData: Record<string, unknown> | null;
  versionA: string;
  versionB: string;
}

/* ── Diff item types ──────────────────────────────────────────────── */

interface DiffItem {
  key: string;
  name: string;
  changeType: 'added' | 'modified' | 'deleted';
  details?: string;
}

interface CategoryDiff {
  label: string;
  items: DiffItem[];
}

/* ── Color mapping ────────────────────────────────────────────────── */

const CHANGE_COLORS: Record<string, string> = {
  added: 'green',
  modified: 'gold',
  deleted: 'red',
};

const CHANGE_LABELS: Record<string, string> = {
  added: '新增',
  modified: '修改',
  deleted: '删除',
};

/* ── Helper: extract diff items from a category ───────────────────── */

function extractDiffItems(
  categoryData: unknown,
  categoryKey: string,
): DiffItem[] {
  if (!categoryData || typeof categoryData !== 'object') return [];
  const data = categoryData as Record<string, unknown>;
  const items: DiffItem[] = [];

  // Handle added items (string[] or object[])
  const added = data.added || data[`${categoryKey}_added`];
  if (Array.isArray(added)) {
    added.forEach((item: unknown, idx: number) => {
      if (typeof item === 'string') {
        items.push({ key: `added-${idx}`, name: item, changeType: 'added' });
      } else if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>;
        items.push({
          key: `added-${idx}`,
          name: (obj.name as string) || (obj.display_name as string) || `Item ${idx + 1}`,
          changeType: 'added',
          details: obj.description ? String(obj.description) : undefined,
        });
      }
    });
  }

  // Handle deleted items (string[] or object[])
  const deleted = data.deleted || data.removed || data[`${categoryKey}_deleted`];
  if (Array.isArray(deleted)) {
    deleted.forEach((item: unknown, idx: number) => {
      if (typeof item === 'string') {
        items.push({ key: `deleted-${idx}`, name: item, changeType: 'deleted' });
      } else if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>;
        items.push({
          key: `deleted-${idx}`,
          name: (obj.name as string) || (obj.display_name as string) || `Item ${idx + 1}`,
          changeType: 'deleted',
          details: obj.description ? String(obj.description) : undefined,
        });
      }
    });
  }

  // Handle modified items (object[] with changes field)
  const modified = data.modified || data[`${categoryKey}_modified`];
  if (Array.isArray(modified)) {
    modified.forEach((item: unknown, idx: number) => {
      if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>;
        const changes = obj.changes as Array<Record<string, unknown>> | undefined;
        const detailStr = changes
          ? changes.map((c) => `${c.field || c.property}: ${String(c.old_value ?? '')} -> ${String(c.new_value ?? '')}`).join('; ')
          : undefined;
        items.push({
          key: `modified-${idx}`,
          name: (obj.name as string) || (obj.type_name as string) || (obj.display_name as string) || `Item ${idx + 1}`,
          changeType: 'modified',
          details: detailStr,
        });
      }
    });
  }

  return items;
}

/* ── Category definitions ─────────────────────────────────────────── */

const CATEGORY_KEYS: Array<{ key: string; label: string }> = [
  { key: 'object_types', label: '对象类型' },
  { key: 'link_types', label: '关系类型' },
  { key: 'action_types', label: '动作类型' },
  { key: 'process_types', label: '业务过程' },
  { key: 'rule_types', label: '规则类型' },
  { key: 'function_types', label: '逻辑函数' },
  { key: 'indicator_types', label: '指标类型' },
];

/* ── Main Component ───────────────────────────────────────────────── */

export function VersionDiffView({ diffData, versionA, versionB }: VersionDiffViewProps) {
  const categories = useMemo<CategoryDiff[]>(() => {
    if (!diffData) return [];

    return CATEGORY_KEYS.map(({ key, label }) => {
      // Try both nested and flat key patterns
      const categoryData = diffData[key] || diffData;
      const items = extractDiffItems(categoryData, key);
      return { label, items };
    }).filter((cat) => cat.items.length > 0);
  }, [diffData]);

  const columns: ColumnsType<DiffItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: '35%',
      render: (text: string, record: DiffItem) => (
        <span style={{
          color: record.changeType === 'deleted' ? '#cf1322' :
                 record.changeType === 'added' ? '#389e0d' : '#d48806',
        }}>
          {text}
        </span>
      ),
    },
    {
      title: '变更类型',
      dataIndex: 'changeType',
      key: 'changeType',
      width: '20%',
      render: (type: string) => (
        <Tag color={CHANGE_COLORS[type]}>{CHANGE_LABELS[type]}</Tag>
      ),
    },
    {
      title: '变更详情',
      dataIndex: 'details',
      key: 'details',
      width: '45%',
      render: (text: string) => text || '-',
    },
  ];

  if (!diffData) {
    return <Empty description="请选择两个版本进行对比" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  if (categories.length === 0) {
    return <Empty description="两个版本之间无差异" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  // Summary stats
  const totalAdded = categories.reduce((sum, cat) => sum + cat.items.filter((i) => i.changeType === 'added').length, 0);
  const totalModified = categories.reduce((sum, cat) => sum + cat.items.filter((i) => i.changeType === 'modified').length, 0);
  const totalDeleted = categories.reduce((sum, cat) => sum + cat.items.filter((i) => i.changeType === 'deleted').length, 0);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <span style={{ fontWeight: 500 }}>
            v{versionA} → v{versionB} 差异对比
          </span>
          <Tag color="green">+{totalAdded} 新增</Tag>
          <Tag color="gold">~{totalModified} 修改</Tag>
          <Tag color="red">-{totalDeleted} 删除</Tag>
        </Space>
      </div>

      <Collapse
        defaultActiveKey={categories.map((_, idx) => String(idx))}
        items={categories.map((category, idx) => ({
          key: String(idx),
          label: (
            <Space>
              <span>{category.label}</span>
              <Tag color="green">{category.items.filter((i) => i.changeType === 'added').length} 新增</Tag>
              <Tag color="gold">{category.items.filter((i) => i.changeType === 'modified').length} 修改</Tag>
              <Tag color="red">{category.items.filter((i) => i.changeType === 'deleted').length} 删除</Tag>
            </Space>
          ),
          children: (
            <AdvancedTable<DiffItem>
              dataSource={category.items}
              columns={columns}
              size="small"
              pagination={false}
              rowKey="key"
            />
          ),
        }))}
      />
    </div>
  );
}
