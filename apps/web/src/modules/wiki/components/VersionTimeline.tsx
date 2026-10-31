/**
 * 版本时间线（AC-05：按 created_at DESC，含 change_note）
 *
 * 竖向时间线，节点为图标 + 连线的 1px 细线，不使用彩色侧条纹。
 */
import { Icon } from '@/modules/shared/components/Icon';
import type { WikiVersion } from '../services/wikiTypes';
import { formatDate, formatRelative } from '../services/wikiFormat';

export interface VersionTimelineProps {
  versions: WikiVersion[];
}

export function VersionTimeline({ versions }: VersionTimelineProps) {
  if (versions.length === 0) {
    return <div className="wiki-meta">该条目尚无版本快照。</div>;
  }

  return (
    <ol className="wiki-timeline" aria-label="版本时间线">
      {versions.map((version, index) => (
        <li key={version.id} className="wiki-timeline__item">
          <div className="wiki-timeline__rail">
            <Icon role="ontologyVersion" size={16} />
            {index < versions.length - 1 ? <span className="wiki-timeline__line" aria-hidden="true" /> : null}
          </div>
          <div>
            <div className="wiki-timeline__version">
              {version.version}
              <span className="wiki-meta" style={{ marginLeft: 8 }}>
                {formatRelative(version.created_at)} · {formatDate(version.created_at)}
              </span>
            </div>
            <div className="wiki-timeline__note">{version.change_note}</div>
            <div className="wiki-meta">
              <Icon role="owner" size={16} />
              <span className="wiki-meta__num">{version.author_id}</span>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
