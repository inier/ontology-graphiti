import { useState, useEffect } from 'react';
import { Card, Row, Col, Tree, Tag, Empty, Spin, Select, Space, Button } from 'antd';
import { api } from '../services/api';
import type { Entity } from '../types';

interface GraphRelation {
  id: string;
  source: string;
  target: string;
  type: string;
}

export function GraphView() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<GraphRelation[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('default');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadGraphData();
  }, [selectedScenario]);

  const loadGraphData = async () => {
    setLoading(true);
    try {
      const [entitiesData, relationsData] = await Promise.all([
        api.getEntities(selectedScenario),
        api.getRelations(selectedScenario),
      ]);
      setEntities(entitiesData);
      setRelations(relationsData.edges || []);
    } catch (error) {
      console.error('加载图数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const entityTreeData = () => {
    const typeMap = new Map<string, Entity[]>();
    entities.forEach((entity) => {
      const list = typeMap.get(entity.entity_type) || [];
      list.push(entity);
      typeMap.set(entity.entity_type, list);
    });

    return Array.from(typeMap.entries()).map(([type, items]) => ({
      title: `${type} (${items.length})`,
      key: type,
      children: items.map((item) => ({
        title: item.name,
        key: item.entity_id,
      })),
    }));
  };

  const relationList = relations.slice(0, 20).map((rel) => ({
    id: rel.id,
    source: entities.find((e) => e.entity_id === rel.source)?.name || rel.source,
    target: entities.find((e) => e.entity_id === rel.target)?.name || rel.target,
    type: rel.type,
  }));

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="本体图谱视图">
          <Space style={{ marginBottom: 16 }}>
            <Select
              value={selectedScenario}
              onChange={setSelectedScenario}
              style={{ width: 200 }}
              options={[
                { value: 'default', label: '默认场景' },
              ]}
            />
            <Button onClick={loadGraphData}>刷新</Button>
          </Space>

          <Row gutter={16}>
            <Col span={8}>
              <Card title="实体类型树" size="small">
                {loading ? (
                  <Spin />
                ) : entities.length > 0 ? (
                  <Tree treeData={entityTreeData()} />
                ) : (
                  <Empty description="暂无实体数据" />
                )}
              </Card>
            </Col>

            <Col span={16}>
              <Card title="关系网络" size="small">
                {loading ? (
                  <Spin />
                ) : relationList.length > 0 ? (
                  <div style={{ maxHeight: 400, overflow: 'auto' }}>
                    {relationList.map((rel) => (
                      <Tag key={rel.id} style={{ margin: 4 }}>
                        {rel.source} → [{rel.type}] → {rel.target}
                      </Tag>
                    ))}
                  </div>
                ) : (
                  <Empty description="暂无关系数据" />
                )}
              </Card>
            </Col>
          </Row>
        </Card>
      </Space>
    </div>
  );
}
