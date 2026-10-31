import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

/** 未登录跳转登录页（token 由登录流程写入 localStorage） */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
