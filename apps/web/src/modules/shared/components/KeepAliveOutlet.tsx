import { useState, useLayoutEffect, useRef, Activity, type ReactNode, useEffect } from 'react';
import { useLocation, useOutlet } from 'react-router-dom';
import { useLayoutStore } from '../stores/layoutStore';

interface CacheEntry {
  element: ReactNode;
  refreshToken: number;
}

/**
 * KeepAliveOutlet — 基于 React 19 <Activity> 的组件级 keep-alive 容器
 *
 * 原理:
 *   - 使用 useOutlet() 获取当前路由匹配的子路由元素
 *   - 将元素按 pathname + refreshToken 缓存到 state Map
 *   - 每个缓存项用 <Activity mode="visible"|"hidden"> 包裹:
 *       visible = 当前路由，正常渲染
 *       hidden  = 非激活路由，React 暂停其 effects、延迟更新、
 *                 保留 state 与 DOM（内部 display:none），但不再消耗渲染资源
 *   - 当 tab 关闭时，从缓存移除 → <Activity> 卸载，释放内存
 *   - 当 tab 刷新时，refreshToken 递增 → 缓存替换 → <Activity> 重建
 *
 * 相比 display:none 手动方案的改进:
 *   - 隐藏组件的 useEffect/useLayoutEffect 会被销毁，不再后台运行
 *   - 隐藏组件的状态更新被降级为低优先级，不阻塞可见内容
 *   - 状态保留由 React 内部保证，更可靠
 *
 * 使用方式:
 *   <Routes>
 *     <Route path="/login" element={<LoginPage />} />
 *     <Route element={<KeepAliveOutlet />}>
 *       <Route path="/my-agents" element={<MyAgents />} />
 *       ...
 *     </Route>
 *   </Routes>
 */
export function KeepAliveOutlet() {
  const location = useLocation();
  const outlet = useOutlet();
  const { tabs } = useLayoutStore();

  const [cache, setCache] = useState<Map<string, CacheEntry>>(new Map());
  const [prevPathname, setPrevPathname] = useState<string>('');
  const [prevRefreshToken, setPrevRefreshToken] = useState<number>(0);
  const [prevTabPaths, setPrevTabPaths] = useState<string>('');

  /* 当前路由对应的 refreshToken */
  const currentTab = tabs.find((t) => t.path === location.pathname);
  const currentRefreshToken = currentTab?.refreshToken ?? 0;
  const currentTabPaths = tabs.map((t) => t.path).join('\n');

  /* 1. 路由变化或刷新时，将当前 outlet 元素写入缓存
   *    关键：如果缓存中已有该路径且 refreshToken 未变 → 不覆盖
   *    避免 Zustand store 更新触发重渲染时，useOutlet() 新 element 覆盖旧缓存
   *    → 导致 <Activity> children 引用变化 → React 重新挂载组件 → 工作区刷新 */
  useEffect(() => {
    if (!outlet) return;
    
    if (location.pathname !== prevPathname || currentRefreshToken !== prevRefreshToken) {
      setPrevPathname(location.pathname);
      setPrevRefreshToken(currentRefreshToken);
      setCache((prev) => {
        const existing = prev.get(location.pathname);
        // ✅ 已有缓存且 refreshToken 未变 → 不覆盖（保持组件 alive）
        if (existing && existing.refreshToken === currentRefreshToken) {
          return prev;
        }
        // 首次访问 或 用户主动刷新 → 写入新 element
        const next = new Map(prev);
        next.set(location.pathname, { element: outlet, refreshToken: currentRefreshToken });
        return next;
      });
    }
  }, [outlet, location.pathname, currentRefreshToken, prevPathname, prevRefreshToken]);

  /* 2. tab 列表变化时清理已关闭 tab 的缓存（始终保留当前路由） */
  useEffect(() => {
    if (currentTabPaths === prevTabPaths) return;
    
    setPrevTabPaths(currentTabPaths);
    setCache((prev) => {
      const tabPaths = new Set(tabs.map((t) => t.path));
      tabPaths.add(location.pathname);
      let changed = false;
      const next = new Map(prev);
      for (const key of Array.from(next.keys())) {
        if (!tabPaths.has(key)) {
          next.delete(key);
          scrollPositions.current.delete(key);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [currentTabPaths, prevTabPaths, tabs, location.pathname]);

  /* 2b. 刷新时重置该 tab 的滚动位置 */
  useEffect(() => {
    if (currentRefreshToken > prevRefreshToken && location.pathname === prevPathname) {
      scrollPositions.current.delete(location.pathname);
    }
  }, [currentRefreshToken, prevRefreshToken, location.pathname, prevPathname]);

  /* 3. 渲染所有缓存元素，用 <Activity> 控制可见性
   *    key 包含 refreshToken，刷新时 key 变化 → React 卸载旧实例、挂载新实例 */

  /* ═══════════════════════════════════════════════════════════════
   * 4. 滚动位置保持 — 切换 tab 时保存/恢复工作区滚动位置
   *    <Activity> 保留组件 state 但不会保留 DOM 滚动位置，
   *    因此用 useLayoutEffect 在路由变化前后手动保存和恢复。
   * ═══════════════════════════════════════════════════════════════ */
  const scrollPositions = useRef<Map<string, number>>(new Map());

  useLayoutEffect(() => {
    const container = document.querySelector('.odap-col-workspace') as HTMLElement | null;
    if (!container) return;

    // 恢复当前路径的滚动位置
    const saved = scrollPositions.current.get(location.pathname);
    if (saved !== undefined) {
      // requestAnimationFrame 保证 DOM 已渲染完成再设置
      const raf = requestAnimationFrame(() => {
        container.scrollTop = saved;
      });
      return () => {
        cancelAnimationFrame(raf);
      };
    }

    // 无历史 → 滚动到顶部
    container.scrollTop = 0;

    // 路由变化时保存当前滚动位置
    return () => {
      scrollPositions.current.set(location.pathname, container.scrollTop);
    };
  }, [location.pathname]);

  /* 5. 渲染 */
  const entries = Array.from(cache.entries());

  return (
    <>
      {entries.map(([pathname, { element, refreshToken }]) => (
        <Activity
          key={`${pathname}#${refreshToken}`}
          mode={pathname === location.pathname ? 'visible' : 'hidden'}
          name={pathname}
        >
          {element}
        </Activity>
      ))}
    </>
  );
}
