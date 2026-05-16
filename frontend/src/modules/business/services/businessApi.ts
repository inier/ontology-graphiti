import type {
  BusinessProcess, BusinessProcessFormData,
  BusinessRule, BusinessRuleFormData,
  BusinessLogic, BusinessLogicFormData,
  BusinessIndicator, BusinessIndicatorFormData,
  BusinessEntity,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// 业务过程 API
export const processApi = {
  list: (): Promise<BusinessProcess[]> =>
    fetchJson<BusinessProcess[]>(`${API_BASE}/api/business-processes`),
  get: (id: string): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes/${id}`),
  create: (data: BusinessProcessFormData): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessProcessFormData): Promise<BusinessProcess> =>
    fetchJson<BusinessProcess>(`${API_BASE}/api/business-processes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/business-processes/${id}`, { method: 'DELETE' }).then(r => { if (!r.ok) throw new Error(); }),
  importYaml: (yaml: string): Promise<BusinessProcess[]> =>
    fetchJson<BusinessProcess[]>(`${API_BASE}/api/business-processes/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

// 业务规则 API
export const ruleApi = {
  list: (): Promise<BusinessRule[]> =>
    fetchJson<BusinessRule[]>(`${API_BASE}/api/business-rules`),
  get: (id: string): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules/${id}`),
  create: (data: BusinessRuleFormData): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessRuleFormData): Promise<BusinessRule> =>
    fetchJson<BusinessRule>(`${API_BASE}/api/business-rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/business-rules/${id}`, { method: 'DELETE' }).then(r => { if (!r.ok) throw new Error(); }),
  importYaml: (yaml: string): Promise<BusinessRule[]> =>
    fetchJson<BusinessRule[]>(`${API_BASE}/api/business-rules/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

// 业务逻辑 API
export const logicApi = {
  list: (): Promise<BusinessLogic[]> =>
    fetchJson<BusinessLogic[]>(`${API_BASE}/api/business-logics`),
  get: (id: string): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics/${id}`),
  create: (data: BusinessLogicFormData): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessLogicFormData): Promise<BusinessLogic> =>
    fetchJson<BusinessLogic>(`${API_BASE}/api/business-logics/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/business-logics/${id}`, { method: 'DELETE' }).then(r => { if (!r.ok) throw new Error(); }),
  importYaml: (yaml: string): Promise<BusinessLogic[]> =>
    fetchJson<BusinessLogic[]>(`${API_BASE}/api/business-logics/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

// 业务指标 API
export const indicatorApi = {
  list: (): Promise<BusinessIndicator[]> =>
    fetchJson<BusinessIndicator[]>(`${API_BASE}/api/business-indicators`),
  get: (id: string): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators/${id}`),
  create: (data: BusinessIndicatorFormData): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators`, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: BusinessIndicatorFormData): Promise<BusinessIndicator> =>
    fetchJson<BusinessIndicator>(`${API_BASE}/api/business-indicators/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/business-indicators/${id}`, { method: 'DELETE' }).then(r => { if (!r.ok) throw new Error(); }),
  importYaml: (yaml: string): Promise<BusinessIndicator[]> =>
    fetchJson<BusinessIndicator[]>(`${API_BASE}/api/business-indicators/import-yaml`, { method: 'POST', body: JSON.stringify({ yaml }) }),
};

// 通用实体 API（用于统一查询）
export const entityApi = {
  listAll: (): Promise<BusinessEntity[]> =>
    fetchJson<BusinessEntity[]>(`${API_BASE}/api/business-entities`),
};
