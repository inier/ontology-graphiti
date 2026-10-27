/**
 * 决策状态标签
 *
 * 唯一映射入口：`toDisplayLabel(status, outcome)`（`utils/displayStatus.ts`）。
 * 本组件内**不得**再判断 `status === 'executed' && outcome === '...'`。
 */
import React from 'react';
import { Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  MinusCircleOutlined,
  QuestionCircleOutlined,
  StopOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { DecisionOutcome, DecisionStatus } from '../types';
import { isStatusOutcomeConflict, toDisplayLabel, type DisplayTone } from '../utils/displayStatus';
import './DecisionStatusTag.css';

interface Props {
  status: DecisionStatus | null | undefined;
  /** 必传：`status` 不含 `partial_success`，缺 outcome 会丢「部分成功」 */
  outcome?: DecisionOutcome | null;
  /** 历史数据（`status` 为推定值）在标签右侧给出轻量说明 */
  statusAssumed?: boolean;
  /** 状态与结果字段矛盾时的提示，默认开启 */
  showConflictHint?: boolean;
}

const TONE_ICON: Record<DisplayTone, React.ReactNode> = {
  success: <CheckCircleOutlined />,
  partial: <MinusCircleOutlined />,
  failure: <CloseCircleOutlined />,
  pending: <ClockCircleOutlined />,
  rejected: <StopOutlined />,
  unknown: <QuestionCircleOutlined />,
};

export function DecisionStatusTag({
  status,
  outcome,
  statusAssumed = false,
  showConflictHint = true,
}: Props) {
  const { tone, label } = toDisplayLabel(status, outcome);
  // 待执行确认（decided / executing）用 Sync 图标区分「待裁定」的 Clock，颜色仍同 warning
  const icon = status === 'executing' ? <SyncOutlined /> : TONE_ICON[tone];
  const conflict = showConflictHint && isStatusOutcomeConflict(status, outcome);

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
      <span className={`dsi-status dsi-status--${tone}`} data-tone={tone} title={label}>
        {icon}
        <span>{label}</span>
      </span>
      {conflict && (
        <Tooltip title="决策状态与结果字段不一致，请核对执行动作">
          <WarningOutlined className="dsi-status-conflict" aria-label="状态与结果字段不一致" />
        </Tooltip>
      )}
      {statusAssumed && (
        <Tooltip title="这条决策创建于流程状态字段上线之前，当时只有结果记录。它的实际处理过程无法追溯。">
          <span className="dsi-legacy-note">
            <InfoCircleOutlined />
            历史数据，流程状态未记录
          </span>
        </Tooltip>
      )}
    </span>
  );
}

export default DecisionStatusTag;
