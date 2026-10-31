/**
 * Wiki 表格视图测试
 *
 * 用确定性夹具（相对当前时间构造）覆盖：STALE 判定、无标签、超长标题、
 * 以及点击标题回调（不是死链接）。
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { WikiTable } from '../components/WikiTable';
import type { WikiEntry } from '../services/wikiTypes';

const DAY = 86_400_000;

function entry(overrides: Partial<WikiEntry>): WikiEntry {
  return {
    id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
    title: '退货率口径说明（Metric: ReturnRate）',
    status: 'published',
    owner_id: 'u-arch-zhang',
    version: '1.4.0',
    source_ref: 'docs/04-ui/wiki/01J9.md',
    superseded_by: null,
    content_hash: 'a'.repeat(64),
    last_verified: new Date(Date.now() - 10 * DAY).toISOString(),
    tags: ['指标口径'],
    concept_refs: ['Metric:ReturnRate'],
    workspace_id: 'ws-odap-main',
    created_at: new Date(Date.now() - 100 * DAY).toISOString(),
    updated_at: new Date(Date.now() - 10 * DAY).toISOString(),
    ...overrides,
  };
}

describe('WikiTable', () => {
  it('超过 180 天未核验的条目标 STALE，未超过的不标', () => {
    render(
      <WikiTable
        entries={[
          entry({ id: 'stale-1', title: 'SHACL 形状约束落库与写路径校验不变量', last_verified: new Date(Date.now() - 220 * DAY).toISOString() }),
          entry({ id: 'fresh-1', title: '退货率口径说明（Metric: ReturnRate）' }),
        ]}
        onOpen={() => {}}
      />,
    );

    const staleCells = screen.getAllByText(/STALE/);
    expect(staleCells).toHaveLength(1);
    expect(staleCells[0].closest('tr')?.textContent).toContain('SHACL');
  });

  it('无标签条目显示「无标签」，不渲染空 Tag 占位', () => {
    render(<WikiTable entries={[entry({ tags: [] })]} onOpen={() => {}} />);
    expect(screen.getByText('无标签')).toBeInTheDocument();
  });

  it('标签超过 3 个时折叠为 +N', () => {
    render(
      <WikiTable
        entries={[entry({ tags: ['指标口径', '本体', '术语表', '供应链', '验收'] })]}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('点击标题触发 onOpen 并携带条目 id（不真跳转）', () => {
    const onOpen = vi.fn();
    render(<WikiTable entries={[entry({ id: 'entry-42' })]} onOpen={onOpen} />);

    const link = screen.getByRole('link', { name: /退货率口径说明/ });
    fireEvent.click(link);
    expect(onOpen).toHaveBeenCalledWith('entry-42');
  });

  it('空数组时表格渲染空数据占位而不是崩溃', () => {
    const { container } = render(<WikiTable entries={[]} onOpen={() => {}} />);
    expect(container.querySelector('.ant-table')).not.toBeNull();
    expect(container.querySelector('.ant-empty')).not.toBeNull();
  });
});
