/**
 * OntologyRelations 四面板契约测试
 *
 * 目的：把这些组件**钉死在后端真实契约上**。此前它们全部按虚构端点/字段实现
 * （`/api/ontology/mixins`、`/api/ontology/computed`、`/api/ontology/computed/materialized-views`、
 * `/api/ontology/inheritance` 聚合端点、`resolution_chain` 字段、`mixin_id` 主键…），
 * 页面一打开就 404 或空列表，而且不会有人发现——因为没有任何测试断言过 URL。
 *
 * 因此这里断言的粒度是「请求了哪个 URL、带了什么 body」，而不只是"渲染没崩"。
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { ReactNode } from 'react';

// ── 图谱组件用 Cytoscape，jsdom 下无法真实渲染；替换为可控替身，
//    只保留本测试关心的输入（节点/边数量）与回调（onNodeClick）。
vi.mock('@/modules/shared/modules/graph', () => ({
  HierarchyGraph: ({
    nodes,
    edges,
    onNodeClick,
    detailPanel,
  }: {
    nodes: Array<{ id: string }>;
    edges: unknown[];
    onNodeClick?: (n: { id: string }) => void;
    detailPanel?: ReactNode;
  }) => (
    <div>
      <div data-testid="graph-node-count">{nodes.length}</div>
      <div data-testid="graph-edge-count">{edges.length}</div>
      {nodes.map((n) => (
        <button key={n.id} type="button" onClick={() => onNodeClick?.(n)}>
          {n.id}
        </button>
      ))}
      {detailPanel}
    </div>
  ),
}));

vi.mock('@/modules/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, vars?: Record<string, unknown>) => {
      if (!vars) return key;
      return Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{{${k}}}`, String(v)), key);
    },
  }),
}));

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from '@/modules/shared/services/apiClient';
import { InheritanceGraph } from './InheritanceGraph';
import { MixinConfig } from './MixinConfig';
import { ComputedPropertyList } from './ComputedPropertyList';
import { MaterializationJobsPanel } from './MaterializationJobsPanel';

const api = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.put.mockReset();
  api.delete.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ─────────────────────────── InheritanceGraph ───────────────────────────

describe('InheritanceGraph — 继承关系图', () => {
  const OBJECT_TYPES = [
    { object_type_id: 't_person', name: 'Person' },
    { object_type_id: 't_employee', name: 'Employee' },
  ];
  const EDGES = [{ id: 'e1', child_type_id: 't_employee', parent_type_id: 't_person', depth: 1 }];
  const MIXINS = [
    { id: 'm_audit', name: 'Auditable', properties: ['created_at'], target_type_ids: ['t_employee'] },
  ];

  function mockHappyPath() {
    api.get.mockImplementation((url: string) => {
      if (url === '/api/ontology/object-types') return Promise.resolve(OBJECT_TYPES);
      if (url === '/api/ontology/inheritance/edges') return Promise.resolve({ edges: EDGES, count: 1 });
      if (url === '/api/ontology/inheritance/mixins') return Promise.resolve({ mixins: MIXINS, count: 1 });
      if (url.startsWith('/api/ontology/inheritance/resolve/')) {
        return Promise.resolve({
          type_id: 't_employee',
          // 真实形状：属性名 → ResolvedProperty[]（字典，不是数组，也没有 resolution_chain）
          properties: {
            name: [{ property_name: 'name', source: 'parent:t_person', depth: 1, value: null }],
            email: [{ property_name: 'email', source: 'self', depth: 0, value: null }],
          },
          count: 2,
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  }

  it('并行拉取三个真实端点，且不请求不存在的聚合端点', async () => {
    mockHappyPath();
    render(<InheritanceGraph />);

    await waitFor(() => expect(screen.getByTestId('graph-node-count').textContent).toBe('3'));

    const urls = api.get.mock.calls.map((c) => c[0] as string);
    expect(urls).toContain('/api/ontology/object-types');
    expect(urls).toContain('/api/ontology/inheritance/edges');
    expect(urls).toContain('/api/ontology/inheritance/mixins');
    // 曾经的 bug：请求 /api/ontology/inheritance 这个不存在的聚合端点 → 恒 404
    expect(urls).not.toContain('/api/ontology/inheritance');
  });

  it('边方向为 child → parent，并把 mixin 挂接边一并建出', async () => {
    mockHappyPath();
    render(<InheritanceGraph />);
    await waitFor(() => expect(screen.getByTestId('graph-node-count').textContent).toBe('3'));
    // 1 条继承边 + 1 条 mixin 挂接边
    expect(screen.getByTestId('graph-edge-count').textContent).toBe('2');
  });

  it('点击节点后按 resolve 字典渲染属性来源与深度', async () => {
    mockHappyPath();
    render(<InheritanceGraph />);
    await waitFor(() => expect(screen.getByTestId('graph-node-count').textContent).toBe('3'));

    fireEvent.click(screen.getByRole('button', { name: 't_employee' }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/ontology/inheritance/resolve/t_employee');
    });
    // 来自父类的属性
    await waitFor(() => expect(screen.getByText('name')).toBeTruthy());
    expect(screen.getByText('email')).toBeTruthy();
    // t_person 既出现在图上节点按钮里，也出现在抽屉的「来源」标签里
    expect(screen.getAllByText('t_person').length).toBeGreaterThan(0);
    // depth=0 的行渲染「自身」而不是把空 from 直接显示出来
    expect(screen.getByText('inheritanceGraph.selfDeclared')).toBeTruthy();
  });

  it('删除继承边走成对主键端点（child/parent），而不是 edgeId', async () => {
    mockHappyPath();
    api.delete.mockResolvedValue({ status: 'ok' });
    render(<InheritanceGraph />);
    await waitFor(() => expect(screen.getByTestId('graph-node-count').textContent).toBe('3'));

    fireEvent.click(screen.getByRole('button', { name: 't_employee' }));
    await waitFor(() => expect(screen.getAllByText('t_person').length).toBeGreaterThan(0));

    // 父类型行的删除按钮：文案按「中文即 key」约定已合并为「删除」，全页唯一
    fireEvent.click(screen.getByRole('button', { name: /删\s*除/ }));

    // Popconfirm 的确认按钮在浮层里，按容器定位而不是按文案（避免和触发按钮重名）
    const popconfirm = await waitFor(() => {
      const el = document.querySelector('.ant-popconfirm');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    const confirmButtons = within(popconfirm).getAllByRole('button');
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/api/ontology/inheritance/edges/t_employee/t_person');
    });
  });
});

// ─────────────────────────── MixinConfig ───────────────────────────

describe('MixinConfig — Mixin 库与挂接', () => {
  const MIXINS = [
    { id: 'm1', name: 'Auditable', description: '审计字段', properties: ['created_at', 'created_by'], target_type_ids: ['t1'], created_at: '2026-01-01T00:00:00' },
  ];

  it('列表走 /api/ontology/inheritance/mixins，并以 id 为主键渲染', async () => {
    api.get.mockImplementation((url: string) => {
      if (url === '/api/ontology/inheritance/mixins') return Promise.resolve({ mixins: MIXINS, count: 1 });
      if (url === '/api/ontology/object-types') return Promise.resolve({ object_types: [{ object_type_id: 't1', name: 'Person' }] });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    render(<MixinConfig />);

    await waitFor(() => expect(screen.getByText('Auditable')).toBeTruthy());
    const urls = api.get.mock.calls.map((c) => c[0] as string);
    // 曾经请求 /api/ontology/mixins（不存在）
    expect(urls).not.toContain('/api/ontology/mixins');
    expect(urls).toContain('/api/ontology/inheritance/mixins');
    // 派生列：properties.length=2 / target_type_ids.length=1，断言在表格行内取值
    const row = screen.getByText('Auditable').closest('tr');
    expect(row).toBeTruthy();
    const cells = within(row as HTMLElement).getAllByRole('cell').map((c) => c.textContent);
    expect(cells).toContain('2');
    expect(cells).toContain('1');
  });

  it('新建 Mixin 的 properties 是字符串数组（后端 List[str]，不是对象数组）', async () => {
    api.get.mockImplementation((url: string) => {
      if (url === '/api/ontology/inheritance/mixins') return Promise.resolve({ mixins: [], count: 0 });
      if (url === '/api/ontology/object-types') return Promise.resolve({ object_types: [] });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    api.post.mockResolvedValue({ id: 'm_new' });

    render(<MixinConfig />);
    await waitFor(() => expect(screen.getByText('Create Mixin')).toBeTruthy());

    fireEvent.click(screen.getByText('Create Mixin'));
    const nameInput = await screen.findByPlaceholderText('mixin_name');
    fireEvent.change(nameInput, { target: { value: 'Timestamped' } });
    fireEvent.click(screen.getByRole('button', { name: '保 存' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/ontology/inheritance/mixins', {
        name: 'Timestamped',
        description: '',
        properties: [],
      });
    });
  });

  // antd Transfer 的交互链路在 jsdom 下较慢，全量执行时单例耗时可能超过默认 5s，故显式放宽
  it('保存挂接按差集调用 attach/detach，而不是对一个不存在的 PUT 端点整体覆盖', { timeout: 30000 }, async () => {
    api.get.mockImplementation((url: string) => {
      if (url === '/api/ontology/inheritance/mixins') {
        return Promise.resolve({
          mixins: [
            { id: 'm1', name: 'Auditable', description: '', properties: [], target_type_ids: [] },
            { id: 'm2', name: 'SoftDelete', description: '', properties: [], target_type_ids: [] },
          ],
          count: 2,
        });
      }
      if (url === '/api/ontology/object-types') {
        return Promise.resolve({ object_types: [{ object_type_id: 't1', name: 'Person' }] });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    api.post.mockResolvedValue({ status: 'ok' });

    render(<MixinConfig />);
    await waitFor(() => expect(screen.getByText('Mixin Bindings')).toBeTruthy());
    fireEvent.click(screen.getByText('Mixin Bindings'));

    // 选中 ObjectType
    await waitFor(() => expect(screen.getByText('Person')).toBeTruthy());
    fireEvent.click(screen.getByText('Person'));

    // Transfer 里把 Auditable 挪到右侧（Transfer 也渲染同名条目，故限定在 Transfer 容器内查找）
    const transfer = await waitFor(() => {
      const el = document.querySelector('.ant-transfer');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    const transferItem = within(transfer).getAllByText('Auditable')[0];
    const listItem = transferItem.closest('li');
    expect(listItem).toBeTruthy();
    const checkbox = within(listItem as HTMLElement).getByRole('checkbox');
    fireEvent.click(checkbox);

    // Transfer 勾选只是选中，真正移动要点「向右」操作按钮
    // （antd 6 把 operations 区类名从 -operation 改成 -actions，两种都找）
    const moveRight = await waitFor(() => {
      const btn = document.querySelector('.ant-transfer-actions button, .ant-transfer-operation button');
      expect(btn).toBeTruthy();
      return btn as HTMLElement;
    });
    fireEvent.click(moveRight);

    fireEvent.click(screen.getByRole('button', { name: /Save Bindings/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/ontology/inheritance/mixins/m1/attach/t1', {});
    });
    expect(api.put).not.toHaveBeenCalled();
  });
});

// ─────────────────────── ComputedPropertyList ───────────────────────

describe('ComputedPropertyList — 计算属性', () => {
  const PROPS = [
    {
      id: 'cp1',
      name: 'full_name',
      target_type_id: 't1',
      expression: 'concat(properties.first, properties.last)',
      dependencies: ['first', 'last'],
      materialization: 'incremental',
      return_type: 'string',
      description: '',
      enabled: true,
    },
  ];

  function mockList() {
    api.get.mockImplementation((url: string) => {
      if (url.startsWith('/api/ontology/computed/properties')) return Promise.resolve({ properties: PROPS, count: 1 });
      if (url === '/api/ontology/object-types') return Promise.resolve({ object_types: [{ object_type_id: 't1', name: 'Person' }] });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  }

  it('列表走 /properties 且筛选参数名为 target_type', async () => {
    mockList();
    render(<ComputedPropertyList objectTypeId="t1" />);

    await waitFor(() => expect(screen.getByText('full_name')).toBeTruthy());
    const urls = api.get.mock.calls.map((c) => c[0] as string);
    expect(urls.some((u) => u.startsWith('/api/ontology/computed/properties'))).toBe(true);
    expect(urls.some((u) => u.includes('target_type=t1'))).toBe(true);
    // 曾经请求 /api/ontology/computed?object_type_id=... （不存在）
    expect(urls.some((u) => /^\/api\/ontology\/computed(\?|$)/.test(u))).toBe(false);
    // 物化策略列取真实字段
    expect(screen.getByText('incremental')).toBeTruthy();
  });

  it('试算必须先填实例 ID，不会空 body 打到 evaluate', { timeout: 30000 }, async () => {
    mockList();
    render(<ComputedPropertyList />);
    await waitFor(() => expect(screen.getByText('full_name')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /Test/ }));
    const okButton = await screen.findByRole('button', { name: '试 算' });
    fireEvent.click(okButton);

    // 未填 instance_id → 不发请求
    expect(api.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText('instance_uuid'), { target: { value: 'inst-1' } });
    fireEvent.click(okButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/ontology/computed/properties/cp1/evaluate', {
        instance_id: 'inst-1',
        instance_data: {},
      });
    });
  });
});

// ─────────────────────── MaterializationJobsPanel ───────────────────────

describe('MaterializationJobsPanel — 物化任务', () => {
  const PROPS = [
    { id: 'cp1', name: 'full_name', target_type_id: 't1', expression: 'x', materialization: 'incremental', enabled: true },
  ];
  const JOBS = [
    {
      id: 'job1',
      property_id: 'cp1',
      status: 'done',
      started_at: '2026-01-01T00:00:00',
      finished_at: '2026-01-01T00:00:05',
      processed_count: 42,
      error_message: '',
      triggered_by: 'manual',
      mode: 'incremental',
    },
  ];

  it('任务历史走 /properties/{id}/jobs，触发重算走 recompute', async () => {
    api.get.mockImplementation((url: string) => {
      if (url === '/api/ontology/computed/properties') return Promise.resolve({ properties: PROPS, count: 1 });
      if (url === '/api/ontology/computed/properties/cp1/jobs?limit=50') return Promise.resolve({ jobs: JOBS, count: 1 });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    api.post.mockResolvedValue({ job_ids: ['job2'], affected: ['cp1'], mode: 'incremental' });

    render(<MaterializationJobsPanel />);

    // 42 同时出现在 KPI（最近处理实例数）与任务历史表格里
    await waitFor(() => expect(screen.getAllByText('42').length).toBeGreaterThan(0));
    const urls = api.get.mock.calls.map((c) => c[0] as string);
    expect(urls).toContain('/api/ontology/computed/properties/cp1/jobs?limit=50');
    // 曾经请求 /api/ontology/computed/materialized-views（不存在）
    expect(urls.some((u) => u.includes('materialized-views'))).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: /增量重算/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/ontology/computed/properties/cp1/recompute', { mode: 'incremental' });
    });
  });
});
