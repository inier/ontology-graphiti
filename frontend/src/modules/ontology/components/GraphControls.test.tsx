import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { GraphControls } from './GraphControls';

const defaultProps = {
  zoomLevel: 1.0,
  minimapOpen: false,
  onCenterView: vi.fn(),
  onZoomIn: vi.fn(),
  onZoomOut: vi.fn(),
  onZoomReset: vi.fn(),
  onToggleMinimap: vi.fn(),
};

describe('GraphControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    const { container } = render(<GraphControls {...defaultProps} />);
    expect(container).toBeTruthy();
  });

  it('displays zoom level as percentage', () => {
    render(<GraphControls {...defaultProps} zoomLevel={1.5} />);
    expect(screen.getByText('150%')).toBeTruthy();
  });

  it('calls onZoomIn when zoom in button is clicked', () => {
    const onZoomIn = vi.fn();
    render(<GraphControls {...defaultProps} onZoomIn={onZoomIn} />);
    const zoomInBtn = screen.getByRole('img', { name: /zoom-in/i }).closest('button');
    if (zoomInBtn) {
      fireEvent.click(zoomInBtn);
      expect(onZoomIn).toHaveBeenCalledTimes(1);
    }
  });

  it('calls onCenterView when center button is clicked', () => {
    const onCenterView = vi.fn();
    render(<GraphControls {...defaultProps} onCenterView={onCenterView} />);
    const centerBtn = screen.getByRole('img', { name: /aim/i }).closest('button');
    if (centerBtn) {
      fireEvent.click(centerBtn);
      expect(onCenterView).toHaveBeenCalledTimes(1);
    }
  });

  it('calls onZoomReset when zoom percentage is clicked', () => {
    const onZoomReset = vi.fn();
    render(<GraphControls {...defaultProps} zoomLevel={1.5} onZoomReset={onZoomReset} />);
    fireEvent.click(screen.getByText('150%'));
    expect(onZoomReset).toHaveBeenCalledTimes(1);
  });

  it('calls onToggleMinimap when minimap button is clicked', () => {
    const onToggleMinimap = vi.fn();
    render(<GraphControls {...defaultProps} onToggleMinimap={onToggleMinimap} />);
    const expandBtn = screen.getByRole('img', { name: /expand/i }).closest('button');
    if (expandBtn) {
      fireEvent.click(expandBtn);
      expect(onToggleMinimap).toHaveBeenCalledTimes(1);
    }
  });
});
