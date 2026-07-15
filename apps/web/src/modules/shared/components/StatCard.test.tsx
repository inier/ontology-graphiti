import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatCard } from './StatCard';

describe('StatCard', () => {
  it('renders without crashing with required props', () => {
    const { container } = render(<StatCard title="实体总数" value={128} />);
    expect(container).toBeTruthy();
  });

  it('displays title and value correctly', () => {
    render(<StatCard title="实体总数" value={128} />);
    expect(screen.getByText('实体总数')).toBeTruthy();
    expect(screen.getByText('128')).toBeTruthy();
  });

  it('shows positive trend with upward arrow', () => {
    render(<StatCard title="实体总数" value={128} trend={12.5} />);
    expect(screen.getByText('12.5%')).toBeTruthy();
    expect(screen.getByText('较上周')).toBeTruthy();
  });

  it('shows loading state with dash instead of value', () => {
    render(<StatCard title="实体总数" value={128} loading />);
    expect(screen.getByText('-')).toBeTruthy();
  });

  it('displays suffix when provided', () => {
    render(<StatCard title="实体总数" value={128} suffix="个" />);
    expect(screen.getByText('个')).toBeTruthy();
  });

  it('shows negative trend percentage', () => {
    render(<StatCard title="活跃用户" value={50} trend={-5.3} />);
    expect(screen.getByText('5.3%')).toBeTruthy();
  });
});
