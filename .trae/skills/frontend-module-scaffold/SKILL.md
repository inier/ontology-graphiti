---
name: frontend-module-scaffold
description: 在 ODAP 项目中按规范结构创建前端模块（pages/components/hooks/services/types/store），使用 React 19 + TypeScript + Ant Design 6 + Zustand 5，遵循 frontend/src/modules/{领域}/{模块}/ 分层。
compatibility: Requires React 19 + TypeScript + Vite
metadata:
  author: odap-project
  source: AGENTS.md project-structure
---

# 前端模块脚手架

按 ODAP AGENTS.md 第 8 节规定的目录结构创建前端模块。

## 适用场景

- 新增前端业务模块到 `frontend/src/modules/{领域}/{模块名}/`
- 需要页面（Pages）+ 组件（Components）+ 状态（Store）+ 服务（Service）
- 使用 React 19 + TypeScript + Ant Design 6 + Zustand 5

## 用户输入

```
$ARGUMENTS
```

格式：`<领域> <模块名> [简单描述]`

示例：
- `agent agent_chat 智能体对话`
- `audit log_viewer 审计日志查看器`
- `workspace scenario_editor 场景编辑器`

## ODAP 前端业务模块

按 AGENTS.md 项目结构：
```
frontend/src/modules/
├── agent/         # 智能体
├── audit/         # 审计
├── business/      # 业务
├── config/        # 配置
├── ingest/        # 摄取
├── knowledge/     # 知识库
├── ontology/      # 本体
├── qa/            # 问答
├── roles/         # 角色
├── simulation/    # 仿真
├── system/        # 系统
├── version/       # 版本
├── workspace/     # 工作空间
└── shared/        # 共享（services/hooks/types）
```

## 生成的目录结构

```
frontend/src/modules/{domain}/{module_name}/
├── pages/
│   └── {ModuleName}Page.tsx           # 主页面
├── components/
│   └── {ModuleName}List.tsx           # 列表组件
│   └── {ModuleName}Form.tsx           # 表单组件
│   └── {ModuleName}Detail.tsx         # 详情组件
├── hooks/
│   └── use{ModuleName}.ts             # 数据 hook
├── services/
│   └── {module_name}Service.ts        # API 服务
├── types/
│   └── index.ts                       # 类型定义
├── store/
│   └── use{ModuleName}Store.ts        # Zustand store
└── index.ts                           # 模块导出
```

## 生成内容

### 1. `types/index.ts`
```typescript
/**
 * {ModuleName} 类型定义
 */

export interface {ModuleName} {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'active' | 'disabled';
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface {ModuleName}Create {
  name: string;
  description?: string;
  tags?: string[];
}

export interface {ModuleName}Update {
  name?: string;
  description?: string;
  status?: 'draft' | 'active' | 'disabled';
  tags?: string[];
}

export interface {ModuleName}ListResponse {
  total: number;
  items: {ModuleName}[];
  page: number;
  pageSize: number;
}
```

### 2. `services/{module_name}Service.ts`
```typescript
/**
 * {ModuleName} API 服务
 *
 * 遵循前端规范：
 * - 使用 fetch 或 axios 统一封装
 * - 类型安全的请求/响应
 * - 错误处理
 */
import type {
  {ModuleName},
  {ModuleName}Create,
  {ModuleName}Update,
} from '../types';

const BASE_URL = '/api/{module_name}';

export const {moduleName}Service = {
  async list(page = 1, pageSize = 20): Promise<{ModuleName}[]> {
    const response = await fetch(
      `${BASE_URL}?page=${page}&page_size=${pageSize}`
    );
    if (!response.ok) {
      throw new Error(`列表查询失败: ${response.statusText}`);
    }
    return response.json();
  },

  async get(id: string): Promise<{ModuleName}> {
    const response = await fetch(`${BASE_URL}/${id}`);
    if (!response.ok) {
      throw new Error(`查询失败: ${response.statusText}`);
    }
    return response.json();
  },

  async create(data: {ModuleName}Create): Promise<{ModuleName}> {
    const response = await fetch(BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `创建失败: ${response.statusText}`);
    }
    return response.json();
  },

  async update(id: string, data: {ModuleName}Update): Promise<{ModuleName}> {
    const response = await fetch(`${BASE_URL}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `更新失败: ${response.statusText}`);
    }
    return response.json();
  },

  async delete(id: string): Promise<void> {
    const response = await fetch(`${BASE_URL}/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`删除失败: ${response.statusText}`);
    }
  },
};
```

### 3. `store/use{ModuleName}Store.ts`
```typescript
/**
 * {ModuleName} Zustand Store
 */
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { {ModuleName} } from '../types';

interface {ModuleName}State {
  items: {ModuleName}[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  detail: {ModuleName} | null;

  setItems: (items: {ModuleName}[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSelectedId: (id: string | null) => void;
  setDetail: (detail: {ModuleName} | null) => void;
  reset: () => void;
}

export const use{ModuleName}Store = create<{ModuleName}State>()(
  devtools(
    (set) => ({
      items: [],
      loading: false,
      error: null,
      selectedId: null,
      detail: null,

      setItems: (items) => set({ items }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      setSelectedId: (selectedId) => set({ selectedId }),
      setDetail: (detail) => set({ detail }),
      reset: () => set({
        items: [],
        loading: false,
        error: null,
        selectedId: null,
        detail: null,
      }),
    }),
    { name: '{moduleName}-store' }
  )
);
```

### 4. `hooks/use{ModuleName}.ts`
```typescript
/**
 * {ModuleName} 数据 hook
 */
import { useEffect, useCallback } from 'react';
import { use{ModuleName}Store } from '../store/use{ModuleName}Store';
import { {moduleName}Service } from '../services/{module_name}Service';
import type { {ModuleName}Create, {ModuleName}Update } from '../types';

export function use{ModuleName}() {
  const {
    items,
    loading,
    error,
    selectedId,
    detail,
    setItems,
    setLoading,
    setError,
    setSelectedId,
    setDetail,
    reset,
  } = use{ModuleName}Store();

  const fetchList = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    setError(null);
    try {
      const data = await {moduleName}Service.list(page, pageSize);
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [setItems, setLoading, setError]);

  const fetchDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await {moduleName}Service.get(id);
      setDetail(data);
      setSelectedId(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [setDetail, setSelectedId, setLoading, setError]);

  const create = useCallback(async (data: {ModuleName}Create) => {
    setLoading(true);
    setError(null);
    try {
      const created = await {moduleName}Service.create(data);
      setItems([created, ...items]);
      return created;
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [items, setItems, setLoading, setError]);

  const update = useCallback(async (id: string, data: {ModuleName}Update) => {
    setLoading(true);
    setError(null);
    try {
      const updated = await {moduleName}Service.update(id, data);
      setItems(items.map((item) => (item.id === id ? updated : item)));
      if (detail?.id === id) setDetail(updated);
      return updated;
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [items, detail, setItems, setDetail, setLoading, setError]);

  const remove = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await {moduleName}Service.delete(id);
      setItems(items.filter((item) => item.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [items, setItems, setLoading, setError]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  return {
    items,
    loading,
    error,
    selectedId,
    detail,
    fetchList,
    fetchDetail,
    create,
    update,
    remove,
    reset,
  };
}
```

### 5. `components/{ModuleName}List.tsx`
```typescript
/**
 * {ModuleName} 列表组件
 */
import { Table, Tag, Button, Space, Popconfirm } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { {ModuleName} } from '../types';

interface Props {
  items: {ModuleName}[];
  loading: boolean;
  onView: (id: string) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

const STATUS_COLORS: Record<{ModuleName}['status'], string> = {
  draft: 'default',
  active: 'green',
  disabled: 'red',
};

export function {ModuleName}List({ items, loading, onView, onEdit, onDelete }: Props) {
  const columns: ColumnsType<{ModuleName}> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 200 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: {ModuleName}['status']) => (
        <Tag color={STATUS_COLORS[status]}>{status}</Tag>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => (
        <Space wrap>
          {tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => onView(record.id)}
          >
            详情
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => onEdit(record.id)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除？"
            onConfirm={() => onDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      rowKey="id"
      columns={columns}
      dataSource={items}
      loading={loading}
      pagination={{ pageSize: 20 }}
    />
  );
}
```

### 6. `components/{ModuleName}Form.tsx`
```typescript
/**
 * {ModuleName} 表单组件（创建/编辑）
 */
import { Form, Input, Select, Button, Space } from 'antd';
import { useEffect } from 'react';
import type { {ModuleName}, {ModuleName}Create, {ModuleName}Update } from '../types';

interface Props {
  initialValues?: {ModuleName};
  onSubmit: (data: {ModuleName}Create | {ModuleName}Update) => Promise<void>;
  onCancel: () => void;
  loading: boolean;
}

export function {ModuleName}Form({ initialValues, onSubmit, onCancel, loading }: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
    } else {
      form.resetFields();
    }
  }, [initialValues, form]);

  const handleFinish = async (values: {ModuleName}Create) => {
    try {
      await onSubmit(values);
      form.resetFields();
    } catch (e) {
      // 错误已在 hook 中处理
    }
  };

  return (
    <Form form={form} layout="vertical" onFinish={handleFinish}>
      <Form.Item
        label="名称"
        name="name"
        rules={[{ required: true, min: 1, max: 50 }]}
      >
        <Input placeholder="请输入名称" />
      </Form.Item>

      <Form.Item label="描述" name="description">
        <Input.TextArea rows={3} placeholder="请输入描述" />
      </Form.Item>

      <Form.Item label="标签" name="tags">
        <Select mode="tags" placeholder="按回车添加标签" />
      </Form.Item>

      <Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            {initialValues ? '更新' : '创建'}
          </Button>
          <Button onClick={onCancel}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  );
}
```

### 7. `pages/{ModuleName}Page.tsx`
```typescript
/**
 * {ModuleName} 主页面
 */
import { useState } from 'react';
import { Card, Button, Modal, message, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { use{ModuleName} } from '../hooks/use{ModuleName}';
import { {ModuleName}List } from '../components/{ModuleName}List';
import { {ModuleName}Form } from '../components/{ModuleName}Form';
import type { {ModuleName} } from '../types';

export default function {ModuleName}Page() {
  const {
    items,
    loading,
    error,
    detail,
    fetchList,
    fetchDetail,
    create,
    update,
    remove,
  } = use{ModuleName}();

  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<{ModuleName} | undefined>();
  const [detailOpen, setDetailOpen] = useState(false);

  if (error) message.error(error);

  const handleCreate = async (data: any) => {
    await create(data);
    message.success('创建成功');
    setFormOpen(false);
  };

  const handleUpdate = async (data: any) => {
    if (!editingItem) return;
    await update(editingItem.id, data);
    message.success('更新成功');
    setFormOpen(false);
    setEditingItem(undefined);
  };

  const handleDelete = async (id: string) => {
    await remove(id);
    message.success('删除成功');
  };

  return (
    <Card
      title="{ModuleName} 管理"
      extra={
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingItem(undefined);
              setFormOpen(true);
            }}
          >
            新建
          </Button>
          <Button onClick={() => fetchList()}>刷新</Button>
        </Space>
      }
    >
      <{ModuleName}List
        items={items}
        loading={loading}
        onView={async (id) => {
          await fetchDetail(id);
          setDetailOpen(true);
        }}
        onEdit={async (id) => {
          await fetchDetail(id);
          setEditingItem(detail || undefined);
          setFormOpen(true);
        }}
        onDelete={handleDelete}
      />

      <Modal
        title={editingItem ? '编辑 {ModuleName}' : '新建 {ModuleName}'}
        open={formOpen}
        onCancel={() => {
          setFormOpen(false);
          setEditingItem(undefined);
        }}
        footer={null}
        width={600}
      >
        <{ModuleName}Form
          initialValues={editingItem}
          onSubmit={editingItem ? handleUpdate : handleCreate}
          onCancel={() => {
            setFormOpen(false);
            setEditingItem(undefined);
          }}
          loading={loading}
        />
      </Modal>

      <Modal
        title="{ModuleName} 详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={<Button onClick={() => setDetailOpen(false)}>关闭</Button>}
        width={600}
      >
        {detail && (
          <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 4 }}>
            {JSON.stringify(detail, null, 2)}
          </pre>
        )}
      </Modal>
    </Card>
  );
}
```

### 8. `index.ts` 模块导出
```typescript
/**
 * {ModuleName} 模块导出
 */
export { default as {ModuleName}Page } from './pages/{ModuleName}Page';
export { use{ModuleName} } from './hooks/use{ModuleName}';
export { use{ModuleName}Store } from './store/use{ModuleName}Store';
export * from './types';
```

## 注册路由

在 `frontend/src/App.tsx` 或路由配置中添加：

```typescript
import { {ModuleName}Page } from '@/modules/{domain}/{module_name}';

// 路由表
const routes = [
  // ...
  {
    path: '/{domain}/{module_name}',
    element: <{ModuleName}Page />,
  },
];
```

## 添加 Vitest 测试

按 AGENTS.md 测试规则，前端测试用 Vitest。生成 `tests/{module_name}.test.ts`：

```typescript
/**
 * {ModuleName} 模块测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { use{ModuleName} } from '../hooks/use{ModuleName}';

vi.mock('../services/{module_name}Service');

describe('{ModuleName} Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches list on mount', async () => {
    // ...
  });

  it('creates new item', async () => {
    // ...
  });

  it('updates item', async () => {
    // ...
  });

  it('deletes item', async () => {
    // ...
  });
});
```

## 验证步骤

生成完成后：
1. 运行 `cd frontend && npm run typecheck` 确认类型通过
2. 运行 `cd frontend && npm run lint` 确认 ESLint 通过
3. 运行 `cd frontend && npm test` 确认测试通过
4. 运行 `cd frontend && npm run build` 确认构建成功
5. 在浏览器中打开页面验证

## 输出

向用户报告：
- 生成的文件列表
- TypeScript 类型检查结果
- ESLint 检查结果
- Vitest 测试结果
- Vite 构建结果
- 注册到路由的位置
- 下一步建议
