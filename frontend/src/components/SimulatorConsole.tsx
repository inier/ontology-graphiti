import { useState, useRef, useEffect } from 'react';
import { Card, Row, Col, Form, InputNumber, Select, Button, Space, Progress, Statistic } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';

interface SimulatorConsoleProps {
  onStart?: (params: SimulationParams) => void;
  onPause?: () => void;
  onStop?: () => void;
}

interface SimulationParams {
  redForce: number;
  blueForce: number;
  speed: number;
  fireRange: number;
  reinforcementTime: number;
  supplyEfficiency: number;
}

interface SimState {
  status: 'idle' | 'running' | 'paused' | 'stopped';
  redPower: number;
  bluePower: number;
  redCasualties: number;
  blueCasualties: number;
  elapsedTime: string;
}

export function SimulatorConsole({ onStart, onPause, onStop }: SimulatorConsoleProps) {
  const [status, setStatus] = useState<SimState['status']>('idle');
  const [simState, setSimState] = useState<SimState>({
    status: 'idle',
    redPower: 78,
    bluePower: 65,
    redCasualties: 15,
    blueCasualties: 22,
    elapsedTime: '00:00:00',
  });
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || status === 'idle') return;

    const chart = echarts.init(chartRef.current);
    const option = {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['红方战力', '蓝方战力'],
        textStyle: { color: '#595959' },
      },
      xAxis: {
        type: 'category',
        data: ['00:00', '00:05', '00:10', '00:15', '00:20', '00:25', '00:30'],
        axisLine: { lineStyle: { color: '#d9d9d9' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: '#d9d9d9' } },
      },
      series: [
        {
          name: '红方战力',
          type: 'line',
          data: [78, 76, 74, 72, 70, 68, 65],
          smooth: true,
          lineStyle: { color: '#ff4d4f', width: 2 },
          itemStyle: { color: '#ff4d4f' },
        },
        {
          name: '蓝方战力',
          type: 'line',
          data: [65, 63, 61, 59, 57, 55, 52],
          smooth: true,
          lineStyle: { color: '#1890ff', width: 2 },
          itemStyle: { color: '#1890ff' },
        },
      ],
    };
    chart.setOption(option);

    return () => {
      chart.dispose();
    };
  }, [status]);

  const handleStart = () => {
    setStatus('running');
    setSimState((prev) => ({ ...prev, status: 'running' }));
    onStart?.({
      redForce: 320,
      blueForce: 450,
      speed: 1,
      fireRange: 2,
      reinforcementTime: 30,
      supplyEfficiency: 80,
    });
  };

  const handlePause = () => {
    setStatus('paused');
    setSimState((prev) => ({ ...prev, status: 'paused' }));
    onPause?.();
  };

  const handleStop = () => {
    setStatus('stopped');
    setSimState((prev) => ({ ...prev, status: 'stopped' }));
    onStop?.();
  };

  return (
    <Row gutter={16}>
      <Col span={12}>
        <Card title="参数配置" style={{ borderRadius: 8 }}>
          <Form layout="vertical">
            <div style={{ marginBottom: 16, fontWeight: 500, color: '#ff4d4f' }}>基础参数</div>
            <Form.Item label="红方初始兵力">
              <InputNumber min={0} max={1000} defaultValue={320} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="蓝方初始兵力">
              <InputNumber min={0} max={1000} defaultValue={450} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="推演速度">
              <Select
                options={[
                  { value: 0.5, label: '0.5x' },
                  { value: 1, label: '1x' },
                  { value: 2, label: '2x' },
                  { value: 4, label: '4x' },
                ]}
                defaultValue={1}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <div style={{ marginBottom: 16, marginTop: 24, fontWeight: 500, color: '#1890ff' }}>作战参数</div>
            <Form.Item label="开火距离 (km)">
              <InputNumber min={0} max={10} defaultValue={2} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="增援响应时间 (min)">
              <InputNumber min={0} max={60} defaultValue={30} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="补给效率 (%)">
              <InputNumber min={0} max={100} defaultValue={80} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item style={{ marginTop: 24 }}>
              <Space>
                {status === 'idle' || status === 'stopped' ? (
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>
                    开始推演
                  </Button>
                ) : status === 'running' ? (
                  <Button icon={<PauseCircleOutlined />} onClick={handlePause}>
                    暂停
                  </Button>
                ) : (
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>
                    继续
                  </Button>
                )}
                <Button danger icon={<StopOutlined />} onClick={handleStop}>
                  停止
                </Button>
                <Button icon={<ReloadOutlined />}>重置</Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Col>

      <Col span={12}>
        <Card title="实时监控" style={{ borderRadius: 8 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Statistic
                title="红方战力"
                value={simState.redPower}
                suffix="%"
                valueStyle={{ color: '#ff4d4f' }}
              />
              <Progress percent={simState.redPower} showInfo={false} strokeColor="#ff4d4f" style={{ marginTop: 8 }} />
            </Col>
            <Col span={12}>
              <Statistic
                title="蓝方战力"
                value={simState.bluePower}
                suffix="%"
                valueStyle={{ color: '#1890ff' }}
              />
              <Progress percent={simState.bluePower} showInfo={false} strokeColor="#1890ff" style={{ marginTop: 8 }} />
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={12}>
              <Statistic title="红方伤亡" value={simState.redCasualties} valueStyle={{ color: '#ff4d4f' }} />
            </Col>
            <Col span={12}>
              <Statistic title="蓝方伤亡" value={simState.blueCasualties} valueStyle={{ color: '#1890ff' }} />
            </Col>
          </Row>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>伤亡比</div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>
              <span style={{ color: '#ff4d4f' }}>{simState.redCasualties}</span>
              <span style={{ color: '#8c8c8c', margin: '0 8px' }}>:</span>
              <span style={{ color: '#1890ff' }}>{simState.blueCasualties}</span>
            </div>
          </div>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>战力变化曲线</div>
            <div ref={chartRef} style={{ width: '100%', height: 200 }} />
          </div>
        </Card>
      </Col>
    </Row>
  );
}
