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
  duration_ms?: number | null;
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
  const token = localStorage.getItem('token');
  const authHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) authHeaders['Authorization'] = `Bearer ${token}`;
  const mergedOptions: RequestInit = { ...options, headers: { ...authHeaders, ...(options?.headers as Record<string, string>) } };
  const response = await fetch(url, mergedOptions);
  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }
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

  // ==================== 旧版场景 API（兼容） ====================

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

  async getEntities(scenarioId: string, workspaceId?: string): Promise<Entity[]> {
    const params = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
    const data = await fetchJson<{ entities: Entity[] }>(`${API_BASE}/api/scenarios/${scenarioId}/entities${params}`);
    return data.entities;
  },

  async getRelations(scenarioId: string, workspaceId?: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
    const params = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
    const data = await fetchJson<unknown>(`${API_BASE}/api/scenarios/${scenarioId}/relations${params}`);
    
    if (!isRelationsResponse(data)) {
      console.warn('Invalid relations response format:', data);
      return { nodes: [], edges: [] };
    }
    
    const nodes = safeCastArray<GraphNode>(data.nodes, isGraphNode);
    const edges = safeCastArray<GraphEdge>(data.links, isGraphEdge);
    
    return { nodes, edges };
  },

  // ==================== 本体摄入 API ====================

  /**
   * 统一的数据摄入方法
   * 
   * 支持多种摄入类型，使用统一的调用格式
   * 
   * @param options 摄入选项
   * @param options.type 摄入类型
   * @param options.data 摄入数据（根据 type 不同，数据结构不同）
   * @param options.scenario_id 场景 ID（可选）
   * 
   * @returns 摄入结果
   * 
   * @example 文本摄入
   * ```javascript
   * await api.ingest({
   *   type: 'manual',
   *   data: '红方部队进攻蓝方阵地',
   *   scenario_id: currentScenario
   * });
   * ```
   * 
   * @example 新闻摄入
   * ```javascript
   * // 方式1：直接传递 URL 字符串
   * await api.ingest({
   *   type: 'news',
   *   data: 'https://example.com/news',
   *   scenario_id: currentScenario
   * });
   * 
   * // 方式2：传递包含详细参数的对象
   * await api.ingest({
   *   type: 'news',
   *   data: {
   *     url: 'https://example.com/news',
   *     event_context: '军事冲突',
   *     max_sources: 5
   *   },
   *   scenario_id: currentScenario
   * });
   * ```
   * 
   * @example JSON摄入
   * ```javascript
   * await api.ingest({
   *   type: 'json',
   *   data: '{"entities": [...], "relations": [...]}',
   *   scenario_id: currentScenario
   * });
   * ```
   * 
   * @example 自然语言摄入
   * ```javascript
   * await api.ingest({
   *   type: 'natural_language',
   *   data: '美军航母舰队在南海进行军事演习',
   *   scenario_id: currentScenario
   * });
   * ```
   * 
   * @example 手动录入
   * ```javascript
   * await api.ingest({
   *   type: 'manual',
   *   data: {
   *     title: '事件标题',
   *     description: '事件描述'
   *   },
   *   scenario_id: currentScenario
   * });
   * ```
   * 
   * @example 随机生成
   * ```javascript
   * await api.ingest({
   *   type: 'random',
   *   data: {
   *     parties: ['蓝方', '红方'],
   *     count: 3
   *   },
   *   scenario_id: currentScenario
   * });
   * ```
   */
  async ingest(options: {
    type: 'news' | 'manual' | 'json' | 'natural_language' | 'random';
    data: any;
    scenario_id?: string;
  }): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    switch (options.type) {
      case 'news':
        // 统一使用 data 字段
        return this.ingestFromNews({
          data: options.data,
          scenario_id: options.scenario_id
        });
      case 'manual':
        // data 可以是字符串或表单对象
        return this.ingestFromManual(options.data, options.scenario_id);
      case 'json':
        // data 是 JSON 字符串
        return this.ingestFromJson(options.data, options.scenario_id);
      case 'natural_language':
        // data 是自然语言文本
        return this.ingestFromNaturalLanguage(options.data, options.scenario_id);
      case 'random':
        // data 是包含 parties 等字段的对象
        return this.ingestRandomEvents({
          data: options.data,
          scenario_id: options.scenario_id
        });
      default:
        throw new Error(`Unknown ingest type: ${options.type}`);
    }
  },

  async ingestOntology(data: {
    source_type: string;
    data?: string;
    url?: string;
    query?: string;
    form_data?: Record<string, unknown>;
    json_data?: string;
    text?: string;
    parties?: string[];
    scenario_context?: Record<string, unknown>;
    count?: number;
    event_context?: string;
    max_sources?: number;
    scenario_id?: string;
  }): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async ingestFromNews(request: {
    data: string | { url?: string; query?: string; event_context?: string; max_sources?: number };
    scenario_id?: string;
  }): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/news`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async ingestFromManual(data: string | Record<string, unknown>, scenarioId?: string): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/manual`, {
      method: 'POST',
      body: JSON.stringify({ data, scenario_id: scenarioId }),
    });
  },

  async ingestFromJson(data: string, scenarioId?: string): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/json`, {
      method: 'POST',
      body: JSON.stringify({ data, scenario_id: scenarioId }),
    });
  },

  async ingestFromNaturalLanguage(data: string, scenarioId?: string): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/natural-language`, {
      method: 'POST',
      body: JSON.stringify({ data, scenario_id: scenarioId }),
    });
  },

  async ingestRandomEvents(request: {
    data: { parties: string[]; scenario_context?: Record<string, unknown>; count?: number; generator_type?: string };
    scenario_id?: string;
  }): Promise<{ 
    ingest_id: string; 
    status: string;
    source_details?: Record<string, unknown>;
    original_content?: string;
    extracted_data?: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/random`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async getRandomGeneratorTypes(): Promise<{
    types: Array<{
      type: string;
      name: string;
      description: string;
    }>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/random/generators`);
  },

  async getIngestStatus(ingestId: string): Promise<{
    id: string;
    source: string;
    status: string;
    record_count: number;
    processed_count: number;
    failed_count: number;
    start_time: string;
    end_time?: string;
    duration_seconds?: number;
    errors?: Array<{ source: string; error: string }>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/${ingestId}`);
  },

  async getIngestHistory(limit: number = 100, scenarioId?: string): Promise<Array<{
    id: string;
    source: string;
    status: string;
    record_count: number;
    processed_count: number;
    failed_count: number;
    start_time: string;
    end_time?: string;
    duration_seconds?: number;
  }>> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (scenarioId) {
      params.append('scenario_id', scenarioId);
    }
    return fetchJson(`${API_BASE}/api/ontology/ingest?${params.toString()}`);
  },

  // ==================== 本体构建 API ====================

  async getBuildStatus(buildId: string): Promise<{
    build_id: string;
    status: string;
    document_id: string;
    version_info?: {
      version_id: string;
      commit_message: string;
    };
    ingest_id: string;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/builds/${buildId}`);
  },

  async getBuildHistory(limit: number = 50): Promise<Array<{
    build_id: string;
    status: string;
    document_id: string;
    version_info?: {
      version_id: string;
      commit_message: string;
    };
    ingest_id: string;
    ingest_source: string;
    ingest_time: string;
  }>> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/builds?limit=${limit}`);
  },

  // ==================== 处理日志 API ====================

  async getProcessLogs(ingestId: string): Promise<Array<{
    id: string;
    ingest_id: string;
    stage: string;
    operation: string;
    details: Record<string, unknown>;
    status: string;
    error_message?: string;
    duration_ms?: number;
    timestamp: string;
  }>> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/${ingestId}/logs`);
  },

  async getFullIngestRecord(ingestId: string): Promise<{
    id: string;
    source: string;
    status: string;
    start_time: string;
    end_time?: string;
    logs: Array<{
      id: string;
      ingest_id: string;
      stage: string;
      operation: string;
      details: Record<string, unknown>;
      status: string;
      error_message?: string;
      duration_ms?: number;
      timestamp: string;
    }>;
    builds: Array<{
      build_id: string;
      status: string;
      document_id?: string;
      version_info?: {
        version_id: string;
        commit_message: string;
      };
      entity_count?: number;
      relation_count?: number;
      event_count?: number;
    }>;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/${ingestId}/full`);
  },

  async buildOntology(ingestId: string, scenarioId?: string): Promise<{
    build_id: string;
    status: string;
    document_id?: string;
    version_info?: {
      version_id: string;
      commit_message: string;
    };
    entity_count?: number;
    relation_count?: number;
    event_count?: number;
    error?: string;
  }> {
    const params = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : '';
    return fetchJson(`${API_BASE}/api/ontology/ingest/${ingestId}/build${params}`, {
      method: 'POST',
    });
  },

  async getIngestBuildHistory(ingestId: string): Promise<{
    id: string;
    ingest_id: string;
    build_id: string;
    version_id?: string;
    document_id?: string;
    entity_count: number;
    relation_count: number;
    event_count: number;
    status: string;
    start_time: string;
    end_time?: string;
    duration_seconds?: number;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/${ingestId}/build-history`);
  },

  // ==================== 本体版本 API ====================

  async getVersions(scenarioId?: string, limit: number = 50): Promise<Array<{
    version_id: string;
    scenario_id: string;
    created_at: string;
    commit_message: string;
  }>> {
    const params = new URLSearchParams();
    if (scenarioId) params.set('scenario_id', scenarioId);
    params.set('limit', String(limit));
    return fetchJson(`${API_BASE}/api/ontology/ingest/versions?${params.toString()}`);
  },

  async rollbackVersion(versionId: string, scenarioId: string = 'default'): Promise<{
    status: string;
    version_id: string;
    message: string;
  }> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/versions/rollback?version_id=${versionId}&scenario_id=${scenarioId}`, {
      method: 'POST',
    });
  },

  // ==================== 本体文档 API ====================

  async getOntologySchema(): Promise<Record<string, unknown>> {
    return fetchJson(`${API_BASE}/api/ontology/schema`);
  },

  async getOntologyDocuments(scenarioId?: string, limit: number = 100): Promise<Array<Record<string, unknown>>> {
    const params = new URLSearchParams();
    if (scenarioId) params.set('scenario_id', scenarioId);
    params.set('limit', String(limit));
    return fetchJson(`${API_BASE}/api/ontology/ingest/documents/list?${params.toString()}`);
  },

  async getOntologyDocument(docId: string): Promise<Record<string, unknown>> {
    return fetchJson(`${API_BASE}/api/ontology/ingest/documents/${docId}`);
  },

  // ==================== 旧版摄入 API（兼容） ====================

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
    const data = await fetchJson<{ workspaces: Workspace[]; total: number }>(`${API_BASE}/api/workspaces?page_size=100`);
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
    if (params?.event_type) searchParams.append('event_types', params.event_type);
    if (params?.severity) {
      const sev = params.severity === 'warning' ? 'warn' : params.severity;
      searchParams.append('severities', sev);
    }
    if (params?.actor_id) searchParams.append('actor_ids', params.actor_id);
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

  // ==================== 场景管理 API（新版） ====================

  async createScenarioInWorkspace(workspaceId: string, name: string, description?: string, ontologyId?: string): Promise<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios`, {
      method: 'POST',
      body: JSON.stringify({ name, description, ontology_id: ontologyId }),
    });
  },

  async getScenariosInWorkspace(workspaceId: string): Promise<{ scenarios: Array<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; current_ontology_version?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }>; workspace_id: string; total: number }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios`);
  },

  async getScenarioInWorkspace(workspaceId: string, scenarioId: string): Promise<{ scenario_id: string; name: string; description: string; workspace_id: string; ontology_id?: string; current_ontology_version?: string; doc_count: number; event_count: number; entity_count: number; created_at: string; updated_at: string }> {
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

  async getScenarioOntologyVersions(workspaceId: string, scenarioId: string): Promise<Array<{
    version_id: string;
    doc_id: string;
    doc_type: string;
    parent_version?: string;
    commit_message: string;
    created_at: string;
    entity_count: number;
    relation_count: number;
    event_count: number;
  }>> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}/versions`);
  },

  async switchScenarioOntologyVersion(workspaceId: string, scenarioId: string, versionId: string): Promise<{
    status: string;
    message: string;
  }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}/switch-version`, {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId }),
    });
  },

  async commitScenarioOntologyVersion(workspaceId: string, scenarioId: string, commitMessage: string = ''): Promise<{
    version_id: string;
    ontology_id: string;
    commit_message: string;
    created_at: string;
    entity_count: number;
    relation_count: number;
    event_count: number;
  }> {
    const params = new URLSearchParams();
    if (commitMessage) params.set('message', commitMessage);
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}/commit-version?${params.toString()}`, {
      method: 'POST',
    });
  },

  async getVersionOntologyData(workspaceId: string, scenarioId: string, versionId: string): Promise<{
    version_id: string;
    entities: Array<Record<string, unknown>>;
    relations: Array<Record<string, unknown>>;
    events: Array<Record<string, unknown>>;
  }> {
    return fetchJson(`${API_BASE}/api/workspaces/${workspaceId}/scenarios/${scenarioId}/versions/${versionId}/data`);
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

  // ==================== Skill 管理 API ====================

  async listSkills(params?: {
    page?: number;
    page_size?: number;
    skill_type?: string;
    status?: string;
    category?: string;
  }): Promise<{
    skills: Array<{
      skill_id: string;
      name: string;
      type: string;
      status: string;
      category: string;
    }>;
    page: number;
    page_size: number;
    total: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.skill_type) searchParams.set('skill_type', params.skill_type);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.category) searchParams.set('category', params.category);
    const queryString = searchParams.toString();
    return fetchJson(`${API_BASE}/api/skill/skills${queryString ? `?${queryString}` : ''}`);
  },

  async scanSkillsDirectory(): Promise<{
    skills: Array<{
      name: string;
      category: string;
      path: string;
      files: string[];
      description?: string;
      parsed?: Record<string, unknown>;
    }>;
    total: number;
  }> {
    return fetchJson(`${API_BASE}/api/skill/scan`);
  },

  async getAllSkills(): Promise<{
    registered: Array<Record<string, unknown>>;
    scanned: Array<Record<string, unknown>>;
    total_registered: number;
    total_scanned: number;
  }> {
    return fetchJson(`${API_BASE}/api/skill/all`);
  },

  async getSkillCategories(): Promise<{
    categories: Array<{
      name: string;
      skill_count: number;
      path: string;
    }>;
  }> {
    return fetchJson(`${API_BASE}/api/skill/categories`);
  },

  async registerSkill(data: {
    name: string;
    skill_type: string;
    description?: string;
    category?: string;
    tags?: string[];
  }): Promise<{
    skill_id: string;
    name: string;
    type: string;
    status: string;
    created_at: string;
  }> {
    const searchParams = new URLSearchParams();
    searchParams.set('name', data.name);
    searchParams.set('skill_type', data.skill_type);
    if (data.description) searchParams.set('description', data.description);
    if (data.category) searchParams.set('category', data.category);
    if (data.tags) searchParams.set('tags', JSON.stringify(data.tags));
    return fetchJson(`${API_BASE}/api/skill/skills?${searchParams.toString()}`, {
      method: 'POST',
    });
  },

  async uploadSkillFile(file: File, category: string = 'custom'): Promise<{
    status: string;
    data: {
      filename: string;
      category: string;
      path: string;
      size: number;
      parsed?: Record<string, unknown>;
    };
  }> {
    const formData = new FormData();
    formData.append('skill_file', file);
    formData.append('category', category);

    const response = await fetch(`${API_BASE}/api/skill/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  },

  async toggleSkill(skillName: string, enabled: boolean): Promise<{
    status: string;
    message?: string;
    enabled?: boolean;
    skill_id?: string;
  }> {
    return fetchJson(`${API_BASE}/api/skill/toggle/${skillName}?enabled=${enabled}`, {
      method: 'POST',
    });
  },

  async activateSkill(skillId: string): Promise<{
    skill_id: string;
    status: string;
  }> {
    return fetchJson(`${API_BASE}/api/skill/skills/${skillId}/activate`, {
      method: 'POST',
    });
  },

  async deactivateSkill(skillId: string): Promise<{
    skill_id: string;
    status: string;
  }> {
    return fetchJson(`${API_BASE}/api/skill/skills/${skillId}/deactivate`, {
      method: 'POST',
    });
  },

  async getLoadedSkills(): Promise<{
    skills: string[];
  }> {
    return fetchJson(`${API_BASE}/api/skill/skills/loaded`);
  },

  async saveSkillContent(skillName: string, category: string, content: string): Promise<{
    status: string;
    skill_id?: string;
    path?: string;
  }> {
    return fetchJson(`${API_BASE}/api/skill/skills/save`, {
      method: 'POST',
      body: JSON.stringify({
        name: skillName,
        category: category,
        content: content,
      }),
    });
  },

  // ==================== 事件模拟器 API ====================

  async getEventTemplates(): Promise<{
    templates: Array<{
      template_id: string;
      name: string;
      description: string;
      event_type: string;
      parameters: Record<string, unknown>;
    }>;
    total: number;
  }> {
    return fetchJson(`${API_BASE}/api/event-simulator/templates`);
  },

  async createEventTemplate(data: {
    name: string;
    description: string;
    event_type: string;
    parameters: Record<string, unknown>;
  }): Promise<{
    template_id: string;
    name: string;
    event_type: string;
    created_at: string;
  }> {
    return fetchJson(`${API_BASE}/api/event-simulator/templates`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async generateEvents(data: {
    template_id?: string;
    count?: number;
    region?: string;
    event_types?: string[];
    parameters?: Record<string, unknown>;
    scenario_id?: string;
  }): Promise<{
    task_id: string;
    events_generated: number;
    events: Array<{
      event_id: string;
      type: string;
      description: string;
      timestamp: string;
      status: string;
    }>;
  }> {
    return fetchJson(`${API_BASE}/api/event-simulator/generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async adoptEvent(eventId: string, scenarioId?: string): Promise<{
    status: string;
    event_id: string;
    message: string;
  }> {
    const params = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : '';
    return fetchJson(`${API_BASE}/api/event-simulator/events/${eventId}/adopt${params}`, {
      method: 'POST',
    });
  },

  async adoptEventsBulk(eventIds: string[], scenarioId?: string): Promise<{
    status: string;
    adopted_count: number;
    failed_count: number;
    results: Array<{ event_id: string; status: string }>;
  }> {
    const params = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : '';
    return fetchJson(`${API_BASE}/api/event-simulator/events/adopt-bulk${params}`, {
      method: 'POST',
      body: JSON.stringify({ event_ids: eventIds }),
    });
  },

  async listSimulationEvents(params?: {
    status?: string;
    event_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    events: Array<{
      event_id: string;
      type: string;
      description: string;
      timestamp: string;
      status: string;
      source: string;
    }>;
    total: number;
    limit: number;
    offset: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.event_type) searchParams.set('event_type', params.event_type);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    const queryString = searchParams.toString();
    return fetchJson(`${API_BASE}/api/event-simulator/events${queryString ? `?${queryString}` : ''}`);
  },

  async controlSimulationTime(data: {
    action: 'start' | 'pause' | 'resume' | 'stop' | 'set_speed';
    speed?: number;
    timestamp?: string;
  }): Promise<{
    status: string;
    action: string;
    current_time?: string;
    speed?: number;
  }> {
    return fetchJson(`${API_BASE}/api/event-simulator/time-control`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getSimulationStatus(): Promise<{
    status: string;
    current_time: string;
    speed: number;
    events_generated: number;
    events_adopted: number;
    events_pending: number;
  }> {
    return fetchJson(`${API_BASE}/api/event-simulator/status`);
  },

  // ==================== OPA 策略管理 API ====================

  async listPolicies(params?: {
    status?: string;
    category?: string;
    limit?: number;
  }): Promise<{
    policies: Array<{
      policy_id: string;
      name: string;
      description: string;
      category: string;
      status: string;
      version: string;
      updated_at: string;
    }>;
    total: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.category) searchParams.set('category', params.category);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    const queryString = searchParams.toString();
    return fetchJson(`${API_BASE}/api/policies${queryString ? `?${queryString}` : ''}`);
  },

  async createPolicy(data: {
    name: string;
    description: string;
    markdown_content: string;
    category?: string;
  }): Promise<{
    policy_id: string;
    name: string;
    status: string;
    rego_content: string;
  }> {
    return fetchJson(`${API_BASE}/api/policies`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getPolicy(policyId: string): Promise<{
    policy_id: string;
    name: string;
    description: string;
    markdown_content: string;
    rego_content: string;
    category: string;
    status: string;
    version: string;
    created_at: string;
    updated_at: string;
  }> {
    return fetchJson(`${API_BASE}/api/policies/${policyId}`);
  },

  async updatePolicy(policyId: string, data: {
    name?: string;
    description?: string;
    markdown_content?: string;
    status?: string;
  }): Promise<{
    policy_id: string;
    name: string;
    status: string;
    version: string;
  }> {
    return fetchJson(`${API_BASE}/api/policies/${policyId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async togglePolicyStatus(policyId: string, enabled: boolean): Promise<{
    policy_id: string;
    status: string;
  }> {
    return fetchJson(`${API_BASE}/api/policies/${policyId}/toggle?enabled=${enabled}`, {
      method: 'POST',
    });
  },

  // ==================== 系统监控 API ====================

  async getSystemMetrics(): Promise<{
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    uptime_seconds: number;
    active_connections: number;
    request_count: number;
    error_count: number;
  }> {
    return fetchJson(`${API_BASE}/api/v1/monitoring/performance`);
  },

  async getSystemHealth(): Promise<{
    status: string;
    openharness_v1: boolean;
    openharness_v2: Record<string, unknown>;
    version: string;
  }> {
    return fetchJson(`${API_BASE}/health`);
  },

  // ==================== 角色管理 API ====================

  async listRoles(params?: {
    page?: number;
    page_size?: number;
  }): Promise<{
    roles: Array<{
      role_id: string;
      name: string;
      description: string;
      permissions: string[];
      created_at: string;
    }>;
    total: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    const queryString = searchParams.toString();
    const data = await fetchJson<unknown>(`${API_BASE}/api/roles${queryString ? `?${queryString}` : ''}`);
    if (Array.isArray(data)) {
      return {
        roles: data.map((r: any) => ({
          role_id: r.id,
          name: r.name,
          description: r.description || '',
          permissions: (r.permissions || []).map((p: any) => typeof p === 'string' ? p : p.id || p.name),
          created_at: r.created_at || '',
        })),
        total: data.length,
      };
    }
    return data as any;
  },

  async createRole(data: {
    name: string;
    description: string;
    permissions?: string[];
  }): Promise<{
    role_id: string;
    name: string;
    description: string;
    permissions: string[];
    created_at: string;
  }> {
    return fetchJson(`${API_BASE}/api/roles`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateRole(roleId: string, data: {
    name?: string;
    description?: string;
    permissions?: string[];
  }): Promise<{
    role_id: string;
    name: string;
    description: string;
    permissions: string[];
  }> {
    return fetchJson(`${API_BASE}/api/roles/${roleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteRole(roleId: string): Promise<{ status: string; message: string }> {
    return fetchJson(`${API_BASE}/api/roles/${roleId}`, {
      method: 'DELETE',
    });
  },

  // ==================== Agent API ====================

  async initAgent(config?: Record<string, unknown>): Promise<{
    status: string;
    agent_id: string;
    tools_available: number;
  }> {
    return fetchJson(`${API_BASE}/api/agent/init`, {
      method: 'POST',
      body: JSON.stringify(config || {}),
    });
  },

  async runAgent(data: {
    input: string;
    agent_id?: string;
    workspace_id?: string;
  }): Promise<{
    status: string;
    result: string;
    agent_id: string;
    execution_time_ms: number;
  }> {
    return fetchJson(`${API_BASE}/api/agent/run`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getAgentStatus(): Promise<{
    status: string;
    agents: Array<{ agent_id: string; type: string; status: string }>;
  }> {
    return fetchJson(`${API_BASE}/api/agent/status`);
  },

  async listAgentTools(): Promise<{
    tools: Array<{ name: string; description: string; category: string }>;
    total: number;
  }> {
    return fetchJson(`${API_BASE}/api/agent/tools`);
  },

  // ==================== 对话 API (agent chat) ====================

  async agentChat(data: {
    message: string;
    session_id?: string;
    workspace_id?: string;
    role?: string;
  }): Promise<{
    session_id: string;
    response: string;
    agent_type: string;
    thinking_steps: Array<{ step: string; detail: string }>;
    tools_used: string[];
  }> {
    return fetchJson(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // ==================== OMS 本体元数据服务 ====================

  async listObjectTypes(activeOnly = true): Promise<any[]> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types?active_only=${activeOnly}`);
  },

  async getObjectType(typeId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types/${typeId}`);
  },

  async createObjectType(data: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateObjectType(typeId: string, data: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types/${typeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteObjectType(typeId: string): Promise<void> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types/${typeId}`, { method: 'DELETE' });
  },

  async listActionTypes(targetType?: string): Promise<any[]> {
    const params = targetType ? `?target_type=${targetType}` : '';
    return fetchJson(`${API_BASE}/api/ontology/oms/action-types${params}`);
  },

  async getActionType(actionTypeId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/action-types/${actionTypeId}`);
  },

  async createActionType(data: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/action-types`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateActionType(actionTypeId: string, data: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/ontology/oms/action-types/${actionTypeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteActionType(actionTypeId: string): Promise<void> {
    return fetchJson(`${API_BASE}/api/ontology/oms/action-types/${actionTypeId}`, { method: 'DELETE' });
  },

  async bindActionToObjectType(typeId: string, actionTypeId: string): Promise<void> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types/${typeId}/actions/${actionTypeId}`, { method: 'POST' });
  },

  async unbindActionFromObjectType(typeId: string, actionTypeId: string): Promise<void> {
    return fetchJson(`${API_BASE}/api/ontology/oms/object-types/${typeId}/actions/${actionTypeId}`, { method: 'DELETE' });
  },

  // ==================== 语义地图 API ====================

  async createSemanticMap(data: {
    name: string;
    description?: string;
    ontology_version_id: string;
    ontology_id: string;
    scenario_id?: string;
    created_by?: string;
    generation_config?: Record<string, unknown>;
  }): Promise<{
    id: string;
    name: string;
    status: string;
    objects: Array<{
      object_id: string;
      entity_id: string;
      object_type: string;
      name: string;
      name_en: string;
      aliases: string[];
      properties: Record<string, unknown>;
      type_definition_id: string | null;
      type_definition_name: string | null;
      relation_ids: string[];
      cluster: string | null;
      confidence: number;
    }>;
    relations: Array<{
      relation_id: string;
      source_object_id: string;
      target_object_id: string;
      relation_type: string;
      display_name: string;
      properties: Record<string, unknown>;
      is_bidirectional: boolean;
    }>;
    clusters: Array<{
      cluster_id: string;
      cluster_name: string;
      cluster_type: string;
      object_ids: string[];
      properties: Record<string, unknown>;
    }>;
    statistics: {
      total_objects: number;
      total_relations: number;
      total_clusters: number;
      objects_by_type: Record<string, number>;
      relations_by_type: Record<string, number>;
      avg_relations_per_object: number;
      coverage_score: number;
    };
    created_at: string;
  }> {
    return fetchJson(`${API_BASE}/api/semantic-map`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async listSemanticMaps(params?: {
    ontology_version_id?: string;
    ontology_id?: string;
    scenario_id?: string;
    limit?: number;
  }): Promise<{
    semantic_maps: Array<{
      id: string;
      name: string;
      description: string;
      ontology_version_id: string;
      ontology_id: string;
      scenario_id: string | null;
      status: string;
      total_objects: number;
      total_relations: number;
      total_clusters: number;
      created_at: string;
      created_by: string;
    }>;
    total: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.ontology_version_id) searchParams.set('ontology_version_id', params.ontology_version_id);
    if (params?.ontology_id) searchParams.set('ontology_id', params.ontology_id);
    if (params?.scenario_id) searchParams.set('scenario_id', params.scenario_id);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    return fetchJson(`${API_BASE}/api/semantic-map${qs ? '?' + qs : ''}`);
  },

  async getSemanticMap(mapId: string): Promise<{
    id: string;
    name: string;
    description: string;
    ontology_version_id: string;
    ontology_id: string;
    scenario_id: string | null;
    status: string;
    objects: Array<{
      object_id: string;
      entity_id: string;
      object_type: string;
      name: string;
      name_en: string;
      aliases: string[];
      properties: Record<string, unknown>;
      type_definition_id: string | null;
      type_definition_name: string | null;
      relation_ids: string[];
      cluster: string | null;
      confidence: number;
    }>;
    relations: Array<{
      relation_id: string;
      source_object_id: string;
      target_object_id: string;
      relation_type: string;
      display_name: string;
      properties: Record<string, unknown>;
      is_bidirectional: boolean;
    }>;
    clusters: Array<{
      cluster_id: string;
      cluster_name: string;
      cluster_type: string;
      object_ids: string[];
      properties: Record<string, unknown>;
    }>;
    statistics: {
      total_objects: number;
      total_relations: number;
      total_clusters: number;
      objects_by_type: Record<string, number>;
      relations_by_type: Record<string, number>;
      avg_relations_per_object: number;
      coverage_score: number;
    };
    error_message: string | null;
    created_at: string;
    created_by: string;
  }> {
    return fetchJson(`${API_BASE}/api/semantic-map/${mapId}`);
  },

  async getSemanticMapGraph(mapId: string): Promise<{
    nodes: Array<{
      id: string;
      entity_id: string;
      name: string;
      type: string;
      cluster: string | null;
      properties: Record<string, unknown>;
      type_definition_id: string | null;
      type_definition_name: string | null;
    }>;
    edges: Array<{
      id: string;
      source: string;
      target: string;
      type: string;
      display_name: string;
      properties: Record<string, unknown>;
    }>;
    clusters: Array<{
      cluster_id: string;
      cluster_name: string;
      cluster_type: string;
      object_ids: string[];
      properties: Record<string, unknown>;
    }>;
    statistics: Record<string, unknown>;
  }> {
    return fetchJson(`${API_BASE}/api/semantic-map/${mapId}/graph`);
  },

  async regenerateSemanticMap(mapId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/semantic-map/${mapId}/regenerate`, {
      method: 'POST',
    });
  },

  async deleteSemanticMap(mapId: string): Promise<{ status: string; message: string }> {
    return fetchJson(`${API_BASE}/api/semantic-map/${mapId}`, {
      method: 'DELETE',
    });
  },

  // ==================== OSv2 对象服务 ====================

  async queryObjects(query: {
    object_type?: string;
    filters?: any[];
    limit?: number;
    offset?: number;
    include_links?: boolean;
    include_actions?: boolean;
  }): Promise<{ results: any[]; total: number; limit: number; offset: number }> {
    return fetchJson(`${API_BASE}/api/objects/query`, {
      method: 'POST',
      body: JSON.stringify(query),
    });
  },

  async semanticObjectSearch(query: {
    query_text: string;
    object_type?: string;
    top_k?: number;
    include_links?: boolean;
  }): Promise<{ results: any[]; total: number }> {
    return fetchJson(`${API_BASE}/api/objects/semantic`, {
      method: 'POST',
      body: JSON.stringify(query),
    });
  },

  async getObject(objectId: string, objectType?: string): Promise<any> {
    const params = objectType ? `?object_type=${objectType}` : '';
    return fetchJson(`${API_BASE}/api/objects/${objectId}${params}`);
  },

  // ==================== Action Service 动作服务 ====================

  async submitAction(request: {
    action_type_id: string;
    target_object_id: string;
    target_object_type: string;
    parameters?: Record<string, any>;
    requested_by?: string;
    reason?: string;
    agent_id?: string;
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/actions/submit`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async approveAction(recordId: string, approval: {
    approved: boolean;
    approver?: string;
    comment?: string;
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/actions/${recordId}/approve`, {
      method: 'POST',
      body: JSON.stringify(approval),
    });
  },

  async listActionRecords(status?: string, limit = 50, offset = 0): Promise<any[]> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (status) params.set('status', status);
    return fetchJson(`${API_BASE}/api/actions/records?${params}`);
  },

  async getActionRecord(recordId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/actions/records/${recordId}`);
  },

  async listActionsByTarget(targetObjectId: string, limit = 20): Promise<any[]> {
    return fetchJson(`${API_BASE}/api/actions/target/${targetObjectId}?limit=${limit}`);
  },

  // ==================== Perception Hub 感知服务 ====================

  async ingestPerception(event: { source_type: string; raw_content: string; metadata?: any; workspace_id?: string }): Promise<any> {
    return fetchJson(`${API_BASE}/api/perception/ingest`, {
      method: 'POST',
      body: JSON.stringify(event),
    });
  },

  async ingestManualV2(content: string, sourceType = 'manual', metadata?: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/perception/ingest/manual`, {
      method: 'POST',
      body: JSON.stringify({ content, source_type: sourceType, metadata }),
    });
  },

  async ingestWebhook(payload: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/perception/ingest/webhook`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async observeAndProcess(): Promise<any[]> {
    return fetchJson(`${API_BASE}/api/perception/observe`, { method: 'POST' });
  },

  async getPerceptionStatus(): Promise<any> {
    return fetchJson(`${API_BASE}/api/perception/status`);
  },

  async toggleObserver(name: string, enabled: boolean): Promise<any> {
    return fetchJson(`${API_BASE}/api/perception/observers/${name}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    });
  },

  // ==================== Decision Pipeline 决策管道 ====================

  async executeDecisionPipeline(input: {
    query: string;
    context?: any;
    workspace_id?: string;
    scenario_id?: string;
    agent_id?: string;
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/decision-pipeline/execute`, {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  async analyzeOnly(input: { query: string; context?: any }): Promise<any> {
    return fetchJson(`${API_BASE}/api/decision-pipeline/analyze`, {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  // ==================== Simulation Sandbox 模拟沙盒 ====================

  async simulateWhatIf(scenario: {
    action_type_id: string;
    target_object_id: string;
    target_object_type: string;
    parameters?: any;
    variant_parameters?: any[];
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/whatif/simulate`, {
      method: 'POST',
      body: JSON.stringify(scenario),
    });
  },

  async compareWhatIfScenarios(scenarios: any[]): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/whatif/compare`, {
      method: 'POST',
      body: JSON.stringify(scenarios),
    });
  },

  async createDeductionScenario(data: {
    name: string; description?: string; source_recommendation_id?: string;
    source_analysis_id?: string; target_object_id?: string; target_object_type?: string;
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios`, {
      method: 'POST', body: JSON.stringify(data),
    });
  },

  async listDeductionScenarios(params?: { page?: number; page_size?: number; status?: string; name?: string; target_object_type?: string }): Promise<any> {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    if (params?.status) query.set('status', params.status);
    if (params?.name) query.set('name', params.name);
    if (params?.target_object_type) query.set('target_object_type', params.target_object_type);
    const qs = query.toString();
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios${qs ? '?' + qs : ''}`);
  },

  async getDeductionScenario(scenarioId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}`);
  },

  async deleteDeductionScenario(scenarioId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}`, {
      method: 'DELETE',
    });
  },

  async loadDeductionConditions(scenarioId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/conditions`, {
      method: 'POST',
    });
  },

  async updateDeductionCondition(scenarioId: string, conditionId: string, value: any): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/conditions/${conditionId}`, {
      method: 'PUT', body: JSON.stringify({ value }),
    });
  },

  async addDeductionChain(scenarioId: string, data: {
    name: string; description?: string; steps: any[]; conditions?: any[];
  }): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/chains`, {
      method: 'POST', body: JSON.stringify(data),
    });
  },

  async simulateDeductionChain(scenarioId: string, chainId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/chains/${chainId}/simulate`, {
      method: 'POST',
    });
  },

  async simulateAllDeductionChains(scenarioId: string): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/simulate-all`, {
      method: 'POST',
    });
  },

  async compareDeductionChains(scenarioId: string, chainIds: string[]): Promise<any> {
    return fetchJson(`${API_BASE}/api/simulation/deduction/scenarios/${scenarioId}/compare`, {
      method: 'POST', body: JSON.stringify({ chain_ids: chainIds }),
    });
  },
};

export const apiService = api;
export default api;