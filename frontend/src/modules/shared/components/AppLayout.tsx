import { useState, useEffect, createContext, useContext } from 'react';
import { Layout, Menu, Select, Spin, message, Button, Empty, Tooltip, Dropdown } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  BlockOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  TeamOutlined,
  FileTextOutlined,
  AuditOutlined,
  AppstoreOutlined,
  LeftOutlined,
  RightOutlined,
  CloseOutlined,
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
} from '@ant-design/icons';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { GlobalLoading } from './GlobalLoading';
import { useTourStore } from '@/modules/guide';

const { Header, Sider, Content } = Layout;

interface Workspace {
  workspace_id: string;
  name: string;
}

interface Scenario {
  scenario_id: string;
  name: string;
  description?: string;
  workspace_id: string;
  ontology_id?: string;
  current_ontology_version?: string;
}

interface WorkspaceContextType {
  currentWorkspace: string;
  setCurrentWorkspace: (id: string) => void;
  workspaces: Workspace[];
  reloadWorkspaces: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType>({
  currentWorkspace: '',
  setCurrentWorkspace: () => {},
  workspaces: [],
  reloadWorkspaces: async () => {},
});

interface ScenarioContextType {
  currentScenario: string;
  setCurrentScenario: (id: string) => void;
  scenarios: Scenario[];
  reloadScenarios: () => Promise<void>;
}

const ScenarioContext = createContext<ScenarioContextType>({
  currentScenario: '',
  setCurrentScenario: () => {},
  scenarios: [],
  reloadScenarios: async () => {},
});

export const useScenario = () => useContext(ScenarioContext);

export const useWorkspace = () => useContext(WorkspaceContext);

interface OntologyVersionContextType {
  currentOntologyId: string;
  currentVersionId: string;
}

const OntologyVersionContext = createContext<OntologyVersionContextType>({
  currentOntologyId: '',
  currentVersionId: '',
});

export const useOntologyVersion = () => useContext(OntologyVersionContext);

interface AppLayoutProps {
  children: React.ReactNode;
  currentWorkspace?: string;
  onWorkspaceChange?: (workspaceId: string) => void;
}

interface RightPanelContextType {
  showRightPanel: boolean;
  setShowRightPanel: (show: boolean) => void;
  rightPanelContent: React.ReactNode;
  setRightPanelContent: (content: React.ReactNode) => void;
  rightPanelTitle: string;
  setRightPanelTitle: (title: string) => void;
}

const RightPanelContext = createContext<RightPanelContextType>({
  showRightPanel: false,
  setShowRightPanel: () => {},
  rightPanelContent: null,
  setRightPanelContent: () => {},
  rightPanelTitle: '',
  setRightPanelTitle: () => {},
});

export const useRightPanel = () => useContext(RightPanelContext);

interface PrimaryMenu {
  key: string;
  icon: React.ReactNode;
  label: string;
  children?: { key: string; icon?: React.ReactNode; label: string }[];
}

const primaryMenus: PrimaryMenu[] = [
  {
    key: 'guide',
    icon: <BookOutlined />,
    label: '快速指南',
    children: [
      { key: '/guide', icon: <BookOutlined />, label: '系统指南' },
    ],
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
    ],
  },
];

const routeToPrimaryMap: Record<string, string> = {};
primaryMenus.forEach(m => {
  if (m.children) {
    m.children.forEach(c => {
      routeToPrimaryMap[c.key] = m.key;
    });
  } else {
    routeToPrimaryMap[m.key] = m.key;
  }
});
routeToPrimaryMap['/agent-chat'] = 'agent';

const directRoutes: Record<string, string> = {};

export function AppLayout({ children, currentWorkspace, onWorkspaceChange }: AppLayoutProps) {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [subCollapsed, setSubCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspaceState, setCurrentWorkspaceState] = useState<string>(() => {
    return localStorage.getItem('currentWorkspaceId') || '';
  });
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [currentScenarioState, setCurrentScenarioState] = useState<string>(() => {
    return localStorage.getItem('currentScenarioId') || '';
  });
  const [loading, setLoading] = useState(true);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [rightPanelContent, setRightPanelContent] = useState<React.ReactNode>(null);
  const [rightPanelTitle, setRightPanelTitle] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { resetGuideTour, resetAllTours } = useTourStore();

  /* Theme state */
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    (localStorage.getItem('odap-theme') as 'light' | 'dark') || 'light'
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('odap-theme', theme);
  }, [theme]);
  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light');

  const activeWorkspaceId = currentWorkspace || currentWorkspaceState;
  const leftSiderWidth = leftCollapsed ? 64 : 160;
  const activePrimary = routeToPrimaryMap[location.pathname] || routeToPrimaryMap['/' + location.pathname.split('/')[1]] || '';
  const activeMenu = primaryMenus.find(m => m.key === activePrimary);
  const hasSubMenus = activeMenu && activeMenu.children && activeMenu.children.length > 0;
  const subSiderWidth = subCollapsed ? 0 : (hasSubMenus ? 180 : 0);
  const rightSiderWidth = rightCollapsed ? 0 : 280;

  const isAgentMode = location.pathname.startsWith('/agent-chat/');

  useEffect(() => {
    loadWorkspaces();
  }, []);

  useEffect(() => {
    if (activeWorkspaceId) {
      loadScenarios(activeWorkspaceId);
    }
  }, [activeWorkspaceId]);

  const loadWorkspaces = async () => {
    try {
      setLoading(true);
      const data = await api.listWorkspaces();
      setWorkspaces(data);

      const savedWorkspaceId = localStorage.getItem('currentWorkspaceId');
      if (data.length > 0) {
        if (!savedWorkspaceId || !data.find(w => w.workspace_id === savedWorkspaceId)) {
          const defaultWorkspace = data[0].workspace_id;
          setCurrentWorkspaceState(defaultWorkspace);
          localStorage.setItem('currentWorkspaceId', defaultWorkspace);
          onWorkspaceChange?.(defaultWorkspace);
        }
      }
    } catch (error) {
      console.error('加载工作空间列表失败:', error);
      message.error('加载工作空间列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadScenarios = async (workspaceId: string) => {
    try {
      setScenariosLoading(true);
      const data = await api.getScenariosInWorkspace(workspaceId);
      const newScenarios = data.scenarios || [];
      setScenarios(newScenarios);

      const savedScenarioId = localStorage.getItem('currentScenarioId');
      const currentId = currentScenarioState;

      if (newScenarios.length > 0) {
        const existingScenario = newScenarios.find(s => s.scenario_id === currentId);
        const savedScenario = newScenarios.find(s => s.scenario_id === savedScenarioId);

        if (existingScenario) {
          setCurrentScenarioState(currentId);
        } else if (savedScenario) {
          setCurrentScenarioState(savedScenarioId!);
          localStorage.setItem('currentScenarioId', savedScenarioId!);
        } else {
          const defaultScenario = newScenarios[0].scenario_id;
          setCurrentScenarioState(defaultScenario);
          localStorage.setItem('currentScenarioId', defaultScenario);
        }
      } else {
        setCurrentScenarioState('');
        localStorage.removeItem('currentScenarioId');
      }
    } catch (error) {
      console.error('加载场景列表失败:', error);
    } finally {
      setScenariosLoading(false);
    }
  };

  const handleWorkspaceChange = (value: string) => {
    localStorage.setItem('currentWorkspaceId', value);
    setCurrentWorkspaceState(value);
    onWorkspaceChange?.(value);
    message.success('已切换工作空间');
  };

  const handleScenarioChange = (value: string) => {
    localStorage.setItem('currentScenarioId', value);
    setCurrentScenarioState(value);
    message.success('已切换场景');
  };

  const handlePrimaryMenuClick = ({ key }: { key: string }) => {
    const menu = primaryMenus.find(m => m.key === key);
    if (!menu) return;

    if (menu.children && menu.children.length > 0) {
      if (activePrimary === key) {
        setSubCollapsed(!subCollapsed);
      } else {
        setSubCollapsed(false);
        const firstChild = menu.children[0];
        navigate(firstChild.key);
      }
    } else {
      const route = directRoutes[key] || key;
      navigate(route);
    }
  };

  const handleSubMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogoClick = () => {
    navigate('/guide');
  };

  const handleSwitchMode = () => {
    if (isAgentMode) {
      navigate('/ontology/designer');
    } else {
      navigate('/my-agents');
    }
  };

  const contextValue = {
    currentWorkspace: activeWorkspaceId,
    setCurrentWorkspace: handleWorkspaceChange,
    workspaces,
    reloadWorkspaces: loadWorkspaces,
  };

  const scenarioContextValue = {
    currentScenario: currentScenarioState,
    setCurrentScenario: handleScenarioChange,
    scenarios,
    reloadScenarios: () => loadScenarios(activeWorkspaceId),
  };

  const rightPanelContextValue = {
    showRightPanel,
    setShowRightPanel,
    rightPanelContent,
    setRightPanelContent,
    rightPanelTitle,
    setRightPanelTitle,
  };

  const currentScenarioObj = scenarios.find(s => s.scenario_id === currentScenarioState);
  const ontologyVersionContextValue = {
    currentOntologyId: currentScenarioObj?.ontology_id || '',
    currentVersionId: currentScenarioObj?.current_ontology_version || '',
  };

  const totalLeftWidth = isAgentMode ? 0 : (leftSiderWidth + subSiderWidth);

  return (
    <WorkspaceContext.Provider value={contextValue}>
      <ScenarioContext.Provider value={scenarioContextValue}>
        <OntologyVersionContext.Provider value={ontologyVersionContextValue}>
        <RightPanelContext.Provider value={rightPanelContextValue}>
          <Layout style={{ minHeight: '100vh', minWidth: 1200 }}>
            {!isAgentMode && (
              <>
                <Sider
                  trigger={null}
                  collapsed={leftCollapsed}
                  collapsedWidth={64}
                  style={{
                    overflow: 'auto',
                    height: '100vh',
                    position: 'fixed',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    zIndex: 100,
                    background: 'linear-gradient(180deg, #1E1B4B 0%, #0F0F1A 100%)',
                    borderRight: '1px solid rgba(255,255,255,0.06)',
                    transition: 'width 250ms cubic-bezier(0.16,1,0.3,1)',
                  }}
                  width={160}
                >
                  <div
                    style={{
                      height: 64,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#ffffff',
                      fontSize: leftCollapsed ? 16 : 20,
                      fontWeight: 700,
                      letterSpacing: '0.05em',
                      borderBottom: '1px solid rgba(255,255,255,0.08)',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      background: leftCollapsed ? 'transparent' : 'linear-gradient(135deg, rgba(129,140,248,0.2), rgba(167,139,250,0.1))',
                    }}
                    onClick={handleLogoClick}
                  >
                    <span style={{
                      background: leftCollapsed ? 'none' : 'linear-gradient(135deg, #818CF8, #A78BFA)',
                      WebkitBackgroundClip: leftCollapsed ? 'none' : 'text',
                      WebkitTextFillColor: leftCollapsed ? '#818CF8' : 'transparent',
                      backgroundClip: leftCollapsed ? 'none' : 'text',
                    }}>
                      {leftCollapsed ? 'O' : 'ODAP'}
                    </span>
                  </div>
                  <Menu
                    theme="dark"
                    mode="inline"
                    selectedKeys={[activePrimary]}
                    onClick={handlePrimaryMenuClick}
                    items={primaryMenus.map(m => ({
                      key: m.key,
                      icon: m.icon,
                      label: leftCollapsed ? '' : m.label,
                      title: m.label,
                    }))}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      width: '100%',
                      borderTop: '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    <Button
                      type="text"
                      block
                      icon={leftCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                      onClick={() => setLeftCollapsed(!leftCollapsed)}
                      style={{
                        color: 'rgba(255,255,255,0.4)',
                        height: 48,
                        borderRadius: 0,
                        transition: 'color 150ms',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
                    />
                  </div>
                </Sider>

                {hasSubMenus && !subCollapsed && (
                  <div
                    style={{
                      position: 'fixed',
                      left: leftSiderWidth,
                      top: 0,
                      bottom: 0,
                      width: 180,
                      zIndex: 99,
                      background: 'var(--odap-color-bg-primary)',
                      borderRight: '1px solid var(--odap-color-border-light)',
                      overflow: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      transition: 'left 250ms cubic-bezier(0.16,1,0.3,1)',
                    }}
                  >
                    <div
                      style={{
                        height: 64,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0 16px',
                        borderBottom: '1px solid var(--odap-color-border-light)',
                        flexShrink: 0,
                        background: 'var(--odap-color-bg-secondary)',
                      }}
                    >
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--odap-color-text-primary)' }}>
                        {activeMenu!.label}
                      </span>
                      <Button
                        type="text"
                        size="small"
                        icon={<LeftOutlined />}
                        onClick={() => setSubCollapsed(true)}
                        style={{ color: 'var(--odap-color-text-tertiary)' }}
                      />
                    </div>
                    <Menu
                      mode="inline"
                      selectedKeys={[location.pathname]}
                      onClick={handleSubMenuClick}
                      style={{ borderRight: 0, flex: 1 }}
                      items={activeMenu!.children!.map(c => ({
                        key: c.key,
                        icon: c.icon,
                        label: c.label,
                      }))}
                    />
                  </div>
                )}

                {hasSubMenus && subCollapsed && (
                  <Tooltip title={`${activeMenu!.label} - 展开子菜单`} placement="right">
                    <div
                      style={{
                        position: 'fixed',
                        left: leftSiderWidth,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        zIndex: 99,
                        background: 'var(--odap-color-bg-primary)',
                        border: '1px solid var(--odap-color-border)',
                        borderLeft: 'none',
                        borderRadius: '0 6px 6px 0',
                        cursor: 'pointer',
                        padding: '8px 4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: 'var(--odap-shadow-sm)',
                        transition: 'left 250ms cubic-bezier(0.16,1,0.3,1)',
                      }}
                      onClick={() => setSubCollapsed(false)}
                    >
                      <RightOutlined style={{ fontSize: 10, color: 'var(--odap-color-text-tertiary)' }} />
                    </div>
                  </Tooltip>
                )}
              </>
            )}

            <Layout style={{
              marginLeft: isAgentMode ? 0 : totalLeftWidth,
              marginRight: rightSiderWidth,
              transition: 'margin-left 250ms cubic-bezier(0.16,1,0.3,1), margin-right 250ms cubic-bezier(0.16,1,0.3,1)'
            }}>
              <Header
                style={{
                  padding: '0 24px',
                  background: 'var(--odap-color-bg-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid var(--odap-color-border-light)',
                  boxShadow: 'var(--odap-shadow-xs)',
                  position: 'sticky',
                  top: 0,
                  zIndex: 99,
                  height: 56,
                  lineHeight: '56px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                  {!isAgentMode && (
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--odap-color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>工作空间</span>
                        {loading ? (
                          <Spin size="small" spinning />
                        ) : workspaces.length > 0 ? (
                          <Select
                            value={activeWorkspaceId || undefined}
                            onChange={handleWorkspaceChange}
                            style={{ width: 180 }}
                            options={workspaces.map(w => ({
                              value: w.workspace_id,
                              label: w.name,
                            }))}
                          />
                        ) : (
                          <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 14 }}>暂无工作空间</span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--odap-color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>场景</span>
                        {scenariosLoading ? (
                          <Spin size="small" />
                        ) : scenarios.length > 0 ? (
                          <Select
                            value={currentScenarioState || undefined}
                            onChange={handleScenarioChange}
                            style={{ width: 180 }}
                            options={scenarios.map(s => ({
                              value: s.scenario_id,
                              label: s.name,
                            }))}
                          />
                        ) : (
                          <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 14 }}>暂无场景</span>
                        )}
                      </div>
                    </>
                  )}
                  {isAgentMode && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <RobotOutlined style={{ fontSize: 20, color: 'var(--odap-color-primary)' }} />
                      <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--odap-color-text-primary)' }}>ODAP 智能体</span>
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <Tooltip title="帮助与引导">
                    <Button
                      type="text"
                      icon={<QuestionCircleOutlined />}
                      onClick={() => {
                        resetGuideTour();
                        navigate('/guide');
                      }}
                      style={{ color: 'var(--odap-color-text-secondary)' }}
                    />
                  </Tooltip>
                  <Tooltip title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}>
                    <Button
                      type="text"
                      icon={theme === 'light' ? <span style={{fontSize:16}}>🌙</span> : <span style={{fontSize:16}}>☀️</span>}
                      onClick={toggleTheme}
                      style={{
                        color: 'var(--odap-color-text-secondary)',
                        fontSize: 16,
                        transition: 'transform 300ms cubic-bezier(0.34,1.56,0.64,1)',
                      }}
                    />
                  </Tooltip>
                  <Button
                    type="text"
                    icon={<SwitcherOutlined />}
                    onClick={handleSwitchMode}
                    style={{ color: 'var(--odap-color-text-secondary)' }}
                  >
                    {isAgentMode ? '管理后台' : '我的智能体'}
                  </Button>
                  <Button
                    type="text"
                    icon={rightCollapsed ? <RightOutlined /> : <LeftOutlined />}
                    onClick={() => setRightCollapsed(!rightCollapsed)}
                    title={rightCollapsed ? '展开侧边栏' : '收起侧边栏'}
                    style={{ color: 'var(--odap-color-text-secondary)' }}
                  />
                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: 'logout',
                          icon: <LogoutOutlined />,
                          label: '退出登录',
                          onClick: () => {
                            logout();
                            navigate('/login');
                          },
                        },
                      ],
                    }}
                    placement="bottomRight"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <span style={{ color: 'var(--odap-color-text-secondary)', fontSize: 14 }}>{user?.username || '未登录'}</span>
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          background: 'linear-gradient(135deg, var(--odap-color-primary-600), var(--odap-color-accent-500))',
                          color: '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 14,
                          fontWeight: 600,
                        }}
                      >
                        {user?.username?.[0]?.toUpperCase() || '?'}
                      </div>
                    </div>
                  </Dropdown>
                </div>
              </Header>
              <Content style={{ padding: isAgentMode ? 0 : 24, height: 'calc(100vh - 56px)', overflow: "auto", background: 'var(--odap-color-bg-secondary)', position: 'relative' }}>
                <GlobalLoading />
                {children}
              </Content>
            </Layout>

            <Sider
              collapsible
              collapsed={rightCollapsed}
              onCollapse={setRightCollapsed}
              collapsedWidth={0}
              trigger={null}
              style={{
                overflow: 'auto',
                height: '100vh',
                position: 'fixed',
                right: 0,
                top: 0,
                bottom: 0,
                zIndex: 100,
                background: 'var(--odap-color-bg-primary)',
                borderLeft: '1px solid var(--odap-color-border-light)',
                boxShadow: 'var(--odap-shadow-sm)',
              }}
              width={280}
            >
              <div
                style={{
                  height: 64,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 16px',
                  borderBottom: '1px solid var(--odap-color-border-light)',
                  background: 'var(--odap-color-bg-secondary)',
                }}
              >
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--odap-color-text-primary)' }}>
                  {rightPanelTitle || '扩展面板'}
                </span>
                <Button
                  type="text"
                  size="small"
                  onClick={() => setRightCollapsed(true)}
                  icon={<CloseOutlined />}
                />
              </div>
              <div style={{ padding: 16 }}>
                {rightPanelContent || (
                  <Empty description="暂无内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </div>
            </Sider>
          </Layout>
        </RightPanelContext.Provider>
        </OntologyVersionContext.Provider>
      </ScenarioContext.Provider>
    </WorkspaceContext.Provider>
  );
}
