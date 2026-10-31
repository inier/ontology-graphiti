/**
 * 旧路由重定向组件（F4 / AC-18）
 *
 * 行为：挂载时上报 `route_redirect` 埋点，然后 `<Navigate replace/>`。
 * 用 replace 而非 push，避免用户"后退"回一个立刻再次重定向的地址。
 */
import { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { trackRouteRedirect } from '@/modules/shared/utils/analytics';

export interface LegacyRedirectProps {
  from: string;
  to: string;
  reason: string;
}

export function LegacyRedirect({ from, to, reason }: LegacyRedirectProps) {
  useEffect(() => {
    trackRouteRedirect(from, to, reason);
  }, [from, to, reason]);

  return <Navigate to={to} replace />;
}
