import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Row, Col, Card, List, Input, Tag, Popconfirm, Empty, Spin, Modal, Form, Select as AntSelect, message, Drawer } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SearchOutlined, HistoryOutlined, ExportOutlined } from '@ant-design/icons';
import adapter from '../../shared/components/adapter';
import { PageHeader } from '../../shared/components/PageHeader';
import { useOntologyStore } from '../stores/ontologyStore';
import { EntityTypeEditor } from '../components/EntityTypeEditor';
import { VersionPanel } from '../components/VersionPanel';
import type { EntityType } from '../services/ontologyApi';

const Button = adapter.getButton();

const CLASSIFICATION_COLORS: Record<string, string> = {
  TS: 'red',
  S: 'orange',
  C: 'blue',
  U: 'green',
};

export function OntologyDesignerPage() {
  const {
    entityTypes,
    selectedTypeId,
    document,
    loading,
    error,
    loadEntityTypes,
    createEntityType,
    updateEntityType,
    deleteEntityType,
    setSelectedTypeId,
    loadOntologyDocument,
    exportDocument,
  } = useOntologyStore();

  const [searchText, setSearchText] = useState('');
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [versionDrawerVisible, setVersionDrawerVisible] = useState(false);
  const [createForm] = Form.useForm();
  const graphCanvasRef = useRef<HTMLDivElement>(null);

  const documentId = 'default';

  useEffect(() => {
    loadEntityTypes(documentId);
    loadOntologyDocument(documentId);
  }, []);

  const filteredTypes = useMemo(() => {
    if (!searchText) return entityTypes;
    const lower = searchText.toLowerCase();
    return entityTypes.filter(
      (t) =>
        t.name.toLowerCase().includes(lower) ||
        t.display_name.toLowerCase().includes(lower)
    );
  }, [entityTypes, searchText]);

  const selectedEntityType = useMemo(
    () => entityTypes.find((t) => t.type_id === selectedTypeId) || null,
    [entityTypes, selectedTypeId]
  );

  const handleCreate = useCallback(async () => {
    try {
      const values = await createForm.validateFields();
      await createEntityType(documentId, {
        name: values.name,
        display_name: values.display_name || values.name,
        description: values.description || '',
        classification_level: values.classification_level || 'U',
        properties: [],
        relations: [],
      });
      setCreateModalVisible(false);
      createForm.resetFields();
      adapter.getMessage().success('创建成功');
    } catch {
      // validation error
    }
  }, [documentId, createEntityType, createForm]);

  const handleSaveEntityType = useCallback(
    async (data: Partial<EntityType>) => {
      if (!selectedTypeId) return;
      await updateEntityType(documentId, selectedTypeId, data);
      adapter.getMessage().success('保存成功');
    },
    [documentId, selectedTypeId, updateEntityType]
  );

  const handleDelete = useCallback(
    async (typeId: string) => {
      await deleteEntityType(documentId, typeId);
      adapter.getMessage().success('删除成功');
    },
    [documentId, deleteEntityType]
  );

  const handleExport = useCallback(async () => {
    const result = await exportDocument(documentId);
    if (result) {
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ontology-${documentId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      adapter.getMessage().success('导出成功');
    }
  }, [documentId, exportDocument]);

  const graphNodes = useMemo(() => {
    return entityTypes.map((t, i) => ({
      id: t.type_id,
      label: t.display_name || t.name,
      x: 100 + (i % 4) * 200,
      y: 80 + Math.floor(i / 4) * 120,
    }));
  }, [entityTypes]);

  const graphEdges = useMemo(() => {
    const edges: Array<{ source: string; target: string; label: string }> = [];
    entityTypes.forEach((t) => {
      t.relations.forEach((r) => {
        const target = entityTypes.find((et) => et.name === r.target_type);
        if (target) {
          edges.push({
            source: t.type_id,
            target: target.type_id,
            label: r.name,
          });
        }
      });
    });
    return edges;
  }, [entityTypes]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <PageHeader
        title="本体设计器"
        actions={
          <>
            <Button icon={<HistoryOutlined />} onClick={() => setVersionDrawerVisible(true)}>
              版本管理
            </Button>
            <Button icon={<ExportOutlined />} onClick={handleExport}>
              导出
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
              新增实体类型
            </Button>
          </>
        }
      />

      {error && (
        <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>
      )}

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Row gutter={16} style={{ height: '100%' }}>
          <Col span={5} style={{ height: '100%', overflow: 'auto' }}>
            <Card
              title="实体类型"
              size="small"
              style={{ height: '100%' }}
              bodyStyle={{ padding: 0 }}
            >
              <div style={{ padding: '8px 12px' }}>
                <Input
                  prefix={<SearchOutlined />}
                  placeholder="搜索实体类型..."
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  allowClear
                  size="small"
                />
              </div>
              <List
                dataSource={filteredTypes}
                loading={loading}
                locale={{ emptyText: <Empty description="暂无实体类型" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                renderItem={(item) => (
                  <List.Item
                    onClick={() => setSelectedTypeId(item.type_id)}
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      background: selectedTypeId === item.type_id ? '#e6f7ff' : 'transparent',
                    }}
                    actions={[
                      <Popconfirm
                        key="delete"
                        title="确认删除此实体类型？"
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          handleDelete(item.type_id);
                        }}
                      >
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>,
                    ]}
                  >
                    <List.Item.Meta
                      title={
                        <span>
                          {item.display_name || item.name}{' '}
                          <Tag color={CLASSIFICATION_COLORS[item.classification_level] || 'default'} style={{ marginLeft: 4 }}>
                            {item.classification_level}
                          </Tag>
                        </span>
                      }
                      description={`${item.properties.length} 属性 · ${item.relations.length} 关系`}
                    />
                  </List.Item>
                )}
              />
            </Card>
          </Col>

          <Col span={12} style={{ height: '100%', overflow: 'auto' }}>
            <EntityTypeEditor
              entityType={selectedEntityType}
              allEntityTypes={entityTypes}
              onSave={handleSaveEntityType}
            />
          </Col>

          <Col span={7} style={{ height: '100%' }}>
            <Card title="关系图预览" size="small" style={{ height: '100%' }}>
              <div
                ref={graphCanvasRef}
                style={{
                  width: '100%',
                  height: 'calc(100vh - 220px)',
                  minHeight: 400,
                  background: '#fafafa',
                  border: '1px solid #f0f0f0',
                  borderRadius: 4,
                  position: 'relative',
                  overflow: 'auto',
                }}
              >
                {graphNodes.length === 0 ? (
                  <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 100 }} />
                ) : (
                  <svg width="100%" height={Math.max(400, graphNodes.length * 60)} style={{ display: 'block' }}>
                    {graphEdges.map((edge, i) => {
                      const sourceNode = graphNodes.find((n) => n.id === edge.source);
                      const targetNode = graphNodes.find((n) => n.id === edge.target);
                      if (!sourceNode || !targetNode) return null;
                      return (
                        <g key={`edge-${i}`}>
                          <line
                            x1={sourceNode.x + 60}
                            y1={sourceNode.y + 20}
                            x2={targetNode.x + 60}
                            y2={targetNode.y + 20}
                            stroke="#999"
                            strokeWidth={1.5}
                            markerEnd="url(#arrowhead)"
                          />
                          <text
                            x={(sourceNode.x + targetNode.x) / 2 + 60}
                            y={(sourceNode.y + targetNode.y) / 2 + 14}
                            textAnchor="middle"
                            fill="#666"
                            fontSize={10}
                          >
                            {edge.label}
                          </text>
                        </g>
                      );
                    })}
                    {graphNodes.map((node) => (
                      <g key={node.id}>
                        <rect
                          x={node.x}
                          y={node.y}
                          width={120}
                          height={40}
                          rx={6}
                          fill={selectedTypeId === node.id ? '#1890ff' : '#fff'}
                          stroke={selectedTypeId === node.id ? '#1890ff' : '#d9d9d9'}
                          strokeWidth={1.5}
                          style={{ cursor: 'pointer' }}
                          onClick={() => setSelectedTypeId(node.id)}
                        />
                        <text
                          x={node.x + 60}
                          y={node.y + 24}
                          textAnchor="middle"
                          fill={selectedTypeId === node.id ? '#fff' : '#333'}
                          fontSize={12}
                          fontWeight={500}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          onClick={() => setSelectedTypeId(node.id)}
                        >
                          {node.label}
                        </text>
                      </g>
                    ))}
                    <defs>
                      <marker
                        id="arrowhead"
                        markerWidth="10"
                        markerHeight="7"
                        refX="10"
                        refY="3.5"
                        orient="auto"
                      >
                        <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
                      </marker>
                    </defs>
                  </svg>
                )}
              </div>
            </Card>
          </Col>
        </Row>
      </div>

      <Modal
        title="新增实体类型"
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入实体类型名称' }]}
          >
            <Input placeholder="entity_type_name" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="显示名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="描述" />
          </Form.Item>
          <Form.Item name="classification_level" label="密级" initialValue="U">
            <AntSelect
              options={[
                { label: 'TS - 绝密', value: 'TS' },
                { label: 'S - 机密', value: 'S' },
                { label: 'C - 秘密', value: 'C' },
                { label: 'U - 公开', value: 'U' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="版本管理"
        placement="right"
        width={480}
        open={versionDrawerVisible}
        onClose={() => setVersionDrawerVisible(false)}
      >
        <VersionPanel documentId={documentId} />
      </Drawer>
    </div>
  );
}
