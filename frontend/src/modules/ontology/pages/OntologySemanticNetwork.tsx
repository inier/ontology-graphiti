import { useState, useEffect } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button, Space, message, Statistic, Tabs } from 'antd';
import { InfoCircleOutlined, ApartmentOutlined, DatabaseOutlined } from '@ant-design/icons';
import { GraphCanvas } from '../components/GraphCanvas';
import { OntologySchemaViewer } from '../components/OntologySchemaViewer';
import { useScenario, useWorkspace } from '../../shared/components/AppLayout';
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

interface OntologyVersion {
  version_id: string;
  ontology_id: string;
  doc_id: string;
  doc_type: string;
  parent_version?: string;
  commit_message: string;
  created_at: string;
  entity_count: number;
  relation_count: number;
  event_count: number;
}

export function OntologySemanticNetwork() {
  const { currentScenario } = useScenario();
  const { currentWorkspace } = useWorkspace();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ entityCount: 0, relationCount: 0 });
  const [versions, setVersions] = useState<OntologyVersion[]>([]);
  const [currentVersion, setCurrentVersion] = useState<string>('latest');
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('graph');

  const loadVersions = async (scenarioId?: string) => {
    if (!scenarioId || !currentWorkspace) return;
    try {
      setVersionsLoading(true);
      const versionList = await api.getScenarioOntologyVersions(currentWorkspace, scenarioId);
      setVersions(versionList);

      if (versionList.length > 0) {
        const sorted = [...versionList].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setCurrentVersion(sorted[0].version_id);
      }
    } catch (error) {
      console.error('加载版本列表失败:', error);
    } finally {
      setVersionsLoading(false);
    }
  };

  const loadGraph = async (scenarioId?: string, versionId?: string) => {
    if (!scenarioId || !currentWorkspace) return;
    try {
      setLoading(true);

      if (versionId && versionId !== 'latest') {
        const versionData = await api.getVersionOntologyData(currentWorkspace, scenarioId, versionId);
        const graphNodes: GraphNode[] = versionData.entities.map((e: any) => ({
          id: e.entity_id,
          name: e.name,
          type: e.entity_type,
          side: e.side,
          properties: e.properties
        }));
        const graphEdges: GraphEdge[] = versionData.relations.map((l: any) => ({
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
      } else {
        const [entitiesResult, relationsResult] = await Promise.all([
          api.getEntities(scenarioId, currentWorkspace).catch(() => {
            return { entities: [] };
          }),
          api.getRelations(scenarioId, currentWorkspace).catch(() => {
            return { nodes: [], links: [] };
          })
        ]);

        let entitiesList: Entity[] = [];
        if (Array.isArray(entitiesResult)) {
          entitiesList = entitiesResult as unknown as Entity[];
        } else if (entitiesResult && typeof entitiesResult === 'object' && 'entities' in entitiesResult) {
          entitiesList = (entitiesResult as unknown as { entities: Entity[] }).entities || [];
        }
        const relations = relationsResult as { nodes?: GraphNode[]; links?: GraphEdge[]; edges?: GraphEdge[] };
        const relLinks = relations.links || relations.edges || [];

        const graphNodes: GraphNode[] = entitiesList.map((e: Entity) => ({
          id: e.entity_id,
          name: e.name,
          type: e.entity_type,
          side: e.side,
          properties: e.properties
        }));

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
      }
    } catch (error) {
      console.error('加载语义网络失败:', error);
      message.error('加载语义网络失败');
    } finally {
      setLoading(false);
    }
  };

  const handleVersionChange = async (versionId: string) => {
    setCurrentVersion(versionId);
    if (currentScenario && currentWorkspace) {
      if (versionId !== 'latest') {
        try {
          await api.switchScenarioOntologyVersion(currentWorkspace, currentScenario, versionId);
          message.success('已切换本体版本');
        } catch (error) {
          console.error('切换版本失败:', error);
        }
      }
      await loadGraph(currentScenario, versionId);
    }
  };

  useEffect(() => {
    if (currentScenario && currentWorkspace) {
      loadVersions(currentScenario);
      loadGraph(currentScenario, 'latest');
    }
  }, [currentScenario, currentWorkspace]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedEdge(null);
    setSelectedNode(node);
  };

  const handleEdgeClick = (edge: GraphEdge) => {
    setSelectedNode(null);
    setSelectedEdge(edge);
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

  const tabItems = [
    {
      key: 'graph',
      label: (
        <span>
          <ApartmentOutlined style={{ marginRight: 4 }} />
          语义地图
        </span>
      ),
      children: (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="实体总数"
                  value={stats.entityCount}
                  styles={{ content: { color: '#1890ff' } }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="关系总数"
                  value={stats.relationCount}
                  styles={{ content: { color: '#52c41a' } }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small">
                <Space wrap>
                  {!currentScenario && (
                    <span style={{ color: '#ff4d4f' }}>
                      <InfoCircleOutlined /> 请先选择场景
                    </span>
                  )}
                  {currentScenario && (
                    <span style={{ color: '#666', fontSize: 13 }}>
                      当前场景: {currentScenario}
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
                  onEdgeClick={handleEdgeClick}
                  onRefresh={() => currentScenario && loadGraph(currentScenario, currentVersion)}
                  versions={versions}
                  currentVersion={currentVersion}
                  onVersionChange={handleVersionChange}
                  versionsLoading={versionsLoading}
                />
              )}
            </Col>
          </Row>
        </>
      ),
    },
    {
      key: 'schema',
      label: (
        <span>
          <DatabaseOutlined style={{ marginRight: 4 }} />
          本体定义
        </span>
      ),
      children: <OntologySchemaViewer />,
    },
  ];

  return (
    <>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
      />

      <Drawer
        title={selectedEdge ? '边详情' : '节点详情'}
        placement="right"
        size="large"
        open={!!selectedNode || !!selectedEdge}
        onClose={() => { setSelectedNode(null); setSelectedEdge(null); }}
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
        {selectedEdge && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="边ID">{selectedEdge.id}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color="blue">{selectedEdge.type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="源节点">
              {nodes.find((n) => n.id === selectedEdge.source)?.name || selectedEdge.source}
            </Descriptions.Item>
            <Descriptions.Item label="目标节点">
              {nodes.find((n) => n.id === selectedEdge.target)?.name || selectedEdge.target}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </>
  );
}
