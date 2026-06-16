import React, { useState, useEffect } from 'react';
import { Input, Button, Select, Card, Typography, Space, Alert, Spin, Tag, Divider, Badge } from 'antd';
import { RobotOutlined, LinkOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface LinkItem {
  text: string;
  href: string;
  link_type: string;
}

const WebCrawlPanel: React.FC = () => {
  const [url, setUrl] = useState('');
  const [outputFormat, setOutputFormat] = useState('markdown');
  const [cssSelector, setCssSelector] = useState('');
  const [timeout, setTimeout_] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    api.webCrawlHealth().then(setHealth).catch(() => {});
  }, []);

  const handleCrawl = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await api.webCrawl(url, outputFormat, cssSelector || undefined, timeout);
      setResult(res);
    } catch (e: any) {
      setError(e.message || '爬取失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '0 4px' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Input
          placeholder="输入要爬取的 URL (如 https://example.com)"
          value={url}
          onChange={e => setUrl(e.target.value)}
          onPressEnter={handleCrawl}
          prefix={<LinkOutlined />}
          size="large"
        />
        <Space wrap>
          <span>格式:</span>
          <Select value={outputFormat} onChange={setOutputFormat} style={{ width: 130 }} size="small"
            options={[
              { value: 'markdown', label: 'Markdown' },
              { value: 'fit_markdown', label: '精简 Markdown' },
              { value: 'html', label: 'HTML' },
              { value: 'text', label: '纯文本' },
            ]} />
          <span>CSS 选择器:</span>
          <Input placeholder="可选" value={cssSelector} onChange={e => setCssSelector(e.target.value)}
            style={{ width: 150 }} size="small" />
          <span>超时:</span>
          <Select value={timeout} onChange={setTimeout_} style={{ width: 80 }} size="small"
            options={[10, 30, 60, 120].map(n => ({ value: n, label: `${n}s` }))} />
          <Button type="primary" icon={<RobotOutlined />} onClick={handleCrawl} loading={loading}>
            爬取
          </Button>
        </Space>

        {health && (
          <Space>
            <Tag color={health.crawl4ai_available ? 'green' : 'default'}>
              Crawl4AI: {health.crawl4ai_available ? '可用' : '不可用'}
            </Tag>
            <Tag color={health.fallback_available ? 'green' : 'red'}>
              降级: {health.fallback_available ? '可用' : '不可用'}
            </Tag>
          </Space>
        )}

        {error && <Alert type="error" message={error} showIcon closable onClose={() => setError('')} />}

        {loading && <Spin spinning description="爬取中，请等待..." style={{ width: '100%' }}><div style={{ minHeight: 40 }} /></Spin>}

        {result && (
          <Card size="small" title={
            <Space>
              <Text strong>{result.title || url}</Text>
              <Tag color={result.crawl_method === 'crawl4ai' ? 'blue' : 'orange'}>
                {result.crawl_method === 'crawl4ai' ? 'JS 渲染' : '静态降级'}
              </Tag>
              <Tag color={result.confidence === 'medium' ? 'green' : 'gold'}>
                可信度: {result.confidence === 'medium' ? '中' : '低'}
              </Tag>
            </Space>
          }>
            <Space orientation="vertical" style={{ width: '100%' }} size="small">
              {result.sanitize_warnings && result.sanitize_warnings.length > 0 && (
                <Alert type="warning" message={`安全过滤: ${result.sanitize_warnings.join('; ')}`} showIcon />
              )}
              <Paragraph>
                <Text type="secondary">URL: </Text>
                <a href={result.url} target="_blank" rel="noopener noreferrer">{result.url}</a>
              </Paragraph>
              <Divider style={{ margin: '4px 0' }}>内容</Divider>
              <div style={{
                maxHeight: 400, overflow: 'auto', padding: 8,
                background: '#fafafa', borderRadius: 4, fontSize: 13,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {result.content || '(无内容)'}
              </div>
              {result.links && result.links.length > 0 && (
                <>
                  <Divider style={{ margin: '4px 0' }}>链接 ({result.links.length})</Divider>
                  <div style={{ maxHeight: 150, overflow: 'auto' }}>
                    {result.links.slice(0, 20).map((link: LinkItem, i: number) => (
                      <div key={i} style={{ fontSize: 12, marginBottom: 2 }}>
                        <Tag style={{ fontSize: 11 }}>{link.link_type}</Tag>
                        {link.href ? <a href={link.href} target="_blank" rel="noopener noreferrer">{link.text || link.href}</a> : link.text}
                      </div>
                    ))}
                    {result.links.length > 20 && <Text type="secondary">...还有 {result.links.length - 20} 条</Text>}
                  </div>
                </>
              )}
            </Space>
          </Card>
        )}
      </Space>
    </div>
  );
};

export default WebCrawlPanel;
