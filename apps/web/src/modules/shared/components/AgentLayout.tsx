import React, { useState, useEffect, useCallback, useMemo, useContext } from 'react';
import { Layout, Select, Button, App, ConfigProvider, theme as antdTheme } from 'antd';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { RobotOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { GlobalLoading } from './GlobalLoading';
import { LayoutHeader } from './LayoutHeader';
import { useLayoutStore, type ColorTheme } from '../stores/layoutStore';
import { WorkspaceContext, ScenarioContext, type Workspace, type Scenario } from './LayoutContexts';
import { applyColorTheme } from '../styles/colorThemeUtils';
import './OdapLayout.css';

const { Header, Sider } = Layout;

/** colorTheme → Ant Design primary color (OKLCH-based) */
const COLOR_THEME_PRIMARY: Record<string, string> = {
  indigo:  '#6366F1',
  violet:  '#8B5CF6',
  emerald: '#10B981',
  rose:    '#F43F5E',
  amber:   '#F59E0B',
};

/** Agent 模式下需要创建 tab 的路由 */
const agentRouteTabInfo: Record<string, { title: string }> = {
  '/my-agents': { title: '我的智能体' },
  '/agent-chat/new': { title: '新建对话' },
};

/* ──────────────────────────────────────────
 * AgentLayoutInner — 渲染在 <App> 内部，
 * 可以安全使用 App.useApp() 获取 message/notification/modal
 * ────────────────────────────────────────── */
function AgentLayoutInner() {
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();

  /* ── Auth ── */
  const { user, logout } = useAuthStore();

  /* ── Theme ── */
  const { theme, colorTheme, setColorTheme, setTheme, setShowTour, showTour } = useLayoutStore();

  const toggleTheme = () => setTheme(theme === 'light' ? 'dark' : 'light');

  /* ── Workspace & Scenario：从 Context 读取（由 App.tsx 统一管理） ── */
  const workspaceCtx = useContext(WorkspaceContext);
  const scenarioCtx = useContext(ScenarioContext);

  const {
    currentWorkspace: activeWorkspaceId,
    setCurrentWorkspace: setWorkspaceInContext,
    workspaces,
    reloadWorkspaces,
  } = workspaceCtx;

  const {
    currentScenario: activeScenarioId,
    setCurrentScenario: setScenarioInContext,
    scenarios,
    reloadScenarios,
  } = scenarioCtx;

  const [loading, setLoading] = useState(false);
  const [scenariosLoading, setScenariosLoading] = useState(false);

  /* ── 初始加载（仅当 Context 中数据为空时） ── */
  useEffect(() => {
    if (workspaces.length === 0) {
      setLoading(true);
      reloadWorkspaces().finally(() => setLoading(false));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeWorkspaceId && scenarios.length === 0) {
      setScenariosLoading(true);
      reloadScenarios().finally(() => setScenariosLoading(false));
    }
  }, [activeWorkspaceId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleWorkspaceChange = (value: string) => {
    setWorkspaceInContext(value);
    message.success('已切换工作空间');
  };

  const handleScenarioChange = (value: string) => {
    setScenarioInContext(value);
    message.success('已切换场景');
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleResetTour = () => {
    setShowTour(true);
    navigate('/guide');
  };

  /* ── "返回管理后台" 按钮（注入到 header 右侧） ── */
  const rightExtra = (
    <Button
      type="text"
      size="small"
      icon={<MenuFoldOutlined />}
      onClick={() => navigate('/guide')}
      style={{ color: 'var(--odap-color-text-secondary)', marginRight: 4 }}
    >
      管理后台
    </Button>
  );

  /* ── Ant Design theme (synced with theme / colorTheme) ── */
  const antdThemeConfig = useMemo(() => ({
    cssVar: {},
    algorithm: theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: COLOR_THEME_PRIMARY[colorTheme] || '#6366F1',
      borderRadius: 8,
      colorBgContainer: theme === 'dark' ? '#1F1F1F' : '#FFFFFF',
      colorBgElevated: theme === 'dark' ? '#262626' : '#FFFFFF',
      colorBgLayout: theme === 'dark' ? '#141414' : '#F8F9FC',
    },
    components: {
      Button: {
        primaryShadow: `0 2px 8px ${COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'}40`,
      },
      Input: {
        activeBorderColor: COLOR_THEME_PRIMARY[colorTheme] || '#6366F1',
        hoverBorderColor: COLOR_THEME_PRIMARY[colorTheme] || '#6366F1',
      },
      Select: {
        optionSelectedBg: `${COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'}10`,
      },
    },
  }), [theme, colorTheme]);

  return (
    <ConfigProvider theme={antdThemeConfig}>
      <Layout className="odap-layout" style={{ minWidth: 1200 }}>
        {/* 无左侧菜单 —— AgentLayout 全宽 */}

        {/* ── 共享 Header ── */}
        <LayoutHeader
          rightExtra={rightExtra}
          workspaces={workspaces}
          scenarios={scenarios}
          loading={loading}
          scenariosLoading={scenariosLoading}
          activeWorkspaceId={activeWorkspaceId}
          activeScenarioId={activeScenarioId}
          onWorkspaceChange={handleWorkspaceChange}
          onScenarioChange={handleScenarioChange}
          theme={theme}
          colorTheme={colorTheme}
          onToggleTheme={toggleTheme}
          onColorThemeChange={(c) => setColorTheme(c)}
          onResetTour={handleResetTour}
          username={user?.username || ''}
          onLogout={handleLogout}
        />

        {/* ── 主内容区：全宽，无 tab、无侧栏 ── */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            background: 'var(--odap-color-bg-secondary)',
            padding: 'var(--odap-layout-workspace-padding, 24px)',
          }}
        >
          <Outlet />
        </div>
      </Layout>
    </ConfigProvider>
  );
}

/* ──────────────────────────────────────────
 * AgentLayout — 外层壳，提供 <App> 上下文
 * ────────────────────────────────────────── */
export function AgentLayout() {
  /* ── 全局 theme 副作用（独立于 <App> 上下文） ── */
  const { theme, colorTheme } = useLayoutStore();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-color-theme', colorTheme);
    localStorage.setItem('odap-color-theme', colorTheme);
    applyColorTheme(colorTheme, theme === 'dark');
  }, [theme, colorTheme]);

  return (
    <App>
      <AgentLayoutInner />
    </App>
  );
}
