import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Card,
  Steps,
  Button,
  Typography,
  Space,
  Tag,
  Collapse,
  Divider,
  Alert,
  Progress,
  Badge,
  Flex,
  message,
  Tour,
} from 'antd';
import {
  BookOutlined,
  RocketOutlined,
  ProjectOutlined,
  ApiOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  RightCircleOutlined,
  ApiFilled,
  CodeOutlined,
  DatabaseOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTourStore } from '../store/tourStore';
import { guideTourSteps, PAGE_IDS } from '../config/tourSteps';

const { Content } = Layout;
const { Title, Paragraph, Text } = Typography;

interface StepData {
  title: string;
  description: string;
  path?: string;
  icon: React.ReactNode;
  status: 'wait' | 'process' | 'finish' | 'error';
}

const GuidePage: React.FC = () => {
  const navigate = useNavigate();
  const [tourOpen, setTourOpen] = useState(false);
  const {
    guideCompletedSteps: completedSteps,
    guideCurrentStep: currentStep,
    guideTourFinished,
    markGuideStepComplete,
    setGuideCurrentStep,
    finishGuideTour,
    resetGuideTour,
    setActiveTour,
    activeTourId,
  } = useTourStore();

  // Auto-start tour on first visit
  useEffect(() => {
    if (!guideTourFinished && !activeTourId) {
      const timer = setTimeout(() => {
        setActiveTour(PAGE_IDS.GUIDE);
        setTourOpen(true);
      }, 600);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTourClose = useCallback(() => {
    setTourOpen(false);
    setActiveTour(null);
  }, [setActiveTour]);

  const handleTourFinish = useCallback(() => {
    setTourOpen(false);
    finishGuideTour();
    setActiveTour(null);
  }, [finishGuideTour, setActiveTour]);

  const handleRestartTour = useCallback(() => {
    resetGuideTour();
    // Small delay so the DOM updates before tour tries to find targets
    setTimeout(() => {
      setActiveTour(PAGE_IDS.GUIDE);
      setTourOpen(true);
    }, 100);
  }, [resetGuideTour, setActiveTour]);

  const steps: StepData[] = [
    {
      title: '1. 工作空间设置',
      description: '创建或选择工作空间和场景',
      path: '/workspace',
      icon: <ProjectOutlined />,
      status: completedSteps.includes(0) ? 'finish' : currentStep === 0 ? 'process' : 'wait',
    },
    {
      title: '2. 本体设计器',
      description: '创建实体类型、属性和关系',
      path: '/ontology/designer',
      icon: <DatabaseOutlined />,
      status: completedSteps.includes(1) ? 'finish' : currentStep === 1 ? 'process' : 'wait',
    },
    {
      title: '3. 蓝图设计',
      description: '设计业务流程',
      path: '/blueprint',
      icon: <ApiOutlined />,
      status: completedSteps.includes(2) ? 'finish' : currentStep === 2 ? 'process' : 'wait',
    },
    {
      title: '4. 对象管理',
      description: '管理实体实例',
      path: '/business/entities',
      icon: <BookOutlined />,
      status: completedSteps.includes(3) ? 'finish' : currentStep === 3 ? 'process' : 'wait',
    },
    {
      title: '5. 数据摄入',
      description: '导入数据并应用',
      path: '/ingest',
      icon: <ExperimentOutlined />,
      status: completedSteps.includes(4) ? 'finish' : currentStep === 4 ? 'process' : 'wait',
    },
  ];

  const quickStartItems = [
    {
      title: '快速开始',
      description: '完整的操作流程指南',
      icon: <RocketOutlined />,
      onClick: () => setGuideCurrentStep(0),
    },
    {
      title: '查看 API 文档',
      description: '后端 API 接口文档',
      icon: <ApiFilled />,
      onClick: () => window.open('http://localhost:8000/docs', '_blank'),
    },
    {
      title: '运行测试',
      description: '运行项目单元测试',
      icon: <CheckCircleOutlined />,
      onClick: () => message.info('请在命令行运行: pytest tests/unit/ -v'),
    },
    {
      title: '查看代码示例',
      description: '查看示例代码',
      icon: <CodeOutlined />,
      onClick: () => message.info('示例代码见项目根目录'),
    },
  ];

  const stepDetails = [
    {
      key: '0',
      label: '步骤 1: 工作空间设置',
      children: (
        <div>
          <Paragraph>
            工作空间是所有操作的基础容器。您需要先创建或选择一个工作空间，然后在其中创建场景。
          </Paragraph>
          <Flex vertical gap={8}>
            {[
              '登录系统（默认账号：admin/admin123）',
              '在顶部导航栏选择或创建工作空间',
              '然后选择或创建场景',
              '这是后续所有操作的基础容器',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>{item}</div>
            ))}
          </Flex>
          <Divider />
          <Button
            type="primary"
            onClick={() => navigate('/workspace')}
            icon={<RightCircleOutlined />}
          >
            前往工作空间
          </Button>
        </div>
      ),
    },
    {
      key: '1',
      label: '步骤 2: 本体设计器',
      children: (
        <div>
          <Paragraph>
            在本体设计器中，您可以创建实体类型、定义属性和建立关系。
          </Paragraph>
          <Title level={4}>创建实体类型</Title>
          <Flex vertical gap={8}>
            {[
              '点击右上角新增实体类型按钮',
              '填写实体类型信息：名称、显示名称、描述、密级',
              '添加属性：基础属性、统计属性、能力属性',
              '建立关系：与其他实体类型关联',
              '保存并查看关系图预览',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>{item}</div>
            ))}
          </Flex>
          <Title level={4}>实体类型层次</Title>
          <Flex vertical gap={8}>
            {[
              'Person (人员) → OperationalPersonnel (业务人员)',
              'Organization (组织) → OrganizationUnit (组织单元)',
              'Location (地点) → OperationalBase (业务基地)',
              'ToolSystem (工具系统) → Aircraft (飞行器)',
              'Event (事件) → OperationalAction (业务行动)',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}><Tag color="blue">{item}</Tag></div>
            ))}
          </Flex>
          <Divider />
          <Button
            type="primary"
            onClick={() => navigate('/ontology/designer')}
            icon={<RightCircleOutlined />}
          >
            前往本体设计器
          </Button>
        </div>
      ),
    },
    {
      key: '2',
      label: '步骤 3: 蓝图设计',
      children: (
        <div>
          <Paragraph>
            在蓝图设计器中，您可以设计业务流程，使用各种节点类型来构建数据流。
          </Paragraph>
          <Title level={4}>节点类型</Title>
          <Flex gap={16} wrap="wrap">
            {[
              { title: '数据源节点', desc: '文件、API、数据库' },
              { title: '转换节点', desc: '清洗、转换、聚合' },
              { title: '本体节点', desc: '与实体类型映射' },
              { title: '动作节点', desc: '创建、更新、删除' },
              { title: 'Agent节点', desc: 'LLM 推理、分析' },
              { title: '决策节点', desc: '条件判断' },
              { title: '验证节点', desc: '规则验证' },
              { title: '输出节点', desc: '存储、展示' },
            ].map((item, i) => (
              <Card key={i} size="small" style={{ flex: '1 1 calc(50% - 16px)', minWidth: 200 }}>
                <div><Text strong>{item.title}</Text></div>
                <div><Text type="secondary">{item.desc}</Text></div>
              </Card>
            ))}
          </Flex>
          <Divider />
          <Button
            type="primary"
            onClick={() => navigate('/blueprint')}
            icon={<RightCircleOutlined />}
          >
            前往蓝图设计器
          </Button>
        </div>
      ),
    },
    {
      key: '3',
      label: '步骤 4: 对象管理',
      children: (
        <div>
          <Paragraph>
            在对象管理页面，您可以查看和管理实体实例。
          </Paragraph>
          <Flex vertical gap={8}>
            {[
              '查看实体列表：表格展示所有实体',
              '按类型、来源、状态过滤',
              '查看属性分布：统计图表展示',
              '查看实体详情：按语义类别分组显示',
              '编辑属性和关联关系',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>{item}</div>
            ))}
          </Flex>
          <Divider />
          <Button
            type="primary"
            onClick={() => navigate('/business/entities')}
            icon={<RightCircleOutlined />}
          >
            前往对象管理
          </Button>
        </div>
      ),
    },
    {
      key: '4',
      label: '步骤 5: 数据摄入与应用',
      children: (
        <div>
          <Paragraph>
            最后，您可以导入数据并开始应用知识图谱。
          </Paragraph>
          <Title level={4}>数据摄入</Title>
          <Flex vertical gap={8}>
            {[
              '上传文档（PDF、Word、文本等）',
              '选择摄入配置',
              '启动摄入任务',
              '自动提取实体并添加到知识图谱',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>{item}</div>
            ))}
          </Flex>
          <Title level={4}>知识问答</Title>
          <Flex vertical gap={8}>
            {[
              '输入问题',
              '选择智能体',
              '查看回答',
              '查看引用来源',
            ].map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>{item}</div>
            ))}
          </Flex>
          <Divider />
          <Space>
            <Button
              type="primary"
              onClick={() => navigate('/ingest')}
              icon={<RightCircleOutlined />}
            >
              前往数据摄入
            </Button>
            <Button
              onClick={() => navigate('/qa')}
              icon={<RobotOutlined />}
            >
              前往问答系统
            </Button>
          </Space>
        </div>
      ),
    },
  ];

  const handleMarkStepComplete = (stepIndex: number) => {
    markGuideStepComplete(stepIndex);
    if (stepIndex < steps.length - 1) {
      setGuideCurrentStep(stepIndex + 1);
    }
    message.success('步骤 ' + (stepIndex + 1) + ' 已完成！');
  };

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <Title level={2}>
                <BookOutlined /> ODAP 本体设计系统指南
              </Title>
              <Text type="secondary">
                按照以下步骤，您将快速上手使用系统完整操作整个流程
              </Text>
            </div>
            <Button
              icon={<RocketOutlined />}
              onClick={handleRestartTour}
            >
              {guideTourFinished ? '重新引导' : '开始引导'}
            </Button>
          </div>

          <Alert
            title="欢迎使用 ODAP 本体设计系统！"
            description="本指南将带您完成从工作空间设置到数据应用的完整流程。点击下方步骤，让您开始使用。"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Card title="快速入门" style={{ marginBottom: 24 }} data-tour="quick-start">
            <Flex gap={16} wrap="wrap">
              {quickStartItems.map((item, i) => (
                <Card
                  key={i}
                  hoverable
                  style={{ flex: '1 1 calc(25% - 16px)', minWidth: 150, textAlign: 'center', cursor: 'pointer' }}
                  onClick={item.onClick}
                >
                  <div style={{ fontSize: 32, marginBottom: 8 }}>
                    {item.icon}
                  </div>
                  <div style={{ fontWeight: 'bold' }}>{item.title}</div>
                  <div style={{ fontSize: 12, color: '#666' }}>
                    {item.description}
                  </div>
                </Card>
              ))}
            </Flex>
          </Card>

          <Card title="操作步骤" style={{ marginBottom: 24 }}>
            <Steps
              current={currentStep}
              items={steps.map((step) => ({
                title: step.title,
                content: step.description,
                icon: step.icon,
                status: step.status,
              }))}
              onChange={(index) => setGuideCurrentStep(index)}
              style={{ marginBottom: 24 }}
            />
            <Progress
              percent={(completedSteps.length / steps.length) * 100}
              status="active"
              style={{ marginBottom: 24 }}
            />
            <Collapse
              activeKey={[currentStep.toString()]}
              defaultActiveKey={['0']}
              items={stepDetails}
            />
            <div style={{ marginTop: 24, textAlign: 'center' }}>
              <Space>
                <Button
                  disabled={currentStep === 0}
                  onClick={() => setGuideCurrentStep(Math.max(0, currentStep - 1))}
                >
                  上一步
                </Button>
                <Button
                  type="primary"
                  onClick={() => handleMarkStepComplete(currentStep)}
                  disabled={completedSteps.includes(currentStep)}
                >
                  标记为已完成
                </Button>
                <Button
                  disabled={currentStep === steps.length - 1}
                  onClick={() => setGuideCurrentStep(Math.min(steps.length - 1, currentStep + 1))}
                >
                  下一步
                </Button>
              </Space>
            </div>
          </Card>

          {/* Step cards with data-tour attributes */}
          <div style={{ marginBottom: 24 }}>
            <Flex gap={16} wrap="wrap">
              {steps.map((step, index) => (
                <Card
                  key={index}
                  hoverable
                  data-tour={`step-${['workspace', 'ontology', 'blueprint', 'entities', 'ingest'][index]}`}
                  style={{
                    flex: '1 1 calc(20% - 16px)',
                    minWidth: 180,
                    textAlign: 'center',
                    cursor: 'pointer',
                    borderLeft: completedSteps.includes(index) ? '3px solid #52c41a' : '3px solid #d9d9d9',
                  }}
                  onClick={() => {
                    if (step.path) navigate(step.path);
                  }}
                >
                  <div style={{ fontSize: 28, marginBottom: 8, color: completedSteps.includes(index) ? '#52c41a' : '#1890ff' }}>
                    {completedSteps.includes(index) ? <CheckCircleOutlined /> : step.icon}
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{step.title}</div>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{step.description}</div>
                </Card>
              ))}
            </Flex>
          </div>

          <Card title="技术支持">
            <Flex vertical gap={8}>
              {[
                '项目文档: docs/',
                '设计文档: docs/03-modules/',
                'API 文档: http://localhost:8000/docs',
              ].map((item, i) => (
                <div key={i}><Badge status="success" text={item} /></div>
              ))}
            </Flex>
          </Card>
        </div>
      </Content>

      {/* Guide Page Tour */}
      <Tour
        open={tourOpen}
        onClose={handleTourClose}
        onFinish={handleTourFinish}
        steps={guideTourSteps}
      />
    </Layout>
  );
};

export default GuidePage;
