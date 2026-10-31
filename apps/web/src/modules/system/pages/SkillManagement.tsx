import { useState, useEffect, useCallback } from 'react';
import { Card, Button, Space, Tag, Switch, Upload, Modal, Form, Input, Select, Tabs, Row, Col, Statistic, message, Popconfirm, Empty, Descriptions, Badge, Divider, Typography, Table } from 'antd';
import { UploadOutlined, PlusOutlined, DeleteOutlined, CheckCircleOutlined, StopOutlined, AppstoreOutlined, FolderOutlined, FileTextOutlined, EyeOutlined, ThunderboltOutlined, ScanOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';
import { PageHeader } from '@/modules/shared';
import { SkillEditor } from '../components/SkillEditor';
import ToolRegistry from '../components/ToolRegistry';
import HookManager from '../components/HookManager';
import MCPManager from '../components/MCPManager';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

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
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState('directory');
  const [scannedCount, setScannedCount] = useState(0);
  const [registeredCount, setRegisteredCount] = useState(0);
  const [categories, setCategories] = useState<Array<{ name: string; skill_count: number; path: string }>>([]);
  const [loadedSkills, setLoadedSkills] = useState<string[]>([]);
  const [allScannedSkills, setAllScannedSkills] = useState<Skill[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [registerModalVisible, setRegisterModalVisible] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('custom');
  const [registerForm] = Form.useForm();
  const [skillEditorVisible, setSkillEditorVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);

  /**
   * 表格刷新令牌：AdvancedTable 的 `params` 变更会触发 ProTable 重新发起 request。
   * 相比持有 ProTable 的 ActionType ref，这样做不产生渲染期 ref 读取，
   * 也让刷新动作可以由任意 async 处理函数触发。
   */
  const [reloadToken, setReloadToken] = useState(0);

  // 统计数据加载（分类 + 已加载Skill + 已扫描Skills + 计数）
  const loadStats = useCallback(async () => {
    try {
      const [categoriesResult, loadedResult, allResult] = await Promise.all([
        api.getSkillCategories().catch(() => ({ categories: [] as { name: string; skill_count: number; path: string }[] })),
        api.getLoadedSkills().catch(() => ({ skills: [] as string[] })),
        api.getAllSkills().catch(() => ({ registered: [] as Skill[], scanned: [] as Skill[], total_registered: 0, total_scanned: 0 })),
      ]);
      setCategories(categoriesResult.categories || []);
      setLoadedSkills(loadedResult.skills || []);
      const registered = (allResult.registered || []) as Skill[];
      const scanned = (allResult.scanned || []) as Skill[];
      // 构建 name → skill_id 映射，注入到 scanned 数据中以便删除按钮可用
      const nameToSkillId = new Map<string, string>();
      registered.forEach((s) => {
        if (s.name && s.skill_id) nameToSkillId.set(s.name, s.skill_id);
      });
      const enabledNames = new Set(registered.filter((s: Skill) => s.status === 'active').map((s: Skill) => s.name));
      setAllScannedSkills(scanned.map(s => ({
        ...s,
        skill_id: nameToSkillId.get(s.name),
        enabled: s.enabled ?? enabledNames.has(s.name),
      })));
      // 关键修复：用接口返回的 total 字段初始化计数，避免条件渲染死锁
      setScannedCount(allResult.total_scanned ?? scanned.length);
      setRegisteredCount(allResult.total_registered ?? registered.length);
    } catch (error) {
      console.error('加载统计数据失败:', error);
    }
  }, []);

  useEffect(() => {
        void (async () => {
      loadStats();
    })();
  }, []);

  // 目录Skills请求
  const fetchScannedSkills = async (): Promise<Skill[]> => {
    const [scanResult, allResult] = await Promise.all([
      api.scanSkillsDirectory().catch(() => ({ skills: [] as Skill[], total: 0 })),
      api.getAllSkills().catch(() => ({
        registered: [] as Array<Record<string, unknown>>,
        scanned: [] as Array<Record<string, unknown>>,
        total_registered: 0,
        total_scanned: 0,
      })),
    ]);
    // /api/skill/all 的 registered 是未建模的裸对象，逐字段取值而非整体断言
    const registered = allResult.registered || [];
    const nameToSkillId = new Map<string, string>();
    const enabledNames = new Set<string>();
    for (const raw of registered) {
      const name = typeof raw.name === 'string' ? raw.name : '';
      if (!name) continue;
      if (typeof raw.skill_id === 'string') nameToSkillId.set(name, raw.skill_id);
      if (raw.status === 'active') enabledNames.add(name);
    }
    return (scanResult.skills || []).map(s => ({
      ...s,
      skill_id: nameToSkillId.get(s.name),
      enabled: enabledNames.has(s.name),
    }));
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

  const refreshAll = useCallback(() => {
    setReloadToken((n) => n + 1);
    void loadStats();
  }, [loadStats]);

  const handleScanAndRegister = async () => {
    try {
      const result = await api.scanAndRegisterSkills();
      if (result.status === 'success') {
        const data = result.data;
        message.success(
          t('扫描完成: 共发现 {{total}} 个Skill，新注册 {{registered}} 个', { 
            total: data.total_scanned, 
            registered: data.registered 
          })
        );
        if (data.errors.length > 0) {
          message.warning(
            t('有 {{count}} 个Skill注册失败', { count: data.errors.length })
          );
        }
        refreshAll();
      }
    } catch (error) {
      message.error(t('扫描失败') + `: ${error}`);
    }
  };

  const handleToggleSkill = useCallback(async (skill: Skill, enabled: boolean) => {
    try {
      await api.toggleSkill(skill.name, enabled);
      message.success(enabled ? t('Skill "{{name}}" 已启用', { name: skill.name }) : t('Skill "{{name}}" 已禁用', { name: skill.name }));
      // 函数式更新：避免闭包捕获 selectedSkill，同时让 useCallback 依赖收敛为稳定函数
      setSelectedSkill((prev) =>
        prev && prev.name === skill.name ? { ...prev, enabled, status: enabled ? 'active' : 'inactive' } : prev,
      );
      refreshAll();
    } catch (error) {
      message.error(t('操作失败') + `: ${error}`);
    }
  }, [refreshAll, t]);

  const handleRegisterSkill = async (values: { name: string; skill_type: string; description: string; category: string }) => {
    try {
      await api.registerSkill(values);
      message.success(t('Skill 注册成功'));
      setRegisterModalVisible(false);
      registerForm.resetFields();
      refreshAll();
    } catch (error) {
      message.error(t('注册失败') + `: ${error}`);
    }
  };

  const handleUploadFile = async (file: File) => {
    try {
      if (file.name.toLowerCase().endsWith('.zip')) {
        // ZIP上传处理
        const result = await api.uploadSkillZip(file, uploadCategory);
        if (result.status === 'success') {
          const data = result.data;
          message.success(
            t('Skill "{{name}}" 上传并注册成功', { name: data.name || file.name })
          );
          if (data.parsed?.description) {
            message.info(t('描述: {{desc}}', { desc: data.parsed.description as string }));
          }
          setUploadModalVisible(false);
          refreshAll();
        }
      } else {
        // 单文件上传处理
        const result = await api.uploadSkillFile(file, uploadCategory);
        if (result.status === 'success') {
          message.success(t('文件 {{name}} 上传成功', { name: file.name }));
          setUploadModalVisible(false);
          refreshAll();
        }
      }
    } catch (error) {
      message.error(t('上传失败') + `: ${error}`);
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
              title={t('目录中的Skills')}
              value={scannedCount}
              prefix={<FolderOutlined />}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('已注册的Skills')}
              value={registeredCount}
              prefix={<AppstoreOutlined />}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('分类数量')}
              value={categories.length}
              prefix={<FileTextOutlined />}
              styles={{ content: { color: '#722ed1' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('已加载的Skills')}
              value={loadedSkills.length}
              prefix={<ThunderboltOutlined />}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={t('目录Skills')}
        extra={
          <Space>
            <Button type="primary" icon={<ScanOutlined />} onClick={handleScanAndRegister}>
              {t('扫描并注册')}
            </Button>
            <Button icon={<UploadOutlined />} onClick={() => setUploadModalVisible(true)}>
              {t('上传Skill')}
            </Button>
            <Button icon={<PlusOutlined />} onClick={() => setRegisterModalVisible(true)}>
              {t('注册Skill')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          request={scannedRequest}
          params={{ reloadToken }}
          rowKey="name"
          pagination={{ pageSize: 10 }}
          columns={[
              {
                title: t('名称'),
                dataIndex: 'name',
                key: 'name',
                render: (name: string) => <Text strong>{name}</Text>,
              },
              {
                title: t('分类'),
                dataIndex: 'category',
                key: 'category',
                render: (category: string) => <Tag color="blue">{category}</Tag>,
              },
              {
                title: t('描述'),
                dataIndex: 'description',
                key: 'description',
                render: (desc: string) => <Text type="secondary">{desc || '-'}</Text>,
              },
              {
                title: t('文件'),
                dataIndex: 'files',
                key: 'files',
                render: (files: string[]) => (
                  <Space>
                    {files.map((f, i) => <Tag key={i}>{f}</Tag>)}
                  </Space>
                ),
              },
              {
                title: t('状态'),
                dataIndex: 'enabled',
                key: 'enabled',
                render: (enabled: boolean, record: Skill) => (
                  <Switch
                    checked={enabled}
                    disabled={!record.skill_id}
                    onChange={(checked) => handleToggleSkill(record, checked)}
                    checkedChildren={<CheckCircleOutlined />}
                    unCheckedChildren={<StopOutlined />}
                  />
                ),
              },
              {
                title: t('操作'),
                key: 'action',
                render: (_: unknown, record: Skill) => (
                  <Space>
                    <Button
                      type="link"
                      icon={<EyeOutlined />}
                      size="small"
                      onClick={() => handleViewDetail(record)}
                    >
                      {t('详情')}
                    </Button>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleEditSkill(record)}
                    >
                      {t('编辑')}
                    </Button>
                    <Popconfirm
                      title={t('确认删除此Skill?')}
                      onConfirm={() => handleDeleteSkill(record)}
                    >
                      <Button type="link" danger icon={<DeleteOutlined />} size="small">
                        {t('删除')}
                      </Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
        />
      </Card>
    </>
  );

  const handleDeleteSkill = async (skill: Skill) => {
    try {
      // 优先使用 skill_id 调用 DELETE 接口真正删除
      if (skill.skill_id) {
        await api.deleteSkill(skill.skill_id);
        message.success(t('Skill "{{name}}" 已删除', { name: skill.name }));
      } else {
        // 兜底：skill_id 缺失时只禁用
        await api.toggleSkill(skill.name, false);
        message.success(t('Skill "{{name}}" 已禁用（无 skill_id，未真正删除）', { name: skill.name }));
      }
      refreshAll();
    } catch (error) {
      message.error(t('删除失败') + `: ${error}`);
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
      message.success(t('Skill "{{name}}" 保存成功', { name: skillDef.name }));
      setSkillEditorVisible(false);
      setEditingSkill(null);
      refreshAll();
    } catch (error) {
      message.error(t('保存失败') + `: ${error}`);
    }
  };

  const renderRegisteredTab = () => (
    <Card title={t('已注册的Skills')}>
      <AdvancedTable
        request={registeredRequest}
        params={{ reloadToken }}
        rowKey="skill_id"
        pagination={{ pageSize: 10 }}
        columns={[
            {
              title: t('名称'),
              dataIndex: 'name',
              key: 'name',
              render: (name: string) => <Text strong>{name}</Text>,
            },
            {
              title: t('类型'),
              dataIndex: 'type',
              key: 'type',
              render: (type: string) => <Tag color="green">{type}</Tag>,
            },
            {
              title: t('分类'),
              dataIndex: 'category',
              key: 'category',
              render: (category: string) => <Tag color="blue">{category}</Tag>,
            },
            {
              title: t('状态'),
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => (
                <Badge status={status === 'active' ? 'success' : 'default'} text={status} />
              ),
            },
            {
              title: t('操作'),
              key: 'action',
              render: (_: unknown, record: Skill) => (
                <Space>
                  {record.status !== 'active' ? (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleToggleSkill(record as Skill, true)}
                    >
                      {t('启用')}
                    </Button>
                  ) : (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleToggleSkill(record as Skill, false)}
                    >
                      {t('禁用')}
                    </Button>
                  )}
                </Space>
              ),
            },
          ]}
      />
    </Card>
  );

  const renderCategoriesTab = () => {
    const categorySkills = selectedCategory
      ? allScannedSkills.filter(s => s.category === selectedCategory)
      : [];

    return (
      <>
        <Card title={t('Skill分类')} style={{ marginBottom: 16 }}>
          {categories.length === 0 ? (
            <Empty description={t('暂无分类')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Row gutter={[16, 16]}>
              {categories.map((cat) => (
                <Col span={8} key={cat.name}>
                  <Card 
                    size="small" 
                    hoverable
                    style={{ 
                      cursor: 'pointer',
                      borderColor: selectedCategory === cat.name ? '#1890ff' : undefined,
                      boxShadow: selectedCategory === cat.name ? '0 0 0 2px rgba(24,144,255,0.2)' : undefined
                    }}
                    onClick={() => setSelectedCategory(cat.name)}
                  >
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

        {selectedCategory && (
          <Card 
            title={t('分类 "{{cat}}" 下的Skill', { cat: selectedCategory })}
            extra={
              <Button size="small" onClick={() => setSelectedCategory(null)}>
                {t('返回全部分类')}
              </Button>
            }
          >
            {categorySkills.length === 0 ? (
              <Empty description={t('该分类下暂无Skill')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Table
                rowKey="name"
                pagination={{ pageSize: 10 }}
                dataSource={categorySkills}
                columns={[
                  {
                    title: t('名称'),
                    dataIndex: 'name',
                    key: 'name',
                    render: (name: string) => <Text strong>{name}</Text>,
                  },
                  {
                    title: t('描述'),
                    dataIndex: 'description',
                    key: 'description',
                    render: (desc: string) => <Text type="secondary">{desc || '-'}</Text>,
                  },
                  {
                    title: t('文件'),
                    dataIndex: 'files',
                    key: 'files',
                    render: (files: string[]) => (
                      <Space>
                        {files.map((f, i) => <Tag key={i}>{f}</Tag>)}
                      </Space>
                    ),
                  },
                  {
                    title: t('状态'),
                    dataIndex: 'enabled',
                    key: 'enabled',
                    render: (enabled: boolean, record: Skill) => (
                      <Switch
                        checked={enabled}
                        disabled={!record.skill_id}
                        onChange={(checked) => handleToggleSkill(record, checked)}
                        checkedChildren={<CheckCircleOutlined />}
                        unCheckedChildren={<StopOutlined />}
                      />
                    ),
                  },
                  {
                    title: t('操作'),
                    key: 'action',
                    render: (_: unknown, record: Skill) => (
                      <Space>
                        <Button
                          type="link"
                          icon={<EyeOutlined />}
                          size="small"
                          onClick={() => handleViewDetail(record)}
                        >
                          {t('详情')}
                        </Button>
                        <Button
                          type="link"
                          size="small"
                          onClick={() => handleEditSkill(record)}
                        >
                          {t('编辑')}
                        </Button>
                        <Popconfirm
                          title={t('确认删除此Skill?')}
                          onConfirm={() => handleDeleteSkill(record)}
                        >
                          <Button type="link" danger icon={<DeleteOutlined />} size="small">
                            {t('删除')}
                          </Button>
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
              />
            )}
          </Card>
        )}
      </>
    );
  };

  return (
    <div>
      <PageHeader title={t('Skill 管理')} />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'directory', label: t('目录Skills'), children: renderDirectoryTab() },
          { key: 'registered', label: t('已注册'), children: renderRegisteredTab() },
          { key: 'categories', label: t('分类'), children: renderCategoriesTab() },
          // 工具与钩子是技能体系的另外两层：技能声明"做什么"，
          // 工具是可供调用的实现，钩子是执行前后的拦截点。三者共用 /api/skill|tools|hooks。
          { key: 'tools', label: t('工具注册表'), children: <ToolRegistry /> },
          { key: 'hooks', label: t('钩子管理'), children: <HookManager /> },
          // MCP 服务器是「工具从哪来」的上一层：工具注册表登记本仓工具，
          // MCP 管理登记外部 server 及其暴露的 tool（/api/mcp/servers 全套端点）。
          { key: 'mcp', label: t('MCP 服务器'), children: <MCPManager /> },
        ]}
      />

      <Modal
        title={t('Skill详情')}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            {t('关闭')}
          </Button>
        ]}
        width={700}
      >
        {selectedSkill && (
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Descriptions column={1}>
              <Descriptions.Item label={t('名称')}>
                <Text strong>{selectedSkill.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label={t('分类')}>
                <Tag color="blue">{selectedSkill.category}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('描述')}>
                {selectedSkill.description || '-'}
              </Descriptions.Item>
              <Descriptions.Item label={t('已启用')}>
                <Switch
                  checked={selectedSkill.enabled}
                  disabled={!selectedSkill.skill_id}
                  onChange={(checked) => handleToggleSkill(selectedSkill, checked)}
                />
              </Descriptions.Item>
            </Descriptions>

            {selectedSkill.parsed && (
              <>
                <Divider>{t('解析的Schema')}</Divider>
                {selectedSkill.parsed.input_schema && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>{t('输入Schema:')}</Text>
                    <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, fontSize: 11 }}>
                      {JSON.stringify(selectedSkill.parsed.input_schema, null, 2)}
                    </pre>
                  </div>
                )}
                {selectedSkill.parsed.output_schema && (
                  <div>
                    <Text strong>{t('输出Schema:')}</Text>
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
        title={t('上传Skill文件')}
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Select
            value={uploadCategory}
            onChange={setUploadCategory}
            options={[
              { value: 'custom', label: t('custom (自定义)') },
              { value: 'data_ingestion', label: t('data_ingestion (数据摄入)') },
              { value: 'data_cleaning', label: t('data_cleaning (数据清洗)') },
              { value: 'llm_extraction', label: t('llm_extraction (LLM提取)') },
              { value: 'ontology_builder', label: t('ontology_builder (本体构建)') },
              { value: 'version_manager', label: t('version_manager (版本管理)') },
              { value: 'graph_builder', label: t('graph_builder (图谱构建)') },
              { value: 'audit_logger', label: t('audit_logger (审计日志)') },
            ]}
            style={{ width: '100%' }}
          />
          <Upload.Dragger
            accept=".md,.yaml,.yml,.zip"
            beforeUpload={handleUploadFile}
            showUploadList={false}
          >
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">{t('点击或拖拽上传Skill文件或压缩包')}</p>
            <p className="ant-upload-hint">{t('支持 .md, .yaml, .yml 格式文件，或包含 SKILL.md 的 .zip 压缩包')}</p>
          </Upload.Dragger>
        </Space>
      </Modal>

      <Modal
        title={t('注册新Skill')}
        open={registerModalVisible}
        onCancel={() => setRegisterModalVisible(false)}
        footer={null}
      >
        <Form form={registerForm} onFinish={handleRegisterSkill} layout="vertical">
          <Form.Item
            name="name"
            label={t('Skill名称')}
            rules={[{ required: true, message: t('请输入Skill名称') }]}
          >
            <Input placeholder={t('例如: my_custom_skill')} />
          </Form.Item>
          <Form.Item
            name="skill_type"
            label={t('类型')}
            rules={[{ required: true, message: t('请选择类型') }]}
          >
            <Select
              options={[
                { value: 'action', label: t('action (执行动作)') },
                { value: 'query', label: t('query (查询)') },
                { value: 'transform', label: t('transform (转换)') },
                { value: 'integration', label: t('integration (集成)') },
              ]}
            />
          </Form.Item>
          <Form.Item name="category" label={t('分类')}>
            <Input placeholder={t('例如: custom')} />
          </Form.Item>
          <Form.Item name="description" label={t('描述')}>
            <TextArea rows={3} placeholder={t('Skill的描述信息')} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            {t('注册')}
          </Button>
        </Form>
      </Modal>

      {/* Skill 可视化编辑器 */}
      <SkillEditor
        key={skillEditorVisible ? (editingSkill?.name ?? '__new__') : '__closed__'}
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
