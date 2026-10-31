/**
 * 去重合并 —— 左右对照 + 合并动作（SPEC §7 Wiki 去重合并页）
 *
 * 合并语义（SPEC §6 约束）：只置 discard 为 superseded，禁止物理删除。
 * 冲突项用 warn 整块底色 + 图标标注，不使用彩色左边框（绝对禁令 #1）。
 */
import { Alert, Button, Space, Tag } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import type { DedupeCandidate, WikiMergeRequest } from '../services/wikiTypes';
import type { WikiErrorInfo } from '../services/wikiError';

export interface DedupeDiffProps {
  candidate: DedupeCandidate;
  merging: boolean;
  error: WikiErrorInfo | null;
  result: { kept: string; superseded: string } | null;
  onMerge: (req: WikiMergeRequest) => void;
}

export function DedupeDiff({ candidate, merging, error, result, onMerge }: DedupeDiffProps) {
  const sides = [
    { key: 'left' as const, id: candidate.left_id, title: candidate.left_title },
    { key: 'right' as const, id: candidate.right_id, title: candidate.right_title },
  ];

  const submit = (keep: 'left' | 'right') => {
    const keepSide = sides.find((s) => s.key === keep)!;
    const discardSide = sides.find((s) => s.key !== keep)!;
    const fieldChoices = Object.fromEntries(candidate.conflicting_fields.map((f) => [f, keep]));
    onMerge({
      keep_id: keepSide.id,
      discard_id: discardSide.id,
      field_choices: fieldChoices,
      note: `合并 ${discardSide.id} 到 ${keepSide.id}（相似度 ${(candidate.similarity * 100).toFixed(1)}%）`,
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--odap-space-4)' }}>
      <div className="wiki-meta">
        <Icon role="merge" size={20} />
        <span>
          相似度 <span className="wiki-meta__num">{(candidate.similarity * 100).toFixed(1)}%</span>
        </span>
        <span aria-hidden="true">·</span>
        <span>{candidate.reason}</span>
      </div>

      <div className="wiki-diff">
        {sides.map((side) => (
          <section
            key={side.key}
            className={`wiki-diff__col ${candidate.conflicting_fields.length > 0 ? 'wiki-diff__col--conflict' : ''}`}
            aria-label={side.key === 'left' ? '左侧条目' : '右侧条目'}
          >
            <div className="wiki-diff__label">{side.key === 'left' ? '左侧条目' : '右侧条目'}</div>
            <h3 style={{ fontSize: 'var(--odap-font-size-base)', marginBottom: 'var(--odap-space-2)' }}>
              {side.title}
            </h3>
            <div className="wiki-ref-item__ref">{side.id}</div>

            <div style={{ marginTop: 'var(--odap-space-3)' }}>
              {candidate.conflicting_fields.length === 0 ? (
                <div className="wiki-meta">无冲突字段</div>
              ) : (
                candidate.conflicting_fields.map((field) => (
                  <div key={field} className="wiki-diff__field wiki-diff__field--conflict">
                    <Icon role="warning" size={16} />
                    <span>{field}</span>
                    <span className="wiki-ref-item__ref">冲突字段</span>
                  </div>
                ))
              )}
            </div>
          </section>
        ))}
      </div>

      <div className="wiki-meta">
        <Icon role="diff" size={20} />
        <span>content_hash 相同即判重</span>
        <Tag style={{ fontFamily: 'var(--odap-font-mono)' }}>{candidate.content_hash.slice(0, 16)}…</Tag>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          icon={<Icon role="error" size={24} />}
          message={<span className="wiki-state__code">{error.errorCode}</span>}
          description={
            <span>
              {error.message}
              {error.conflictingId ? `（冲突对象 ${error.conflictingId}）` : ''}
              {error.traceId ? ` · trace_id: ${error.traceId}` : ''}
            </span>
          }
        />
      ) : null}

      {result ? (
        <Alert
          type="success"
          showIcon
          icon={<Icon role="success" size={16} />}
          message={`已合并：保留 ${result.kept}，${result.superseded} 置为 superseded（未物理删除）`}
        />
      ) : null}

      <Space wrap>
        <Button
          type="primary"
          loading={merging}
          onClick={() => submit('left')}
          icon={<Icon role="merge" size={20} />}
        >
          确认合并（保留左侧）
        </Button>
        <Button loading={merging} onClick={() => submit('right')}>
          确认合并（保留右侧）
        </Button>
      </Space>
    </div>
  );
}
