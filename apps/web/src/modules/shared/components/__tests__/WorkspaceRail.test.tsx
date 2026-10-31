/**
 * 工作区导轨测试（F4 / AC-19）
 *
 * 断言全局导航只呈现 6 个工作区、当前工作区有 aria-current、
 * 点击一级项跳到该工作区 home（导航不是纯展示）。
 */
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { WorkspaceRail } from '../WorkspaceRail';
import { WORKSPACES } from '../../navigation/workspaces';

function LocationProbe() {
  const { pathname } = useLocation();
  return <div data-testid="pathname">{pathname}</div>;
}

function renderRail(path = '/wiki') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <WorkspaceRail />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('WorkspaceRail', () => {
  it('恰好渲染 6 个一级工作区按钮（AC-19）', () => {
    renderRail();
    expect(screen.getByRole('navigation', { name: '工作区导航' })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(WORKSPACES.length);
  });

  it.each(WORKSPACES.map((ws) => [ws.label, ws.id] as const))(
    '工作区「%s」渲染为可访问按钮',
    (label) => {
      renderRail();
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    },
  );

  it('当前路由所属工作区带 aria-current="page"，其余不带', () => {
    renderRail('/wiki');
    expect(screen.getByRole('button', { name: '知识' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '本体' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('button', { name: '语义治理' })).not.toHaveAttribute('aria-current');
  });

  it('语义治理路由高亮治理工作区（深层路由也能归属）', () => {
    renderRail('/semantic-admin/gaps/stats');
    expect(screen.getByRole('button', { name: '语义治理' })).toHaveAttribute('aria-current', 'page');
  });

  it('点击一级项跳到该工作区 home', () => {
    renderRail('/wiki');
    fireEvent.click(screen.getByRole('button', { name: '本体' }));
    expect(screen.getByTestId('pathname').textContent).toBe('/ontology/designer');
  });
});
