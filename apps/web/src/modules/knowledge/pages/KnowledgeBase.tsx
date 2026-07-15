import { useState, useEffect, useRef, useCallback } from 'react';

import {
  App,
  Card, Button, Input, Modal, Form, Popconfirm,

  Space, Tag, Tooltip, Tree, Upload, Tabs, Progress, Spin,

  Empty, Divider, Select, Radio, Descriptions, Badge, Drawer,

  List, Typography, Alert, Row, Col, Statistic,

} from 'antd';

import {

  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined,

  FolderOutlined, FileOutlined, UploadOutlined, GlobalOutlined,

  FileTextOutlined, LinkOutlined, BuildOutlined, EyeOutlined,

  RobotOutlined, ArrowLeftOutlined, InboxOutlined, DatabaseOutlined,

  BookOutlined, TagOutlined, BarChartOutlined, ApartmentOutlined,

} from '@ant-design/icons';

import type { UploadProps } from 'antd';

import { knowledgeApi } from '../services/knowledgeApi';

import type {

  KnowledgeBase as KB, KnowledgeCategory, KnowledgeDocument,

  KnowledgeBaseFormData, DocumentUploadData, KbGraphData,

} from '../types';

import { EmptyState } from '@/modules/shared/components/organisms';

import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { AdvancedTable, DocumentViewer } from '@/modules/shared';



const { Dragger } = Upload;

const { TextArea } = Input;

const { Title, Text } = Typography;

const MIME_FRIENDLY: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word 文档',
  'application/msword': 'Word 文档 (旧版)',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel 表格',
  'application/vnd.ms-excel': 'Excel 表格 (旧版)',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPT 演示',
  'application/vnd.ms-powerpoint': 'PPT 演示 (旧版)',
  'text/plain': '纯文本',
  'text/markdown': 'Markdown',
  'text/csv': 'CSV 表格',
  'text/html': 'HTML',
  'application/json': 'JSON',
  'image/png': 'PNG 图片',
  'image/jpeg': 'JPEG 图片',
  'image/gif': 'GIF 图片',
  'image/svg+xml': 'SVG 图片',
};

function friendlyFileType(fileType?: string): string {
  if (!fileType) return '未知';
  return MIME_FRIENDLY[fileType] || fileType.split('/').pop()?.toUpperCase() || fileType;
}

/** 检测关键词是否为 URL */
const URL_RE = /^https?:\/\/\S+/i;
function isUrlKeyword(k: string): boolean { return URL_RE.test(k.trim()); }

/** 从 URL 提取简短域名显示 */
function shortDomain(url: string): string {
  try {
    const u = new URL(url.trim());
    return u.hostname.replace(/^www\./, '');
  } catch { return url.slice(0, 30); }
}

/** 智能关键词标签：URL 显示为可点击链接，长文本截断+Tooltip */
function KeywordTag({ keyword, maxLen = 24 }: { keyword: string; maxLen?: number }) {
  if (isUrlKeyword(keyword)) {
    return (
      <Tooltip title={keyword}>
        <Tag icon={<LinkOutlined />} color="blue" style={{ cursor: 'pointer' }}>
          <a href={keyword.trim()} target="_blank" rel="noreferrer" style={{ color: 'inherit' }}>
            {shortDomain(keyword)}
          </a>
        </Tag>
      </Tooltip>
    );
  }
  const truncated = keyword.length > maxLen;
  const display = truncated ? keyword.slice(0, maxLen) + '…' : keyword;
  return truncated ? (
    <Tooltip title={keyword}>
      <Tag style={{ maxWidth: maxLen * 10 + 40 }}>{display}</Tag>
    </Tooltip>
  ) : (
    <Tag>{keyword}</Tag>
  );
}

function deriveDocStatus(doc: KnowledgeDocument): { label: string; color: string } {
  if (doc.status === 'error') return { label: '处理失败', color: 'error' };
  if (doc.status === 'processing') return { label: '处理中', color: 'processing' };
  if (doc.graph_built) return { label: '图谱已构建', color: 'success' };
  if (doc.status === 'indexed') return { label: '已索引', color: 'success' };
  return { label: '待处理', color: 'default' };
}



type ViewMode = 'list' | 'detail' | 'document';



export function KnowledgeBase() {

  const { message } = App.useApp();

  const [viewMode, setViewMode] = useState<ViewMode>('list');

  const [knowledgeBases, setKnowledgeBases] = useState<KB[]>([]);

  const [loading, setLoading] = useState(false);

  const { currentWorkspace } = useWorkspace();

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

  const [categoryModalOpen, setCategoryModalOpen] = useState(false);

  const [categoryForm] = Form.useForm();

  const [graphModalOpen, setGraphModalOpen] = useState(false);

  const [graphData, setGraphData] = useState<KbGraphData | null>(null);

  const [graphLoading, setGraphLoading] = useState(false);

  const graphChartRef = useRef<HTMLDivElement>(null);

  const echartsInstanceRef = useRef<any>(null);



  useEffect(() => {

    loadKnowledgeBases();

  }, []);

  // 组件卸载时清理 ECharts 实例
  useEffect(() => {
    return () => {
      if (echartsInstanceRef.current) {
        echartsInstanceRef.current.dispose();
        echartsInstanceRef.current = null;
      }
    };
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
      message.error('加载分类失败，请稍后重试');

    }

  };



  const loadDocuments = async (kbId: string, categoryId?: string) => {

    try {

      const data = await knowledgeApi.listDocuments(kbId, categoryId);

      setDocuments(data);

    } catch (e) {

      console.warn('加载文档失败', e);
      message.error('加载文档列表失败，请稍后重试');

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



  const handleCreateCategory = async () => {

    if (!currentKb) return;

    try {

      const values = await categoryForm.validateFields();

      await knowledgeApi.createCategory(currentKb.kb_id, values);

      message.success('分类创建成功');

      setCategoryModalOpen(false);

      categoryForm.resetFields();

      const cats = await knowledgeApi.listCategories(currentKb.kb_id);

      setCategories(cats);

    } catch (error) {

      message.error(`创建分类失败: ${error}`);

    }

  };



  const handleSaveUpload = async () => {

    if (!currentKb) return;

    try {

      const values = uploadForm.getFieldsValue();

      // 如果标题为空且上传了文件，自动使用文件名作为标题
      let title = values.title;
      if (!title && uploadFile) {
        title = uploadFile.name.replace(/\.[^.]+$/, ''); // 去除扩展名
      }

      // 按 tab 类型验证必填字段
      if (uploadTab === 'file' && !uploadFile) {
        message.warning('请选择要上传的文件');
        return;
      }
      if ((uploadTab === 'online_doc' || uploadTab === 'web') && !values.web_url) {
        message.warning('请输入文档链接');
        return;
      }
      if (uploadTab === 'text' && !values.content?.trim()) {
        message.warning('请输入文本内容');
        return;
      }
      if (!title && uploadTab !== 'file') {
        message.warning('请输入文档标题');
        return;
      }

      const docCategoryId: string | undefined = values.category_id || selectedCategory || undefined;

      const data: DocumentUploadData = {

        kb_id: currentKb.kb_id,

        category_id: docCategoryId,

        content_type: uploadTab === 'web' ? 'web_crawl' : uploadTab,

        title: title || '',

        content: values.content,

        web_url: values.web_url,

        file: uploadFile || undefined,

      };

      await knowledgeApi.uploadDocument(data);

      message.success('上传成功');

      setUploadModalOpen(false);

      loadDocuments(currentKb.kb_id, docCategoryId);

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

  const handleViewGraph = async (kbId: string) => {
    setGraphModalOpen(true);
    setGraphLoading(true);
    setGraphData(null);
    try {
      const data = await knowledgeApi.getKbGraph(kbId);
      setGraphData(data);
      // 延迟渲染，确保 Modal DOM 就绪
      setTimeout(() => renderGraph(data), 100);
    } catch {
      message.error('加载图谱数据失败');
    } finally {
      setGraphLoading(false);
    }
  };

  const renderGraph = useCallback((data: KbGraphData) => {
    if (!graphChartRef.current) return;
    // 清理旧实例
    if (echartsInstanceRef.current) {
      echartsInstanceRef.current.dispose();
    }
    const echarts = (window as any).echarts;
    if (!echarts) {
      // 动态加载 echarts
      import('echarts').then((ec) => {
        (window as any).echarts = ec;
        doRender(ec, data);
      });
      return;
    }
    doRender(echarts, data);
  }, []);

  const doRender = (echarts: any, data: KbGraphData) => {
    if (!graphChartRef.current) return;
    const chart = echarts.init(graphChartRef.current);
    echartsInstanceRef.current = chart;

    // 按类型分配颜色
    const typeColors: Record<string, string> = {};
    const palette = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc'];
    let colorIdx = 0;

    const categories = [...new Set(data.nodes.map(n => n.type))];
    categories.forEach(cat => {
      typeColors[cat] = palette[colorIdx % palette.length];
      colorIdx++;
    });

    const nodes = data.nodes.map(node => ({
      id: node.id,
      name: node.name,
      symbolSize: 40,
      category: categories.indexOf(node.type),
      itemStyle: { color: typeColors[node.type] || '#5470c6' },
      label: { show: true, fontSize: 12 },
    }));

    const links = data.edges.map(edge => ({
      source: edge.source,
      target: edge.target,
      label: { show: true, formatter: edge.type, fontSize: 10, color: '#666' },
      lineStyle: { color: '#aaa', curveness: 0.1 },
    }));

    chart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const node = data.nodes.find(n => n.id === params.data.id);
            return `<b>${node?.name || params.data.name}</b><br/>类型: ${node?.type || '—'}`;
          }
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}<br/>${params.data.label?.formatter || ''}`;
          }
          return '';
        },
      },
      legend: {
        data: categories,
        orient: 'vertical',
        left: 10,
        top: 10,
      },
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes,
        links: links,
        categories: categories.map(c => ({ name: c })),
        roam: true,
        draggable: true,
        force: {
          repulsion: 300,
          edgeLength: [80, 200],
          gravity: 0.1,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
        label: { show: true, position: 'bottom', fontSize: 11 },
        lineStyle: { opacity: 0.7, width: 1.5 },
      }],
    });

    // 响应窗口变化
    const resizeHandler = () => chart.resize();
    window.addEventListener('resize', resizeHandler);
    chart.on('disposed', () => window.removeEventListener('resize', resizeHandler));
  };



  const handleViewDoc = async (doc: KnowledgeDocument) => {

    setCurrentDoc(doc);

    setDocDrawerOpen(true);

    // 获取最新的 presigned URL（可能已过期或需要刷新）
    if (doc.file_url) {
      try {
        const kbId = doc.kb_id || currentKb?.kb_id;
        if (!kbId) return;
        const freshDoc = await knowledgeApi.getDocument(kbId, doc.doc_id);
        if (freshDoc?.presigned_url) {
          setCurrentDoc(prev => prev && prev.doc_id === doc.doc_id
            ? { ...prev, presigned_url: freshDoc.presigned_url }
            : prev);
        }
      } catch {
        // 静默降级：使用列表返回的 presigned_url
      }
    }

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

        {!loading && filteredKbs.length === 0 ? (

          <EmptyState

            icon={<DatabaseOutlined />}

            title="暂无知识库"

            description="创建知识库来管理文档和构建知识图谱，或加载示例数据快速体验"

            actionLabel="新建知识库"

            onAction={handleCreateKb}

            showSampleData

            onLoadSampleData={async () => {

              if (!currentWorkspace) { message.warning('请先选择工作空间'); return; }

              try {

                const { api } = await import('@/modules/shared/services/api');

                await api.generateSampleData(currentWorkspace);

                message.success('示例数据已加载');

                loadKnowledgeBases();

              } catch (e) { message.error('加载示例数据失败'); }

            }}

          />

        ) : (

          <AdvancedTable

            dataSource={filteredKbs}

            columns={columns}

            rowKey="kb_id"

            loading={loading}

            pagination={{ pageSize: 10 }}

          />

        )}



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

              <div>{record.title || record.file_url?.split('/').pop() || '未命名文档'}</div>

              {record.keywords?.length > 0 && (

                <Space size={4} style={{ marginTop: 4 }} wrap>

                  {[...new Set(record.keywords)].slice(0, 3).map((k, idx) => <KeywordTag key={`${k}-${idx}`} keyword={k} maxLen={16} />)}
                  {record.keywords.length > 3 && <Tag>+{record.keywords.length - 3}</Tag>}

                </Space>

              )}

            </div>

          </div>

        ),

      },

      {

        title: '类型',

        dataIndex: 'content_type',

        width: 130,

        render: (t: string, record: KnowledgeDocument) => {

          const typeMap: Record<string, string> = {

            file: '文件', online_doc: '在线文档', text: '纯文本', web_crawl: '网页抓取',

          };

          return (
            <Space size={4}>
              <Tag>{typeMap[t] || t}</Tag>
              {record.file_type && <Tag color="blue" style={{ fontSize: 11 }}>{friendlyFileType(record.file_type)}</Tag>}
            </Space>
          );

        },

      },

      {

        title: '状态',

        dataIndex: 'status',

        width: 120,

        render: (_status: string, record: KnowledgeDocument) => {

          const st = deriveDocStatus(record);

          return <Tag color={st.color}>{st.label}</Tag>;

        },

      },

      {

        title: '图谱',

        dataIndex: 'graph_built',

        width: 150,

        render: (built: boolean, record: KnowledgeDocument) => (

          built ? (
            <Space>
              <Tag color="success">已构建</Tag>
              <Tooltip title="查看图谱">
                <Button size="small" type="link" icon={<ApartmentOutlined />} onClick={() => handleViewGraph(record.kb_id)}>
                  查看
                </Button>
              </Tooltip>
            </Space>
          ) :

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

            <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => { categoryForm.resetFields(); setCategoryModalOpen(true); }}>新建</Button>

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

          <AdvancedTable

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

            <Form.Item name="title" label="标题" rules={[{ required: uploadTab !== 'file', message: '请输入文档标题' }]}>

              <Input placeholder={uploadTab === 'file' ? '留空则自动使用文件名' : '请输入文档标题'} />

            </Form.Item>



            <Tabs activeKey={uploadTab} onChange={k => setUploadTab(k as any)} items={[

              {

                key: 'file',

                label: '文件',

                children: (

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

                ),

              },

              {

                key: 'online_doc',

                label: '在线文档',

                children: (

                  <Form.Item name="web_url" label="文档链接">

                    <Input placeholder="请输入在线文档链接" prefix={<LinkOutlined />} />

                  </Form.Item>

                ),

              },

              {

                key: 'text',

                label: '纯文本',

                children: (

                  <Form.Item name="content" label="内容">

                    <TextArea placeholder="请输入文本内容" rows={6} />

                  </Form.Item>

                ),

              },

              {

                key: 'web',

                label: '网页抓取',

                children: (

                  <>

                    <Form.Item name="web_url" label="网页URL">

                      <Input placeholder="请输入要抓取的网页URL" prefix={<GlobalOutlined />} />

                    </Form.Item>

                    <Alert

                      type="info"

                      showIcon

                      title="系统将自动抓取网页内容并提取结构化知识"

                      style={{ marginTop: 8 }}

                    />

                  </>

                ),

              },

            ]} />



            <Form.Item name="category_id" label="分类">

              <Select placeholder="请选择分类（可选）" allowClear>

                {categories.map(cat => (

                  <Select.Option key={cat.category_id} value={cat.category_id}>{cat.name}</Select.Option>

                ))}

              </Select>

            </Form.Item>

          </Form>

        </Modal>



        {/* 新建分类 */}

        <Modal

          title="新建分类"

          open={categoryModalOpen}

          onOk={handleCreateCategory}

          onCancel={() => { setCategoryModalOpen(false); categoryForm.resetFields(); }}

          okText="创建"

          cancelText="取消"

        >

          <Form form={categoryForm} layout="vertical">

            <Form.Item name="name" label="分类名称" rules={[{ required: true, message: '请输入分类名称' }]}>

              <Input placeholder="输入分类名称" />

            </Form.Item>

            <Form.Item name="parent_id" label="父级分类">

              <Select placeholder="无（顶级分类）" allowClear>

                {categories.map(c => (

                  <Select.Option key={c.category_id} value={c.category_id}>{c.name}</Select.Option>

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

          size="large"

        >

          {currentDoc && (

            <div>

              <Descriptions column={1}>

                <Descriptions.Item label="标题">{currentDoc.title || '未命名文档'}</Descriptions.Item>

                <Descriptions.Item label="类型">

                  <Tag>{currentDoc.content_type}</Tag>
                  {currentDoc.file_type && <Tag color="blue">{friendlyFileType(currentDoc.file_type)}</Tag>}

                </Descriptions.Item>

                <Descriptions.Item label="处理状态">
                  {(() => {
                    const st = deriveDocStatus(currentDoc);
                    return <Tag color={st.color}>{st.label}</Tag>;
                  })()}
                </Descriptions.Item>

                {currentDoc.file_size != null && (
                  <Descriptions.Item label="文件大小">
                    {currentDoc.file_size < 1024 * 1024
                      ? `${(currentDoc.file_size / 1024).toFixed(1)} KB`
                      : `${(currentDoc.file_size / 1024 / 1024).toFixed(1)} MB`}
                  </Descriptions.Item>
                )}

                {currentDoc.file_url && (
                  <Descriptions.Item label="存储路径">
                    <Tooltip title={currentDoc.file_url}>
                      <Text copyable style={{ maxWidth: 400, wordBreak: 'break-all' }}>
                        {currentDoc.file_url.startsWith('/') ? currentDoc.file_url : `minio://odap-documents/${currentDoc.file_url}`}
                      </Text>
                    </Tooltip>
                    {currentDoc.presigned_url && (
                      <Button size="small" type="link" href={currentDoc.presigned_url} target="_blank" rel="noreferrer">
                        下载
                      </Button>
                    )}
                  </Descriptions.Item>
                )}

                <Descriptions.Item label="关键词">

                  <Space wrap>

                    {([...new Set(currentDoc.keywords ?? [])]).map((k, idx) => <KeywordTag key={`${k}-${idx}`} keyword={k} maxLen={40} />)}
                    {(!currentDoc.keywords?.length) && <Text type="secondary">暂无关键词</Text>}

                  </Space>

                </Descriptions.Item>

                <Descriptions.Item label="摘要">{currentDoc.summary || '—'}</Descriptions.Item>

                <Descriptions.Item label="图谱状态">

                  <Space>
                    {currentDoc.graph_built ? <Tag color="success">已构建</Tag> : <Tag>未构建</Tag>}
                    {currentDoc.graph_built && (
                      <Button size="small" type="link" icon={<ApartmentOutlined />} onClick={() => handleViewGraph(currentDoc.kb_id)}>
                        查看图谱
                      </Button>
                    )}
                  </Space>

                </Descriptions.Item>

              </Descriptions>



              {/* 文档预览区域 */}
              {currentDoc.file_url ? (
                <div style={{ marginTop: 24 }}>
                  <Title level={5}>文档预览</Title>
                  <DocumentViewer
                    fileUrl={currentDoc.file_url}
                    presignedUrl={currentDoc.presigned_url}
                    filename={currentDoc.title || currentDoc.file_url.split('/').pop()}
                    fileType={currentDoc.file_type}
                    height={500}
                  />
                </div>
              ) : currentDoc.content ? (
                <div style={{ marginTop: 24 }}>

                  <Title level={5}>内容预览</Title>

                  <div style={{

                    padding: 16, background: '#f5f7fa', borderRadius: 8,

                    maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap',

                  }}>

                    {currentDoc.content}

                  </div>

                </div>
              ) : null}



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

      {/* 知识图谱可视化弹窗 */}
      <Modal
        title={
          <Space>
            <ApartmentOutlined />
            <span>知识图谱 — {currentKb?.name || ''}</span>
          </Space>
        }
        open={graphModalOpen}
        onCancel={() => {
          setGraphModalOpen(false);
          if (echartsInstanceRef.current) {
            echartsInstanceRef.current.dispose();
            echartsInstanceRef.current = null;
          }
        }}
        footer={
          graphData ? (
            <Space>
              <Tag>实体: {graphData.statistics.total_entities}</Tag>
              <Tag>关系: {graphData.statistics.total_relationships}</Tag>
              <Button onClick={() => { setGraphModalOpen(false); if (echartsInstanceRef.current) { echartsInstanceRef.current.dispose(); echartsInstanceRef.current = null; } }}>
                关闭
              </Button>
            </Space>
          ) : null
        }
        width={900}
        destroyOnHidden
      >
        {graphLoading ? (
          <div style={{ height: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin description="加载图谱数据..." />
          </div>
        ) : graphData && graphData.nodes.length > 0 ? (
          <>
            <div ref={graphChartRef} style={{ width: '100%', height: 500 }} />
            <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
              提示：鼠标拖拽移动画布，滚轮缩放，点击节点高亮关联关系
            </div>
          </>
        ) : (
          <Empty
            description={graphData?.error ? `图谱加载失败: ${graphData.error}` : '暂无图谱数据，请先为文档构建图谱'}
            style={{ height: 300, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}
          />
        )}
      </Modal>

      </div>

    );

  }



  return null;

}

