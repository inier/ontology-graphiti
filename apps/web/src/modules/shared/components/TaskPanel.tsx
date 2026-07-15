import React, { useState, useRef, useCallback } from 'react';
import { Tooltip, Dropdown, Empty, Badge } from 'antd';
import {
  ReloadOutlined,
  CloseOutlined,
  CloseCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  PushpinOutlined,
  AppstoreOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { useLayoutStore, type TaskTab } from '@/modules/shared/stores/layoutStore';

/**
 * TaskPanel — 任务区面板
 *
 * 功能:
 *   - 列表/卡片两种视图切换
 *   - 点击 tab 激活
 *   - 右键菜单: 刷新/删除/关闭上方/关闭下方/关闭全部/添加到快捷区
 *   - 拖拽排序
 *   - 拖拽到快捷区
 */

interface TaskPanelProps {
  /** tab 点击回调（通常用于导航） */
  onTabClick?: (tab: TaskTab) => void;
  /** tab 刷新回调 */
  onTabRefresh?: (tab: TaskTab) => void;
}

export function TaskPanel({ onTabClick, onTabRefresh }: TaskPanelProps) {
  const {
    tabs,
    activeTabId,
    taskViewMode,
    setActiveTab,
    closeTab,
    closeAllTabs,
    closeTabsAbove,
    closeTabsBelow,
    refreshTab,
    reorderTabs,
    setTaskViewMode,
    addQuickAction,
  } = useLayoutStore();

  const [draggedTabId, setDraggedTabId] = useState<string | null>(null);
  const [dragOverTabId, setDragOverTabId] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (tab: TaskTab) => {
      setActiveTab(tab.id);
      onTabClick?.(tab);
    },
    [setActiveTab, onTabClick],
  );

  const handleRefresh = useCallback(
    (tab: TaskTab) => {
      refreshTab(tab.id);
      onTabRefresh?.(tab);
    },
    [refreshTab, onTabRefresh],
  );

  /* 右键菜单 */
  const getContextMenu = useCallback(
    (tab: TaskTab) => ({
      items: [
        {
          key: 'refresh',
          icon: <ReloadOutlined />,
          label: '刷新',
          onClick: () => handleRefresh(tab),
        },
        {
          key: 'close',
          icon: <CloseOutlined />,
          label: '关闭',
          disabled: tabs.length <= 1,
          onClick: () => closeTab(tab.id),
        },
        {
          key: 'closeAbove',
          icon: <ArrowUpOutlined />,
          label: '关闭上方任务',
          onClick: () => closeTabsAbove(tab.id),
        },
        {
          key: 'closeBelow',
          icon: <ArrowDownOutlined />,
          label: '关闭下方任务',
          onClick: () => closeTabsBelow(tab.id),
        },
        {
          key: 'closeAll',
          icon: <CloseCircleOutlined />,
          label: '关闭全部任务',
          onClick: () => closeAllTabs(),
        },
        { type: 'divider' as const },
        {
          key: 'pin',
          icon: <PushpinOutlined />,
          label: '添加到快捷区',
          onClick: () => addQuickAction(tab.id),
        },
      ],
    }),
    [tabs.length, handleRefresh, closeTab, closeTabsAbove, closeTabsBelow, closeAllTabs, addQuickAction],
  );

  /* 拖拽排序 */
  const handleDragStart = (e: React.DragEvent, tabId: string) => {
    setDraggedTabId(tabId);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', tabId);
  };

  const handleDragOver = (e: React.DragEvent, tabId: string) => {
    e.preventDefault();
    if (draggedTabId && draggedTabId !== tabId) {
      setDragOverTabId(tabId);
    }
  };

  const handleDrop = (e: React.DragEvent, targetTabId: string) => {
    e.preventDefault();
    if (draggedTabId && draggedTabId !== targetTabId) {
      reorderTabs(draggedTabId, targetTabId);
    }
    setDraggedTabId(null);
    setDragOverTabId(null);
  };

  const handleDragEnd = () => {
    setDraggedTabId(null);
    setDragOverTabId(null);
  };

  if (tabs.length === 0) {
    return (
      <div className="odap-task-panel" ref={panelRef}>
        <div className="odap-task-header">
          <span className="odap-task-title">任务</span>
          <div className="odap-task-view-toggle">
            <Tooltip title="列表视图">
              <button
                className={taskViewMode === 'list' ? 'active' : ''}
                onClick={() => setTaskViewMode('list')}
              >
                <UnorderedListOutlined />
              </button>
            </Tooltip>
            <Tooltip title="卡片视图">
              <button
                className={taskViewMode === 'card' ? 'active' : ''}
                onClick={() => setTaskViewMode('card')}
              >
                <AppstoreOutlined />
              </button>
            </Tooltip>
          </div>
        </div>
        <div className="odap-task-empty">
          <Empty description="暂无任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      </div>
    );
  }

  return (
    <div className="odap-task-panel" ref={panelRef}>
      <div className="odap-task-header">
        <span className="odap-task-title">任务</span>
        <div className="odap-task-view-toggle">
          <Tooltip title="列表视图">
            <button
              className={taskViewMode === 'list' ? 'active' : ''}
              onClick={() => setTaskViewMode('list')}
            >
              <UnorderedListOutlined />
            </button>
          </Tooltip>
          <Tooltip title="卡片视图">
            <button
              className={taskViewMode === 'card' ? 'active' : ''}
              onClick={() => setTaskViewMode('card')}
            >
              <AppstoreOutlined />
            </button>
          </Tooltip>
        </div>
      </div>

      <div className="odap-task-list">
        {taskViewMode === 'list' ? (
          /* ── 列表视图 ── */
          <div className="odap-task-list-view">
            {tabs.map((tab) => (
              <Dropdown key={tab.id} menu={getContextMenu(tab)} trigger={['contextMenu']}>
                <div
                  className={`odap-task-item ${tab.id === activeTabId ? 'active' : ''} ${dragOverTabId === tab.id ? 'drag-over' : ''} ${draggedTabId === tab.id ? 'dragging' : ''}`}
                  draggable
                  onDragStart={(e) => handleDragStart(e, tab.id)}
                  onDragOver={(e) => handleDragOver(e, tab.id)}
                  onDrop={(e) => handleDrop(e, tab.id)}
                  onDragEnd={handleDragEnd}
                  onClick={() => handleClick(tab)}
                >
                  <span className="odap-task-item-icon">{tab.icon || '📄'}</span>
                  <span className="odap-task-item-title">{tab.title}</span>
                  <button
                    className="odap-task-item-close"
                    onClick={(e) => {
                      e.stopPropagation();
                      closeTab(tab.id);
                    }}
                  >
                    <CloseOutlined />
                  </button>
                </div>
              </Dropdown>
            ))}
          </div>
        ) : (
          /* ── 卡片视图 ── */
          <div className="odap-task-card-view">
            {tabs.map((tab) => (
              <Dropdown key={tab.id} menu={getContextMenu(tab)} trigger={['contextMenu']}>
                <div
                  className={`odap-task-card ${tab.id === activeTabId ? 'active' : ''} ${dragOverTabId === tab.id ? 'drag-over' : ''} ${draggedTabId === tab.id ? 'dragging' : ''}`}
                  draggable
                  onDragStart={(e) => handleDragStart(e, tab.id)}
                  onDragOver={(e) => handleDragOver(e, tab.id)}
                  onDrop={(e) => handleDrop(e, tab.id)}
                  onDragEnd={handleDragEnd}
                  onClick={() => handleClick(tab)}
                >
                  <div className="odap-task-card-header">
                    <span className="odap-task-card-icon">{tab.icon || '📄'}</span>
                    <span className="odap-task-card-title">{tab.title}</span>
                    <button
                      className="odap-task-card-close"
                      onClick={(e) => {
                        e.stopPropagation();
                        closeTab(tab.id);
                      }}
                    >
                      <CloseOutlined />
                    </button>
                  </div>
                  {tab.summary && (
                    <div className="odap-task-card-summary">{tab.summary}</div>
                  )}
                  <div className="odap-task-card-meta">
                    <Badge status={tab.active ? 'processing' : 'default'} />
                    <span className="odap-task-card-time">
                      {new Date(tab.lastVisitedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              </Dropdown>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
