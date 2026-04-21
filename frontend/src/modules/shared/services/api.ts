import type { Scenario, Entity, TimelineEvent, Version, DiffResult, Stats } from '../types';
import { API_BASE } from '../../../config';

interface GraphNode {
  id: string;
  name: string;
  type?: string;
  [key: string]: unknown;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  event_id?: string;
  [key: string]: unknown;
}

interface RelationsResponse {
  scenario_id: string;
  nodes: GraphNode[];
  links: GraphEdge[];
}

export interface Workspace {
  workspace_id: string;
  name: string;
  description: string;
  type: string;
  status: string;
  owner: string;
  members?: string[];
  created_at: string;
  updated_at?: string;
  member_count?: number;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  actor_id: string;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: string;
  result_status: string;
  result_message: string;
  workspace_id: string;
  trace_id: string;
  context?: Record<string, unknown>;
}

function isGraphNode(obj: unknown): obj is GraphNode {
  return typeof obj === 'object' && obj !== null && 'id' in obj && 'name' in obj;
}

function isGraphEdge(obj: unknown): obj is GraphEdge {
  return typeof obj === 'object' && obj !== null && 'id' in obj && 'source' in obj && 'target' in obj;
}

function isRelationsResponse(obj: unknown): obj is RelationsResponse {
  return typeof obj === 'object' && obj !== null && 'scenario_id' in obj && 'nodes' in obj && 'links' in obj;
}

function safeCastArray<T>(arr: unknown, validator: (item: unknown) => boolean): T[] {
  if (!Array.isArray(arr)) return [];
  return arr.filter(validator) as T[];
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  async listScenarios(): Promise<Scenario[]> {
    const data = await fetchJson<{ scenarios: Scenario[] }>(`${API_BASE}/api/scenarios`);
    return data.scenarios;
  },

  async getScenario(scenarioId: string): Promise<Scenario> {
    return fetchJson(`${API_BASE}/api/scenarios/${scenarioId}`);
  },

  async createScenario(data: Partial<Scenario>): Promise<Scenario> {
    return fetchJson(`${API_BASE}/api/scenarios`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async syncScenario(scenarioId: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/api/scenarios/${scenarioId}/sync`, {
      method: 'POST',
    });
  },

  async getTimeline(scenarioId: string): Promise<TimelineEvent[]> {
    const data = await fetchJson<{ events: TimelineEvent[] }>(`${API_BASE}/api/scenarios/${scenarioId}/timeline`);
    return data.events;
  },

  async getEntities(scenarioId: string): Promise<Entity[]> {
    const data = await fetchJson<{ entities: Entity[] }>(`${API_BASE}/api/scenarios/${scenarioId}/entities`);
    return data.entities;
  },

  async getRelations(scenarioId: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
    const data = await fetchJson<unknown>(`${API_BASE}/api/scenarios/${scenarioId}/relations`);
    
    if (!isRelationsResponse(data)) {
      console.warn('Invalid relations response format:', data);
      return { nodes: [], edges: [] };
    }
    
    const nodes = safeCastArray<GraphNode>(data.nodes, isGraphNode);
    const edges = safeCastArray<GraphEdge>(data.links, isGraphEdge);
    
    return { nodes, edges };
  },

  async ingestText(text: string, scenarioId?: string): Promise<{ success: boolean; task_id: string }> {
    return fetchJson(`${API_BASE}/api/ingest/text`, {
      method: 'POST',
      body: JSON.stringify({ text, scenario_id: scenarioId }),
    });
  },

  async ingestNews(url: string, scenarioId?: string): Promise<{ success: boolean; task_id: string }> {
    return fetchJson(`${API_BASE}/api/ingest/news`, {
      method: 'POST',
      body: JSON.stringify({ url, scenario_id: scenarioId }),
    });
  },

  async ingestRandom(scenarioId?: string): Promise<{ success: boolean; doc_count: number; versions: string[] }> {
    return fetchJson(`${API_BASE}/api/ingest/random`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId }),
    });
  },

  async ingestManual(data: Record<string, unknown>, scenarioId?: string): Promise<{ task_id: string }> {
    return fetchJson(`${API_BASE}/api/ingest/manual`, {
      method: 'POST',
      body: JSON.stringify({ data, scenario_id: scenarioId }),
    });
  },

  async ingestFile(file: File, scenarioId?: string): Promise<{ success: boolean; task_id: string; filename: string; file_size: number }> {
    const formData = new FormData();
    formData.append('file', file);
    if (scenarioId) {
      formData.append('scenario_id', scenarioId);
    }
    
    const response = await fetch(`${API_BASE}/api/ingest/file`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return response.json();
  },

  async listVersions(): Promise<Version[]> {
    const data = await fetchJson<{ versions: Version[] }>(`${API_BASE}/api/versions`);
    return data.versions;
  },

  async getVersion(versionId: string): Promise<Version> {
    return fetchJson(`${API_BASE}/api/versions/${versionId}`);
  },

  async rollback(versionId: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/api/versions/${versionId}/rollback`, {
      method: 'POST',
    });
  },

  async diffVersions(versionA: string, versionB: string): Promise<DiffResult> {
    return fetchJson(`${API_BASE}/api/versions/diff?version_a=${versionA}&version_b=${versionB}`);
  },

  async getEntityHistory(entityId: string): Promise<TimelineEvent[]> {
    return fetchJson(`${API_BASE}/api/entities/${entityId}/history`);
  },

  async getStats(): Promise<Stats> {
    return fetchJson(`${API_BASE}/api/stats`);
  },

  async getHealth(): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/health`);
  },

  async listWorkspaces(): Promise<Workspace[]> {
    const data = await fetchJson<{ workspaces: Workspace[] }>(`${API_BASE}/api/workspaces`);
    return data.workspaces || [];
  },

  async getWorkspace(workspaceId: string): Promise<Workspace> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}`);
  },

  async createWorkspace(data: { name: string; description?: string; owner?: string }): Promise<Workspace> {
    return fetchJson(`${API_BASE}/api/workspaces`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateWorkspace(workspaceId: string, data: { name?: string; description?: string; status?: string }): Promise<Workspace> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteWorkspace(workspaceId: string): Promise<{ status: string; message: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}`, {
      method: 'DELETE',
    });
  },

  async activateWorkspace(workspaceId: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/activate`, {
      method: 'POST',
    });
  },

  async deactivateWorkspace(workspaceId: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/deactivate`, {
      method: 'POST',
    });
  },

  async listAuditEvents(params?: {
    start_time?: string;
    end_time?: string;
    event_type?: string;
    severity?: string;
    actor_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ events: AuditEvent[]; total: number; limit: number; offset: number }> {
    const searchParams = new URLSearchParams();
    if (params?.start_time) searchParams.set('start_time', params.start_time);
    if (params?.end_time) searchParams.set('end_time', params.end_time);
    if (params?.event_type) searchParams.set('event_type', params.event_type);
    if (params?.severity) searchParams.set('severity', params.severity);
    if (params?.actor_id) searchParams.set('actor_id', params.actor_id);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    
    const queryString = searchParams.toString();
    const url = `${API_BASE}/api/audit/events${queryString ? `?${queryString}` : ''}`;
    return fetchJson(url);
  },

  async createAuditEvent(data: {
    event_type: string;
    action: string;
    severity?: string;
    actor_id?: string;
    actor_name?: string;
    resource_type?: string;
    resource_id?: string;
    result_status?: string;
    result_message?: string;
    workspace_id?: string;
  }): Promise<AuditEvent> {
    return fetchJson(`${API_BASE}/api/audit/events`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getAuditStats(): Promise<{
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
  }> {
    return fetchJson(`${API_BASE}/api/audit/stats`);
  },

  async getAuditTimeline(params?: {
    start_time?: string;
    end_time?: string;
    workspace_id?: string;
  }): Promise<{ events: AuditEvent[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.start_time) searchParams.set('start_time', params.start_time);
    if (params?.end_time) searchParams.set('end_time', params.end_time);
    if (params?.workspace_id) searchParams.set('workspace_id', params.workspace_id);
    
    const queryString = searchParams.toString();
    const url = `${API_BASE}/api/audit/timeline${queryString ? `?${queryString}` : ''}`;
    return fetchJson(url);
  },

  async getSituationMap(scenarioId: string): Promise<Array<{
    id: string;
    name: string;
    side: 'blue' | 'red' | 'neutral';
    position: [number, number];
    type: string;
    status: string;
  }>> {
    const data = await fetchJson<{ units: Array<{
      id: string;
      name: string;
      side: 'blue' | 'red' | 'neutral';
      position: [number, number];
      type: string;
      status: string;
    }> }>(`${API_BASE}/api/scenarios/${scenarioId}/situation-map`);
    return data.units;
  },

  // ==================== 图谱查询 API ====================

  async queryEntities(query: { keyword?: string; type?: string }, workspaceId?: string): Promise<{ entities: Array<{ entity_id: string; name: string; type: string; properties: Record<string, unknown> }>; total: number }> {
    return fetchJson(`${API_BASE}/api/query/entities`, {
      method: 'POST',
      body: JSON.stringify({ query, workspace_id: workspaceId }),
    });
  },

  async queryRelations(query: { source_id?: string; target_id?: string; relation_type?: string }, workspaceId?: string): Promise<{ relations: Array<Record<string, unknown>>; total: number }> {
    return fetchJson(`${API_BASE}/api/query/relations`, {
      method: 'POST',
      body: JSON.stringify({ query, workspace_id: workspaceId }),
    });
  },

  async complexQuery(conditions: Array<{ type: string; field?: string; operator?: string; value: string }>, workspaceId?: string): Promise<{ results: Array<{ entity_id: string; name: string; type: string; properties: Record<string, unknown> }>; total: number }> {
    return fetchJson(`${API_BASE}/api/query/complex`, {
      method: 'POST',
      body: JSON.stringify({ conditions, workspace_id: workspaceId }),
    });
  },

  async getQueryHistory(limit: number = 50): Promise<{ history: Array<Record<string, unknown>>; limit: number }> {
    return fetchJson(`${API_BASE}/api/query/history?limit=${limit}`);
  },

  async exportQueryResults(results: Array<Record<string, unknown>>, format: 'json' | 'csv' = 'json'): Promise<{ success: boolean; data: string }> {
    return fetchJson(`${API_BASE}/api/query/export`, {
      method: 'POST',
      body: JSON.stringify({ results, format }),
    });
  },

  // ==================== 图谱生成 API ====================

  async generateGraph(scenarioId: string, config?: Record<string, unknown>): Promise<{ task_id: string; status: string; scenario_id: string }> {
    return fetchJson(`${API_BASE}/api/graph/generate`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId, config }),
    });
  },

  async getGraphProgress(taskId: string): Promise<{ task_id: string; status: string; progress: number; entities_generated: number; relations_generated: number }> {
    return fetchJson(`${API_BASE}/api/graph/progress/${taskId}`);
  },

  async cancelGraphTask(taskId: string): Promise<{ task_id: string; status: string }> {
    return fetchJson(`${API_BASE}/api/graph/cancel/${taskId}`, {
      method: 'POST',
    });
  },

  async getGraphHistory(limit: number = 20): Promise<{ history: Array<Record<string, unknown>>; limit: number; total: number }> {
    return fetchJson(`${API_BASE}/api/graph/history?limit=${limit}`);
  },

  async getGraphDetail(graphId: string): Promise<{ graph_id: string; nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }> {
    return fetchJson(`${API_BASE}/api/graph/${graphId}`);
  },
};