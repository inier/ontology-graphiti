import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { Card, Select, Space, Spin } from 'antd';

interface VisualizationProps {
  data: Array<{ [key: string]: any }>;
  loading?: boolean;
}

export const Visualization: React.FC<VisualizationProps> = ({ data, loading = false }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [chartType, setChartType] = useState<string>('bar');
  const [chartInstance, setChartInstance] = useState<echarts.ECharts | null>(null);

  useEffect(() => {
    if (chartRef.current) {
      const chart = echarts.init(chartRef.current);
      setChartInstance(chart);

      return () => {
        chart.dispose();
      };
    }
  }, []);

  useEffect(() => {
    if (chartInstance && data.length > 0) {
      updateChart();
    }
  }, [chartInstance, data, chartType]);

  const updateChart = () => {
    if (!chartInstance) return;

    let option: echarts.EChartsOption = {};

    switch (chartType) {
      case 'bar':
        option = {
          title: {
            text: '实体类型分布',
            left: 'center'
          },
          tooltip: {
            trigger: 'axis',
            axisPointer: {
              type: 'shadow'
            }
          },
          xAxis: {
            type: 'category',
            data: getEntityTypes()
          },
          yAxis: {
            type: 'value',
            name: '数量'
          },
          series: [{
            data: getEntityTypeCounts(),
            type: 'bar',
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#83bff6' },
                { offset: 0.5, color: '#188df0' },
                { offset: 1, color: '#188df0' }
              ])
            },
            emphasis: {
              itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: '#2378f7' },
                  { offset: 0.7, color: '#2378f7' },
                  { offset: 1, color: '#83bff6' }
                ])
              }
            }
          }]
        };
        break;

      case 'pie':
        option = {
          title: {
            text: '实体类型占比',
            left: 'center'
          },
          tooltip: {
            trigger: 'item'
          },
          legend: {
            orient: 'vertical',
            left: 'left'
          },
          series: [{
            name: '实体类型',
            type: 'pie',
            radius: '70%',
            data: getPieData(),
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }]
        };
        break;

      case 'line':
        option = {
          title: {
            text: '实体数量趋势',
            left: 'center'
          },
          tooltip: {
            trigger: 'axis'
          },
          xAxis: {
            type: 'category',
            data: ['1月', '2月', '3月', '4月', '5月', '6月']
          },
          yAxis: {
            type: 'value',
            name: '数量'
          },
          series: [{
            data: [120, 132, 101, 134, 90, 230],
            type: 'line',
            smooth: true,
            lineStyle: {
              width: 3,
              color: '#188df0'
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(24, 141, 240, 0.5)' },
                { offset: 1, color: 'rgba(24, 141, 240, 0.1)' }
              ])
            }
          }]
        };
        break;

      case 'scatter':
        option = {
          title: {
            text: '实体关系散点图',
            left: 'center'
          },
          tooltip: {
            trigger: 'item'
          },
          xAxis: {
            type: 'value',
            name: 'X轴'
          },
          yAxis: {
            type: 'value',
            name: 'Y轴'
          },
          series: [{
            data: data.map((item) => [
              Math.random() * 100,
              Math.random() * 100,
              item.name
            ]),
            type: 'scatter',
            symbolSize: 10,
            itemStyle: {
              color: '#188df0'
            }
          }]
        };
        break;

      default:
        break;
    }

    chartInstance.setOption(option);
  };

  const getEntityTypes = (): string[] => {
    const types = new Set(data.map(item => item.type || 'Unknown'));
    return Array.from(types);
  };

  const getEntityTypeCounts = (): number[] => {
    const types = getEntityTypes();
    return types.map(type => {
      return data.filter(item => item.type === type).length;
    });
  };

  const getPieData = (): { value: number; name: string }[] => {
    const types = getEntityTypes();
    return types.map(type => {
      return {
        value: data.filter(item => item.type === type).length,
        name: type
      };
    });
  };

  return (
    <Card title="数据可视化" style={{ marginBottom: 16 }}>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={chartType}
          onChange={setChartType}
          style={{ width: 120 }}
          options={[
            { value: 'bar', label: '柱状图' },
            { value: 'pie', label: '饼图' },
            { value: 'line', label: '折线图' },
            { value: 'scatter', label: '散点图' }
          ]}
        />
      </Space>
      <div style={{ position: 'relative', height: 400 }}>
        {loading ? (
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
            <Spin size="large" />
          </div>
        ) : (
          <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
        )}
      </div>
    </Card>
  );
};

export default Visualization;