import { useState, useRef, useEffect } from 'react';
import { Card, Button, Space, Tag, Switch, Upload, Modal, Form, Input, Select, Tabs, Row, Col, Statistic, message, Popconfirm, Empty, Descriptions, Badge, Divider, Typography } from 'antd';
import { UploadOutlined, PlusOutlined, DeleteOutlined, CheckCircleOutlined, StopOutlined, AppstoreOutlined, FolderOutlined, FileTextOutlined, EyeOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';
import { PageHeader } from '@/modules/shared';
import { SkillEditor } from '../components/SkillEditor';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import type { ActionType } from '@ant-design/pro-components';

const { Text } = Typography;
const { TextArea } = Input;

interface Skill {
  name: string;
  category: string;
  path: string;
  files: string[];
  description?: string;
  parsed?: {
    name?: string;
    description?: string;
    input_schema?: Record<string, unknown>;
    output_schema?: Record<string, unknown>;
    sections?: Record<string, string>;
  };
  enabled?: boolean;
  skill_id?: string;
  type?: string;
  status?: string;
}

export function SkillManagement() {
  const [activeTab, setActiveTab] = useState('directory');
  const [scannedCount, setScannedCount] = useState(0);
  const [registeredCount, setRegisteredCount] = useState(0);
  const [categories, setCategories] = useState<Array<{ name: string; skill_count: number; path: string }>>([]);
  const [loadedSkills, setLoadedSkills] = useState<string[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [registerModalVisible, setRegisterModalVisible] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('custom');
  const [registerForm] = Form.useForm();
  const [skillEditorVisible, setSkillEditorVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);

  const scannedActionRef = useRef<ActionType>(null);
  const registeredActionRef = useRef<ActionType>(null);

  // 统计数据加载（分类 + 已加载Skill）
  const loadStats = async () => {
    try {
      const [categoriesResult, loadedResult] = await Promise.all([
        api.getSkillCategories().catch(() => ({ categories: [] as { name: string; skill_count: number; path: string }[] })),
        api.getLoadedSkills().catch(() => ({ skills: [] as string[] })),
      ]);
      setCategories(categoriesResult.categories || []);
      setLoadedSkills(loadedResult.skills || []);
    } catch (error) {
      console.error('加载统计数据失败:', error);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  // 目录Skills请求
  const fetchScannedSkills = async (): Promise<Skill[]> => {
    const [scanResult, allResult] = await Promise.all([
      api.scanSkillsDirectory().catch(() => ({ skills: [] as Skill[], total: 0 })),
      api.getAllSkills().catch(() => ({ registered: [] as Skill[], scanned: [] as Skill[], total_registered: 0, total_scanned: 0 })),
    ]);
    const enabledNames = new Set((allResult.registered as Skill[] | undefined)?.map((s) => s.name) || []);
    return ((scanResult.skills || []) as Skill[]).map(s => ({ ...s, enabled: enabledNames.has(s.name) }));
  };

  const scannedRequest = async (params: { current?: number; pageSize?: number }, sort: unknown, filter: unknown) => {
    const result = await wrapRequest(fetchScannedSkills)(params, sort, filter);
    setScannedCount(result.total);
    return result;
  };

  // 已注册Skills请求
  const fetchRegisteredSkills = async (): Promise<Skill[]> => {
    const allResult = await api.getAllSkills().catch(() => ({ registered: [] as Skill[], scanned: [] as Skill[], total_registered: 0, total_scanned: 0 }));
    return (allResult.registered || []) as Skill[];
  };

  const registeredRequest = async (params: { current?: number; pageSize?: number }, sort: unknown, filter: unknown) => {
    const result = await wrapRequest(fetchRegisteredSkills)(params, sort, filter);
    setRegisteredCount(result.total);
    return result;
  };

  const refreshAll = () => {
    scannedActionRef.current?.reload();
    registeredActionRef.current?.reload();
    loadStats();
  };

  const handleToggleSkill = async (skill: Skill, enabled: boolean) => {
    try {
      await api.toggleSkill(skill.name, enabled);
      message.success(`Skill "${skill.name}" 已${enabled ? '启用' : '禁用'}`);
      refreshAll();
    } catch (error) {
      message.error(`操作失败: ${error}`);
    }
  };

  const handleRegisterSkill = async (values: { name: string; skill_type: string; description: string; category: string }) => {
    try {
      await api.registerSkill(values);
      message.success('Skill 注册成功');
      setRegisterModalVisible(false);
      registerForm.resetFields();
      refreshAll();
    } catch (error) {
      message.error(`注册失败: ${error}`);
    }
  };

  const handleUploadFile = async (file: File) => {
    try {
      const result = await api.uploadSkillFile(file, uploadCategory);
      if (result.status === 'success') {
        message.success(`文件 ${file.name} 上传成功`);
        setUploadModalVisible(false);
        refreshAll();
      }
    } catch (error) {
      message.error(`上传失败: ${error}`);
    }
    return false;
  };

  const handleViewDetail = (skill: Skill) => {
    setSelectedSkill(skill);
    setDetailModalVisible(true);
  };

  const renderDirectoryTab = () => (
    <>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="目录中的Skills"
              value={scannedCount}
              prefix={<FolderOutlined />}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已注册的Skills"
              value={registeredCount}
              prefix={<AppstoreOutlined />}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="分类数量"
              value={categories.length}
              prefix={<FileTextOutlined />}
              styles={{ content: { color: '#722ed1' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已加载的Skills"
              value={loadedSkills.length}
              prefix={<ThunderboltOutlined />}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="目录Skills"
        extra={
          <Space>
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalVisible(true)}>
              上传Skill
            </Button>
            <Button icon={<PlusOutlined />} onClick={() => setRegisterModalVisible(true)}>
              注册Skill
            </Button>
          </Space>
        }
      >
        {scannedCount === 0 ? (
          <Empty description="暂无目录Skills，请上传或扫描" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <AdvancedTable
            request={scannedRequest}
            actionRef={scannedActionRef}
            rowKey="name"
            pagination={{ pageSize: 10 }}
            columns={[
              {
                title: '名称',
                dataIndex: 'name',
                key: 'name',
                render: (name: string) => <Text strong>{name}</Text>,
              },
              {
                title: '分类',
                dataIndex: 'category',
                key: 'category',
                render: (category: string) => <Tag color="blue">{category}</Tag>,
              },
              {
                title: '描述',
                dataIndex: 'description',
                key: 'description',
                render: (desc: string) => <Text type="secondary">{desc || '-'}</Text>,
              },
              {
                title: '文件',
                dataIndex: 'files',
                key: 'files',
                render: (files: string[]) => (
                  <Space>
                    {files.map((f, i) => <Tag key={i}>{f}</Tag>)}
                  </Space>
                ),
              },
              {
                title: '状态',
                dataIndex: 'enabled',
                key: 'enabled',
                render: (enabled: boolean, record: Skill) => (
                  <Switch
                    checked={enabled}
                    onChange={(checked) => handleToggleSkill(record, checked)}
                    checkedChildren={<CheckCircleOutlined />}
                    unCheckedChildren={<StopOutlined />}
                  />
                ),
              },
              {
                title: '操作',
                key: 'action',
                render: (_: unknown, record: Skill) => (
                  <Space>
                    <Button
                      type="link"
                      icon={<EyeOutlined />}
                      size="small"
                      onClick={() => handleViewDetail(record)}
                    >
                      详情
                    </Button>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleEditSkill(record)}
                    >
                      编辑
                    </Button>
                    <Popconfirm
                      title="确认删除此Skill?"
                      onConfirm={() => handleDeleteSkill(record)}
                    >
                      <Button type="link" danger icon={<DeleteOutlined />} size="small">
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>
    </>
  );

  const handleDeleteSkill = async (skill: Skill) => {
    try {
      await api.toggleSkill(skill.name, false);
      message.success(`Skill "${skill.name}" 已禁用并从注册列表移除`);
      refreshAll();
    } catch (error) {
      message.error(`删除失败: ${error}`);
    }
  };

  const handleEditSkill = (skill: Skill) => {
    setEditingSkill(skill);
    setSkillEditorVisible(true);
  };

  const handleSaveSkill = async (skillDef: {
    name: string;
    description: string;
    category: string;
    triggers: string[];
    input_schema: Record<string, unknown>;
    output_schema: Record<string, unknown>;
    sections?: Record<string, string>;
  }) => {
    try {
      const markdown = `# ${skillDef.name}\n\n## Description\n\n${skillDef.description}\n\n## Triggers\n\n${skillDef.triggers.map(t => `- ${t}`).join('\n')}\n\n## Input Schema\n\n\`\`\`json\n${JSON.stringify(skillDef.input_schema, null, 2)}\n\`\`\`\n\n## Output Schema\n\n\`\`\`json\n${JSON.stringify(skillDef.output_schema, null, 2)}\n\`\`\`\n`;
      await api.saveSkillContent(skillDef.name, skillDef.category, markdown);
      message.success(`Skill "${skillDef.name}" 保存成功`);
      setSkillEditorVisible(false);
      setEditingSkill(null);
      refreshAll();
    } catch (error) {
      message.error(`保存失败: ${error}`);
    }
  };

  const renderRegisteredTab = () => (
    <Card title="已注册的Skills">
      {registeredCount === 0 ? (
        <Empty description="暂无注册的Skills" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <AdvancedTable
          request={registeredRequest}
          actionRef={registeredActionRef}
          rowKey="skill_id"
          pagination={{ pageSize: 10 }}
          columns={[
            {
              title: '名称',
              dataIndex: 'name',
              key: 'name',
              render: (name: string) => <Text strong>{name}</Text>,
            },
            {
              title: '类型',
              dataIndex: 'type',
              key: 'type',
              render: (type: string) => <Tag color="green">{type}</Tag>,
            },
            {
              title: '分类',
              dataIndex: 'category',
              key: 'category',
              render: (category: string) => <Tag color="blue">{category}</Tag>,
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => (
                <Badge status={status === 'active' ? 'success' : 'default'} text={status} />
              ),
            },
            {
              title: '操作',
              key: 'action',
              render: (_: unknown, record: any) => (
                <Space>
                  {record.status !== 'active' ? (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleToggleSkill(record as Skill, true)}
                    >
                      启用
                    </Button>
                  ) : (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleToggleSkill(record as Skill, false)}
                    >
                      禁用
                    </Button>
                  )}
                </Space>
              ),
            },
          ]}
        />
      )}
    </Card>
  );

  const renderCategoriesTab = () => (
    <Card title="Skill分类">
      {categories.length === 0 ? (
        <Empty description="暂无分类" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Row gutter={[16, 16]}>
          {categories.map((cat) => (
            <Col span={8} key={cat.name}>
              <Card size="small">
                <Space orientation="vertical">
                  <Text strong>{cat.name}</Text>
                  <Tag color="blue">{cat.skill_count} Skills</Tag>
                  <Text type="secondary" style={{ fontSize: 11 }}>{cat.path}</Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </Card>
  );

  return (
    <div>
      <PageHeader title="Skill 管理" />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'directory', label: '目录Skills', children: renderDirectoryTab() },
          { key: 'registered', label: '已注册', children: renderRegisteredTab() },
          { key: 'categories', label: '分类', children: renderCategoriesTab() },
        ]}
      />

      <Modal
        title="Skill详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={700}
      >
        {selectedSkill && (
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Descriptions column={1}>
              <Descriptions.Item label="名称">
                <Text strong>{selectedSkill.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="分类">
                <Tag color="blue">{selectedSkill.category}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="路径">
                <Text type="secondary" style={{ fontSize: 11 }}>{selectedSkill.path}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="文件">
                <Space>
                  {selectedSkill.files.map((f, i) => <Tag key={i}>{f}</Tag>)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="描述">
                {selectedSkill.description || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="已启用">
                <Switch
                  checked={selectedSkill.enabled}
                  onChange={(checked) => handleToggleSkill(selectedSkill, checked)}
                />
              </Descriptions.Item>
            </Descriptions>

            {selectedSkill.parsed && (
              <>
                <Divider>解析的Schema</Divider>
                {selectedSkill.parsed.input_schema && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>输入Schema:</Text>
                    <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, fontSize: 11 }}>
                      {JSON.stringify(selectedSkill.parsed.input_schema, null, 2)}
                    </pre>
                  </div>
                )}
                {selectedSkill.parsed.output_schema && (
                  <div>
                    <Text strong>输出Schema:</Text>
                    <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, fontSize: 11 }}>
                      {JSON.stringify(selectedSkill.parsed.output_schema, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
          </Space>
        )}
      </Modal>

      <Modal
        title="上传Skill文件"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Select
            value={uploadCategory}
            onChange={setUploadCategory}
            options={[
              { value: 'custom', label: 'custom (自定义)' },
              { value: 'data_ingestion', label: 'data_ingestion (数据摄入)' },
              { value: 'data_cleaning', label: 'data_cleaning (数据清洗)' },
              { value: 'llm_extraction', label: 'llm_extraction (LLM提取)' },
              { value: 'ontology_builder', label: 'ontology_builder (本体构建)' },
              { value: 'version_manager', label: 'version_manager (版本管理)' },
              { value: 'graph_builder', label: 'graph_builder (图谱构建)' },
              { value: 'audit_logger', label: 'audit_logger (审计日志)' },
            ]}
            style={{ width: '100%' }}
          />
          <Upload.Dragger
            accept=".md,.yaml,.yml"
            beforeUpload={handleUploadFile}
            showUploadList={false}
          >
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽上传SKILL.md文件</p>
            <p className="ant-upload-hint">支持 .md, .yaml, .yml 格式</p>
          </Upload.Dragger>
        </Space>
      </Modal>

      <Modal
        title="注册新Skill"
        open={registerModalVisible}
        onCancel={() => setRegisterModalVisible(false)}
        footer={null}
      >
        <Form form={registerForm} onFinish={handleRegisterSkill} layout="vertical">
          <Form.Item
            name="name"
            label="Skill名称"
            rules={[{ required: true, message: '请输入Skill名称' }]}
          >
            <Input placeholder="例如: my_custom_skill" />
          </Form.Item>
          <Form.Item
            name="skill_type"
            label="类型"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select
              options={[
                { value: 'action', label: 'action (执行动作)' },
                { value: 'query', label: 'query (查询)' },
                { value: 'transform', label: 'transform (转换)' },
                { value: 'integration', label: 'integration (集成)' },
              ]}
            />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Input placeholder="例如: custom" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="Skill的描述信息" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            注册
          </Button>
        </Form>
      </Modal>

      {/* Skill 可视化编辑器 */}
      <SkillEditor
        open={skillEditorVisible}
        skill={editingSkill ? {
          name: editingSkill.name,
          description: editingSkill.description || '',
          category: editingSkill.category,
          triggers: [],
          input_schema: editingSkill.parsed?.input_schema || {},
          output_schema: editingSkill.parsed?.output_schema || {},
          sections: editingSkill.parsed?.sections,
        } : undefined}
        onSave={handleSaveSkill}
        onCancel={() => {
          setSkillEditorVisible(false);
          setEditingSkill(null);
        }}
      />
    </div>
  );
}

export default SkillManagement;
