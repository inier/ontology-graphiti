import { apiClient } from '@/modules/shared/services/apiClient';

export const knowledgePageApi = {
  navigate: (entityId: string, direction: string = 'outbound', depth: number = 1) =>
    apiClient.post('/api/cognition/navigate', { entity_id: entityId, direction, depth }),

  recognizeIntent: (inputText: string, role: string = 'guest') =>
    apiClient.post('/api/cognition/recognize-intent', { input_text: inputText, role }),

  explain: (decisionId: string, context: Record<string, unknown> = {}) =>
    apiClient.post('/api/cognition/explain', { decision_id: decisionId, context }),

  getRoleView: (role: string) =>
    apiClient.get(`/api/cognition/role-view?role=${role}`),

  parseIntent: (naturalLanguage: string) =>
    apiClient.post('/api/semantic/parse-intent', { natural_language: naturalLanguage }),

  planTasks: (intent: string, entities: string[] = [], filters: Record<string, unknown> = {}) =>
    apiClient.post('/api/semantic/plan-tasks', { intent, entities, filters }),

  getSynonyms: () =>
    apiClient.get('/api/semantic/synonyms'),

  addSynonym: (canonical: string, synonym: string) =>
    apiClient.post('/api/semantic/synonyms', { canonical, synonym }),

  getExpansionRules: () =>
    apiClient.get('/api/semantic/expansion-rules'),

  addExpansionRule: (pattern: string, expansion: string) =>
    apiClient.post('/api/semantic/expansion-rules', { pattern, expansion }),

  getSessionMemory: (sessionId: string) =>
    apiClient.get(`/api/session-memory/memory/session/${sessionId}`),

  storeSessionMemory: (sessionId: string, key: string, value: unknown, tier: string = 'short_term') =>
    apiClient.post(`/api/session-memory/memory/session/${sessionId}/store`, { key, value, tier }),

  clearShortTermMemory: (sessionId: string) =>
    apiClient.post(`/api/session-memory/memory/session/${sessionId}/clear`, {}),

  retrieveLongTermMemory: (query: string, limit: number = 10) =>
    apiClient.get(`/api/session-memory/memory/long-term?query=${encodeURIComponent(query)}&limit=${limit}`),

  storeLongTermMemory: (key: string, value: unknown) =>
    apiClient.post('/api/session-memory/memory/long-term', { key, value }),

  collectFeedback: (sourceId: string, feedbackType: string = 'action_result', outcome: string = 'success', data: Record<string, unknown> = {}) =>
    apiClient.post('/api/feedback/collect', { source_id: sourceId, feedback_type: feedbackType, outcome, data }),

  analyzeFeedback: (taskId: string) =>
    apiClient.get(`/api/feedback/analysis/${taskId}`),

  aggregateFeedback: (ontologyId: string) =>
    apiClient.get(`/api/feedback/aggregate?ontology_id=${ontologyId}`),

  closeLoop: (sourceId: string, feedbackType: string = 'action_result', outcome: string = 'success', data: Record<string, unknown> = {}) =>
    apiClient.post('/api/feedback/close-loop', { source_id: sourceId, feedback_type: feedbackType, outcome, data }),

  listTools: (category?: string) =>
    apiClient.get(`/api/tools${category ? `?category=${category}` : ''}`),

  registerTool: (name: string, description: string, category: string = 'general') =>
    apiClient.post('/api/tools/register', { name, description, category }),

  invokeTool: (toolId: string, params: Record<string, unknown> = {}) =>
    apiClient.post(`/api/tools/${toolId}/invoke`, { params }),

  discoverTools: (query: string, topK: number = 5) =>
    apiClient.post('/api/tools/discover', { query, top_k: topK }),

  listHooks: (page: number = 1, pageSize: number = 10) =>
    apiClient.get(`/api/hooks?page=${page}&page_size=${pageSize}`),

  registerHook: (name: string, hookType: string, script: string, phase: string = 'post') =>
    apiClient.post('/api/hooks/register', { name, hook_type: hookType, script, phase }),

  unregisterHook: (hookId: string) =>
    apiClient.delete(`/api/hooks/${hookId}`),

  enableHook: (hookId: string) =>
    apiClient.post(`/api/hooks/${hookId}/enable`, {}),

  disableHook: (hookId: string) =>
    apiClient.post(`/api/hooks/${hookId}/disable`, {}),
};
