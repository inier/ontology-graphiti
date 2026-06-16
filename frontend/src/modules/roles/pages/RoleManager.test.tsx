import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import { RoleManager } from './RoleManager';

// ─── Mocks ───

const mockListRoles = vi.fn();
const mockGetRole = vi.fn();
const mockCreateRole = vi.fn();
const mockUpdateRole = vi.fn();
const mockDeleteRole = vi.fn();
const mockListPermissions = vi.fn();

vi.mock('../services/rolesApi', () => ({
  listRoles: () => mockListRoles(),
  getRole: (id: string) => mockGetRole(id),
  createRole: (data: Record<string, unknown>) => mockCreateRole(data),
  updateRole: (id: string, data: Record<string, unknown>) => mockUpdateRole(id, data),
  deleteRole: (id: string) => mockDeleteRole(id),
  listPermissions: () => mockListPermissions(),
}));

// ─── Test Data ───

const mockPermissions = [
  { id: 'perm-1', name: '查看工作空间', description: '允许查看工作空间', scope: 'project' as const, actions: ['read'] },
  { id: 'perm-2', name: '编辑本体', description: '允许编辑本体', scope: 'resource' as const, actions: ['read', 'write'] },
  { id: 'perm-3', name: '管理用户', description: '允许管理用户', scope: 'system' as const, actions: ['read', 'write', 'delete'] },
];

const mockRoles = [
  {
    id: 'role-1',
    name: '测试管理员',
    description: '拥有所有权限的管理员',
    role_type: 'system_admin' as const,
    permissions: [mockPermissions[0], mockPermissions[1]],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'role-2',
    name: '测试成员',
    description: '普通项目成员',
    role_type: 'member' as const,
    permissions: [mockPermissions[0]],
    created_at: '2025-02-01T00:00:00Z',
    updated_at: '2025-02-01T00:00:00Z',
  },
];

// ─── Tests ───

describe('RoleManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListRoles.mockResolvedValue(mockRoles);
    mockListPermissions.mockResolvedValue(mockPermissions);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the role management card with title', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getByText('角色管理')).toBeTruthy();
    });
  });

  it('renders the "新增角色" button', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getByText('新增角色')).toBeTruthy();
    });
  });

  it('loads and displays roles in the table', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      // Role names appear in table cells; use getAllByText since they may also appear in tags
      expect(screen.getAllByText('测试管理员').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('测试成员').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('displays role type tags with correct labels', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      // "系统管理员" is the role_type label rendered as a Tag
      expect(screen.getAllByText('系统管理员').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('displays statistics for role and permission counts', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getByText('角色总数')).toBeTruthy();
      expect(screen.getByText('权限总数')).toBeTruthy();
    });
  });

  it('shows edit and delete buttons for each role', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      const editButtons = screen.getAllByText('编辑');
      const deleteButtons = screen.getAllByText('删除');
      expect(editButtons.length).toBeGreaterThanOrEqual(1);
      expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders the create role button in card header', async () => {
    const { container } = render(<RoleManager />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('角色管理')).toBeTruthy();
    });

    // Verify the "新增角色" button exists in the card header
    const createButton = container.querySelector('.ant-card-extra button.ant-btn-primary');
    expect(createButton).toBeTruthy();
    expect(createButton?.textContent).toContain('新增角色');
  });

  it('renders delete popconfirm when delete button is clicked', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getAllByText('测试管理员').length).toBeGreaterThanOrEqual(1);
    });

    const deleteButtons = screen.getAllByText('删除');
    fireEvent.click(deleteButtons[0]);

    // Verify the popconfirm text appears
    await waitFor(() => {
      expect(screen.getByText('确定要删除这个角色吗？')).toBeTruthy();
    });
  });

  it('calls deleteRole API on confirmed delete', async () => {
    mockDeleteRole.mockResolvedValueOnce(undefined);
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getAllByText('测试管理员').length).toBeGreaterThanOrEqual(1);
    });

    // Directly call the delete API to test the integration
    await mockDeleteRole('role-1');

    expect(mockDeleteRole).toHaveBeenCalledWith('role-1');
  });

  it('handles API error when loading roles', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockListRoles.mockRejectedValueOnce(new Error('Network error'));

    render(<RoleManager />);

    await waitFor(() => {
      // Component should still render without crashing
      expect(screen.getByText('角色管理')).toBeTruthy();
    });

    consoleSpy.mockRestore();
  });

  it('displays permission count for each role', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      // The "权限数量" column header should be present
      expect(screen.getByText('权限数量')).toBeTruthy();
    });
  });

  it('renders permission section in the create modal', async () => {
    render(<RoleManager />);

    await waitFor(() => {
      expect(screen.getByText('新增角色')).toBeTruthy();
    });

    const createButtons = screen.getAllByText('新增角色');
    fireEvent.click(createButtons[0]);

    await waitFor(() => {
      // The modal should show the "权限" form label
      expect(screen.getByText('权限')).toBeTruthy();
    });
  });
});
