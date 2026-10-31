/**
 * 一级工作区导轨（F4 / AC-19：全局导航仅呈现 6 个工作区）
 *
 * 视觉：图标 + 悬停文字提示，命中区 ≥44x44（--odap-size-control-xl）。
 * 数据：来自 navigation/workspaces.ts（单一真源），因此导航项与路由表可被同一测试断言。
 */
import { Tooltip } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { Icon } from './Icon';
import { WORKSPACES, findWorkspaceByPath } from '../navigation/workspaces';

export interface WorkspaceRailProps {
  /** 折叠态：仅显示图标；展开态：图标 + 文字 */
  collapsed?: boolean;
}

export function WorkspaceRail({ collapsed = true }: WorkspaceRailProps) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const active = findWorkspaceByPath(pathname);

  return (
    <nav
      aria-label="工作区导航"
      style={{
        display: 'flex',
        flexDirection: collapsed ? 'column' : 'row',
        flexWrap: collapsed ? 'nowrap' : 'wrap',
        alignItems: 'center',
        gap: 'var(--odap-space-1)',
        padding: 'var(--odap-space-2)',
        borderBottom: 'var(--odap-sidebar-border-strong)',
      }}
    >
      {WORKSPACES.map((ws) => {
        const isActive = active?.id === ws.id;
        const button = (
          <button
            key={ws.id}
            type="button"
            aria-label={ws.label}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => navigate(ws.home)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--odap-space-1)',
              minWidth: 'var(--odap-size-control-xl)',
              minHeight: 'var(--odap-size-control-xl)',
              padding: collapsed ? 0 : '0 var(--odap-space-2)',
              border: 'none',
              borderRadius: 'var(--odap-nav-item-radius)',
              cursor: 'pointer',
              background: isActive ? 'var(--odap-nav-item-bg-active)' : 'transparent',
              color: isActive ? 'var(--odap-nav-item-fg-active)' : 'var(--odap-color-fg-secondary)',
              transition: 'background-color var(--odap-duration-fast) var(--odap-ease-standard)',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = 'var(--odap-nav-item-bg-hover)';
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = 'transparent';
            }}
          >
            <Icon role={ws.iconRole} size={24} />
            {collapsed ? null : (
              <span style={{ fontSize: 'var(--odap-font-size-xs)', whiteSpace: 'nowrap' }}>{ws.label}</span>
            )}
          </button>
        );

        return collapsed ? (
          <Tooltip key={ws.id} title={ws.label} placement="right">
            {button}
          </Tooltip>
        ) : (
          button
        );
      })}
    </nav>
  );
}
