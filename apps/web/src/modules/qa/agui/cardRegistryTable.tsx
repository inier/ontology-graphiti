/**
 * 卡片类型 → 组件 的注册表。
 *
 * 独立于 `CardRegistry.tsx`：后者只导出 `<CardRenderer>` 组件，
 * 本文件只导出注册表与查询函数（无组件声明），两者各自满足 react-refresh 的模块边界。
 */

import React from 'react';
import type { CardType } from './agui_types';
import { InlineChart } from '../components/InlineChart';
import { TemporalCardView } from '../components/TemporalCardView';
import { ReportLinkView } from '../components/ReportLinkView';
import {
  UnknownCard,
  ActionCard,
  ConfirmCardUI,
  InputCardUI,
  type CardRendererProps,
} from './cardComponents';

/** 已注册的卡片组件表；`Record<CardType, ...>` 保证新增 CardType 时编译期报缺 */
export const CARD_REGISTRY: Record<CardType, React.FC<CardRendererProps>> = {
  chart: InlineChart as unknown as React.FC<CardRendererProps>,
  graph: UnknownCard, // G6 图谱组件占位
  temporal: TemporalCardView as unknown as React.FC<CardRendererProps>,
  report_link: ReportLinkView as unknown as React.FC<CardRendererProps>,
  action: ActionCard,
  confirm: ConfirmCardUI,
  input: InputCardUI,
};

/** 列出所有已注册的卡片类型 */
export function getRegisteredCardTypes(): CardType[] {
  return Object.keys(CARD_REGISTRY) as CardType[];
}
