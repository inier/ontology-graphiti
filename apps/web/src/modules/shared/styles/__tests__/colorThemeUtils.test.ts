/**
 * 主题适配层测试（W0-1：渐变退场，改为 data 属性驱动）
 *
 * 核心断言：applyColorTheme 只写 data-accent / data-appearance，
 * 绝不写内联颜色或渐变；旧版本残留的内联变量必须被清除（否则会遮蔽 Token 层）。
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { applyColorTheme, resolveAccent, resolveAppearance } from '../colorThemeUtils';

const root = () => document.documentElement;

beforeEach(() => {
  root().removeAttribute('data-accent');
  root().removeAttribute('data-appearance');
  root().removeAttribute('style');
});

describe('resolveAccent', () => {
  it('旧色相映射到 4 个纯色强调色相，violet 退役到 indigo', () => {
    expect(resolveAccent('indigo')).toBe('indigo');
    expect(resolveAccent('blue')).toBe('cobalt');
    expect(resolveAccent('green')).toBe('teal');
    expect(resolveAccent('amber')).toBe('graphite');
    expect(resolveAccent('violet')).toBe('indigo');
  });

  it('未知/脏持久化值回落到 cobalt，而不是留空导致无强调色', () => {
    expect(resolveAccent('magenta-neon')).toBe('cobalt');
    expect(resolveAccent('')).toBe('cobalt');
  });
});

describe('resolveAppearance', () => {
  it('亮/暗对应 luminous / nebula', () => {
    expect(resolveAppearance(false)).toBe('luminous');
    expect(resolveAppearance(true)).toBe('nebula');
  });
});

describe('applyColorTheme', () => {
  it('写入 data-accent 与 data-appearance', () => {
    applyColorTheme('green', true);
    expect(root().getAttribute('data-accent')).toBe('teal');
    expect(root().getAttribute('data-appearance')).toBe('nebula');
  });

  it('不写任何内联颜色/渐变（P0-2：禁止硬编码与跨色相渐变）', () => {
    applyColorTheme('violet', false);
    const style = root().getAttribute('style') ?? '';
    expect(style).not.toContain('gradient');
    expect(style).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    expect(root().getAttribute('data-accent')).toBe('indigo');
  });

  it('清除 v1 残留的内联变量，避免遮蔽 Token 层', () => {
    root().style.setProperty('--odap-gradient-brand', 'linear-gradient(135deg,#4F46E5,#8B5CF6)');
    root().style.setProperty('--odap-color-primary-600', '#7C3AED');
    root().style.setProperty('--odap-sidebar-bg', '#1E1B4B');

    applyColorTheme('indigo', false);

    expect(root().style.getPropertyValue('--odap-gradient-brand')).toBe('');
    expect(root().style.getPropertyValue('--odap-color-primary-600')).toBe('');
    expect(root().style.getPropertyValue('--odap-sidebar-bg')).toBe('');
  });

  it('重复调用是幂等的（切换主题不会累积 style 属性）', () => {
    applyColorTheme('blue', false);
    const first = root().getAttribute('style') ?? '';
    applyColorTheme('blue', false);
    expect(root().getAttribute('style') ?? '').toBe(first);
    expect(root().getAttribute('data-accent')).toBe('cobalt');
  });
});
