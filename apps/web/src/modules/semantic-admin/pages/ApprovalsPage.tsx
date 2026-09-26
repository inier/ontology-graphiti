/**
 * 审批工作台 ApprovalsPage（Semantic Admin）
 *
 * 统一对接 approvalApi（非裸 fetch），按业务角色分流：
 *   - schema_auditor（L1 审核员）→ 待 PENDING_REVIEW 审核
 *   - admin（L2 管理员）→ 待 ADMIN_PENDING 终审
 *
 * 状态枚举统一使用 types/index.ts 的 CandidateStatus 与 CANDIDATE_STATUS_COLOR/LABEL。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card,
  Table,
  Tabs,
  Tag,
  Space,
  Button,
  Typography,
  Tooltip,
  message,
  Spin,
  Empty,
  Descriptions,
  Modal,
  Form,
  Input,
} from 'antd';
import {
  AuditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  EditOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import {
  listApprovalTasks,
  actionAudit,
  actionModify,
  actionReject,
  actionFinalApprove,
} from '../services/approvalApi';
import {
  type ApprovalTask,
  CANDIDATE_STATUS_COLOR,
  CANDIDATE_STATUS_LABEL,
} from '../types';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

type RoleFilter = 'schema_auditor' | 'admin' | 'ALL';

export function ApprovalsPage() {
  const { t } = useI18n();
  const [role, setRole] = useState<RoleFilter>('ALL');
  const [tasks, setTasks] = useState<ApprovalTask[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listApprovalTasks({
        assigned_role: role === 'ALL' ? undefined : role,
        page: 1,
        page_size: 200,
      });
      setTasks(res.items ?? []);
    } catch (e) {
      message.error(e instanceof Error ? e.message : t('加载审批任务失败'));
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [role, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const statusLabel = useMemo(
    () => (v: string) => CANDIDATE_STATUS_LABEL[v as keyof typeof CANDIDATE_STATUS_LABEL] ?? v,
    [],
  );
  const statusColor = useMemo(
    () => (v: string) => CANDIDATE_STATUS_COLOR[v as keyof typeof CANDIDATE_STATUS_COLOR] ?? 'default',
    [],
  );

  const openModify = (task: ApprovalTask) => {
    let modifyComment = '';
    let patchJson = '';
    Modal.confirm({
      title: t('修改候选 · {{id}}', { id: task.candidate_id }),
      icon: <EditOutlined />,
      okText: t('提交修改'),
      cancelText: t('取消'),
      okButtonProps: { icon: <SaveOutlined /> },
      content: (
        <Form layout="vertical">
          <Form.Item label={t('修改说明（必填）')} required>
            <TextArea
              rows={3}
              onChange={(e) => { modifyComment = e.target.value; }}
              placeholder={t('例如：层级从「势力主公」改为「君主」')}
            />
          </Form.Item>
          <Form.Item label={t('字段 Patch（JSON，可选）')}>
            <TextArea
              rows={3}
              onChange={(e) => { patchJson = e.target.value; }}
              placeholder='{"canonical": "刘备", "semantic_type": "OBJECT"}'
            />
          </Form.Item>
        </Form>
      ),
      onOk: async () => {
        if (!modifyComment.trim()) {
          message.warning(t('请填写修改说明'));
          return;
        }
        let patch: Record<string, unknown> = {};
        if (patchJson.trim()) {
          try {
            patch = JSON.parse(patchJson);
          } catch {
            message.warning(t('Patch JSON 格式错误'));
            return;
          }
        }
        try {
          await actionModify(task.task_id, {
            candidate_patch: patch,
            editor_comment: modifyComment,
          });
          message.success(t('已提交修改'));
        } catch (e) {
          message.error(e instanceof Error ? e.message : t('修改失败'));
        }
        void load();
      },
    });
  };

  const openReject = (task: ApprovalTask) => {
    Modal.confirm({
      title: t('驳回 · {{label}}', { label: task.candidate_id }),
      icon: <StopOutlined />,
      okText: t('确认驳回'),
      okButtonProps: { danger: true, icon: <CloseCircleOutlined /> },
      content: (
        <Paragraph type="warning">
          {t('驳回的候选会进入驳回态，再次被 pipeline 命中时直接加入 STOPLISTED（跳过质量闸）')}
        </Paragraph>
      ),
      onOk: async () => {
        try {
          await actionReject(task.task_id, { reason: t('不合规'), close_task: true });
          message.success(t('已驳回'));
        } catch (e) {
          message.error(e instanceof Error ? e.message : t('驳回失败'));
        }
        void load();
      },
    });
  };

  const onAudit = async (task: ApprovalTask) => {
    try {
      // approve: true 必须显式传。后端 AuditRequest.approve 是必填字段，
      // 早先这里只传 {comment}，后端 decisions.get("approve", False) 取到 False
      // → 候选被写成 REVIEWER_REJECTED，而界面弹的是「L1 审核通过」。
      await actionAudit(task.task_id, { approve: true, comment: t('L1 审核通过') });
      message.success(t('L1 审核通过'));
    } catch (e) {
      message.error(e instanceof Error ? e.message : t('审核失败'));
    }
    void load();
  };

  const onFinalApprove = async (task: ApprovalTask) => {
    try {
      await actionFinalApprove(task.task_id, { comment: t('L2 终审通过'), auto_promote: true });
      message.success(t('L2 终审通过 → 触发 USL 写回'));
    } catch (e) {
      message.error(e instanceof Error ? e.message : t('终审失败'));
    }
    void load();
  };

  return (
    <SemanticAdminTabsContainer>
      <Card
        title={
          <Space size="middle">
            <span><AuditOutlined style={{ marginRight: 6 }} /> {t('审批工作台 · Approvals')}</span>
          </Space>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>{t('刷新')}</Button>
        }
      >
        <Title level={5} style={{ marginBottom: 12 }}>{t('按业务角色分流')}</Title>
        <Tabs
          activeKey={role}
          onChange={(k) => setRole(k as RoleFilter)}
          items={[
            { key: 'ALL', label: t('全部待审 (ALL)') },
            { key: 'schema_auditor', label: t('L1 · 语义审核员 (schema_auditor)') },
            { key: 'admin', label: t('L2 · 语义管理员 (admin)') },
          ]}
        />
      </Card>

      <Spin spinning={loading} tip={t('加载审批任务...')}>
        <Card style={{ marginTop: 16 }}>
          <Table<ApprovalTask>
            rowKey={(r) => r.task_id}
            locale={{ emptyText: <Empty description={t('当前暂无待审任务')} /> }}
            columns={[
              {
                title: t('候选'),
                dataIndex: 'candidate_id',
                key: 'candidate',
                width: 260,
                render: (_, r) => (
                  <Space direction="vertical" size={0}>
                    <span style={{ fontWeight: 600 }}>{r.title ?? r.candidate_id}</span>
                    <span style={{ color: '#8c8c8c', fontSize: 12 }}>{r.candidate_id}</span>
                  </Space>
                ),
              },
              {
                title: t('角色'),
                dataIndex: 'assigned_role',
                key: 'role',
                width: 160,
                render: (v) => (
                  <Tag color={v === 'admin' ? 'orange' : 'blue'}>
                    {v === 'admin' ? t('语义管理员') : t('语义审核员')}
                  </Tag>
                ),
              },
              {
                title: t('状态'),
                dataIndex: 'status',
                key: 'status',
                width: 160,
                render: (v: string) => <Tag color={statusColor(v)}>{statusLabel(v)}</Tag>,
              },
              {
                title: t('优先级'),
                dataIndex: 'priority',
                key: 'priority',
                width: 90,
                render: (v) => v ? <Tag>{v}</Tag> : '-',
              },
              { title: t('时间'), dataIndex: 'created_at', key: 'ts', width: 180, render: (v) => v ? new Date(v).toLocaleString() : '-' },
              {
                title: t('操作'),
                key: 'op',
                width: 320,
                render: (_, r) => {
                  const isAuditor = r.assigned_role !== 'admin';
                  const isAdmin = r.assigned_role === 'admin';
                  return (
                    <Space size={4} wrap>
                      {isAuditor ? (
                        <Tooltip title={t('L1 审核通过 → AUDITOR_APPROVED（加速通道直接 APPROVED）')}>
                          <Button type="link" icon={<CheckCircleOutlined />} onClick={() => onAudit(r)}>{t('L1 通过')}</Button>
                        </Tooltip>
                      ) : null}
                      {isAuditor ? (
                        <Tooltip title={t('修改候选后回退，可再次送审')}>
                          <Button type="link" icon={<EditOutlined />} onClick={() => openModify(r)}>{t('修改')}</Button>
                        </Tooltip>
                      ) : null}
                      {isAuditor ? (
                        <Tooltip title={t('驳回 → 下次命中 STOPLISTED')}>
                          <Button type="link" danger icon={<CloseCircleOutlined />} onClick={() => openReject(r)}>{t('驳回')}</Button>
                        </Tooltip>
                      ) : null}
                      {isAdmin ? (
                        <Tooltip title={t('L2 终审通过 → APPROVED → USL 写回')}>
                          <Button type="link" style={{ color: '#13c2c2' }} icon={<CheckCircleOutlined />} onClick={() => onFinalApprove(r)}>{t('L2 终审')}</Button>
                        </Tooltip>
                      ) : null}
                      {isAdmin ? (
                        <Tooltip title={t('L2 驳回 → 驳回态')}>
                          <Button type="link" danger icon={<CloseCircleOutlined />} onClick={() => openReject(r)}>{t('L2 驳回')}</Button>
                        </Tooltip>
                      ) : null}
                    </Space>
                  );
                },
              },
            ]}
            dataSource={tasks}
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total: number) => t('共 {{n}} 条', { n: total }) }}
            expandable={{
              expandedRowRender: (r) => (
                <Descriptions size="small" bordered column={1} title={t('审批详情')}>
                  <Descriptions.Item label={t('任务 ID')}>{r.task_id}</Descriptions.Item>
                  <Descriptions.Item label={t('类型')}>{r.task_type ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label={t('域')}>{r.domain_id ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label={t('指派用户')}>{r.assignee_user_id ?? t('（未指派）')}</Descriptions.Item>
                </Descriptions>
              ),
            }}
          />
        </Card>
      </Spin>
    </SemanticAdminTabsContainer>
  );
}

export default ApprovalsPage;
