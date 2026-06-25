import React, { useState, useCallback, useRef, useMemo, useEffect, useImperativeHandle } from 'react';
import {
  ProTable,
  type ProColumns,
  type ActionType,
} from '@ant-design/pro-components';
import type { OptionConfig } from '@ant-design/pro-components/es/table/components/ToolBar';
import type { ColumnsType } from 'antd/es/table';
import './AdvancedTable.css';

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

export interface AdvancedTableProps<T = Record<string, unknown>> {
  // ========== 与 antd Table 兼容的核心 props ==========
  columns?: ColumnsType<T> | ProColumns<T>[];
  dataSource?: readonly T[];
  rowKey?: string | ((record: T) => string);
  loading?: boolean;
  pagination?: false | { pageSize?: number; current?: number; total?: number; showSizeChanger?: boolean; showTotal?: (total: number) => string };
  size?: 'small' | 'middle' | 'large';
  onChange?: (pagination: unknown, filters: unknown, sorter: unknown) => void;
  rowSelection?: Record<string, unknown>;
  expandable?: Record<string, unknown>;
  footer?: (currentPageData: readonly T[]) => React.ReactNode;
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
  title?: React.ReactNode;
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

function AdvancedTableInner<T extends Record<string, unknown>>(
  props: AdvancedTableProps<T>,
  ref: React.Ref<HTMLDivElement>,
) {
  const {
    columns: rawColumns,
    dataSource,
    rowKey,
    loading,
    pagination,
    size,
    onChange,
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
    toolbarExtra,
    title,
    actionRef,
  } = props;

  const proColumns = (rawColumns || []) as ProColumns<T>[];

  // 列宽拖拽
  const { resolvedColumns } = useColumnResize(proColumns);

  // 内部 actionRef 用于调用 ProTable 的 reload 方法
  const internalActionRef = useRef<ActionType>(null);

  // 合并外部和内部 actionRef
  useImperativeHandle(actionRef, () => internalActionRef.current as ActionType);

  // ProTable options - v3 API
  // 只有当至少一个选项启用时才传入 options，否则传入 false 禁用工具栏
  const options: OptionConfig | false = (enableDensity || enableReload || enableColumnSetting || enableFullscreen)
    ? {
        density: enableDensity,
        reload: enableReload,
        setting: enableColumnSetting,
        fullScreen: enableFullscreen,
      }
    : false;

  // 工具栏渲染 - 仅在有额外内容时提供，避免覆盖默认工具栏
  const toolBarRender = toolbarExtra
    ? () => [toolbarExtra]
    : undefined;

  return (
    <div ref={ref} className="advanced-table-container">
      <ProTable<T>
        columns={enableColumnResize ? resolvedColumns : proColumns}
        dataSource={dataSource as readonly T[]}
        rowKey={rowKey as string}
        loading={loading}
        pagination={pagination}
        size={size as 'small' | 'middle' | 'large'}
        onChange={onChange}
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
        search={false}
        headerTitle={title}
        toolBarRender={toolBarRender}
        actionRef={internalActionRef}
      />
    </div>
  );
}

const AdvancedTable = React.forwardRef(AdvancedTableInner) as <
  T extends Record<string, unknown>,
>(
  props: AdvancedTableProps<T> & { ref?: React.Ref<HTMLDivElement> },
) => React.ReactElement;

export { AdvancedTable };
export default AdvancedTable;
