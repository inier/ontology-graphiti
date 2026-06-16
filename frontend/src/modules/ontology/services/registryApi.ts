import { apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/ontology/registry`;

// ─── Shared Types ────────────────────────────────────────────────────

export interface PropertyDefinition {
  name: string;
  data_type: 'string' | 'integer' | 'float' | 'boolean' | 'date' | 'datetime' | 'json' | 'array';
  required: boolean;
  default_value?: string;
  classification_level?: 'TS' | 'S' | 'C' | 'U';
  description?: string;
}

// ─── Object Type ─────────────────────────────────────────────────────

export interface ObjectType {
  id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  properties?: PropertyDefinition[];
  constraints?: Record<string, unknown>;
  classification_level?: 'TS' | 'S' | 'C' | 'U';
  created_at: string;
  updated_at: string;
}

export interface CreateObjectTypeRequest {
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  properties?: PropertyDefinition[];
  constraints?: Record<string, unknown>;
  classification_level?: 'TS' | 'S' | 'C' | 'U';
}

export type UpdateObjectTypeRequest = Partial<Omit<CreateObjectTypeRequest, 'ontology_id'>>;

// ─── Action Type ─────────────────────────────────────────────────────

export interface ActionType {
  id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  properties?: PropertyDefinition[];
  created_at: string;
  updated_at: string;
}

export interface CreateActionTypeRequest {
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  properties?: PropertyDefinition[];
}

export type UpdateActionTypeRequest = Partial<Omit<CreateActionTypeRequest, 'ontology_id'>>;

// ─── Link Type ───────────────────────────────────────────────────────

export interface LinkType {
  id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  source_type?: string;
  target_type?: string;
  cardinality?: '1:1' | '1:N' | 'N:1' | 'N:N' | 'N:M';
  link_type?: 'association' | 'composition' | 'dependency' | 'inheritance';
  is_bidirectional?: boolean;
  reverse_name?: string;
  properties?: PropertyDefinition[];
  created_at: string;
  updated_at: string;
}

export interface CreateLinkTypeRequest {
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  source_type?: string;
  target_type?: string;
  cardinality?: '1:1' | '1:N' | 'N:1' | 'N:N' | 'N:M';
  link_type?: 'association' | 'composition' | 'dependency' | 'inheritance';
  is_bidirectional?: boolean;
  reverse_name?: string;
  properties?: PropertyDefinition[];
}

export type UpdateLinkTypeRequest = Partial<Omit<CreateLinkTypeRequest, 'ontology_id'>>;

// ─── Validation & Commit ─────────────────────────────────────────────

export interface ValidationResult {
  valid: boolean;
  errors?: string[];
  warnings?: string[];
}

export interface CommitResult {
  version_id: string;
  version_number: string;
  changelog: string;
  committed_at: string;
}

// ─── OMS (read-only) ────────────────────────────────────────────────

export interface OmsObjectType {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  properties?: PropertyDefinition[];
}

export interface OmsActionType {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
}

// ─── API Service ─────────────────────────────────────────────────────

export const registryApi = {
  // ── Object Types ──────────────────────────────────────────────────

  objectTypes: {
    create: (data: CreateObjectTypeRequest) =>
      apiClient.post<ObjectType>(`${BASE}/object-types`, data),

    list: (ontologyId: string) =>
      apiClient.get<ObjectType[]>(`${BASE}/ontologies/${ontologyId}/object-types`),

    get: (typeId: string) =>
      apiClient.get<ObjectType>(`${BASE}/object-types/${typeId}`),

    update: (typeId: string, data: UpdateObjectTypeRequest) =>
      apiClient.put<ObjectType>(`${BASE}/object-types/${typeId}`, data),

    delete: (typeId: string) =>
      apiClient.delete<void>(`${BASE}/object-types/${typeId}`),
  },

  // ── Action Types ──────────────────────────────────────────────────

  actionTypes: {
    create: (data: CreateActionTypeRequest) =>
      apiClient.post<ActionType>(`${BASE}/action-types`, data),

    list: (ontologyId: string) =>
      apiClient.get<ActionType[]>(`${BASE}/ontologies/${ontologyId}/action-types`),

    update: (actionTypeId: string, data: UpdateActionTypeRequest) =>
      apiClient.put<ActionType>(`${BASE}/action-types/${actionTypeId}`, data),

    delete: (actionTypeId: string) =>
      apiClient.delete<void>(`${BASE}/action-types/${actionTypeId}`),
  },

  // ── Link Types ────────────────────────────────────────────────────

  linkTypes: {
    create: (data: CreateLinkTypeRequest) =>
      apiClient.post<LinkType>(`${BASE}/link-types`, data),

    list: (ontologyId: string) =>
      apiClient.get<LinkType[]>(`${BASE}/ontologies/${ontologyId}/link-types`),

    update: (linkTypeId: string, data: UpdateLinkTypeRequest) =>
      apiClient.put<LinkType>(`${BASE}/link-types/${linkTypeId}`, data),

    delete: (linkTypeId: string) =>
      apiClient.delete<void>(`${BASE}/link-types/${linkTypeId}`),
  },

  // ── Validate & Commit ─────────────────────────────────────────────

  validateIngest: (ontologyId: string) =>
    apiClient.get<ValidationResult>(`${BASE}/ontologies/${ontologyId}/validate`),

  commitVersion: (ontologyId: string, changelog: string) =>
    apiClient.post<CommitResult>(`${BASE}/ontologies/${ontologyId}/commit`, { changelog }),

  // ── OMS (read-only) ──────────────────────────────────────────────

  oms: {
    listObjectTypes: () =>
      apiClient.get<OmsObjectType[]>(`${BASE}/oms/object-types`),

    getObjectType: (id: string) =>
      apiClient.get<OmsObjectType>(`${BASE}/oms/object-types/${id}`),

    listActionTypes: () =>
      apiClient.get<OmsActionType[]>(`${BASE}/oms/action-types`),

    getActionType: (id: string) =>
      apiClient.get<OmsActionType>(`${BASE}/oms/action-types/${id}`),
  },
};
