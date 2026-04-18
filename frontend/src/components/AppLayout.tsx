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
} from '@ant-design/icons';
import { api } from '../services/api';

const { Header, Sider, Content } = Layout;

interface Scenario {
  scenario_id: string;
  name: string;
}

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

interface AppLayoutProps {
  children: React.ReactNode;
}

const menuItems = [
  { key: '/', icon: <HomeOutlined />, label: '首页仪表盘' },
  { key: '/ontology', icon: <BlockOutlined />, label: '本体图谱' },
  { key: '/timeline', icon: <ClockCircleOutlined />, label: '时间线' },
  { key: '/map', icon: <EnvironmentOutlined />, label: '态势地图' },
  { key: '/simulator', icon: <ThunderboltOutlined />, label: '模拟推演' },
  { key: '/ingest', icon: <UploadOutlined />, label: '数据摄入' },
  { key: '/versions', icon: <HistoryOutlined />, label: '版本管理' },
  { key: '/config', icon: <SettingOutlined />, label: '配置中心' },
  { key: '/roles', icon: <TeamOutlined />, label: '角色管理' },
  { key: '/policies', icon: <FileTextOutlined />, label: 'OPA 策略' },
  { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
  { key: '/skills', icon: <AppstoreOutlined />, label: 'Skill 管理' },
];

export function AppLayout({ children }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [currentScenario, setCurrentScenarioState] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    loadScenarios();
  }, []);

  const loadScenarios = async () => {
    try {
      setLoading(true);
      const data = await api.listScenarios();
      setScenarios(data);
      if (data.length > 0) {
        if (!currentScenario || !data.find(s => s.scenario_id === currentScenario)) {
          setCurrentScenarioState(data[0].scenario_id);
        }
      }
    } catch (error) {
      console.error('加载场景列表失败:', error);
      message.error('加载场景列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleScenarioChange = (value: string) => {
    setCurrentScenarioState(value);
    message.success('已切换工作空间');
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogoClick = () => {
    navigate('/');
  };

  const contextValue = {
    currentScenario,
    setCurrentScenario: handleScenarioChange,
    scenarios,
    reloadScenarios: loadScenarios,
  };

  return (
    <ScenarioContext.Provider value={contextValue}>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16, fontWeight: 500 }}>工作空间:</span>
              {loading ? (
                <Spin size="small" />
              ) : scenarios.length > 0 ? (
                <Select
                  value={currentScenario || undefined}
                  onChange={handleScenarioChange}
                  style={{ width: 200 }}
                  options={scenarios.map(s => ({
                    value: s.scenario_id,
                    label: s.name,
                  }))}
                />
              ) : (
                <span style={{ color: '#8c8c8c' }}>暂无场景</span>
              )}
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
  );
}