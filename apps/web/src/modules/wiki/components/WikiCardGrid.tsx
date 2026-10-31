/**
 * Wiki 列表 —— 卡片视图（同屏信息少于表格，用于快速浏览与扫描）
 */
import { Tooltip } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import type { WikiEntry } from '../services/wikiTypes';
import { formatRelative, isStale } from '../services/wikiFormat';
import { WikiStatusBadge } from './WikiStatusBadge';

export interface WikiCardGridProps {
  entries: WikiEntry[];
  onOpen: (entryId: string) => void;
}

export function WikiCardGrid({ entries, onOpen }: WikiCardGridProps) {
  return (
    <div className="wiki-card-list">
      {entries.map((entry) => (
        <article
          key={entry.id}
          className="wiki-card"
          tabIndex={0}
          role="link"
          aria-label={`打开条目：${entry.title}`}
          onClick={() => onOpen(entry.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onOpen(entry.id);
            }
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <WikiStatusBadge status={entry.status} />
            <span className="wiki-meta__num">{entry.version}</span>
          </div>

          <Tooltip title={entry.title} placement="topLeft">
            <h3 className="wiki-card__title">{entry.title}</h3>
          </Tooltip>

          <div className="wiki-meta">
            <Icon role="owner" size={16} />
            <span className="wiki-meta__num">{entry.owner_id}</span>
            <span aria-hidden="true">·</span>
            <Icon role="date" size={16} />
            <span>{formatRelative(entry.last_verified)}</span>
            {isStale(entry.last_verified) ? (
              <span style={{ color: 'var(--odap-color-warn)' }}>STALE</span>
            ) : null}
          </div>

          {entry.tags.length > 0 ? (
            <div className="wiki-meta">
              <Icon role="tag" size={16} />
              <span>{entry.tags.slice(0, 3).join(' / ')}</span>
              {entry.tags.length > 3 ? <span>+{entry.tags.length - 3}</span> : null}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}
