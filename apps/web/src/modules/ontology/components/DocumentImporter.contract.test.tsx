/**
 * DocumentImporter 契约测试
 *
 * 该组件此前打的是虚构端点：
 *   POST /api/ontology/documents/import                     （不存在）
 *   POST /api/ontology/documents/{id}/export?format=owl|rdf （不存在）
 * 真实契约（odap/biz/core/ontology/design/model/api/routes.py）：
 *   POST /api/ontology/model/documents                      → CreateDocumentRequest → {id, name}
 *   POST /api/ontology/model/documents/{ontology_id}/export → to_palantir()（无 format 参数）
 *
 * 断言粒度同样是「请求了哪个 URL、带了什么 body」，并含负向断言防止回退到虚构端点。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from '@/modules/shared/services/apiClient';

const api = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

import DocumentImporter from './DocumentImporter';

const SAMPLE_DOC = {
  id: 'doc-42',
  name: '制造本体',
  version: '1.2.0',
  object_types: [{ name: 'Order' }, { name: 'Part' }],
  action_types: [{ name: 'Ship' }],
  relations: [{ name: 'order_contains_part' }],
  metadata: { owner: 'mfg' },
  // 多余字段必须被裁掉，不能透传给 Pydantic
  unknown_field: 'should-be-dropped',
};

/** 通过隐藏的 input[type=file] 喂一个 JSON 文件给 Upload
 *
 * jsdom 的 `input.files` 是只读 getter，`fireEvent.change(..., {target:{files}})` 会静默失败，
 * 导致 rc-upload 收不到文件。必须用 defineProperty 直接写入后再派发 change。
 */
function setInputFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, 'files', { value: files, configurable: true });
  fireEvent.change(input);
}

async function uploadJson(payload: unknown) {
  const file = new File([JSON.stringify(payload)], 'ontology.json', { type: 'application/json' });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input).toBeTruthy();
  setInputFiles(input, [file]);
  await waitFor(() => expect(screen.getByText('制造本体')).toBeInTheDocument(), { timeout: 4000 });
}

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  // 导出走 a.click() + createObjectURL，jsdom 未实现导航与 blob URL
  Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(() => 'blob:mock'), configurable: true });
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

describe('DocumentImporter — 本体文档导入导出', () => {
  it('文件解析后展示预览统计（对象类型/动作类型/关系）', async () => {
    render(<DocumentImporter />);
    await uploadJson(SAMPLE_DOC);

    expect(screen.getByText('Order')).toBeInTheDocument();
    expect(screen.getByText('Part')).toBeInTheDocument();
    expect(screen.getByText('order_contains_part')).toBeInTheDocument();
    expect(screen.getByText('1.2.0')).toBeInTheDocument();
  });

  it('导入走真实端点并裁剪未知字段', async () => {
    api.post.mockResolvedValue({ id: 'server-side-id', name: '制造本体' });
    render(<DocumentImporter />);
    await uploadJson(SAMPLE_DOC);

    fireEvent.click(screen.getByRole('button', { name: /导入为新文档|Import as new document/ }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, body] = api.post.mock.calls[0];
    expect(String(url)).toContain('/api/ontology/model/documents');
    expect(String(url)).not.toContain('/documents/import');
    expect(body).toEqual({
      id: 'doc-42',
      name: '制造本体',
      version: '1.2.0',
      object_types: SAMPLE_DOC.object_types,
      action_types: SAMPLE_DOC.action_types,
      relations: SAMPLE_DOC.relations,
      metadata: SAMPLE_DOC.metadata,
    });
    expect(body).not.toHaveProperty('unknown_field');
  });

  it('导入成功后导出目标切换为服务端返回的 id', async () => {
    api.post.mockResolvedValueOnce({ id: 'server-side-id', name: '制造本体' });
    render(<DocumentImporter />);
    await uploadJson(SAMPLE_DOC);

    fireEvent.click(screen.getByRole('button', { name: /导入为新文档|Import as new document/ }));
    await waitFor(() => expect(screen.getByText(/server-side-id/)).toBeInTheDocument());

    api.post.mockResolvedValueOnce({ objectTypes: [] });
    fireEvent.click(screen.getByRole('button', { name: /导出 JSON|Export JSON/ }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));
    expect(String(api.post.mock.calls[1][0]).endsWith('/api/ontology/model/documents/server-side-id/export')).toBe(true);
    // 负向：不得再出现 query 形式的 format 参数
    expect(String(api.post.mock.calls[1][0])).not.toContain('format=');
  });

  it('未选文件但给了 ontologyId 时可直接导出当前本体', async () => {
    api.post.mockResolvedValue({});
    render(<DocumentImporter ontologyId="current-onto" />);

    const exportBtn = screen.getByRole('button', { name: /导出 JSON|Export JSON/ });
    expect(exportBtn).toBeEnabled();
    fireEvent.click(exportBtn);

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(String(api.post.mock.calls[0][0]).endsWith('/api/ontology/model/documents/current-onto/export')).toBe(true);
  });

  it('既无文件也无 ontologyId 时导出按钮禁用', () => {
    render(<DocumentImporter />);
    expect(screen.getByRole('button', { name: /导出 JSON|Export JSON/ })).toBeDisabled();
  });

  it('非法 JSON 暴露具体解析错误，而不是笼统失败', async () => {
    render(<DocumentImporter />);
    const file = new File(['{ not json'], 'bad.json', { type: 'application/json' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    setInputFiles(input, [file]);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument(), { timeout: 4000 });
    expect(screen.getByRole('alert').textContent).toMatch(/文件解析失败/);
    expect(screen.getByRole('alert').textContent).not.toBe('文件解析失败');
    expect(api.post).not.toHaveBeenCalled();
  });
});
