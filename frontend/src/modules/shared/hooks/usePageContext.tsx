/**
 * 统一页面上下文系统（全自动版本）
 *
 * 设计目标：
 * 1. **完全自动化**：无需任何页面组件注册，自动从路由识别页面类型
 * 2. **智能提取**：自动从URL参数、状态管理获取上下文信息
 * 3. **零配置**：页面组件无需做任何额外操作即可被AI助手识别
 *
 * 工作原理：
 * 1. 通过React Router获取当前路由路径
 * 2. 自动匹配预定义的页面路由配置（pageRouteConfig.ts）
 * 3. 从URL参数中提取上下文（如 agentId）
 * 4. 从状态管理（ontologyStore/workspace）获取本体和工作空间信息
 * 5. 自动构建完整的页面上下文
 *
 * 使用方式：
 * 1. AI助手组件直接调用 useAIContext() 即可获取完整上下文
 * 2. 页面组件可调用 usePageContext().updateContext() 补充额外信息（可选）
 * 3. 新页面只需在 pageRouteConfig.ts 中添加路由配置
 */

import { createContext, useContext, useCallback, useState, useEffect, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useOntologyStore } from '@/modules/ontology/stores/ontologyStore';
import { useWorkspace } from '../components/LayoutContexts';
import {
  getPageMetadata,
  extractUrlParams,
  matchRoutePattern,
  type PageMetadata,
} from './pageRouteConfig';

/* ──────────────────────────────────────────────────────────────────
 * 页面上下文接口定义
 * ────────────────────────────────────────────────────────────────── */

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

interface PageContextValue {
  /** 当前页面上下文（只读） */
  context: PageContext;

  /** 更新上下文的部分字段（页面可主动调用补充信息） */
  updateContext: (updates: Partial<PageContext>) => void;

  /** 当前页面元信息 */
  metadata: PageMetadata;
}

const PageContext = createContext<PageContextValue | null>(null);

/* ──────────────────────────────────────────────────────────────────
 * Context Provider（全自动版本）
 * ────────────────────────────────────────────────────────────────── */

export function PageContextProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { currentOntology, objectTypes, linkTypes, actionTypes } = useOntologyStore();
  const { currentWorkspace } = useWorkspace();

  // 状态管理
  const [state, setState] = useState<{
    currentContext: PageContext;
    currentMetadata: PageMetadata;
  }>({
    currentContext: {
      pageId: 'unknown',
      route: location.pathname,
    },
    currentMetadata: {
      pageId: 'unknown',
      name: '未知页面',
      description: '未知页面',
    },
  });

  // 当路由变化时，自动更新上下文（核心逻辑）
  useEffect(() => {
    const currentPath = location.pathname;

    // 1. 获取页面元信息（自动匹配路由）
    const metadata = getPageMetadata(currentPath);

    // 2. 从URL提取参数（如 agentId）
    const urlParams = extractUrlParamsFromCurrentPath(currentPath);

    // 3. 构建基础上下文
    const baseContext: PageContext = {
      pageId: metadata.pageId,
      route: currentPath,
      pageName: metadata.name,
      summary: metadata.description,
      requiresOntology: metadata.requiresOntology,
      ...urlParams,
    };

    // 4. 从状态管理补充本体信息（最重要！）
    if (currentOntology) {
      baseContext.ontologyId = currentOntology.ontology_id;
      baseContext.workspaceId = currentOntology.workspace_id || currentWorkspace;
      baseContext.summary = buildOntologySummary(currentOntology, metadata, objectTypes, linkTypes, actionTypes);
      baseContext.selectedTypes = objectTypes.map((t: { name: string }) => t.name);
      baseContext.pageData = {
        ontologyName: currentOntology.name,
        ontologyStatus: currentOntology.status,
        objectTypeCount: objectTypes.length,
        linkTypeCount: linkTypes.length,
        actionTypeCount: actionTypes.length,
      };
    } else if (currentWorkspace) {
      baseContext.workspaceId = currentWorkspace;
    }

    setState({
      currentContext: baseContext,
      currentMetadata: metadata,
    });
  }, [location.pathname, currentOntology, currentWorkspace, objectTypes, linkTypes, actionTypes]);

  // 更新上下文的部分字段（页面可主动调用补充信息）
  const updateContext = useCallback((updates: Partial<PageContext>) => {
    setState(prev => ({
      ...prev,
      currentContext: {
        ...prev.currentContext,
        ...updates,
      },
    }));
  }, []);

  const value: PageContextValue = {
    context: state.currentContext,
    updateContext,
    metadata: state.currentMetadata,
  };

  return <PageContext.Provider value={value}>{children}</PageContext.Provider>;
}

/* ──────────────────────────────────────────────────────────────────
 * Hook：使用页面上下文
 * ────────────────────────────────────────────────────────────────── */

export function usePageContext(): PageContextValue {
  const context = useContext(PageContext);

  if (!context) {
    return {
      context: {
        pageId: 'unknown',
        route: '',
      },
      updateContext: () => {},
      metadata: {
        pageId: 'unknown',
        name: '未知页面',
        description: '未知页面',
      },
    };
  }

  return context;
}

/* ──────────────────────────────────────────────────────────────────
 * Hook：AI助手专用 - 自动获取完整上下文
 * ────────────────────────────────────────────────────────────────── */

/**
 * AI助手专用：获取完整的上下文用于发送给后端
 *
 * 自动整合：
 * - 当前页面上下文（从路由自动识别）
 * - ontologyStore 中的本体信息（自动获取）
 * - 全局状态（工作空间等）
 *
 * @example
 * ```tsx
 * function AIChatPanel() {
 *   const aiContext = useAIContext();
 *   // aiContext 包含:
 *   // - ontologyId: 当前本体ID
 *   // - workspaceId: 当前工作空间ID
 *   // - pageId: 当前页面ID
 *   // - pageName: 页面显示名称
 *   // - summary: 页面摘要（含本体信息）
 *   // - pageData: 页面特定数据（类型数量等）
 * }
 * ```
 */
export function useAIContext() {
  const { context } = usePageContext();
  const { currentOntology, objectTypes, linkTypes, actionTypes } = useOntologyStore();
  const { currentWorkspace } = useWorkspace();

  // 整合所有上下文信息，确保关键字段不丢失
  return {
    ...context,
    // 优先使用 ontologyStore 的本体信息
    ontologyId: currentOntology?.ontology_id || context.ontologyId,
    workspaceId: currentOntology?.workspace_id || currentWorkspace || context.workspaceId,
    // 补充本体详情
    ontologyName: currentOntology?.name,
    ontologyDescription: currentOntology?.description,
    ontologyStatus: currentOntology?.status,
    // 补充类型统计
    objectTypes: objectTypes,
    linkTypes: linkTypes,
    actionTypes: actionTypes,
  };
}

/* ──────────────────────────────────────────────────────────────────
 * 内部工具函数
 * ────────────────────────────────────────────────────────────────── */

/**
 * 从当前路径提取URL参数
 */
function extractUrlParamsFromCurrentPath(path: string): Partial<PageContext> {
  const result: Partial<PageContext> = {};
  const pageData: Record<string, unknown> = {};

  // 遍历所有路由配置，找到匹配的模式并提取参数
  const PAGE_ROUTE_CONFIG: Record<string, PageMetadata> = {};
  for (const [pattern, metadata] of Object.entries(PAGE_ROUTE_CONFIG)) {
    if (matchRoutePattern(pattern, path)) {
      const params = extractUrlParams(pattern, path);

      // 根据 paramMap 映射到上下文字段
      if (metadata.paramMap) {
        for (const [paramName, fieldName] of Object.entries(metadata.paramMap)) {
          if (params[paramName]) {
            result[fieldName] = params[paramName] as PageContext[keyof PageContext];
          }
        }
      }

      // 调用自定义提取器
      if (metadata.extractContext) {
        const customContext = metadata.extractContext(params);
        Object.assign(result, customContext);
      }

      // 将所有URL参数放入 pageData
      Object.assign(pageData, params);
      break;
    }
  }

  if (Object.keys(pageData).length > 0) {
    result.pageData = pageData;
  }

  return result;
}

/**
 * 构建本体摘要（包含详细的本体信息）
 */
function buildOntologySummary(
  ontology: {
    name: string;
    description?: string;
    status?: string;
    ontology_id: string;
  },
  metadata: PageMetadata,
  objectTypes: Array<{ name: string }>,
  linkTypes: Array<{ name: string }>,
  actionTypes: Array<{ name: string }>
): string {
  const parts: string[] = [
    `当前本体：${ontology.name}`,
    `页面：${metadata.name}`,
  ];

  // 添加本体描述（如果存在）
  if (ontology.description) {
    parts.push(`(${ontology.description})`);
  }
  const typeStats = [];
  if (objectTypes.length > 0) {
    typeStats.push(`${objectTypes.length} 个对象类型`);
  }
  if (linkTypes.length > 0) {
    typeStats.push(`${linkTypes.length} 个关系类型`);
  }
  if (actionTypes.length > 0) {
    typeStats.push(`${actionTypes.length} 个动作类型`);
  }
  if (typeStats.length > 0) {
    parts.push(`包含：${typeStats.join('、')}`);
  }

  if (ontology.status) {
    parts.push(`状态：${ontology.status}`);
  }

  return parts.join(' ');
}

/* ──────────────────────────────────────────────────────────────────
 * 兼容旧版API（保留向后兼容）
 * ────────────────────────────────────────────────────────────────── */

export interface PageRegistration {
  pageId: string;
  pathPatterns: string[];
  priority?: number;
}

export function createOntologyDesignerCollector(): PageRegistration {
  return {
    pageId: 'ontology_designer',
    pathPatterns: ['/ontology', '/ontology/*', '/blueprint'],
    priority: 10,
  };
}

export function createBusinessRulesCollector(): PageRegistration {
  return {
    pageId: 'business_rules',
    pathPatterns: ['/business/rules', '/business/*'],
    priority: 20,
  };
}

export function createSimulatorCollector(): PageRegistration {
  return {
    pageId: 'simulator',
    pathPatterns: ['/simulator', '/simulation/*'],
    priority: 20,
  };
}
