/**
 * Wiki 去重合并页（/wiki/dedupe）
 *
 * 候选列表 + 左右对照 diff + 合并动作（合并只置 superseded）。
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Empty } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import { useWikiStore } from '../stores/wikiStore';
import { WIKI_API_MOCK } from '../services/wikiApi';
import { WikiStateBlock } from '../components/WikiStateBlock';
import { DedupeDiff } from '../components/DedupeDiff';
import '../wiki.css';

export function WikiDedupePage() {
  const navigate = useNavigate();
  const {
    dedupePhase,
    candidates,
    dedupeError,
    activeIndex,
    merging,
    mergeError,
    mergeResult,
    fetchDedupe,
    setActiveCandidate,
    merge,
  } = useWikiStore();

  useEffect(() => {
    void fetchDedupe();
  }, [fetchDedupe]);

  const active = activeIndex !== null ? candidates[activeIndex] ?? null : null;

  return (
    <div className="wiki-page">
      <header>
        <h1 style={{ fontSize: 'var(--odap-font-size-3xl)', letterSpacing: 'var(--odap-tracking-tight)' }}>
          去重合并
        </h1>
        <p style={{ color: 'var(--odap-color-fg-secondary)', marginTop: 'var(--odap-space-1)' }}>
          content_hash 相同或段落高度重合的条目作为合并候选。合并只把被丢弃一侧置为 superseded 并保留全部版本，
          不执行物理删除。
        </p>
      </header>

      {WIKI_API_MOCK ? (
        <div className="wiki-banner" role="status">
          <Icon role="warning" size={16} />
          <span>演示数据（mock 开关开启）。候选来自 GET /api/v1/docs/governance/dedupe 的 mock 实现。</span>
        </div>
      ) : null}

      <div className="wiki-toolbar">
        <Button
          type="text"
          icon={<Icon role="chevronLeft" size={16} />}
          onClick={() => navigate('/wiki')}
        >
          返回列表
        </Button>
        <span className="wiki-toolbar__spacer" />
        <Button onClick={() => void fetchDedupe()} icon={<Icon role="retry" size={16} />}>
          重新计算候选
        </Button>
      </div>

      <WikiStateBlock
        phase={dedupePhase}
        error={dedupeError}
        isEmpty={dedupePhase === 'ready' && candidates.length === 0}
        emptyTitle="当前没有需要合并的条目"
        emptyDesc="系统未发现 content_hash 相同或段落高度重合的条目。若刚导入新文档，可先执行文档治理校验再回来。"
        onRetry={() => void fetchDedupe()}
        skeletonCount={2}
      >
        <div className="wiki-grid wiki-grid--split">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--odap-space-4)' }}>
            {active ? (
              <DedupeDiff
                key={`${active.left_id}-${active.right_id}`}
                candidate={active}
                merging={merging}
                error={mergeError}
                result={mergeResult}
                onMerge={(req) => void merge(req)}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请从右侧候选列表选择一组条目" />
            )}
          </div>

          <aside className="wiki-inspector" aria-label="合并候选列表">
            <div className="wiki-ref-group__title">候选（{candidates.length}）</div>
            <div className="wiki-ref-group">
              {candidates.map((candidate, index) => (
                <button
                  key={`${candidate.left_id}-${candidate.right_id}`}
                  type="button"
                  className="wiki-ref-item"
                  aria-current={index === activeIndex}
                  style={{
                    width: '100%',
                    cursor: 'pointer',
                    textAlign: 'left',
                    borderColor:
                      index === activeIndex ? 'var(--odap-color-accent)' : 'var(--odap-color-border-subtle)',
                    background:
                      index === activeIndex ? 'var(--odap-color-accent-subtle)' : 'var(--odap-color-bg-subtle)',
                  }}
                  onClick={() => setActiveCandidate(index)}
                >
                  <Icon role="diff" size={20} />
                  <span className="wiki-meta__num">{(candidate.similarity * 100).toFixed(1)}%</span>
                  <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {candidate.left_title}
                  </span>
                </button>
              ))}
            </div>
          </aside>
        </div>
      </WikiStateBlock>
    </div>
  );
}
