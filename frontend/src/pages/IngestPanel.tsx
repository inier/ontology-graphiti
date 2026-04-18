import { useState } from 'react';
import { Card, Tabs, Input, Button, Space, message, Spin, List, Tag } from 'antd';
import { api } from '../services/api';
import { ReloadOutlined } from '@ant-design/icons';

const { TextArea } = Input;

export function IngestPanel() {
  const [activeTab, setActiveTab] = useState('text');
  const [textInput, setTextInput] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<{ type: string; content: string; time: string }[]>([]);

  const handleIngestText = async () => {
    if (!textInput.trim()) {
      message.warning('请输入文本内容');
      return;
    }
    setLoading(true);
    try {
      const result = await api.ingestText(textInput);
      setHistory((prev) => [
        { type: 'text', content: textInput.substring(0, 50) + '...', time: new Date().toLocaleTimeString() },
        ...prev,
      ]);
      message.success(`任务已提交: ${result.task_id}`);
      setTextInput('');
    } catch (error) {
      message.error('提交失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestNews = async () => {
    if (!urlInput.trim()) {
      message.warning('请输入新闻 URL');
      return;
    }
    setLoading(true);
    try {
      const result = await api.ingestNews(urlInput);
      setHistory((prev) => [
        { type: 'news', content: urlInput, time: new Date().toLocaleTimeString() },
        ...prev,
      ]);
      message.success(`任务已提交: ${result.task_id}`);
      setUrlInput('');
    } catch (error) {
      message.error('提交失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestRandom = async () => {
    setLoading(true);
    try {
      const result = await api.ingestRandom();
      setHistory((prev) => [
        { type: 'random', content: `生成 ${result.doc_count} 个文档`, time: new Date().toLocaleTimeString() },
        ...prev,
      ]);
      message.success(`随机数据已生成，版本: ${result.versions.join(', ')}`);
    } catch (error) {
      message.error('提交失败');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'text',
      label: '文本输入',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <TextArea
            rows={6}
            placeholder="输入要分析的文本内容..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
          />
          <Button type="primary" onClick={handleIngestText} loading={loading}>
            提交文本
          </Button>
        </Space>
      ),
    },
    {
      key: 'news',
      label: '新闻采集',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Input placeholder="输入新闻 URL" value={urlInput} onChange={(e) => setUrlInput(e.target.value)} />
          <Button type="primary" onClick={handleIngestNews} loading={loading}>
            采集新闻
          </Button>
        </Space>
      ),
    },
    {
      key: 'random',
      label: '随机生成',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <p>生成随机模拟数据用于测试</p>
          <Button type="primary" onClick={handleIngestRandom} loading={loading}>
            生成随机数据
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="数据摄入">
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        </Card>

        <Card
          title="摄入历史"
          extra={
            <Button icon={<ReloadOutlined />} onClick={() => setHistory([])}>
              清空
            </Button>
          }
        >
          {loading && <Spin description="处理中..." style={{ width: '100%', margin: 20 }} />}
          <List
            dataSource={history}
            renderItem={(item) => (
              <List.Item>
                <Space>
                  <Tag color={item.type === 'text' ? 'blue' : item.type === 'news' ? 'green' : 'orange'}>
                    {item.type}
                  </Tag>
                  <span>{item.content}</span>
                  <Tag>{item.time}</Tag>
                </Space>
              </List.Item>
            )}
            locale={{ emptyText: '暂无摄入记录' }}
          />
        </Card>
      </Space>
    </div>
  );
}
