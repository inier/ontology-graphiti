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
 *
 * 模块边界：Provider 组件在 `PageContextProvider.tsx`，本文件只导出 hooks 与兼容工厂，
 * 以保持 react-refresh 的「一个模块只导出组件」约定。
 */

import { useContext } from 'react';
import { useOntologyStore } from '@/modules/ontology/stores/ontologyStore';
import { useWorkspace } from '../components/LayoutContexts';
import {
  pageContextStore,
  type PageContext,
  type PageContextValue,
} from './pageContextCore';

export type { PageContext, PageContextValue };

/* ──────────────────────────────────────────────────────────────────
 * Hook：使用页面上下文
 * ────────────────────────────────────────────────────────────────── */

export function usePageContext(): PageContextValue {
  const context = useContext(pageContextStore);

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
