import { useState } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { AppLayout } from './modules/shared';
import { AppRoutes } from './AppRoutes';
import './App.css';

export function App() {
  const [currentWorkspace, setCurrentWorkspace] = useState('default');

  const handleWorkspaceChange = (workspaceId: string) => {
    setCurrentWorkspace(workspaceId);
  };

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