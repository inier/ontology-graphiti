/**
 * T070 AIInlineCompletion — 属性名输入时的行内类型推断补全
 *
 * 功能：
 * - 监听属性名输入，debounce 300ms 后调用类型推断
 * - 在输入框下方显示推断类型 + 约束建议
 * - Tab/Enter 接受建议，Esc 关闭
 *
 * 使用场景：
 * - ObjectTypeEditor 属性名输入框
 * - 用户输入 "email" → 显示 "STRING + email 约束"
 */

import { useState, useEffect, useRef } from 'react';
import { Tag, Spin, Tooltip } from 'antd';
import { ThunderboltOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useTypeInference } from '../hooks/useTypeInference';

export interface AIInlineCompletionProps {
  /** 当前属性名 */
  propertyName: string;
  /** 当前已选数据类型 */
  currentDataType?: string;
  /** 接受建议时回调（返回推断的类型 + 约束） */
  onAccept: (suggestion: {
    inferredType: string;
    constraints?: Record<string, unknown>;
  }) => void;
  /** 拒绝建议时回调 */
  onReject?: () => void;
  /** 是否禁用 */
  disabled?: boolean;
}

export function AIInlineCompletion({
  propertyName,
  currentDataType,
  onAccept,
  onReject,
  disabled = false,
}: AIInlineCompletionProps) {
  const { inference, loading, inferType, reset } = useTypeInference();
  const lastQueriedRef = useRef<string>('');
  // 跟踪已被用户忽略的属性名；属性名变化时自动重置（render 期间调整 state，合法模式）
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);
  const [prevPropertyName, setPrevPropertyName] = useState(propertyName);

  if (prevPropertyName !== propertyName) {
    setPrevPropertyName(propertyName);
    setDismissedFor(null);
  }

  // 属性名变化时触发推断（不在 effect 内调用 setState，仅启动外部异步操作）
  useEffect(() => {
    if (disabled || !propertyName || propertyName.trim().length < 2) {
      reset();
      lastQueriedRef.current = '';
      return;
    }

    // 避免重复查询相同名称
    if (propertyName === lastQueriedRef.current) return;
    lastQueriedRef.current = propertyName;

    inferType(propertyName);
  }, [propertyName, disabled, inferType, reset]);

  // 渲染期间派生可见性
  const isDismissed = dismissedFor === propertyName;
  const visible = !isDismissed && !disabled && propertyName.trim().length >= 2;

  const handleAccept = () => {
    if (inference) {
      onAccept({
        inferredType: inference.inferredType,
        constraints: inference.constraints,
      });
    }
    setDismissedFor(propertyName);
  };

  const handleReject = () => {
    onReject?.();
    setDismissedFor(propertyName);
    reset();
  };

  // 不显示的条件
  if (!visible) return null;
  if (loading && !inference) {
    return (
      <div
        style={{
          position: 'absolute',
          zIndex: 1050,
          background: '#fff',
          border: '1px solid #d9d9d9',
          borderRadius: 4,
          padding: '4px 8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <Spin size="small" />
        <span style={{ color: '#999' }}>AI 推断中...</span>
      </div>
    );
  }

  if (!inference || inference.confidence === 0) return null;

  // 如果推断类型与当前类型相同，不显示
  if (currentDataType && inference.inferredType === currentDataType) return null;

  const confidenceColor = inference.confidence >= 0.8 ? 'green' : inference.confidence >= 0.5 ? 'blue' : 'orange';
  const matchRuleLabel: Record<string, string> = {
    exact: '精确匹配',
    prefix: '前缀匹配',
    suffix: '后缀匹配',
    contains: '包含匹配',
    default: '默认',
  };

  return (
    <div
      style={{
        position: 'absolute',
        zIndex: 1050,
        background: '#fff',
        border: '1px solid #d9d9d9',
        borderRadius: 4,
        padding: '6px 10px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
        fontSize: 12,
        minWidth: 200,
        maxWidth: 320,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <ThunderboltOutlined style={{ color: '#722ed1' }} />
        <span style={{ fontWeight: 500, color: '#722ed1' }}>AI 建议</span>
        <Tag color={confidenceColor} style={{ marginLeft: 'auto', fontSize: 11 }}>
          {Math.round(inference.confidence * 100)}%
        </Tag>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>推荐类型:</span>
        <Tag color="purple" style={{ fontWeight: 600 }}>
          {inference.inferredType}
        </Tag>
        <Tooltip title={matchRuleLabel[inference.matchRule] || inference.matchRule}>
          <Tag style={{ fontSize: 10, color: '#999' }}>{matchRuleLabel[inference.matchRule] || inference.matchRule}</Tag>
        </Tooltip>
      </div>
      {inference.constraints && Object.keys(inference.constraints).length > 0 && (
        <div style={{ marginTop: 4, color: '#666' }}>
          <span>约束: </span>
          {Object.keys(inference.constraints).map((k) => (
            <Tag key={k} style={{ fontSize: 10 }}>
              {k}
            </Tag>
          ))}
        </div>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <a
          style={{ fontSize: 11, color: '#999', cursor: 'pointer' }}
          onClick={handleReject}
        >
          <CloseOutlined /> 忽略
        </a>
        <a
          style={{ fontSize: 11, color: '#722ed1', cursor: 'pointer', fontWeight: 500 }}
          onClick={handleAccept}
        >
          <CheckOutlined /> 接受 (Tab)
        </a>
      </div>
    </div>
  );
}
