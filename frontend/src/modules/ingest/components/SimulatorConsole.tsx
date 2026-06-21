import { useState, useRef, useEffect } from 'react';
import { Row, Col, InputNumber, Select, Button, Space, Progress, Statistic } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';

interface SimulatorConsoleProps {
  onStart?: (params: SimulationParams) => void;
  onPause?: () => void;
  onStop?: () => void;
  onReset?: () => void;
  initialRedPower?: number;
  initialBluePower?: number;
  initialRedCasualties?: number;
  initialBlueCasualties?: number;
  chartData?: {
    categories: string[];
    partyASeries: number[];
    partyBSeries: number[];
  };
}

interface SimulationParams {
  partyAForce: number;
  partyBForce: number;
  speed: number;
  fireRange: number;
  reinforcementTime: number;
  supplyEfficiency: number;
}

interface SimState {
  status: 'idle' | 'running' | 'paused' | 'stopped';
  partyAPower: number;
  partyBPower: number;
  partyALosses: number;
  partyBLosses: number;
  elapsedTime: string;
}

export function SimulatorConsole({ onStart, onPause, onStop, onReset, initialRedPower = 78, initialBluePower = 65, initialRedCasualties = 0, initialBlueCasualties = 0, chartData }: SimulatorConsoleProps) {
  const [status, setStatus] = useState<SimState['status']>('idle');
  const [simState, setSimState] = useState<SimState>({
    status: 'idle',
    partyAPower: initialRedPower,
    partyBPower: initialBluePower,
    partyALosses: initialRedCasualties,
    partyBLosses: initialBlueCasualties,
    elapsedTime: '00:00:00',
  });
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || status === 'idle') return;

    const chart = echarts.init(chartRef.current);
    const categories = chartData?.categories || ['00:00', '00:05', '00:10', '00:15', '00:20', '00:25', '00:30'];
    const partyAData = chartData?.partyASeries || [simState.partyAPower];
    const partyBData = chartData?.partyBSeries || [simState.partyBPower];
    const option = {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['甲方能力', '乙方能力'],
        textStyle: { color: '#595959' },
      },
      xAxis: {
        type: 'category',
        data: categories,
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
          name: '甲方能力',
          type: 'line',
          data: partyAData,
          smooth: true,
          lineStyle: { color: '#ff4d4f', width: 2 },
          itemStyle: { color: '#ff4d4f' },
        },
        {
          name: '乙方能力',
          type: 'line',
          data: partyBData,
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
  }, [status, chartData, simState.partyAPower, simState.partyBPower]);

  const handleStart = () => {
    setStatus('running');
    setSimState((prev) => ({ ...prev, status: 'running' }));
    onStart?.({
      partyAForce: 320,
      partyBForce: 450,
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

  const handleReset = () => {
    setStatus('idle');
    setSimState({
      status: 'idle',
      partyAPower: initialRedPower,
      partyBPower: initialBluePower,
      partyALosses: initialRedCasualties,
      partyBLosses: initialBlueCasualties,
      elapsedTime: '00:00:00',
    });
    onReset?.();
  };

  return (
    <Row gutter={16}>
      <Col span={12}>
        <Card title="参数配置" style={{ borderRadius: 8 }}>
          <Form layout="vertical">
            <div style={{ marginBottom: 16, fontWeight: 500, color: '#ff4d4f' }}>基础参数</div>
            <Form.Item label="甲方初始资源">
              <InputNumber min={0} max={1000} defaultValue={320} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="乙方初始资源">
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

            <div style={{ marginBottom: 16, marginTop: 24, fontWeight: 500, color: '#1890ff' }}>运营参数</div>
            <Form.Item label="开火距离 (km)">
              <InputNumber min={0} max={10} defaultValue={2} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="支援响应时间 (min)">
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
                <Button icon={<ReloadOutlined />} onClick={handleReset}>重置</Button>
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
                title="甲方能力"
                value={simState.partyAPower}
                suffix="%"
                styles={{ content: { color: '#ff4d4f' } }}
              />
              <Progress percent={simState.partyAPower} showInfo={false} strokeColor="#ff4d4f" style={{ marginTop: 8 }} />
            </Col>
            <Col span={12}>
              <Statistic
                title="乙方能力"
                value={simState.partyBPower}
                suffix="%"
                styles={{ content: { color: '#1890ff' } }}
              />
              <Progress percent={simState.partyBPower} showInfo={false} strokeColor="#1890ff" style={{ marginTop: 8 }} />
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={12}>
              <Statistic title="甲方损耗" value={simState.partyALosses} styles={{ content: { color: '#ff4d4f' } }} />
            </Col>
            <Col span={12}>
              <Statistic title="乙方损耗" value={simState.partyBLosses} styles={{ content: { color: '#1890ff' } }} />
            </Col>
          </Row>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>损耗比</div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>
              <span style={{ color: '#ff4d4f' }}>{simState.partyALosses}</span>
              <span style={{ color: '#8c8c8c', margin: '0 8px' }}>:</span>
              <span style={{ color: '#1890ff' }}>{simState.partyBLosses}</span>
            </div>
          </div>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>能力变化曲线</div>
            <div ref={chartRef} style={{ width: '100%', height: 200 }} />
          </div>
        </Card>
      </Col>
    </Row>
  );
}
