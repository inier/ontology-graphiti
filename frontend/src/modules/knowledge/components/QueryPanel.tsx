import { useState } from 'react';
import { Select, Input, Button, Table, Card, Space, Typography, Tabs, Tag, Empty, Spin, message } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';

const { Text } = Typography;
const { TextArea } = Input;

type QuerySource = 'schema' | 'entity' | 'topo' | 'temporal';

interface QueryResult {
  results: Record<string, unknown>[];
  total: number;
  source: string;
  query: string;
  workspace_id: string;
}

interface QueryPanelProps {
  workspaceId: string;
}

const SOURCE_OPTIONS: { value: QuerySource; label: string }[] = [
  { value: 'schema', label: 'Schema' },
  { value: 'entity', label: 'Entity' },
  { value: 'topo', label: 'Topology' },
  { value: 'temporal', label: 'Temporal' },
];

export default function QueryPanel({ workspaceId }: QueryPanelProps) {
  const [source, setSource] = useState<QuerySource>('schema');
  const [queryText, setQueryText] = useState('');
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('text');

  const handleQuery = async () => {
    if (!queryText.trim()) {
      message.warning('Please enter a query');
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.post<QueryResult>('/api/query', {
        query: queryText,
        workspace_id: workspaceId,
        limit: 20,
      });
      setResults(data.results || []);
      setTotal(data.total || 0);
    } catch (e) {
      message.error(`Query failed: ${(e as Error).message}`);
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!queryText.trim()) {
      message.warning('Please enter a query');
      return;
    }
    try {
      const data = await apiClient.post<{ valid: boolean; errors?: string[] }>('/api/query/validate', {
        query: queryText,
      });
      if (data.valid) {
        message.success('Query is valid');
      } else {
        message.error(`Invalid query: ${data.errors?.join(', ') || 'unknown error'}`);
      }
    } catch (e) {
      message.error(`Validation failed: ${(e as Error).message}`);
    }
  };

  const handleExplain = async () => {
    if (!queryText.trim()) {
      message.warning('Please enter a query');
      return;
    }
    try {
      const data = await apiClient.post<Record<string, unknown>>('/api/query/explain', undefined, {
        headers: { 'Content-Type': 'application/json' },
      });
      message.info(`Query plan: ${JSON.stringify(data)}`);
    } catch (e) {
      message.error(`Explain failed: ${(e as Error).message}`);
    }
  };

  const columns = results.length > 0
    ? Object.keys(results[0]).map((key) => ({
        title: key,
        dataIndex: key,
        key,
        ellipsis: true,
        render: (value: unknown) => {
          if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
            return String(value);
          }
          return <Tag>{JSON.stringify(value)}</Tag>;
        },
      }))
    : [];

  const tabItems = [
    {
      key: 'text',
      label: 'Text Query',
      children: (
        <TextArea
          placeholder="Enter query expression..."
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          rows={4}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      key: 'structured',
      label: 'Structured Query',
      children: (
        <TextArea
          placeholder='{"intent": "query", "entities": [], "filters": {}}'
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          rows={4}
          style={{ width: '100%', fontFamily: 'monospace' }}
        />
      ),
    },
  ];

  return (
    <Card title="Unified Query" size="small">
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space wrap>
          <Select
            value={source}
            onChange={setSource}
            options={SOURCE_OPTIONS}
            style={{ width: 140 }}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            loading={loading}
            onClick={handleQuery}
          >
            Query
          </Button>
          <Button onClick={handleValidate}>Validate</Button>
          <Button onClick={handleExplain}>Explain</Button>
        </Space>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />

        <Spin spinning={loading}>
          {results.length > 0 ? (
            <>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">
                  {total} result{total !== 1 ? 's' : ''} from <Tag color="blue">{source}</Tag> source
                </Text>
              </div>
              <Table
                dataSource={results}
                columns={columns}
                rowKey={(_, index) => String(index)}
                size="small"
                pagination={{ pageSize: 10 }}
                scroll={{ x: 'max-content' }}
              />
            </>
          ) : (
            <Empty description="No results" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Spin>
      </Space>
    </Card>
  );
}
