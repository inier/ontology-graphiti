import React, { useState, useEffect } from 'react';
import { Input, Button, Select, Typography, Space, Alert, Spin, Tag, Divider, Badge } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { RobotOutlined, LinkOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface LinkItem {
  text: string;
  href: string;
  link_type: string;
}

const WebCrawlPanel: React.FC = () => {
  const { t } = useI18n('ingest');
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
      setError(e.message || t('webCrawl.crawlFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '0 4px' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Input
          placeholder={t('webCrawl.urlPlaceholder')}
          value={url}
          onChange={e => setUrl(e.target.value)}
          onPressEnter={handleCrawl}
          prefix={<LinkOutlined />}
          size="large"
        />
        <Space wrap>
          <span>{t('webCrawl.format')}</span>
          <Select value={outputFormat} onChange={setOutputFormat} style={{ width: 130 }} size="small"
            options={[
              { value: 'markdown', label: 'Markdown' },
              { value: 'fit_markdown', label: t('webCrawl.fitMarkdown') },
              { value: 'html', label: 'HTML' },
              { value: 'text', label: t('webCrawl.plainText') },
            ]} />
          <span>{t('webCrawl.cssSelector')}</span>
          <Input placeholder={t('webCrawl.cssSelectorPlaceholder')} value={cssSelector} onChange={e => setCssSelector(e.target.value)}
            style={{ width: 150 }} size="small" />
          <span>{t('webCrawl.timeout')}</span>
          <Select value={timeout} onChange={setTimeout_} style={{ width: 80 }} size="small"
            options={[10, 30, 60, 120].map(n => ({ value: n, label: `${n}s` }))} />
          <Button type="primary" icon={<RobotOutlined />} onClick={handleCrawl} loading={loading}>
            {t('webCrawl.crawlBtn')}
          </Button>
        </Space>

        {health && (
          <Space>
            <Tag color={health.crawl4ai_available ? 'green' : 'default'}>
              Crawl4AI: {health.crawl4ai_available ? t('webCrawl.available') : t('webCrawl.unavailable')}
            </Tag>
            <Tag color={health.fallback_available ? 'green' : 'red'}>
              {t('webCrawl.fallback')} {health.fallback_available ? t('webCrawl.available') : t('webCrawl.unavailable')}
            </Tag>
          </Space>
        )}

        {error && <Alert type="error" title={error} showIcon closable onClose={() => setError('')} />}

        {loading && <Spin spinning description={t('webCrawl.crawling')} style={{ width: '100%' }}><div style={{ minHeight: 40 }} /></Spin>}

        {result && (
          <Card size="small" title={
            <Space>
              <Text strong>{result.title || url}</Text>
              <Tag color={result.crawl_method === 'crawl4ai' ? 'blue' : 'orange'}>
                {result.crawl_method === 'crawl4ai' ? t('webCrawl.jsRendered') : t('webCrawl.staticFallback')}
              </Tag>
              <Tag color={result.confidence === 'medium' ? 'green' : 'gold'}>
                {t('webCrawl.confidence')} {result.confidence === 'medium' ? t('webCrawl.confidenceMedium') : t('webCrawl.confidenceLow')}
              </Tag>
            </Space>
          }>
            <Space orientation="vertical" style={{ width: '100%' }} size="small">
              {result.sanitize_warnings && result.sanitize_warnings.length > 0 && (
                <Alert type="warning" title={`${t('webCrawl.safetyFilter')} ${result.sanitize_warnings.join('; ')}`} showIcon />
              )}
              <Paragraph>
                <Text type="secondary">{t('webCrawl.urlLabel')}</Text>
                <a href={result.url} target="_blank" rel="noopener noreferrer">{result.url}</a>
              </Paragraph>
              <Divider style={{ margin: '4px 0' }}>{t('webCrawl.content')}</Divider>
              <div style={{
                maxHeight: 400, overflow: 'auto', padding: 8,
                background: '#fafafa', borderRadius: 4, fontSize: 13,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {result.content || t('webCrawl.noContent')}
              </div>
              {result.links && result.links.length > 0 && (
                <>
                  <Divider style={{ margin: '4px 0' }}>{t('webCrawl.links', { count: result.links.length })}</Divider>
                  <div style={{ maxHeight: 150, overflow: 'auto' }}>
                    {result.links.slice(0, 20).map((link: LinkItem, i: number) => (
                      <div key={i} style={{ fontSize: 12, marginBottom: 2 }}>
                        <Tag style={{ fontSize: 11 }}>{link.link_type}</Tag>
                        {link.href ? <a href={link.href} target="_blank" rel="noopener noreferrer">{link.text || link.href}</a> : link.text}
                      </div>
                    ))}
                    {result.links.length > 20 && <Text type="secondary">{t('webCrawl.moreLinks', { count: result.links.length - 20 })}</Text>}
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
