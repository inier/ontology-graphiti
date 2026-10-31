/**
 * Wiki 去重合并页测试（/wiki/dedupe）
 *
 * 覆盖：候选列表、左右对照、合并成功提示、版本冲突错误码展示，
 * 以及「合并只置 superseded」的文案语义（不得出现"已删除"）。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WikiDedupePage } from '../pages/WikiDedupePage';
import { useWikiStore } from '../stores/wikiStore';
import { setMockFailure } from '../services/wikiMock';
import { MOCK_ENTRIES } from '../services/wikiMock';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/wiki/dedupe']}>
      <WikiDedupePage />
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

describe('WikiDedupePage', () => {
  it('渲染候选列表并默认选中第一组，左右两侧都展示条目', async () => {
    renderPage();

    expect(await screen.findByText(/候选（2）/)).toBeInTheDocument();
    expect(screen.getByLabelText('左侧条目')).toBeInTheDocument();
    expect(screen.getByLabelText('右侧条目')).toBeInTheDocument();
    expect(screen.getByText(/相似度/)).toBeInTheDocument();
    expect(screen.getByText(/content_hash 前缀相同/)).toBeInTheDocument();
  });

  it('冲突字段以警告图标 + 文本标注，不依赖颜色单独传达', async () => {
    renderPage();
    await screen.findByText(/候选（2）/);

    const conflicts = screen.getAllByText('冲突字段');
    expect(conflicts.length).toBeGreaterThan(0);
    // 左右两侧各出现一次冲突字段名（每个候选重复标注，不合并同类项）
    expect(screen.getAllByText('version').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('status').length).toBeGreaterThanOrEqual(2);
  });

  it('点击另一组候选会切换对照内容', async () => {
    renderPage();
    await screen.findByText(/候选（2）/);

    fireEvent.click(screen.getByText(/牛鞭效应/));

    await waitFor(() => {
      expect(screen.getByText(/标签重合 1 项/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/content_hash 前缀相同/)).toBeNull();
  });

  it('合并成功后提示「置为 superseded（未物理删除）」', async () => {
    renderPage();
    await screen.findByText(/候选（2）/);

    fireEvent.click(screen.getByRole('button', { name: /确认合并（保留左侧）/ }));

    expect(await screen.findByText(/置为 superseded（未物理删除）/)).toBeInTheDocument();
    expect(screen.queryByText(/已删除/)).toBeNull();
  });

  it('合并冲突时展示 WIKI_VERSION_CONFLICT 与冲突条目 id', async () => {
    renderPage();
    await screen.findByText(/候选（2）/);

    setMockFailure('merge');
    fireEvent.click(screen.getByRole('button', { name: /确认合并（保留左侧）/ }));

    expect(await screen.findByText('WIKI_VERSION_CONFLICT')).toBeInTheDocument();
    expect(screen.getByText(/discard 侧已被他人更新/)).toBeInTheDocument();
    expect(screen.queryByText(/置为 superseded（未物理删除）/)).toBeNull();
  });

  it('去重索引缺失时展示后端给出的可执行指引，而不是空列表', async () => {
    setMockFailure('dedupe');
    renderPage();

    expect(await screen.findByText('DOCS_DEDUPE_INDEX_MISSING')).toBeInTheDocument();
    expect(screen.getByText(/去重索引未建立/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument();
  });

  it('候选列表是真实条目 id（点击可定位到具体条目）', async () => {
    renderPage();
    await screen.findByText(/候选（2）/);

    const known = MOCK_ENTRIES.find((e) => e.id === '01J9Z6Q2X8K3M4N5P6R7S8T9V1');
    expect(known).toBeTruthy();
    expect(screen.getAllByText(known!.id).length).toBeGreaterThan(0);
  });
});
