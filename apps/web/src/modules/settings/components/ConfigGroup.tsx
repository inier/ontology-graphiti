import { ConfigPanelLabel } from './ConfigPanelLabel';
import { ConfigPanelBody } from './ConfigPanelBody';
import type { ServiceConfig, ServiceCategory } from '../types';

interface ConfigGroupProps {
  config: ServiceConfig;
  onSave: (category: ServiceCategory, items: Array<{ key: string; value: string }>) => void;
  saving?: boolean;
}

/**
 * 一个 Collapse 面板描述符（标题 + 右侧操作 + 表单内容）。
 *
 * `buildConfigPanel` 必须是纯函数：Collapse 需要 items 描述符数组，
 * 若在此处调用 hooks 会违反 hook 调用规则（在 map 中调用）。因此所有
 * 需要状态的 UI 都下沉为独立组件（`ConfigPanelLabel` / `ConfigPanelBody`）。
 *
 * 这两个组件已拆到同目录的独立文件：本文件只导出类型与工厂函数，
 * 保持「一个模块要么只导出组件，要么不含组件」以便 react-refresh 正常工作。
 */
export interface ConfigPanel {
  key: ServiceCategory;
  label: React.ReactNode;
  extra: React.ReactNode;
  children: React.ReactNode;
}

export function buildConfigPanel({ config, onSave, saving = false }: ConfigGroupProps): ConfigPanel {
  return {
    key: config.category,
    label: <ConfigPanelLabel config={config} />,
    extra: null,
    children: <ConfigPanelBody config={config} onSave={onSave} saving={saving} />,
  };
}
