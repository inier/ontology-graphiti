import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

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
  cardinality: '1:1' | '1:N' | 'N:1' | 'N:N';
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
};
