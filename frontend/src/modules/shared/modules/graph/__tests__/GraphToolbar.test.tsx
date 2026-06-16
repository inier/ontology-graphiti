import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { GraphToolbar } from '../components/GraphToolbar';

const defaultProps = {
  onRefresh: vi.fn(),
  layout: 'force' as const,
  onLayoutChange: vi.fn(),
  searchText: '',
  onSearchChange: vi.fn(),
  filterType: 'all',
  onFilterChange: vi.fn(),
  entityTypes: ['Location', 'MilitaryUnit', 'WeaponSystem'],
  showAudit: false,
  onShowAuditChange: vi.fn(),
};

describe('GraphToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    const { container } = render(<GraphToolbar {...defaultProps} />);
    expect(container).toBeTruthy();
  });

  it('displays search input with correct value', () => {
    render(<GraphToolbar {...defaultProps} searchText="测试搜索" />);
    const searchInput = screen.getByDisplayValue('测试搜索');
    expect(searchInput).toBeTruthy();
  });

  it('calls onSearchChange when typing in search input', () => {
    const onSearchChange = vi.fn();
    render(<GraphToolbar {...defaultProps} onSearchChange={onSearchChange} />);
    const searchInput = screen.getByPlaceholderText('搜索实体');
    fireEvent.change(searchInput, { target: { value: '新搜索' } });
    expect(onSearchChange).toHaveBeenCalledWith('新搜索');
  });

  it('calls onRefresh when refresh button is clicked', () => {
    const onRefresh = vi.fn();
    render(<GraphToolbar {...defaultProps} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByText('刷新'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('displays filter button with default label when filterType is all', () => {
    render(<GraphToolbar {...defaultProps} filterType="all" />);
    expect(screen.getByText('筛选')).toBeTruthy();
  });

  it('displays filter type label when a specific type is selected', () => {
    render(<GraphToolbar {...defaultProps} filterType="MilitaryUnit" />);
    expect(screen.getByText('类型: MilitaryUnit')).toBeTruthy();
  });

  it('renders audit switch with correct state', () => {
    render(<GraphToolbar {...defaultProps} showAudit={true} />);
    const auditText = screen.getByText('审计');
    expect(auditText).toBeTruthy();
  });
});
