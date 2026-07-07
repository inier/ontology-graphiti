/**
 * 页面上下文路由配置
 * 
 * 自动识别路由并提供页面上下文，无需手动注册收集器。
 * 
 * 设计目标：
 * 1. 路由层面自动匹配页面类型
 * 2. 自动从URL参数提取上下文（如 ontology_id）
 * 3. 自动从状态管理获取上下文
 * 4. 无需页面组件做任何额外操作
 */

import type { PageContext } from './usePageContext';

/** 路由匹配模式类型 */
type RoutePattern = string;

/** 页面元信息 */
export interface PageMetadata {
  pageId: string;
  name: string;
  description: string;
  icon?: string;
  /** 是否需要本体上下文 */
  requiresOntology?: boolean;
  /** 是否需要工作空间上下文 */
  requiresWorkspace?: boolean;
  /** URL参数映射到上下文字段 */
  paramMap?: Record<string, keyof PageContext>;
  /** 自定义上下文提取器 */
  extractContext?: (params: Record<string, string>) => Partial<PageContext>;
}

/** 路由配置映射 */
export const PAGE_ROUTE_CONFIG: Record<RoutePattern, PageMetadata> = {
  // ── 本体设计相关 ──
  '/ontology': {
    pageId: 'ontology_designer',
    name: '本体设计器',
    description: '设计和编辑本体类型定义',
    requiresOntology: true,
    requiresWorkspace: true,
  },
  '/ontology/*': {
    pageId: 'ontology_designer',
    name: '本体设计器',
    description: '设计和编辑本体类型定义',
    requiresOntology: true,
    requiresWorkspace: true,
  },
  '/blueprint': {
    pageId: 'blueprint_designer',
    name: '蓝图设计器',
    description: '可视化编排本体蓝图',
    requiresOntology: true,
    requiresWorkspace: true,
  },
  '/blueprint/*': {
    pageId: 'blueprint_designer',
    name: '蓝图设计器',
    description: '可视化编排本体蓝图',
    requiresOntology: true,
    requiresWorkspace: true,
  },

  // ── 业务规则相关 ──
  '/business/rules': {
    pageId: 'business_rules',
    name: '业务规则',
    description: '管理业务规则和逻辑',
    requiresWorkspace: true,
  },
  '/business/process': {
    pageId: 'business_process',
    name: '业务流程',
    description: '设计业务流程',
    requiresWorkspace: true,
  },
  '/business/indicators': {
    pageId: 'business_indicators',
    name: '指标体系',
    description: '管理指标定义和计算',
    requiresWorkspace: true,
  },
  '/business/logic': {
    pageId: 'business_logic',
    name: '逻辑模型',
    description: '构建逻辑表达式',
    requiresWorkspace: true,
  },
  '/business/entities': {
    pageId: 'business_entities',
    name: '对象管理',
    description: '管理业务对象',
    requiresWorkspace: true,
  },
  '/business/extraction': {
    pageId: 'business_extraction',
    name: '智能生成',
    description: '自动提取和生成',
    requiresWorkspace: true,
  },

  // ── 模拟仿真相关 ──
  '/simulator': {
    pageId: 'simulator',
    name: '模拟器',
    description: '运行模拟和推演',
    requiresWorkspace: true,
  },
  '/simulation/deduction': {
    pageId: 'simulation_deduction',
    name: '策略推演',
    description: '策略分析和推演',
    requiresWorkspace: true,
  },

  // ── 知识管理相关 ──
  '/knowledge': {
    pageId: 'knowledge_base',
    name: '知识库',
    description: '管理知识文档',
    requiresWorkspace: true,
  },
  '/ingest': {
    pageId: 'data_ingest',
    name: '数据摄入',
    description: '导入和处理数据',
    requiresWorkspace: true,
  },

  // ── 智能体相关 ──
  '/my-agents': {
    pageId: 'agent_list',
    name: '我的智能体',
    description: '管理智能体列表',
    requiresWorkspace: true,
  },
  '/agent-chat/:agentId': {
    pageId: 'agent_chat',
    name: '智能体对话',
    description: '与智能体对话',
    requiresWorkspace: true,
    paramMap: { agentId: 'selectedEntityId' },
    extractContext: (params) => ({
      pageData: { agentId: params.agentId },
    }),
  },

  // ── 系统管理 ──
  '/workspace': {
    pageId: 'workspace_manager',
    name: '工作空间管理',
    description: '管理工作空间',
  },
  '/roles': {
    pageId: 'role_manager',
    name: '角色管理',
    description: '管理用户角色',
  },
  '/skills': {
    pageId: 'skill_management',
    name: '技能管理',
    description: '管理技能库',
    requiresWorkspace: true,
  },
  '/minio-admin': {
    pageId: 'minio_admin',
    name: '对象存储管理',
    description: '管理 MinIO 对象存储',
  },

  // ── 版本管理 ──
  '/versions': {
    pageId: 'version_history',
    name: '版本历史',
    description: '查看版本历史',
    requiresWorkspace: true,
  },
};

/**
 * 根据当前路由获取页面元信息
 * 
 * @param path 当前路由路径
 * @returns 页面元信息，如果没有匹配则返回默认值
 */
export function getPageMetadata(path: string): PageMetadata {
  // 精确匹配优先
  if (PAGE_ROUTE_CONFIG[path]) {
    return PAGE_ROUTE_CONFIG[path];
  }

  // 通配符匹配（按优先级排序）
  const patterns = Object.keys(PAGE_ROUTE_CONFIG)
    .filter(p => p.includes('*'))
    .sort((a, b) => {
      // 更具体的模式优先（星号越少越优先）
      const aWildcards = (a.match(/\*/g) || []).length;
      const bWildcards = (b.match(/\*/g) || []).length;
      return aWildcards - bWildcards;
    });

  for (const pattern of patterns) {
    if (matchRoutePattern(pattern, path)) {
      return PAGE_ROUTE_CONFIG[pattern];
    }
  }

  // 默认返回
  return {
    pageId: 'unknown',
    name: '未知页面',
    description: '未知页面',
  };
}

/**
 * 路由模式匹配
 * 支持通配符 * 匹配任意字符
 * 
 * @example
 * matchRoutePattern('/ontology/*', '/ontology/designer') // true
 * matchRoutePattern('/agent-chat/:agentId', '/agent-chat/123') // true
 */
export function matchRoutePattern(pattern: string, path: string): boolean {
  // 处理参数路由（如 :agentId）
  const regexPattern = pattern
    .replace(/:\w+/g, '[^/]+')  // 将 :param 转换为正则
    .replace(/\*/g, '.*');       // 将 * 转换为正则

  const regex = new RegExp(`^${regexPattern}$`);
  return regex.test(path);
}

/**
 * 从URL路径提取参数
 * 
 * @example
 * extractUrlParams('/agent-chat/:agentId', '/agent-chat/123')
 * // { agentId: '123' }
 */
export function extractUrlParams(pattern: string, path: string): Record<string, string> {
  const params: Record<string, string> = {};
  
  // 解析模式中的参数
  const paramNames = pattern.match(/:(\w+)/g) || [];
  if (paramNames.length === 0) {
    return params;
  }

  // 转换为正则表达式
  const regexPattern = pattern.replace(/:\w+/g, '([^/]+)');
  const regex = new RegExp(`^${regexPattern}$`);
  const match = path.match(regex);

  if (match) {
    paramNames.forEach((param, index) => {
      const paramName = param.slice(1); // 去掉冒号
      params[paramName] = match[index + 1];
    });
  }

  return params;
}
