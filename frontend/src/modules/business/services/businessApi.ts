import type {
  BusinessProcess, BusinessProcessFormData,
  BusinessRule, BusinessRuleFormData,
  BusinessLogic, BusinessLogicFormData,
  BusinessIndicator, BusinessIndicatorFormData,
  BusinessEntity,
} from '../types';
import { fetchJson, apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

function buildVersionQuery(ontologyId?: string, versionId?: string): string {
  const params: string[] = [];
  if (ontologyId) params.push(`ontology_id=${encodeURIComponent(ontologyId)}`);
  if (versionId) params.push(`version_id=${encodeURIComponent(versionId)}`);
  return params.length > 0 ? `?${params.join('&')}` : '';
}

export const processApi = {
  list: (ontologyId?: string, versionId?: string): Promise<BusinessProcess[]> =>
    fetchJson<BusinessProcess[]>(`${API_BASE}/api/business-processes${buildVersionQuery(ontologyId, versionId)}`),
  get: (id: string): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes/${id}`),
  create: (data: BusinessProcessFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessProcessFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`${API_BASE}/api/business-processes/${id}`),
  importYaml: (yaml: string): Promise<BusinessProcess[]> =>
    fetchJson<BusinessProcess[]>(`${API_BASE}/api/business-processes/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

export const ruleApi = {
  list: (ontologyId?: string, versionId?: string): Promise<BusinessRule[]> =>
    fetchJson<BusinessRule[]>(`${API_BASE}/api/business-rules${buildVersionQuery(ontologyId, versionId)}`),
  get: (id: string): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules/${id}`),
  create: (data: BusinessRuleFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessRuleFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`${API_BASE}/api/business-rules/${id}`),
  importYaml: (yaml: string): Promise<BusinessRule[]> =>
    fetchJson<BusinessRule[]>(`${API_BASE}/api/business-rules/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

export const logicApi = {
  list: (ontologyId?: string, versionId?: string): Promise<BusinessLogic[]> =>
    fetchJson<BusinessLogic[]>(`${API_BASE}/api/business-logics${buildVersionQuery(ontologyId, versionId)}`),
  get: (id: string): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics/${id}`),
  create: (data: BusinessLogicFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessLogicFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`${API_BASE}/api/business-logics/${id}`),
  importYaml: (yaml: string): Promise<BusinessLogic[]> =>
    fetchJson<BusinessLogic[]>(`${API_BASE}/api/business-logics/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

export const indicatorApi = {
  list: (ontologyId?: string, versionId?: string): Promise<BusinessIndicator[]> =>
    fetchJson<BusinessIndicator[]>(`${API_BASE}/api/business-indicators${buildVersionQuery(ontologyId, versionId)}`),
  get: (id: string): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators/${id}`),
  create: (data: BusinessIndicatorFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessIndicatorFormData & { ontology_id?: string; version_id?: string }): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`${API_BASE}/api/business-indicators/${id}`),
  importYaml: (yaml: string): Promise<BusinessIndicator[]> =>
    fetchJson<BusinessIndicator[]>(`${API_BASE}/api/business-indicators/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

export const entityApi = {
  listAll: (): Promise<BusinessEntity[]> =>
    fetchJson<BusinessEntity[]>(`${API_BASE}/api/business-entities`),
};

// Type definition queries for dropdown population
export const processTypeDefinitions = {
  list: (ontologyId: string) => apiClient.get(`/api/process-type-definitions?ontology_id=${ontologyId}`),
};

export const ruleTypeDefinitions = {
  list: (ontologyId: string) => apiClient.get(`/api/rule-type-definitions?ontology_id=${ontologyId}`),
};

export const functionTypeDefinitions = {
  list: (ontologyId: string) => apiClient.get(`/api/function-type-definitions?ontology_id=${ontologyId}`),
};

export const indicatorTypeDefinitions = {
  list: (ontologyId: string) => apiClient.get(`/api/indicator-type-definitions?ontology_id=${ontologyId}`),
};
