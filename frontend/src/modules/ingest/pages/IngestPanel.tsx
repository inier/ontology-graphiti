import { useState } from 'react';
import { Card, Tabs, Button, Space, Input, Select, Upload, message, Table, Spin } from 'antd';
import { UploadOutlined, EditOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import type { Scenario } from '../../shared/types';

const { TabPane } = Tabs;
const { Option } = Select;
const { Dragger } = Upload;

export function IngestPanel() {
  const [activeTab, setActiveTab] = useState('text');
  const [scenarioId, setScenarioId] = useState('');
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [manualData, setManualData] = useState({
    type: 'entity',
    name: '',
    properties: '',
  });
  const [scenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);

  const handleIngestText = async () => {
    if (!text) {
      message.warning('请输入文本');
      return;
    }
    try {
      setLoading(true);
      await api.ingestText(text, scenarioId);
      message.success('文本摄入成功');
      setText('');
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
      await api.ingestNews(url, scenarioId);
      message.success('新闻摄入成功');
      setUrl('');
    } catch (error) {
      message.error('新闻摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestRandom = async () => {
    try {
      setLoading(true);
      const result = await api.ingestRandom(scenarioId);
      message.success(`随机数据摄入成功，生成了 ${result.doc_count} 个文档`);
    } catch (error) {
      message.error('随机数据摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestManual = async () => {
    try {
      setLoading(true);
      const data = {
        type: manualData.type,
        name: manualData.name,
        properties: JSON.parse(manualData.properties || '{}'),
      };
      await api.ingestManual(data, scenarioId);
      message.success('手动数据摄入成功');
      setManualData({
        type: 'entity',
        name: '',
        properties: '',
      });
    } catch (error) {
      message.error('手动数据摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const [uploadLoading, setUploadLoading] = useState(false);

  const uploadProps = {
    name: 'file',
    multiple: false,
    customRequest: async (options: any) => {
      const { file, onSuccess, onError } = options;
      try {
        setUploadLoading(true);
        await api.ingestFile(file, scenarioId);
        onSuccess();
        message.success(`${file.name} 文件上传成功`);
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

  return (
    <Card title="数据摄入" style={{ padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <Select
          placeholder="选择场景"
          style={{ width: 300, marginRight: 16 }}
          value={scenarioId}
          onChange={setScenarioId}
          options={scenarios.map(s => ({ value: s.scenario_id, label: s.name }))}
        />
        <Button type="primary" onClick={() => console.log('创建场景')}>
          创建场景
        </Button>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab="文本摄入" key="text">
          <Card style={{ marginBottom: 16 }}>
            <Input.TextArea
              rows={8}
              placeholder="请输入要摄入的文本内容"
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
          </Card>
        </TabPane>

        <TabPane tab="新闻摄入" key="news">
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
          </Card>
        </TabPane>

        <TabPane tab="文件上传" key="upload">
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
        </TabPane>

        <TabPane tab="手动录入" key="manual">
          <Card style={{ marginBottom: 16 }}>
            <Select
              style={{ width: 150, marginBottom: 16 }}
              value={manualData.type}
              onChange={(value) => setManualData({ ...manualData, type: value })}
            >
              <Option value="entity">实体</Option>
              <Option value="relation">关系</Option>
              <Option value="event">事件</Option>
            </Select>
            <Input
              placeholder="名称"
              value={manualData.name}
              onChange={(e) => setManualData({ ...manualData, name: e.target.value })}
              style={{ marginBottom: 16 }}
            />
            <Input.TextArea
              placeholder="属性 (JSON格式)"
              value={manualData.properties}
              onChange={(e) => setManualData({ ...manualData, properties: e.target.value })}
              rows={4}
              style={{ marginBottom: 16 }}
            />
            <Button type="primary" onClick={handleIngestManual} loading={loading}>
              开始摄入
            </Button>
          </Card>
        </TabPane>

        <TabPane tab="随机生成" key="random">
          <Card style={{ marginBottom: 16 }}>
            <p>随机生成测试数据，用于快速构建知识图谱</p>
            <Space style={{ marginTop: 16 }}>
              <Button type="primary" onClick={handleIngestRandom} loading={loading}>
                生成数据
              </Button>
            </Space>
          </Card>
        </TabPane>
      </Tabs>

      <Card title="摄入历史" style={{ marginTop: 16 }}>
        <Table
          columns={[
            {
              title: '时间',
              dataIndex: 'time',
              key: 'time',
            },
            {
              title: '类型',
              dataIndex: 'type',
              key: 'type',
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
            },
            {
              title: '操作',
              key: 'action',
              render: () => (
                <Space size="small">
                  <Button size="small" type="link" icon={<EditOutlined />}>编辑</Button>
                  <Button size="small" danger type="link">删除</Button>
                </Space>
              ),
            },
          ]}
          dataSource={[]}
          pagination={{ pageSize: 5 }}
        />
      </Card>
    </Card>
  );
}