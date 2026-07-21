import React, { useState } from 'react';
import { CloseOutlined, DownOutlined, PushpinOutlined, PushpinFilled } from '@ant-design/icons';
import { Dropdown, Tooltip } from 'antd';
import type { ExtensionSpec } from '../stores/layoutStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/**
 * ExtensionPanel — 扩展区（第3列）通用内容容器
 *
 * 支持扩展注册表：通过 header 中的下拉菜单切换已注册的扩展。
 * 上方组件（ProLayout）通过 props 传入扩展列表和当前激活的扩展 ID。
 *
 * hold 模式：hold=true 时面板固定占布局宽度；hold=false 时以抽屉浮层呈现。
 */

interface ExtensionPanelProps {
  onClose: () => void;
  children?: React.ReactNode;
  title?: string;
  icon?: React.ReactNode;
  extensions?: ExtensionSpec[];
  activeExtensionId?: string | null;
  onSwitchExtension?: (id: string) => void;
  /** 是否 hold（固定模式） */
  hold?: boolean;
  /** 切换 hold 回调 */
  onToggleHold?: () => void;
}

export function ExtensionPanel({
  onClose,
  children,
  title,
  icon,
  extensions = [],
  activeExtensionId,
  onSwitchExtension,
  hold = true,
  onToggleHold,
}: ExtensionPanelProps) {
  const { t } = useI18n();
  const resolvedTitle = title || t('扩展区');
  const hasMultiple = extensions.length > 1;

  const switcherItems = extensions.map((ext) => ({
    key: ext.id,
    label: (
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          display: 'inline-flex',
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: ext.id === activeExtensionId ? 'var(--odap-color-primary)' : 'var(--odap-color-text-quaternary)',
        }} />
        {ext.name}
      </span>
    ),
    onClick: () => onSwitchExtension?.(ext.id),
  }));

  return (
    <div className="odap-extension-panel">
      <div className="odap-extension-header">
        {hasMultiple ? (
          <Dropdown menu={{ items: switcherItems }} trigger={['click']}>
            <span className="odap-extension-title" style={{ cursor: 'pointer' }}>
              {icon && (
                <span style={{ marginRight: 6, display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
              )}
              {resolvedTitle}
              <DownOutlined style={{ marginLeft: 6, fontSize: 10, opacity: 0.5 }} />
            </span>
          </Dropdown>
        ) : (
          <span className="odap-extension-title">
            {icon && (
              <span style={{ marginRight: 6, display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
            )}
            {resolvedTitle}
          </span>
        )}
        <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {onToggleHold && (
            <Tooltip title={hold ? t('取消固定（切换为抽屉）') : t('固定到面板')}>
              <button
                className="odap-extension-close"
                onClick={onToggleHold}
                title={hold ? t('取消固定') : t('固定')}
                style={{ color: hold ? 'var(--odap-color-primary)' : undefined }}
              >
                {hold ? <PushpinFilled /> : <PushpinOutlined />}
              </button>
            </Tooltip>
          )}
          <button className="odap-extension-close" onClick={onClose} title={t('折叠扩展区')}>
            <CloseOutlined />
          </button>
        </span>
      </div>
      <div className="odap-extension-content">
        {children || (
          <div style={{ padding: 16, color: 'var(--odap-color-text-secondary)', textAlign: 'center' }}>
            {t('扩展内容区')}
          </div>
        )}
      </div>
    </div>
  );
}
