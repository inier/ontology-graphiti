import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button, Select, Space, message } from 'antd';
import { GraphCanvas } from '../components/GraphCanvas';
import { api } from '../../shared/services/api';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface Scenario {
  scenario_id: string;
  name: string;
  description: string;
  entity_count: number;
}

export function OntologyGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);

  const loadScenarios = async () => {
    try {
      const data = await api.listScenarios();
      setScenarios(data);
      if (data.length > 0) {
        setSelectedScenarioId(data[0].scenario_id);
      }
    } catch (error) {
      console.error('加载场景失败', error);
    }
  };

  const loadGraph = async (scenarioId?: string) => {
    if (!scenarioId) return;
    try {
      setLoading(true);
      const result = await api.getRelations(scenarioId);
      setNodes(result.nodes as GraphNode[]);
      setEdges(result.edges as GraphEdge[]);
    } catch (error) {
      console.error('加载图数据失败', error);
      message.error('加载图数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScenarios();
  }, []);

  useEffect(() => {
    if (selectedScenarioId) {
      loadGraph(selectedScenarioId);
    }
  }, [selectedScenarioId]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  const getScenarioOptions = () => {
    return scenarios.map(scenario => ({
      label: `${scenario.name} (${scenario.entity_count} 个实体)`,
      value: scenario.scenario_id,
    }));
  };

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Space>
            <span style={{ fontWeight: 500 }}>选择场景：</span>
            <Select
              style={{ width: 400 }}
              placeholder="选择场景"
              options={getScenarioOptions()}
              value={selectedScenarioId}
              onChange={(value) => setSelectedScenarioId(value)}
            />
            <Button
              onClick={() => selectedScenarioId && loadGraph(selectedScenarioId)}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          {loading ? (
            <Card style={{ borderRadius: 8 }}>
              <div style={{ textAlign: 'center', padding: 100 }}>
                <Spin description="加载图谱数据..." />
              </div>
            </Card>
          ) : (
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              onNodeClick={handleNodeClick}
              onRefresh={() => selectedScenarioId && loadGraph(selectedScenarioId)}
            />
          )}
        </Col>
      </Row>

      <Drawer
        title="实体详情"
        placement="right"
        width={400}
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
      >
        {selectedNode && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="实体ID">{selectedNode.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{selectedNode.name}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color="blue">{selectedNode.type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="方位">
              {selectedNode.side ? (
                <Tag color={selectedNode.side === 'red' ? 'red' : 'blue'}>{selectedNode.side}</Tag>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="属性">
              <Button type="link">展开</Button>
            </Descriptions.Item>
            <Descriptions.Item label="关系">
              <Button type="link">展开</Button>
            </Descriptions.Item>
            <Descriptions.Item label="历史">
              <Button type="link">展开</Button>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}