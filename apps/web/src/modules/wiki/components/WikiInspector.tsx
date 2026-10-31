/**
 * 详情页右侧检查器（SPEC §7 Wiki 详情：版本时间线 / 引用图 / 去重候选）
 */
import { Tabs, Descriptions, Empty } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import type { DedupeCandidate, ReferenceGraph, WikiEntry, WikiVersion } from '../services/wikiTypes';
import type { WikiErrorInfo } from '../services/wikiError';
import type { LoadPhase } from '../stores/wikiStore';
import { VersionTimeline } from './VersionTimeline';
import { ReferenceGraphView } from './ReferenceGraphView';
import { WikiStatusBadge } from './WikiStatusBadge';
import { formatDate, isStale } from '../services/wikiFormat';

export interface WikiInspectorProps {
  entry: WikiEntry;
  versions: WikiVersion[];
  references: ReferenceGraph | null;
  candidates: DedupeCandidate[];
  dedupePhase: LoadPhase;
  dedupeError: WikiErrorInfo | null;
  onOpenCandidate: (candidate: DedupeCandidate) => void;
}

export function WikiInspector({
  entry,
  versions,
  references,
  candidates,
  dedupePhase,
  dedupeError,
  onOpenCandidate,
}: WikiInspectorProps) {
  const properties = (
    <Descriptions column={1} size="small" bordered={false}>
      <Descriptions.Item label="状态">
        <WikiStatusBadge status={entry.status} />
      </Descriptions.Item>
      <Descriptions.Item label="owner">
        <span className="wiki-meta__num">{entry.owner_id}</span>
      </Descriptions.Item>
      <Descriptions.Item label="版本">
        <span className="wiki-meta__num">{entry.version}</span>
      </Descriptions.Item>
      <Descriptions.Item label="最后核验">
        <span style={{ color: isStale(entry.last_verified) ? 'var(--odap-color-warn)' : undefined }}>
          {formatDate(entry.last_verified)}
          {isStale(entry.last_verified) ? ' · STALE' : ''}
        </span>
      </Descriptions.Item>
      <Descriptions.Item label="content_hash">
        <span className="wiki-meta__num" style={{ wordBreak: 'break-all' }}>
          {entry.content_hash.slice(0, 16)}…
        </span>
      </Descriptions.Item>
      <Descriptions.Item label="source_ref">
        <span className="wiki-meta__num">{entry.source_ref ?? '（未与仓库文档绑定）'}</span>
      </Descriptions.Item>
      <Descriptions.Item label="关联概念">
        {entry.concept_refs.length === 0 ? (
          <span className="wiki-meta">未关联 TBox 元素</span>
        ) : (
          entry.concept_refs.map((ref) => (
            <span key={ref} className="wiki-ref-item__ref" style={{ display: 'block' }}>
              {ref}
            </span>
          ))
        )}
      </Descriptions.Item>
    </Descriptions>
  );

  const dedupePanel = (() => {
    if (dedupePhase === 'loading' || dedupePhase === 'idle') {
      return <div className="wiki-skeleton" style={{ height: 80 }} />;
    }
    if (dedupePhase === 'error') {
      return (
        <div role="alert">
          <div className="wiki-state__code">{dedupeError?.errorCode ?? 'DOCS_DEDUPE_UNAVAILABLE'}</div>
          <div className="wiki-state__desc">{dedupeError?.message ?? '去重候选不可用'}</div>
        </div>
      );
    }
    if (candidates.length === 0) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本条目暂无去重候选" />;
    }
    return (
      <div className="wiki-ref-group">
        {candidates.map((candidate) => (
          <button
            key={`${candidate.left_id}-${candidate.right_id}`}
            type="button"
            className="wiki-ref-item"
            style={{ width: '100%', cursor: 'pointer', textAlign: 'left' }}
            onClick={() => onOpenCandidate(candidate)}
          >
            <Icon role="merge" size={20} />
            <span>
              相似度 <span className="wiki-meta__num">{(candidate.similarity * 100).toFixed(1)}%</span>
            </span>
            <span className="wiki-ref-item__ref">{candidate.reason}</span>
          </button>
        ))}
      </div>
    );
  })();

  return (
    <aside className="wiki-inspector" aria-label="条目检查器">
      <Tabs
        size="small"
        items={[
          { key: 'props', label: '属性', children: properties },
          {
            key: 'versions',
            label: `版本 (${versions.length})`,
            children: <VersionTimeline versions={versions} />,
          },
          { key: 'refs', label: '引用', children: <ReferenceGraphView graph={references} /> },
          { key: 'dedupe', label: `去重候选 (${candidates.length})`, children: dedupePanel },
        ]}
      />
    </aside>
  );
}
