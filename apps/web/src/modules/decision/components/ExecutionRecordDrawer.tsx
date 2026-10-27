/**
 * 执行记录核对抽屉（只读）
 *
 * 为什么要有它：E41 要求同步态**必须给出核对入口**，否则「状态可能未同步」只是
 * 把一个更吓人的问号丢给用户。前端没有执行记录页面，所以这里直接按
 * `action_record_id` 读既有 `GET /api/actions/records/{id}`（复用 `@/modules/shared` 的 `api`，
 * 零新增依赖），只读展示、不做任何写操作。
 */
import React, { useEffect, useState } from 'react';
import { Alert, Descriptions, Drawer, Skeleton, Typography } from 'antd';
// 直接从具体文件导入，不走 `@/modules/shared` 桶文件：
// 桶文件会把 ProTable 等重组件拖进来，测试与首屏都白白付这笔代价
import { api } from '@/modules/shared/services/api';
import { describeError } from '../services/decisionRequest';

const { Text } = Typography;

interface Props {
  open: boolean;
  actionRecordId: string | null;
  onClose: () => void;
}

/** 只展示契约里稳定存在的字段，不猜字段名 */
const FIELDS: Array<{ key: string; label: string }> = [
  { key: 'action_record_id', label: '执行记录 ID' },
  { key: 'action_type_id', label: '动作类型' },
  { key: 'target_object_id', label: '目标对象' },
  { key: 'status', label: '执行状态' },
  { key: 'approved_by', label: '审批人' },
  { key: 'created_at', label: '创建时间' },
  { key: 'updated_at', label: '更新时间' },
  { key: 'error_message', label: '错误信息' },
];

export function ExecutionRecordDrawer({ open, actionRecordId, onClose }: Props) {
  const [record, setRecord] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<unknown>(null);
  // 不用独立的 loading state：`record` 与 `error` 都还没落地就是加载中，
  // 少一个 state 少一次渲染，也避免在 effect 体里同步 setState
  const loading = open && record === null && error === null;

  useEffect(() => {
    if (!open || !actionRecordId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = (await api.getActionRecord(actionRecordId)) as Record<string, unknown>;
        if (!cancelled) setRecord(data ?? {});
      } catch (e) {
        if (!cancelled) setError(e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, actionRecordId]);

  return (
    <Drawer
      title="执行记录"
      open={open}
      onClose={onClose}
      size="large"
      destroyOnHidden
      styles={{ body: { padding: 'var(--odap-spacing-md)' } }}
    >
      {loading && <Skeleton active paragraph={{ rows: 6 }} />}

      {!loading && error != null && (
        <Alert
          type="error"
          showIcon
          message="执行记录读取失败"
          description={<Text type="secondary">{describeError(error)}</Text>}
        />
      )}

      {!loading && !error && record && (
        <Descriptions column={1} size="small" bordered>
          {FIELDS.map((field) => {
            const value = record[field.key];
            if (value === undefined || value === null || value === '') return null;
            return (
              <Descriptions.Item key={field.key} label={field.label}>
                <Text style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {String(value)}
                </Text>
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      )}

      {!loading && !error && !record && (
        <Text type="secondary">没有可展示的执行记录字段。</Text>
      )}
    </Drawer>
  );
}

export default ExecutionRecordDrawer;
