/**
 * GlobalLoading - 全局浮层加载指示器
 *
 * 渲染在 AppLayout Content 层级，覆盖在页面内容上方。
 * 不占用页面空间，不影响布局。
 *
 * 由 useGlobalLoading store 控制。
 */
import React from 'react';
import { Spin } from 'antd';
import { useGlobalLoading } from '../stores/globalLoadingStore';

export function GlobalLoading() {
  const { visible, tip, delay } = useGlobalLoading();

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(255, 255, 255, 0.6)',
        backdropFilter: 'blur(2px)',
        pointerEvents: 'auto',
      }}
    >
      <Spin size="large" delay={delay} />
    </div>
  );
}
