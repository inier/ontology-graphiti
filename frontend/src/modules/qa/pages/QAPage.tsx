import React, { useState } from 'react';
import { Layout, Input, Button, Card, Typography, Space, Spin, Tabs, Empty, Tag, Divider } from 'antd';
import { ClockCircleOutlined, BarChartOutlined, SendOutlined } from '@ant-design/icons';
import { QAChatPage } from './QAChatPage';
import { useQAStore } from '../stores/qaStore';

const { Title, Text, Paragraph } = Typography;

function TemporalQAPanel() {
  const [question, setQuestion] = useState('');
  const [validTime, setValidTime] = useState('');
  const { temporalLoading, temporalResult, temporalError, askTemporal, clearTemporal } = useQAStore();

  const handleAsk = () => {
    if (!question.trim()) return;
    askTemporal({
      question,
      valid_time: validTime || undefined,
    });
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>时序问答</Text>
            <br />
            <Text type="secondary">支持自然语言时间表达式，如"2024年3月1日"、"上周"、"3小时前"等</Text>
          </div>
          <Input.TextArea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="输入时序问题，如：在2024年3月1日，A区的状态是什么？"
            rows={3}
          />
          <Input
            value={validTime}
            onChange={(e) => setValidTime(e.target.value)}
            placeholder="指定时间（可选，如 2024-03-01T00:00:00Z）"
          />
          <Space>
            <Button
              type="primary"
              icon={<ClockCircleOutlined />}
              onClick={handleAsk}
              loading={temporalLoading}
              disabled={!question.trim()}
            >
              时序查询
            </Button>
            <Button onClick={clearTemporal}>清除</Button>
          </Space>
        </Space>
      </Card>

      {temporalLoading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
        </div>
      )}

      {temporalError && (
        <Card style={{ marginBottom: 16, borderColor: '#ff4d4f' }}>
          <Text type="danger">{temporalError}</Text>
        </Card>
      )}

      {temporalResult && !temporalLoading && (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Tag color="blue">{temporalResult.time_type || 'specific'}</Tag>
              <Text type="secondary">有效时间: {temporalResult.valid_time || '自动解析'}</Text>
            </div>
            <Divider style={{ margin: '8px 0' }} />
            <Paragraph>{temporalResult.answer}</Paragraph>
            <Text type="secondary">相关实体数: {temporalResult.entity_count}</Text>
          </Space>
        </Card>
      )}
    </div>
  );
}

function ChartPanel() {
  const [chartType, setChartType] = useState('line');
  const [chartTitle, setChartTitle] = useState('');
  const [chartData, setChartData] = useState('{"categories":["A","B","C"],"values":[10,20,30]}');
  const { chartLoading, chartResult, chartError, renderChart, clearChart } = useQAStore();

  const handleRender = () => {
    try {
      const data = JSON.parse(chartData);
      renderChart({
        chart_type: chartType,
        data,
        title: chartTitle,
      });
    } catch {
      return;
    }
  };

  const chartTypes = [
    { label: '折线图', value: 'line' },
    { label: '柱状图', value: 'bar' },
    { label: '饼图', value: 'pie' },
    { label: '散点图', value: 'scatter' },
    { label: '热力图', value: 'heatmap' },
    { label: '雷达图', value: 'radar' },
    { label: '地图', value: 'map' },
    { label: '网络图', value: 'network' },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>图表渲染</Text>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {chartTypes.map((ct) => (
              <Tag
                key={ct.value}
                color={chartType === ct.value ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setChartType(ct.value)}
              >
                {ct.label}
              </Tag>
            ))}
          </div>
          <Input
            value={chartTitle}
            onChange={(e) => setChartTitle(e.target.value)}
            placeholder="图表标题（可选）"
          />
          <Input.TextArea
            value={chartData}
            onChange={(e) => setChartData(e.target.value)}
            placeholder="图表数据（JSON格式）"
            rows={6}
          />
          <Space>
            <Button
              type="primary"
              icon={<BarChartOutlined />}
              onClick={handleRender}
              loading={chartLoading}
            >
              渲染图表
            </Button>
            <Button onClick={clearChart}>清除</Button>
          </Space>
        </Space>
      </Card>

      {chartError && (
        <Card style={{ marginBottom: 16, borderColor: '#ff4d4f' }}>
          <Text type="danger">{chartError}</Text>
        </Card>
      )}

      {chartResult && !chartLoading && (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Tag color="green">{chartResult.chart_type}</Tag>
              <Tag>{chartResult.render_mode}</Tag>
              {chartResult.title && <Text strong>{chartResult.title}</Text>}
            </div>
            <Divider style={{ margin: '8px 0' }} />
            <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12, borderRadius: 8, fontSize: 12 }}>
              {JSON.stringify(chartResult.spec, null, 2)}
            </pre>
          </Space>
        </Card>
      )}
    </div>
  );
}

export function QAPage() {
  const items = [
    {
      key: 'chat',
      label: '智能问答',
      children: <QAChatPage />,
    },
    {
      key: 'temporal',
      label: '时序问答',
      icon: <ClockCircleOutlined />,
      children: <TemporalQAPanel />,
    },
    {
      key: 'chart',
      label: '图表渲染',
      icon: <BarChartOutlined />,
      children: <ChartPanel />,
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs
        items={items}
        style={{ height: '100%', padding: '0 16px' }}
        tabBarStyle={{ marginBottom: 0, padding: '0 8px' }}
      />
    </div>
  );
}
