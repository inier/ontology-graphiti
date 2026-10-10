/**
 * RoutingTicketsPage —— 路由工单列表（ADR-090 D-D14）。
 *
 * 工程债可见可操作：统计卡（按状态/优先级/违约数）+ 过滤 + 表格
 * （优先级 Tag、状态 Badge、SLA 违约红色高亮、处理人），行点击进详情。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Table, Tag, Badge, Select, Space, Statistic, Row, Col, Typography,
  message, Tooltip,
} from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  routingTicketApi,
  PRIORITY_SLA_HOURS,
  type RoutingTicket,
  type TicketStats,
  type TicketStatus,
  type TicketPriority,
} from '../services/routingTicketApi';

const { Text } = Typography;

const STATUS_META: Record<TicketStatus, { color: string; text: string }> = {
  open: { color: 'default', text: '待处理' },
  assigned: { color: 'blue', text: '已指派' },
  in_progress: { color: 'processing', text: '处理中' },
  resolved: { color: 'success', text: '已解决' },
  rejected: { color: 'error', text: '已驳回' },
  closed: { color: 'default', text: '已关闭' },
};

const PRIORITY_COLOR: Record<TicketPriority, string> = {
  P0: 'red', P1: 'orange', P2: 'blue', P3: 'default',
};

export const statusMeta = (s: string) =>
  STATUS_META[s as TicketStatus] ?? { color: 'default', text: s };

export const RoutingTicketsPage: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<RoutingTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<TicketStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | undefined>();
  const [priority, setPriority] = useState<string | undefined>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, st] = await Promise.all([
        routingTicketApi.list({ status, priority, page: 1, page_size: 50 }),
        routingTicketApi.stats(),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setStats(st);
    } catch (e) {
      message.error((e as Error).message || '加载工单列表失败');
    } finally {
      setLoading(false);
    }
  }, [status, priority]);

  useEffect(() => { void load(); }, [load]);

  const columns: ColumnsType<RoutingTicket> = [
    {
      title: '优先级', dataIndex: 'priority', width: 90,
      render: (p: TicketPriority, r) => (
        <Tooltip title={`SLA ${PRIORITY_SLA_HOURS[p]} 小时`}>
          <Tag color={r.sla_breached ? 'red' : PRIORITY_COLOR[p]}>{p}</Tag>
        </Tooltip>
      ),
    },
    {
      title: '状态', dataIndex: 'status', width: 110,
      render: (s: string) => {
        const m = statusMeta(s);
        return <Badge status={m.color as never} text={m.text} />;
      },
    },
    {
      title: '标题', dataIndex: 'title', ellipsis: true,
      render: (t: string, r) => (
        <Space size={4}>
          {r.sla_breached && <WarningOutlined style={{ color: '#cf1322' }} />}
          <a onClick={() => navigate(`/semantic-admin/routing-tickets/${r.id}`)}>{t}</a>
        </Space>
      ),
    },
    { title: '检索引擎', dataIndex: 'engine', width: 150, ellipsis: true },
    {
      title: '处理人', dataIndex: 'assignee', width: 120,
      render: (a: string | null) => a || <Text type="secondary">—</Text>,
    },
    {
      title: 'SLA 截止', dataIndex: 'sla_deadline', width: 200,
      render: (d: string | null, r) => (
        <Text type={r.sla_breached ? 'danger' : undefined} style={{ fontSize: 12 }}>
          {d ? d.slice(0, 19).replace('T', ' ') : '—'}
          {r.sla_breached ? '（已违约）' : ''}
        </Text>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }} data-testid="routing-tickets-page">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="工单总数" value={stats?.total ?? 0} /></Card></Col>
        <Col span={6}>
          <Card>
            <Statistic title="待处理 (open)" value={stats?.by_status?.open ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="处理中 (in_progress)"
              value={stats?.by_status?.in_progress ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="SLA 违约" value={stats?.breached_count ?? 0}
              valueStyle={{ color: (stats?.breached_count ?? 0) > 0 ? '#cf1322' : undefined }} />
          </Card>
        </Col>
      </Row>

      <Card
        title="路由工单（tool 层工程债）"
        extra={
          <Space>
            <Select
              allowClear placeholder="状态" style={{ width: 140 }}
              value={status} onChange={setStatus}
              options={Object.entries(STATUS_META).map(([v, m]) => ({ value: v, label: m.text }))}
            />
            <Select
              allowClear placeholder="优先级" style={{ width: 120 }}
              value={priority} onChange={setPriority}
              options={(['P0', 'P1', 'P2', 'P3'] as TicketPriority[])
                .map((p) => ({ value: p, label: p }))}
            />
          </Space>
        }
      >
        <Table<RoutingTicket>
          rowKey="id" size="small" loading={loading}
          columns={columns} dataSource={items}
          pagination={{ total, pageSize: 50, showSizeChanger: false }}
        />
      </Card>
    </div>
  );
};

export default RoutingTicketsPage;
