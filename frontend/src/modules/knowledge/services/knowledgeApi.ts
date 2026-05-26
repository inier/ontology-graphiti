import type {
  KnowledgeBase,
  KnowledgeCategory,
  KnowledgeDocument,
  KnowledgeBaseFormData,
  DocumentUploadData,
  GraphBuildRequest,
  RAGQueryRequest,
  RAGQueryResult,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token');
  const authHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) authHeaders['Authorization'] = `Bearer ${token}`;
  const mergedOptions: RequestInit = { ...options, headers: { ...authHeaders, ...(options?.headers as Record<string, string>) } };
  const res = await fetch(url, mergedOptions);
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const knowledgeApi = {
  // 知识库 CRUD
  listKnowledgeBases: (): Promise<KnowledgeBase[]> =>
    fetchJson<KnowledgeBase[]>(`${API_BASE}/api/knowledge-bases`),

  getKnowledgeBase: (id: string): Promise<KnowledgeBase> =>
    fetchJson<KnowledgeBase>(`${API_BASE}/api/knowledge-bases/${id}`),

  createKnowledgeBase: (data: KnowledgeBaseFormData): Promise<KnowledgeBase> =>
    fetchJson<KnowledgeBase>(`${API_BASE}/api/knowledge-bases`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateKnowledgeBase: (id: string, data: KnowledgeBaseFormData): Promise<KnowledgeBase> =>
    fetchJson<KnowledgeBase>(`${API_BASE}/api/knowledge-bases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteKnowledgeBase: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/knowledge-bases/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    }),

  // 分类管理
  listCategories: (kbId: string): Promise<KnowledgeCategory[]> =>
    fetchJson<KnowledgeCategory[]>(`${API_BASE}/api/knowledge-bases/${kbId}/categories`),

  createCategory: (kbId: string, data: { name: string; parent_id?: string }): Promise<KnowledgeCategory> =>
    fetchJson<KnowledgeCategory>(`${API_BASE}/api/knowledge-bases/${kbId}/categories`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  deleteCategory: (kbId: string, categoryId: string): Promise<void> =>
    fetch(`${API_BASE}/api/knowledge-bases/${kbId}/categories/${categoryId}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    }),

  // 文档管理
  listDocuments: (kbId: string, categoryId?: string): Promise<KnowledgeDocument[]> =>
    fetchJson<KnowledgeDocument[]>(
      `${API_BASE}/api/knowledge-bases/${kbId}/documents${categoryId ? `?category_id=${categoryId}` : ''}`
    ),

  uploadDocument: (data: DocumentUploadData): Promise<KnowledgeDocument> => {
    const formData = new FormData();
    formData.append('kb_id', data.kb_id);
    if (data.category_id) formData.append('category_id', data.category_id);
    formData.append('content_type', data.content_type);
    formData.append('title', data.title);
    if (data.content) formData.append('content', data.content);
    if (data.file) formData.append('file', data.file);
    if (data.web_url) formData.append('web_url', data.web_url);

    return fetch(`${API_BASE}/api/knowledge-bases/${data.kb_id}/documents`, {
      method: 'POST',
      body: formData,
    }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
  },

  deleteDocument: (kbId: string, docId: string): Promise<void> =>
    fetch(`${API_BASE}/api/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    }),

  getDocument: (kbId: string, docId: string): Promise<KnowledgeDocument> =>
    fetchJson<KnowledgeDocument>(`${API_BASE}/api/knowledge-bases/${kbId}/documents/${docId}`),

  // 图谱构建
  buildGraph: (data: GraphBuildRequest): Promise<{ task_id: string; status: string }> =>
    fetchJson<{ task_id: string; status: string }>(`${API_BASE}/api/knowledge-bases/documents/${data.doc_id}/build-graph`, {
      method: 'POST',
      body: JSON.stringify(data.extraction_config),
    }),

  getGraphBuildStatus: (taskId: string): Promise<{ status: string; progress: number; result?: any }> =>
    fetchJson<{ status: string; progress: number; result?: any }>(`${API_BASE}/api/knowledge-bases/graph-tasks/${taskId}`),

  // RAG 查询
  ragQuery: (data: RAGQueryRequest): Promise<RAGQueryResult> =>
    fetchJson<RAGQueryResult>(`${API_BASE}/api/knowledge-bases/${data.kb_id}/rag-query`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 外部抓取
  crawlWeb: (kbId: string, url: string, config?: { max_depth?: number; max_pages?: number }): Promise<{ task_id: string }> =>
    fetchJson<{ task_id: string }>(`${API_BASE}/api/knowledge-bases/${kbId}/crawl`, {
      method: 'POST',
      body: JSON.stringify({ url, ...config }),
    }),
};
