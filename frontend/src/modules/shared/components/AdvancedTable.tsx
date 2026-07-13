import React, { useState, useCallback, useRef, useMemo, useEffect, useImperativeHandle } from 'react';
import {
  ProTable,
  type ProColumns,
  type ActionType,
} from '@ant-design/pro-components';
import type { OptionConfig } from '@ant-design/pro-components/es/table/components/ToolBar';
import type { ColumnsType } from 'antd/es/table';
import { Dropdown, App } from 'antd';
import type { MenuProps } from 'antd';
import {
  ReloadOutlined,
  ColumnHeightOutlined,
  SettingOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
} from '@ant-design/icons';
import './AdvancedTable.css';

/**
 * 工具函数：将简单的数据获取函数包装为 ProTable request 格式。
 * 各页面只需传入返回 T[] 的异步函数，即可让 ProTable 接管 loading + 刷新。
 */
function wrapRequest<T>(
  fetcher: () => Promise<T[]>,
): (params: { current?: number; pageSize?: number }, sort: unknown, filter: unknown) => Promise<{ data: T[]; success: boolean; total: number }> {
  return async () => {
    try {
      const data = await fetcher();
      return { data, success: true, total: data.length };
    } catch (error) {
      console.error('[AdvancedTable] request error:', error);
      return { data: [], success: false, total: 0 };
    }
  };
}

/**
 * AdvancedTable — 基于 ProTable 的封装，兼容原有 antd Table API。
 *
 * 内部使用 @ant-design/pro-components v3 的 ProTable（antd v6 适配），
 * 自动提供密度切换、列设置、全屏、刷新、列宽拖拽等内置功能。
 *
 * 支持两种数据模式：
 * - 静态模式：传入 dataSource（与 antd Table 一致）
 * - 请求模式：传入 request（ProTable 接管 loading + 分页）
 */

// ---- types ----------------------------------------------------------------

export interface AdvancedTableProps<T extends object = object> {
  // ========== 与 antd Table 兼容的核心 props ==========
  columns?: ColumnsType<T> | ProColumns<T>[];
  dataSource?: readonly T[];
  rowKey?: string | ((record: T, index: number) => string);
  loading?: boolean;
  pagination?: false | {
    pageSize?: number;
    current?: number;
    total?: number;
    showSizeChanger?: boolean;
    showTotal?: (total: number) => string;
    showQuickJump?: boolean;
    onChange?: (page: number, pageSize: number) => void;
  };
  size?: 'small' | 'middle' | 'large';
  onChange?: (pagination: unknown, filters: unknown, sorter: unknown) => void;
  onRow?: (record: T, index?: number) => Record<string, unknown>;
  rowSelection?: Record<string, unknown>;
  expandable?: Record<string, unknown>;
  footer?: React.ReactNode | ((currentPageData: readonly T[]) => React.ReactNode);
  summary?: (currentData: readonly T[]) => React.ReactNode;
  sticky?: boolean;
  scroll?: { x?: number | string; y?: number | string };
  rowClassName?: (record: T, index: number) => string;
  showHeader?: boolean;
  locale?: Record<string, unknown>;

  // ========== ProTable 请求模式 ==========
  request?: (params: { current?: number; pageSize?: number }, sort: unknown, filter: unknown) => Promise<{
    data: T[];
    success: boolean;
    total?: number;
  }>;

  // ========== 增强功能 ==========
  /** 列宽拖拽，默认 true */
  enableColumnResize?: boolean;
  /** 密度切换，默认 true */
  enableDensity?: boolean;
  /** 列设置，默认 true */
  enableColumnSetting?: boolean;
  /** 全屏切换，默认 true */
  enableFullscreen?: boolean;
  /** 刷新按钮，默认 true */
  enableReload?: boolean;
  onReload?: () => void;
  toolbarExtra?: React.ReactNode;
  title?: React.ReactNode | (() => React.ReactNode);
  actionRef?: React.Ref<ActionType>;
  /** 自定义表格尺寸（优先级高于密度） */
  densitySize?: 'small' | 'middle' | 'large';
}

// ---- column resize --------------------------------------------------------

const COL_MIN_WIDTH = 60;

/**
 * 列宽拖拽 hook
 *
 * 策略：不在 columns 的 title 上做文章（会干扰排序/筛选），
 * 而是直接修改每个 column 的 title，内嵌一个可拖拽的 resize handle。
 */
function useColumnResize<T>(columns: ProColumns<T>[]) {
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const dragging = useRef<{ colKey: string; startX: number; startWidth: number } | null>(null);
  // 缓存列 keys（只在 columns 结构变化时重算）
  const stableKeys = useMemo(
    () => columns.map((c, i) => String(c.key ?? c.dataIndex ?? `col-${i}`)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columns.map(c => c.key ?? c.dataIndex).join(',')],
  );

  // 从 columns 的 width 属性初始化
  useEffect(() => {
    const initial: Record<string, number> = {};
    columns.forEach((col, i) => {
      const key = stableKeys[i];
      if (col.width !== undefined && col.width !== null) {
        initial[key] = Number(col.width);
      }
    });
    setColumnWidths(prev => {
      const merged = { ...prev, ...initial };
      return JSON.stringify(merged) === JSON.stringify(prev) ? prev : merged;
    });
  }, [columns, stableKeys]);

  const handleResizeStart = useCallback(
    (colKey: string, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.clientX;
      const startWidth = columnWidths[colKey] ?? 120;
      dragging.current = { colKey, startX, startWidth };

      const onMouseMove = (ev: MouseEvent) => {
        if (!dragging.current) return;
        const delta = ev.clientX - dragging.current.startX;
        const newWidth = Math.max(COL_MIN_WIDTH, dragging.current.startWidth + delta);
        const key = dragging.current.colKey;
        setColumnWidths(prev => ({ ...prev, [key]: newWidth }));
      };

      const onMouseUp = () => {
        dragging.current = null;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [columnWidths],
  );

  /** 注入列宽 + resize handle 后的 columns */
  const resolvedColumns = useMemo<ProColumns<T>[]>(() => {
    return columns.map((col, i) => {
      const key = stableKeys[i];
      const currentWidth = columnWidths[key] ?? col.width;
      const colWidth = currentWidth !== undefined ? Number(currentWidth) : undefined;

      // 把 resize handle 嵌入 title
      const originalTitle = col.title as React.ReactNode;
      const resizableTitle = (
        <ResizeTitleWrapper
          colKey={key}
          onResizeStart={handleResizeStart}
        >
          {originalTitle}
        </ResizeTitleWrapper>
      );

      return {
        ...col,
        width: colWidth,
        title: resizableTitle,
      } as ProColumns<T>;
    });
  }, [columns, columnWidths, stableKeys, handleResizeStart]);

  return { resolvedColumns };
}

/** 内嵌 resize handle 的列头包装组件（React.memo 避免不必要的重渲染） */
const ResizeTitleWrapper = React.memo(function ResizeTitleWrapper({
  colKey,
  children,
  onResizeStart,
}: {
  colKey: string;
  children: React.ReactNode;
  onResizeStart: (colKey: string, e: React.MouseEvent) => void;
}) {
  return (
    <span className="react-resizable" style={{ display: 'inline-flex', alignItems: 'center', width: '100%', minWidth: 0, position: 'relative' }}>
      <span
        style={{
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          minWidth: 0,
        }}
      >
        {children ?? colKey}
      </span>
      <span
        className="react-resizable-handle"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onResizeStart(colKey, e);
        }}
      />
    </span>
  );
});

// ---- component ------------------------------------------------------------

function AdvancedTableInner<T extends object>(
  props: AdvancedTableProps<T>,
  ref: React.Ref<HTMLDivElement>,
) {
  const {
    columns: rawColumns,
    dataSource,
    rowKey,
    loading,
    pagination,
    size: externalSize,
    onChange,
    onRow,
    rowSelection,
    expandable,
    footer,
    summary,
    sticky,
    scroll,
    rowClassName,
    showHeader,
    locale,
    request,
    enableColumnResize = true,
    enableDensity = true,
    enableColumnSetting = true,
    enableFullscreen = true,
    enableReload = true,
    onReload,
    toolbarExtra,
    title,
    actionRef,
    densitySize,
  } = props;

  const { message } = App.useApp?.() ?? { message: null };

  const proColumns = (rawColumns || []) as ProColumns<T>[];

  // 列宽拖拽
  const { resolvedColumns } = useColumnResize(proColumns);

  // 内部 actionRef 用于调用 ProTable 的 reload 方法
  const internalActionRef = useRef<ActionType>(null);

  // 合并外部和内部 actionRef
  useImperativeHandle(actionRef, () => internalActionRef.current as ActionType);

  // 容器 ref，用于全屏
  const containerRef = useRef<HTMLDivElement>(null);

  // 合并外层 ref 和内部 containerRef
  useEffect(() => {
    if (!ref) return;
    if (typeof ref === 'function') {
      ref(containerRef.current);
    } else {
      (ref as React.MutableRefObject<HTMLDivElement | null>).current = containerRef.current;
    }
  }, [ref]);

  // 全屏状态管理
  const [isFullscreen, setIsFullscreen] = useState(false);

  // 监听浏览器全屏变化，同步状态
  useEffect(() => {
    const onFsChange = () => {
      const fsEl = document.fullscreenElement;
      const container = containerRef.current;
      if (fsEl && container && fsEl === container) {
        setIsFullscreen(true);
      } else if (!fsEl) {
        setIsFullscreen(false);
      }
    };
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  // 密度状态管理（内部管理，避免外部 size 覆盖）
  const [internalDensity, setInternalDensity] = useState<'small' | 'middle' | 'large'>(
    densitySize ?? externalSize ?? 'middle'
  );

  // 当 densitySize 或 externalSize 变化时同步内部密度
  useEffect(() => {
    const newSize = densitySize ?? externalSize;
    if (newSize) {
      setInternalDensity(newSize);
    }
  }, [densitySize, externalSize]);

  // ===== 自定义 reload =====
  const handleReload = useCallback(async () => {
    // 优先调用外部回调
    if (onReload) {
      try {
        await Promise.resolve(onReload());
      } catch (err) {
        console.error('[AdvancedTable] reload error:', err);
        message?.error?.('刷新失败');
      }
    }
    // request 模式：通过 actionRef 触发 ProTable 内置 reload
    if (request && internalActionRef.current?.reload) {
      internalActionRef.current.reload();
    }
    // onReload 回调
    if (!request && onReload) {
      try {
        await Promise.resolve(onReload());
      } catch (err) {
        console.error('[AdvancedTable] reload error:', err);
        message?.error?.('刷新失败');
      }
    }
  }, [onReload, request, message]);

  // ===== 自定义全屏切换 =====
  const handleFullscreen = useCallback(async () => {
    const container = containerRef.current;
    if (!container) return;

    const isFs = !!document.fullscreenElement;
    try {
      if (!isFs) {
        // 进入全屏：优先使用原生 Fullscreen API
        if (container.requestFullscreen) {
          await container.requestFullscreen();
        } else {
          setIsFullscreen(true);
        }
      } else {
        // 退出全屏
        if (document.fullscreenElement === container && document.exitFullscreen) {
          await document.exitFullscreen();
        } else {
          setIsFullscreen(false);
        }
      }
    } catch (err) {
      // Fullscreen API 被拒绝（如非用户手势触发、iframe 限制等），降级到 CSS 全屏
      setIsFullscreen(prev => !prev);
    }
  }, []);

  // ===== 密度切换菜单 =====
  const densityMenuItems: MenuProps['items'] = [
    { key: 'large', label: '宽松' , icon: <ColumnHeightOutlined /> },
    { key: 'middle', label: '中等' },
    { key: 'small', label: '紧凑' },
  ];

  // ===== 辅助：在 ReactNode 数组中找到 setting 按钮 =====
  const findSettingButton = useCallback(
    (nodes: React.ReactNode[] | undefined): React.ReactNode | null => {
      if (!Array.isArray(nodes)) return null;
      for (const node of nodes) {
        if (!React.isValidElement(node)) continue;
        const el = node as React.ReactElement<any>;
        // 直接匹配 key
        if ((el as any).key === 'setting' || el.props?.key === 'setting') return node;
        // 匹配子元素中的 Setting 图标 / aria-label
        const children = el.props?.children;
        if (el.props?.['aria-label'] === 'setting') return node;
        if (Array.isArray(children)) {
          const nested = findSettingButton(children as React.ReactNode[]);
          if (nested) return node;
        } else if (React.isValidElement(children)) {
          const child = children as React.ReactElement<any>;
          if (
            child.props?.['aria-label'] === 'setting' ||
            child.type === SettingOutlined ||
            (child.type as any)?.displayName?.includes?.('Setting') ||
            (child.type as any)?.name?.includes?.('Setting')
          ) {
            return node;
          }
        }
        // 简单的 className 匹配：anticon-setting
        const childHtml = (children as any)?.props?.className ?? '';
        if (typeof childHtml === 'string' && childHtml.includes('setting')) return node;
      }
      return null;
    },
    []
  );

  // ===== 构造自定义 optionsRender：完全接管工具栏按钮，确保各功能生效 =====
  // ProTable v3 ToolBar 签名：optionsRender(toolbarProps, defaultDom: ReactNode[])
  // 第 1 个参数：ToolBar props 对象
  // 第 2 个参数：defaultDom（默认按钮数组，只有 setting=true 时会包含 setting 按钮）
  const optionsRender = (_toolbarProps: unknown, defaultDom: React.ReactNode[]) => {
    const actions: React.ReactNode[] = [];
    const defaultActions = defaultDom ?? [];

    // 刷新按钮
    if (enableReload) {
      actions.push(
        <span
          key="reload"
          className="ant-pro-table-list-toolbar-setting-item advanced-table-toolbar-btn"
          onClick={handleReload}
          title="刷新"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleReload(); }}
        >
          <ReloadOutlined className="anticon" aria-label="reload" />
        </span>
      );
    }

    // 密度切换按钮
    if (enableDensity) {
      const DensityLabel =
        internalDensity === 'large' ? '宽松' :
        internalDensity === 'small' ? '紧凑' : '中等';
      actions.push(
        <Dropdown
          key="density"
          trigger={['click']}
          menu={{
            items: densityMenuItems,
            selectedKeys: [internalDensity],
            onClick: ({ key }) => {
              const newDensity = key as 'small' | 'middle' | 'large';
              setInternalDensity(newDensity);
            },
          }}
        >
          <span
            className="ant-pro-table-list-toolbar-setting-item advanced-table-toolbar-btn"
            title={`密度：${DensityLabel}`}
            role="button"
            tabIndex={0}
          >
            <ColumnHeightOutlined className="anticon" aria-label="density" />
          </span>
        </Dropdown>
      );
    }

    // 列设置（使用 ProTable 默认列设置按钮，即 defaultActions 中的 setting 按钮）
    if (enableColumnSetting) {
      const settingBtn = findSettingButton(defaultActions);
      if (settingBtn) {
        actions.push(
          <span key="setting-wrapper" className="ant-pro-table-list-toolbar-setting-item">
            {settingBtn}
          </span>
        );
      } else {
        // fallback：找不到默认 setting 时，借助 options.setting=true 由 ProTable 在 defaultActions 中生成的其他节点
        // 遍历 defaultActions 找到看起来不像 density/reload/fullScreen 的元素直接加入
        defaultActions.forEach((act, i) => {
          // 只有 setting=true 时，defaultActions 中应该有且仅有 1 个元素（setting 按钮）
          actions.push(
            <span
              key={`setting-fb-${i}`}
              className="ant-pro-table-list-toolbar-setting-item"
            >
              {act}
            </span>
          );
        });
      }
    }

    // 全屏按钮
    if (enableFullscreen) {
      actions.push(
        <span
          key="fullscreen"
          className="ant-pro-table-list-toolbar-setting-item advanced-table-toolbar-btn"
          onClick={handleFullscreen}
          title={isFullscreen ? '退出全屏' : '全屏'}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleFullscreen(); }}
        >
          {isFullscreen ? (
            <FullscreenExitOutlined className="anticon" aria-label="fullscreen-exit" />
          ) : (
            <FullscreenOutlined className="anticon" aria-label="fullscreen" />
          )}
        </span>
      );
    }

    return actions;
  };

  // ProTable options 对象：
  // - density: false（我们自己实现密度按钮和控制 size，避免内部覆盖）
  // - reload: false（自己实现）
  // - setting: enableColumnSetting（保留 ProTable 内置列设置，defaultDom 中会包含 setting 按钮）
  // - fullScreen: false（自己实现）
  const options: OptionConfig | false =
    enableDensity || enableReload || enableColumnSetting || enableFullscreen
      ? {
          density: false,
          reload: false,
          setting: enableColumnSetting,
          fullScreen: false,
        }
      : false;

  // optionsRender：作为 ProTable 的顶层 prop（不是 options 嵌套）。自定义顺序：刷新/密度/设置/全屏
  const optionsRenderProp:
    | ((_props: unknown, defaultDom: React.ReactNode[]) => React.ReactNode[])
    | undefined = options !== false ? optionsRender : undefined;

  // 工具栏渲染 - 仅在有额外内容时提供，避免覆盖默认工具栏
  const toolBarRender = toolbarExtra
    ? () => [toolbarExtra]
    : undefined;

  // 如果 title 是函数，执行它得到 ReactNode
  const resolvedTitle: React.ReactNode =
    typeof title === 'function' ? title() : title;

  // 默认大小：用内部管理的密度
  const tableSize = internalDensity;

  // 计算容器 CSS 类
  // 注意：必须显式检查 document.fullscreenElement 不为 null，避免初始化时 null === null 返回 true
  const fullscreenByApi =
    typeof document !== 'undefined' &&
    !!document.fullscreenElement &&
    document.fullscreenElement === containerRef.current;
  const containerClass = [
    'advanced-table-container',
    `advanced-table-density-${tableSize}`,
    isFullscreen || fullscreenByApi ? 'advanced-table-fullscreen' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div ref={containerRef} className={containerClass}>
      <ProTable<T>
        columns={enableColumnResize ? resolvedColumns : proColumns}
        dataSource={dataSource as readonly T[]}
        rowKey={rowKey as string}
        loading={loading}
        pagination={pagination}
        size={tableSize}
        defaultSize={tableSize}
        onChange={onChange}
        onRow={onRow as any}
        rowSelection={rowSelection as never}
        expandable={expandable as never}
        footer={footer}
        summary={summary}
        sticky={sticky}
        scroll={scroll}
        rowClassName={rowClassName}
        showHeader={showHeader}
        locale={locale}
        request={request}
        options={options}
        optionsRender={optionsRenderProp as any}
        search={false}
        headerTitle={resolvedTitle}
        toolBarRender={toolBarRender}
        actionRef={internalActionRef}
      />
    </div>
  );
}

const AdvancedTable = React.forwardRef(AdvancedTableInner) as <
  T extends object = object,
>(
  props: AdvancedTableProps<T> & { ref?: React.Ref<HTMLDivElement> },
) => React.ReactElement;

export { AdvancedTable, wrapRequest };
export default AdvancedTable;
