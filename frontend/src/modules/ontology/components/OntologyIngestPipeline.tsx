import { useState, useEffect } from 'react';
import {
  Card,
  Steps,
  Typography,
  Space,
  Descriptions,
  Tag,
  Button,
  Divider,
  Table,
  Alert,
  Progress,
  Timeline,
  Collapse,
  Badge,
  Row,
  Col
} from 'antd';
import {
  DatabaseOutlined,
  ApiOutlined,
  CloudServerOutlined,
  RobotOutlined,
  GitlabOutlined,
  LoadingOutlined,
  InfoCircleOutlined,
  FolderOutlined,
  BarChartOutlined
} from '@ant-design/icons';

const { Text, Paragraph } = Typography;

interface PipelineStep {
  title: string;
  description: string;
  status: 'waiting' | 'processing' | 'completed' | 'error';
  icon: React.ReactNode;
  details: Record<string, any>;
}

interface EntityDefinition {
  id: string;
  name: string;
  type: string;
  side: string;
  confidence: number;
  properties: Record<string, any>;
}

interface RelationDefinition {
  id: string;
  source: string;
  target: string;
  type: string;
  description: string;
}

interface EventDefinition {
  id: string;
  type: string;
  location: string;
  timestamp: string;
  participants: string[];
  description: string;
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    title: '数据采集',
    description: '从多个数据源收集原始数据',
    status: 'waiting',
    icon: <DatabaseOutlined />,
    details: {
      sources: ['新闻API', '网页爬取', '手动输入', 'JSON导入'],
      formats: ['文本', '结构化数据', '网页内容']
    }
  },
  {
    title: '数据清洗',
    description: '清洗和标准化原始数据',
    status: 'waiting',
    icon: <ApiOutlined />,
    details: {
      operations: ['去重', '格式转换', '缺失值处理', '文本预处理']
    }
  },
  {
    title: 'LLM归纳',
    description: '使用大语言模型提取结构化信息',
    status: 'waiting',
    icon: <RobotOutlined />,
    details: {
      operations: ['实体识别', '关系提取', '事件建模', '属性推断']
    }
  },
  {
    title: '本体构建',
    description: '生成OntologyDocument并验证',
    status: 'waiting',
    icon: <CloudServerOutlined />,
    details: {
      output: ['实体', '关系', '事件', '行动', '规则', '约束']
    }
  },
  {
    title: '版本管理',
    description: '创建版本记录并存储',
    status: 'waiting',
    icon: <GitlabOutlined />,
    details: {
      features: ['版本历史', '回滚', '差异比较']
    }
  },
  {
    title: '图谱生成',
    description: '构建Neo4j图谱',
    status: 'waiting',
    icon: <FolderOutlined />,
    details: {
      output: ['实体节点', '关系边', '索引', '查询优化']
    }
  }
];

const MOCK_ENTITIES: EntityDefinition[] = [
  {
    id: 'unit-red-001',
    name: '甲方第1机动组',
    type: 'Unit',
    side: 'party_a',
    confidence: 0.95,
    properties: {
      规模: '3000人',
      装备: '重型载具',
      位置: 'B区高地',
      状态: '待命'
    }
  },
  {
    id: 'unit-blue-002',
    name: '乙方第2行动组',
    type: 'Unit',
    side: 'party_b',
    confidence: 0.92,
    properties: {
      规模: '1500人',
      装备: '突击步枪',
      位置: 'C区城镇',
      状态: '巡查'
    }
  },
  {
    id: 'location-b-zone',
    name: 'B区高地',
    type: 'Location',
    side: 'neutral',
    confidence: 1.0,
    properties: {
      地形: '高地',
      战略重要性: '高',
      植被覆盖: '低'
    }
  },
  {
    id: 'event-contact-001',
    name: '交锋事件',
    type: 'Event',
    side: 'neutral',
    confidence: 0.88,
    properties: {
      持续时间: '30分钟',
      烈度: '中等',
      结果: '未分胜负'
    }
  }
];

const MOCK_RELATIONS: RelationDefinition[] = [
  {
    id: 'rel-001',
    source: 'unit-red-001',
    target: 'unit-blue-002',
    type: 'engaged_with',
    description: '甲方第1机动组与乙方第2行动组交锋'
  },
  {
    id: 'rel-002',
    source: 'unit-red-001',
    target: 'location-b-zone',
    type: 'deployed_at',
    description: '甲方第1机动组部署在B区高地'
  },
  {
    id: 'rel-003',
    source: 'event-contact-001',
    target: 'location-b-zone',
    type: 'occurred_at',
    description: '交锋事件发生在B区高地'
  },
  {
    id: 'rel-004',
    source: 'event-contact-001',
    target: 'unit-red-001',
    type: 'participated_in',
    description: '甲方第1机动组参与交锋事件'
  }
];

const MOCK_EVENTS: EventDefinition[] = [
  {
    id: 'evt-001',
    type: 'contact',
    location: 'B区高地',
    timestamp: '2026-04-30T15:00:00Z',
    participants: ['unit-red-001', 'unit-blue-002'],
    description: '甲方第1机动组与乙方第2行动组发生交锋'
  }
];

export function OntologyIngestPipeline() {
  const [steps, setSteps] = useState<PipelineStep[]>(PIPELINE_STEPS);
  const [currentStep, setCurrentStep] = useState(-1);
  const [isRunning, setIsRunning] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const entityColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => <Tag color="blue">{type}</Tag>
    },
    {
      title: '阵营',
      dataIndex: 'side',
      key: 'side',
      width: 100,
      render: (side: string) => {
        const colors: Record<string, string> = {
          party_a: 'red',
          party_b: 'blue',
          neutral: 'default'
        };
        return <Tag color={colors[side] || 'default'}>{side}</Tag>;
      }
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (conf: number) => (
        <Progress
          percent={conf * 100}
          size="small"
          status={conf >= 0.9 ? 'success' : conf >= 0.7 ? 'normal' : 'exception'}
        />
      )
    },
    { title: '属性', dataIndex: 'properties', key: 'properties' }
  ];

  const relationColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
    { title: '源实体', dataIndex: 'source', key: 'source', width: 150 },
    {
      title: '关系类型',
      dataIndex: 'type',
      key: 'type',
      width: 140,
      render: (type: string) => <Tag color="green">{type}</Tag>
    },
    { title: '目标实体', dataIndex: 'target', key: 'target', width: 150 },
    { title: '描述', dataIndex: 'description', key: 'description' }
  ];

  const eventColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
    {
      title: '事件类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => <Tag color="orange">{type}</Tag>
    },
    { title: '位置', dataIndex: 'location', key: 'location', width: 120 },
    { title: '时间戳', dataIndex: 'timestamp', key: 'timestamp', width: 200 },
    { title: '参与者', dataIndex: 'participants', key: 'participants', width: 250 },
    { title: '描述', dataIndex: 'description', key: 'description' }
  ];

  const startPipeline = async () => {
    setIsRunning(true);
    setCurrentStep(0);
    setShowDetails(false);

    for (let i = 0; i < steps.length; i++) {
      setSteps(prev => {
        const updated = [...prev];
        updated[i] = { ...updated[i], status: 'processing' };
        return updated;
      });

      await new Promise(resolve => setTimeout(resolve, 1500));

      setSteps(prev => {
        const updated = [...prev];
        updated[i] = { ...updated[i], status: 'completed' };
        return updated;
      });

      setCurrentStep(i + 1);
    }

    setShowDetails(true);
    setIsRunning(false);
  };

  const resetPipeline = () => {
    setSteps(PIPELINE_STEPS);
    setCurrentStep(-1);
    setShowDetails(false);
  };

  const collapseItems = [
    {
      key: '1',
      label: (
        <Space>
          <Badge count={MOCK_ENTITIES.length} color="blue" />
          <Text strong>实体定义</Text>
        </Space>
      ),
      children: (
        <Table
          dataSource={MOCK_ENTITIES}
          columns={entityColumns}
          rowKey="id"
          pagination={{ pageSize: 5 }}
          size="small"
        />
      )
    },
    {
      key: '2',
      label: (
        <Space>
          <Badge count={MOCK_RELATIONS.length} color="green" />
          <Text strong>关系定义</Text>
        </Space>
      ),
      children: (
        <Table
          dataSource={MOCK_RELATIONS}
          columns={relationColumns}
          rowKey="id"
          pagination={{ pageSize: 5 }}
          size="small"
        />
      )
    },
    {
      key: '3',
      label: (
        <Space>
          <Badge count={MOCK_EVENTS.length} color="orange" />
          <Text strong>事件定义</Text>
        </Space>
      ),
      children: (
        <Table
          dataSource={MOCK_EVENTS}
          columns={eventColumns}
          rowKey="id"
          pagination={{ pageSize: 5 }}
          size="small"
        />
      )
    },
    {
      key: '4',
      label: (
        <Space>
          <InfoCircleOutlined />
          <Text strong>本体架构说明</Text>
        </Space>
      ),
      children: (
        <Descriptions variant="bordered" column={1} size="small">
          <Descriptions.Item label="文档格式">OntologyDocument (JSON)</Descriptions.Item>
          <Descriptions.Item label="实体类型">Unit, Equipment, Location, Person, Organization, EventNode</Descriptions.Item>
          <Descriptions.Item label="关系类型">engaged_with, commands, supported_by, deployed_at, supports</Descriptions.Item>
          <Descriptions.Item label="事件类型">contact, engage, withdraw, support, patrol, cease_operation</Descriptions.Item>
          <Descriptions.Item label="四层属性">basic_properties, statistical_properties, capabilities, constraints</Descriptions.Item>
          <Descriptions.Item label="版本控制">语义化版本 + 父版本指针</Descriptions.Item>
        </Descriptions>
      )
    }
  ];

  return (
    <div>
      <Card style={{ marginBottom: 12, borderRadius: 8 }}>
        <Space orientation="vertical" style={{ width: '100%' }} size="small">
          <Row align="middle" justify="end">
            <Space size="small">
              {!isRunning && currentStep === -1 && (
                <Button type="primary" size="small" icon={<BarChartOutlined />} onClick={startPipeline}>
                  开始演示
                </Button>
              )}
              {!isRunning && currentStep > -1 && (
                <Button size="small" onClick={resetPipeline}>
                  重置演示
                </Button>
              )}
              {isRunning && (
                <Button size="small" disabled icon={<LoadingOutlined spin />}>
                  处理中...
                </Button>
              )}
            </Space>
          </Row>

          <Divider style={{ margin: '8px 0' }} />

          <Steps
            size="small"
            current={currentStep}
            items={steps.map((step) => ({
              title: step.title,
              description: step.description,
              icon: step.icon,
              status: (step.status === 'completed' ? 'finish' : step.status === 'processing' ? 'process' : step.status) as 'wait' | 'process' | 'finish' | 'error'
            }))}
          />
        </Space>
      </Card>

      {currentStep >= 0 && (
        <>
          {currentStep < steps.length && (
            <Card
              style={{ marginBottom: 12, borderRadius: 8 }}
              size="small"
            >
              {currentStep < steps.length && steps[currentStep] && (
                <Descriptions variant="bordered" column={1} size="small">
                  <Descriptions.Item label="步骤">
                    {steps[currentStep].title}
                  </Descriptions.Item>
                  <Descriptions.Item label="描述">
                    {steps[currentStep].description}
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={
                      steps[currentStep].status === 'completed' ? 'success' :
                      steps[currentStep].status === 'processing' ? 'blue' : 'default'
                    }>
                      {steps[currentStep].status === 'waiting' && '等待中'}
                      {steps[currentStep].status === 'processing' && '处理中'}
                      {steps[currentStep].status === 'completed' && '已完成'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="详情">
                    <pre style={{ maxHeight: 150, overflow: 'auto', fontSize: '11px', margin: 0 }}>
                      {JSON.stringify(steps[currentStep].details, null, 2)}
                    </pre>
                  </Descriptions.Item>
                </Descriptions>
              )}
            </Card>
          )}

          {showDetails && (
            <Card
              style={{ borderRadius: 8 }}
              size="small"
              extra={<Alert type="success" message="构建完成！本体已成功生成" banner />}
            >
              <Collapse items={collapseItems} defaultActiveKey={['1']} size="small" />
            </Card>
          )}
        </>
      )}

      {currentStep === -1 && (
        <Card style={{ borderRadius: 8 }} size="small">
          <Timeline
            items={[
              {
                color: 'blue',
                children: (
                  <div>
                    <Text strong>数据采集</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      从新闻API、网页爬取、手动输入或JSON文件中获取原始数据。
                    </Paragraph>
                  </div>
                )
              },
              {
                color: 'cyan',
                children: (
                  <div>
                    <Text strong>数据清洗</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      对原始数据进行清洗和标准化。
                    </Paragraph>
                  </div>
                )
              },
              {
                color: 'green',
                children: (
                  <div>
                    <Text strong>LLM归纳</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      使用大语言模型从清洗后的数据中提取结构化信息。
                    </Paragraph>
                  </div>
                )
              },
              {
                color: 'orange',
                children: (
                  <div>
                    <Text strong>本体构建</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      生成符合OntologyDocument规范的结构化文档。
                    </Paragraph>
                  </div>
                )
              },
              {
                color: 'purple',
                children: (
                  <div>
                    <Text strong>版本管理</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      创建版本记录，支持历史查看、回滚和差异比较。
                    </Paragraph>
                  </div>
                )
              },
              {
                color: 'red',
                children: (
                  <div>
                    <Text strong>图谱生成</Text>
                    <Paragraph style={{ marginBottom: 8 }}>
                      将本体导入Neo4j图数据库，构建实体节点和关系边。
                    </Paragraph>
                  </div>
                )
              }
            ]}
          />
        </Card>
      )}
    </div>
  );
}

export default OntologyIngestPipeline;
