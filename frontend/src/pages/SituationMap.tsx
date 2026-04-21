import { useState, useEffect } from 'react';
import { Card, Button, Space, Select, message } from 'antd';
import { ReloadOutlined, ZoomInOutlined, SaveOutlined } from '@ant-design/icons';
import { MapView } from '../modules/ontology/components/MapView';
import { api } from '../modules/shared/services/api';
import type { Scenario, MapUnit } from '../modules/shared/types';

export function SituationMap() {
  const [scenarioId, setScenarioId] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [units, setUnits] = useState<MapUnit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadScenarios();
  }, []);

  const loadScenarios = async () => {
    try {
      const data = await api.listScenarios();
      setScenarios(data);
    } catch (error) {
      console.error('加载场景失败', error);
      message.error('加载场景失败');
    }
  };

  const loadSituationMap = async () => {
    if (!scenarioId) {
      message.warning('请选择场景');
      return;
    }
    try {
      setLoading(true);
      const data = await api.getSituationMap(scenarioId);
      setUnits(data);
    } catch (error) {
      console.error('加载态势图失败', error);
      message.error('加载态势图失败');
    } finally {
      setLoading(false);
    }
  };

  // 模拟数据
  const mockUnits: MapUnit[] = [
    {
      id: '1',
      name: '蓝方基地',
      side: 'blue',
      position: [100, 100],
      type: 'base',
      status: 'active',
    },
    {
      id: '2',
      name: '红方基地',
      side: 'red',
      position: [700, 500],
      type: 'base',
      status: 'active',
    },
    {
      id: '3',
      name: '蓝方坦克',
      side: 'blue',
      position: [200, 200],
      type: 'tank',
      status: 'moving',
    },
    {
      id: '4',
      name: '红方坦克',
      side: 'red',
      position: [600, 400],
      type: 'tank',
      status: 'moving',
    },
    {
      id: '5',
      name: '中立村庄',
      side: 'neutral',
      position: [400, 300],
      type: 'village',
      status: 'peaceful',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="态势图"
        extra={
          <Space>
            <Button icon={<SaveOutlined />}>
              保存
            </Button>
            <Button icon={<ZoomInOutlined />}>
              缩放
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadSituationMap}>
              刷新
            </Button>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Select
            placeholder="选择场景"
            style={{ width: 300, marginRight: 16 }}
            value={scenarioId}
            onChange={setScenarioId}
            options={scenarios.map(s => ({ value: s.scenario_id, label: s.name }))}
          />
          <Button type="primary" onClick={loadSituationMap} loading={loading}>
            加载态势图
          </Button>
        </div>

        <div style={{ height: 600, border: '1px solid #e8e8e8' }}>
          <MapView units={units.length > 0 ? units : mockUnits} />
        </div>

        <Card title="单位列表" style={{ marginTop: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
            {(units.length > 0 ? units : mockUnits).map((unit) => (
              <div
                key={unit.id}
                style={{
                  padding: 12,
                  border: '1px solid #e8e8e8',
                  borderRadius: 8,
                  backgroundColor: unit.side === 'blue' ? '#e6f7ff' : unit.side === 'red' ? '#fff2f0' : '#f6ffed',
                }}
              >
                <div style={{ fontWeight: 500, marginBottom: 4 }}>{unit.name}</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>类型: {unit.type}</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>状态: {unit.status}</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>位置: ({unit.position[0]}, {unit.position[1]})</div>
              </div>
            ))}
          </div>
        </Card>
      </Card>
    </div>
  );
}