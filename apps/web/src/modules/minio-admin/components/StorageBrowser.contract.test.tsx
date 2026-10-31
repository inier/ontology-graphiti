/**
 * StorageBrowser 契约测试 —— 对象存储浏览
 *
 * 这个组件的存在前提是：后端 7 个 `/api/minio-admin/*` 端点全部实现且已注册，
 * 前端 service 7 个方法也全部写好，但页面上只有 iframe + 关于两个页签 ——
 * **service 从未被任何 UI 消费**。这里把这个漏洞钉住。
 *
 * 契约细节（易错点，逐条断言）：
 *  · `GET /buckets` **直接返回数组**，不是 `{ buckets: [...] }`；
 *  · `GET /objects` 的查询参数是 bucket / prefix / page / page_size；
 *  · `DELETE /objects` 用 query 传 bucket 与 key，不是路径段；
 *  · 非管理员在 `/objects` 上是 403 且带明确 detail，必须原样透出。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  const t = (key: string, opts?: Record<string, unknown>) =>
    opts && Object.keys(opts).length ? `${key}|${JSON.stringify(opts)}` : key;
  return { useI18n: () => ({ t }) };
});

type Call = { method: string; url: string };
const calls: Call[] = [];

const BUCKETS = [
  { name: 'odap-documents', display_name: '文档库', description: '', object_count: 3, total_size: 1024, total_size_display: '1.0 KB' },
  { name: 'odap-assets', display_name: '素材库', description: '', object_count: 1, total_size: 2048, total_size_display: '2.0 KB' },
];

const ROOT_OBJECTS = {
  bucket: 'odap-documents',
  prefix: '',
  items: [
    { name: 'reports/', display_name: 'reports', size: 0, size_display: '0 B', content_type: '', is_dir: true },
    { name: 'readme.md', display_name: 'readme.md', size: 512, size_display: '512 B', content_type: 'text/markdown', last_modified: '2026-10-19T10:00:00Z', is_dir: false },
  ],
  total: 2,
  page: 1,
  page_size: 50,
  total_pages: 1,
};

const SUB_OBJECTS = {
  bucket: 'odap-documents',
  prefix: 'reports/',
  items: [
    { name: 'reports/q3.pdf', display_name: 'q3.pdf', size: 4096, size_display: '4.0 KB', content_type: 'application/pdf', last_modified: '2026-10-18T09:00:00Z', is_dir: false },
  ],
  total: 1,
  page: 1,
  page_size: 50,
  total_pages: 1,
};

let objectsStatus = 200;

const fetchJsonMock = vi.fn(async (rawUrl: string, options?: { method?: string }) => {
  // 测试环境注入了 VITE_API_BASE=http://localhost:8000，断言只关心路径部分
  const url = rawUrl.replace(/^https?:\/\/[^/]+/, '');
  calls.push({ method: options?.method ?? 'GET', url });

  if (url === '/api/minio-admin/status') {
    return { available: true, endpoint: 'minio:9000', sdk_installed: true, detail: 'ok' };
  }
  if (url === '/api/minio-admin/buckets') {
    // 关键：直接是数组
    return BUCKETS;
  }
  if (url === '/api/minio-admin/stats') {
    return {
      total_buckets: 2,
      total_objects: 4,
      total_size: 3072,
      total_size_display: '3.0 KB',
      buckets: [],
    };
  }
  if (url.startsWith('/api/minio-admin/objects/metadata')) {
    return {
      bucket: 'odap-documents',
      key: 'readme.md',
      size: 512,
      size_display: '512 B',
      content_type: 'text/markdown',
      last_modified: '2026-10-19T10:00:00Z',
      etag: 'abc123',
      metadata: { 'x-amz-meta-origin': 'upload' },
    };
  }
  if (url.startsWith('/api/minio-admin/objects/presigned-url')) {
    return { url: 'http://minio:9000/odap-documents/readme.md?X-Amz-Signature=deadbeef', expires_seconds: 3600 };
  }
  if (url.startsWith('/api/minio-admin/objects/metadata')) {
    return {};
  }
  if (url.startsWith('/api/minio-admin/objects')) {
    if (options?.method === 'DELETE') return { message: 'deleted' };
    if (objectsStatus === 403) {
      throw Object.assign(new Error('HTTP 403'), {
        status: 403,
        detail: '仅管理员可访问对象存储管理',
      });
    }
    if (url.includes('prefix=reports%2F')) return SUB_OBJECTS;
    return ROOT_OBJECTS;
  }
  throw new Error(`unexpected ${options?.method ?? 'GET'} ${url}`);
});

vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (url: string, options?: { method?: string }) => fetchJsonMock(url, options),
  apiClient: {
    get: () => Promise.reject(new Error('StorageBrowser 不应使用 apiClient')),
    post: () => Promise.reject(new Error('StorageBrowser 不应使用 apiClient')),
  },
}));

import { StorageBrowser } from './StorageBrowser';

const urls = (method?: string) =>
  calls.filter((c) => !method || c.method === method).map((c) => c.url);

beforeEach(() => {
  calls.length = 0;
  objectsStatus = 200;
  fetchJsonMock.mockClear();
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn(async () => undefined) },
  });
});

describe('StorageBrowser — 对象存储浏览', () => {
  it('概览并发打 status / buckets / stats 三个端点', async () => {
    render(<StorageBrowser />);

    await waitFor(() => expect(urls()).toContain('/api/minio-admin/buckets'));
    expect(urls()).toContain('/api/minio-admin/status');
    expect(urls()).toContain('/api/minio-admin/stats');
  });

  it('/buckets 按裸数组解析（不是 { buckets }），并渲染 display_name 与统计', async () => {
    render(<StorageBrowser />);

    await waitFor(() => expect(screen.getByText('文档库')).toBeTruthy());
    expect(screen.getByText('素材库')).toBeTruthy();
    // 统计卡片来自 /stats
    expect(screen.getByText('3.0 KB')).toBeTruthy();
  });

  it('首次加载自动选中第一个桶，按真实查询参数拉对象列表', async () => {
    render(<StorageBrowser />);

    await waitFor(() =>
      expect(urls().some((u) => u.startsWith('/api/minio-admin/objects?'))).toBe(true),
    );
    const listUrl = urls().find((u) => u.startsWith('/api/minio-admin/objects?'))!;
    expect(listUrl).toContain('bucket=odap-documents');
    expect(listUrl).toContain('page=1');
    expect(listUrl).toContain('page_size=50');
    // 负向：prefix 为空时不得拼出 prefix=undefined
    expect(listUrl).not.toContain('prefix=undefined');

    await waitFor(() => expect(screen.getByText('readme.md')).toBeTruthy());
  });

  it('点目录行进入子路径，重发请求时带 prefix', async () => {
    render(<StorageBrowser />);
    await waitFor(() => expect(screen.getByText('reports')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /reports/ }));

    await waitFor(() =>
      expect(urls().some((u) => u.includes('prefix=reports%2F'))).toBe(true),
    );
    await waitFor(() => expect(screen.getByText('q3.pdf')).toBeTruthy());
  });

  it('元数据走 /objects/metadata，Drawer 里同时展示 ETag 与自定义 metadata', async () => {
    render(<StorageBrowser />);
    await waitFor(() => expect(screen.getByText('readme.md')).toBeTruthy());

    const metaBtn = document.querySelector('[title="元数据"]') as HTMLElement;
    fireEvent.click(metaBtn);

    await waitFor(() =>
      expect(urls().some((u) => u.startsWith('/api/minio-admin/objects/metadata?'))).toBe(true),
    );
    const metaUrl = urls().find((u) => u.startsWith('/api/minio-admin/objects/metadata?'))!;
    expect(metaUrl).toContain('bucket=odap-documents');
    expect(metaUrl).toContain('key=readme.md');

    await waitFor(() => expect(screen.getByText('abc123')).toBeTruthy());
    expect(screen.getByText('x-amz-meta-origin')).toBeTruthy();
  });

  it('复制下载链接走 /objects/presigned-url 并写入剪贴板', async () => {
    render(<StorageBrowser />);
    await waitFor(() => expect(screen.getByText('readme.md')).toBeTruthy());

    const linkBtn = document.querySelector('[title="复制下载链接"]') as HTMLElement;
    fireEvent.click(linkBtn);

    await waitFor(() =>
      expect(urls().some((u) => u.startsWith('/api/minio-admin/objects/presigned-url?'))).toBe(true),
    );
    const presignUrl = urls().find((u) => u.startsWith('/api/minio-admin/objects/presigned-url'))!;
    expect(presignUrl).toContain('expires_hours=1');
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        'http://minio:9000/odap-documents/readme.md?X-Amz-Signature=deadbeef',
      ),
    );
  });

  it('删除需二次确认，确认后用 query 传 bucket/key 打 DELETE', async () => {
    render(<StorageBrowser />);
    await waitFor(() => expect(screen.getByText('readme.md')).toBeTruthy());

    const delBtn = document.querySelector('[title="删除"]') as HTMLElement;
    fireEvent.click(delBtn);
    expect(urls('DELETE')).toHaveLength(0);

    await waitFor(() => expect(document.querySelector('.ant-popconfirm-buttons')).toBeTruthy());
    const confirmBtn = document.querySelector('.ant-popconfirm-buttons .ant-btn-primary') as HTMLElement;
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(urls('DELETE')).toHaveLength(1));
    const delUrl = urls('DELETE')[0];
    expect(delUrl).toContain('/api/minio-admin/objects?');
    expect(delUrl).toContain('bucket=odap-documents');
    expect(delUrl).toContain('key=readme.md');
  });

  it('非管理员的 403 原样透出后端 detail，不盖成笼统「加载失败」', async () => {
    objectsStatus = 403;
    render(<StorageBrowser />);

    await waitFor(() => expect(screen.getByText('对象列表不可用')).toBeTruthy());
    expect(screen.getByText('仅管理员可访问对象存储管理')).toBeTruthy();
  });
});
