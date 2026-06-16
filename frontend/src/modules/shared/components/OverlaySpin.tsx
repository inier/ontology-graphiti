/**
 * OverlaySpin - 浮层加载指示器
 * 不占用页面空间，以半透明遮罩覆盖在内容上方
 */
import React from 'react';
import { Spin } from 'antd';

interface OverlaySpinProps {
  spinning: boolean;
  tip?: string;
  children?: React.ReactNode;
  /** 容器最小高度（仅在无 children 时生效），默认 120px */
  minHeight?: number;
}

export function OverlaySpin({ spinning, tip, children, minHeight = 120 }: OverlaySpinProps) {
  // 有子内容时：Spin 包裹子内容，loading 为 overlay 遮罩
  if (children) {
    return (
      <Spin spinning={spinning} description={tip} style={{ width: '100%' }}>
        {children}
      </Spin>
    );
  }

  // 无子内容时：居中 overlay，不占布局空间
  return spinning ? (
    <div
      style={{
        position: 'relative',
        minHeight,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Spin description={tip} />
    </div>
  ) : null;
}
