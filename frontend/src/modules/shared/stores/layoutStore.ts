import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/* ──────────────────────────────────────────────────────────────────
 * Layout Store — 4 列布局状态管理
 *
 * 列结构（从左到右）:
 *   1. 菜单区 (Menu)        — ProLayout 内置，折叠/展开
 *   2. 功能区 (Task)        — 任务 tab + 快捷操作
 *   3. 工作区 (Workspace)   — 主体内容
 *   4. 扩展区 (Extension)   — AI 助手等
 *
 * 功能区内部纵向分割:
 *   - 任务区 (上)  — 历史 tab 列表/卡片
 *   - 快捷操作区(下) — 快捷图标
 * ────────────────────────────────────────────────────────────────── */

export interface TaskTab {
  id: string;
  title: string;
  path: string;
  icon?: string;
  /** 是否激活 */
  active: boolean;
  /** 创建时间戳 */
  createdAt: number;
  /** 最后访问时间戳 */
  lastVisitedAt: number;
  /** 概要信息（卡片视图用） */
  summary?: string;
  /** 刷新令牌：每次刷新递增，KeepAliveOutlet 据此销毁并重建组件 */
  refreshToken: number;
}

export interface QuickAction {
  id: string;
  tabId: string;
  title: string;
  path: string;
  icon?: string;
}

export type TaskViewMode = 'list' | 'card';
export type ColorTheme = 'indigo' | 'blue' | 'green' | 'violet' | 'amber';

/** 扩展区中可注册的扩展定义（仅存储元数据，组件由 UI 层映射） */
export interface ExtensionSpec {
  /** 唯一标识，如 'ai-chat'、'tab-preview' */
  id: string;
  /** 展示名称 */
  name: string;
  /** Ant Design 图标名（用于跨层传递，UI 层解析为 React 组件） */
  iconName: string;
  /** 排序权重，越小越靠前 */
  order: number;
}

interface LayoutState {
  /* ── 列折叠状态 ── */
  /** 功能区（第2列）是否折叠 */
  taskPanelCollapsed: boolean;
  /** 扩展区（第4列）是否折叠 */
  extensionPanelCollapsed: boolean;
  /** 扩展区是否 hold（hold=true 占布局宽度，false 切换为抽屉浮层） */
  extensionHold: boolean;

  /* ── 列宽度（百分比，仅展开时生效） ── */
  /** 功能区宽度占比（默认 10%） */
  taskPanelWidth: number;
  /** 扩展区宽度占比（默认 10%） */
  extensionPanelWidth: number;

  /* ── 功能区内部分割 ── */
  /** 快捷操作区高度占比（默认 10%） */
  quickActionHeight: number;

  /* ── 任务 tab ── */
  tabs: TaskTab[];
  /** 当前激活的 tab id */
  activeTabId: string | null;
  /** 任务区视图模式 */
  taskViewMode: TaskViewMode;

  /* ── 快捷操作 ── */
  quickActions: QuickAction[];

  /* ── 主题色 ── */
  colorTheme: ColorTheme;

  /* ── 亮暗模式 ── */
  theme: 'light' | 'dark';

  /* ── 扩展区注册表 ── */
  /** 已注册的扩展列表（元数据） */
  extensionSpecs: ExtensionSpec[];
  /** 当前激活的扩展 ID */
  activeExtensionId: string | null;

  /* ── Tab 预览（扩展区显示） ── */
  previewTabId: string | null;

  /* ── Actions ── */
  toggleTaskPanel: () => void;
  toggleExtensionPanel: () => void;
  toggleExtensionHold: () => void;
  setTaskPanelWidth: (width: number) => void;
  setExtensionPanelWidth: (width: number) => void;
  setQuickActionHeight: (height: number) => void;
  setColorTheme: (theme: ColorTheme) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setPreviewTab: (tabId: string | null) => void;
  registerExtension: (spec: ExtensionSpec) => void;
  unregisterExtension: (id: string) => void;
  setActiveExtension: (id: string | null) => void;

  /* Tab actions */
  openTab: (tab: Omit<TaskTab, 'active' | 'createdAt' | 'lastVisitedAt'>) => void;
  closeTab: (id: string) => void;
  closeAllTabs: () => void;
  closeTabsAbove: (id: string) => void;
  closeTabsBelow: (id: string) => void;
  refreshTab: (id: string) => void;
  setActiveTab: (id: string) => void;
  reorderTabs: (fromId: string, toId: string) => void;
  setTaskViewMode: (mode: TaskViewMode) => void;

  /* Quick action actions */
  addQuickAction: (tabId: string) => void;
  removeQuickAction: (id: string) => void;
}

const MIN_PANEL_WIDTH = 5;
const MAX_PANEL_WIDTH = 30;
const MIN_QUICK_HEIGHT = 5;
const MAX_QUICK_HEIGHT = 40;

const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      /* ── 初始状态 ── */
      taskPanelCollapsed: false,
      extensionPanelCollapsed: true,
      taskPanelWidth: 10,
      extensionPanelWidth: 10,
      quickActionHeight: 10,

      tabs: [],
      activeTabId: null,
      taskViewMode: 'list',

      quickActions: [],

      /* ── 主题色 ── */
      colorTheme: 'indigo',

      /* ── 亮暗模式（从 localStorage 读取初始值） ── */
      theme: (localStorage.getItem('odap-theme') as 'light' | 'dark') || 'light',

      /* ── 扩展区注册表 ── */
      extensionSpecs: [],
      activeExtensionId: null,
      extensionHold: true, // 默认 hold 模式（占布局宽度）

      /* ── Tab 预览 ── */
      previewTabId: null,

      /* ── 面板控制 ── */
      toggleTaskPanel: () => set((s) => ({ taskPanelCollapsed: !s.taskPanelCollapsed })),
      toggleExtensionPanel: () => set((s) => ({ extensionPanelCollapsed: !s.extensionPanelCollapsed })),
      toggleExtensionHold: () => set((s) => ({ extensionHold: !s.extensionHold })),
      setTaskPanelWidth: (width) => set({ taskPanelWidth: clamp(width, MIN_PANEL_WIDTH, MAX_PANEL_WIDTH) }),
      setExtensionPanelWidth: (width) => set({ extensionPanelWidth: clamp(width, MIN_PANEL_WIDTH, MAX_PANEL_WIDTH) }),
      setQuickActionHeight: (height) => set({ quickActionHeight: clamp(height, MIN_QUICK_HEIGHT, MAX_QUICK_HEIGHT) }),
      setColorTheme: (colorTheme) => set({ colorTheme }),
      setTheme: (theme) => {
        localStorage.setItem('odap-theme', theme);
        set({ theme });
      },
      setPreviewTab: (previewTabId) => set({ previewTabId }),
      registerExtension: (spec) => set((s) => {
        if (s.extensionSpecs.find((e) => e.id === spec.id)) return s;
        return { extensionSpecs: [...s.extensionSpecs, spec].sort((a, b) => a.order - b.order) };
      }),
      unregisterExtension: (id) => set((s) => ({
        extensionSpecs: s.extensionSpecs.filter((e) => e.id !== id),
        activeExtensionId: s.activeExtensionId === id ? null : s.activeExtensionId,
      })),
      setActiveExtension: (id) => set({ activeExtensionId: id }),

      /* ── Tab 操作 ── */
      openTab: (tab) => {
        const now = Date.now();
        set((state) => {
          const existing = state.tabs.find((t) => t.path === tab.path);
          if (existing) {
            return {
              activeTabId: existing.id,
              tabs: state.tabs.map((t) =>
                t.id === existing.id
                  ? { ...t, active: true, lastVisitedAt: now, title: tab.title, icon: tab.icon, summary: tab.summary }
                  : { ...t, active: false }
              ),
            };
          }
          const newTab: TaskTab = {
            ...tab,
            id: tab.id || `tab-${now}-${Math.random().toString(36).slice(2, 8)}`,
            active: true,
            createdAt: now,
            lastVisitedAt: now,
            refreshToken: 0,
          };
          return {
            activeTabId: newTab.id,
            tabs: [...state.tabs.map((t) => ({ ...t, active: false })), newTab],
          };
        });
      },

      closeTab: (id) =>
        set((state) => {
          const idx = state.tabs.findIndex((t) => t.id === id);
          if (idx === -1) return state;
          const newTabs = state.tabs.filter((t) => t.id !== id);
          let newActiveId = state.activeTabId;
          if (state.activeTabId === id) {
            newActiveId = newTabs.length > 0 ? newTabs[Math.min(idx, newTabs.length - 1)].id : null;
          }
          return {
            tabs: newTabs.map((t) => ({ ...t, active: t.id === newActiveId })),
            activeTabId: newActiveId,
          };
        }),

      closeAllTabs: () => set({ tabs: [], activeTabId: null }),

      closeTabsAbove: (id) =>
        set((state) => {
          const idx = state.tabs.findIndex((t) => t.id === id);
          if (idx === -1) return state;
          return {
            tabs: state.tabs.slice(idx),
          };
        }),

      closeTabsBelow: (id) =>
        set((state) => {
          const idx = state.tabs.findIndex((t) => t.id === id);
          if (idx === -1) return state;
          return {
            tabs: state.tabs.slice(0, idx + 1),
          };
        }),

      refreshTab: (id) =>
        set((state) => ({
          tabs: state.tabs.map((t) =>
            t.id === id ? { ...t, lastVisitedAt: Date.now(), refreshToken: t.refreshToken + 1 } : t,
          ),
        })),

      setActiveTab: (id) =>
        set((state) => ({
          activeTabId: id,
          tabs: state.tabs.map((t) => ({ ...t, active: t.id === id, lastVisitedAt: t.id === id ? Date.now() : t.lastVisitedAt })),
        })),

      reorderTabs: (fromId, toId) =>
        set((state) => {
          const fromIdx = state.tabs.findIndex((t) => t.id === fromId);
          const toIdx = state.tabs.findIndex((t) => t.id === toId);
          if (fromIdx === -1 || toIdx === -1) return state;
          const newTabs = [...state.tabs];
          const [moved] = newTabs.splice(fromIdx, 1);
          newTabs.splice(toIdx, 0, moved);
          return { tabs: newTabs };
        }),

      setTaskViewMode: (mode) => set({ taskViewMode: mode }),

      /* ── 快捷操作 ── */
      addQuickAction: (tabId) =>
        set((state) => {
          const tab = state.tabs.find((t) => t.id === tabId);
          if (!tab) return state;
          if (state.quickActions.some((q) => q.path === tab.path)) return state;
          return {
            quickActions: [
              ...state.quickActions,
              { id: `qa-${Date.now()}`, tabId, title: tab.title, path: tab.path, icon: tab.icon },
            ],
          };
        }),

      removeQuickAction: (id) =>
        set((state) => ({ quickActions: state.quickActions.filter((q) => q.id !== id) })),
    }),
    {
      name: 'odap-layout',
      partialize: (state) => ({
        taskPanelCollapsed: state.taskPanelCollapsed,
        extensionPanelCollapsed: state.extensionPanelCollapsed,
        taskPanelWidth: state.taskPanelWidth,
        extensionPanelWidth: state.extensionPanelWidth,
        quickActionHeight: state.quickActionHeight,
        taskViewMode: state.taskViewMode,
        quickActions: state.quickActions,
        tabs: state.tabs,
        activeTabId: state.activeTabId,
        colorTheme: state.colorTheme,
        theme: state.theme,
        activeExtensionId: state.activeExtensionId,
        extensionHold: state.extensionHold,
      }),
    },
  ),
);
