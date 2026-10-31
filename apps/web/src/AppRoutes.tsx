/**
 * 应用路由装配（数据驱动）
 *
 * 路由定义全部来自 routes/routeDefs.tsx（单一真源），本文件只负责布局嵌套：
 *   /login            —— 公开
 *   KeepAliveOutlet   —— 受保护布局（缓存各页面状态）
 */
import { Routes, Route } from 'react-router-dom';
import { LoginPage } from '@/modules/shared/pages/LoginPage';
import { KeepAliveOutlet } from '@/modules/shared/components/KeepAliveOutlet';
import { APP_ROUTE_DEFS } from './routes/routeDefs';
import { LegacyRedirect } from './routes/LegacyRedirect';
import { ProtectedRoute } from './routes/ProtectedRoute';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<KeepAliveOutlet />}>
        {APP_ROUTE_DEFS.map((def) =>
          def.kind === 'page' ? (
            <Route
              key={def.path}
              path={def.path}
              element={<ProtectedRoute>{def.element}</ProtectedRoute>}
            />
          ) : (
            <Route
              key={def.path}
              path={def.path}
              element={<LegacyRedirect from={def.path} to={def.to} reason={def.reason} />}
            />
          ),
        )}
      </Route>
    </Routes>
  );
}
