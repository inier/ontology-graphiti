/**
 * useGraphToolbar — 图谱工具栏通用状态管理 hook
 *
 * 管理：搜索关键词、当前布局、筛选条件、工具栏展开/折叠
 */
import { useState, useCallback } from 'react';
import type { SigmaLayoutType, CytoscapeLayoutType } from '../types';

interface UseGraphToolbarOptions<T extends string> {
  layouts: readonly { value: T; label: string }[];
  defaultLayout?: T;
  onSearch?: (keyword: string) => string | null;
  onLayoutChange?: (layout: T) => void;
}

interface UseGraphToolbarReturn<T extends string> {
  searchKeyword: string;
  currentLayout: T;
  setSearchKeyword: (kw: string) => void;
  handleSearch: (kw: string) => string | null;
  setLayout: (layout: T) => void;
}

export function useGraphToolbar<T extends string>({
  layouts,
  defaultLayout,
  onSearch,
  onLayoutChange,
}: UseGraphToolbarOptions<T>): UseGraphToolbarReturn<T> {
  const [searchKeyword, setSearchKeyword] = useState('');
  const [currentLayout, setCurrentLayout] = useState<T>(defaultLayout ?? layouts[0].value);

  const handleSearch = useCallback((kw: string): string | null => {
    setSearchKeyword(kw);
    if (!kw.trim()) return null;
    return onSearch?.(kw) ?? null;
  }, [onSearch]);

  const setLayout = useCallback((layout: T) => {
    setCurrentLayout(layout);
    onLayoutChange?.(layout);
  }, [onLayoutChange]);

  return {
    searchKeyword,
    currentLayout,
    setSearchKeyword,
    handleSearch,
    setLayout,
  };
}

// 预设类型
export type SigmaToolbar = UseGraphToolbarReturn<SigmaLayoutType>;
export type CytoscapeToolbar = UseGraphToolbarReturn<CytoscapeLayoutType>;
