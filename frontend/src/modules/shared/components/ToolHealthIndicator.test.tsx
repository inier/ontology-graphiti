import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ToolHealthIndicator } from './ToolHealthIndicator';

const healthyHealth = {
  status: 'healthy' as const,
  success_rate: 98.5,
  avg_duration_ms: 120,
};

const degradedHealth = {
  status: 'degraded' as const,
  success_rate: 75.0,
  avg_duration_ms: 450,
  error_count: 3,
};

const unhealthyHealth = {
  status: 'unhealthy' as const,
  success_rate: 45.2,
  avg_duration_ms: 1200,
  error_count: 15,
  last_error: 'Connection timeout after 30s',
};

describe('ToolHealthIndicator', () => {
  it('renders without crashing with healthy status', () => {
    const { container } = render(
      <ToolHealthIndicator toolName="EntityExtractor" health={healthyHealth} />
    );
    expect(container).toBeTruthy();
  });

  it('displays tool name and status tag', () => {
    render(<ToolHealthIndicator toolName="EntityExtractor" health={healthyHealth} />);
    expect(screen.getByText('EntityExtractor')).toBeTruthy();
    expect(screen.getByText('Healthy')).toBeTruthy();
  });

  it('displays success rate and avg duration', () => {
    render(<ToolHealthIndicator toolName="EntityExtractor" health={healthyHealth} />);
    expect(screen.getByText('98.5%')).toBeTruthy();
    expect(screen.getByText('120ms')).toBeTruthy();
  });

  it('displays error count when present', () => {
    render(<ToolHealthIndicator toolName="DataIngest" health={degradedHealth} />);
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('displays last error message when present', () => {
    render(<ToolHealthIndicator toolName="DataIngest" health={unhealthyHealth} />);
    expect(screen.getByText(/Connection timeout after 30s/)).toBeTruthy();
  });

  it('does not display error section when error_count is 0', () => {
    const healthNoErrors = { ...healthyHealth, error_count: 0 };
    render(<ToolHealthIndicator toolName="EntityExtractor" health={healthNoErrors} />);
    expect(screen.queryByText('Errors (24h)')).toBeNull();
  });
});
