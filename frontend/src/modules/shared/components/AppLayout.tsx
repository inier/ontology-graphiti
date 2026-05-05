import { useState, useEffect, createContext, useContext } from 'react';
import { Layout, Menu, Select, Spin, message, Button, Empty } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  BlockOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  HistoryOutlined,
  SettingOutlined,
  TeamOutlined,
  FileTextOutlined,
  AuditOutlined,
  AppstoreOutlined,
  SearchOutlined,
  LeftOutlined,
  RightOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { api } from '../services/api';

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

interface AppLayoutProps {
  children: React.ReactNode;
  currentWorkspace?: string;
  onWorkspaceChange?: (workspaceId: string) => void;
}

// 右栏展开状态 Context
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

const menuItems = [
  {
    key: 'user-operations',
    icon: <HomeOutlined />,
    label: '用户操作区',
    children: [
      { key: '/', icon: <HomeOutlined />, label: '首页仪表盘' },
      { key: '/query', icon: <SearchOutlined />, label: '查询界面' },
      { key: '/timeline', icon: <ClockCircleOutlined />, label: '时间线' },
      { key: '/map', icon: <EnvironmentOutlined />, label: '态势地图' },
      { key: '/simulator', icon: <ThunderboltOutlined />, label: '模拟推演' },
      { key: '/qa', icon: <SearchOutlined />, label: '智能问答' },
    ],
  },
  {
    key: 'ontology-management',
    icon: <BlockOutlined />,
    label: '本体管理区',
    children: [
      { key: '/ontology', icon: <BlockOutlined />, label: '本体语义网络' },
      { key: '/ingest', icon: <UploadOutlined />, label: '数据摄入' },
      { key: '/versions', icon: <HistoryOutlined />, label: '版本管理' },
    ],
  },
  {
    key: 'system-config',
    icon: <SettingOutlined />,
    label: '系统配置区',
    children: [
      { key: '/workspace', icon: <BlockOutlined />, label: '工作空间' },
      { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
      { key: '/roles', icon: <TeamOutlined />, label: '角色管理' },
      { key: '/policies', icon: <FileTextOutlined />, label: 'OPA 策略' },
      { key: '/skills', icon: <AppstoreOutlined />, label: 'Skill 管理' },
      { key: '/config', icon: <SettingOutlined />, label: '配置中心' },
    ],
  },
];

export function AppLayout({ children, currentWorkspace, onWorkspaceChange }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
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

  const activeWorkspaceId = currentWorkspace || currentWorkspaceState;
  const leftSiderWidth = collapsed ? 80 : 200;
  const rightSiderWidth = rightCollapsed ? 0 : 280;

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
      console.log('Workspaces data:', data);
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
      console.log('Scenarios data:', data);
      setScenarios(data.scenarios || []);

      const savedScenarioId = localStorage.getItem('currentScenarioId');
      if (data.scenarios && data.scenarios.length > 0) {
        if (!savedScenarioId || !data.scenarios.find(s => s.scenario_id === savedScenarioId)) {
          const defaultScenario = data.scenarios[0].scenario_id;
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

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogoClick = () => {
    navigate('/');
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

  return (
    <WorkspaceContext.Provider value={contextValue}>
      <ScenarioContext.Provider value={scenarioContextValue}>
        <RightPanelContext.Provider value={rightPanelContextValue}>
          <Layout style={{ minHeight: '100vh' }}>
            {/* 左栏 - 导航菜单 */}
            <Sider
              collapsible
              collapsed={collapsed}
              onCollapse={setCollapsed}
              style={{
                overflow: 'auto',
                height: '100vh',
                position: 'fixed',
                left: 0,
                top: 0,
                bottom: 0,
                zIndex: 100,
              }}
            >
              <div
                style={{
                  height: 64,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                  fontSize: collapsed ? 16 : 20,
                  fontWeight: 600,
                  borderBottom: '1px solid rgba(255,255,255,0.1)',
                  cursor: 'pointer',
                }}
                onClick={handleLogoClick}
              >
                {collapsed ? 'ODAP' : 'ODAP 本体平台'}
              </div>
              <Menu
                theme="dark"
                mode="inline"
                selectedKeys={[location.pathname]}
                onClick={handleMenuClick}
                items={menuItems}
              />
            </Sider>
            
            {/* 中间主内容区 + 右栏 */}
            <Layout style={{ 
              marginLeft: leftSiderWidth, 
              marginRight: rightSiderWidth,
              transition: 'margin-left 0.2s, margin-right 0.2s' 
            }}>
              <Header
                style={{
                  padding: '0 24px',
                  background: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
                  position: 'sticky',
                  top: 0,
                  zIndex: 99,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: '#666' }}>工作空间:</span>
                    {loading ? (
                      <Spin size="small" />
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
                      <span style={{ color: '#8c8c8c', fontSize: 14 }}>暂无工作空间</span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: '#666' }}>场景:</span>
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
                      <span style={{ color: '#8c8c8c', fontSize: 14 }}>暂无场景</span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {/* 右栏切换按钮 */}
                  <Button
                    type="text"
                    icon={rightCollapsed ? <RightOutlined /> : <LeftOutlined />}
                    onClick={() => setRightCollapsed(!rightCollapsed)}
                    title={rightCollapsed ? '展开侧边栏' : '收起侧边栏'}
                    style={{ color: '#666' }}
                  />
                  <span style={{ color: '#8c8c8c', fontSize: 14 }}>管理员</span>
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: '50%',
                      background: '#1890ff',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 14,
                      fontWeight: 500,
                    }}
                  >
                    A
                  </div>
                </div>
              </Header>
              <Content style={{ padding: 16, minHeight: 'calc(100vh - 64px)' }}>
                {children}
              </Content>
            </Layout>

            {/* 右栏 - 扩展面板 */}
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
                background: '#ffffff',
                borderLeft: '1px solid #f0f0f0',
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
                  borderBottom: '1px solid #f0f0f0',
                }}
              >
                <span style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>
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
      </ScenarioContext.Provider>
    </WorkspaceContext.Provider>
  );
}
