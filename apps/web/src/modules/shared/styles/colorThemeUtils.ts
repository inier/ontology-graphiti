/**
 * 主题运行时适配层（W0-1）
 *
 * 背景：v1 在此文件用内联 `--odap-gradient-brand` 生成「跨色相紫→品红」渐变，
 * 命中团队 P0-2 红线。v2 起主题由 Token 真源驱动：
 *
 *   <html data-appearance="luminous|nebula" data-accent="cobalt|teal|indigo|graphite">
 *
 * 真源：docs/04-ui/design-tokens.css（镜像 apps/web/src/modules/shared/styles/design-tokens.css）
 * 本文件只负责把旧 store 的 `colorTheme + isDark` 翻译成上述两个 data 属性，
 * 并清理旧版本残留的内联变量（否则内联值会遮蔽 Token 层）。
 */

/** Token 真源定义的 4 个强调色相（violet/amber 已退役，见 UIUX §3.4） */
export type AccentHue = 'cobalt' | 'teal' | 'indigo' | 'graphite';

/** Token 真源定义的双外观 */
export type Appearance = 'luminous' | 'nebula';

/** 旧 store 的取值域（layoutStore.ColorTheme），保留以兼容持久化数据 */
export type LegacyColorTheme = 'indigo' | 'blue' | 'green' | 'violet' | 'amber';

/**
 * 旧色相 → 新强调色相。to 语义最接近的纯色族，不含跨色相渐变。
 * violet 已退役（P0-2 的渐变色相来源），降级映射到 indigo 纯色。
 */
const LEGACY_TO_ACCENT: Record<LegacyColorTheme, AccentHue> = {
  indigo: 'indigo',
  blue: 'cobalt',
  green: 'teal',
  violet: 'indigo',
  amber: 'graphite',
};

/** 旧实现写入的内联变量清单 —— 必须清除，避免遮蔽 Token 层 */
const LEGACY_INLINE_PROPS = [
  '--odap-gradient-brand',
  '--odap-gradient-brand-hover',
  '--odap-shadow-glow',
  '--odap-color-primary',
  '--odap-gradient-sidebar',
  '--odap-sidebar-bg',
  '--odap-sidebar-logo-bg',
  '--odap-sidebar-logo-text',
  '--odap-sidebar-logo-color',
  '--odap-sidebar-border',
  '--odap-sidebar-border-strong',
  '--odap-sidebar-text',
  '--odap-sidebar-text-hover',
];

const SHADE_KEYS = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900'];

export function resolveAccent(colorTheme: string): AccentHue {
  return LEGACY_TO_ACCENT[colorTheme as LegacyColorTheme] ?? 'cobalt';
}

export function resolveAppearance(isDark: boolean): Appearance {
  return isDark ? 'nebula' : 'luminous';
}

function clearLegacyInlineProps(root: HTMLElement): void {
  for (const prop of LEGACY_INLINE_PROPS) {
    root.style.removeProperty(prop);
  }
  for (const shade of SHADE_KEYS) {
    root.style.removeProperty(`--odap-color-primary-${shade}`);
    root.style.removeProperty(`--odap-color-accent-${shade}`);
  }
}

/**
 * 应用主题：只写 data 属性，不写任何内联颜色/渐变。
 * 颜色切换的唯一切换点是 design-tokens.css 的 semantic 层。
 */
export function applyColorTheme(colorTheme: string, isDark: boolean): void {
  const root = document.documentElement;
  clearLegacyInlineProps(root);
  root.setAttribute('data-accent', resolveAccent(colorTheme));
  root.setAttribute('data-appearance', resolveAppearance(isDark));
}
