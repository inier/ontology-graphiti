/**
 * 全局 Loading Store
 *
 * 用于页面级数据初始化时的全局 loading 遮罩。
 * 任何组件可通过 useGlobalLoading 触发全局 loading。
 *
 * 使用场景：
 * - 页面首次加载（如 MyAgents、OntologySemanticNetwork 等）
 * - 全局性操作（如工作空间切换后的数据刷新）
 *
 * 不适用场景：
 * - 组件内局部操作（如搜索、查询、表单提交）→ 用局部 Spin
 * - Table 翻页 → 用 Table loading prop
 * - Drawer/Modal 内操作 → 用局部 Spin
 */
import { create } from 'zustand';

interface GlobalLoadingState {
  /** 是否显示全局 loading */
  visible: boolean;
  /** loading 提示文字 */
  tip: string;
  /** 延迟显示（ms），避免闪烁，默认 200ms */
  delay: number;
  /** 显示全局 loading */
  show: (tip?: string, delay?: number) => void;
  /** 隐藏全局 loading */
  hide: () => void;
}

export const useGlobalLoading = create<GlobalLoadingState>((set) => ({
  visible: false,
  tip: '加载中...',
  delay: 200,
  show: (tip = '加载中...', delay = 200) => set({ visible: true, tip, delay }),
  hide: () => set({ visible: false, tip: '加载中...' }),
}));
