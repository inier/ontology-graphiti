/**
 * NL 查询审计面板 - 嵌入审计页面的查询审计标签页
 */
import React, { useEffect, useState } from 'react';
import { Table, Card, Tag, Space, Typography, Statistic, Row, Col, Select, Button } from 'antd';
import { ReloadOutlined, SearchOutlined, ApiOutlined, BranchesOutlined } from '@ant-design/icons';
import { useNLQueryStore } from '@/modules/qa/stores/nlQueryStore';

const { Text } = Typography;

const PILLAR_ICON: Record<string, React.ReactNode> = {
  bm25: <SearchOutlined />,
  vector: <ApiOutlined />,
  graph: <BranchesOutlined />,
};

const INTENT_LABELS: Record<string, { label: string; color: string }> = {
  keyword_lookup: { label: '关键词', color: 'blue' },
  semantic_search: { label: '语义', color: 'green' },
  graph_traverse: { label: '图遍历', color: 'orange' },
  complex_analysis: { label: '复杂分析', color: 'purple' },
  temporal_query: { label: '时态', color: 'cyan' },
  action: { label: '动作', color: 'red' },
};

export function NLQueryAuditPanel() {
  const {
    auditRecords,
    auditTotal,
    auditStats,
    auditLoading,
    fetchAuditRecords,
    fetchAuditStats,
  } = useNLQueryStore();

  const [workspaceFilter, setWorkspaceFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    fetchAuditRecords({ limit: 20 });
    fetchAuditStats();
  }, [fetchAuditRecords, fetchAuditStats]);

  const handleRefresh = () => {
    fetchAuditRecords({ limit: 20, workspace_id: workspaceFilter });
    fetchAuditStats(workspaceFilter);
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 140,
      render: (ts: string) => {
        try {
          return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        } catch {
          return ts;
        }
      },
    },
    {
      title: '查询',
      dataIndex: 'original_query',
      key: 'original_query',
      width: 200,
      ellipsis: true,
    },
    {
      title: '意图',
      dataIndex: 'intent',
      key: 'intent',
      width: 90,
      render: (intent: string) => {
        const info = INTENT_LABELS[intent] || { label: intent, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '支柱',
      dataIndex: 'selected_pillars',
      key: 'selected_pillars',
      width: 120,
      render: (pillars: string[]) => (
        <Space size={2}>
          {pillars.map((p) => (
            <Tag key={p} icon={PILLAR_ICON[p]} style={{ fontSize: 10, margin: 0 }} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'}>
              {p}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'total_time_ms',
      key: 'total_time_ms',
      width: 80,
      render: (ms: number) => (
        <Text style={{ fontSize: 12, color: ms < 500 ? '#52c41a' : ms < 2000 ? '#1890ff' : '#ff4d4f' }}>
          {ms.toFixed(0)}ms
        </Text>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_count',
      key: 'source_count',
      width: 60,
      render: (c: number) => <Text style={{ fontSize: 12 }}>{c}</Text>,
    },
    {
      title: '用户',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 80,
      ellipsis: true,
    },
  ];

  return (
    <div>
      {/* 统计概览 */}
      {auditStats && (
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic title="总查询次数" value={auditStats.total_queries} loading={auditLoading} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="平均耗时"
                value={auditStats.avg_time_ms}
                suffix="ms"
                styles={{ content: { color: auditStats.avg_time_ms < 1000 ? '#52c41a' : '#faad14' } }}
                loading={auditLoading}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="支柱使用" styles={{ body: { padding: '4px 12px' } }}>
              <Space>
                {Object.entries(auditStats.pillar_usage).map(([p, c]) => (
                  <Tag key={p} icon={PILLAR_ICON[p]} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'}>
                    {p}: {c}
                  </Tag>
                ))}
              </Space>
            </Card>
          </Col>
        </Row>
      )}

      {/* 过滤 + 刷新 */}
      <Space style={{ marginBottom: 12 }}>
        <Select
          placeholder="工作空间"
          allowClear
          style={{ width: 180 }}
          value={workspaceFilter}
          onChange={(v) => setWorkspaceFilter(v)}
        />
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={auditLoading}>
          刷新
        </Button>
      </Space>

      {/* 审计表格 */}
      <Table
        columns={columns}
        dataSource={auditRecords}
        rowKey="query_id"
        loading={auditLoading}
        size="small"
        scroll={{ x: 770 }}
        pagination={{
          total: auditTotal,
          pageSize: 20,
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (page) => {
            fetchAuditRecords({ limit: 20, offset: (page - 1) * 20, workspace_id: workspaceFilter });
          },
        }}
      />
    </div>
  );
}
