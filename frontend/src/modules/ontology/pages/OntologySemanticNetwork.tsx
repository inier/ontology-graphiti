import { useState, useEffect, useCallback } from 'react';
import { Row, Col, Card, Drawer, Descriptions, Tag, Spin, Button, Space, message, Statistic, Tabs, Select, Input, Modal, Empty, Tooltip } from 'antd';
import { InfoCircleOutlined, ApartmentOutlined, DatabaseOutlined, SaveOutlined, ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { GraphCanvas } from '../components/GraphCanvas';
import { OntologySchemaViewer } from '../components/OntologySchemaViewer';
import { useScenario, useWorkspace, useOntologyVersion } from '../../shared/components/AppLayout';
import { api } from '../../shared/services/api';
import { EmptyState } from '../../shared/components/organisms';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
  properties?: Record<string, unknown>;
  cluster?: string | null;
  type_definition_id?: string | null;
  type_definition_name?: string | null;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface SemanticMapCluster {
  cluster_id: string;
  cluster_name: string;
  cluster_type: string;
  object_ids: string[];
  properties: Record<string, unknown>;
}

interface SemanticMapStatistics {
  total_objects: number;
  total_relations: number;
  total_clusters: number;
  objects_by_type: Record<string, number>;
  relations_by_type: Record<string, number>;
  avg_relations_per_object: number;
  coverage_score: number;
}

interface SemanticMapSummary {
  id: string;
  name: string;
  description: string;
  ontology_version_id: string;
  ontology_id: string;
  scenario_id: string | null;
  status: string;
  total_objects: number;
  total_relations: number;
  total_clusters: number;
  created_at: string;
  created_by: string;
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
  ontology_id?: string;
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
  const { currentScenario, scenarios } = useScenario();
  const { currentWorkspace } = useWorkspace();
  const { currentVersionId: scenarioVersionId } = useOntologyVersion();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [clusters, setClusters] = useState<SemanticMapCluster[]>([]);
  const [statistics, setStatistics] = useState<SemanticMapStatistics | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ entityCount: 0, relationCount: 0 });
  const [versions, setVersions] = useState<OntologyVersion[]>([]);
  const [currentVersion, setCurrentVersion] = useState<string>('latest');
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('graph');
  const [commitModalOpen, setCommitModalOpen] = useState(false);
  const [commitMessage, setCommitMessage] = useState('');
  const [committing, setCommitting] = useState(false);

  const [semanticMaps, setSemanticMaps] = useState<SemanticMapSummary[]>([]);
  const [currentSemanticMapId, setCurrentSemanticMapId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const loadVersions = async (scenarioId?: string) => {
    if (!scenarioId || !currentWorkspace) return;
    try {
      setVersionsLoading(true);
      const versionList = await api.getScenarioOntologyVersions(currentWorkspace, scenarioId);
      setVersions(versionList);

      if (versionList.length > 0) {
        if (scenarioVersionId && versionList.some(v => v.version_id === scenarioVersionId)) {
          setCurrentVersion(scenarioVersionId);
        } else {
          const sorted = [...versionList].sort((a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
          setCurrentVersion(sorted[0].version_id);
        }
      } else {
        setCurrentVersion('latest');
      }
    } catch (error) {
      console.error('加载版本列表失败:', error);
    } finally {
      setVersionsLoading(false);
    }
  };

  const loadSemanticMaps = useCallback(async (scenarioId?: string) => {
    if (!scenarioId) {
      setSemanticMaps([]);
      setCurrentSemanticMapId(null);
      return;
    }
    try {
      const result = await api.listSemanticMaps({ scenario_id: scenarioId });
      setSemanticMaps(result.semantic_maps);
      if (result.semantic_maps.length > 0) {
        const latest = result.semantic_maps[0];
        setCurrentSemanticMapId(latest.id);
      } else {
        setCurrentSemanticMapId(null);
      }
    } catch (error) {
      console.error('加载语义地图列表失败:', error);
      setSemanticMaps([]);
      setCurrentSemanticMapId(null);
    }
  }, []);

  const loadSemanticMapGraph = useCallback(async (mapId: string) => {
    try {
      setLoading(true);
      const result = await api.getSemanticMapGraph(mapId);
      const graphNodes: GraphNode[] = result.nodes.map(n => ({
        id: n.id,
        name: n.name,
        type: n.type,
        properties: n.properties,
        cluster: n.cluster,
        type_definition_id: n.type_definition_id,
        type_definition_name: n.type_definition_name,
      }));
      const graphEdges: GraphEdge[] = result.edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type || e.display_name || 'related_to',
      }));
      setNodes(graphNodes);
      setEdges(graphEdges);
      setClusters(result.clusters || []);
      setStatistics(result.statistics as unknown as SemanticMapStatistics);
      setStats({
        entityCount: graphNodes.length,
        relationCount: graphEdges.length,
      });
    } catch (error) {
      console.error('加载语义地图图谱失败:', error);
      message.error('加载语义地图图谱失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLegacyGraph = useCallback(async (scenarioId: string, versionId?: string) => {
    if (!currentWorkspace) return;
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
        setClusters([]);
        setStatistics(null);
        setStats({
          entityCount: graphNodes.length,
          relationCount: graphEdges.length
        });
      } else {
        const [entitiesResult, relationsResult] = await Promise.all([
          api.getEntities(scenarioId, currentWorkspace).catch(() => ({ entities: [] })),
          api.getRelations(scenarioId, currentWorkspace).catch(() => ({ nodes: [], edges: [] }))
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
        setClusters([]);
        setStatistics(null);
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
  }, [currentWorkspace]);

  const loadGraph = useCallback(async (scenarioId?: string, versionId?: string) => {
    if (!scenarioId || !currentWorkspace) return;

    await loadSemanticMaps(scenarioId);

    if (currentSemanticMapId) {
      await loadSemanticMapGraph(currentSemanticMapId);
    } else {
      await loadLegacyGraph(scenarioId, versionId);
    }
  }, [currentWorkspace, currentSemanticMapId, loadSemanticMaps, loadSemanticMapGraph, loadLegacyGraph]);

  const handleGenerateSemanticMap = async () => {
    if (!currentScenario || !currentWorkspace) return;
    try {
      setGenerating(true);

      const scenario = scenarios.find(s => s.scenario_id === currentScenario);
      const ontologyId = scenario?.ontology_id || '';
      const versionId = currentVersion !== 'latest' ? currentVersion : '';

      if (!ontologyId) {
        message.warning('当前场景未关联本体，无法生成语义地图');
        return;
      }

      const result = await api.createSemanticMap({
        name: `${scenario?.name || currentScenario} - 语义地图`,
        description: `基于场景 ${scenario?.name || currentScenario} 自动生成的语义地图`,
        ontology_version_id: versionId || 'latest',
        ontology_id: ontologyId,
        scenario_id: currentScenario,
      });

      if (result.id) {
        setCurrentSemanticMapId(result.id);
        await loadSemanticMapGraph(result.id);
        await loadSemanticMaps(currentScenario);
        message.success('语义地图生成成功');
      }
    } catch (error) {
      console.error('生成语义地图失败:', error);
      message.error('生成语义地图失败');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerateSemanticMap = async () => {
    if (!currentSemanticMapId) return;
    try {
      setGenerating(true);
      const result = await api.regenerateSemanticMap(currentSemanticMapId);
      if (result.id) {
        await loadSemanticMapGraph(currentSemanticMapId);
        message.success('语义地图重新生成成功');
      }
    } catch (error) {
      console.error('重新生成语义地图失败:', error);
      message.error('重新生成语义地图失败');
    } finally {
      setGenerating(false);
    }
  };

  const handleSemanticMapChange = async (mapId: string) => {
    if (mapId === '__legacy__') {
      setCurrentSemanticMapId(null);
      if (currentScenario) {
        await loadLegacyGraph(currentScenario, currentVersion);
      }
      return;
    }
    setCurrentSemanticMapId(mapId);
    await loadSemanticMapGraph(mapId);
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
      setCurrentSemanticMapId(null);
      await loadLegacyGraph(currentScenario, versionId);
    }
  };

  const handleCommitVersion = async () => {
    if (!currentScenario || !currentWorkspace) return;
    try {
      setCommitting(true);
      await api.commitScenarioOntologyVersion(currentWorkspace, currentScenario, commitMessage);
      message.success('版本提交成功');
      setCommitModalOpen(false);
      setCommitMessage('');
      await loadVersions(currentScenario);
    } catch (error) {
      console.error('提交版本失败:', error);
      message.error('提交版本失败');
    } finally {
      setCommitting(false);
    }
  };

  useEffect(() => {
    if (currentScenario && currentWorkspace) {
      loadVersions(currentScenario);
      loadGraph(currentScenario, scenarioVersionId || 'latest');
    }
  }, [currentScenario, currentWorkspace, scenarioVersionId]);

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
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="对象总数"
                  value={stats.entityCount}
                  styles={{ content: { color: '#1890ff' } }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="关系总数"
                  value={stats.relationCount}
                  styles={{ content: { color: '#52c41a' } }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="聚类数"
                  value={clusters.length}
                  styles={{ content: { color: '#722ed1' } }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="覆盖率"
                  value={statistics?.coverage_score ? `${(statistics.coverage_score * 100).toFixed(0)}%` : '-'}
                  styles={{ content: { color: '#fa8c16' } }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small">
                <Space wrap size="middle" style={{ width: '100%', justifyContent: 'space-between' }}>
                  {!currentScenario ? (
                    <span style={{ color: '#ff4d4f' }}>
                      <InfoCircleOutlined /> 请先选择场景
                    </span>
                  ) : (
                    <>
                      <Space size="middle">
                        <span style={{ color: '#333', fontSize: 13, fontWeight: 500 }}>
                          场景: {scenarios.find(s => s.scenario_id === currentScenario)?.name || currentScenario}
                        </span>
                      </Space>
                      <Space size={8}>
                        <Select
                          value={currentSemanticMapId || '__legacy__'}
                          onChange={handleSemanticMapChange}
                          style={{ minWidth: 160 }}
                          size="small"
                          options={[
                            { value: '__legacy__', label: '原始数据' },
                            ...semanticMaps.map(m => ({
                              value: m.id,
                              label: `${m.name} (${m.total_objects}对象)`,
                            })),
                          ]}
                        />
                        {currentSemanticMapId ? (
                          <Tooltip title="重新生成">
                            <Button
                              size="small"
                              icon={<ReloadOutlined />}
                              onClick={handleRegenerateSemanticMap}
                              loading={generating}
                            />
                          </Tooltip>
                        ) : (
                          <Button
                            type="primary"
                            size="small"
                            icon={<PlusOutlined />}
                            onClick={handleGenerateSemanticMap}
                            loading={generating}
                          >
                            生成语义地图
                          </Button>
                        )}
                        <Select
                          value={currentVersion}
                          onChange={handleVersionChange}
                          loading={versionsLoading}
                          style={{ minWidth: 180 }}
                          size="small"
                          options={[
                            { value: 'latest', label: '最新版本' },
                            ...versions.map(v => ({
                              value: v.version_id,
                              label: `${v.commit_message} (E:${v.entity_count} R:${v.relation_count})`,
                            })),
                          ]}
                        />
                        <Button
                          size="small"
                          icon={<SaveOutlined />}
                          onClick={() => setCommitModalOpen(true)}
                        >
                          提交版本
                        </Button>
                      </Space>
                    </>
                  )}
                </Space>
              </Card>
            </Col>
          </Row>

          {statistics && (
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={24}>
                <Card size="small" title="类型分布">
                  <Space wrap>
                    {Object.entries(statistics.objects_by_type).map(([type, count]) => (
                      <Tag key={type} color={getEntityTypeColor(type)}>
                        {type}: {count}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              </Col>
            </Row>
          )}

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
                  <EmptyState
                    icon={<ApartmentOutlined />}
                    title="暂无语义地图数据"
                    description={
                      currentSemanticMapId
                        ? '语义地图为空，请尝试重新生成'
                        : '请点击"生成语义地图"按钮，或通过数据摄入添加实体'
                    }
                    actionLabel={currentSemanticMapId ? '重新生成' : '生成语义地图'}
                    onAction={currentSemanticMapId ? handleRegenerateSemanticMap : handleGenerateSemanticMap}
                    showSampleData={!currentSemanticMapId && !!currentScenario}
                    onLoadSampleData={async () => {
                      if (!currentWorkspace) { message.warning('请先选择工作空间'); return; }
                      try {
                        await api.generateSampleData(currentWorkspace);
                        message.success('示例数据已加载');
                        if (currentScenario) {
                          loadGraph(currentScenario, currentVersion);
                        }
                      } catch (e) { message.error('加载示例数据失败'); }
                    }}
                  />
                </Card>
              ) : (
                <GraphCanvas
                  nodes={nodes}
                  edges={edges}
                  onNodeClick={handleNodeClick}
                  onEdgeClick={handleEdgeClick}
                  onRefresh={() => {
                    if (currentSemanticMapId) {
                      loadSemanticMapGraph(currentSemanticMapId);
                    } else if (currentScenario) {
                      loadLegacyGraph(currentScenario, currentVersion);
                    }
                  }}
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
            {selectedNode.type_definition_name && (
              <Descriptions.Item label="本体定义">
                <Tag color="geekblue">{selectedNode.type_definition_name}</Tag>
              </Descriptions.Item>
            )}
            {selectedNode.cluster && (
              <Descriptions.Item label="所属聚类">
                <Tag color="purple">{selectedNode.cluster}</Tag>
              </Descriptions.Item>
            )}
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
                      {typeof value === 'object' ? JSON.stringify(value) : String(value)}
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

      <Modal
        title="提交版本"
        open={commitModalOpen}
        onOk={handleCommitVersion}
        onCancel={() => { setCommitModalOpen(false); setCommitMessage(''); }}
        confirmLoading={committing}
        okText="提交"
        cancelText="取消"
      >
        <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
          将当前场景的本体数据锁定为新版本，提交后可在版本列表中切换查看。
        </div>
        <Input.TextArea
          value={commitMessage}
          onChange={e => setCommitMessage(e.target.value)}
          placeholder="请输入版本说明（可选）"
          rows={3}
          maxLength={200}
          showCount
        />
      </Modal>
    </>
  );
}
