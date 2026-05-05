import { useState, useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { AppLayout } from './modules/shared';
import { AppRoutes } from './AppRoutes';
import { api } from './modules/shared/services/api';
import './App.css';

export function App() {
  const [currentWorkspace, setCurrentWorkspace] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadInitialWorkspace = async () => {
      try {
        const workspaces = await api.listWorkspaces();
        if (workspaces && workspaces.length > 0) {
          const savedId = localStorage.getItem('currentWorkspaceId');
          const validId = workspaces.find(w => w.workspace_id === savedId);
          const targetId: string = validId && savedId ? savedId : workspaces[0].workspace_id;
          setCurrentWorkspace(targetId);
          localStorage.setItem('currentWorkspaceId', targetId);
        }
      } catch (error) {
        console.error('加载工作空间失败:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialWorkspace();
  }, []);

  const handleWorkspaceChange = (workspaceId: string) => {
    setCurrentWorkspace(workspaceId);
    localStorage.setItem('currentWorkspaceId', workspaceId);
  };

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>加载中...</div>;
  }

  return (
    <Router>
      <AppLayout
        currentWorkspace={currentWorkspace}
        onWorkspaceChange={handleWorkspaceChange}
      >
        <AppRoutes />
      </AppLayout>
    </Router>
  );
}

export default App;