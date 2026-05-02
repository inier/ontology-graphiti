import { Card, Row, Col, Tag, Button, Table, Progress, Timeline, Collapse, List, Typography, Space, Divider, Tooltip } from 'antd';
import {
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  SearchOutlined,
  CheckCircleFilled,
  LoadingOutlined,
  WarningFilled,
  InfoCircleOutlined,
  RightOutlined,
  DownOutlined,
  EyeOutlined,
  LinkOutlined
} from '@ant-design/icons';
import { useState } from 'react';

const { Text, Paragraph } = Typography;

export interface Document {
  id: string;
  name: string;
  relevance: number;
  preview?: string;
  type?: string;
}

export interface SearchResult {
  id: string;
  title: string;
  source: string;
  relevance: number;
  url?: string;
  snippet?: string;
}

export interface LogMessage {
  id: string;
  timestamp: Date;
  level: 'info' | 'success' | 'warning' | 'error';
  content: string;
}

export interface Artifact {
  type: 'text' | 'table' | 'image' | 'json';
  name: string;
  data: any;
}

export interface StageDetail {
  stageId: string;
  stageName: string;
  messages: LogMessage[];
  progress: number;
  artifacts?: Artifact[];
}

export interface OntologyNode {
  id: string;
  name: string;
  type: 'concept' | 'domain' | 'instance' | 'event';
  properties: Record<string, any>;
  propertyCount: number;
  relationshipCount: number;
}

export interface Relationship {
  id: string;
  name: string;
  sourceId: string;
  targetId: string;
  type: string;
}

export interface Ontology {
  nodes: OntologyNode[];
  relationships: Relationship[];
}

export interface SourceDataPanelProps {
  question: string;
  documents: Document[];
  searchResults: SearchResult[];
  onDocumentPreview?: (doc: Document) => void;
  onSearchResultClick?: (result: SearchResult) => void;
}

export interface TransformPanelProps {
  currentStage: string;
  stageDetails: StageDetail[];
}

export interface OntologyPanelProps {
  ontology: Ontology;
  onNodeClick?: (node: OntologyNode) => void;
  onNodeEdit?: (node: OntologyNode) => void;
  onRelationshipClick?: (rel: Relationship) => void;
}

export interface DataFlowVisualizationProps {
  question: string;
  documents: Document[];
  searchResults: SearchResult[];
  currentStage: string;
  stageDetails: StageDetail[];
  ontology: Ontology;
  onDocumentPreview?: (doc: Document) => void;
  onSearchResultClick?: (result: SearchResult) => void;
  onNodeClick?: (node: OntologyNode) => void;
  onNodeEdit?: (node: OntologyNode) => void;
  onRelationshipClick?: (rel: Relationship) => void;
}

const LEVEL_COLORS = {
  info: '#1890ff',
  success: '#52c41a',
  warning: '#faad14',
  error: '#ff4d4f'
};

const LEVEL_ICONS = {
  info: <InfoCircleOutlined style={{ color: LEVEL_COLORS.info }} />,
  success: <CheckCircleFilled style={{ color: LEVEL_COLORS.success }} />,
  warning: <WarningFilled style={{ color: LEVEL_COLORS.warning }} />,
  error: <InfoCircleOutlined style={{ color: LEVEL_COLORS.error }} />
};

const NODE_TYPE_COLORS = {
  concept: '#1890ff',
  domain: '#52c41a',
  instance: '#722ed1',
  event: '#faad14'
};

const NODE_TYPE_TAGS = {
  concept: { color: 'blue', text: '概念' },
  domain: { color: 'green', text: '领域' },
  instance: { color: 'purple', text: '实例' },
  event: { color: 'orange', text: '事件' }
};

function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function SourceDataPanel({ question, documents, searchResults, onDocumentPreview, onSearchResultClick }: SourceDataPanelProps) {
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({
    documents: true,
    searchResults: true
  });

  const getFileIcon = (type?: string) => {
    if (type?.includes('pdf')) return <FilePdfOutlined style={{ color: '#ff4d4f' }} />;
    if (type?.includes('word') || type?.includes('doc')) return <FileWordOutlined style={{ color: '#1890ff' }} />;
    return <FileTextOutlined style={{ color: '#8c8c8c' }} />;
  };

  return (
    <Card
      title="原始数据"
      size="small"
      extra={
        <Button size="small" type="link">
          全部展开
        </Button>
      }
      style={{ height: '100%', borderRadius: 8 }}
      bodyStyle={{ padding: 0 }}
    >
      <div>
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            用户问题
          </Text>
          <Card size="small" style={{ background: '#fafafa', borderRadius: 6 }}>
            <Paragraph style={{ margin: 0, fontSize: 14, color: '#262626' }}>
              "{question}"
            </Paragraph>
          </Card>
        </div>

        <Collapse
          ghost
          activeKey={Object.entries(expandedKeys).filter(([_, v]) => v).map(([k]) => k)}
          onChange={(keys) => setExpandedKeys({ documents: keys.includes('documents'), searchResults: keys.includes('searchResults') })}
          style={{ background: 'transparent' }}
        >
          <Collapse.Panel
            key="documents"
            header={
              <Space>
                <FileTextOutlined />
                <span>相关文档 ({documents.length})</span>
              </Space>
            }
          >
            <List
              size="small"
              dataSource={documents}
              renderItem={(doc) => (
                <List.Item
                  style={{ padding: '8px 0', cursor: 'pointer' }}
                  onClick={() => onDocumentPreview?.(doc)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 8 }}>
                    {getFileIcon(doc.type)}
                    <Text ellipsis style={{ flex: 1, fontSize: 13 }}>{doc.name}</Text>
                    <Tag color={doc.relevance > 90 ? 'green' : doc.relevance > 80 ? 'blue' : 'default'}>
                      {doc.relevance}%
                    </Tag>
                    <Button size="small" type="text" icon={<EyeOutlined />}>
                      预览
                    </Button>
                  </div>
                </List.Item>
              )}
            />
          </Collapse.Panel>

          <Collapse.Panel
            key="searchResults"
            header={
              <Space>
                <SearchOutlined />
                <span>搜索结果 ({searchResults.length})</span>
              </Space>
            }
          >
            <List
              size="small"
              dataSource={searchResults}
              renderItem={(result) => (
                <List.Item
                  style={{ padding: '8px 0', cursor: 'pointer' }}
                  onClick={() => onSearchResultClick?.(result)}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <SearchOutlined style={{ color: '#1890ff', fontSize: 12 }} />
                      <Text ellipsis style={{ flex: 1, fontSize: 13 }}>{result.title}</Text>
                      <Tag color={result.relevance > 90 ? 'green' : result.relevance > 80 ? 'blue' : 'default'}>
                        {result.relevance}%
                      </Tag>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>来源: {result.source}</Text>
                      {result.url && (
                        <Button size="small" type="text" icon={<LinkOutlined />}>
                          查看
                        </Button>
                      )}
                    </div>
                    {result.snippet && (
                      <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                        {result.snippet}
                      </Text>
                    )}
                  </div>
                </List.Item>
              )}
            />
          </Collapse.Panel>
        </Collapse>
      </div>
    </Card>
  );
}

function TransformPanel({ currentStage, stageDetails }: TransformPanelProps) {
  const currentDetail = stageDetails.find(d => d.stageId === currentStage);

  return (
    <Card
      title="转化过程"
      size="small"
      style={{ height: '100%', borderRadius: 8 }}
      bodyStyle={{ padding: 16, overflow: 'auto', maxHeight: 'calc(100vh - 400px)', minHeight: 400 }}
    >
      {stageDetails.map((detail, index) => (
        <div key={detail.stageId} style={{ marginBottom: index < stageDetails.length - 1 ? 24 : 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Text strong style={{ fontSize: 14 }}>{detail.stageName}</Text>
            {detail.stageId === currentStage && (
              <LoadingOutlined style={{ color: '#1890ff', animation: 'spin 1s linear infinite' }} />
            )}
            {detail.stageId !== currentStage && detail.progress === 100 && (
              <CheckCircleFilled style={{ color: '#52c41a' }} />
            )}
          </div>

          <Card size="small" style={{ background: '#fafafa', borderRadius: 6, marginBottom: 8 }}>
            <Progress
              percent={detail.progress}
              size="small"
              strokeColor={detail.progress === 100 ? '#52c41a' : '#1890ff'}
              trailColor="#e8e8e8"
              format={(percent) => `${percent}%`}
            />
          </Card>

          <div
            style={{
              maxHeight: currentDetail?.stageId === detail.stageId ? 300 : 150,
              overflow: 'auto',
              background: '#fff',
              borderRadius: 6,
              border: '1px solid #f0f0f0'
            }}
          >
            {detail.messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  gap: 8,
                  padding: '6px 12px',
                  borderBottom: '1px solid #f5f5f5',
                  alignItems: 'flex-start'
                }}
              >
                <span style={{ fontSize: 11, color: '#8c8c8c', minWidth: 70 }}>
                  {formatTimestamp(msg.timestamp)}
                </span>
                {LEVEL_ICONS[msg.level]}
                <Text style={{ fontSize: 12, color: '#262626', flex: 1 }}>{msg.content}</Text>
              </div>
            ))}
          </div>

          {detail.artifacts && detail.artifacts.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>产出物:</Text>
              <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                {detail.artifacts.map((artifact, i) => (
                  <Tag key={i} color="blue" style={{ fontSize: 11 }}>{artifact.name}</Tag>
                ))}
              </div>
            </div>
          )}

          {index < stageDetails.length - 1 && (
            <div style={{ textAlign: 'center', marginTop: 16, marginBottom: 8 }}>
              <RightOutlined style={{ color: '#d9d9d9', fontSize: 12 }} />
            </div>
          )}
        </div>
      ))}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Card>
  );
}

function OntologyPanel({ ontology, onNodeClick, onNodeEdit, onRelationshipClick }: OntologyPanelProps) {
  const nodeColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (name: string, record: OntologyNode) => (
      <a onClick={() => onNodeClick?.(record)} style={{ color: '#1890ff' }}>{name}</a>
    )},
    { title: '类型', dataIndex: 'type', key: 'type', render: (type: string) => (
      <Tag color={NODE_TYPE_TAGS[type as keyof typeof NODE_TYPE_TAGS].color}>
        {NODE_TYPE_TAGS[type as keyof typeof NODE_TYPE_TAGS].text}
      </Tag>
    )},
    { title: '属性', dataIndex: 'propertyCount', key: 'propertyCount', width: 50 },
    { title: '关系', dataIndex: 'relationshipCount', key: 'relationshipCount', width: 50 },
    { title: '操作', key: 'action', width: 80, render: (_: any, record: OntologyNode) => (
      <Space size={4}>
        <Button size="small" type="text" onClick={() => onNodeClick?.(record)}>详情</Button>
        <Button size="small" type="text" onClick={() => onNodeEdit?.(record)}>编辑</Button>
      </Space>
    )}
  ];

  const relationshipColumns = [
    { title: '关系', dataIndex: 'name', key: 'name', render: (name: string) => <Tag>{name}</Tag> },
    { title: '类型', dataIndex: 'type', key: 'type', render: (type: string) => <Tag color="blue">{type}</Tag> },
    { title: '操作', key: 'action', width: 60, render: (_: any, record: Relationship) => (
      <Button size="small" type="text" onClick={() => onRelationshipClick?.(record)}>详情</Button>
    )}
  ];

  return (
    <Card
      title="本体定义"
      size="small"
      style={{ height: '100%', borderRadius: 8 }}
      bodyStyle={{ padding: 0, overflow: 'auto', maxHeight: 'calc(100vh - 400px)', minHeight: 400 }}
    >
      {ontology.nodes.length === 0 && ontology.relationships.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <Text type="secondary">暂无本体数据</Text>
        </div>
      ) : (
        <>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
            <Text strong style={{ fontSize: 13 }}>本体图谱预览</Text>
            <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
              <Space size={16}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  实体: <Text strong>{ontology.nodes.length}</Text>
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  关系: <Text strong>{ontology.relationships.length}</Text>
                </Text>
              </Space>
            </div>
          </div>

          <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong style={{ fontSize: 13 }}>实体列表 ({ontology.nodes.length})</Text>
            </div>
            <Table
              size="small"
              dataSource={ontology.nodes}
              columns={nodeColumns}
              rowKey="id"
              pagination={false}
              scroll={{ y: 200 }}
            />
          </div>

          <div style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong style={{ fontSize: 13 }}>关系列表 ({ontology.relationships.length})</Text>
            </div>
            <Table
              size="small"
              dataSource={ontology.relationships}
              columns={relationshipColumns}
              rowKey="id"
              pagination={false}
              scroll={{ y: 200 }}
            />
          </div>
        </>
      )}
    </Card>
  );
}

export function DataFlowVisualization({
  question,
  documents,
  searchResults,
  currentStage,
  stageDetails,
  ontology,
  onDocumentPreview,
  onSearchResultClick,
  onNodeClick,
  onNodeEdit,
  onRelationshipClick
}: DataFlowVisualizationProps) {
  return (
    <Row gutter={[16, 16]}>
      <Col span={7}>
        <SourceDataPanel
          question={question}
          documents={documents}
          searchResults={searchResults}
          onDocumentPreview={onDocumentPreview}
          onSearchResultClick={onSearchResultClick}
        />
      </Col>
      <Col span={9}>
        <TransformPanel
          currentStage={currentStage}
          stageDetails={stageDetails}
        />
      </Col>
      <Col span={8}>
        <OntologyPanel
          ontology={ontology}
          onNodeClick={onNodeClick}
          onNodeEdit={onNodeEdit}
          onRelationshipClick={onRelationshipClick}
        />
      </Col>
    </Row>
  );
}

export default DataFlowVisualization;