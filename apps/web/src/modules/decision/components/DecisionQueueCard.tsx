/**
 * 待决策队列条目卡片（uiux §5.2）
 *
 * 两条硬规则：
 * 1. **按钮由后端 `available_operations` 驱动**，不按 `status` 硬编码按钮组合。
 * 2. `available_operations` 为空时**不渲染按钮组**，改渲染进度说明文字。
 *    「禁用态」只表达「你没权限」一种语义；「这个动作对谁都不存在」是另一种语义，
 *    混用会让用户反复点击并怀疑权限（uiux §5.1.4）。
 * SLA 全部来自后端 `sla_state`，前端不自算阈值（spec §10）。
 */
import React from 'react';
import { Button, Space, Tooltip, Typography } from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  EyeOutlined,
  FieldTimeOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { PendingDecisionItem } from '../types';
import { DecisionStatusTag } from './DecisionStatusTag';
import { EvidenceCount } from './EvidenceCount';
import {
  formatDuration,
  hasOperation,
  toEntrySourceLabel,
  toSlaBadge,
  toWaitMinutes,
} from '../utils/displayStatus';
import './DecisionQueueCard.css';

const { Text } = Typography;

interface Props {
  item: PendingDecisionItem;
  /** false = 无裁决权限：按钮禁用 + Tooltip，但**不隐藏**、不整页 403 */
  canOperate?: boolean;
  busy?: boolean;
  onApprove?: (item: PendingDecisionItem) => void;
  onReject?: (item: PendingDecisionItem) => void;
  onExecute?: (item: PendingDecisionItem) => void;
  onOpenDetail?: (decisionId: string) => void;
}

const PERMISSION_TIP = '需要决策审批权限';
const LOW_CONFIDENCE_TIP = '低置信度决策建议先查看证据链';

function disableWithTip(node: React.ReactElement, disabled: boolean) {
  return disabled ? <Tooltip title={PERMISSION_TIP}>{node}</Tooltip> : node;
}

export function DecisionQueueCard({
  item,
  canOperate = true,
  busy = false,
  onApprove,
  onReject,
  onExecute,
  onOpenDetail,
}: Props) {
  const { decision, available_operations: operations, sla_state: slaState } = item;
  // 等待时长按 group 取字段：to_execute 用 decided_waited_minutes，两者不可互替
  const waited = toWaitMinutes(item);
  const sla = toSlaBadge(slaState, decision.status);
  const source = toEntrySourceLabel(decision.entry_source);
  const confidence = typeof decision.confidence === 'number' ? Math.round(decision.confidence * 100) : null;
  const lowConfidence = confidence !== null && confidence < 60;
  const noOperation = !operations || operations.length === 0;

  const approveBtn = (
    <Button
      type="primary"
      icon={<CheckOutlined style={{ fontSize: 20 }} />}
      disabled={!canOperate || busy}
      onClick={() => onApprove?.(item)}
    >
      采纳
    </Button>
  );

  const rejectBtn = (
    <Button
      disabled={!canOperate || busy}
      icon={<CloseOutlined style={{ fontSize: 20 }} />}
      onClick={() => onReject?.(item)}
    >
      驳回
    </Button>
  );

  const executeBtn = (
    <Button
      type="primary"
      disabled={!canOperate || busy}
      icon={<SyncOutlined style={{ fontSize: 20 }} />}
      onClick={() => onExecute?.(item)}
    >
      发起执行
    </Button>
  );

  const retryBtn = (
    <Button
      disabled={!canOperate || busy}
      icon={<SyncOutlined style={{ fontSize: 20 }} />}
      onClick={() => onExecute?.(item)}
    >
      重试执行
    </Button>
  );

  return (
    <div
      className="dsi-queue-card"
      data-decision-id={decision.decision_id}
      role="group"
      style={{ cursor: 'pointer' }}
      onClick={() => onOpenDetail?.(decision.decision_id)}
    >
      <Space size={8} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
        <Space size={8} wrap>
          <DecisionStatusTag
            status={decision.status}
            outcome={decision.outcome}
            statusAssumed={decision.status_assumed}
          />
          {sla && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--odap-spacing-xs)',
                fontSize: 'var(--odap-font-size-xs)',
                color:
                  sla.tone === 'breached'
                    ? 'var(--odap-color-error)'
                    : 'var(--odap-color-warning)',
              }}
            >
              <FieldTimeOutlined style={{ fontSize: 16 }} />
              {sla.text}
            </span>
          )}
          {decision.status_assumed && (
            <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
              历史数据，流程状态未记录
            </Text>
          )}
        </Space>

        <Tooltip title={lowConfidence ? LOW_CONFIDENCE_TIP : undefined}>
          <Text
            style={{
              fontVariantNumeric: 'tabular-nums',
              color: lowConfidence ? 'var(--odap-color-warning)' : 'var(--odap-color-text-primary)',
            }}
          >
            {confidence === null ? '置信度 未评估' : `置信度 ${confidence}%${lowConfidence ? ' 低' : ''}`}
          </Text>
        </Tooltip>
      </Space>

      <div className="dsi-queue-card__summary" title={decision.context_summary}>
        {decision.context_summary || '未填写场景描述'}
      </div>

      <div style={{ fontSize: 'var(--odap-font-size-base)' }}>
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)', marginRight: 8 }}>
          推荐方案
        </Text>
        <Text>{decision.recommended_option || '未给出方案'}</Text>
      </div>

      <div className="dsi-queue-card__meta" style={{ marginTop: 'var(--odap-spacing-sm)' }}>
        {/* 字段缺失 = 「证据数未知」，**不是 0**：「0 条证据」是一个结论，「未知」是另一个 */}
        <EvidenceCount
          entityCount={decision.evidence_entity_ids?.length}
          episodeCount={decision.evidence_episode_ids?.length}
        />
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-sm)' }}>
          {`来源 ${source.label}`}
        </Text>
        {/* 等待时长由后端给（按 group 取字段），不做自动刷新的相对时间 */}
        <span className="dsi-queue-card__meta-mono">
          {waited === null ? '等待时长未知' : `等待 ${formatDuration(waited)}`}
        </span>
      </div>

      <div className="dsi-queue-card__footer" onClick={(e) => e.stopPropagation()}>
        {noOperation ? (
          <span className="dsi-queue-card__progress">
            <SyncOutlined style={{ fontSize: 16 }} />
            {decision.status === 'executing'
              ? '执行中，等待完成（该决策已在执行，无需再操作）'
              : '已裁决，等待执行完成'}
          </span>
        ) : (
          <Space size={8}>
            <Button
              type="text"
              icon={<EyeOutlined style={{ fontSize: 20 }} />}
              onClick={() => onOpenDetail?.(decision.decision_id)}
            >
              查看详情
            </Button>
            {hasOperation(operations, 'reject') && disableWithTip(rejectBtn, !canOperate)}
            {hasOperation(operations, 'approve') && disableWithTip(approveBtn, !canOperate)}
            {hasOperation(operations, 'execute') && disableWithTip(executeBtn, !canOperate)}
            {hasOperation(operations, 'retry') && disableWithTip(retryBtn, !canOperate)}
          </Space>
        )}
      </div>
    </div>
  );
}

export default DecisionQueueCard;
