import { useState, useEffect, createContext, useContext } from 'react';
import { Layout, Menu, Select, Spin, message } from 'antd';
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
  PlaySquareOutlined,
} from '@ant-design/icons';
import { api } from '../services/api';
import type { Scenario } from '../types';

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
      { key: '/workspace', icon: <BlockOutlined />, label: '工作空间' },
      { key: '/versions', icon: <HistoryOutlined />, label: '版本管理' },
      { key: '/ontology/builder', icon: <FileTextOutlined />, label: '本体构建' },
    ],
  },
  {
    key: 'system-config',
    icon: <SettingOutlined />,
    label: '系统配置区',
    children: [
      { key: '/roles', icon: <TeamOutlined />, label: '角色管理' },
      { key: '/policies', icon: <FileTextOutlined />, label: 'OPA 策略' },
      { key: '/skills', icon: <AppstoreOutlined />, label: 'Skill 管理' },
      { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
      { key: '/config', icon: <SettingOutlined />, label: '配置中心' },
    ],
  },
];

export function AppLayout({ children, currentWorkspace, onWorkspaceChange }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspaceState, setCurrentWorkspaceState] = useState<string>(() => {
    // 优先从 localStorage 读取已保存的工作空间
    return localStorage.getItem('currentWorkspaceId') || '';
  });
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [currentScenarioState, setCurrentScenarioState] = useState<string>(() => {
    // 优先从 localStorage 读取已保存的场景
    return localStorage.getItem('currentScenarioId') || '';
  });
  const [loading, setLoading] = useState(true);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 优先使用 props，如果没有则使用内部状态
  const activeWorkspaceId = currentWorkspace || currentWorkspaceState;

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
      
      // 如果没有设置过工作空间，或者当前工作空间不在列表中，自动选择第一个
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
      
      // 如果没有设置过场景，或者当前场景不在列表中，自动选择第一个
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
      // 场景加载失败不显示错误，因为可能没有场景
    } finally {
      setScenariosLoading(false);
    }
  };

  const handleWorkspaceChange = (value: string) => {
    // 保存到 localStorage
    localStorage.setItem('currentWorkspaceId', value);
    
    // 更新内部状态
    setCurrentWorkspaceState(value);
    
    // 调用回调（如果提供）
    onWorkspaceChange?.(value);
    
    message.success('已切换工作空间');
  };

  const handleScenarioChange = (value: string) => {
    // 保存到 localStorage
    localStorage.setItem('currentScenarioId', value);
    
    // 更新内部状态
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

  return (
    <WorkspaceContext.Provider value={contextValue}>
      <ScenarioContext.Provider value={scenarioContextValue}>
        <Layout style={{ minHeight: '100vh' }}>
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
          <Layout style={{ marginLeft: collapsed ? 80 : 240, transition: 'margin-left 0.2s' }}>
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
                {/* 工作空间选择 */}
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
                
                {/* 场景选择 */}
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
            <Content style={{ padding: 24, minHeight: 'calc(100vh - 64px)', background: '#f0f2f5' }}>
              {children}
            </Content>
          </Layout>
        </Layout>
      </ScenarioContext.Provider>
    </WorkspaceContext.Provider>
  );
}