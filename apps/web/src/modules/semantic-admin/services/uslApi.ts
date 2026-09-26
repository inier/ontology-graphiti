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

/** 删除结果（对齐后端 DeleteResponse）。cascade_counts 为逐表级联删除行数，
 *  仅 DELETE /domains/{ref} 会填（其余删除路由无级联，返回空对象）。 */
export interface UslDeleteResult {
  status: string;
  deleted: boolean;
  id: string;
  cascade_counts?: Record<string, number>;
}

/** @deprecated 用 UslDeleteResult；保留别名避免既有 import 断裂 */
export type DeleteDomainResult = UslDeleteResult;

/** 删除语义域（后端级联清除该域下术语/层级/属性/不相交对/基数，不可恢复） */
export async function deleteDomain(code: string): Promise<UslDeleteResult> {
  return fetchJson(`${URL_PREFIX}/domains/${encodeURIComponent(code)}`, {
    method: 'DELETE',
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

/** 更新术语（含停用词开关）。
 *  后端 UpdateTermRequest 是 extra="forbid"，只收
 *  semantic_type/synonyms/near_synonyms/aliases/stoplist_flag/definition；
 *  传 domain_id 或 canonical 会被拒 422，故 payload 用 Omit 显式排除身份字段。 */
export async function updateTerm(
  termId: string,
  payload: Partial<Omit<TermPayload, 'domain_id' | 'canonical'>>,
): Promise<UslTerm> {
  return fetchJson(`${URL_PREFIX}/terms/${encodeURIComponent(termId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** 删除术语。后端 DELETE /terms/{term_id} 一直存在（返回 DeleteResponse），
 *  早先前端没有这个函数，TermTable 的删除按钮只弹「接口待上线」——是个假按钮。 */
export async function deleteTerm(termId: string): Promise<UslDeleteResult> {
  return fetchJson(`${URL_PREFIX}/terms/${encodeURIComponent(termId)}`, {
    method: 'DELETE',
  });
}

// ============================================================
// 3. Hierarchy（层级结构）
// ============================================================

/** 后端所有 list 路由都返回分页对象 {items,total,page,page_size}
 *  （见 usl_manager/api/schemas.py 的 *ListResponse）。早先这里把返回类型标成
 *  裸数组，组件再 Array.isArray(x)?x:[] 一判恒为 []，于是 4 张子表永远空。 */
export async function listHierarchies(domainId: string): Promise<PagedResponse<UslHierarchy>> {
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

export async function listPropertySpecs(domainId: string): Promise<PagedResponse<UslPropertySpec>> {
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

/** 更新属性规范。后端 UpdatePropertySpecRequest 是 extra="forbid"，只收
 *  data_type/unit/required_flag/description；传 domain_id/for_term/prop_name 会 422。 */
export async function updatePropertySpec(
  id: string,
  payload: Partial<Pick<UslPropertySpec, 'data_type' | 'unit' | 'required_flag' | 'description'>>,
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

export async function listDisjointPairs(domainId: string): Promise<PagedResponse<UslDisjointPair>> {
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

export async function listCardinalities(domainId: string): Promise<PagedResponse<UslCardinality>> {
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

/** 更新关系基数。后端 UpdateCardinalityRequest 是 extra="forbid"，只收
 *  rel_name/domain_term/range_term/min_card/max_card；传 domain_id 会 422。
 *  max_card 为 null 表示无限（不是 -1）。 */
export async function updateCardinality(
  id: string,
  payload: Partial<Pick<UslCardinality, 'rel_name' | 'domain_term' | 'range_term' | 'min_card' | 'max_card'>>,
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
