import { Layout, Select, message, Button, Tooltip, Dropdown } from 'antd';
import {
  SwitcherOutlined,
  QuestionCircleOutlined,
  LogoutOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { LanguageSwitcher } from './LanguageSwitcher';
import { ThemeColorPicker } from './ThemeColorPicker';
import type { Workspace, Scenario } from './LayoutContexts';
import type { ColorTheme } from '../stores/layoutStore';

const { Header } = Layout;

interface LayoutHeaderProps {
  /** 左侧额外内容（如页面标题、返回按钮） */
  leftExtra?: React.ReactNode;
  /** 右侧额外内容（如模式切换按钮） */
  rightExtra?: React.ReactNode;
  /** 工作空间列表 */
  workspaces: Workspace[];
  /** 场景列表 */
  scenarios: Scenario[];
  /** 工作空间加载中 */
  loading: boolean;
  /** 场景加载中 */
  scenariosLoading: boolean;
  /** 当前工作空间 ID */
  activeWorkspaceId: string;
  /** 当前场景 ID */
  activeScenarioId: string;
  /** 切换工作空间回调 */
  onWorkspaceChange: (value: string) => void;
  /** 切换场景回调 */
  onScenarioChange: (value: string) => void;
  /** 主题 */
  theme: string;
  /** 主题色 */
  colorTheme: ColorTheme;
  /** 切换主题回调 */
  onToggleTheme: () => void;
  /** 设置主题色回调 */
  onColorThemeChange: (c: ColorTheme) => void;
  /** 重置引导 tour */
  onResetTour: () => void;
  /** 用户名 */
  username: string;
  /** 退出登录回调 */
  onLogout: () => void;
}

/**
 * 共享 Header 组件 —— AdminLayout 和 AgentLayout 共用同一套样式与结构。
 * 左侧：工作空间 + 场景选择器（+ leftExtra 插槽）
 * 右侧：语言切换 + 主题色 + 明暗切换 + 帮助 + rightExtra 插槽 + 用户头像
 */
export function LayoutHeader({
  leftExtra,
  rightExtra,
  workspaces,
  scenarios,
  loading,
  scenariosLoading,
  activeWorkspaceId,
  activeScenarioId,
  onWorkspaceChange,
  onScenarioChange,
  theme,
  colorTheme,
  onToggleTheme,
  onColorThemeChange,
  onResetTour,
  username,
  onLogout,
}: LayoutHeaderProps) {
  const navigate = useNavigate();

  return (
    <Header
      className="odap-layout-header"
      style={{
        height: 48,
        lineHeight: '48px',
        padding: '0 16px',
        background: 'var(--odap-color-bg-primary)',
        borderBottom: '1px solid var(--odap-color-border-light)',
        boxShadow: 'var(--odap-shadow-xs)',
        position: 'sticky',
        top: 0,
        zIndex: 99,
      }}
    >
      {/* Left: selectors + leftExtra slot */}
      <div className="odap-header-left">
        {leftExtra}

        <div className="odap-header-selector">
          <span className="odap-header-selector-label">工作空间</span>
          {loading ? (
            <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 13 }}>加载中…</span>
          ) : workspaces.length > 0 ? (
            <Select
              value={activeWorkspaceId || undefined}
              onChange={onWorkspaceChange}
              size="small"
              style={{ width: 160 }}
              options={workspaces.map((w) => ({
                value: w.workspace_id,
                label: w.name,
              }))}
            />
          ) : (
            <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 13 }}>暂无</span>
          )}
        </div>

        <div className="odap-header-selector">
          <span className="odap-header-selector-label">场景</span>
          {scenariosLoading ? (
            <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 13 }}>加载中…</span>
          ) : scenarios.length > 0 ? (
            <Select
              value={activeScenarioId || undefined}
              onChange={onScenarioChange}
              size="small"
              style={{ width: 160 }}
              options={scenarios.map((s) => ({
                value: s.scenario_id,
                label: s.name || s.scenario_id, // 防御：name 为空时显示 ID
              }))}
            />
          ) : (
            <span style={{ color: 'var(--odap-color-text-tertiary)', fontSize: 13 }}>暂无</span>
          )}
        </div>
      </div>

      {/* Right: actions + rightExtra slot */}
      <div className="odap-header-right">
        <LanguageSwitcher size="small" />

        <ThemeColorPicker value={colorTheme} onChange={onColorThemeChange} size="small" />

        <Tooltip title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}>
          <Button
            type="text"
            size="small"
            icon={theme === 'light' ? <span style={{ fontSize: 14 }}>🌙</span> : <span style={{ fontSize: 14 }}>☀️</span>}
            onClick={onToggleTheme}
            style={{ color: 'var(--odap-color-text-secondary)' }}
          />
        </Tooltip>

        <Tooltip title="帮助与引导">
          <Button
            type="text"
            size="small"
            icon={<QuestionCircleOutlined />}
            onClick={onResetTour}
            style={{ color: 'var(--odap-color-text-secondary)' }}
          />
        </Tooltip>

        {rightExtra}

        <Dropdown
          menu={{
            items: [
              {
                key: 'logout',
                icon: <LogoutOutlined />,
                label: '退出登录',
                onClick: onLogout,
              },
            ],
          }}
          placement="bottomRight"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--odap-color-primary-600), var(--odap-color-accent-500))',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {username?.[0]?.toUpperCase() || '?'}
            </div>
          </div>
        </Dropdown>
      </div>
    </Header>
  );
}
