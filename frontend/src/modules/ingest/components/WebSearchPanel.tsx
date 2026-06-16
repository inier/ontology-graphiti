import React, { useState } from 'react';
import { Input, Button, Select, Card, Typography, Space, Alert, Spin, Tag, Divider } from 'antd';
import { SearchOutlined, LinkOutlined, GlobalOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared';

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
      setError(e.message || '搜索失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '0 4px' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Input
          placeholder="输入搜索关键词..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onPressEnter={handleSearch}
          prefix={<SearchOutlined />}
          size="large"
        />
        <Space>
          <span>结果数:</span>
          <Select value={maxResults} onChange={setMaxResults} style={{ width: 80 }} size="small"
            options={[1, 3, 5, 10, 20].map(n => ({ value: n, label: n }))} />
          <span>深度:</span>
          <Select value={searchDepth} onChange={setSearchDepth} style={{ width: 100 }} size="small"
            options={[{ value: 'basic', label: '基础' }, { value: 'advanced', label: '深度' }]} />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch} loading={loading}>
            搜索
          </Button>
        </Space>

        {error && <Alert type="error" message={error} showIcon closable onClose={() => setError('')} />}

        {loading && <Spin spinning description="搜索中..." style={{ width: '100%' }}><div style={{ minHeight: 40 }} /></Spin>}

        {results.length > 0 && (
          <div>
            <Text type="secondary">
              找到 {totalCount} 条结果 (引擎: {engineUsed})
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
