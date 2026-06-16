import { useState, useEffect } from 'react';
import { BrowserRouter as Router, useLocation } from 'react-router-dom';
import { AppLayout } from '@/modules/shared';
import { AppRoutes } from './AppRoutes';
import { api } from '@/modules/shared/services/api';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import './App.css';

function AppContent() {
  const location = useLocation();
  const isLoginPage = location.pathname === '/login';
  const [currentWorkspace, setCurrentWorkspace] = useState<string>('');
  const [ready, setReady] = useState(isLoginPage);
  const { show, hide } = useGlobalLoading();

  useEffect(() => {
    if (isLoginPage) return;
    const loadInitialWorkspace = async () => {
      show('加载中...', 0);
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
        hide();
        setReady(true);
      }
    };

    loadInitialWorkspace();
  }, [isLoginPage, show, hide]);

  const handleWorkspaceChange = (workspaceId: string) => {
    setCurrentWorkspace(workspaceId);
    localStorage.setItem('currentWorkspaceId', workspaceId);
  };

  if (isLoginPage) {
    return <AppRoutes />;
  }

  if (!ready) {
    return (
      <AppLayout currentWorkspace={currentWorkspace} onWorkspaceChange={handleWorkspaceChange}>
        <div />
      </AppLayout>
    );
  }

  return (
    <AppLayout currentWorkspace={currentWorkspace} onWorkspaceChange={handleWorkspaceChange}>
      <AppRoutes />
    </AppLayout>
  );
}

export function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
