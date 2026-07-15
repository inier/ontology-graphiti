import { describe, it, expect, vi, beforeEach } from 'vitest';
import { knowledgeApi } from './knowledgeApi';

const API_BASE = 'http://localhost:8000';

function mockFetchResponse<T>(data: T, status = 200) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
}

function mockFetchError(status: number, statusText: string) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve({ detail: statusText }),
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', 'test-jwt-token');
});

// ─── Knowledge Base CRUD ───────────────────────────────────────

describe('knowledgeApi - Knowledge Base CRUD', () => {
  const mockKB = {
    id: 'kb-1',
    name: 'Test KB',
    description: 'A test knowledge base',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

  it('listKnowledgeBases calls GET /api/knowledge-bases', async () => {
    mockFetchResponse([mockKB]);

    const result = await knowledgeApi.listKnowledgeBases();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('kb-1');
  });

  it('getKnowledgeBase calls GET /api/knowledge-bases/:id', async () => {
    mockFetchResponse(mockKB);

    const result = await knowledgeApi.getKnowledgeBase('kb-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1'),
      expect.any(Object),
    );
    expect(result.id).toBe('kb-1');
  });

  it('createKnowledgeBase sends POST with correct body', async () => {
    const formData = { name: 'New KB', description: 'desc' };
    mockFetchResponse({ id: 'kb-new', ...formData });

    const result = await knowledgeApi.createKnowledgeBase(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(formData),
      }),
    );
    expect(result.id).toBe('kb-new');
  });

  it('updateKnowledgeBase sends PUT with correct body', async () => {
    const formData = { name: 'Updated KB', description: 'new desc' };
    mockFetchResponse({ id: 'kb-1', ...formData });

    const result = await knowledgeApi.updateKnowledgeBase('kb-1', formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(formData),
      }),
    );
    expect(result.name).toBe('Updated KB');
  });

  it('deleteKnowledgeBase sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await knowledgeApi.deleteKnowledgeBase('kb-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Categories ────────────────────────────────────────────────

describe('knowledgeApi - Categories', () => {
  const mockCategory = {
    id: 'cat-1',
    name: 'General',
    parent_id: null,
    created_at: '2026-01-01',
  };

  it('listCategories calls GET /api/knowledge-bases/:kbId/categories', async () => {
    mockFetchResponse([mockCategory]);

    const result = await knowledgeApi.listCategories('kb-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/categories'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('createCategory sends POST with correct body', async () => {
    const data = { name: 'New Category', parent_id: 'cat-1' };
    mockFetchResponse({ id: 'cat-new', ...data });

    const result = await knowledgeApi.createCategory('kb-1', data);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/categories'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(data),
      }),
    );
    expect(result.id).toBe('cat-new');
  });

  it('createCategory works without parent_id', async () => {
    const data = { name: 'Root Category' };
    mockFetchResponse({ id: 'cat-root', name: 'Root Category' });

    await knowledgeApi.createCategory('kb-1', data);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(JSON.parse(callOptions.body as string)).toEqual(data);
  });

  it('deleteCategory sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await knowledgeApi.deleteCategory('kb-1', 'cat-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/categories/cat-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Documents ─────────────────────────────────────────────────

describe('knowledgeApi - Documents', () => {
  const mockDoc = {
    id: 'doc-1',
    title: 'Test Document',
    content_type: 'text',
    kb_id: 'kb-1',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

  it('listDocuments calls GET /api/knowledge-bases/:kbId/documents', async () => {
    mockFetchResponse([mockDoc]);

    const result = await knowledgeApi.listDocuments('kb-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/documents'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('listDocuments passes category_id as query param', async () => {
    mockFetchResponse([]);

    await knowledgeApi.listDocuments('kb-1', 'cat-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('category_id=cat-1');
  });

  it('listDocuments omits query when no category_id', async () => {
    mockFetchResponse([]);

    await knowledgeApi.listDocuments('kb-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('category_id');
  });

  it('getDocument calls GET /api/knowledge-bases/:kbId/documents/:docId', async () => {
    mockFetchResponse(mockDoc);

    const result = await knowledgeApi.getDocument('kb-1', 'doc-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/documents/doc-1'),
      expect.any(Object),
    );
    expect(result.id).toBe('doc-1');
  });

  it('deleteDocument sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await knowledgeApi.deleteDocument('kb-1', 'doc-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/documents/doc-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('uploadDocument sends POST with FormData', async () => {
    const uploadData = {
      kb_id: 'kb-1',
      content_type: 'text',
      title: 'Upload Test',
      content: 'Hello world',
    };
    mockFetchResponse({ id: 'doc-new', title: 'Upload Test' });

    const result = await knowledgeApi.uploadDocument(uploadData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/documents'),
      expect.objectContaining({
        method: 'POST',
      }),
    );
    // Verify FormData body is sent (not JSON string)
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(callOptions.body).toBeInstanceOf(FormData);
    expect(result.id).toBe('doc-new');
  });

  it('uploadDocument includes optional fields in FormData', async () => {
    const uploadData = {
      kb_id: 'kb-1',
      category_id: 'cat-1',
      content_type: 'file',
      title: 'File Upload',
      web_url: 'https://example.com',
    };
    mockFetchResponse({ id: 'doc-url' });

    await knowledgeApi.uploadDocument(uploadData as any);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const formData = callOptions.body as FormData;
    expect(formData.get('kb_id')).toBe('kb-1');
    expect(formData.get('category_id')).toBe('cat-1');
    expect(formData.get('content_type')).toBe('file');
    expect(formData.get('title')).toBe('File Upload');
    expect(formData.get('web_url')).toBe('https://example.com');
  });
});

// ─── Graph Build ───────────────────────────────────────────────

describe('knowledgeApi - Graph Build', () => {
  it('buildGraph sends POST with extraction config', async () => {
    const data = {
      doc_id: 'doc-1',
      extraction_method: 'auto',
      entity_types: ['Person', 'Organization'],
    };
    mockFetchResponse({ task_id: 'task-1', status: 'running', method: 'auto' });

    const result = await knowledgeApi.buildGraph(data as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/documents/doc-1/build-graph'),
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.task_id).toBe('task-1');
    expect(result.method).toBe('auto');
  });

  it('buildGraph defaults extraction_method to auto', async () => {
    const data = { doc_id: 'doc-2' };
    mockFetchResponse({ task_id: 'task-2', status: 'running' });

    await knowledgeApi.buildGraph(data as any);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const body = JSON.parse(callOptions.body as string);
    expect(body.extraction_method).toBe('auto');
    expect(body.entity_types).toEqual([]);
  });

  it('buildGraph uses extraction_config entity_types as fallback', async () => {
    const data = {
      doc_id: 'doc-3',
      extraction_config: { entity_types: ['Event'] },
    };
    mockFetchResponse({ task_id: 'task-3', status: 'running' });

    await knowledgeApi.buildGraph(data as any);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const body = JSON.parse(callOptions.body as string);
    expect(body.entity_types).toEqual(['Event']);
  });

  it('getGraphBuildStatus calls GET endpoint', async () => {
    mockFetchResponse({ status: 'completed', progress: 100 });

    const result = await knowledgeApi.getGraphBuildStatus('task-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/graph-tasks/task-1'),
      expect.any(Object),
    );
    expect(result.status).toBe('completed');
    expect(result.progress).toBe(100);
  });
});

// ─── RAG Query ─────────────────────────────────────────────────

describe('knowledgeApi - RAG Query', () => {
  it('ragQuery sends POST with query data', async () => {
    const data = {
      kb_id: 'kb-1',
      question: 'What is ontology?',
    };
    const mockResult = {
      answer: 'Ontology is a knowledge representation framework.',
      sources: [],
      confidence: 0.9,
    };
    mockFetchResponse(mockResult);

    const result = await knowledgeApi.ragQuery(data as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/rag-query'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(data),
      }),
    );
    expect(result.answer).toContain('Ontology');
    expect(result.confidence).toBe(0.9);
  });
});

// ─── Web Crawl ─────────────────────────────────────────────────

describe('knowledgeApi - Web Crawl', () => {
  it('crawlWeb sends POST with url and config', async () => {
    mockFetchResponse({ task_id: 'crawl-1' });

    const result = await knowledgeApi.crawlWeb('kb-1', 'https://example.com', { max_depth: 3, max_pages: 50 });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge-bases/kb-1/crawl'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ url: 'https://example.com', max_depth: 3, max_pages: 50 }),
      }),
    );
    expect(result.task_id).toBe('crawl-1');
  });

  it('crawlWeb works without optional config', async () => {
    mockFetchResponse({ task_id: 'crawl-2' });

    await knowledgeApi.crawlWeb('kb-1', 'https://example.com');
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const body = JSON.parse(callOptions.body as string);
    expect(body.url).toBe('https://example.com');
    expect(body.max_depth).toBeUndefined();
    expect(body.max_pages).toBeUndefined();
  });
});

// ─── Error Handling ────────────────────────────────────────────

describe('knowledgeApi - Error Handling', () => {
  it('throws on HTTP error response', async () => {
    mockFetchError(500, 'Internal Server Error');

    await expect(knowledgeApi.listKnowledgeBases()).rejects.toThrow('HTTP 500');
  });

  it('throws on 404 error', async () => {
    mockFetchError(404, 'Not Found');

    await expect(knowledgeApi.getKnowledgeBase('nonexistent')).rejects.toThrow('HTTP 404');
  });

  it('throws on network error', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(knowledgeApi.listKnowledgeBases()).rejects.toThrow('Failed to fetch');
  });

  it('throws on 400 error for invalid input', async () => {
    mockFetchError(400, 'Bad Request');

    await expect(knowledgeApi.createKnowledgeBase({} as any)).rejects.toThrow('HTTP 400');
  });

  it('throws on 422 for validation error', async () => {
    mockFetchError(422, 'Unprocessable Entity');

    await expect(knowledgeApi.ragQuery({} as any)).rejects.toThrow('HTTP 422');
  });
});

// ─── Auth Headers ──────────────────────────────────────────────

describe('knowledgeApi - Auth Headers', () => {
  it('includes Authorization header when token exists', async () => {
    mockFetchResponse([]);

    await knowledgeApi.listKnowledgeBases();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
  });

  it('includes Content-Type application/json header', async () => {
    mockFetchResponse([]);

    await knowledgeApi.listKnowledgeBases();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('uploadDocument includes Authorization but not Content-Type (FormData sets it)', async () => {
    const uploadData = {
      kb_id: 'kb-1',
      content_type: 'text',
      title: 'Test',
    };
    mockFetchResponse({ id: 'doc-1' });

    await knowledgeApi.uploadDocument(uploadData as any);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
    // FormData upload should NOT set Content-Type manually (browser sets boundary)
    expect(headers['Content-Type']).toBeUndefined();
  });
});
