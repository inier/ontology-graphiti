import React, { useState, useCallback } from 'react';
import { Tooltip, Empty } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useLayoutStore, type QuickAction } from '@/modules/shared/stores/layoutStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/**
 * QuickActionBar — 快捷操作区
 *
 * 功能:
 *   - 显示快捷操作图标
 *   - 点击快捷图标打开对应 tab
 *   - 拖拽 tab 到此区域可添加快捷操作
 *   - 右键移除快捷操作
 */

interface QuickActionBarProps {
  onQuickActionClick?: (action: QuickAction) => void;
}

export function QuickActionBar({ onQuickActionClick }: QuickActionBarProps) {
  const { quickActions, addQuickAction, removeQuickAction, tabs } = useLayoutStore();
  const { t } = useI18n();
  const [dragOver, setDragOver] = useState(false);

  const handleClick = useCallback(
    (action: QuickAction) => {
      onQuickActionClick?.(action);
    },
    [onQuickActionClick],
  );

  const handleRemove = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      removeQuickAction(id);
    },
    [removeQuickAction],
  );

  /* 拖拽 tab 到快捷区 */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDragOver(true);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const tabId = e.dataTransfer.getData('text/plain');
    if (tabId) {
      addQuickAction(tabId);
    }
  };

  return (
    <div
      className={`odap-quick-action-bar ${dragOver ? 'drag-over' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      <div className="odap-quick-action-header">
        <span className="odap-quick-action-title">{t('快捷操作')}</span>
      </div>

      {quickActions.length === 0 ? (
        <div className="odap-quick-action-empty">
          <Empty
            description={dragOver ? t('松开添加到快捷区') : t('拖拽任务至此添加快捷操作')}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      ) : (
        <div className="odap-quick-action-list">
          {quickActions.map((action) => (
            <Tooltip key={action.id} title={action.title} placement="right">
              <div
                className="odap-quick-action-item"
                onClick={() => handleClick(action)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  handleRemove(e as unknown as React.MouseEvent, action.id);
                }}
              >
                <span className="odap-quick-action-icon">{action.icon || '📌'}</span>
                <span className="odap-quick-action-label">{action.title}</span>
                <button
                  className="odap-quick-action-close"
                  onClick={(e) => handleRemove(e, action.id)}
                >
                  <CloseOutlined />
                </button>
              </div>
            </Tooltip>
          ))}
        </div>
      )}
    </div>
  );
}
