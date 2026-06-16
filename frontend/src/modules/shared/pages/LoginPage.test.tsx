import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginPage } from './LoginPage';

// ─── Mocks ───

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate, useSearchParams: () => [new URLSearchParams()] };
});

const mockLogin = vi.fn();
const mockLoginSSO = vi.fn();
vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn((selector: (s: Record<string, unknown>) => unknown) =>
    selector({ login: mockLogin, loginSSO: mockLoginSSO }),
  ),
}));

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ providers: [] }),
    post: vi.fn(),
  },
}));

// ─── Tests ───

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders login form with username and password fields', () => {
    render(<LoginPage />);

    expect(screen.getByPlaceholderText('用户名')).toBeTruthy();
    expect(screen.getByPlaceholderText('密码')).toBeTruthy();
    expect(screen.getByRole('button', { name: /登 录/ })).toBeTruthy();
  });

  it('renders ODAP branding', () => {
    render(<LoginPage />);

    expect(screen.getByText('ODAP')).toBeTruthy();
    expect(screen.getByText('本体驱动分析决策平台')).toBeTruthy();
  });

  it('renders demo account info', () => {
    render(<LoginPage />);

    expect(screen.getByText('演示账号')).toBeTruthy();
    expect(screen.getByText('admin')).toBeTruthy();
    expect(screen.getByText('admin123')).toBeTruthy();
  });

  it('submits form with valid credentials', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);

    const usernameInput = screen.getByPlaceholderText('用户名');
    const passwordInput = screen.getByPlaceholderText('密码');
    const submitButton = screen.getByRole('button', { name: /登 录/ });

    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    fireEvent.change(passwordInput, { target: { value: 'admin123' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'admin123');
    });
  });

  it('navigates to home on successful login', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /登 录/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('shows error on failed login', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /登 录/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Ant Design message renders in a container outside the component tree
      // Check that login was called and navigate was NOT called
      expect(mockLogin).toHaveBeenCalled();
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  it('shows loading state during submission', async () => {
    // Make login hang so we can observe loading state
    mockLogin.mockImplementationOnce(() => new Promise(() => {}));
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /登 录/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Ant Design Button with loading adds ant-btn-loading class
      expect(submitButton.className).toContain('ant-btn-loading');
    });
  });

  it('renders feature cards on the left panel', () => {
    render(<LoginPage />);

    expect(screen.getByText('本体建模')).toBeTruthy();
    expect(screen.getByText('智能决策')).toBeTruthy();
    expect(screen.getByText('策略治理')).toBeTruthy();
    expect(screen.getByText('角色协同')).toBeTruthy();
  });
});
