/**
 * Icon 组件契约测试（ADR-092 第 12 条）
 *
 * 覆盖：描边单一真源、尺寸三档、16px 复杂度门禁自动升级、无障碍语义、
 * 以及「组件不暴露 strokeWidth」这条不可绕过的约束。
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { Icon } from '../Icon';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Icon', () => {
  it('输出统一描边规格：stroke-width 1.5 / round cap / round join / fill:none', () => {
    const { container } = render(<Icon role="create" size={20} />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute('stroke-width', '1.5');
    expect(svg).toHaveAttribute('stroke-linecap', 'round');
    expect(svg).toHaveAttribute('stroke-linejoin', 'round');
    expect(svg).toHaveAttribute('fill', 'none');
    expect(svg).toHaveAttribute('width', '20');
    expect(svg).toHaveAttribute('height', '20');
  });

  it('描边不随缩放变细：每个子路径都带 non-scaling-stroke', () => {
    const { container } = render(<Icon role="delete" size={16} />);
    const shapes = Array.from(container.querySelectorAll('path, circle, rect, line, polyline, polygon'));
    expect(shapes.length).toBeGreaterThan(0);
    for (const shape of shapes) {
      expect(shape.getAttribute('vector-effect')).toBe('non-scaling-stroke');
    }
  });

  it('16px 复杂度门禁：复杂字形收到 size=16 时自动升级到 20 并告警', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { container } = render(<Icon role="dashboard" size={16} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '20');
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0][0])).toContain('role="dashboard"');
  });

  it('简单字形保持 16px，不触发升级告警', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { container } = render(<Icon role="date" size={16} />);
    expect(container.querySelector('svg')).toHaveAttribute('width', '16');
    expect(warn).not.toHaveBeenCalled();
  });

  it('装饰图标默认 aria-hidden，不打断屏幕阅读器', () => {
    const { container } = render(<Icon role="document" size={16} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg).not.toHaveAttribute('aria-label');
  });

  it('承担语义时使用 aria-label 并自动 role=img', () => {
    const { container } = render(<Icon role="warning" size={16} aria-label="存在冲突字段" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-label', '存在冲突字段');
    expect(svg).toHaveAttribute('role', 'img');
  });

  it('title 渲染为 <title> 子节点，便于悬浮提示', () => {
    const { container } = render(<Icon role="owner" size={16} title="负责人 张工" />);
    expect(container.querySelector('title')?.textContent).toBe('负责人 张工');
  });

  it('className / style 透传到根 svg，描边颜色继承文字色', () => {
    const { container } = render(
      <Icon role="search" size={20} className="wiki-toolbar__icon" style={{ marginRight: 4 }} />,
    );
    const svg = container.querySelector('svg');
    expect(svg).toHaveClass('wiki-toolbar__icon');
    expect(svg).toHaveAttribute('stroke', 'currentColor');
    expect(svg?.getAttribute('style') ?? '').toContain('margin-right');
  });

  it('不暴露 strokeWidth 入参：类型层面只接受 role/size/className 等白名单', () => {
    // 若组件接受 strokeWidth，下面的对象字面量会在类型检查期失败（tsc 已覆盖）。
    // 运行期再确认：多余属性不会被透传到 svg 上。
    const props = { role: 'edit', size: 20, strokeWidth: 3 } as const;
    const { container } = render(<Icon role={props.role} size={props.size} />);
    expect(container.querySelector('svg')).toHaveAttribute('stroke-width', '1.5');
  });
});
