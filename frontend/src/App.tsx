import { useState, useEffect, useCallback, useMemo } from 'react';
import { BrowserRouter as Router, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { AdminLayout } from '@/modules/shared';
import { AgentLayout } from '@/modules/shared/components/AgentLayout';
import { AppRoutes } from './AppRoutes';
import { api } from '@/modules/shared/services/api';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import {
  WorkspaceContext,
  ScenarioContext,
  OntologyVersionContext,
  RightPanelContext,
  type Workspace,
  type Scenario,
} from '@/modules/shared/components/LayoutContexts';
import {
  setWorkspacesCache,
  setScenariosCache,
  clearScenariosCache,
  setCachedWorkspaceId,
  setCachedScenarioId,
} from '@/modules/shared/services/workspaceCache';
import './App.css';

/** 模块级缓存：跨 Layout 卸载/重挂不丢失 */
let cachedWorkspaces: Workspace[] = [];
let cachedScenarios: Scenario[] = [];

function AppContent() {
  const location = useLocation();
  const isLoginPage = location.pathname === '/login';
  const isAgentMode =
    location.pathname === '/my-agents' ||
    location.pathname.startsWith('/agent-chat/') ||
    location.pathname === '/agent';

  const [workspaces, setWorkspaces] = useState<Workspace[]>(cachedWorkspaces);
  const [scenarios, setScenarios] = useState<Scenario[]>(cachedScenarios);
  const [currentWorkspace, setCurrentWorkspaceState] = useState<string>('');
  const [currentScenario, setCurrentScenarioState] = useState<string>('');
  const { show, hide } = useGlobalLoading();

  /* ── 加载工作空间（仅执行一次） ── */
  const loadWorkspaces = useCallback(async () => {
    if (cachedWorkspaces.length > 0) {
      setWorkspaces(cachedWorkspaces);
      const savedId = localStorage.getItem('currentWorkspaceId');
      const valid = cachedWorkspaces.find(w => w.workspace_id === savedId);
      const targetId = valid?.workspace_id ?? cachedWorkspaces[0]?.workspace_id ?? '';
      setCurrentWorkspaceState(targetId);
      localStorage.setItem('currentWorkspaceId', targetId);
      return;
    }
    show('加载工作空间...', 0);
    try {
      const data = await api.listWorkspaces();
      if (data && data.length > 0) {
        cachedWorkspaces = data;
        setWorkspaces(data);
        // 同步写入统一缓存，供 Layout 组件复用
        setWorkspacesCache(data);
        const savedId = localStorage.getItem('currentWorkspaceId');
        const valid = data.find(w => w.workspace_id === savedId);
        const targetId = valid?.workspace_id ?? data[0]?.workspace_id ?? '';
        setCurrentWorkspaceState(targetId);
        localStorage.setItem('currentWorkspaceId', targetId);
        setCachedWorkspaceId(targetId);
      }
    } catch (e) {
      console.error('加载工作空间失败:', e);
    } finally {
      hide();
    }
  }, [show, hide]);

  /* ── 加载场景 ── */
  const loadScenarios = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return;
    try {
      const data = await api.listScenarios(workspaceId);
      cachedScenarios = data ?? [];
      setScenarios(cachedScenarios);
      // 同步写入统一缓存
      setScenariosCache(workspaceId, cachedScenarios);
      const saved = localStorage.getItem('currentScenarioId');
      const valid = (data ?? []).find(s => s.scenario_id === saved);
      if (valid) setCurrentScenarioState(valid.scenario_id);
      else if (data && data.length > 0) setCurrentScenarioState(data[0].scenario_id);
    } catch (e) {
      console.error('加载场景失败:', e);
    }
  }, [currentWorkspace]);

  /* ── 初始加载 ── */
  useEffect(() => {
    if (isLoginPage) return;
    loadWorkspaces();
  }, [isLoginPage, loadWorkspaces]);

  useEffect(() => {
    if (currentWorkspace) loadScenarios(currentWorkspace);
  }, [currentWorkspace, loadScenarios]);

  /* ── WorkspaceContext 回调（供 Layout 内组件触发刷新） ── */
  const reloadWorkspaces = useCallback(async () => {
    cachedWorkspaces = [];
    setWorkspacesCache([]);
    await loadWorkspaces();
  }, [loadWorkspaces]);

  const reloadScenarios = useCallback(async () => {
    cachedScenarios = [];
    const wid = localStorage.getItem('currentWorkspaceId') || '';
    if (wid) setScenariosCache(wid, []);
    if (currentWorkspace) await loadScenarios(currentWorkspace);
  }, [currentWorkspace, loadScenarios]);

  const handleWorkspaceChange = useCallback((workspaceId: string) => {
    setCurrentWorkspaceState(workspaceId);
    localStorage.setItem('currentWorkspaceId', workspaceId);
    setCachedWorkspaceId(workspaceId);
    clearScenariosCache();
    // 切换工作空间后重新加载场景
    setScenarios([]);
    cachedScenarios = [];
    loadScenarios(workspaceId);
  }, [loadScenarios]);

  const handleScenarioChange = useCallback((scenarioId: string) => {
    setCurrentScenarioState(scenarioId);
    localStorage.setItem('currentScenarioId', scenarioId);
    setCachedScenarioId(scenarioId);
  }, []);

  /* ── Context 值（用 useMemo 稳定引用） ── */
  const workspaceContextValue = useMemo(() => ({
    currentWorkspace,
    setCurrentWorkspace: handleWorkspaceChange,
    workspaces,
    reloadWorkspaces,
  }), [currentWorkspace, workspaces, reloadWorkspaces, handleWorkspaceChange]);

  const scenarioContextValue = useMemo(() => ({
    currentScenario,
    setCurrentScenario: handleScenarioChange,
    scenarios,
    reloadScenarios,
  }), [currentScenario, scenarios, reloadScenarios, handleScenarioChange]);

  if (isLoginPage) {
    return <AppRoutes />;
  }

  /* ── 未 ready 时渲染一个轻量 loading（不触发 Layout 完整的 useEffect） ── */
  if (workspaces.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <WorkspaceContext.Provider value={workspaceContextValue}>
      <ScenarioContext.Provider value={scenarioContextValue}>
        {isAgentMode ? (
          <AgentLayout>
            <AppRoutes />
          </AgentLayout>
        ) : (
          <AdminLayout>
            <AppRoutes />
          </AdminLayout>
        )}
      </ScenarioContext.Provider>
    </WorkspaceContext.Provider>
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
