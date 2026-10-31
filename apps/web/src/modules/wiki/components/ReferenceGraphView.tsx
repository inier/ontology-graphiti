/**
 * 引用关系视图（AC-06：outgoing[] + incoming[]，每条含 kind 与 ref）
 *
 * 用列表呈现而非图形库：本轮禁止引入新图库（SPEC §4 已锁定 3 套渲染栈），
 * 引用关系是「少量条目 + 强语义」，列表比画布更可读、可键盘遍历。
 */
import { Icon } from '@/modules/shared/components/Icon';
import type { CitationKind, CitationRef, ReferenceGraph } from '../services/wikiTypes';
import type { IconRole } from '@/modules/shared/components/Icon';

const KIND_META: Record<CitationKind, { label: string; role: IconRole }> = {
  doc: { label: '文档', role: 'document' },
  tbox_node: { label: '本体节点', role: 'objectType' },
  metric: { label: '指标', role: 'metric' },
  graph_edge: { label: '图谱边', role: 'linkType' },
  opa_decision: { label: 'OPA 决策', role: 'rule' },
};

function RefList({ title, refs }: { title: string; refs: CitationRef[] }) {
  return (
    <div className="wiki-ref-group">
      <div className="wiki-ref-group__title">
        {title}（{refs.length}）
      </div>
      {refs.length === 0 ? (
        <div className="wiki-meta">无</div>
      ) : (
        refs.map((ref) => {
          const meta = KIND_META[ref.kind] ?? { label: ref.kind, role: 'document' as IconRole };
          return (
            <div key={`${ref.kind}:${ref.ref}`} className="wiki-ref-item">
              <Icon role={meta.role} size={16} />
              <span>{ref.label}</span>
              <span className="wiki-ref-item__ref">
                {meta.label} · {ref.ref}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}

export function ReferenceGraphView({ graph }: { graph: ReferenceGraph | null }) {
  if (!graph) {
    return <div className="wiki-meta">尚未加载引用关系。</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--odap-space-4)' }}>
      <RefList title="出向引用" refs={graph.outgoing} />
      <RefList title="入向引用" refs={graph.incoming} />
    </div>
  );
}
