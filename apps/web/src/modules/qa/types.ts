/**
 * QA 卡片数据类型。
 *
 * 这些类型原定义在 `hooks/useQAI.ts`（QA v1 独立对话栈的 hook）。
 * 该 hook 已被 `ai-assistant` 的 `useAIChat` 取代 —— `pages/QAPage.tsx`
 * 直接渲染 `AIChatPanel`，注释明确「不再使用独立的 QAChatPage 实现」。
 * 但 AG-UI 生成式卡片（`agui/cardRegistryTable.tsx`）仍然需要这三个类型，
 * 故在此独立存放，与对话引擎解耦：卡片渲染不该依赖某个具体的对话 hook。
 */

/**
 * 图表规格 —— 与后端 `impl/chart_renderer.py::ChartType` 枚举逐项对齐（8 类）。
 *
 * 注意：后端支持 8 类，但前端内联渲染器 `components/InlineChart.tsx`
 * 只实现了其中 6 类。`map` 需要注册 echarts GeoJSON（项目未注册，
 * 且受地图合规约束），`network` 是图谱专用能力（项目已有 Sigma.js
 * `GraphCanvas` 与 ReactFlow `BlueprintDesigner`，不引入第三套）。
 * 这两类在此保守保留以忠实反映后端契约，由渲染器显式报「不支持」，
 * 绝不静默降级成折线图。
 */
export type ChartSpec = {
  chart_type: 'line' | 'bar' | 'pie' | 'scatter' | 'heatmap' | 'radar' | 'map' | 'network';
  title?: string;
  data: Record<string, unknown>;
  render_mode?: string;
};

/** 时序卡片 —— 对应 `agui/cardRegistryTable.tsx` 的 `temporal` 卡片 */
export type TemporalCard = {
  time_type: string;
  valid_time: string;
  answer: string;
  entity_count?: number;
};

/** 报告链接卡片 —— 对应 `agui/cardRegistryTable.tsx` 的 `report_link` 卡片 */
export type ReportLink = {
  report_id: string;
  title: string;
  summary?: string;
  created_at?: string;
};
