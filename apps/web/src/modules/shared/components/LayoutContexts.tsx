/**
 * LayoutContexts — ProLayout 上下文定义（独立模块）
 *
 * 从 AppLayout.tsx 提取，供 ProLayout.tsx 和外部页面共同引用。
 * 消除 ProLayout → AppLayout 的循环依赖。
 */
import { createContext, useContext, type ReactNode } from 'react';

/* ═══════════════════════════════════════════════════════════
 * 类型定义
 * ═══════════════════════════════════════════════════════════ */

export interface Workspace {
  workspace_id: string;
  name: string;
}

export interface Scenario {
  scenario_id: string;
  name: string;
  description?: string;
  workspace_id: string;
  ontology_id?: string;
  current_ontology_version?: string;
}

export interface WorkspaceContextType {
  currentWorkspace: string;
  setCurrentWorkspace: (id: string) => void;
  workspaces: Workspace[];
  reloadWorkspaces: () => Promise<void>;
}

export interface ScenarioContextType {
  currentScenario: string;
  setCurrentScenario: (id: string) => void;
  scenarios: Scenario[];
  reloadScenarios: () => Promise<void>;
}

export interface OntologyVersionContextType {
  currentOntologyId: string;
  currentVersionId: string;
}

export interface RightPanelContextType {
  showRightPanel: boolean;
  setShowRightPanel: (show: boolean) => void;
  rightPanelContent: ReactNode;
  setRightPanelContent: (content: ReactNode) => void;
  rightPanelTitle: string;
  setRightPanelTitle: (title: string) => void;
}

/* ═══════════════════════════════════════════════════════════
 * Context 定义
 * ═══════════════════════════════════════════════════════════ */

export const WorkspaceContext = createContext<WorkspaceContextType>({
  currentWorkspace: '',
  setCurrentWorkspace: () => {},
  workspaces: [],
  reloadWorkspaces: async () => {},
});

export const ScenarioContext = createContext<ScenarioContextType>({
  currentScenario: '',
  setCurrentScenario: () => {},
  scenarios: [],
  reloadScenarios: async () => {},
});

export const OntologyVersionContext = createContext<OntologyVersionContextType>({
  currentOntologyId: '',
  currentVersionId: '',
});

export const RightPanelContext = createContext<RightPanelContextType>({
  showRightPanel: false,
  setShowRightPanel: () => {},
  rightPanelContent: null,
  setRightPanelContent: () => {},
  rightPanelTitle: '',
  setRightPanelTitle: () => {},
});

/* ═══════════════════════════════════════════════════════════
 * 便利 Hooks
 * ═══════════════════════════════════════════════════════════ */

export const useWorkspace = () => useContext(WorkspaceContext);
export const useScenario = () => useContext(ScenarioContext);
export const useOntologyVersion = () => useContext(OntologyVersionContext);
export const useRightPanel = () => useContext(RightPanelContext);
