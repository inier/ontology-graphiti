/**
 * 驳回理由弹窗（uiux §5.3 动作二）
 * 校验：≥5 字（后端同样硬拒），错误就近显示在字段下方，不在顶部集中提示。
 */
import React, { useState } from 'react';
import { Input, Modal, Typography } from 'antd';

const { Text } = Typography;

interface Props {
  open: boolean;
  decisionSummary?: string;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}

const MIN_LENGTH = 5;

/**
 * 状态不靠 effect 重置：调用方给每条决策传 `key`，打开新条目即自然重建组件，
 * 避免「effect 内同步 setState」引发的级联渲染。
 */
export function RejectDecisionModal({ open, decisionSummary, submitting, onCancel, onSubmit }: Props) {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);

  const tooShort = reason.trim().length < MIN_LENGTH;
  const showError = touched && tooShort;

  return (
    <Modal
      open={open}
      title="驳回这条决策"
      okText="确认驳回"
      cancelText="取消"
      confirmLoading={submitting}
      okButtonProps={{ disabled: tooShort, danger: true }}
      onCancel={onCancel}
      onOk={() => {
        setTouched(true);
        if (!tooShort) onSubmit(reason.trim());
      }}
      destroyOnHidden
    >
      <Text type="secondary">驳回后该决策将标记为「已驳回」，不会进入执行。</Text>
      {decisionSummary ? (
        <div style={{ margin: '8px 0', color: 'var(--odap-color-text-primary)' }}>{decisionSummary}</div>
      ) : null}
      <Input.TextArea
        value={reason}
        rows={4}
        maxLength={500}
        showCount
        status={showError ? 'error' : undefined}
        placeholder="例如：库存数据是上周的，需要先更新再决策"
        onChange={(e) => setReason(e.target.value)}
        onBlur={() => setTouched(true)}
        style={{ marginTop: 8 }}
      />
      {showError && (
        <Text type="danger" style={{ fontSize: 'var(--odap-font-size-sm)' }}>
          请填写至少 5 个字，说明为什么没有采纳
        </Text>
      )}
    </Modal>
  );
}

export default RejectDecisionModal;
