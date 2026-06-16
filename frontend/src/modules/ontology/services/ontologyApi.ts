import { fetchJson, apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/ontology/model`;

export interface PropertyDefinition {
  name: string;
  data_type: 'string' | 'integer' | 'float' | 'boolean' | 'date' | 'datetime' | 'json' | 'array';
  required: boolean;
  default_value?: string;
  classification_level: 'TS' | 'S' | 'C' | 'U';
  description?: string;
}

export interface RelationDefinition {
  name: string;
  target_type: string;
  cardinality: '1:1' | '1:N' | 'N:1' | 'N:N' | 'N:M';
  link_type: 'association' | 'composition' | 'dependency' | 'inheritance';
  description?: string;
}

export interface EntityType {
  type_id: string;
  name: string;
  display_name: string;
  description: string;
  classification_level: 'TS' | 'S' | 'C' | 'U';
  properties: PropertyDefinition[];
  primary_key?: string;
  relations: RelationDefinition[];
  constraints?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface OntologyDocument {
  document_id: string;
  name: string;
  description: string;
  version: string;
  entity_types: EntityType[];
  created_at: string;
  updated_at: string;
}

export interface InstanceData {
  instance_id: string;
  type_id: string;
  type_name: string;
  properties: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const ontologyApi = {
  listEntityTypes: (documentId: string) =>
    fetchJson<EntityType[]>(`${BASE}/${documentId}/entity-types`),

  getEntityType: (documentId: string, typeId: string) =>
    fetchJson<EntityType>(`${BASE}/${documentId}/entity-types/${typeId}`),

  createEntityType: (documentId: string, data: Omit<EntityType, 'type_id' | 'created_at' | 'updated_at'>) =>
    fetchJson<EntityType>(`${BASE}/${documentId}/entity-types`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateEntityType: (documentId: string, typeId: string, data: Partial<EntityType>) =>
    fetchJson<EntityType>(`${BASE}/${documentId}/entity-types/${typeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteEntityType: (documentId: string, typeId: string) =>
    fetchJson<void>(`${BASE}/${documentId}/entity-types/${typeId}`, { method: 'DELETE' }),

  listInstances: (documentId: string, typeId: string, page?: number, pageSize?: number) => {
    const params = new URLSearchParams();
    if (page) params.set('page', String(page));
    if (pageSize) params.set('page_size', String(pageSize));
    const qs = params.toString();
    return fetchJson<{ instances: InstanceData[]; total: number }>(`${BASE}/${documentId}/entity-types/${typeId}/instances${qs ? '?' + qs : ''}`);
  },

  createInstance: (documentId: string, typeId: string, data: Record<string, unknown>) =>
    fetchJson<InstanceData>(`${BASE}/${documentId}/entity-types/${typeId}/instances`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateInstance: (documentId: string, typeId: string, instanceId: string, data: Record<string, unknown>) =>
    fetchJson<InstanceData>(`${BASE}/${documentId}/entity-types/${typeId}/instances/${instanceId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteInstance: (documentId: string, typeId: string, instanceId: string) =>
    fetchJson<void>(`${BASE}/${documentId}/entity-types/${typeId}/instances/${instanceId}`, { method: 'DELETE' }),

  batchImport: (documentId: string, typeId: string, instances: Record<string, unknown>[]) =>
    fetchJson<{ imported_count: number }>(`${BASE}/${documentId}/entity-types/${typeId}/instances/batch`, {
      method: 'POST',
      body: JSON.stringify({ instances }),
    }),

  loadOntologyDocument: (documentId: string) =>
    fetchJson<OntologyDocument>(`${BASE}/${documentId}`),

  exportDocument: (documentId: string, format: string = 'json') =>
    fetchJson<{ format: string; data: unknown }>(`${BASE}/${documentId}/export?format=${format}`),

  // ─── Ontology CRUD ───────────────────────────────────────────────
  ontologies: {
    list: (workspaceId?: string) =>
      apiClient.get(`/api/ontologies${workspaceId ? `?workspace_id=${workspaceId}` : ''}`),
    get: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}`),
    create: (data: { name: string; description?: string; workspace_id?: string; scenario_id?: string }) =>
      apiClient.post('/api/ontologies', data),
    update: (ontologyId: string, data: { name?: string; description?: string; status?: string }) =>
      apiClient.put(`/api/ontologies/${ontologyId}`, data),
    delete: (ontologyId: string) =>
      apiClient.delete(`/api/ontologies/${ontologyId}`),
  },

  // ─── Schema Versions ─────────────────────────────────────────────
  schemaVersions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/versions`),
    commit: (ontologyId: string, changelog: string) =>
      apiClient.post(`/api/ontologies/${ontologyId}/commit`, { changelog }),
    diff: (ontologyId: string, versionIdA: string, versionIdB: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/diff?version_id_a=${versionIdA}&version_id_b=${versionIdB}`),
    rollback: (ontologyId: string, versionId: string) =>
      apiClient.post(`/api/ontologies/${ontologyId}/rollback`, { target_version_id: versionId }),
  },

  // ─── Object Type Definitions ─────────────────────────────────────
  objectTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/object-types`),
    get: (ontologyId: string, typeId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/object-types/${typeId}`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/object-types`, data),
    update: (ontologyId: string, typeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/object-types/${typeId}`, data),
    delete: (ontologyId: string, typeId: string) =>
      apiClient.delete(`/api/ontologies/object-types/${typeId}`),
  },

  // ─── Link Type Definitions ───────────────────────────────────────
  linkTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/link-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/link-types`, data),
    update: (ontologyId: string, linkId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/link-types/${linkId}`, data),
    delete: (ontologyId: string, linkId: string) =>
      apiClient.delete(`/api/ontologies/link-types/${linkId}`),
  },

  // ─── Action Type Definitions ─────────────────────────────────────
  actionTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/action-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/action-types`, data),
    update: (ontologyId: string, actionTypeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/action-types/${actionTypeId}`, data),
    delete: (ontologyId: string, actionTypeId: string) =>
      apiClient.delete(`/api/ontologies/action-types/${actionTypeId}`),
  },

  // ─── Business Type Definitions ───────────────────────────────────
  processTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/process-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/process-types`, data),
    update: (ontologyId: string, typeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/process-types/${typeId}`, data),
    delete: (ontologyId: string, typeId: string) =>
      apiClient.delete(`/api/ontologies/process-types/${typeId}`),
  },
  ruleTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/rule-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/rule-types`, data),
    update: (ontologyId: string, typeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/rule-types/${typeId}`, data),
    delete: (ontologyId: string, typeId: string) =>
      apiClient.delete(`/api/ontologies/rule-types/${typeId}`),
  },
  functionTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/function-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/function-types`, data),
    update: (ontologyId: string, typeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/function-types/${typeId}`, data),
    delete: (ontologyId: string, typeId: string) =>
      apiClient.delete(`/api/ontologies/function-types/${typeId}`),
  },
  indicatorTypeDefinitions: {
    list: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/indicator-types`),
    create: (ontologyId: string, data: unknown) =>
      apiClient.post(`/api/ontologies/${ontologyId}/indicator-types`, data),
    update: (ontologyId: string, typeId: string, data: unknown) =>
      apiClient.put(`/api/ontologies/indicator-types/${typeId}`, data),
    delete: (ontologyId: string, typeId: string) =>
      apiClient.delete(`/api/ontologies/indicator-types/${typeId}`),
  },

  // ─── Graph ───────────────────────────────────────────────────────
  graph: {
    get: (ontologyId: string) =>
      apiClient.get(`/api/ontologies/${ontologyId}/graph`),
  },

  // ─── Database Connections ────────────────────────────────────────
  databaseConnections: {
    list: (workspaceId: string) =>
      apiClient.get(`/api/ontologies/database-connections?workspace_id=${workspaceId}`),
    save: (data: unknown) =>
      apiClient.post('/api/ontologies/database-connections', data),
    delete: (connectionId: string) =>
      apiClient.delete(`/api/ontologies/database-connections/${connectionId}`),
  },

  // ─── Extraction ─────────────────────────────────────────────────
  extraction: {
    testConnection: (data: Record<string, unknown>) =>
      apiClient.post('/api/extraction/test-connection', data),
    extractDatabase: (data: Record<string, unknown>) =>
      apiClient.post('/api/extraction/extract/database', data),
    extractNL: (data: Record<string, unknown>) =>
      apiClient.post('/api/extraction/extract/natural-language', data),
    getSession: (sessionId: string) =>
      apiClient.get(`/api/extraction/sessions/${sessionId}`),
    confirm: (sessionId: string, data: Record<string, unknown>) =>
      apiClient.post(`/api/extraction/sessions/${sessionId}/confirm`, data),
  },
};
