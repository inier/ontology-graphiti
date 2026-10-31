/**
 * Generative UI Card Registry
 *
 * v2.0 演示能力：7 类内置卡片类型
 * - chart / graph / temporal / report_link / action / confirm / input
 *
 * 组件实现见 `cardComponents.tsx`，类型注册表见 `cardRegistryTable.tsx`；
 * 本文件只导出 `<CardRenderer>`，保持单组件模块以便 react-refresh 生效。
 */

import { CARD_REGISTRY } from './cardRegistryTable';
import { UnknownCard, type CardRendererProps } from './cardComponents';

export type { CardRendererProps };

/**
 * CardRenderer 入口：根据 card_type 选择对应组件
 */
export function CardRenderer(props: CardRendererProps) {
  const Comp = CARD_REGISTRY[props.metadata.card_type] || UnknownCard;
  return <Comp {...props} />;
}
