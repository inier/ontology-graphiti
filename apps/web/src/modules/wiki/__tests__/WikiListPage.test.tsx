/**
 * Wiki 列表页测试（/wiki）
 *
 * 四态全覆盖：Loading 骨架 / Populated / Empty / Error（展示 error_code）。
 * 另覆盖表-卡双视图切换与「演示数据」横幅（mock 不得静默）。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WikiListPage } from '../pages/WikiListPage';
import { useWikiStore } from '../stores/wikiStore';
import { setMockFailure } from '../services/wikiMock';
import { WIKI_API_MOCK } from '../services/wikiConfig';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/wiki']}>
      <WikiListPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useWikiStore.getState().resetAll();
  setMockFailure('none');
});

afterEach(() => {
  setMockFailure('none');
});

describe('WikiListPage', () => {
  it('首屏先出骨架，再渲染业务条目', async () => {
    const { container } = renderPage();
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();

    expect(await screen.findByText('退货率口径说明（Metric: ReturnRate）')).toBeInTheDocument();
    expect(screen.getByText('客户流失（Churn）与「客户流失率」的口径差异')).toBeInTheDocument();
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
  });

  it('mock 开启时显示「演示数据」横幅（不把假数据当真数据）', async () => {
    renderPage();
    await screen.findByText('退货率口径说明（Metric: ReturnRate）');
    if (WIKI_API_MOCK) {
      expect(screen.getByRole('status')).toHaveTextContent('演示数据');
    }
  });

  it('表头与关键列齐备', async () => {
    renderPage();
    await screen.findByText('退货率口径说明（Metric: ReturnRate）');
    for (const header of ['标题', '状态', 'owner', '版本', '最后核验', '标签']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument();
    }
  });

  it('页脚给出台数与页码（分页不是摆设）', async () => {
    const { container } = renderPage();
    await screen.findByText('退货率口径说明（Metric: ReturnRate）');
    const footer = Array.from(container.querySelectorAll('.wiki-meta')).find((el) =>
      (el.textContent ?? '').includes('共'),
    );
    expect(footer?.textContent).toMatch(/共\s*\d+\s*条/);
    expect(footer?.textContent).toMatch(/第\s*\d+\s*页/);
  });

  it('筛选无命中时显示空态，而不是空白表格或报错', async () => {
    useWikiStore.getState().setFilters({ keyword: '完全不存在口径-zzz' });
    renderPage();

    expect(await screen.findByText('还没有符合条件的 Wiki 条目')).toBeInTheDocument();
    expect(screen.getByText(/请放宽筛选条件/)).toBeInTheDocument();
  });

  it('上游超时显示具体 error_code 与后端 message，并可重试恢复', async () => {
    setMockFailure('list');
    renderPage();

    expect(await screen.findByText('WIKI_LIST_UPSTREAM_TIMEOUT')).toBeInTheDocument();
    expect(screen.getByText(/上游 SQLite 查询超时/)).toBeInTheDocument();
    expect(screen.queryByText('加载失败')).toBeNull();

    setMockFailure('none');
    fireEvent.click(screen.getByRole('button', { name: /重试/ }));
    expect(await screen.findByText('退货率口径说明（Metric: ReturnRate）')).toBeInTheDocument();
  });

  it('关键词筛选会命中真实条目（语义过滤而非前端摆设）', async () => {
    renderPage();
    await screen.findByText('退货率口径说明（Metric: ReturnRate）');

    fireEvent.change(screen.getByLabelText('按标题搜索 Wiki 条目'), { target: { value: '牛鞭效应' } });

    expect(await screen.findByText(/牛鞭效应/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('退货率口径说明（Metric: ReturnRate）')).toBeNull();
    });
  });

  it('可切换到卡片视图，卡片展示 owner 与标签', async () => {
    renderPage();
    await screen.findByText('退货率口径说明（Metric: ReturnRate）');

    fireEvent.click(screen.getByText('卡片'));

    await waitFor(() => {
      expect(screen.getAllByText('u-arch-zhang').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('指标口径').length).toBeGreaterThan(0);
  });
});
