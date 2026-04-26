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
    try {
      // 先尝试获取所有工作空间的场景
      const workspacesData = await fetchJson<{ workspaces: Workspace[] }>(`${API_BASE}/api/workspaces`);
      let allScenarios: Scenario[] = [];
      for (const ws of workspacesData.workspaces || []) {
        try {
          const scenariosData = await fetchJson<{ scenarios: Scenario[] }>(`${API_BASE}/api/workspaces/${ws.workspace_id}/scenarios`);
          allScenarios = allScenarios.concat(scenariosData.scenarios || []);
        } catch (e) {
          console.error(`获取工作空间 ${ws.workspace_id} 场景失败`, e);
        }
      }
      if (allScenarios.length > 0) {
        return allScenarios;
      }
    } catch (e) {
      console.error('获取新路由场景失败，尝试旧路由', e);
    }
    // 回退到旧路由
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

  // ==================== 场景管理 API ====================

  async createScenario(workspaceId: string, name: string, description?: string, ontologyId?: string): Promise<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios`, {
      method: 'POST',
      body: JSON.stringify({ name, description, ontology_id: ontologyId }),
    });
  },

  async getScenarios(workspaceId: string): Promise<{ scenarios: Array<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }>; workspace_id: string; total: number }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios`);
  },

  async getScenario(workspaceId: string, scenarioId: string): Promise<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}`);
  },

  async updateScenario(workspaceId: string, scenarioId: string, name?: string, description?: string, ontologyId?: string): Promise<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }> {
    const body: Record<string, unknown> = {};
    if (name !== undefined) body.name = name;
    if (description !== undefined) body.description = description;
    if (ontologyId !== undefined) body.ontology_id = ontologyId;
    
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },

  async deleteScenario(workspaceId: string, scenarioId: string): Promise<{ status: string; message: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}`, {
      method: 'DELETE',
    });
  },

  async buildGraph(workspaceId: string, scenarioId: string): Promise<{
    status: string;
    scenario_id: string;
    ontology_id?: string;
    entity_count: number;
    event_count: number;
    entities?: Array<{ id: string; type: string; name: string; properties: Record<string, unknown> }>;
  }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}/build-graph`, {
      method: 'POST',
    });
  },

  // ==================== 智能问答 API ====================

  async askQuestion(question: string, sessionId?: string, workspaceId?: string): Promise<{
    session_id: string;
    answer: string;
    sources: Array<{ source: string; excerpt: string; confidence: number }>;
    intent: { type: string; confidence: number };
    sources_used: string[];
  }> {
    return fetchJson(`${API_BASE}/api/qa/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, session_id: sessionId, workspace_id: workspaceId }),
    });
  },

  async listQASessions(userId?: string, limit: number = 50): Promise<{ sessions: Array<Record<string, unknown>>; total: number; limit: number }> {
    const params = new URLSearchParams();
    if (userId) params.set('user_id', userId);
    params.set('limit', String(limit));
    return fetchJson(`${API_BASE}/api/qa/sessions?${params.toString()}`);
  },

  async getQASession(sessionId: string): Promise<{ session_id: string; messages: Array<Record<string, unknown>>; total: number }> {
    return fetchJson(`${API_BASE}/api/qa/sessions/${sessionId}`);
  },

  async closeQASession(sessionId: string): Promise<{ status: string; session_id: string }> {
    return fetchJson(`${API_BASE}/api/qa/sessions/${sessionId}`, { method: 'DELETE' });
  },

  async getQAHistory(sessionId: string, limit: number = 50): Promise<{ session_id: string; history: Array<Record<string, unknown>>; total: number }> {
    return fetchJson(`${API_BASE}/api/qa/sessions/${sessionId}/history?limit=${limit}`);
  },

  async submitQAFeedback(sessionId: string, feedback: Record<string, unknown>, rating: number): Promise<{ status: string; feedback_id: string }> {
    return fetchJson(`${API_BASE}/api/qa/sessions/${sessionId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback, rating }),
    });
  },

  async getQAStats(workspaceId?: string, startTime?: string, endTime?: string): Promise<{
    total: number;
    today: number;
    by_intent: Record<string, number>;
    by_source: Record<string, number>;
    time_distribution: Record<string, number>;
    period: { start: string | null; end: string | null };
  }> {
    const params = new URLSearchParams();
    if (workspaceId) params.set('workspace_id', workspaceId);
    if (startTime) params.set('start_time', startTime);
    if (endTime) params.set('end_time', endTime);
    return fetchJson(`${API_BASE}/api/qa/stats?${params.toString()}`);
  },

  async getUserQAStats(workspaceId?: string, limit: number = 10): Promise<{
    user_stats: Array<{ user_id: string; count: number; first_time: string; last_time: string }>;
    total_users: number;
    limit: number;
  }> {
    const params = new URLSearchParams();
    if (workspaceId) params.set('workspace_id', workspaceId);
    params.set('limit', String(limit));
    return fetchJson(`${API_BASE}/api/qa/stats/users?${params.toString()}`);
  },

  async getTopicStats(workspaceId?: string, limit: number = 20): Promise<{
    topics: Array<{ topic: string; count: number; trend: string }>;
    limit: number;
  }> {
    const params = new URLSearchParams();
    if (workspaceId) params.set('workspace_id', workspaceId);
    params.set('limit', String(limit));
    return fetchJson(`${API_BASE}/api/qa/stats/topics?${params.toString()}`);
  },

  // ==================== 用户认知引擎 API ====================

  async recognizeIntent(inputText: string, role: string = 'guest'): Promise<{
    intent: { type: string; confidence: number };
    knowledge_results: Array<{ id: string; content: unknown; relevance: number; source: string }>;
    session_id: string;
  }> {
    return fetchJson(`${API_BASE}/api/cognition/intent`, {
      method: 'POST',
      body: JSON.stringify({ input_text: inputText, role }),
    });
  },

  async getRoleView(role: string): Promise<Record<string, unknown>> {
    return fetchJson(`${API_BASE}/api/cognition/view?role=${role}`);
  },

  async navigateKnowledge(entityId: string, direction: string = 'outbound'): Promise<{
    entity_id: string;
    navigation_path: string[];
    related_entities: unknown[];
    entity_context: unknown;
  }> {
    return fetchJson(`${API_BASE}/api/cognition/navigate`, {
      method: 'POST',
      body: JSON.stringify({ entity_id: entityId, direction }),
    });
  },

  async explainDecision(decisionId: string, context: Record<string, unknown>): Promise<{
    explanation_id: string;
    query: string;
    answer: string;
    confidence: number;
    reasoning_chain: Array<{ step_id: string; step_type: string; description: string }>;
    sources: string[];
  }> {
    return fetchJson(`${API_BASE}/api/cognition/explain`, {
      method: 'POST',
      body: JSON.stringify({ decision_id: decisionId, context }),
    });
  },

  // ==================== 闭环反馈 API ====================

  async submitActionFeedback(data: {
    action_id: string;
    decision_id?: string;
    outcome: string;
    result_data?: Record<string, unknown>;
    error_message?: string;
    duration_ms?: number;
  }): Promise<{ status: string; feedback_id: string; outcome: string }> {
    return fetchJson(`${API_BASE}/api/feedback/action`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getDecisionFeedback(decisionId: string): Promise<{
    decision_id: string;
    feedback_count: number;
    feedbacks: Array<{ feedback_id: string; outcome: string; timestamp: string }>;
  }> {
    return fetchJson(`${API_BASE}/api/feedback/decision/${decisionId}`);
  },
};