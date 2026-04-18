import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button } from 'antd';
import { GraphCanvas } from '../components/GraphCanvas';
import { api } from '../services/api';

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

export function OntologyGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);

  const loadGraph = async () => {
    try {
      setLoading(true);
      const scenarios = await api.listScenarios();
      if (scenarios.length === 0) {
        setLoading(false);
        return;
      }

      const scenarioId = scenarios[0].scenario_id;
      const [entitiesData, relationsData] = await Promise.all([
        api.getEntities(scenarioId),
        api.getRelations(scenarioId),
      ]);

      const loadedNodes: GraphNode[] = entitiesData.map((e) => ({
        id: e.entity_id,
        name: e.name,
        type: e.entity_type,
        side: (e.basic_properties?.side as string) || undefined,
      }));

      const loadedEdges: GraphEdge[] = relationsData.edges.map((r) => ({
        id: r.id,
        source: r.source,
        target: r.target,
        type: r.type,
      }));

      setNodes(loadedNodes);
      setEdges(loadedEdges);
    } catch (error) {
      console.error('加载图数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, []);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  return (
    <div>
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
              onRefresh={loadGraph}
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
