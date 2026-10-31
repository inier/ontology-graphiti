/**
 * Wiki 详情页（/wiki/:entryId）
 *
 * 阅读器 + 右侧检查器（属性 / 版本时间线 / 引用关系 / 去重候选）。
 */
import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Tag } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import { useWikiStore } from '../stores/wikiStore';
import { WIKI_API_MOCK } from '../services/wikiApi';
import { WikiStateBlock } from '../components/WikiStateBlock';
import { WikiReader } from '../components/WikiReader';
import { WikiInspector } from '../components/WikiInspector';
import { WikiStatusBadge } from '../components/WikiStatusBadge';
import type { DedupeCandidate } from '../services/wikiTypes';
import '../wiki.css';

export function WikiEntryPage() {
  const { entryId = '' } = useParams<{ entryId: string }>();
  const navigate = useNavigate();
  const {
    detailPhase,
    entry,
    content,
    versions,
    references,
    detailError,
    candidates,
    dedupePhase,
    dedupeError,
    fetchDetail,
    fetchDedupe,
    resetDetail,
    setActiveCandidate,
  } = useWikiStore();

  useEffect(() => {
    void fetchDetail(entryId);
    void fetchDedupe();
    return () => resetDetail();
  }, [entryId, fetchDetail, fetchDedupe, resetDetail]);

  const relatedCandidates: DedupeCandidate[] = candidates.filter(
    (c) => c.left_id === entryId || c.right_id === entryId,
  );

  const openCandidate = (candidate: DedupeCandidate) => {
    const index = candidates.findIndex(
      (c) => c.left_id === candidate.left_id && c.right_id === candidate.right_id,
    );
    setActiveCandidate(index >= 0 ? index : null);
    navigate('/wiki/dedupe');
  };

  return (
    <div className="wiki-page">
      <div className="wiki-toolbar">
        <Button
          type="text"
          icon={<Icon role="chevronLeft" size={16} />}
          onClick={() => navigate('/wiki')}
        >
          返回列表
        </Button>
        <span className="wiki-toolbar__spacer" />
        {entry ? <WikiStatusBadge status={entry.status} /> : null}
        {entry ? <Tag style={{ fontFamily: 'var(--odap-font-mono)' }}>v{entry.version}</Tag> : null}
      </div>

      {WIKI_API_MOCK ? (
        <div className="wiki-banner" role="status">
          <Icon role="warning" size={16} />
          <span>演示数据（mock 开关开启）。正文与版本快照来自 services/wikiMock.ts。</span>
        </div>
      ) : null}

      <WikiStateBlock
        phase={detailPhase}
        error={detailError}
        emptyTitle="条目内容为空"
        emptyDesc="后端返回了空的 wiki_versions.content，请检查该条目的版本快照是否已写入。"
        isEmpty={detailPhase === 'ready' && !entry}
        onRetry={() => void fetchDetail(entryId)}
        skeletonCount={2}
      >
        {entry ? (
          <div className="wiki-grid wiki-grid--split">
            <article>
              <header style={{ marginBottom: 'var(--odap-space-3)' }}>
                <h1
                  style={{
                    fontSize: 'var(--odap-font-size-3xl)',
                    letterSpacing: 'var(--odap-tracking-tight)',
                    lineHeight: 'var(--odap-leading-tight)',
                  }}
                >
                  {entry.title}
                </h1>
                <div className="wiki-meta" style={{ marginTop: 'var(--odap-space-2)' }}>
                  <Icon role="owner" size={16} />
                  <span className="wiki-meta__num">{entry.owner_id}</span>
                  <span aria-hidden="true">·</span>
                  <span className="wiki-ref-item__ref">{entry.id}</span>
                </div>
              </header>
              <WikiReader content={content} title={entry.title} />
            </article>

            <WikiInspector
              entry={entry}
              versions={versions}
              references={references}
              candidates={relatedCandidates}
              dedupePhase={dedupePhase}
              dedupeError={dedupeError}
              onOpenCandidate={openCandidate}
            />
          </div>
        ) : null}
      </WikiStateBlock>
    </div>
  );
}
