import { useState } from 'react';
import { Layout, Menu } from 'antd';
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

const { Header, Sider, Content } = Layout;

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
  const navigate = useNavigate();
  const location = useLocation();

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  return (
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
          }}
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
          <div style={{ fontSize: 16, fontWeight: 500 }}>
            工作空间: 默认战争场景
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
  );
}
