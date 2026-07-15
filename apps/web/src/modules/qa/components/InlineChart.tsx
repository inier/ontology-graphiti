import React, { useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import type { ChartSpec } from '../hooks/useQAI';

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
      return { ...base, xAxis: { type: 'category', data: categories }, yAxis: { type: 'value' }, series: [{ type: 'line', data: values }] };
  }
}

export function InlineChart({ spec }: { spec: ChartSpec }) {
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
    <div style={{ margin: '8px 0', borderRadius: 8, border: '1px solid #e5e7eb', overflow: 'hidden', background: '#fff' }}>
      <div style={{ padding: '6px 12px', background: '#fafafa', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#666' }}>{chartTypeNames[spec.chart_type] || spec.chart_type}</span>
        {spec.title && <span style={{ fontSize: 12, fontWeight: 500 }}>{spec.title}</span>}
      </div>
      <div ref={chartRef} style={{ width: '100%', height: 280 }} />
    </div>
  );
}
