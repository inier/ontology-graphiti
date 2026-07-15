/**
 * USL 规范配置 API 二次封装
 * 基于 @/modules/shared/services/apiClient 的 fetchJson
 * 所有接口挂载前缀 /api/semantic-admin/usl
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type {
  UslDomain,
  DomainPayload,
  UslTerm,
  TermPayload,
  UslHierarchy,
  UslPropertySpec,
  UslDisjointPair,
  UslCardinality,
  PagedResponse,
} from '../types';

const URL_PREFIX = `${API_BASE}/api/semantic-admin/usl`;

// ============================================================
// 1. Domain（语义域）CRUD
// ============================================================

/** 列出语义域（支持分页）
 * 注意：后端 list_domains 仅支持 page/page_size；keyword 搜索由前端本地过滤
 */
export async function listDomains(params?: {
  page?: number;
  page_size?: number;
}): Promise<PagedResponse<UslDomain>> {
  const query = new URLSearchParams();
  if (params?.page !== undefined) query.set('page', String(params.page));
  if (params?.page_size !== undefined) query.set('page_size', String(params.page_size));
  const qs = query.toString();
  return fetchJson(`${URL_PREFIX}/domains${qs ? `?${qs}` : ''}`);
}

/** 获取单个语义域详情 */
export async function getDomain(code: string): Promise<UslDomain> {
  return fetchJson(`${URL_PREFIX}/domains/${encodeURIComponent(code)}`);
}

/** 创建语义域 */
export async function createDomain(payload: DomainPayload): Promise<UslDomain> {
  return fetchJson(`${URL_PREFIX}/domains`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** 更新语义域 */
export async function updateDomain(
  code: string,
  payload: Partial<DomainPayload>,
): Promise<UslDomain> {
  return fetchJson(`${URL_PREFIX}/domains/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// ============================================================
// 2. Term（规范术语）CRUD
// ============================================================

/** 按域列出术语（query字段名严格对齐后端 list_terms Query 参数：
 *   domain_id/semantic_type/synonym_keyword/page/page_size
 * 注意：后端 list_terms 目前无 stoplist 过滤参数，停用词筛选由前端本地过滤
 */
export async function listTerms(domainId: string, params?: {
  page?: number;
  page_size?: number;
  semantic_type?: string;
  synonym_keyword?: string;
}): Promise<PagedResponse<UslTerm>> {
  const query = new URLSearchParams();
  query.set('domain_id', domainId);
  if (params?.page !== undefined) query.set('page', String(params.page));
  if (params?.page_size !== undefined) query.set('page_size', String(params.page_size));
  if (params?.semantic_type) query.set('semantic_type', params.semantic_type);
  if (params?.synonym_keyword) query.set('synonym_keyword', params.synonym_keyword);
  return fetchJson(`${URL_PREFIX}/terms?${query.toString()}`);
}

/** 创建术语 */
export async function createTerm(payload: TermPayload): Promise<UslTerm> {
  return fetchJson(`${URL_PREFIX}/terms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** 更新术语（含停用词开关） */
export async function updateTerm(
  termId: string,
  payload: Partial<TermPayload>,
): Promise<UslTerm> {
  return fetchJson(`${URL_PREFIX}/terms/${encodeURIComponent(termId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// ============================================================
// 3. Hierarchy（层级结构）
// ============================================================

export async function listHierarchies(domainId: string): Promise<UslHierarchy[]> {
  return fetchJson(`${URL_PREFIX}/hierarchies?domain_id=${encodeURIComponent(domainId)}`);
}

export async function createHierarchy(
  payload: Omit<UslHierarchy, 'id' | 'created_at'>,
): Promise<UslHierarchy> {
  return fetchJson(`${URL_PREFIX}/hierarchies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteHierarchy(id: string): Promise<{ status: string }> {
  return fetchJson(`${URL_PREFIX}/hierarchies/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

// ============================================================
// 4. PropertySpec（属性规范）
// ============================================================

export async function listPropertySpecs(domainId: string): Promise<UslPropertySpec[]> {
  return fetchJson(`${URL_PREFIX}/property-specs?domain_id=${encodeURIComponent(domainId)}`);
}

export async function createPropertySpec(
  payload: Omit<UslPropertySpec, 'id' | 'created_at'>,
): Promise<UslPropertySpec> {
  return fetchJson(`${URL_PREFIX}/property-specs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updatePropertySpec(
  id: string,
  payload: Partial<Omit<UslPropertySpec, 'id' | 'created_at'>>,
): Promise<UslPropertySpec> {
  return fetchJson(`${URL_PREFIX}/property-specs/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deletePropertySpec(id: string): Promise<{ status: string }> {
  return fetchJson(`${URL_PREFIX}/property-specs/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

// ============================================================
// 5. DisjointPair（不相交对）
// ============================================================

export async function listDisjointPairs(domainId: string): Promise<UslDisjointPair[]> {
  return fetchJson(`${URL_PREFIX}/disjoint-pairs?domain_id=${encodeURIComponent(domainId)}`);
}

export async function createDisjointPair(
  payload: Omit<UslDisjointPair, 'id' | 'created_at'>,
): Promise<UslDisjointPair> {
  return fetchJson(`${URL_PREFIX}/disjoint-pairs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteDisjointPair(id: string): Promise<{ status: string }> {
  return fetchJson(`${URL_PREFIX}/disjoint-pairs/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

// ============================================================
// 6. Cardinality（关系基数）
// ============================================================

export async function listCardinalities(domainId: string): Promise<UslCardinality[]> {
  return fetchJson(`${URL_PREFIX}/cardinalities?domain_id=${encodeURIComponent(domainId)}`);
}

export async function createCardinality(
  payload: Omit<UslCardinality, 'id' | 'created_at'>,
): Promise<UslCardinality> {
  return fetchJson(`${URL_PREFIX}/cardinalities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateCardinality(
  id: string,
  payload: Partial<Omit<UslCardinality, 'id' | 'created_at'>>,
): Promise<UslCardinality> {
  return fetchJson(`${URL_PREFIX}/cardinalities/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteCardinality(id: string): Promise<{ status: string }> {
  return fetchJson(`${URL_PREFIX}/cardinalities/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}
