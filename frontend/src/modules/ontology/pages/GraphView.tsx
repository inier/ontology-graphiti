import { useState, useEffect } from 'react';
import { Card, Button, Space, Select, Input, message, Spin } from 'antd';
import { SearchOutlined, ReloadOutlined, ExportOutlined, PlusOutlined } from '@ant-design/icons';
import { GraphCanvas } from '../components/GraphCanvas';
import { api } from '../../shared/services/api';
import type { Scenario } from '../../shared/types';

export function GraphView() {
  const [scenarioId, setScenarioId] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
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

  const loadGraphData = async () => {
    if (!scenarioId) {
      message.warning('请选择场景');
      return;
    }
    try {
      setLoading(true);
      const data = await api.getRelations(scenarioId);
      setNodes(data.nodes);
      setEdges(data.edges);
    } catch (error) {
      console.error('加载图谱数据失败', error);
      message.error('加载图谱数据失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="图谱视图"
        extra={
          <Space>
            <Input.Search
              placeholder="搜索实体"
              style={{ width: 200 }}
              prefix={<SearchOutlined />}
            />
            <Button type="primary" icon={<PlusOutlined />}>
              添加节点
            </Button>
            <Button icon={<ExportOutlined />}>
              导出
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadGraphData}>
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
          <Button type="primary" onClick={loadGraphData} loading={loading}>
            加载图谱
          </Button>
        </div>

        <div style={{ height: 600, border: '1px solid #e8e8e8' }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Spin size="large" />
            </div>
          ) : (
            <GraphCanvas nodes={nodes} edges={edges} />
          )}
        </div>
      </Card>
    </div>
  );
}