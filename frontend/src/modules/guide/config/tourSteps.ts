import type { TourProps } from 'antd';

/**
 * Helper: create a target getter from a data-tour attribute selector.
 * Returns null-safe function for antd Tour `target` prop.
 */
const tourTarget = (selector: string): (() => HTMLElement | null) => {
  return () => document.querySelector(`[data-tour="${selector}"]`) as HTMLElement | null;
};

/* ─── Guide Page Tour Steps (5 steps) ─────────────────────────────── */

export const guideTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('quick-start'),
    title: '快速开始',
    description: '点击这里可以随时重新开始引导流程，或查看 API 文档和代码示例。',
    placement: 'bottom',
  },
  {
    target: tourTarget('step-workspace'),
    title: '工作空间设置',
    description: '创建或选择工作空间和场景，这是后续所有操作的基础容器。',
    placement: 'bottom',
  },
  {
    target: tourTarget('step-ontology'),
    title: '本体设计器',
    description: '创建实体类型、定义属性和建立关系，构建知识图谱的骨架。',
    placement: 'bottom',
  },
  {
    target: tourTarget('step-blueprint'),
    title: '蓝图设计',
    description: '设计业务流程，使用各种节点类型来构建数据流。',
    placement: 'bottom',
  },
  {
    target: tourTarget('step-ingest'),
    title: '数据摄入',
    description: '导入数据并应用知识图谱，完成从数据到知识的闭环。',
    placement: 'bottom',
  },
];

/* ─── Workspace Page Tour Steps ───────────────────────────────────── */

export const workspaceTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('workspace-create-btn'),
    title: '创建工作空间',
    description: '点击此按钮创建新的工作空间，作为所有资源的顶级容器。',
    placement: 'bottomLeft',
  },
  {
    target: tourTarget('workspace-scenario-tab'),
    title: '场景管理',
    description: '切换到场景标签页，管理工作空间下的业务场景。',
    placement: 'bottom',
  },
  {
    target: tourTarget('workspace-scenario-create-btn'),
    title: '创建场景',
    description: '在场景标签页中创建新场景，场景是本体和数据的隔离单元。',
    placement: 'bottomLeft',
  },
];

/* ─── Ontology Designer Page Tour Steps ────────────────────────────── */

export const ontologyDesignerTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('ontology-add-type-btn'),
    title: '添加实体类型',
    description: '点击此按钮新增对象类型，定义实体的属性和关系。',
    placement: 'bottomRight',
  },
  {
    target: tourTarget('ontology-type-list'),
    title: '类型列表',
    description: '左侧列表展示所有已定义的对象类型，点击可编辑详情。',
    placement: 'right',
  },
  {
    target: tourTarget('ontology-editor-panel'),
    title: '属性编辑器',
    description: '右侧面板用于编辑选中类型的属性、关系等详细信息。',
    placement: 'left',
  },
];

/* ─── Blueprint Designer Page Tour Steps ───────────────────────────── */

export const blueprintTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('blueprint-node-panel'),
    title: '节点面板',
    description: '从节点面板中选择需要的节点类型，拖拽到画布中。',
    placement: 'right',
  },
  {
    target: tourTarget('blueprint-canvas'),
    title: '画布区域',
    description: '在画布中拖拽、连接节点，设计业务流程。',
    placement: 'left',
  },
  {
    target: tourTarget('blueprint-run-btn'),
    title: '运行蓝图',
    description: '设计完成后，点击运行按钮执行蓝图流程。',
    placement: 'bottomLeft',
  },
];

/* ─── Object Management Page Tour Steps ────────────────────────────── */

export const objectManagementTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('obj-mgmt-type-tab'),
    title: '类型管理',
    description: '在类型管理标签页中查看和管理所有对象类型定义。',
    placement: 'bottom',
  },
  {
    target: tourTarget('obj-mgmt-instances-tab'),
    title: '实例列表',
    description: '切换到实例标签页，查看和管理实体实例数据。',
    placement: 'bottom',
  },
  {
    target: tourTarget('obj-mgmt-filter'),
    title: '筛选器',
    description: '使用筛选器按类型、来源、状态过滤实体实例。',
    placement: 'bottom',
  },
];

/* ─── Ingest Panel Page Tour Steps ─────────────────────────────────── */

export const ingestTourSteps: TourProps['steps'] = [
  {
    target: tourTarget('ingest-source-tabs'),
    title: '数据源选择',
    description: '选择数据摄入方式：文本、新闻、JSON、自然语言、文件上传等。',
    placement: 'bottom',
  },
  {
    target: tourTarget('ingest-start-btn'),
    title: '开始摄入',
    description: '输入数据后点击此按钮启动摄入流程。',
    placement: 'bottom',
  },
  {
    target: tourTarget('ingest-history-table'),
    title: '构建进度',
    description: '下方表格展示摄入历史记录，可查看构建详情和版本信息。',
    placement: 'top',
  },
];

/* ─── Page ID constants ────────────────────────────────────────────── */

export const PAGE_IDS = {
  GUIDE: 'guide',
  WORKSPACE: 'workspace',
  ONTOLOGY_DESIGNER: 'ontology-designer',
  BLUEPRINT: 'blueprint',
  OBJECT_MANAGEMENT: 'object-management',
  INGEST: 'ingest',
} as const;

export type PageId = (typeof PAGE_IDS)[keyof typeof PAGE_IDS];
