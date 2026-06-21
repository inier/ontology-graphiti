import React, { useState } from 'react';
import { Input, Button, Select, Typography, Space, Alert, Spin, Tag, Divider } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { SearchOutlined, LinkOutlined, GlobalOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source_domain: string;
  published_date: string;
}

const WebSearchPanel: React.FC = () => {
  const { t } = useI18n('ingest');
  const [query, setQuery] = useState('');
  const [maxResults, setMaxResults] = useState(5);
  const [searchDepth, setSearchDepth] = useState('basic');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [engineUsed, setEngineUsed] = useState('');
  const [error, setError] = useState('');

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.webSearch(query, maxResults, searchDepth);
      setResults(res.results || []);
      setTotalCount(res.total_count || 0);
      setEngineUsed(res.engine_used || 'unknown');
    } catch (e: any) {
      setError(e.message || t('webSearch.searchFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '0 4px' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Input
          placeholder={t('webSearch.searchPlaceholder')}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onPressEnter={handleSearch}
          prefix={<SearchOutlined />}
          size="large"
        />
        <Space>
          <span>{t('webSearch.resultCount')}</span>
          <Select value={maxResults} onChange={setMaxResults} style={{ width: 80 }} size="small"
            options={[1, 3, 5, 10, 20].map(n => ({ value: n, label: n }))} />
          <span>{t('webSearch.depth')}</span>
          <Select value={searchDepth} onChange={setSearchDepth} style={{ width: 100 }} size="small"
            options={[
              { value: 'basic', label: t('webSearch.depthBasic') },
              { value: 'advanced', label: t('webSearch.depthAdvanced') },
            ]} />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch} loading={loading}>
            {t('webSearch.searchBtn')}
          </Button>
        </Space>

        {error && <Alert type="error" message={error} showIcon closable onClose={() => setError('')} />}

        {loading && <Spin spinning description={t('webSearch.searching')} style={{ width: '100%' }}><div style={{ minHeight: 40 }} /></Spin>}

        {results.length > 0 && (
          <div>
            <Text type="secondary">
              {t('webSearch.resultSummary', { count: totalCount, engine: engineUsed })}
            </Text>
            <Divider style={{ margin: '8px 0' }} />
            {results.map((r, i) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }} hoverable>
                <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                  <Text strong>
                    {r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title || r.url}</a> : r.title}
                  </Text>
                  {r.snippet && <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0 }}>{r.snippet}</Paragraph>}
                  <Space size={4}>
                    {r.source_domain && <Tag icon={<GlobalOutlined />}>{r.source_domain}</Tag>}
                    {r.published_date && <Text type="secondary" style={{ fontSize: 12 }}>{r.published_date}</Text>}
                  </Space>
                </Space>
              </Card>
            ))}
          </div>
        )}
      </Space>
    </div>
  );
};

export default WebSearchPanel;
