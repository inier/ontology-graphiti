/**
 * Wiki 详情页测试（/wiki/:entryId）
 *
 * 覆盖：正文渲染（安全 Markdown，无 dangerouslySetInnerHTML）、
 * 右侧检查器四个面板、以及条目不存在时的 404 错误码展示。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WikiEntryPage } from '../pages/WikiEntryPage';
import { useWikiStore } from '../stores/wikiStore';
import { setMockFailure } from '../services/wikiMock';

const ENTRY_ID = '01J9Z6Q2X8K3M4N5P6R7S8T9V1';

function renderPage(entryId = ENTRY_ID) {
  return render(
    <MemoryRouter initialEntries={[`/wiki/${entryId}`]}>
      <Routes>
        <Route path="/wiki/:entryId" element={<WikiEntryPage />} />
      </Routes>
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

describe('WikiEntryPage', () => {
  it('渲染标题、owner、版本与正文段落', async () => {
    renderPage();

    const headings = await screen.findAllByRole('heading', { level: 1 });
    expect(headings.some((h) => /退货率口径说明/.test(h.textContent ?? ''))).toBe(true);
    expect(screen.getAllByText('u-arch-zhang').length).toBeGreaterThan(0);
    expect(screen.getByText(/退货率 = 统计周期内退货订单数/)).toBeInTheDocument();
    expect(screen.getByText(/部分退款按订单维度计一次/)).toBeInTheDocument();
  });

  it('正文里的指标节点以 code 渲染（安全渲染，不注入 HTML）', async () => {
    const { container } = renderPage();
    await screen.findAllByRole('heading', { level: 1 });

    const codes = Array.from(container.querySelectorAll('code')).map((el) => el.textContent);
    expect(codes).toContain('Metric:ReturnRate');
    expect(container.querySelector('[dangerouslySetInnerHTML]')).toBeNull();
  });

  it('检查器默认展示属性面板：状态 / 版本 / content_hash / source_ref', async () => {
    renderPage();
    await screen.findAllByRole('heading', { level: 1 });

    expect(screen.getByRole('tab', { name: '属性' })).toBeInTheDocument();
    expect(screen.getAllByText('已发布').length).toBeGreaterThan(0);
    expect(screen.getByText('1.4.0')).toBeInTheDocument();
    expect(screen.getByText(/docs\/04-ui\/wiki/)).toBeInTheDocument();
    expect(screen.getAllByText('Metric:ReturnRate').length).toBeGreaterThan(0);
  });

  it('版本面板给出版本时间线（含变更说明）', async () => {
    renderPage();
    await screen.findAllByRole('heading', { level: 1 });

    fireEvent.click(screen.getByRole('tab', { name: /版本 \(3\)/ }));

    expect(await screen.findByText(/补充「部分退款按订单维度计一次」的边界说明/)).toBeInTheDocument();
    expect(screen.getByText(/分母从「全部订单」改为「已签收订单」/)).toBeInTheDocument();
  });

  it('引用面板区分出边与入边', async () => {
    renderPage();
    await screen.findAllByRole('heading', { level: 1 });

    fireEvent.click(screen.getByRole('tab', { name: '引用' }));

    expect(await screen.findByText('指标 · 退货率')).toBeInTheDocument();
    expect(screen.getByText(/图谱边 · refundOf/)).toBeInTheDocument();
  });

  it('条目不存在时展示 WIKI_ENTRY_NOT_FOUND，而不是空白页', async () => {
    renderPage('01J9-NOT-EXIST');

    expect(await screen.findByText('WIKI_ENTRY_NOT_FOUND')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('详情接口故障时展示具体错误码并可重试', async () => {
    setMockFailure('detail');
    renderPage();

    expect(await screen.findByText('WIKI_ENTRY_NOT_FOUND')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument();
  });
});
