/**
 * 页面上下文的核心定义（类型 + Context 对象）。
 *
 * 单独成文件的原因：Provider（组件）与 hooks（非组件）必须分属不同模块，
 * 否则 react-refresh 无法对 `PageContextProvider` 做热替换。
 */
import { createContext } from 'react';
import type { PageMetadata } from './pageRouteConfig';

export interface PageContext {
  /** 当前页面标识（如 'ontology_designer', 'blueprint', 'business_rules'） */
  pageId: string;

  /** 页面路由路径 */
  route: string;

  /** 当前工作空间ID */
  workspaceId?: string;

  /** 当前本体ID（如果在本体相关页面） */
  ontologyId?: string;

  /** 当前本体版本ID（如果在本体相关页面） */
  ontologyVersionId?: string;

  /** 场景ID（如果有） */
  scenarioId?: string;

  /** 页面选中的对象类型列表 */
  selectedTypes?: string[];

  /** 页面选中的单个对象类型 */
  selectedType?: string;

  /** 页面选中的实体/节点ID */
  selectedEntityId?: string;

  /** 页面特定数据（键值对，页面可自由扩展） */
  pageData?: Record<string, unknown>;

  /** 页面提供的摘要信息（用于AI助手快速理解页面状态） */
  summary?: string;

  /** 页面显示名称 */
  pageName?: string;

  /** 是否需要本体上下文 */
  requiresOntology?: boolean;
}

/* ──────────────────────────────────────────────────────────────────
 * Context 定义
 * ────────────────────────────────────────────────────────────────── */

export interface PageContextValue {
  /** 当前页面上下文（只读） */
  context: PageContext;

  /** 更新上下文的部分字段（页面可主动调用补充信息） */
  updateContext: (updates: Partial<PageContext>) => void;

  /** 当前页面元信息 */
  metadata: PageMetadata;
}

/** Context 对象：Provider 写入、hooks 读取 */
export const pageContextStore = createContext<PageContextValue | null>(null);
