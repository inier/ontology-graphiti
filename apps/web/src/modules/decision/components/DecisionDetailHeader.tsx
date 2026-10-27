/**
 * 详情页头部：面包屑 + 决策 ID + 状态标签 + 裁决动作
 *
 * 权限口径（PRD §5.6）：无裁决权限时按钮 **禁用 + Tooltip「需要决策审批权限」**，
 * 不整页 403、不空白；**不适用**（当前状态不可裁决）时按钮**不渲染**，改一行说明 ——
 * 「你没权限」与「这个动作对谁都不存在」是两种语义，不得混用禁用态。
 */
import React from 'react';
import { App, Breadcrumb, Button, Skeleton, Space, Tooltip, Typography } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import type { DecisionRecord } from '../types';
import { DecisionStatusTag } from './DecisionStatusTag';

const { Text } = Typography;

interface Props {
  decisionId: string;
  decision?: DecisionRecord | null;
  loading: boolean;
  busy: boolean;
  permissionDenied: boolean;
  onBack: () => void;
  onCopyId: (id: string) => void;
  onApprove: () => void;
  onReject: (reason: string) => void;
}

const PERMISSION_TIP = '需要决策审批权限';

export function DecisionDetailHeader({
  decisionId,
  decision,
  loading,
  busy,
  permissionDenied,
  onBack,
  onCopyId,
  onApprove,
  onReject,
}: Props) {
  const { modal, message } = App.useApp();
  // `status_assumed` 的记录**不提供裁决入口**：它的 status 是迁移时推定的，
  // 不是真实流程状态，允许在此裁决等于让用户对一个猜测盖章
  const assumed = Boolean(decision?.status_assumed);
  const resolvable = decision?.status === 'pending' && !assumed;
  const disabled = permissionDenied || busy;

  const openRejectModal = () => {
    let reason = '';
    modal.confirm({
      title: '驳回这条决策',
      content: (
        <div>
          <Text type="secondary">驳回后该决策将标记为「已驳回」，不会进入执行。</Text>
          <textarea
            aria-label="驳回理由"
            placeholder="请填写至少 5 个字，说明为什么没有采纳"
            style={{ width: '100%', marginTop: 8, minHeight: 72 }}
            onChange={(e) => {
              reason = e.target.value;
            }}
          />
        </div>
      ),
      okText: '确认驳回',
      okButtonProps: { danger: true },
      onOk: async () => {
        if (reason.trim().length < 5) {
          message.warning('请填写至少 5 个字，说明为什么没有采纳');
          throw new Error('驳回理由不足 5 字');
        }
        onReject(reason.trim());
      },
    });
  };

  return (
    <>
      <Breadcrumb
        items={[{ title: '决策台账', onClick: onBack }, { title: decisionId }]}
        style={{ marginBottom: 'var(--odap-spacing-sm)' }}
      />

      <Space
        align="center"
        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}
      >
        <Space size={8} wrap>
          <Text style={{ fontFamily: 'var(--odap-font-family-mono)' }}>{decisionId}</Text>
          <CopyOutlined
            style={{ fontSize: 16, cursor: 'pointer' }}
            aria-label="复制决策 ID"
            onClick={() => onCopyId(decisionId)}
          />
          {loading ? (
            <Skeleton.Button active size="small" style={{ width: 120 }} />
          ) : (
            decision && (
              <DecisionStatusTag
                status={decision.status}
                outcome={decision.outcome}
                statusAssumed={decision.status_assumed}
              />
            )
          )}
        </Space>

        <Space size={8}>
          {resolvable ? (
            <>
              <Tooltip title={permissionDenied ? PERMISSION_TIP : undefined}>
                <Button danger disabled={disabled} onClick={openRejectModal}>
                  驳回
                </Button>
              </Tooltip>
              <Tooltip title={permissionDenied ? PERMISSION_TIP : undefined}>
                <Button type="primary" loading={busy} disabled={disabled} onClick={onApprove}>
                  采纳
                </Button>
              </Tooltip>
            </>
          ) : assumed ? (
            // 显式标注，不用 Tooltip：截图/打印/键盘操作下 Tooltip 等于不存在
            <Text type="secondary" style={{ maxWidth: 360 }}>
              历史数据，流程状态未记录：该状态是迁移时推定的，不能作为验收依据，因此不提供裁决/执行入口
            </Text>
          ) : (
            <Text type="secondary">
              {decision
                ? '该决策当前状态不可裁决，裁决入口只在待裁定阶段可用'
                : '决策加载中，暂无可执行动作'}
            </Text>
          )}
        </Space>
      </Space>
    </>
  );
}

export default DecisionDetailHeader;
