/**
 * Wiki 列表 —— 表格视图（信息密度 compact，数字用等宽 tabular-nums）
 */
import { Table, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { WikiEntry } from '../services/wikiTypes';
import { formatRelative, isStale } from '../services/wikiFormat';
import { WikiStatusBadge } from './WikiStatusBadge';

export interface WikiTableProps {
  entries: WikiEntry[];
  onOpen: (entryId: string) => void;
}

export function WikiTable({ entries, onOpen }: WikiTableProps) {
  const columns: ColumnsType<WikiEntry> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: { showTitle: false },
      render: (title: string, row) => (
        <Tooltip title={title} placement="topLeft">
          <a
            onClick={(e) => {
              e.preventDefault();
              onOpen(row.id);
            }}
            href={`/wiki/${row.id}`}
            style={{ color: 'var(--odap-color-accent)' }}
          >
            {title}
          </a>
        </Tooltip>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 104,
      render: (status: WikiEntry['status']) => <WikiStatusBadge status={status} />,
    },
    {
      title: 'owner',
      dataIndex: 'owner_id',
      key: 'owner',
      width: 150,
      render: (owner: string) => <span className="wiki-meta__num">{owner}</span>,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 88,
      render: (version: string) => <span className="wiki-meta__num">{version}</span>,
    },
    {
      title: '最后核验',
      dataIndex: 'last_verified',
      key: 'last_verified',
      width: 150,
      render: (iso: string) => {
        const stale = isStale(iso);
        return (
          <Tooltip title={stale ? '超过 180 天未核验，判定为陈旧（STALE）' : iso}>
            <span className="wiki-meta__num" style={{ color: stale ? 'var(--odap-color-warn)' : undefined }}>
              {formatRelative(iso)}
              {stale ? ' · STALE' : ''}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) =>
        tags.length === 0 ? (
          <span className="wiki-meta">无标签</span>
        ) : (
          <>
            {tags.slice(0, 3).map((tag) => (
              <Tag key={tag} style={{ marginInlineEnd: 4 }}>
                {tag}
              </Tag>
            ))}
            {tags.length > 3 ? <span className="wiki-meta">+{tags.length - 3}</span> : null}
          </>
        ),
    },
  ];

  return (
    <Table<WikiEntry>
      rowKey="id"
      size="middle"
      columns={columns}
      dataSource={entries}
      pagination={false}
      scroll={{ x: 880 }}
      onRow={(row) => ({
        onClick: () => onOpen(row.id),
        style: { cursor: 'pointer' },
      })}
    />
  );
}
