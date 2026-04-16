import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { Dashboard, GraphView, IngestPanel, VersionHistory } from './pages';
import { useState } from 'react';

const { Header, Content } = Layout;

function App() {
  const [current, setCurrent] = useState('dashboard');

  const menuItems = [
    { key: 'dashboard', label: '仪表盘' },
    { key: 'graph', label: '图谱视图' },
    { key: 'ingest', label: '数据摄入' },
    { key: 'versions', label: '版本历史' },
  ];

  const getPath = (key: string) => {
    switch (key) {
      case 'dashboard': return '/';
      case 'graph': return '/graph';
      case 'ingest': return '/ingest';
      case 'versions': return '/versions';
      default: return '/';
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: 'white', fontSize: 20, fontWeight: 'bold', marginRight: 40 }}>
          ODAP 本体平台
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[current]}
          onClick={({ key }) => {
            setCurrent(key);
          }}
          items={menuItems}
          style={{ flex: 1 }}
        />
      </Header>
      <Content style={{ background: '#f0f2f5' }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/graph" element={<GraphView />} />
          <Route path="/ingest" element={<IngestPanel />} />
          <Route path="/versions" element={<VersionHistory />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}

export default App;
