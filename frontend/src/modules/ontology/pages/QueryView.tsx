import { useState } from 'react';
import { Card, Button, Space, Input, Select, message, Table, Tabs } from 'antd';
import { SearchOutlined, ExportOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import Visualization from '../../shared/components/Visualization';

const { Option } = Select;
const { TabPane } = Tabs;
const { Search } = Input;

interface QueryResult {
  entity_id: string;
  name: string;
  type: string;
  properties: Record<string, unknown>;
}

export function QueryView() {
  const [keyword, setKeyword] = useState('');
  const [entityType, setEntityType] = useState('');
  const [results, setResults] = useState<QueryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const handleSearch = async () => {
    if (!keyword) {
      message.warning('请输入关键词');
      return;
    }

    try {
      setLoading(true);
      const response = await api.queryEntities({ keyword, type: entityType });
      setResults(response.entities);
      message.success(`找到 ${response.total} 个结果`);
    } catch (error) {
      console.error('查询失败', error);
      message.error('查询失败');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'json' | 'csv') => {
    if (results.length === 0) {
      message.warning('没有数据可导出');
      return;
    }

    try {
      setExportLoading(true);
      const response = await api.exportQueryResults(results as any, format);
      if (response.success) {
        const blob = new Blob([response.data], {
          type: format === 'json' ? 'application/json' : 'text/csv'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `query-results.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        message.success('导出成功');
      }
    } catch (error) {
      console.error('导出失败', error);
      message.error('导出失败');
    } finally {
      setExportLoading(false);
    }
  };

  const columns = [
    {
      title: '实体ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
    },
    {
      title: '属性',
      dataIndex: 'properties',
      key: 'properties',
      render: (properties: Record<string, unknown>) => (
        <div style={{ maxWidth: 300, overflow: 'auto' }}>
          {Object.entries(properties)
            .slice(0, 5)
            .map(([key, value]) => (
              <div key={key} style={{ fontSize: '12px' }}>
                <strong>{key}:</strong> {JSON.stringify(value)}
              </div>
            ))}
          {Object.entries(properties).length > 5 && (
            <div style={{ fontSize: '12px', color: '#888' }}>
              ... 还有 {Object.entries(properties).length - 5} 个属性
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card 
        title="查询界面" 
        style={{ marginBottom: 16 }}
        extra={
          <div style={{ fontSize: '12px', color: '#888' }}>
            💡 提示：输入关键词后按回车或点击查询按钮
          </div>
        }
      >
        <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px' }}>
          <div style={{ fontSize: '14px', color: '#389e0d' }}>
            <strong>操作指南：</strong>
          </div>
          <div style={{ fontSize: '12px', color: '#52c41a', marginTop: '4px' }}>
            1. 在搜索框中输入关键词（如：雷达、部队等）<br />
            2. 可选：选择实体类型进行过滤<br />
            3. 点击查询按钮或按回车键执行查询<br />
            4. 在表格视图或可视化视图中查看结果
          </div>
        </div>
        
        <Space style={{ marginBottom: 16 }}>
          <Search
            placeholder="输入关键词，例如：雷达、部队"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 300 }}
            enterButton={<SearchOutlined />}
          />
          <Select
            placeholder="选择实体类型"
            value={entityType}
            onChange={setEntityType}
            style={{ width: 150 }}
          >
            <Option value="">全部类型</Option>
            <Option value="Person">人物</Option>
            <Option value="Organization">组织</Option>
            <Option value="Location">地点</Option>
            <Option value="Event">事件</Option>
            <Option value="Object">对象</Option>
          </Select>
          <Button
            type="primary"
            onClick={handleSearch}
            loading={loading}
            icon={<SearchOutlined />}
          >
            查询
          </Button>
          <Button
            onClick={handleSearch}
            loading={loading}
            icon={<ReloadOutlined />}
          >
            刷新
          </Button>
        </Space>

        <Space style={{ marginBottom: 16 }}>
          <Button
            onClick={() => handleExport('json')}
            loading={exportLoading}
            icon={<ExportOutlined />}
            disabled={results.length === 0}
          >
            导出 JSON
          </Button>
          <Button
            onClick={() => handleExport('csv')}
            loading={exportLoading}
            icon={<ExportOutlined />}
            disabled={results.length === 0}
          >
            导出 CSV
          </Button>
        </Space>
      </Card>

      <Tabs defaultActiveKey="table">
        <TabPane tab="表格视图" key="table">
          <Card>
            <Table
              columns={columns}
              dataSource={results.map((item) => ({ ...item, key: item.entity_id }))}
              loading={loading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条记录`,
              }}
              scroll={{ x: 1000 }}
            />
          </Card>
        </TabPane>

        <TabPane tab="可视化视图" key="visualization">
          <Visualization data={results} loading={loading} />
        </TabPane>
      </Tabs>
    </div>
  );
}

export default QueryView;