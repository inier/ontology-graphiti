import type { Scenario, Entity, TimelineEvent, Version, DiffResult, Stats } from '../types';

const API_BASE = 'http://localhost:8765';

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
};
