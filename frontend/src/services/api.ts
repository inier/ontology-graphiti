import type { Scenario, Entity, Relation, TimelineEvent, Version, DiffResult, Stats } from '../types';

const API_BASE = 'http://localhost:8765';

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
    return fetchJson(`${API_BASE}/api/scenarios`);
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
    return fetchJson(`${API_BASE}/api/scenarios/${scenarioId}/timeline`);
  },

  async getEntities(scenarioId: string): Promise<Entity[]> {
    return fetchJson(`${API_BASE}/api/scenarios/${scenarioId}/entities`);
  },

  async getRelations(scenarioId: string): Promise<Relation[]> {
    return fetchJson(`${API_BASE}/api/scenarios/${scenarioId}/relations`);
  },

  async ingestText(text: string, scenarioId?: string): Promise<{ task_id: string }> {
    return fetchJson(`${API_BASE}/api/ingest/text`, {
      method: 'POST',
      body: JSON.stringify({ text, scenario_id: scenarioId }),
    });
  },

  async ingestNews(url: string, scenarioId?: string): Promise<{ task_id: string }> {
    return fetchJson(`${API_BASE}/api/ingest/news`, {
      method: 'POST',
      body: JSON.stringify({ url, scenario_id: scenarioId }),
    });
  },

  async ingestRandom(scenarioId?: string): Promise<{ task_id: string }> {
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
    return fetchJson(`${API_BASE}/api/versions`);
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
