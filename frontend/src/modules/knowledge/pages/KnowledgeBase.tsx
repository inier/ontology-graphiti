import { useState, useEffect } from 'react';
import {
  Card, Button, Input, Modal, Form, message, Table, Popconfirm,
  Space, Tag, Tooltip, Tree, Upload, Tabs, Progress, Spin,
  Empty, Divider, Select, Radio, Descriptions, Badge, Drawer,
  List, Typography, Alert, Row, Col, Statistic,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined,
  FolderOutlined, FileOutlined, UploadOutlined, GlobalOutlined,
  FileTextOutlined, LinkOutlined, BuildOutlined, EyeOutlined,
  RobotOutlined, ArrowLeftOutlined, InboxOutlined, DatabaseOutlined,
  BookOutlined, TagOutlined, BarChartOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { knowledgeApi } from '../services/knowledgeApi';
import type {
  KnowledgeBase as KB, KnowledgeCategory, KnowledgeDocument,
  KnowledgeBaseFormData, DocumentUploadData,
} from '../types';

const { Dragger } = Upload;
const { TextArea } = Input;
const { Title, Text } = Typography;

type ViewMode = 'list' | 'detail' | 'document';

export function KnowledgeBase() {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [knowledgeBases, setKnowledgeBases] = useState<KB[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [kbModalOpen, setKbModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [docDrawerOpen, setDocDrawerOpen] = useState(false);
  const [editingKb, setEditingKb] = useState<KB | null>(null);
  const [currentKb, setCurrentKb] = useState<KB | null>(null);
  const [currentDoc, setCurrentDoc] = useState<KnowledgeDocument | null>(null);
  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [kbForm] = Form.useForm<KnowledgeBaseFormData>();
  const [uploadForm] = Form.useForm<DocumentUploadData>();
  const [uploadTab, setUploadTab] = useState<'file' | 'online_doc' | 'text' | 'web'>('file');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [buildProgress, setBuildProgress] = useState<Record<string, number>>({});

  useEffect(() => {
    loadKnowledgeBases();
  }, []);

  const loadKnowledgeBases = async () => {
    setLoading(true);
    try {
      const data = await knowledgeApi.listKnowledgeBases();
      setKnowledgeBases(data);
    } catch (e) {
      message.error('加载知识库列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async (kbId: string) => {
    try {
      const data = await knowledgeApi.listCategories(kbId);
      setCategories(data);
    } catch (e) {
      console.warn('加载分类失败', e);
    }
  };

  const loadDocuments = async (kbId: string, categoryId?: string) => {
    try {
      const data = await knowledgeApi.listDocuments(kbId, categoryId);
      setDocuments(data);
    } catch (e) {
      console.warn('加载文档失败', e);
    }
  };

  const handleCreateKb = () => {
    setEditingKb(null);
    kbForm.resetFields();
    setKbModalOpen(true);
  };

  const handleEditKb = (kb: KB) => {
    setEditingKb(kb);
    kbForm.setFieldsValue({ name: kb.name, description: kb.description });
    setKbModalOpen(true);
  };

  const handleSaveKb = async (values: KnowledgeBaseFormData) => {
    try {
      if (editingKb) {
        await knowledgeApi.updateKnowledgeBase(editingKb.kb_id, values);
        message.success('更新成功');
      } else {
        await knowledgeApi.createKnowledgeBase(values);
        message.success('创建成功');
      }
      setKbModalOpen(false);
      loadKnowledgeBases();
    } catch (e) {
      message.error('保存失败');
    }
  };

  const handleDeleteKb = async (id: string) => {
    try {
      await knowledgeApi.deleteKnowledgeBase(id);
      message.success('删除成功');
      loadKnowledgeBases();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleEnterKb = (kb: KB) => {
    setCurrentKb(kb);
    setViewMode('detail');
    loadCategories(kb.kb_id);
    loadDocuments(kb.kb_id);
  };

  const handleUploadDoc = () => {
    uploadForm.resetFields();
    setUploadFile(null);
    setUploadTab('file');
    setUploadModalOpen(true);
  };

  const handleSaveUpload = async () => {
    if (!currentKb) return;
    try {
      const values = uploadForm.getFieldsValue();
      const data: DocumentUploadData = {
        kb_id: currentKb.kb_id,
        category_id: selectedCategory || undefined,
        content_type: uploadTab === 'web' ? 'web_crawl' : uploadTab,
        title: values.title,
        content: values.content,
        web_url: values.web_url,
        file: uploadFile || undefined,
      };
      await knowledgeApi.uploadDocument(data);
      message.success('上传成功');
      setUploadModalOpen(false);
      loadDocuments(currentKb.kb_id, selectedCategory || undefined);
      loadKnowledgeBases();
    } catch (e) {
      message.error('上传失败');
    }
  };

  const handleBuildGraph = async (doc: KnowledgeDocument) => {
    try {
      setBuildProgress(prev => ({ ...prev, [doc.doc_id]: 0 }));
      const result = await knowledgeApi.buildGraph({
        doc_id: doc.doc_id,
        extraction_config: {
          extract_entities: true,
          extract_relations: true,
          entity_types: ['Person', 'Organization', 'Product', 'Location', 'Event'],
          relation_types: ['belongs_to', 'located_at', 'produces', 'participates_in'],
        },
      });
      message.success('图谱构建任务已启动');
      // 模拟进度
      let progress = 0;
      const interval = setInterval(() => {
        progress += 10;
        setBuildProgress(prev => ({ ...prev, [doc.doc_id]: progress }));
        if (progress >= 100) {
          clearInterval(interval);
          loadDocuments(doc.kb_id, selectedCategory || undefined);
        }
      }, 500);
    } catch (e) {
      message.error('图谱构建失败');
    }
  };

  const handleViewDoc = (doc: KnowledgeDocument) => {
    setCurrentDoc(doc);
    setDocDrawerOpen(true);
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!currentKb) return;
    try {
      await knowledgeApi.deleteDocument(currentKb.kb_id, docId);
      message.success('删除成功');
      loadDocuments(currentKb.kb_id, selectedCategory || undefined);
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleCategorySelect = (keys: React.Key[]) => {
    const key = keys[0] as string;
    setSelectedCategory(key || null);
    if (currentKb) {
      loadDocuments(currentKb.kb_id, key || undefined);
    }
  };

  const filteredKbs = knowledgeBases.filter(kb =>
    kb.name.toLowerCase().includes(searchText.toLowerCase()) ||
    kb.description.toLowerCase().includes(searchText.toLowerCase())
  );

  // 知识库列表视图
  if (viewMode === 'list') {
    const columns = [
      {
        title: '知识库',
        dataIndex: 'name',
        render: (_: string, record: KB) => (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 8, background: '#f0f5ff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <BookOutlined style={{ fontSize: 20, color: '#1890ff' }} />
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>{record.name}</div>
              <Text type="secondary" style={{ fontSize: 12 }}>{record.description}</Text>
            </div>
          </div>
        ),
      },
      {
        title: '知识数',
        dataIndex: 'knowledge_count',
        width: 100,
        align: 'center' as const,
      },
      {
        title: '分类数',
        dataIndex: 'category_count',
        width: 100,
        align: 'center' as const,
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 100,
        render: (status: string) => {
          const statusMap: Record<string, { color: string; text: string }> = {
            active: { color: 'success', text: '正常' },
            building: { color: 'processing', text: '构建中' },
            error: { color: 'error', text: '异常' },
          };
          const s = statusMap[status] || { color: 'default', text: status };
          return <Badge status={s.color as any} text={s.text} />;
        },
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        width: 180,
        render: (v: string) => new Date(v).toLocaleString(),
      },
      {
        title: '操作',
        width: 160,
        render: (_: unknown, record: KB) => (
          <Space>
            <Button type="text" icon={<EyeOutlined />} onClick={() => handleEnterKb(record)}>查看</Button>
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEditKb(record)}>编辑</Button>
            <Popconfirm title="确认删除？" onConfirm={() => handleDeleteKb(record.kb_id)}>
              <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          </Space>
        ),
      },
    ];

    return (
      <Card
        title={<Title level={4} style={{ margin: 0 }}><DatabaseOutlined /> 知识库</Title>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateKb}>
            新建知识库
          </Button>
        }
      >
        <Input.Search
          placeholder="搜索知识库"
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          style={{ width: 300, marginBottom: 16 }}
          allowClear
          prefix={<SearchOutlined />}
        />
        <Table
          dataSource={filteredKbs}
          columns={columns}
          rowKey="kb_id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />

        <Modal
          title={editingKb ? '编辑知识库' : '新建知识库'}
          open={kbModalOpen}
          onCancel={() => setKbModalOpen(false)}
          onOk={() => kbForm.submit()}
          width={480}
        >
          <Form form={kbForm} layout="vertical" onFinish={handleSaveKb}>
            <Form.Item name="name" label="知识库名称" rules={[{ required: true }]}>
              <Input placeholder="请输入知识库名称" />
            </Form.Item>
            <Form.Item name="description" label="描述">
              <TextArea placeholder="请输入知识库描述" rows={3} />
            </Form.Item>
          </Form>
        </Modal>
      </Card>
    );
  }

  // 知识库详情视图
  if (viewMode === 'detail' && currentKb) {
    const treeData = categories.map(cat => ({
      title: cat.name,
      key: cat.category_id,
      icon: <FolderOutlined />,
      children: cat.children?.map(child => ({
        title: child.name,
        key: child.category_id,
        icon: <FolderOutlined />,
      })),
    }));

    const docColumns = [
      {
        title: '文档',
        dataIndex: 'title',
        render: (_: string, record: KnowledgeDocument) => (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {record.content_type === 'file' ? <FileOutlined /> :
             record.content_type === 'web_crawl' ? <GlobalOutlined /> :
             <FileTextOutlined />}
            <div>
              <div>{record.title}</div>
              {record.keywords?.length > 0 && (
                <Space size={4} style={{ marginTop: 4 }}>
                  {record.keywords.slice(0, 3).map(k => <Tag key={k}>{k}</Tag>)}
                </Space>
              )}
            </div>
          </div>
        ),
      },
      {
        title: '类型',
        dataIndex: 'content_type',
        width: 100,
        render: (t: string) => {
          const typeMap: Record<string, string> = {
            file: '文件', online_doc: '在线文档', text: '纯文本', web_crawl: '网页抓取',
          };
          return <Tag>{typeMap[t] || t}</Tag>;
        },
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 100,
        render: (status: string) => {
          const statusMap: Record<string, { color: string; text: string }> = {
            pending: { color: 'default', text: '待处理' },
            processing: { color: 'processing', text: '处理中' },
            indexed: { color: 'success', text: '已索引' },
            error: { color: 'error', text: '异常' },
          };
          const s = statusMap[status] || { color: 'default', text: status };
          return <Badge status={s.color as any} text={s.text} />;
        },
      },
      {
        title: '图谱',
        dataIndex: 'graph_built',
        width: 120,
        render: (built: boolean, record: KnowledgeDocument) => (
          built ? <Tag color="success">已构建</Tag> :
          buildProgress[record.doc_id] !== undefined ? (
            <Progress percent={buildProgress[record.doc_id]} size="small" />
          ) : (
            <Button size="small" icon={<BuildOutlined />} onClick={() => handleBuildGraph(record)}>
              构建图谱
            </Button>
          )
        ),
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        width: 180,
        render: (v: string) => new Date(v).toLocaleString(),
      },
      {
        title: '操作',
        width: 120,
        render: (_: unknown, record: KnowledgeDocument) => (
          <Space>
            <Button type="text" icon={<EyeOutlined />} onClick={() => handleViewDoc(record)} />
            <Popconfirm title="确认删除？" onConfirm={() => handleDeleteDoc(record.doc_id)}>
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        ),
      },
    ];

    return (
      <div style={{ display: 'flex', height: 'calc(100vh - 140px)', gap: 16 }}>
        {/* 左侧分类树 */}
        <Card style={{ width: 260, flexShrink: 0 }} styles={{ body: { padding: 12 } }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => setViewMode('list')} />
            <Text strong style={{ fontSize: 16 }}>{currentKb.name}</Text>
          </div>
          <Divider style={{ margin: '8px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Text type="secondary">分类</Text>
            <Button type="text" size="small" icon={<PlusOutlined />}>新建</Button>
          </div>
          <Tree
            treeData={treeData}
            onSelect={handleCategorySelect}
            selectedKeys={selectedCategory ? [selectedCategory] : []}
            defaultExpandAll
          />
        </Card>

        {/* 右侧文档列表 */}
        <Card
          style={{ flex: 1 }}
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <span>{selectedCategory ? '分类文档' : '全部文档'}</span>
                <Tag>{documents.length} 个文档</Tag>
              </Space>
              <Space>
                <Button icon={<GlobalOutlined />}>外部抓取</Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={handleUploadDoc}>
                  添加知识
                </Button>
              </Space>
            </div>
          }
        >
          <Table
            dataSource={documents}
            columns={docColumns}
            rowKey="doc_id"
            pagination={{ pageSize: 10 }}
          />
        </Card>

        {/* 上传弹窗 */}
        <Modal
          title="添加知识"
          open={uploadModalOpen}
          onCancel={() => setUploadModalOpen(false)}
          onOk={handleSaveUpload}
          width={600}
          destroyOnHidden
        >
          <Form form={uploadForm} layout="vertical">
            <Form.Item name="title" label="标题" rules={[{ required: true }]}>
              <Input placeholder="请输入文档标题" />
            </Form.Item>

            <Tabs activeKey={uploadTab} onChange={k => setUploadTab(k as any)}>
              <Tabs.TabPane tab="文件" key="file">
                <Dragger
                  beforeUpload={(file) => { setUploadFile(file); return false; }}
                  maxCount={1}
                  fileList={uploadFile ? [{ uid: '-1', name: uploadFile.name, status: 'done', originFileObj: uploadFile as any }] : []}
                  onRemove={() => setUploadFile(null)}
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p className="ant-upload-text">点击或拖拽文件到此区域</p>
                  <p className="ant-upload-hint">支持 PDF、Word、PPT、TXT 等格式</p>
                </Dragger>
              </Tabs.TabPane>
              <Tabs.TabPane tab="在线文档" key="online_doc">
                <Form.Item name="web_url" label="文档链接">
                  <Input placeholder="请输入在线文档链接" prefix={<LinkOutlined />} />
                </Form.Item>
              </Tabs.TabPane>
              <Tabs.TabPane tab="纯文本" key="text">
                <Form.Item name="content" label="内容">
                  <TextArea placeholder="请输入文本内容" rows={6} />
                </Form.Item>
              </Tabs.TabPane>
              <Tabs.TabPane tab="网页抓取" key="web">
                <Form.Item name="web_url" label="网页URL">
                  <Input placeholder="请输入要抓取的网页URL" prefix={<GlobalOutlined />} />
                </Form.Item>
                <Alert
                  type="info"
                  showIcon
                  message="系统将自动抓取网页内容并提取结构化知识"
                  style={{ marginTop: 8 }}
                />
              </Tabs.TabPane>
            </Tabs>

            <Form.Item name="category_id" label="分类">
              <Select placeholder="请选择分类（可选）" allowClear>
                {categories.map(cat => (
                  <Select.Option key={cat.category_id} value={cat.category_id}>{cat.name}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          </Form>
        </Modal>

        {/* 文档详情抽屉 */}
        <Drawer
          title="文档详情"
          open={docDrawerOpen}
          onClose={() => setDocDrawerOpen(false)}
          size={600}
        >
          {currentDoc && (
            <div>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="标题">{currentDoc.title}</Descriptions.Item>
                <Descriptions.Item label="类型">
                  <Tag>{currentDoc.content_type}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Badge status={currentDoc.status === 'indexed' ? 'success' : 'processing'} text={currentDoc.status} />
                </Descriptions.Item>
                <Descriptions.Item label="关键词">
                  <Space wrap>
                    {currentDoc.keywords?.map(k => <Tag key={k}>{k}</Tag>)}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="摘要">{currentDoc.summary || '—'}</Descriptions.Item>
                <Descriptions.Item label="图谱状态">
                  {currentDoc.graph_built ? <Tag color="success">已构建</Tag> : <Tag>未构建</Tag>}
                </Descriptions.Item>
              </Descriptions>

              {currentDoc.content && (
                <div style={{ marginTop: 24 }}>
                  <Title level={5}>内容预览</Title>
                  <div style={{
                    padding: 16, background: '#f5f7fa', borderRadius: 8,
                    maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap',
                  }}>
                    {currentDoc.content}
                  </div>
                </div>
              )}

              {!currentDoc.graph_built && (
                <div style={{ marginTop: 24 }}>
                  <Button type="primary" icon={<BuildOutlined />} block onClick={() => handleBuildGraph(currentDoc)}>
                    构建知识图谱
                  </Button>
                </div>
              )}
            </div>
          )}
        </Drawer>
      </div>
    );
  }

  return null;
}
