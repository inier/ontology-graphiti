/**
 * 证据计数三态：不可得 / 真的是 0 / 出处层缺失（AC-13）
 * 三者措辞必须不同 —— 「未知」和「0 条」是两个结论，混用会让用户据此做错判断。
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EvidenceCount } from './EvidenceCount';

describe('EvidenceCount', () => {
  it('字段缺失 → 「证据数未知」，**不是** 0 条', () => {
    render(<EvidenceCount entityCount={undefined} episodeCount={undefined} />);
    expect(screen.getByText('证据数未知')).toBeTruthy();
    expect(screen.queryByText(/实体 0/)).toBeNull();
  });

  it('entityCount 为 0 → 「该决策未关联证据实体」（这是一个真实结论）', () => {
    render(<EvidenceCount entityCount={0} episodeCount={0} />);
    expect(screen.getByText('该决策未关联证据实体')).toBeTruthy();
  });

  it('实体有数、出处缺失 → 显式提示，不只是一个 Tooltip', () => {
    render(<EvidenceCount entityCount={4} episodeCount={0} variant="detailed" />);
    expect(screen.getByText('实体 4')).toBeTruthy();
    expect(screen.getByText(/证据出处层不完整/)).toBeTruthy();
  });

  it('实体有数、出处本身不可得 → 「出处未知」，不冒充 0', () => {
    render(<EvidenceCount entityCount={4} episodeCount={undefined} />);
    expect(screen.getByText('实体 4')).toBeTruthy();
    expect(screen.getByText('+ 出处未知')).toBeTruthy();
  });

  it('两层都有数 → 正常显示「实体 N + 出处 M」', () => {
    render(<EvidenceCount entityCount={4} episodeCount={7} />);
    expect(screen.getByText('实体 4')).toBeTruthy();
    expect(screen.getByText('+ 出处 7')).toBeTruthy();
  });
});
