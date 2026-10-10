/**
 * RoutingTicketDetailPage —— 路由工单详情（ADR-090 D-D14）。
 *
 * 基本信息卡 + 事件时间线 + 操作区（指派 / 状态流转 / 评论）；
 * 按 TICKET_TRANSITIONS 禁用非法流转按钮（后端仍会 409 兜底，规则 14）。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Descriptions, Timeline, Tag, Badge, Button, Space, Spin, message,
  Typography, Input, Select, Alert, Divider,
} from 'antd';
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons';
import {
  routingTicketApi, TICKET_TRANSITIONS, PRIORITY_SLA_HOURS,
  type RoutingTicket, type TicketEvent, type TicketStatus, type TicketPriority,
} from '../services/routingTicketApi';
import { statusMeta } from './RoutingTicketsPage';

const { Text } = Typography;

const EVENT_LABEL: Record<string, string> = {
  created: '创建', assigned: '指派', transitioned: '流转',
  commented: '评论', priority_changed: '优先级变更', sla_breached: 'SLA 违约',
};

export const RoutingTicketDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<RoutingTicket | null>(null);
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [assignee, setAssignee] = useState('');
  const [comment, setComment] = useState('');

  const load = useCallback(async () => {
    if (!id) { setLoading(false); return; }
    try {
      const [t, e] = await Promise.all([
        routingTicketApi.get(id), routingTicketApi.events(id),
      ]);
      setTicket(t);
      setEvents(e.events);
      setAssignee(t.assignee || '');
    } catch (err) {
      message.error((err as Error).message || '加载工单失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      message.success(ok);
      await load();
    } catch (e) {
      // 暴露后端具体失败原因（如 INVALID_TICKET_TRANSITION）
      message.error((e as Error).message || '操作失败');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Spin style={{ margin: 24 }} />;
  if (!ticket) return <div style={{ padding: 24 }}>工单不存在</div>;

  const canAssign = !['rejected', 'closed'].includes(ticket.status);
  const targets = TICKET_TRANSITIONS[ticket.status] ?? [];

  return (
    <div style={{ padding: 16 }} data-testid="routing-ticket-detail">
      <Button type="link" icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/semantic-admin/routing-tickets')}>
        返回列表
      </Button>

      <Card
        title={ticket.title}
        extra={
          <Space>
            <Tag color={ticket.sla_breached ? 'red' : undefined}>{ticket.priority}</Tag>
            <Badge status={statusMeta(ticket.status).color as never}
              text={statusMeta(ticket.status).text} />
          </Space>
        }
      >
        {ticket.sla_breached && (
          <Alert type="error" showIcon style={{ marginBottom: 12 }}
            message="SLA 已违约"
            description={`截止 ${ticket.sla_deadline}（${ticket.priority} = ${PRIORITY_SLA_HOURS[ticket.priority]}h）仍未终态。`} />
        )}
        <Descriptions column={2}>
          <Descriptions.Item label="缺口 ID">
            {ticket.gap_id
              ? <a onClick={() => navigate(`/semantic-admin/gaps/${ticket.gap_id}`)}>
                  {ticket.gap_id}</a>
              : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="检索引擎">{ticket.engine}</Descriptions.Item>
          <Descriptions.Item label="表达式">{ticket.expression}</Descriptions.Item>
          <Descriptions.Item label="scope">{ticket.scope_key}</Descriptions.Item>
          <Descriptions.Item label="处理人">
            {ticket.assignee || '—'}
          </Descriptions.Item>
          <Descriptions.Item label="创建">{ticket.created_at}</Descriptions.Item>
          {ticket.resolved_at && (
            <Descriptions.Item label="解决">
              {ticket.resolved_at} · {ticket.resolved_by}
            </Descriptions.Item>)}
          {ticket.resolution_note && (
            <Descriptions.Item label="解决说明">
              {ticket.resolution_note}</Descriptions.Item>)}
        </Descriptions>
      </Card>

      <Card title="操作" style={{ marginTop: 12 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space wrap>
            <Input style={{ width: 220 }} placeholder="处理人（assignee）"
              value={assignee} disabled={!canAssign}
              onChange={(e) => setAssignee(e.target.value)} />
            <Button type="primary" ghost loading={busy} disabled={!canAssign}
              onClick={() => run(
                () => routingTicketApi.assign(ticket.id, { assignee }),
                '已指派')}>
              指派
            </Button>
            <Select<TicketPriority>
              placeholder="改优先级" style={{ width: 140 }} disabled={!canAssign}
              onChange={(p) => run(
                () => routingTicketApi.assign(ticket.id,
                  { assignee: assignee || ticket.assignee || '', priority: p }),
                `优先级已改为 ${p}`)}
              options={(['P0', 'P1', 'P2', 'P3'] as TicketPriority[])
                .map((p) => ({ value: p, label: `${p}（${PRIORITY_SLA_HOURS[p]}h）` }))}
            />
          </Space>

          <Space wrap>
            <Text type="secondary">流转到：</Text>
            {targets.length === 0
              ? <Text type="secondary">终态，无可用流转</Text>
              : targets.map((t: TicketStatus) => (
                <Button key={t} size="small" loading={busy}
                  onClick={() => run(
                    () => routingTicketApi.transition(ticket.id, { to_status: t }),
                    `已流转到 ${statusMeta(t).text}`)}>
                  {statusMeta(t).text}
                </Button>
              ))}
          </Space>

          <Divider style={{ margin: '4px 0' }} />

          <Space.Compact style={{ width: '100%' }}>
            <Input placeholder="添加评论（仅留痕）"
              value={comment} onChange={(e) => setComment(e.target.value)} />
            <Button icon={<SendOutlined />} loading={busy} disabled={!comment}
              onClick={() => run(async () => {
                await routingTicketApi.comment(ticket.id, comment);
                setComment('');
              }, '评论已添加')}>评论</Button>
          </Space.Compact>
        </Space>
      </Card>

      <Card title="事件时间线（不可变审计）" style={{ marginTop: 12 }}>
        <Timeline items={events.map((e) => ({
          color: e.to_status === 'rejected' ? 'red' : undefined,
          children: (
            <Space direction="vertical" size={0}>
              <Text>
                <Tag>{EVENT_LABEL[e.event_type] || e.event_type}</Tag>
                {e.from_status ? `${e.from_status} → ${e.to_status}` : (e.to_status || '')}
                {' · '}{e.actor}
              </Text>
              {e.note && <Text type="secondary" style={{ fontSize: 12 }}>{e.note}</Text>}
              <Text type="secondary" style={{ fontSize: 12 }}>{e.created_at}</Text>
            </Space>
          ),
        }))} />
      </Card>
    </div>
  );
};

export default RoutingTicketDetailPage;
