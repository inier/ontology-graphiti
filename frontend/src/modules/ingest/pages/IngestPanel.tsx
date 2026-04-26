import { useState, useEffect } from 'react';
import { Card, Tabs, Button, Space, Input, Upload, message, Table, Tag, Descriptions, Spin, Alert } from 'antd';
import { UploadOutlined, SyncOutlined, HistoryOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import { useScenario, PageHeader } from '../../shared';
const { Dragger } = Upload;
const { TextArea } = Input;

interface IngestRecord {
  id: string;
  source: string;
  status: string;
  record_count: number;
  processed_count: number;
  failed_count: number;
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
  builds?: Array<{
    build_id: string;
    status: string;
    document_id: string;
    version_info?: {
      version_id: string;
      commit_message: string;
    };
  }>;
}

interface BuildRecord {
  build_id: string;
  status: string;
  document_id: string;
  version_info?: {
    version_id: string;
    commit_message: string;
  };
  ingest_id: string;
  ingest_source: string;
  ingest_time: string;
}

export function IngestPanel() {
  const { currentScenario } = useScenario();
  const [activeTab, setActiveTab] = useState('text');

  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [jsonData, setJsonData] = useState('');
  const [nlDescription, setNlDescription] = useState('');
  const [manualData, setManualData] = useState({
    title: '',
    description: '',
  });

  const [loading, setLoading] = useState(false);
  const [ingestHistory, setIngestHistory] = useState<IngestRecord[]>([]);
  const [buildHistory, setBuildHistory] = useState<BuildRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    
    const loadHistory = async () => {
      if (cancelled) return;
      setLoadingHistory(true);
      try {
        const [ingests, builds] = await Promise.all([
          api.getIngestHistory(20).catch(err => {
            if (err.name === 'AbortError' || cancelled) return [];
            throw err;
          }),
          api.getBuildHistory(20).catch(err => {
            if (err.name === 'AbortError' || cancelled) return [];
            throw err;
          }),
        ]);
        if (!cancelled) {
          setIngestHistory(ingests);
          setBuildHistory(builds);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('加载历史记录失败:', error);
        }
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
        }
      }
    };
    
    loadHistory();
    
    return () => {
      cancelled = true;
    };
  }, []);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const [ingests, builds] = await Promise.all([
        api.getIngestHistory(20),
        api.getBuildHistory(20),
      ]);
      setIngestHistory(ingests);
      setBuildHistory(builds);
    } catch (error) {
      console.error('加载历史记录失败:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleIngestText = async () => {
    if (!text) {
      message.warning('请输入文本内容');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'manual',
        data: text,
        scenario_id: currentScenario,
      });
      message.success(`文本摄入成功，摄入ID: ${result.ingest_id}`);
      setText('');
      await loadHistory();
    } catch (error) {
      message.error('文本摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestNews = async () => {
    if (!url) {
      message.warning('请输入新闻URL');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'news',
        data: url,
        scenario_id: currentScenario,
      });
      message.success(`新闻摄入成功，摄入ID: ${result.ingest_id}`);
      setUrl('');
      await loadHistory();
    } catch (error) {
      message.error('新闻摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestJson = async () => {
    if (!jsonData) {
      message.warning('请输入JSON数据');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'json',
        data: jsonData,
        scenario_id: currentScenario,
      });
      message.success(`JSON摄入成功，摄入ID: ${result.ingest_id}`);
      setJsonData('');
      await loadHistory();
    } catch (error) {
      message.error('JSON摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestNaturalLanguage = async () => {
    if (!nlDescription) {
      message.warning('请输入自然语言描述');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'natural_language',
        data: nlDescription,
        scenario_id: currentScenario,
      });
      message.success(`自然语言摄入成功，摄入ID: ${result.ingest_id}`);
      setNlDescription('');
      await loadHistory();
    } catch (error) {
      message.error('自然语言摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestRandom = async () => {
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'random',
        data: { parties: ['蓝方', '红方'] },
        scenario_id: currentScenario,
      });
      message.success(`随机事件生成成功，摄入ID: ${result.ingest_id}`);
      await loadHistory();
    } catch (error) {
      message.error('随机事件生成失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestManual = async () => {
    if (!manualData.title || !manualData.description) {
      message.warning('请输入标题和描述');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'manual',
        data: manualData,
        scenario_id: currentScenario,
      });
      message.success(`手动录入成功，摄入ID: ${result.ingest_id}`);
      setManualData({ title: '', description: '' });
      await loadHistory();
    } catch (error) {
      message.error('手动录入失败');
    } finally {
      setLoading(false);
    }
  };

  const uploadProps = {
    name: 'file',
    multiple: false,
    customRequest: async (options: any) => {
      const { file, onSuccess, onError } = options;
      try {
        setUploadLoading(true);
        await api.ingestFile(file, currentScenario);
        onSuccess();
        message.success(`${file.name} 文件上传成功`);
        await loadHistory();
      } catch (error) {
        onError();
        message.error(`${file.name} 文件上传失败`);
      } finally {
        setUploadLoading(false);
      }
    },
    onChange(info: any) {
      const { status } = info.file;
      if (status === 'done') {
        message.success(`${info.file.name} 文件上传成功`);
      } else if (status === 'error') {
        message.error(`${info.file.name} 文件上传失败`);
      }
    },
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      completed: { color: 'success', text: '已完成' },
      processing: { color: 'processing', text: '处理中' },
      pending: { color: 'default', text: '等待中' },
      failed: { color: 'error', text: '失败' },
    };
    const map = statusMap[status] || { color: 'default', text: status };
    return <Tag color={map.color}>{map.text}</Tag>;
  };

  const ingestColumns = [
    {
      title: '时间',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (source: string) => {
        const sourceMap: Record<string, string> = {
          news: '新闻',
          manual: '手动',
          json: 'JSON',
          natural_language: '自然语言',
          random: '随机',
        };
        return sourceMap[source] || source;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '记录数',
      dataIndex: 'record_count',
      key: 'record_count',
    },
    {
      title: '构建状态',
      key: 'build_status',
      render: (_: unknown, record: IngestRecord) => {
        if (record.builds && record.builds.length > 0) {
          return record.builds.map((build, idx) => (
            <Tag key={idx} icon={build.status === 'completed' ? <CheckCircleOutlined /> : <SyncOutlined />}>
              {build.version_info?.version_id || build.build_id}
            </Tag>
          ));
        }
        return '-';
      },
    },
  ];

  const buildColumns = [
    {
      title: '构建ID',
      dataIndex: 'build_id',
      key: 'build_id',
      render: (id: string) => <code style={{ fontSize: 12 }}>{id.substring(0, 12)}...</code>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '版本',
      key: 'version',
      render: (_: unknown, record: BuildRecord) => {
        if (record.version_info) {
          return (
            <span>
              <code>{record.version_info.version_id}</code>
              <br />
              <small>{record.version_info.commit_message}</small>
            </span>
          );
        }
        return '-';
      },
    },
    {
      title: '摄入来源',
      dataIndex: 'ingest_source',
      key: 'ingest_source',
    },
    {
      title: '构建时间',
      dataIndex: 'ingest_time',
      key: 'ingest_time',
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
  ];

  const tabItems = [
    {
      key: 'text',
      label: '文本摄入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={8}
            placeholder="请输入要摄入的文本内容，支持多行输入"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestText} loading={loading}>
              开始摄入
            </Button>
            <Button onClick={() => setText('')}>
              清空
            </Button>
          </Space>
          <Alert
            title="提示"
            description="文本摄入后会立即触发本体构建流程，自动提取实体和关系"
            type="info"
            showIcon
            style={{ marginTop: 16 }}
          />
        </Card>
      ),
    },
    {
      key: 'news',
      label: '新闻摄入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Input
            placeholder="请输入新闻URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ marginBottom: 16 }}
          />
          <Button type="primary" onClick={handleIngestNews} loading={loading}>
            开始摄入
          </Button>
          <Alert
            title="提示"
            description="支持两种模式：1) 直接输入新闻网页URL；2) 输入关键词进行检索"
            type="info"
            showIcon
            style={{ marginTop: 16 }}
          />
        </Card>
      ),
    },
    {
      key: 'json',
      label: 'JSON数据',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={10}
            placeholder="请输入JSON格式的本体数据"
            value={jsonData}
            onChange={(e) => setJsonData(e.target.value)}
            style={{ fontFamily: 'monospace' }}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestJson} loading={loading}>
              开始摄入
            </Button>
            <Button onClick={() => setJsonData('')}>
              清空
            </Button>
          </Space>
        </Card>
      ),
    },
    {
      key: 'natural_language',
      label: '自然语言',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={6}
            placeholder="用自然语言描述要构建的本体，例如：美军航母舰队在南海进行军事演习，与中国海军发生对峙"
            value={nlDescription}
            onChange={(e) => setNlDescription(e.target.value)}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestNaturalLanguage} loading={loading}>
              开始处理
            </Button>
            <Button onClick={() => setNlDescription('')}>
              清空
            </Button>
          </Space>
          <Alert
            title="提示"
            description="自然语言输入会自动解析实体、关系和事件，触发完整的本体构建流程"
            type="info"
            showIcon
            style={{ marginTop: 16 }}
          />
        </Card>
      ),
    },
    {
      key: 'manual',
      label: '手动录入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Input
            placeholder="标题"
            value={manualData.title}
            onChange={(e) => setManualData({ ...manualData, title: e.target.value })}
            style={{ marginBottom: 16 }}
          />
          <TextArea
            rows={4}
            placeholder="详细描述"
            value={manualData.description}
            onChange={(e) => setManualData({ ...manualData, description: e.target.value })}
            style={{ marginBottom: 16 }}
          />
          <Button type="primary" onClick={handleIngestManual} loading={loading}>
            开始录入
          </Button>
        </Card>
      ),
    },
    {
      key: 'random',
      label: '随机生成',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <p>随机生成测试数据，用于快速构建知识图谱</p>
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestRandom} loading={loading}>
              生成数据
            </Button>
          </Space>
        </Card>
      ),
    },
    {
      key: 'upload',
      label: '文件上传',
      children: (
        <div style={{ position: 'relative' }}>
          <Dragger {...uploadProps} disabled={uploadLoading}>
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持上传 JSON、CSV、TXT 等格式文件
            </p>
          </Dragger>
          {uploadLoading && (
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10
            }}>
              <Spin size="large" tip="文件上传中..." />
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <PageHeader title="数据摄入" />

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      <Card
        title="摄入历史"
        extra={<Button icon={<HistoryOutlined />} onClick={loadHistory} loading={loadingHistory}>刷新</Button>}
        style={{ marginTop: 16 }}
      >
        <Spin spinning={loadingHistory}>
          <Table
            columns={ingestColumns}
            dataSource={ingestHistory}
            rowKey="id"
            pagination={{ pageSize: 5 }}
            size="small"
          />
        </Spin>
      </Card>

      {buildHistory.length > 0 && (
        <Card title="构建历史" style={{ marginTop: 16 }}>
          <Spin spinning={loadingHistory}>
            <Table
              columns={buildColumns}
              dataSource={buildHistory}
              rowKey="build_id"
              pagination={{ pageSize: 5 }}
              size="small"
            />
          </Spin>
        </Card>
      )}

      {buildHistory.length > 0 && (
        <Card title="最新构建详情" style={{ marginTop: 16 }}>
          <Descriptions bordered column={2}>
            <Descriptions.Item label="构建ID">{buildHistory[0]?.build_id}</Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(buildHistory[0]?.status)}</Descriptions.Item>
            <Descriptions.Item label="版本ID">{buildHistory[0]?.version_info?.version_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="提交说明">{buildHistory[0]?.version_info?.commit_message || '-'}</Descriptions.Item>
            <Descriptions.Item label="摄入来源">{buildHistory[0]?.ingest_source}</Descriptions.Item>
            <Descriptions.Item label="构建时间">
              {buildHistory[0]?.ingest_time ? new Date(buildHistory[0].ingest_time).toLocaleString('zh-CN') : '-'}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  );
}