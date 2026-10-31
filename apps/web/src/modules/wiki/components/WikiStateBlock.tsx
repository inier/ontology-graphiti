/**
 * 四态块：Loading / Empty / Error 的统一表现层。
 *
 * 错误态强制展示后端 `error_code` 与 `message`（SPEC §5：错误码必须具体，
 * 禁止"加载失败"式模糊文案；用户要求可诊断）。
 */
import type { ReactNode } from 'react';
import { Button } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import type { WikiErrorInfo } from '../services/wikiError';
import type { LoadPhase } from '../stores/wikiStore';

export interface WikiStateBlockProps {
  phase: LoadPhase;
  error: WikiErrorInfo | null;
  emptyTitle: string;
  emptyDesc: string;
  /** 数据为就绪但结果集为空 */
  isEmpty?: boolean;
  onRetry?: () => void;
  /** Loading 骨架数量 */
  skeletonCount?: number;
  children: ReactNode;
}

export function WikiStateBlock({
  phase,
  error,
  emptyTitle,
  emptyDesc,
  isEmpty = false,
  onRetry,
  skeletonCount = 3,
  children,
}: WikiStateBlockProps) {
  if (phase === 'loading' || phase === 'idle') {
    return (
      <div className="wiki-card-list" aria-busy="true" aria-live="polite">
        {Array.from({ length: skeletonCount }, (_, i) => (
          <div key={i} className="wiki-skeleton" />
        ))}
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <div className="wiki-state" role="alert">
        <Icon role="error" size={24} />
        <div className="wiki-state__title">无法加载 Wiki 数据</div>
        {error ? (
          <>
            <div className="wiki-state__code">{error.errorCode}</div>
            <div className="wiki-state__desc">{error.message}</div>
            {error.conflictingId ? (
              <div className="wiki-state__desc">冲突对象：{error.conflictingId}</div>
            ) : null}
            {error.traceId ? <div className="wiki-state__trace">trace_id: {error.traceId}</div> : null}
          </>
        ) : (
          <div className="wiki-state__desc">后端未返回错误详情</div>
        )}
        {onRetry ? (
          <Button onClick={onRetry} icon={<Icon role="retry" size={16} />}>
            重试
          </Button>
        ) : null}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="wiki-state">
        <Icon role="empty" size={24} />
        <div className="wiki-state__title">{emptyTitle}</div>
        <div className="wiki-state__desc">{emptyDesc}</div>
      </div>
    );
  }

  return <>{children}</>;
}
