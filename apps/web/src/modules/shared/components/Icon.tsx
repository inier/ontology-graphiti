/**
 * Icon —— 全项目唯一图标出口（ADR-092 第 12 条）
 *
 * 这是唯一允许设置 `strokeWidth` 的文件；业务代码不得直接 `import ... from 'lucide-react'`。
 * 描边规格：stroke-width 1.5 / round cap / round join / fill:none / currentColor
 * 尺寸三档：16(inline) 20(button) 24(standalone)；16px 复杂度门禁由 minSize 兜底
 * 无障碍：默认 aria-hidden；承担语义时用 aria-label（此时自动 role="img"）
 */
import type { CSSProperties, SVGProps } from 'react';
import { ICON_ROLES, type IconRole, type IconSize } from './iconRegistry';

export type { IconRole, IconSize };

/** 描边恒定 1.5px（三档统一，拒绝等比变细，见 UIUX §5.3） */
const STROKE_WIDTH = 1.5;

export interface IconProps {
  /** 语义角色，不是图标名 —— 传未经终裁的角色在编译期即失败 */
  role: IconRole;
  /** 仅 16 | 20 | 24 */
  size?: IconSize;
  className?: string;
  /** 承担语义时提供；不提供则视为装饰图标 */
  'aria-label'?: string;
  style?: CSSProperties;
  /** 仅测试/特殊场景使用的额外 SVG 属性，不含 stroke 类属性 */
  title?: string;
}

export function Icon({ role, size = 20, className, style, title, ...rest }: IconProps) {
  const spec = ICON_ROLES[role];
  const Glyph = spec.icon;

  // 16px 复杂度门禁：复杂字形不允许硬缩到 16px，运行时兜底升级并告警
  let resolved: IconSize = size;
  if (size < spec.minSize) {
    resolved = spec.minSize;
    if (import.meta.env?.DEV) {
      console.warn(
        `[Icon] role="${role}" 的最小尺寸为 ${spec.minSize}px，收到 ${size}px 已自动升级；` +
          `请改用简化替代图标或提升尺寸（CI check:icons 会拦截）。`,
      );
    }
  }

  const ariaLabel = rest['aria-label'];
  const a11y: SVGProps<SVGSVGElement> = ariaLabel
    ? { 'aria-label': ariaLabel, role: 'img' }
    : { 'aria-hidden': true, focusable: 'false' };

  return (
    <Glyph
      width={resolved}
      height={resolved}
      strokeWidth={STROKE_WIDTH}
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
      color="currentColor"
      nonScalingStroke
      className={className}
      style={style}
      {...(title ? { 'aria-hidden': undefined } : {})}
      {...a11y}
    >
      {title ? <title>{title}</title> : null}
    </Glyph>
  );
}

export default Icon;
