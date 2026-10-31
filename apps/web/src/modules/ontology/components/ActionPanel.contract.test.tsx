/**
 * ActionPanel 契约测试
 *
 * 这一屏是「动作提交 → OPA 裁决 → 执行 → 写回」闭环在前端的唯一入口。此前它是断链组件
 * （零路由引用），且一旦挂载就会踩两个真实契约错误：
 *   1) `POST /api/actions/{id}/approve` 的请求体缺少必填字段 `action_record_id` → 422；
 *   2) UI 上给了「批准 / 拒绝」两个按钮，但后端 `approve_and_execute` 只对 `approved`
 *      状态的记录执行，且没有人工拒绝接口 → 点「拒绝」同样会尝试执行。
 *
 * 断言粒度：请求了哪个 URL、带了什么 body，以及**不该出现的按钮不存在**。
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// 只替换表格，避免整个 shared 桶（含图组件、monaco 等）进入 jsdom
vi.mock('@/modules/shared', () => ({
  AdvancedTable: ({
    columns,
    dataSource,
  }: {
    columns: Array<{
      title: ReactNode;
      key: string;
      dataIndex?: string;
      render?: (v: unknown, r: unknown) => ReactNode;
    }>;
    dataSource: Array<Record<string, unknown>>;
  }) => (
    <table>
      <tbody>
        {dataSource.map((row) => (
          <tr key={String(row.action_record_id)} data-testid={`row-${String(row.status)}`}>
            {columns.map((col) => {
              // 真实表格按 dataIndex 取值；actions 列无 dataIndex，只靠 render
              const value = col.dataIndex ? row[col.dataIndex] : undefined;
              return <td key={col.key}>{col.render ? col.render(value, row) : String(value ?? '')}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  ),
}));

vi.mock('@/modules/shared/services/api', () => ({
  api: {
    listActionRecords: vi.fn(),
    listActionTypes: vi.fn(),
    listObjectTypes: vi.fn(),
    submitAction: vi.fn(),
    approveAction: vi.fn(),
  },
}));

import { api } from '@/modules/shared/services/api';
import ActionPanel from './ActionPanel';

const m = api as unknown as {
  listActionRecords: ReturnType<typeof vi.fn>;
  listActionTypes: ReturnType<typeof vi.fn>;
  listObjectTypes: ReturnType<typeof vi.fn>;
  submitAction: ReturnType<typeof vi.fn>;
  approveAction: ReturnType<typeof vi.fn>;
};

const RECORDS = [
  {
    action_record_id: 'ar-approved',
    action_type_id: 'ship_order',
    target_object_id: 'ORDER-1',
    target_object_type: 'Order',
    status: 'approved',
    requested_by: 'alice',
    reason: '按时交付',
    created_at: '2026-10-17T10:00:00',
    updated_at: '2026-10-17T10:05:00',
  },
  {
    action_record_id: 'ar-pending',
    action_type_id: 'ship_order',
    target_object_id: 'ORDER-2',
    target_object_type: 'Order',
    status: 'pending',
    requested_by: 'bob',
    created_at: '2026-10-17T11:00:00',
  },
  {
    action_record_id: 'ar-rejected',
    action_type_id: 'ship_order',
    target_object_id: 'ORDER-3',
    target_object_type: 'Order',
    status: 'rejected',
    requested_by: 'carol',
    created_at: '2026-10-17T12:00:00',
  },
];

const ACTION_TYPES = [
  { action_type_id: 'ship_order', name: 'ship', display_name: '发货', target_type: 'Order' },
];

beforeEach(() => {
  Object.values(m).forEach((fn) => fn.mockReset());
  m.listActionRecords.mockResolvedValue(RECORDS);
  m.listActionTypes.mockResolvedValue(ACTION_TYPES);
  m.listObjectTypes.mockResolvedValue([]);
  m.approveAction.mockResolvedValue({});
  m.submitAction.mockResolvedValue({});
});

describe('ActionPanel — 动作记录与执行', () => {
  it('拉取记录走 /api/actions/records，且不再请求 object-types', async () => {
    render(<ActionPanel />);
    await waitFor(() => expect(m.listActionRecords).toHaveBeenCalled());

    expect(m.listActionRecords).toHaveBeenCalledWith(undefined, 50, 0);
    expect(m.listActionTypes).toHaveBeenCalled();
    // 负向：objectTypes 此前被拉取却从未使用，已移除
    expect(m.listObjectTypes).not.toHaveBeenCalled();
  });

  it('只有 approved 记录可执行；不存在后端没有的「批准/拒绝」入口', async () => {
    render(<ActionPanel />);
    await waitFor(() => expect(screen.getByTestId('row-approved')).toBeInTheDocument());

    const approvedRow = screen.getByTestId('row-approved');
    expect(within(approvedRow).getAllByRole('button').length).toBe(1);
    const executeBtn = within(approvedRow).getByRole('button');
    // antd 会在两个中文字之间插入空格（autoInsertSpace），比对时去掉空白
    expect(executeBtn.textContent?.replace(/\s/g, '')).toBe('执行');

    // pending / rejected 只读
    for (const status of ['pending', 'rejected']) {
      const row = screen.getByTestId(`row-${status}`);
      expect(within(row).queryAllByRole('button').length).toBe(0);
    }

    // 负向：后端无人工审批接口，这两类按钮不应存在
    expect(screen.queryByRole('button', { name: '批准' })).toBeNull();
    expect(screen.queryByRole('button', { name: '拒绝' })).toBeNull();
  });

  it('执行动作时请求体必须带 action_record_id（缺了会 422）', async () => {
    render(<ActionPanel />);
    await waitFor(() => expect(screen.getByTestId('row-approved')).toBeInTheDocument());

    fireEvent.click(within(screen.getByTestId('row-approved')).getByRole('button'));

    await waitFor(() => expect(m.approveAction).toHaveBeenCalledTimes(1));
    const [recordId, approval] = m.approveAction.mock.calls[0];
    expect(recordId).toBe('ar-approved');
    expect(approval).toEqual({ approved: true, approver: 'user', comment: '在前端触发执行' });
  });

  it('提交动作时 target_object_type 取自动作类型定义，不是魔法常量', async () => {
    render(<ActionPanel />);
    await waitFor(() => expect(m.listActionTypes).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /提交动作/ }));
    await waitFor(() => expect(screen.getByLabelText('动作类型')).toBeInTheDocument());

    // 选动作类型（antd Select：点选择器后在弹层里点 .ant-select-item-option）
    fireEvent.mouseDown(screen.getByLabelText('动作类型'));
    const option = await waitFor(() => {
      const el = Array.from(document.querySelectorAll('.ant-select-item-option')).find((o) =>
        (o.textContent ?? '').includes('发货'),
      );
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    fireEvent.click(option);

    fireEvent.change(screen.getByPlaceholderText('输入目标对象的唯一标识'), {
      target: { value: 'ORDER-9' },
    });
    fireEvent.change(screen.getByPlaceholderText('{"destination": "A区", "speed": 50}'), {
      target: { value: '{"destination":"A区"}' },
    });

    // Modal 默认确认按钮文案为 OK
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await waitFor(() => expect(m.submitAction).toHaveBeenCalledTimes(1));
    expect(m.submitAction.mock.calls[0][0]).toMatchObject({
      action_type_id: 'ship_order',
      target_object_id: 'ORDER-9',
      target_object_type: 'Order',
      parameters: { destination: 'A区' },
    });
  });
});
