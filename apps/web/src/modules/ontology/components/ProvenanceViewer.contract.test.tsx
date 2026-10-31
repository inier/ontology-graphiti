/**
 * ProvenanceViewer 契约测试 —— 抽取溯源
 *
 * 真实契约：
 *   GET /api/extraction/provenance/{entity_id}
 *       → { status: "ok", provenance: <extraction_provenance 行> }
 *   GET /api/extraction/provenance/by-source/{doc_id}
 *       → { status: "ok", entities: [...] }
 *
 * 表列（provenance_tracker.py 的 CREATE TABLE）：
 *   provenance_id / entity_id / entity_type / session_id / source_doc_id /
 *   vector_chunk_id / doc_fragment_id / extraction_method / he_template_version /
 *   source_template / confidence_score / timestamp
 *
 * 旧实现的三处硬伤，逐个钉：
 *  ① 读 `confidence`（真实是 `confidence_score`）→ 置信度永远不显示；
 *  ② 读 `source_doc_name`（后端无此列）；
 *  ③ `useState(() => { if (visible) load() })` 当 effect 用 → 首次 visible=false
 *     就永不加载，抽屉打开是空白。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  const t = (key: string, opts?: Record<string, unknown>) =>
    opts && Object.keys(opts).length ? `${key}|${JSON.stringify(opts)}` : key;
  return { useI18n: () => ({ t }) };
});

type Call = { url: string };
const calls: Call[] = [];

const RECORD = {
  provenance_id: 'pv-1',
  entity_id: 'e-1',
  entity_type: 'Customer',
  session_id: 'sess-9',
  source_doc_id: 'doc-77',
  vector_chunk_id: 'chunk-3',
  doc_fragment_id: 'frag-5',
  extraction_method: 'he_template',
  he_template_version: 'v2.1',
  source_template: 'general/graph',
  confidence_score: 0.92,
  timestamp: '2026-10-20T08:00:00Z',
};

const SIBLINGS = [
  { entity_id: 'e-1', entity_type: 'Customer', extraction_method: 'he_template', confidence_score: 0.92 },
  { entity_id: 'e-2', entity_type: 'Order', extraction_method: 'he_template', confidence_score: 0.77 },
];

let provenanceStatus = 200;

const getMock = vi.fn(async (url: string) => {
  calls.push({ url });
  if (url === '/api/extraction/provenance/e-1') {
    if (provenanceStatus === 404) {
      throw Object.assign(new Error('HTTP 404'), { status: 404, detail: 'Provenance not found' });
    }
    return { status: 'ok', provenance: RECORD };
  }
  if (url === '/api/extraction/provenance/by-source/doc-77') {
    return { status: 'ok', entities: SIBLINGS };
  }
  throw new Error(`unexpected GET ${url}`);
});

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (url: string) => getMock(url),
    post: () => Promise.reject(new Error('ProvenanceViewer 不应 POST')),
  },
}));

import { ProvenanceViewer } from './ProvenanceViewer';

const urls = () => calls.map((c) => c.url);

beforeEach(() => {
  calls.length = 0;
  provenanceStatus = 200;
  getMock.mockClear();
});

describe('ProvenanceViewer — 抽取溯源', () => {
  it('未打开抽屉时不发请求', async () => {
    render(<ProvenanceViewer entityId="e-1" visible={false} onClose={() => {}} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(urls()).toHaveLength(0);
  });

  it('打开抽屉即加载（旧实现用 useState 冒充 effect，打开是空白）', async () => {
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() => expect(urls()).toContain('/api/extraction/provenance/e-1'));
    await waitFor(() => expect(screen.getByText('Customer')).toBeTruthy());
  });

  it('置信度读 confidence_score（不是 confidence）：0.92 显示为 92.0%', async () => {
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText('92.0%')).toBeTruthy());
    expect(document.body.textContent).not.toContain('NaN');
  });

  it('展示 source_template 与 he_template_version（模板溯源的真实两列）', async () => {
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText('general/graph')).toBeTruthy());
    expect(screen.getByText('v2.1')).toBeTruthy();
    // 负向：后端没有 source_doc_name 这一列，不得出现「undefined」占位
    expect(document.body.textContent).not.toContain('undefined');
  });

  it('来源文档用 source_doc_id，不做 source_doc_name 回退', async () => {
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText('doc-77')).toBeTruthy());
  });

  it('404 时给出「没有溯源记录」而不是笼统失败', async () => {
    provenanceStatus = 404;
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() =>
      expect(screen.getByText('该实体没有溯源记录（抽取时可能未开启溯源追踪）')).toBeTruthy(),
    );
    expect(screen.getByText('Provenance not found')).toBeTruthy();
  });

  it('失败后「重试」重新发起请求（setLoadToken 必须真的接在按钮上，不能是死变量）', async () => {
    provenanceStatus = 404;
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText('Provenance not found')).toBeTruthy());
    expect(urls().filter((u) => u === '/api/extraction/provenance/e-1')).toHaveLength(1);

    // 后端恢复：只让下一次请求成功，验证确实是重试打出去的
    getMock.mockImplementationOnce(async (url: string) => {
      calls.push({ url });
      return { status: 'ok', provenance: RECORD };
    });

    // AntD 会在两个汉字之间自动插空格（「重 试」），断言需容错
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }));

    await waitFor(() =>
      expect(urls().filter((u) => u === '/api/extraction/provenance/e-1')).toHaveLength(2),
    );
    // 重试成功后错误横幅消失、正常内容渲染
    await waitFor(() => expect(screen.getByText('92.0%')).toBeTruthy());
    expect(screen.queryByText('Provenance not found')).toBeNull();
  });

  it('「查看同源实体」走 by-source 端点并列出结果（替代旧的「待实现」按钮）', async () => {
    render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText('doc-77')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /查看同源实体/ }));

    await waitFor(() => expect(urls()).toContain('/api/extraction/provenance/by-source/doc-77'));
    await waitFor(() => expect(screen.getByText('e-2')).toBeTruthy());
    expect(screen.getByText('Order')).toBeTruthy();
  });

  it('entityId 变化会重新拉取（token 驱动的 loading 不能漏掉这次变化）', async () => {
    const { rerender } = render(<ProvenanceViewer entityId="e-1" visible onClose={() => {}} />);
    await waitFor(() => expect(urls()).toContain('/api/extraction/provenance/e-1'));

    getMock.mockImplementationOnce(async (url: string) => {
      calls.push({ url });
      return { status: 'ok', provenance: { ...RECORD, entity_id: 'e-2', confidence_score: 0.5 } };
    });
    rerender(<ProvenanceViewer entityId="e-2" visible onClose={() => {}} />);

    await waitFor(() => expect(urls()).toContain('/api/extraction/provenance/e-2'));
    await waitFor(() => expect(screen.getByText('50.0%')).toBeTruthy());
  });
});
