import React, { useState, useEffect, useMemo, useContext } from 'react';
import { Layout, Button, App, ConfigProvider, theme as antdTheme } from 'antd';
import { useNavigate, Outlet } from 'react-router-dom';
import { MenuFoldOutlined } from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';
import { LayoutHeader } from './LayoutHeader';
import { useLayoutStore } from '../stores/layoutStore';
import { useTourStore } from '@/modules/guide';
import { WorkspaceContext, ScenarioContext } from './LayoutContexts';
import { useThemeRuntime } from '../styles/useThemeRuntime';
import './OdapLayout.css';
/* ──────────────────────────────────────────
 * AgentLayoutInner — 渲染在 <App> 内部，
 * 可以安全使用 App.useApp() 获取 message/notification/modal
 * ────────────────────────────────────────── */
function AgentLayoutInner({ children }: { children?: React.ReactNode }) {
  const navigate = useNavigate();
  const { message } = App.useApp();

  /* ── Auth ── */
  const { user, logout } = useAuthStore();

  /* ── Theme ── */
  const { theme, colorTheme, setColorTheme, setTheme } = useLayoutStore();
  const { resetGuideTour } = useTourStore();

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
      // 显式 async 边界：加载态在微任务里切换，避免 effect 内同步 setState 触发级联渲染
      void (async () => {
        setLoading(true);
        try {
          await reloadWorkspaces();
        } finally {
          setLoading(false);
        }
      })();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeWorkspaceId && scenarios.length === 0) {
      // 同上：把加载过程整体放进 async 边界
      void (async () => {
        setScenariosLoading(true);
        try {
          await reloadScenarios();
        } finally {
          setScenariosLoading(false);
        }
      })();
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
    resetGuideTour();
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
  const tokens = useThemeRuntime(theme, colorTheme);

  const antdThemeConfig = useMemo(() => ({
    cssVar: {},
    algorithm: theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: tokens.accentSolid,
      colorSuccess: tokens.success,
      colorWarning: tokens.warn,
      colorError: tokens.danger,
      colorInfo: tokens.info,
      colorText: tokens.fg,
      colorTextSecondary: tokens.fgSecondary,
      colorBgContainer: tokens.bgContainer,
      colorBgElevated: tokens.bgElevated,
      colorBgLayout: tokens.bgLayout,
      colorBorder: tokens.border,
      borderRadius: 8,
    },
    components: {
      Button: { primaryShadow: 'none' },
      Input: {
        activeBorderColor: tokens.accent,
        hoverBorderColor: tokens.accentBorder,
      },
      Select: {
        optionSelectedBg: tokens.accentSubtle,
      },
    },
  }), [theme, tokens]);

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
          {/* App.tsx 以 `<AgentLayout><AppRoutes/></AgentLayout>` 方式挂载时用 children；
              作为路由 layout 使用时退回 <Outlet/>。 */}
          {children ?? <Outlet />}
        </div>
      </Layout>
    </ConfigProvider>
  );
}

/* ──────────────────────────────────────────
 * AgentLayout — 外层壳，提供 <App> 上下文
 * ────────────────────────────────────────── */
export function AgentLayout({ children }: { children?: React.ReactNode }) {
  /* ── 全局 theme 副作用（独立于 <App> 上下文） ── */
  const { theme, colorTheme } = useLayoutStore();

  useEffect(() => {
    localStorage.setItem('odap-color-theme', colorTheme);
  }, [theme, colorTheme]);

  return (
    <App>
      <AgentLayoutInner>{children}</AgentLayoutInner>
    </App>
  );
}
