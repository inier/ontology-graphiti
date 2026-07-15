import { useRef, useEffect, useMemo } from 'react';
import * as echarts from 'echarts';
import { InlineChart } from './InlineChart';
import type { ChartSpec } from '../hooks/useQAI';

type ChartType = 'line' | 'bar' | 'pie' | 'scatter' | 'radar' | 'heatmap' | 'graph' | 'map';

interface ChartRendererProps {
  chartType: ChartType;
  data: Record<string, unknown>;
  title?: string;
  width?: string | number;
  height?: number;
}

function GraphView({ data, title, height = 350 }: { data: Record<string, unknown>; title?: string; height?: number }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  const option = useMemo((): echarts.EChartsOption => {
    const nodes = (data.nodes as Array<{ id: string; name: string; category?: number }>) || [];
    const links = (data.links as Array<{ source: string; target: string; value?: number }>) || [];
    const categories = (data.categories as Array<{ name: string }>) || [];

    return {
      title: title ? { text: title, textStyle: { fontSize: 14 } } : undefined,
      tooltip: {},
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes.map(n => ({
          id: n.id,
          name: n.name,
          category: n.category,
        })),
        links: links.map(l => ({
          source: l.source,
          target: l.target,
          value: l.value,
        })),
        categories: categories.map(c => ({ name: c.name })),
        roam: true,
        label: { show: true, position: 'right' },
        force: { repulsion: 100, edgeLength: 80 },
      }],
    };
  }, [data, title]);

  useEffect(() => {
    if (!chartRef.current) return;
    instanceRef.current = echarts.init(chartRef.current);
    instanceRef.current.setOption(option);

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      instanceRef.current?.dispose();
    };
  }, [option]);

  return (
    <div style={{ margin: '8px 0', borderRadius: 8, border: '1px solid #e5e7eb', overflow: 'hidden', background: '#fff' }}>
      <div style={{ padding: '6px 12px', background: '#fafafa', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#666' }}>网络图</span>
        {title && <span style={{ fontSize: 12, fontWeight: 500 }}>{title}</span>}
      </div>
      <div ref={chartRef} style={{ width: '100%', height }} />
    </div>
  );
}

function MapView({ data, title, height = 350 }: { data: Record<string, unknown>; title?: string; height?: number }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  const option = useMemo((): echarts.EChartsOption => {
    const points = (data.points as Array<{ name: string; value: [number, number, number] }>) || [];

    return {
      title: title ? { text: title, textStyle: { fontSize: 14 } } : undefined,
      tooltip: { trigger: 'item' },
      series: [{
        type: 'scatter',
        coordinateSystem: 'geo',
        data: points,
        symbolSize: (val: unknown) => {
          const arr = val as number[];
          return arr && arr[2] ? Math.max(8, Math.min(30, arr[2])) : 10;
        },
      }],
      geo: {
        map: 'world',
        roam: true,
        itemStyle: { areaColor: '#f3f3f3', borderColor: '#999' },
        emphasis: { itemStyle: { areaColor: '#e0e0e0' } },
      },
    };
  }, [data, title]);

  useEffect(() => {
    if (!chartRef.current) return;
    instanceRef.current = echarts.init(chartRef.current);
    instanceRef.current.setOption(option);

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      instanceRef.current?.dispose();
    };
  }, [option]);

  return (
    <div style={{ margin: '8px 0', borderRadius: 8, border: '1px solid #e5e7eb', overflow: 'hidden', background: '#fff' }}>
      <div style={{ padding: '6px 12px', background: '#fafafa', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#666' }}>地图</span>
        {title && <span style={{ fontSize: 12, fontWeight: 500 }}>{title}</span>}
      </div>
      <div ref={chartRef} style={{ width: '100%', height }} />
    </div>
  );
}

function ChartRenderer({ chartType, data, title, height }: ChartRendererProps) {
  if (chartType === 'graph') {
    return <GraphView data={data} title={title} height={height} />;
  }

  if (chartType === 'map') {
    return <MapView data={data} title={title} height={height} />;
  }

  const spec: ChartSpec = {
    chart_type: chartType,
    title,
    data,
  };

  return <InlineChart spec={spec} />;
}

export default ChartRenderer;
