import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, List, Empty } from 'antd';
import { GraphCanvas } from '../components/GraphCanvas';
import { api } from '../services/api';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
  [key: string]: unknown;
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

  useEffect(() => {
    const loadGraph = async () => {
      try {
        const [entitiesData, relationsData] = await Promise.all([
          api.getEntities('default'),
          api.getRelations('default'),
        ]);
        const loadedNodes: GraphNode[] = (entitiesData || []).map((e: { entity_id: string; name: string; entity_type: string; basic_properties?: { side?: string } }) => ({
          id: e.entity_id,
          name: e.name,
          type: e.entity_type,
          side: e.basic_properties?.side,
        }));
        const loadedEdges: GraphEdge[] = (relationsData || []).map((r: { relation_id: string; source_entity: string; target_entity: string; relation_type: string }) => ({
          id: r.relation_id,
          source: r.source_entity,
          target: r.target_entity,
          type: r.relation_type,
        }));
        setNodes(loadedNodes);
        setEdges(loadedEdges);
      } catch (error) {
        console.error('加载图数据失败', error);
      } finally {
        setLoading(false);
      }
    };
    loadGraph();
  }, []);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <GraphCanvas nodes={nodes} edges={edges} onNodeClick={handleNodeClick} />
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
              {selectedNode.side && <Tag color={selectedNode.side === 'red' ? 'red' : 'blue'}>{selectedNode.side}</Tag>}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
