/**
 * 主题运行时：把 Token 真源的 CSS 变量投影成 Ant Design 6 的 ConfigProvider token
 *
 * 对接口径（UIUX §3.6）：CSS 变量（Token）→ html[data-*] → ConfigProvider.token
 * 组件层不得出现 hex 字面量，AntD 的主题也一样从这里取，而不是本地调色板常量。
 *
 * 实现说明：DOM（html[data-appearance]/[data-accent]）是 React 之外的「外部系统」，
 * 因此用 useLayoutEffect 写入属性 + useSyncExternalStore 订阅重读，
 * 而不是在 effect 里同步 setState（会触发级联渲染，也被 react-hooks 规则禁止）。
 */
import { useLayoutEffect, useSyncExternalStore } from 'react';
import { applyColorTheme } from './colorThemeUtils';

export interface ThemeRuntimeTokens {
  /** 强调实心色（按钮底） */
  accentSolid: string;
  /** 强调色（亮/暗面自动取 600/400） */
  accent: string;
  /** 强调色淡底 */
  accentSubtle: string;
  /** 强调色描边 */
  accentBorder: string;
  fg: string;
  fgSecondary: string;
  bgLayout: string;
  bgContainer: string;
  bgElevated: string;
  border: string;
  success: string;
  warn: string;
  danger: string;
  info: string;
}

const VAR_NAMES: Record<keyof ThemeRuntimeTokens, string> = {
  accentSolid: '--odap-button-primary-bg',
  accent: '--odap-color-accent',
  accentSubtle: '--odap-color-accent-subtle',
  accentBorder: '--odap-color-accent-border',
  fg: '--odap-color-fg',
  fgSecondary: '--odap-color-fg-secondary',
  bgLayout: '--odap-color-bg',
  bgContainer: '--odap-color-surface',
  bgElevated: '--odap-color-surface-raised',
  border: '--odap-color-border',
  success: '--odap-color-success',
  warn: '--odap-color-warn',
  danger: '--odap-color-danger',
  info: '--odap-color-info',
};

const TOKEN_KEYS = Object.keys(VAR_NAMES) as Array<keyof ThemeRuntimeTokens>;

function emptyTokens(): ThemeRuntimeTokens {
  return Object.fromEntries(TOKEN_KEYS.map((k) => [k, ''] as const)) as unknown as ThemeRuntimeTokens;
}

function readTokens(): ThemeRuntimeTokens {
  if (typeof window === 'undefined' || typeof document === 'undefined') return emptyTokens();
  const computed = getComputedStyle(document.documentElement);
  const result = emptyTokens();
  for (const key of TOKEN_KEYS) {
    result[key] = computed.getPropertyValue(VAR_NAMES[key]).trim();
  }
  return result;
}

/** 模块级外部 store：DOM 上的样式变化 → 通知订阅者 */
let snapshot: ThemeRuntimeTokens = readTokens();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): ThemeRuntimeTokens {
  return snapshot;
}

/** 重新从 DOM 读一次 Token；仅在布局阶段调用（属性已写入） */
function refreshSnapshot(): void {
  snapshot = readTokens();
  for (const listener of listeners) listener();
}

/**
 * @param theme 'light' | 'dark'（旧 store 的取值）
 * @param colorTheme 旧 store 的色相键，内部映射为 data-accent
 */
export function useThemeRuntime(theme: string, colorTheme: string): ThemeRuntimeTokens {
  const tokens = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useLayoutEffect(() => {
    applyColorTheme(colorTheme, theme === 'dark');
    document.documentElement.setAttribute('data-theme', theme);
    refreshSnapshot();
  }, [theme, colorTheme]);

  return tokens;
}
