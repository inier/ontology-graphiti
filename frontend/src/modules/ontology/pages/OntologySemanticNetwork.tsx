import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button, Space, message } from 'antd';
import { GraphCanvas } from '../components/GraphCanvas';
import { PageHeader } from '../../shared';
import { useScenario } from '../../shared/components/AppLayout';

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

export function OntologySemanticNetwork() {
  const { currentScenario } = useScenario();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);

  const loadGraph = async (scenarioId?: string) => {
    if (!scenarioId) return;
    try {
      setLoading(true);
      // Mock data for now
      const mockData = {
        nodes: [
          { id: '1', name: 'Entity 1', type: 'person', side: 'blue' },
          { id: '2', name: 'Entity 2', type: 'organization', side: 'red' },
          { id: '3', name: 'Entity 3', type: 'location' },
        ],
        edges: [
          { id: '1-2', source: '1', target: '2', type: 'related_to' },
          { id: '1-3', source: '1', target: '3', type: 'located_at' },
        ],
      };
      setNodes(mockData.nodes || []);
      setEdges(mockData.edges || []);
    } catch (error) {
      console.error('加载语义网络失败', error);
      message.error('加载语义网络失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentScenario) {
      loadGraph(currentScenario);
    }
  }, [currentScenario]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  return (
    <div style={{ padding: 24 }}>
      <PageHeader title="本体语义网络" />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Space>
            <Button
              onClick={() => currentScenario && loadGraph(currentScenario)}
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
                <Spin description="加载语义网络数据..." />
              </div>
            </Card>
          ) : (
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              onNodeClick={handleNodeClick}
              onRefresh={() => currentScenario && loadGraph(currentScenario)}
            />
          )}
        </Col>
      </Row>

      <Drawer
        title="节点详情"
        placement="right"
        width={400}
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
      >
        {selectedNode && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="节点ID">{selectedNode.id}</Descriptions.Item>
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
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
