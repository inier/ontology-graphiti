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
import { fetchJson, apiClient } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

export const knowledgeApi = {
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

    return apiClient.upload(`${API_BASE}/api/knowledge-bases/${data.kb_id}/documents`, formData);
  },

  deleteDocument: (kbId: string, docId: string): Promise<void> =>
    fetch(`${API_BASE}/api/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    }),

  getDocument: (kbId: string, docId: string): Promise<KnowledgeDocument> =>
    fetchJson<KnowledgeDocument>(`${API_BASE}/api/knowledge-bases/${kbId}/documents/${docId}`),

  buildGraph: (data: GraphBuildRequest): Promise<{ task_id: string; status: string }> =>
    fetchJson<{ task_id: string; status: string }>(`${API_BASE}/api/knowledge-bases/documents/${data.doc_id}/build-graph`, {
      method: 'POST',
      body: JSON.stringify(data.extraction_config),
    }),

  getGraphBuildStatus: (taskId: string): Promise<{ status: string; progress: number; result?: any }> =>
    fetchJson<{ status: string; progress: number; result?: any }>(`${API_BASE}/api/knowledge-bases/graph-tasks/${taskId}`),

  ragQuery: (data: RAGQueryRequest): Promise<RAGQueryResult> =>
    fetchJson<RAGQueryResult>(`${API_BASE}/api/knowledge-bases/${data.kb_id}/rag-query`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  crawlWeb: (kbId: string, url: string, config?: { max_depth?: number; max_pages?: number }): Promise<{ task_id: string }> =>
    fetchJson<{ task_id: string }>(`${API_BASE}/api/knowledge-bases/${kbId}/crawl`, {
      method: 'POST',
      body: JSON.stringify({ url, ...config }),
    }),
};
