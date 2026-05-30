import { fetchJson } from '../../shared';
import { API_BASE } from '../../../config';

const BASE = `${API_BASE}/api/ontology/blueprints`;

export interface BlueprintNode {
  node_id: string;
  node_type: string;
  name: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface BlueprintEdge {
  edge_id: string;
  source: string;
  target: string;
  edge_type: string;
  label: string;
}

export interface Blueprint {
  blueprint_id: string;
  name: string;
  description: string;
  scenario_id: string | null;
  version: number;
  nodes: BlueprintNode[];
  edges: BlueprintEdge[];
  layout: Record<string, unknown>;
  is_published: boolean;
  parent_version_id: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface BlueprintListItem {
  blueprint_id: string;
  name: string;
  version: number;
  is_published: boolean;
  updated_at: string;
}

export interface ValidationResult {
  status: string;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export const blueprintApi = {
  list: (scenarioId?: string, isPublished?: boolean) => {
    const params = new URLSearchParams();
    if (scenarioId) params.set('scenario_id', scenarioId);
    if (isPublished !== undefined) params.set('is_published', String(isPublished));
    return fetchJson<BlueprintListItem[]>(`${BASE}?${params.toString()}`);
  },

  get: (blueprintId: string) =>
    fetchJson<Blueprint>(`${BASE}/${blueprintId}`),

  create: (data: { name: string; description?: string; scenario_id?: string }) =>
    fetchJson<Blueprint>(BASE, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (blueprintId: string, data: Partial<Pick<Blueprint, 'name' | 'description' | 'layout' | 'metadata'>>) =>
    fetchJson<Blueprint>(`${BASE}/${blueprintId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (blueprintId: string) =>
    fetchJson<void>(`${BASE}/${blueprintId}`, { method: 'DELETE' }),

  addNode: (blueprintId: string, node: { node_type: string; name: string; position?: { x: number; y: number }; config?: Record<string, unknown> }) =>
    fetchJson<{ node_id: string }>(`${BASE}/${blueprintId}/nodes`, {
      method: 'POST',
      body: JSON.stringify(node),
    }),

  updateNode: (blueprintId: string, nodeId: string, data: Partial<BlueprintNode>) =>
    fetchJson<void>(`${BASE}/${blueprintId}/nodes/${nodeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  removeNode: (blueprintId: string, nodeId: string) =>
    fetchJson<void>(`${BASE}/${blueprintId}/nodes/${nodeId}`, { method: 'DELETE' }),

  addEdge: (blueprintId: string, edge: { source: string; target: string; edge_type?: string; label?: string }) =>
    fetchJson<{ edge_id: string }>(`${BASE}/${blueprintId}/edges`, {
      method: 'POST',
      body: JSON.stringify(edge),
    }),

  removeEdge: (blueprintId: string, edgeId: string) =>
    fetchJson<void>(`${BASE}/${blueprintId}/edges/${edgeId}`, { method: 'DELETE' }),

  batchAddNodes: (blueprintId: string, nodes: Array<{ node_type: string; name: string; position?: { x: number; y: number } }>) =>
    fetchJson<void>(`${BASE}/${blueprintId}/nodes/batch`, {
      method: 'POST',
      body: JSON.stringify({ nodes }),
    }),

  batchAddEdges: (blueprintId: string, edges: Array<{ source: string; target: string; edge_type?: string; label?: string }>) =>
    fetchJson<void>(`${BASE}/${blueprintId}/edges/batch`, {
      method: 'POST',
      body: JSON.stringify({ edges }),
    }),

  batchUpdatePositions: (blueprintId: string, positions: Record<string, { x: number; y: number }>) =>
    fetchJson<void>(`${BASE}/${blueprintId}/positions`, {
      method: 'PUT',
      body: JSON.stringify({ positions }),
    }),

  autoLayout: (blueprintId: string, direction: string = 'TB') =>
    fetchJson<void>(`${BASE}/${blueprintId}/auto-layout`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
    }),

  validate: (blueprintId: string) =>
    fetchJson<ValidationResult>(`${BASE}/${blueprintId}/validate`, { method: 'POST' }),

  publish: (blueprintId: string) =>
    fetchJson<void>(`${BASE}/${blueprintId}/publish`, { method: 'POST' }),

  fork: (blueprintId: string, newName?: string) =>
    fetchJson<Blueprint>(`${BASE}/${blueprintId}/fork`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName }),
    }),

  export: (blueprintId: string, format: string = 'json') =>
    fetchJson<{ format: string; blueprint?: Blueprint; code?: string }>(`${BASE}/${blueprintId}/export?format=${format}`),

  import: (data: { name: string; data: Record<string, unknown>; scenario_id?: string }) =>
    fetchJson<Blueprint>(`${BASE}/import`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
