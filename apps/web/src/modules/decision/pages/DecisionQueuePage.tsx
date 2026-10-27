/**
 * 待决策队列页（`/decisions/queue`）
 *
 * 三段分组（不是两段，uiux §5.1.2）：
 *   to_resolve            → status=pending                    「待我拍板」
 *   to_execute + decided  → 已裁决未派发（后端给 execute）      「已裁决，待执行」
 *   to_execute + executing→ 执行中（available_operations 为空）「执行中」
 * `group` 与 `available_operations` 全部来自后端，前端不反推（改状态机不该改前端）。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { App, Button, Empty, Skeleton, Space, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import type { PendingDecisionItem, PendingQueuePage } from '../types';
import {
  executeDecision,
  listPendingDecisions,
  resolveDecision,
} from '../services/decisionApi';
import { describeActionError, describeError, errorStatus } from '../services/decisionRequest';
import { DecisionQueueCard } from '../components/DecisionQueueCard';
import { RejectDecisionModal } from '../components/RejectDecisionModal';
import { formatDuration, toWaitMinutes } from '../utils/displayStatus';
import { splitSections } from '../utils/queueSections';
import '../components/DecisionQueueCard.css';

const { Text } = Typography;

type GroupFilter = 'all' | 'to_resolve' | 'to_execute';

export default function DecisionQueuePage() {
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [group, setGroup] = useState<GroupFilter>('all');
  const [data, setData] = useState<PendingQueuePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<PendingDecisionItem | null>(null);
  const [rejecting, setRejecting] = useState(false);
  // 无裁决权限：按钮禁用 + Tooltip「需要决策审批权限」，**不整页 403**
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [staleNotice, setStaleNotice] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: '1', page_size: '50', group });
      const page = await listPendingDecisions(params);
      setData(page);
      setError(null);
      setStaleNotice(false);
    } catch (e) {
      setError(e);
      // 列表失败时计数条保留上次值并标注可能过期，不阻断既有数据
      setStaleNotice(true);
    } finally {
      setLoading(false);
    }
  }, [group]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleActionError = useCallback(
    (e: unknown) => {
      // 文案统一由 `decisionRequest` 出（`code` 优先于状态码），不在页面里再拼一遍
      const status = errorStatus(e);
      if (status === 403) {
        setPermissionDenied(true);
        message.warning(describeActionError(e));
      } else if (status === 409) {
        message.warning(describeActionError(e));
      } else if (status === 404) {
        message.error(describeActionError(e));
      } else {
        message.error(describeActionError(e));
      }
      void load();
    },
    [load, message],
  );

  const submitResolve = useCallback(
    async (item: PendingDecisionItem, action: 'approve' | 'reject', reason?: string) => {
      setBusyId(item.decision.decision_id);
      try {
        await resolveDecision(item.decision.decision_id, reason ? { action, reason } : { action });
        message.success(action === 'approve' ? '已采纳，可在台账查看' : '已驳回，理由可在台账查看');
        void load();
      } catch (e) {
        handleActionError(e);
      } finally {
        setBusyId(null);
      }
    },
    [handleActionError, load, message],
  );

  const handleApprove = useCallback(
    (item: PendingDecisionItem) => {
      const lowConfidence = item.decision.confidence < 0.5;
      if (!lowConfidence) {
        void submitResolve(item, 'approve');
        return;
      }
      // 低置信度二次确认：显式给出置信度，不替用户做决定
      modal.confirm({
        title: `这条决策的置信度较低（${Math.round(item.decision.confidence * 100)}%）`,
        content: '采纳后将以该方案进入执行。低置信度决策建议先查看证据链。',
        okText: '仍然采纳',
        cancelText: '查看证据',
        onCancel: () => navigate(`/decisions/detail/${item.decision.decision_id}`),
        onOk: () => submitResolve(item, 'approve'),
      });
    },
    [modal, navigate, submitResolve],
  );

  const handleExecute = useCallback(
    async (item: PendingDecisionItem) => {
      setBusyId(item.decision.decision_id);
      try {
        const result = await executeDecision(item.decision.decision_id);
        message.success(
          result.idempotent_replay ? '该决策已执行过，未重复派发' : '已发起执行，等待执行完成',
        );
        void load();
      } catch (e) {
        handleActionError(e);
      } finally {
        setBusyId(null);
      }
    },
    [handleActionError, load, message],
  );

  const counts = data?.counts;
  const sections = data ? splitSections(data.items) : [];
  // 最长等待：按 group 取各自字段（两个字段差一整个待裁定周期，不可互替）
  const waits = (data?.items ?? []).map(toWaitMinutes).filter((m): m is number => m !== null);
  const longestWait = waits.length > 0 ? Math.max(...waits) : null;

  return (
    <div>
      <Space size={16} wrap style={{ marginBottom: 12 }}>
        <Button
          type={group === 'to_resolve' ? 'primary' : 'default'}
          onClick={() => setGroup(group === 'to_resolve' ? 'all' : 'to_resolve')}
        >
          {`待裁定 ${counts ? counts.to_resolve : '—'} 条`}
        </Button>
        <Button
          type={group === 'to_execute' ? 'primary' : 'default'}
          onClick={() => setGroup(group === 'to_execute' ? 'all' : 'to_execute')}
        >
          {`待执行确认 ${counts ? counts.to_execute : '—'} 条`}
        </Button>
        {/* SLA 计数为说明性文字，不是控件：契约没有 sla 过滤参数，做成可点就是死控件 */}
        <Text type="secondary">{`等待较久 ${counts ? counts.sla_warning : '—'} 条`}</Text>
        <Text type="secondary">{`已超时 ${counts ? counts.sla_breached : '—'} 条`}</Text>
        {staleNotice && <Text type="warning">数据可能过期</Text>}
      </Space>

      {loading && !data && (
        <Space orientation="vertical" size={16} style={{ width: '100%' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
          <Skeleton active paragraph={{ rows: 3 }} />
          <Skeleton active paragraph={{ rows: 3 }} />
        </Space>
      )}

      {error != null && !loading && (
        <div role="alert" style={{ textAlign: 'center', padding: 'var(--odap-spacing-xl)' }}>
          <CloseCircleOutlined style={{ fontSize: 24, color: 'var(--odap-color-error)' }} />
          <div style={{ margin: '8px 0' }}>
            <Text strong>待决策队列加载失败</Text>
          </div>
          <Text type="secondary">{describeError(error)}</Text>
          <div style={{ marginTop: 12 }}>
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>
              重试
            </Button>
          </div>
        </div>
      )}

      {!error && data && sections.length === 0 && !loading && (
        <Empty
          image={<CheckCircleOutlined style={{ fontSize: 24, color: 'var(--odap-color-success)' }} />}
          description={
            <Space orientation="vertical" size={4}>
              <Text strong>待决策队列已清空</Text>
              <Text type="secondary">当前没有等你拍板的决策。</Text>
            </Space>
          }
        >
          <Button type="link" onClick={() => navigate('/decisions/ledger')}>
            去台账看看最近的决策
          </Button>
        </Empty>
      )}

      {!error &&
        sections.map((section) => (
          <div key={section.key}>
            <div className="dsi-queue-section-title">
              {section.title}
              <Text type="secondary" style={{ fontWeight: 'normal', marginLeft: 8 }}>
                {`${section.items.length} 条`}
              </Text>
            </div>
            <Space orientation="vertical" size={16} style={{ width: '100%' }}>
              {section.items.map((item) => (
                <DecisionQueueCard
                  key={item.decision.decision_id}
                  item={item}
                  canOperate={!permissionDenied}
                  busy={busyId === item.decision.decision_id}
                  onApprove={handleApprove}
                  onReject={setRejectTarget}
                  onExecute={handleExecute}
                  onOpenDetail={(id) => navigate(`/decisions/detail/${id}`)}
                />
              ))}
            </Space>
          </div>
        ))}

      {data && data.has_more && (
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
          {`共 ${data.total} 条待办，当前展示前 ${data.items.length} 条，请先处理当前条目`}
        </Text>
      )}
      {!data?.has_more && data && data.total > 0 && (
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
          {`共 ${data.total} 条待办，最长等待 ${formatDuration(longestWait)}`}
        </Text>
      )}

      <RejectDecisionModal
        key={rejectTarget?.decision.decision_id ?? 'no-target'}
        open={Boolean(rejectTarget)}
        decisionSummary={rejectTarget?.decision.context_summary}
        submitting={rejecting}
        onCancel={() => setRejectTarget(null)}
        onSubmit={(reason) => {
          if (!rejectTarget) return;
          setRejecting(true);
          void submitResolve(rejectTarget, 'reject', reason).finally(() => {
            setRejecting(false);
            setRejectTarget(null);
          });
        }}
      />
    </div>
  );
}
