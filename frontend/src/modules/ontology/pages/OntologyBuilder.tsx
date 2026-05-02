import { useState, useEffect } from 'react';
import { Card, Row, Col, Tabs, Button, Space, Table, Tag, Select, Input, Steps, Divider } from 'antd';
import { DatabaseOutlined, FileTextOutlined, LayoutOutlined, PlayCircleOutlined, RollbackOutlined } from '@ant-design/icons';
import { useScenario } from '../../shared';

const { TextArea } = Input;

interface Step {
  title: string;
  description: string;
  icon: React.ReactNode;
}

interface ExtractionResult {
  entities: Array<{
    id: string;
    type: string;
    name: string;
    properties?: Record<string, any>;
  }>;
  relations: Array<{
    id: string;
    type: string;
    source: string;
    target: string;
    properties?: Record<string, any>;
  }>;
  events: Array<{
    id: string;
    type: string;
    name: string;
    timestamp?: string;
    properties?: Record<string, any>;
  }>;
}

interface OntologyVersion {
  version_id: string;
  created_at: string;
  entity_count: number;
  relation_count: number;
  event_count: number;
  commit_message: string;
}

export function OntologyBuilder() {
  const { currentScenario } = useScenario();
  const [currentStep, setCurrentStep] = useState(0);
  const [rawData, setRawData] = useState('');
  const [extractionResult, setExtractionResult] = useState<ExtractionResult>({
    entities: [],
    relations: [],
    events: []
  });
  const [ontologyVersions, setOntologyVersions] = useState<OntologyVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('entities');

  const steps: Step[] = [
    {
      title: '原始数据',
      description: '输入或粘贴原始文本数据',
      icon: <FileTextOutlined />
    },
    {
      title: '实体抽取',
      description: '从原始数据中抽取实体、关系和事件',
      icon: <LayoutOutlined />
    },
    {
      title: '本体定义',
      description: '查看和管理本体版本',
      icon: <DatabaseOutlined />
    }
  ];

  useEffect(() => {
    if (currentScenario) {
      loadOntologyVersions();
    }
  }, [currentScenario]);

  const loadOntologyVersions = async () => {
    try {
      setLoading(true);
      // Mock data for now
      const mockVersions: OntologyVersion[] = [
        {
          version_id: 'v1',
          created_at: new Date().toISOString(),
          entity_count: 15,
          relation_count: 10,
          event_count: 5,
          commit_message: 'Initial ontology'
        },
        {
          version_id: 'v2',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          entity_count: 20,
          relation_count: 15,
          event_count: 8,
          commit_message: 'Add new entities'
        }
      ];
      setOntologyVersions(mockVersions);
      if (mockVersions.length > 0) {
        setSelectedVersion(mockVersions[0].version_id);
      }
    } catch (error) {
      console.error('加载本体版本失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!rawData.trim()) return;

    try {
      setLoading(true);
      // Mock extraction result
      const mockResult: ExtractionResult = {
        entities: [
          { id: '1', type: 'Person', name: 'Alice', properties: { age: 30, role: 'Engineer' } },
          { id: '2', type: 'Person', name: 'Bob', properties: { age: 25, role: 'Designer' } },
          { id: '3', type: 'Organization', name: 'Acme Corp', properties: { industry: 'Technology' } }
        ],
        relations: [
          { id: '1', type: 'WORKS_FOR', source: '1', target: '3' },
          { id: '2', type: 'WORKS_FOR', source: '2', target: '3' },
          { id: '3', type: 'KNOWS', source: '1', target: '2' }
        ],
        events: [
          { id: '1', type: 'Meeting', name: 'Team Meeting', timestamp: new Date().toISOString() }
        ]
      };
      setExtractionResult(mockResult);
      setCurrentStep(1);
    } catch (error) {
      console.error('实体抽取失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildOntology = async () => {
    try {
      setLoading(true);
      // Mock build process
      await new Promise(resolve => setTimeout(resolve, 1000));
      const newVersion: OntologyVersion = {
        version_id: `v${ontologyVersions.length + 1}`,
        created_at: new Date().toISOString(),
        entity_count: extractionResult.entities.length,
        relation_count: extractionResult.relations.length,
        event_count: extractionResult.events.length,
        commit_message: 'New ontology version'
      };
      setOntologyVersions([newVersion, ...ontologyVersions]);
      setSelectedVersion(newVersion.version_id);
      setCurrentStep(2);
    } catch (error) {
      console.error('构建本体失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleNext = () => {
    if (currentStep === 0) {
      handleExtract();
    } else if (currentStep === 1) {
      handleBuildOntology();
    }
  };

  const renderRawDataStep = () => (
    <Card size="small">
      <TextArea
        rows={8}
        placeholder="请输入原始文本数据..."
        value={rawData}
        onChange={(e) => setRawData(e.target.value)}
        style={{ marginBottom: 12 }}
      />
      <div style={{ textAlign: 'center' }}>
        <Button 
          type="primary" 
          size="small"
          icon={<PlayCircleOutlined />}
          onClick={handleExtract}
          loading={loading}
          disabled={!rawData.trim()}
        >
          开始抽取
        </Button>
      </div>
    </Card>
  );

  const renderExtractionStep = () => (
    <Card size="small">
      <Tabs activeKey={activeTab} onChange={setActiveTab} size="small">
        <Tabs.TabPane tab="实体" key="entities">
          <Table
            dataSource={extractionResult.entities}
            columns={[
              { title: 'ID', dataIndex: 'id', key: 'id' },
              { title: '类型', dataIndex: 'type', key: 'type' },
              { title: '名称', dataIndex: 'name', key: 'name' },
              { 
                title: '属性', 
                dataIndex: 'properties', 
                key: 'properties',
                render: (properties: Record<string, any>) => (
                  <Tag color="blue">{JSON.stringify(properties || {})}</Tag>
                )
              }
            ]}
            rowKey="id"
            size="small"
          />
        </Tabs.TabPane>
        <Tabs.TabPane tab="关系" key="relations">
          <Table
            dataSource={extractionResult.relations}
            columns={[
              { title: 'ID', dataIndex: 'id', key: 'id' },
              { title: '类型', dataIndex: 'type', key: 'type' },
              { title: '来源', dataIndex: 'source', key: 'source' },
              { title: '目标', dataIndex: 'target', key: 'target' }
            ]}
            rowKey="id"
            size="small"
          />
        </Tabs.TabPane>
        <Tabs.TabPane tab="事件" key="events">
          <Table
            dataSource={extractionResult.events}
            columns={[
              { title: 'ID', dataIndex: 'id', key: 'id' },
              { title: '类型', dataIndex: 'type', key: 'type' },
              { title: '名称', dataIndex: 'name', key: 'name' },
              { title: '时间', dataIndex: 'timestamp', key: 'timestamp' }
            ]}
            rowKey="id"
            size="small"
          />
        </Tabs.TabPane>
      </Tabs>
      <Divider style={{ margin: '12px 0' }} />
      <div style={{ textAlign: 'center' }}>
        <Button 
          type="primary" 
          size="small"
          icon={<DatabaseOutlined />}
          onClick={handleBuildOntology}
          loading={loading}
        >
          构建本体
        </Button>
      </div>
    </Card>
  );

  const renderOntologyStep = () => (
    <Card size="small">
      <Row gutter={12}>
        <Col span={8}>
          <Card style={{ height: '100%' }} size="small">
            <Select
              style={{ width: '100%', marginBottom: 12 }}
              value={selectedVersion}
              onChange={setSelectedVersion}
              options={ontologyVersions.map(version => ({
                label: `${version.version_id} - ${version.commit_message}`,
                value: version.version_id
              }))}
              size="small"
            />
            <Table
              dataSource={ontologyVersions}
              columns={[
                { title: '版本', dataIndex: 'version_id', key: 'version_id' },
                { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
                { title: '实体数', dataIndex: 'entity_count', key: 'entity_count' },
                { title: '关系数', dataIndex: 'relation_count', key: 'relation_count' },
                { title: '事件数', dataIndex: 'event_count', key: 'event_count' },
                { 
                  title: '操作', 
                  key: 'action',
                  render: (_, record) => (
                    <Button 
                      size="small" 
                      icon={<RollbackOutlined />}
                      onClick={() => setSelectedVersion(record.version_id)}
                    >
                      切换
                    </Button>
                  )
                }
              ]}
              rowKey="version_id"
              size="small"
            />
          </Card>
        </Col>
        <Col span={16}>
          <Card style={{ height: '100%' }} size="small">
            <div style={{ padding: 12 }}>
              <div>当前版本: {selectedVersion}</div>
              <div>实体数量: {extractionResult.entities.length}</div>
              <div>关系数量: {extractionResult.relations.length}</div>
              <div>事件数量: {extractionResult.events.length}</div>
              <Divider style={{ margin: '12px 0' }} />
              <div>本体结构预览</div>
              <div style={{ border: '1px solid #f0f0f0', padding: 12, borderRadius: 4, backgroundColor: '#fafafa', marginTop: 8 }}>
                <pre style={{ margin: 0, fontSize: 11 }}>
                  {JSON.stringify({
                    entities: extractionResult.entities,
                    relations: extractionResult.relations,
                    events: extractionResult.events
                  }, null, 2)}
                </pre>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  );

  return (
    <div>
      <Card style={{ marginBottom: 12 }} size="small">
        <Steps
          current={currentStep}
          items={steps.map((step) => ({
            title: step.title,
            description: step.description,
            icon: step.icon
          }))}
          style={{ marginBottom: 12 }}
          size="small"
        />
        
        <div style={{ minHeight: 400 }}>
          {currentStep === 0 && renderRawDataStep()}
          {currentStep === 1 && renderExtractionStep()}
          {currentStep === 2 && renderOntologyStep()}
        </div>
        
        <Divider style={{ margin: '12px 0' }} />
        
        <div style={{ textAlign: 'center' }}>
          <Space>
            <Button 
              size="small"
              icon={<RollbackOutlined />}
              onClick={handlePrevious}
              disabled={currentStep === 0}
            >
              上一步
            </Button>
            {currentStep < 2 && (
              <Button 
                type="primary" 
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={handleNext}
                loading={loading}
              >
                下一步
              </Button>
            )}
          </Space>
        </div>
      </Card>
    </div>
  );
}
