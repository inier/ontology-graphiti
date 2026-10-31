import React, { useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import type { ChartSpec } from '../types';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const chartTypeNames: Record<string, string> = {
  line: '折线图',
  bar: '柱状图',
  pie: '饼图',
  scatter: '散点图',
  heatmap: '热力图',
  radar: '雷达图',
  map: '地图',
  network: '网络图',
};

/**
 * 本渲染器真正实现的类型。
 *
 * 后端 `impl/chart_renderer.py::ChartType` 契约有 8 类，这里只实现 6 类。
 * `map` / `network` 必须显式落到「不支持」分支 —— 绝不能让 switch 的 default
 * 把地图或网络图静默画成折线图，那会给用户一张形式正确、含义完全错误的图。
 */
const RENDERABLE_TYPES = new Set(['line', 'bar', 'pie', 'scatter', 'heatmap', 'radar']);

/** 未实现类型的具体原因（不说笼统的「暂不支持」，直接说清楚为什么、该去哪里看） */
const UNRENDERABLE_REASON: Record<string, string> = {
  map: '地图图表需注册 GeoJSON 底图并受地图数据合规约束，本模块不提供内联渲染',
  network: '网络图请使用知识图谱画布查看',
};

function buildEChartsOption(spec: ChartSpec): echarts.EChartsOption {
  const { chart_type, title, data } = spec;
  const base = {
    title: title ? { text: title, textStyle: { fontSize: 14 } } : undefined,
    tooltip: { trigger: 'axis' as const },
    grid: { left: 40, right: 20, top: title ? 50 : 20, bottom: 30 },
  };

  const categories = (data.categories as string[]) || [];
  const values = (data.values as number[]) || [];

  switch (chart_type) {
    case 'line':
      return { ...base, xAxis: { type: 'category', data: categories }, yAxis: { type: 'value' }, series: [{ type: 'line', data: values, smooth: true, areaStyle: { opacity: 0.15 } }] };
    case 'bar':
      return { ...base, xAxis: { type: 'category', data: categories }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: values }] };
    case 'pie':
      return { title: base.title, tooltip: { trigger: 'item' as const }, series: [{ type: 'pie', radius: ['35%', '65%'], data: categories.map((c, i) => ({ name: c, value: values[i] })), label: { formatter: '{b}: {d}%' } }] };
    case 'scatter':
      return { ...base, xAxis: { type: 'value' }, yAxis: { type: 'value' }, series: [{ type: 'scatter', data: (data.points as number[][]) || [] }] };
    case 'radar':
      return { title: base.title, radar: { indicator: categories.map(c => ({ name: c })) }, series: [{ type: 'radar', data: [{ value: values }] }] };
    case 'heatmap':
      return { ...base, xAxis: { type: 'category', data: (data.xLabels as string[]) || [] }, yAxis: { type: 'category', data: (data.yLabels as string[]) || [] }, visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 }, series: [{ type: 'heatmap', data: (data.heatmapData as number[][]) || [], label: { show: true } }] };
    default:
      // 已由 InlineChart 的 RENDERABLE_TYPES 拦截，此处不可达；保留兜底仅为满足穷尽性
      return { ...base, xAxis: { type: 'category', data: categories }, yAxis: { type: 'value' }, series: [{ type: 'line', data: values }] };
  }
}

const frameStyle: React.CSSProperties = {
  margin: '8px 0',
  borderRadius: 8,
  border: '1px solid #e5e7eb',
  overflow: 'hidden',
  background: '#fff',
};

const headerStyle: React.CSSProperties = {
  padding: '6px 12px',
  background: '#fafafa',
  borderBottom: '1px solid #e5e7eb',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

function ChartHeader({ spec }: { spec: ChartSpec }) {
  return (
    <div style={headerStyle}>
      <span style={{ fontSize: 12, color: '#666' }}>{chartTypeNames[spec.chart_type] || spec.chart_type}</span>
      {spec.title && <span style={{ fontSize: 12, fontWeight: 500 }}>{spec.title}</span>}
    </div>
  );
}

/** 未实现类型的显式说明，替代静默降级 */
function UnsupportedChart({ spec }: { spec: ChartSpec }) {
  const { t } = useI18n('qa');
  const typeName = chartTypeNames[spec.chart_type] || spec.chart_type;
  const reason = UNRENDERABLE_REASON[spec.chart_type];

  return (
    <div style={frameStyle} data-testid="inline-chart-unsupported">
      <ChartHeader spec={spec} />
      <div style={{ padding: '16px 12px', fontSize: 12, color: '#8c8c8c' }}>
        <div>{t('该图表类型暂不支持内联渲染: {{type}}', { type: typeName })}</div>
        {reason && <div style={{ marginTop: 4 }}>{t(reason)}</div>}
      </div>
    </div>
  );
}

function EChartBox({ spec }: { spec: ChartSpec }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    instanceRef.current = echarts.init(chartRef.current);
    instanceRef.current.setOption(buildEChartsOption(spec));

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      instanceRef.current?.dispose();
    };
  }, [spec]);

  return (
    <div style={frameStyle}>
      <ChartHeader spec={spec} />
      <div ref={chartRef} style={{ width: '100%', height: 280 }} />
    </div>
  );
}

export function InlineChart({ spec }: { spec: ChartSpec }) {
  if (!RENDERABLE_TYPES.has(spec.chart_type)) {
    return <UnsupportedChart spec={spec} />;
  }
  return <EChartBox spec={spec} />;
}
