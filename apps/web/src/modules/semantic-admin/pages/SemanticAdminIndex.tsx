/**
 * 语义管理首页：/semantic-admin 根路由
 * - 顶部 4 Tab 导航（USL / Pipeline / Candidates / Quality）
 * - 通过 URL searchParams 或 navigate 切换子路由
 * - 此页也作为 4 个子页的共用 Tab 栏容器
 */
import React, { useMemo } from 'react';
import { Card, Tabs } from 'antd';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useSemanticAdminStore, type AdminTopTab } from '../store/useSemanticAdminStore';
import { getSemanticAdminTabItems, TOP_TAB_TO_PATH, PATH_TO_TOP_TAB } from '../constants';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export interface SemanticAdminTabsContainerProps {
  children: React.ReactNode;
}

export function SemanticAdminTabsContainer({ children }: SemanticAdminTabsContainerProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const setTopTab = useSemanticAdminStore((s) => s.setCurrentTopTab);
  const { t } = useI18n();

  const activeKey = useMemo<AdminTopTab>(() => {
    const match = PATH_TO_TOP_TAB[location.pathname] || 'usl';
    // 轻量同步 store（避免 setState-in-effect）
    queueMicrotask(() => setTopTab(match));
    return match;
  }, [location.pathname, setTopTab]);

  const tabItems = useMemo(() => getSemanticAdminTabItems(t), [t]);

  const handleChange = (key: string) => {
    const target = TOP_TAB_TO_PATH[key as AdminTopTab] || TOP_TAB_TO_PATH.usl;
    navigate(target);
  };

  return (
    <div style={{ padding: 16 }}>
      <Card styles={{ body: { padding: '0 16px 16px' } }} variant="borderless">
        <Tabs
          activeKey={activeKey}
          onChange={handleChange}
          items={tabItems}
          size="large"
          style={{ marginBottom: 8 }}
        />
        {children}
      </Card>
    </div>
  );
}

/**
 * /semantic-admin 根路由 → 自动跳转到 /semantic-admin/usl
 */
export function SemanticAdminIndex() {
  return <Navigate to="/semantic-admin/usl" replace />;
}
