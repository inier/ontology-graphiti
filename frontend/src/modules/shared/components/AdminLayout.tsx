import React, { useState, useEffect, useCallback, useRef, useMemo, useContext } from 'react';
import { Layout, Menu, Select, Spin, App, Button, Tooltip, Dropdown, Badge, ConfigProvider, theme as antdTheme, Drawer } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  BlockOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  TeamOutlined,
  FileTextOutlined,
  AuditOutlined,
  AppstoreOutlined,
  ApartmentOutlined,
  BranchesOutlined,
  NodeIndexOutlined,
  FundOutlined,
  DatabaseOutlined,
  FileProtectOutlined,
  UnorderedListOutlined,
  ExperimentOutlined,
  RobotOutlined,
  SwitcherOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SafetyOutlined,
  LogoutOutlined,
  UserOutlined,
  PartitionOutlined,
  HistoryOutlined,
  ApiOutlined,
  CompassOutlined,
  QuestionCircleOutlined,
  GlobalOutlined,
  BookOutlined,
  RightOutlined,
  LeftOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { applyColorTheme } from '../styles/colorThemeUtils';
import { GlobalLoading } from './GlobalLoading';
import { TaskPanel } from './TaskPanel';
import { QuickActionBar } from './QuickActionBar';
import { ExtensionPanel } from './ExtensionPanel';
import { LayoutHeader } from './LayoutHeader';
import { TabDetailPreview } from './TabDetailPreview';
import { AIChatPanel } from '@/modules/ai-assistant';
import { useLayoutStore, type TaskTab, type QuickAction, type ColorTheme, type ExtensionSpec } from '../stores/layoutStore';
import { useTourStore } from '@/modules/guide';
import {
  WorkspaceContext,
  ScenarioContext,
  OntologyVersionContext,
  RightPanelContext,
  type Workspace,
  type Scenario,
} from './LayoutContexts';
import './OdapLayout.css';

const { Header, Sider } = Layout;

/* ── Extension icon resolution (iconName → React element) ──
 *   新增扩展只需在此处添加映射条目 */
const EXTENSION_ICON_MAP: Record<string, React.ReactNode> = {
  robot: <RobotOutlined />,
  'file-text': <FileTextOutlined />,
};

/** Map colorTheme → primary color (kept in sync with global.css) */
const COLOR_THEME_PRIMARY: Record<string, string> = {
  indigo: '#6366F1',
  blue:   '#3B82F6',
  green:  '#10B981',
  violet: '#8B5CF6',
  amber:  '#F59E0B',
};

/** extension id → component mapping ── 新增扩展在此注册渲染组件 */
const EXTENSION_COMPONENT_MAP: Record<string, React.ComponentType> = {
  'ai-chat': AIChatPanel,
  'tab-preview': TabDetailPreview,
};

/** 内置扩展定义（ProLayout 挂载时自动注册到 store） */
const BUILTIN_EXTENSIONS: ExtensionSpec[] = [
  { id: 'ai-chat', name: 'AI 助手', iconName: 'robot', order: 0 },
  { id: 'tab-preview', name: 'Tab 详情', iconName: 'file-text', order: 1 },
];
/* ── Menu Definition ── */

interface MenuItem {
  key: string;
  icon: React.ReactNode;
  label: string;
  children?: { key: string; icon?: React.ReactNode; label: string }[];
}

const primaryMenus: MenuItem[] = [
  {
    key: 'guide',
    icon: <BookOutlined />,
    label: '快速指南',
    children: [{ key: '/guide', icon: <BookOutlined />, label: '系统指南' }],
  },
  {
    key: 'ontology-map',
    icon: <BlockOutlined />,
    label: '语义地图',
    children: [
      { key: '/ontology/designer', icon: <BlockOutlined />, label: '本体设计器' },
      { key: '/ontology/graph', icon: <ApartmentOutlined />, label: '语义图谱' },
      { key: '/business/entities', icon: <UnorderedListOutlined />, label: '对象管理' },
      { key: '/business/process', icon: <BranchesOutlined />, label: '业务过程' },
      { key: '/business/rules', icon: <FileProtectOutlined />, label: '规则' },
      { key: '/business/indicators', icon: <FundOutlined />, label: '指标' },
      { key: '/business/logic', icon: <NodeIndexOutlined />, label: '逻辑' },
      { key: '/ingest', icon: <ExperimentOutlined />, label: '数据摄入' },
      { key: '/blueprint', icon: <PartitionOutlined />, label: '蓝图设计' },
      { key: '/versions', icon: <HistoryOutlined />, label: '版本历史' },
    ],
  },
  {
    key: 'agent',
    icon: <RobotOutlined />,
    label: '智能体',
    children: [
      { key: '/agent', icon: <ApiOutlined />, label: 'Agent调度' },
      { key: '/admin/agents', icon: <TeamOutlined />, label: '智能体管理' },
      { key: '/skills', icon: <AppstoreOutlined />, label: 'Skill管理' },
    ],
  },
  {
    key: 'simulation',
    icon: <ThunderboltOutlined />,
    label: '推演仿真',
    children: [
      { key: '/simulation', icon: <ThunderboltOutlined />, label: '沙箱推演' },
      { key: '/simulator', icon: <ExperimentOutlined />, label: '事件模拟' },
      { key: '/simulation/deduction', icon: <SafetyOutlined />, label: '策略推演' },
    ],
  },
  {
    key: 'knowledge',
    icon: <DatabaseOutlined />,
    label: '知识检索',
    children: [
      { key: '/knowledge', icon: <DatabaseOutlined />, label: '知识库' },
      { key: '/knowledge/navigation', icon: <CompassOutlined />, label: '知识导航' },
    ],
  },
  {
    key: 'system',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/workspace/manage', icon: <BlockOutlined />, label: '工作空间' },
      { key: '/policy-editor', icon: <FileTextOutlined />, label: '策略编辑器' },
      { key: '/users', icon: <UserOutlined />, label: '用户管理' },
      { key: '/roles', icon: <TeamOutlined />, label: '角色管理' },
      { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
      { key: '/i18n-admin', icon: <GlobalOutlined />, label: '国际化' },
      { key: '/settings/channels/default', icon: <MessageOutlined />, label: 'IM渠道' },
      { key: '/settings', icon: <SettingOutlined />, label: '系统配置' },
    ],
  },
];

/* Build flat route → tab info map */
const routeTabInfo: Record<string, { title: string }> = {};
primaryMenus.forEach((m) => {
  if (m.children) {
    m.children.forEach((c) => {
      routeTabInfo[c.key] = { title: c.label };
    });
  } else {
    routeTabInfo[m.key] = { title: m.label };
  }
});
routeTabInfo['/my-agents'] = { title: '我的智能体' };
routeTabInfo['/agent-chat'] = { title: '智能体对话' };
routeTabInfo['/qa'] = { title: '问答引擎' };

/* ── Resize Handle (inline, absolute-position based) ── */

interface ResizeHandleProps {
  /** 拖拽结束时回调绝对百分比值（非增量），消除累计误差 */
  onResize: (absolutePercent: number) => void;
  /** 当前面板尺寸百分比（拖拽起始基准） */
  startSizePercent: number;
  /** 反转拖拽方向：右侧面板拖拽向左时应增大 */
  invert?: boolean;
  direction?: 'horizontal' | 'vertical';
  onToggle?: () => void;
  collapsed?: boolean;
}

function ResizeHandle({
  onResize,
  startSizePercent,
  invert = false,
  direction = 'horizontal',
  onToggle,
  collapsed = false,
}: ResizeHandleProps) {
  // ref 保持最新的起始尺寸，避免 useCallback 闭包捕获旧值
  const startSizeRef = useRef(startSizePercent);
  startSizeRef.current = startSizePercent;

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (collapsed) return;
      e.preventDefault();
      e.stopPropagation();

      const container = (e.currentTarget as HTMLElement).parentElement;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const startPos = direction === 'horizontal' ? e.clientX : e.clientY;
      const containerSize = direction === 'horizontal' ? rect.width : rect.height;
      // 🔧 关键修复：mousedown 时锁定起始尺寸，绝对计算避免累积误差
      const lockedStartSize = startSizeRef.current;

      const handleMouseMove = (ev: MouseEvent) => {
        const currentPos = direction === 'horizontal' ? ev.clientX : ev.clientY;
        const delta = currentPos - startPos;
        const deltaPercent = (delta / containerSize) * 100;
        // invert: 右侧面板向左拖时应增大，所以取反
        const newAbsolute = invert
          ? lockedStartSize - deltaPercent
          : lockedStartSize + deltaPercent;
        onResize(newAbsolute);
      };

      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
      document.body.style.userSelect = 'none';
    },
    [onResize, direction, collapsed, invert],
  );

  return (
    <div
      className={`odap-resize-handle ${direction} ${collapsed ? 'collapsed' : ''}`}
      onMouseDown={handleMouseDown}
      onDoubleClick={onToggle}
    >
      {onToggle && (
        <button
          className="odap-resize-toggle-btn"
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          title={collapsed ? '展开' : '折叠'}
        >
          {collapsed
            ? direction === 'horizontal'
              ? '›'
              : '∧'
            : direction === 'horizontal'
              ? '‹'
              : '∨'}
        </button>
      )}
    </div>
  );
}

/* ── ProLayout ── */

export function AdminLayout({ children }: { children: React.ReactNode }) {
  /* ── Context：工作空间 / 场景（由 App.tsx 统一管理） ── */
  const workspaceCtx = useContext(WorkspaceContext);
  const scenarioCtx  = useContext(ScenarioContext);

  const {
    currentWorkspace: activeWorkspaceId,
    setCurrentWorkspace: setWorkspaceInContext,
    workspaces,
    reloadWorkspaces,
  } = workspaceCtx;

  const {
    currentScenario: currentScenarioState,
    setCurrentScenario: setScenarioInContext,
    scenarios,
    reloadScenarios,
  } = scenarioCtx;

  /* ── Left menu: collapsed by default ── */
  const [leftCollapsed, setLeftCollapsed] = useState(true);
  const [openKeys, setOpenKeys] = useState<string[]>([]);

  /* ── 加载状态（UI 用，数据来自 Context） ── */
  const [loading, setLoading]             = useState(false);
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

  /* ── Right panel (legacy context) ── */
  const [showRightPanel, setShowRightPanel]     = useState(false);
  const [rightPanelContent, setRightPanelContent] = useState<React.ReactNode>(null);
  const [rightPanelTitle, setRightPanelTitle]     = useState('');

  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { resetGuideTour } = useTourStore();
  const { message } = App.useApp();

  /* ── Layout store ── */
  const {
    taskPanelCollapsed,
    extensionPanelCollapsed,
    taskPanelWidth,
    extensionPanelWidth,
    extensionHold,
    quickActionHeight,
    toggleTaskPanel,
    toggleExtensionPanel,
    toggleExtensionHold,
    setTaskPanelWidth,
    setExtensionPanelWidth,
    setQuickActionHeight,
    openTab,
    theme,
    setTheme,
    colorTheme,
    setColorTheme,
    previewTabId,
    setPreviewTab,
    tabs,
    extensionSpecs,
    activeExtensionId,
    registerExtension,
    unregisterExtension,
    setActiveExtension,
  } = useLayoutStore();

  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('odap-theme', theme);
  }, [theme]);

  /* Sync color theme to DOM + CSS variables */
  useEffect(() => {
    document.documentElement.setAttribute('data-color-theme', colorTheme);
    localStorage.setItem('odap-color-theme', colorTheme);
    applyColorTheme(colorTheme, theme === 'dark');
  }, [colorTheme, theme]);

  /* Register built-in extensions on mount */
  useEffect(() => {
    BUILTIN_EXTENSIONS.forEach((ext) => registerExtension(ext));
    // Set default active extension if none selected
    if (!activeExtensionId) {
      setActiveExtension('ai-chat');
    }
    return () => {
      BUILTIN_EXTENSIONS.forEach((ext) => unregisterExtension(ext.id));
    };
    // Only run on mount/unmount
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Derived: active extension spec ── */
  const activeExtensionSpec = extensionSpecs.find((e) => e.id === activeExtensionId) ?? null;
  const activeExtensionIcon = activeExtensionSpec
    ? EXTENSION_ICON_MAP[activeExtensionSpec.iconName] ?? <BlockOutlined />
    : null;
  const activeExtensionComponent = activeExtensionId
    ? EXTENSION_COMPONENT_MAP[activeExtensionId] ?? null
    : null;

  const toggleTheme = () => setTheme(theme === 'light' ? 'dark' : 'light');

  /* 全宽模式：agent-chat 对话页 和 我的智能体列表 均隐藏两侧面板、不创建 tab */
  const isFullWidthMode = false;  // AdminLayout: always show 3-column
  /* 智能体区域：用于切换按钮文案 */
  const isAgentArea = false;  // AdminLayout

  const handleWorkspaceChange = (value: string) => {
    setWorkspaceInContext(value);
    if (message && typeof message.success === 'function') {
      message.success('已切换工作空间');
    }
  };

  const handleScenarioChange = (value: string) => {
    setScenarioInContext(value);
    if (message && typeof message.success === 'function') {
      message.success('已切换场景');
    }
  };

  /* ── Navigation → Tab integration ── */
  useEffect(() => {
    // AdminLayout: always create tabs
    const path = location.pathname;
    const info = routeTabInfo[path] || routeTabInfo['/' + path.split('/')[1]];
    if (info) {
      openTab({ id: path, title: info.title, path });
    }
  }, [location.pathname, isFullWidthMode, openTab]);

  /* ── Determine active menu keys ── */
  const activeMenuKey = (() => {
    const path = location.pathname;
    for (const m of primaryMenus) {
      if (m.children) {
        for (const c of m.children) {
          if (c.key === path || c.key === '/' + path.split('/')[1]) {
            return c.key;
          }
        }
      }
    }
    return path;
  })();

  const activeParentKey = (() => {
    const path = location.pathname;
    for (const m of primaryMenus) {
      if (m.children) {
        for (const c of m.children) {
          if (c.key === path || c.key === '/' + path.split('/')[1]) {
            return m.key;
          }
        }
      }
    }
    return '';
  })();

  /* Auto-open the active parent's submenu when menu expands —
     use "store previous state" pattern to avoid setState-in-effect cascading renders */
  const [prevAutoOpenKey, setPrevAutoOpenKey] = useState<string>('');
  if (!leftCollapsed && activeParentKey && activeParentKey !== prevAutoOpenKey) {
    setPrevAutoOpenKey(activeParentKey);
    if (!openKeys.includes(activeParentKey)) {
      setOpenKeys((prev) => [...prev, activeParentKey]);
    }
  }

  const parentMenuKeys = useMemo(() => primaryMenus.map(m => m.key), []);

  const menuClickRef = useRef(0);

  const handleMenuMouseDown = () => {
    menuClickRef.current = Date.now();
  };

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (leftCollapsed && parentMenuKeys.includes(key)) {
      setLeftCollapsed(false);
      setOpenKeys([key]);
      return;
    }
    navigate(key);
  };

  const handleOpenChange = (keys: string[]) => {
    if (leftCollapsed && keys.length > 0) {
      if (Date.now() - menuClickRef.current < 300) {
        setLeftCollapsed(false);
        setOpenKeys(keys);
      }
      return;
    }
    setOpenKeys(keys);
  };

  const handleLogoClick = () => {
    navigate('/guide');
  };

  const handleSwitchMode = () => {
    if (isAgentArea) {
      navigate('/ontology/designer');
    } else {
      navigate('/my-agents');
    }
  };

  /* ── Tab click → navigate + switch extension to tab-preview + expand ── */
  const handleTabClick = useCallback(
    (tab: TaskTab) => {
      navigate(tab.path);
      setPreviewTab(tab.id);
      setActiveExtension('tab-preview');
      if (extensionPanelCollapsed) {
        toggleExtensionPanel();
      }
    },
    [navigate, setPreviewTab, setActiveExtension, extensionPanelCollapsed, toggleExtensionPanel],
  );

  /* ── Tab refresh: refreshToken 递增触发 <Activity> key 变化，React 自动重建组件 ──
   *  不需要 navigate — refreshTab 已在 TaskPanel 中调用 store 更新 refreshToken，
   *  KeepAliveOutlet 检测到变化后更新缓存，key 变化导致 <Activity> 重建 */
  const handleTabRefresh = useCallback(() => {
    /* no-op: refreshTab in TaskPanel already handles the store update */
  }, []);

  /* ── Quick action click → navigate ── */
  const handleQuickActionClick = useCallback(
    (action: QuickAction) => {
      navigate(action.path);
    },
    [navigate],
  );

  /* ── Resize handlers for 3-column layout (absolute-position based) ── */
  const handleTaskPanelResize = useCallback(
    (absolutePercent: number) => {
      setTaskPanelWidth(absolutePercent);
    },
    [setTaskPanelWidth],
  );

  const handleExtensionPanelResize = useCallback(
    (absolutePercent: number) => {
      // 扩展区从右侧拖拽，delta 是反方向的，这里用 startSize - (absolute - startSize) 保持语义
      setExtensionPanelWidth(absolutePercent);
    },
    [setExtensionPanelWidth],
  );

  /* ── OntologyVersion（供子组件读取） ── */
  const currentScenarioObj = scenarios.find((s) => s.scenario_id === currentScenarioState);
  const ontologyVersionContextValue = {
    currentOntologyId: currentScenarioObj?.ontology_id || '',
    currentVersionId: currentScenarioObj?.current_ontology_version || '',
  };

  /* ── RightPanel context value ── */
  const rightPanelContextValue = {
    showRightPanel,
    setShowRightPanel,
    rightPanelContent,
    setRightPanelContent,
    rightPanelTitle,
    setRightPanelTitle,
  };

  /* ── Menu items for Ant Design Menu ── */
  const menuItems: MenuProps['items'] = primaryMenus.map((m) => ({
    key: m.key,
    icon: m.icon,
    label: m.label,
    children: m.children?.map((c) => ({
      key: c.key,
      icon: c.icon,
      label: c.label,
    })),
  }));

  /* ── Ant Design theme (synced with theme / colorTheme) ── */
  const antdThemeConfig = useMemo(() => ({
    cssVar: true,
    algorithm: theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: COLOR_THEME_PRIMARY[colorTheme] || '#6366F1',
      borderRadius: 8,
      colorBgContainer: theme === 'dark' ? '#1F1F1F' : '#FFFFFF',
      colorBgElevated: theme === 'dark' ? '#262626' : '#FFFFFF',
      colorBgLayout: theme === 'dark' ? '#141414' : '#F8F9FC',
    },
    components: {
      Menu: {
        darkItemBg: 'transparent',
        darkSubMenuItemBg: 'rgba(255,255,255,0.04)',
        darkItemSelectedBg: `${COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'}40`,
        darkItemHoverBg: 'rgba(255,255,255,0.08)',
        darkItemColor: 'rgba(255,255,255,0.65)',
        darkItemHoverColor: '#ffffff',
        darkItemSelectedColor: '#ffffff',
        itemBg: theme === 'dark' ? 'transparent' : '#FFFFFF',
        subMenuItemBg: theme === 'dark' ? 'rgba(255,255,255,0.04)' : '#F8F9FC',
        itemSelectedBg: `${COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'}20`,
        itemHoverBg: `${COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'}10`,
        itemColor: theme === 'dark' ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.88)',
        itemHoverColor: theme === 'dark' ? '#ffffff' : (COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'),
        itemSelectedColor: theme === 'dark' ? '#ffffff' : (COLOR_THEME_PRIMARY[colorTheme] || '#6366F1'),
      },
      Button: {
        primaryShadow: `0 2px 8px ${(COLOR_THEME_PRIMARY[colorTheme] || '#6366F1')}40`,
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

  const leftSiderWidth = leftCollapsed ? 48 : 200;

  return (
    <ConfigProvider theme={antdThemeConfig}>
      <App>
        <OntologyVersionContext.Provider value={ontologyVersionContextValue}>
          <RightPanelContext.Provider value={rightPanelContextValue}>
            <Layout className="odap-layout" style={{ minWidth: 1200 }}>
              {/* ── Column 1 (Left): Menu Area — collapsed by default ── */}
              {!isFullWidthMode && (
                <Sider
                  trigger={null}
                  collapsed={leftCollapsed}
                  collapsedWidth={48}
                  width={200}
                  style={{
                    overflow: 'auto',
                    height: '100vh',
                    position: 'fixed',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    zIndex: 100,
                    background: 'var(--odap-sidebar-bg)',
                    borderRight: 'var(--odap-sidebar-border)',
                    transition: 'width 350ms cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  {/* Logo */}
                  <div
                    style={{
                      height: 48,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#ffffff',
                      fontSize: leftCollapsed ? 16 : 18,
                      fontWeight: 700,
                      letterSpacing: '0.05em',
                      borderBottom: 'var(--odap-sidebar-border)',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      background: leftCollapsed
                        ? 'transparent'
                        : 'var(--odap-sidebar-logo-bg)',
                    }}
                    onClick={handleLogoClick}
                  >
                    <span
                      style={{
                        background: leftCollapsed
                          ? 'none'
                          : 'var(--odap-sidebar-logo-text)',
                        WebkitBackgroundClip: leftCollapsed ? 'none' : 'text',
                        WebkitTextFillColor: leftCollapsed ? 'var(--odap-sidebar-logo-color)' : 'transparent',
                        backgroundClip: leftCollapsed ? 'none' : 'text',
                      }}
                    >
                      {leftCollapsed ? 'O' : 'ODAP'}
                    </span>
                  </div>

                  {/* Menu with inline sub-menus */}
                  <Menu
                    theme="dark"
                    mode="inline"
                    selectedKeys={[activeMenuKey]}
                    openKeys={leftCollapsed ? [] : openKeys}
                    onOpenChange={handleOpenChange}
                    onClick={handleMenuClick}
                    onMouseDown={handleMenuMouseDown}
                    style={{ background: 'transparent', borderRight: 0 }}
                    items={menuItems}
                  />

                  {/* Collapse toggle at bottom */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      width: '100%',
                      borderTop: 'var(--odap-sidebar-border-strong)',
                    }}
                  >
                    <Button
                      type="text"
                      block
                      icon={leftCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                      onClick={() => setLeftCollapsed(!leftCollapsed)}
                      style={{
                        color: 'var(--odap-sidebar-text)',
                        height: 40,
                        borderRadius: 0,
                        transition: 'color 150ms',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--odap-sidebar-text-hover)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--odap-sidebar-text)')}
                    />
                  </div>
                </Sider>
              )}

              {/* ── Right Area: Header + 3-column body ── */}
              <Layout
                style={{
                  marginLeft: isFullWidthMode ? 0 : leftSiderWidth,
                  transition: 'margin-left 350ms cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                {/* ── Global Header ── */}
                <LayoutHeader
                  workspaces={workspaces}
                  scenarios={scenarios}
                  loading={loading}
                  scenariosLoading={scenariosLoading}
                  activeWorkspaceId={activeWorkspaceId}
                  activeScenarioId={currentScenarioState}
                  onWorkspaceChange={handleWorkspaceChange}
                  onScenarioChange={handleScenarioChange}
                  theme={theme}
                  colorTheme={colorTheme}
                  onToggleTheme={toggleTheme}
                  onColorThemeChange={(c) => setColorTheme(c)}
                  onResetTour={() => {
                    resetGuideTour();
                    navigate('/guide');
                  }}
                  username={user?.username || ''}
                  onLogout={() => {
                    logout();
                    navigate('/login');
                  }}
                  rightExtra={
                    <>
                      <Button
                        type="text"
                        size="small"
                        icon={<RobotOutlined />}
                        onClick={() => {
                          if (extensionPanelCollapsed) toggleExtensionPanel();
                          setActiveExtension('ai-chat');
                        }}
                        style={{ color: 'var(--odap-color-text-secondary)', marginRight: 4 }}
                        title="AI 助手"
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<SwitcherOutlined />}
                        onClick={handleSwitchMode}
                        style={{ color: 'var(--odap-color-text-secondary)' }}
                      >
                        我的智能体
                      </Button>
                    </>
                  }
                />

                {/* ── 3-column body container ── */}
                <div className="odap-layout-body" ref={bodyRef} style={{ height: 'calc(100vh - 48px)' }}>
                  {/* ── Column 1: Function Area (default 10%, expanded) ── */}
                  {!isFullWidthMode && !taskPanelCollapsed && (
                    <>
                      <div
                        className="odap-col-function"
                        style={{
                          width: `${taskPanelWidth}%`,
                          flexShrink: 0,
                          display: 'flex',
                          flexDirection: 'column',
                          overflow: 'hidden',
                        }}
                      >
                        {/* Task area (top) + Quick action area (bottom) */}
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                          {/* Task area */}
                          <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
                            <TaskPanel onTabClick={handleTabClick} onTabRefresh={handleTabRefresh} />
                          </div>
                          {/* Vertical resize handle */}
                          <ResizeHandle
                            direction="vertical"
                            invert
                            startSizePercent={quickActionHeight}
                            onResize={(abs) => setQuickActionHeight(abs)}
                          />
                          {/* Quick action area (bottom, default 10% height) */}
                          <div
                            style={{
                              height: `${quickActionHeight}%`,
                              flexShrink: 0,
                              overflow: 'hidden',
                            }}
                          >
                            <QuickActionBar onQuickActionClick={handleQuickActionClick} />
                          </div>
                        </div>
                      </div>
                      {/* Horizontal resize handle */}
                      <ResizeHandle
                        direction="horizontal"
                        startSizePercent={taskPanelWidth}
                        onResize={handleTaskPanelResize}
                        onToggle={toggleTaskPanel}
                      />
                    </>
                  )}

                  {/* Collapsed function area toggle with tab count badge */}
                  {!isFullWidthMode && taskPanelCollapsed && (
                    <Tooltip title={`展开功能区 (${tabs.length} 个任务)`} placement="right">
                      <div
                        style={{
                          width: 24,
                          flexShrink: 0,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 6,
                          cursor: 'pointer',
                          background: 'var(--odap-color-bg-secondary)',
                          borderRight: '1px solid var(--odap-color-border-light)',
                          transition: 'background 150ms',
                        }}
                        onClick={toggleTaskPanel}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = 'var(--odap-layout-primary-light, rgba(99, 102, 241, 0.08))';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'var(--odap-color-bg-secondary)';
                        }}
                      >
                        <Badge
                          count={tabs.length}
                          size="small"
                          overflowCount={99}
                          style={{ fontSize: 10 }}
                          styles={{ indicator: { zIndex: 1 } }}
                        />
                        <RightOutlined style={{ fontSize: 10, color: 'var(--odap-color-text-tertiary)' }} />
                      </div>
                    </Tooltip>
                  )}

                  {/* ── Column 2: Work Area (default 80%) ── */}
                  <div
                    className="odap-col-workspace"
                    style={{
                      flex: 1,
                      overflow: 'auto',
                      background: 'var(--odap-color-bg-secondary)',
                      position: 'relative',
                      minWidth: 0,
                    }}
                  >
                    <GlobalLoading />
                    {children}
                  </div>

                  {/* ── Column 3: Extension Area ──
                      hold=true  → 固定占布局宽度（当前行为）
                      hold=false → 抽屉浮层（不占布局宽度）
                      Always renders: collapsed → reopen strip */}
                  {!isFullWidthMode && (
                    <>
                      {/* Hold 模式展开：拖拽手柄 */}
                      {!extensionPanelCollapsed && extensionHold && (
                        <ResizeHandle
                          direction="horizontal"
                          startSizePercent={extensionPanelWidth}
                          invert
                          onResize={handleExtensionPanelResize}
                          onToggle={toggleExtensionPanel}
                        />
                      )}

                      {extensionPanelCollapsed ? (
                        /* Collapsed: reopen strip */
                        <Tooltip
                          title={activeExtensionSpec ? `展开扩展区 (${activeExtensionSpec.name})` : '展开扩展区'}
                          placement="left"
                        >
                          <div
                            style={{
                              width: 28,
                              flexShrink: 0,
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '12px 0',
                              cursor: 'pointer',
                              background: 'var(--odap-color-bg-secondary)',
                              borderLeft: '1px solid var(--odap-color-border-light)',
                            }}
                            onClick={toggleExtensionPanel}
                          >
                            <span style={{ display: 'inline-flex', color: 'var(--odap-color-primary)', fontSize: 14 }}>
                              {activeExtensionIcon}
                            </span>
                            <div style={{
                              writingMode: 'vertical-rl',
                              fontSize: 10,
                              color: 'var(--odap-color-text-tertiary)',
                              letterSpacing: 2,
                              userSelect: 'none',
                            }}>
                              {activeExtensionSpec?.name ?? '扩展'}
                            </div>
                            <LeftOutlined style={{ fontSize: 10, color: 'var(--odap-color-text-tertiary)' }} />
                          </div>
                        </Tooltip>
                      ) : extensionHold ? (
                        /* Hold 模式展开：固定面板 */
                        <div
                          className="odap-col-extension"
                          style={{
                            width: `${extensionPanelWidth}%`,
                            flexShrink: 0,
                            overflow: 'hidden',
                          }}
                        >
                          <ExtensionPanel
                            onClose={toggleExtensionPanel}
                            icon={activeExtensionIcon}
                            title={activeExtensionSpec?.name ?? '扩展区'}
                            extensions={extensionSpecs}
                            activeExtensionId={activeExtensionId}
                            onSwitchExtension={setActiveExtension}
                            hold={extensionHold}
                            onToggleHold={toggleExtensionHold}
                          >
                            {activeExtensionComponent ? React.createElement(activeExtensionComponent) : (
                              <div style={{ padding: 16, color: 'var(--odap-color-text-secondary)', textAlign: 'center' }}>
                                选择一个扩展
                              </div>
                            )}
                          </ExtensionPanel>
                        </div>
                      ) : null}
                    </>
                  )}

                  {/* ── 非 Hold 模式展开：Drawer 抽屉（不受 layout 宽度影响） ── */}
                  {!isFullWidthMode && !extensionPanelCollapsed && !extensionHold && (
                    <Drawer
                      open
                      placement="right"
                      onClose={toggleExtensionPanel}
                      width={Math.max(300, window.innerWidth * 0.25)}
                      mask={false}
                      closable={false}
                      styles={{
                        body: { padding: 0 },
                        wrapper: { position: 'absolute' },
                      }}
                      getContainer={false}
                    >
                      <ExtensionPanel
                        onClose={toggleExtensionPanel}
                        icon={activeExtensionIcon}
                        title={activeExtensionSpec?.name ?? '扩展区'}
                        extensions={extensionSpecs}
                        activeExtensionId={activeExtensionId}
                        onSwitchExtension={setActiveExtension}
                        hold={extensionHold}
                        onToggleHold={toggleExtensionHold}
                      >
                        {activeExtensionComponent ? React.createElement(activeExtensionComponent) : (
                          <div style={{ padding: 16, color: 'var(--odap-color-text-secondary)', textAlign: 'center' }}>
                            选择一个扩展
                          </div>
                        )}
                      </ExtensionPanel>
                    </Drawer>
                  )}
                </div>
              </Layout>
            </Layout>
          </RightPanelContext.Provider>
        </OntologyVersionContext.Provider>
      </App>
    </ConfigProvider>
  );
}
