import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PageHeader, ActionButton } from './PageHeader';
import { PlusOutlined } from '@ant-design/icons';

describe('PageHeader', () => {
  it('renders without crashing with title', () => {
    render(<PageHeader title="本体管理" />);
    expect(screen.getByText('本体管理')).toBeTruthy();
  });

  it('renders with default title level h3', () => {
    const { container } = render(<PageHeader title="本体管理" />);
    const heading = container.querySelector('h3');
    expect(heading).toBeTruthy();
    expect(heading?.textContent).toBe('本体管理');
  });

  it('renders with custom title level', () => {
    const { container } = render(<PageHeader title="大标题" titleLevel={1} />);
    const heading = container.querySelector('h1');
    expect(heading).toBeTruthy();
    expect(heading?.textContent).toBe('大标题');
  });

  it('renders action buttons when provided', () => {
    render(
      <PageHeader
        title="本体管理"
        actions={<button>新建</button>}
      />
    );
    expect(screen.getByText('新建')).toBeTruthy();
  });
});

describe('ActionButton', () => {
  it('renders with icon and label', () => {
    const onClick = vi.fn();
    render(<ActionButton icon={<PlusOutlined />} label="新建" onClick={onClick} />);
    expect(screen.getByText('新建')).toBeTruthy();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<ActionButton icon={<PlusOutlined />} label="新建" onClick={onClick} />);
    fireEvent.click(screen.getByText('新建'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
