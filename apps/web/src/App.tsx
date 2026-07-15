import { useState, useEffect, useCallback, useMemo } from 'react';
import { BrowserRouter as Router, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { AdminLayout } from '@/modules/shared';
import { AgentLayout } from '@/modules/shared/components/AgentLayout';
import { AppRoutes } from './AppRoutes';
import { api } from '@/modules/shared/services/api';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import EmptyState from '@/modules/shared/components/organisms/EmptyState';
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

const LOAD_TIMEOUT_MS = 15000 as const;

type LoadStage = 'idle' | 'loading' | 'ready' | 'error';

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
  const [loadStage, setLoadStage] = useState<LoadStage>(
    cachedWorkspaces.length > 0 ? 'ready' : 'idle',
  );
  const [loadError, setLoadError] = useState<string>('');
  const { show, hide } = useGlobalLoading();

  const applyWorkspaceSelection = useCallback((list: readonly Workspace[]) => {
    const savedId = localStorage.getItem('currentWorkspaceId');
    const valid = list.find(w => w.workspace_id === savedId);
    const targetId = valid?.workspace_id ?? list[0]?.workspace_id ?? '';
    setCurrentWorkspaceState(targetId);
    localStorage.setItem('currentWorkspaceId', targetId);
    if (targetId) {
      setCachedWorkspaceId(targetId);
    }
  }, []);

  /* ── 加载工作空间（带超时与错误降级） ── */
  const loadWorkspaces = useCallback(async (signal: AbortSignal) => {
    if (cachedWorkspaces.length > 0) {
      setWorkspaces(cachedWorkspaces);
      applyWorkspaceSelection(cachedWorkspaces);
      setLoadStage('ready');
      return;
    }
    setLoadStage('loading');
    setLoadError('');
    show('加载工作空间...', 0);

    const controllerTimeout = new AbortController();
    const combinedSignal = AbortSignal.any([signal, controllerTimeout.signal]);
    let timeoutId: number | undefined;

    try {
      timeoutId = window.setTimeout(() => {
        controllerTimeout.abort(
          new DOMException('工作空间加载超时', 'AbortError'),
        );
      }, LOAD_TIMEOUT_MS);

      let data: Workspace[] | null = null;
      try {
        data = await api.listWorkspaces({ signal: combinedSignal });
      } finally {
        if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      }
      if (data && data.length > 0) {
        cachedWorkspaces = data;
        setWorkspaces(data);
        setWorkspacesCache(data);
        applyWorkspaceSelection(data);
        setLoadStage('ready');
      } else {
        cachedWorkspaces = [];
        setWorkspaces([]);
        setWorkspacesCache([]);
        setLoadStage('error');
        setLoadError('当前没有可用的工作空间，请先创建或检查后端服务。');
      }
    } catch (err) {
      if (signal.aborted) return;

      const isTimeoutAbort =
        controllerTimeout.signal.aborted ||
        (err instanceof DOMException && err.name === 'AbortError') ||
        (err instanceof Error && (err.name === 'AbortError' || err.message.includes('aborted')));

      if (isTimeoutAbort) {
        if (!signal.aborted) {
          setLoadStage('error');
          setLoadError('加载工作空间超时（超过 15 秒），请检查后端服务是否正常响应后重试。');
        }
        return;
      }

      const cause = err instanceof Error ? err : new Error(String(err));
      console.error('加载工作空间失败:', cause);
      setLoadStage('error');
      setLoadError(`加载工作空间失败：${cause.message}`);
    } finally {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      hide();
    }
  }, [show, hide, applyWorkspaceSelection]);

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
    const controller = new AbortController();
    void loadWorkspaces(controller.signal);
    return () => controller.abort();
  }, [isLoginPage, loadWorkspaces]);

  useEffect(() => {
    if (currentWorkspace) void loadScenarios(currentWorkspace);
  }, [currentWorkspace, loadScenarios]);

  /* ── WorkspaceContext 回调（供 Layout 内组件触发刷新） ── */
  const reloadWorkspaces = useCallback(async () => {
    cachedWorkspaces = [];
    setWorkspacesCache([]);
    const controller = new AbortController();
    await loadWorkspaces(controller.signal);
  }, [loadWorkspaces]);

  const handleRetryClick = useCallback(() => {
    const controller = new AbortController();
    void loadWorkspaces(controller.signal);
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

  if (loadStage === 'loading' || loadStage === 'idle') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" description="正在初始化..." />
      </div>
    );
  }

  if (loadStage === 'error') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', padding: 24 }}>
        <EmptyState
          title="后端服务连接失败"
          description={loadError || '无法获取工作空间列表，请检查后端服务是否正常启动并可访问。'}
          actionLabel="重新连接"
          onAction={handleRetryClick}
        />
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
