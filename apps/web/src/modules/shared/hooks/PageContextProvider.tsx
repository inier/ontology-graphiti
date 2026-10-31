/**
 * 统一页面上下文 Provider（全自动版本）。
 *
 * 完全无需页面注册：从路由匹配页面元信息、从 URL 提取参数、
 * 从 ontologyStore / workspace 补充本体信息，派生出完整上下文。
 */

import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useOntologyStore } from '@/modules/ontology/stores/ontologyStore';
import { useWorkspace } from '../components/LayoutContexts';
import {
  getPageMetadata,
  extractUrlParams,
  matchRoutePattern,
  PAGE_ROUTE_CONFIG,
  type PageMetadata,
} from './pageRouteConfig';
import { pageContextStore, type PageContext, type PageContextValue } from './pageContextCore';

/**
 * 从当前路径提取URL参数
 */
function extractUrlParamsFromCurrentPath(path: string): Partial<PageContext> {
  const result: Partial<PageContext> = {};
  const pageData: Record<string, unknown> = {};

  // 遍历所有路由配置，找到匹配的模式并提取参数
  const PAGE_ROUTE_CONFIG_ENTRIES: Array<[string, PageMetadata]> = Object.entries(PAGE_ROUTE_CONFIG);
  for (const [pattern, metadata] of PAGE_ROUTE_CONFIG_ENTRIES) {
    if (matchRoutePattern(pattern, path)) {
      const params = extractUrlParams(pattern, path);

      // 根据 paramMap 映射到上下文字段
      if (metadata.paramMap) {
        for (const [paramName, fieldName] of Object.entries(metadata.paramMap)) {
          const value = params[paramName];
          if (value) {
            result[fieldName] = value;
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

export function PageContextProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { currentOntology, objectTypes, linkTypes, actionTypes } = useOntologyStore();
  const { currentWorkspace } = useWorkspace();

  // 页面主动补充的字段（唯一需要存放的可变状态，其余全部由路由/store 派生）
  const [patch, setPatch] = useState<Partial<PageContext>>({});

  // 当路由或 store 变化时，同步派生上下文（派生值，不再用 effect 回写 state）
  const derived = useMemo<{
    currentContext: PageContext;
    currentMetadata: PageMetadata;
  }>(() => {
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

    return { currentContext: baseContext, currentMetadata: metadata };
  }, [location.pathname, currentOntology, currentWorkspace, objectTypes, linkTypes, actionTypes]);

  // 更新上下文的部分字段（页面可主动调用补充信息）
  const updateContext = useCallback((updates: Partial<PageContext>) => {
    setPatch(prev => ({ ...prev, ...updates }));
  }, []);

  const value: PageContextValue = {
    context: { ...derived.currentContext, ...patch },
    updateContext,
    metadata: derived.currentMetadata,
  };

  return <pageContextStore.Provider value={value}>{children}</pageContextStore.Provider>;
}
