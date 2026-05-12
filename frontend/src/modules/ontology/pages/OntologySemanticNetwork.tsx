import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button, Space, message, Statistic } from 'antd';
import { ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { GraphCanvas } from '../components/GraphCanvas';
import { PageHeader } from '../../shared';
import { useScenario } from '../../shared/components/AppLayout';
import { api } from '../../shared/services/api';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
  properties?: Record<string, unknown>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface Entity {
  entity_id: string;
  name: string;
  entity_type: string;
  side?: string;
  properties?: Record<string, unknown>;
  created_at?: string;
}

export function OntologySemanticNetwork() {
  const { currentScenario } = useScenario();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ entityCount: 0, relationCount: 0 });

  const loadGraph = async (scenarioId?: string) => {
    if (!scenarioId) return;
    try {
      setLoading(true);
      
      // 并行获取实体和关系数据
      const [entitiesResult, relationsResult] = await Promise.all([
        api.getEntities(scenarioId).catch(() => {
          // 返回空数组作为降级
          return { entities: [] };
        }),
        api.getRelations(scenarioId).catch(() => {
          // 返回空数据作为降级
          return { nodes: [], links: [] };
        })
      ]);

      // 确保是数组格式
      let entitiesList: Entity[] = [];
      if (Array.isArray(entitiesResult)) {
        entitiesList = entitiesResult as unknown as Entity[];
      } else if (entitiesResult && typeof entitiesResult === 'object' && 'entities' in entitiesResult) {
        entitiesList = (entitiesResult as unknown as { entities: Entity[] }).entities || [];
      }
      const relations = relationsResult as { nodes?: GraphNode[]; links?: GraphEdge[]; edges?: GraphEdge[] };
      const relLinks = relations.links || relations.edges || [];

      // 转换为 G6 格式的节点
      const graphNodes: GraphNode[] = entitiesList.map((e: Entity) => ({
        id: e.entity_id,
        name: e.name,
        type: e.entity_type,
        side: e.side,
        properties: e.properties
      }));

      // 转换为 G6 格式的边
      const graphEdges: GraphEdge[] = relLinks.map((l: { id?: string; source: string; target: string; type?: string; relation_type?: string }) => ({
        id: l.id || `${l.source}-${l.target}`,
        source: l.source,
        target: l.target,
        type: l.type || l.relation_type || 'related_to'
      }));

      setNodes(graphNodes);
      setEdges(graphEdges);
      setStats({
        entityCount: graphNodes.length,
        relationCount: graphEdges.length
      });
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

  const getEntityTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      Unit: 'blue',
      Equipment: 'green',
      Location: 'orange',
      Event: 'red',
      Organization: 'purple',
      Person: 'cyan',
      Weapon: 'magenta'
    };
    return colors[type] || 'default';
  };

  return (
    <div style={{ padding: 24 }}>
      <PageHeader title="语义地图" />

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic 
              title="实体总数" 
              value={stats.entityCount} 
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic 
              title="关系总数" 
              value={stats.relationCount} 
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small">
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => currentScenario && loadGraph(currentScenario)}
                loading={loading}
              >
                刷新
              </Button>
              {!currentScenario && (
                <span style={{ color: '#ff4d4f' }}>
                  <InfoCircleOutlined /> 请先选择场景
                </span>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          {loading ? (
            <Card style={{ borderRadius: 8 }}>
              <div style={{ textAlign: 'center', padding: 100 }}>
                <Spin description="加载语义地图数据..." />
              </div>
            </Card>
          ) : nodes.length === 0 ? (
            <Card style={{ borderRadius: 8 }}>
              <div style={{ textAlign: 'center', padding: 100, color: '#8c8c8c' }}>
                暂无语义地图数据，请先通过数据摄入添加实体
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
        size="large"
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
      >
        {selectedNode && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="节点ID">{selectedNode.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{selectedNode.name}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={getEntityTypeColor(selectedNode.type)}>{selectedNode.type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="方位">
              {selectedNode.side ? (
                <Tag color={selectedNode.side === 'red' ? 'red' : 'blue'}>
                  {selectedNode.side === 'red' ? '红方' : '蓝方'}
                </Tag>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="属性">
              {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 ? (
                <Descriptions column={1} size="small">
                  {Object.entries(selectedNode.properties).map(([key, value]) => (
                    <Descriptions.Item key={key} label={key}>
                      {String(value)}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              ) : (
                '无'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="关联关系">
              {edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).length > 0 ? (
                <Space direction="vertical">
                  {edges
                    .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                    .slice(0, 10)
                    .map((edge, idx) => {
                      const relatedNodeId = edge.source === selectedNode.id ? edge.target : edge.source;
                      const relatedNode = nodes.find(n => n.id === relatedNodeId);
                      return (
                        <Tag key={idx}>
                          {edge.type}: {relatedNode?.name || relatedNodeId}
                        </Tag>
                      );
                    })}
                </Space>
              ) : (
                '无'
              )}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
