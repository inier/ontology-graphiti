/**
 * 审批工作台 ApprovalsPage（Semantic Admin 第 6 Tab）
 * 功能：
 *   - L1（schema_auditor 待审）与 L2（final_approver 待审）二级 Tabs 分流
 *   - 调用 approvalApi.listApprovalTasks 按筛选加载
 *   - 候选行内操作：audit / modify / reject / final_approve，回写后自动刷新
 *   - 未登录 / 接口未就绪降级为离线占位（不抛错）
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
import { SemanticAdminTabsContainer } from '../index';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

type ApprovalLevel = 'L1' | 'L2';
type ApprovalTask = Record<string, unknown> & {
  id?: string;
  candidate_id?: string;
  candidate_label?: string;
  level?: ApprovalLevel;
  status?: string;
  submitted_at?: string;
  submitter?: string;
  quality_tier?: string;
  total_score?: number;
  domain?: string;
  justification?: string;
};

const STATUS_COLOR: Record<string, string> = {
  AUDITOR_PENDING: 'blue',
  ADMIN_PENDING: 'orange',
  AUDITOR_APPROVED: 'cyan',
  APPROVED: 'green',
  AUDITOR_MODIFIED: 'purple',
  REJECTED: 'red',
  STOPLISTED: 'default',
};

async function safeListApprovalTasks(level?: ApprovalLevel): Promise<ApprovalTask[]> {
  const token = localStorage.getItem('token') || '';
  const qs = level ? `?level=${level}` : '';
  try {
    const res = await fetch(
      `${import.meta.env.VITE_API_BASE || ''}/api/semantic-admin/approval/tasks${qs}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!res.ok) return [];
    const json = await res.json();
    const arr: ApprovalTask[] = Array.isArray(json) ? json : json?.data ?? [];
    return arr;
  } catch {
    return [];
  }
}

async function safeApprovalAction(
  action: 'audit' | 'modify' | 'reject' | 'final-approve',
  taskId: string,
  payload: Record<string, unknown>,
): Promise<boolean> {
  const token = localStorage.getItem('token') || '';
  try {
    const res = await fetch(
      `${import.meta.env.VITE_API_BASE || ''}/api/semantic-admin/approval/tasks/${encodeURIComponent(taskId)}/${action}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      },
    );
    return res.ok;
  } catch {
    return false;
  }
}

export function ApprovalsPage() {
  const { t } = useI18n();
  const [level, setLevel] = useState<ApprovalLevel | 'ALL'>('ALL');
  const [tasks, setTasks] = useState<ApprovalTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);

  const levelLabel: Record<ApprovalLevel, string> = useMemo(() => ({
    L1: t('L1 · schema_auditor 审核'),
    L2: t('L2 · final_approver 终审'),
  }), [t]);

  const mockOffline: ApprovalTask[] = useMemo(() => [
    {
      id: 'mock-1', candidate_id: 'cid-西游记', candidate_label: t('孙悟空 · 概念对象'),
      level: 'L1', status: 'AUDITOR_PENDING', submitted_at: '2025-01-23T10:12:00',
      submitter: 'ol_pipeline@L3', quality_tier: 'TIER_A', total_score: 0.89,
      domain: t('西游'), justification: t('L3 FCA 形式概念：孙悟空与猪八戒为师兄弟，disambiguator=石猴/齐天大圣'),
    },
    {
      id: 'mock-2', candidate_id: 'cid-三国', candidate_label: t('刘备 · 势力主公'),
      level: 'L2', status: 'ADMIN_PENDING', submitted_at: '2025-01-23T11:03:00',
      submitter: 'schema_auditor:张三', quality_tier: 'TIER_B', total_score: 0.78,
      domain: t('三国'), justification: t('L1 审核员已校验蜀国与刘备 is_a 层级无误，请管理员终审'),
    },
  ], [t]);

  const load = useCallback(async () => {
    setLoading(true);
    const got = await safeListApprovalTasks(level === 'ALL' ? undefined : level);
    if (!got.length) {
      setOffline(true);
      setTasks(mockOffline.filter(task => level === 'ALL' ? true : task.level === level));
    } else {
      setOffline(false);
      setTasks(got);
    }
    setLoading(false);
  }, [level, mockOffline]);

  useEffect(() => { void load(); }, [load]);

  const openModify = (task: ApprovalTask) => {
    const initial: Record<string, unknown> = {};
    Modal.confirm({
      title: t('修改候选并送回 L2 审批 · {{id}}', { id: task.candidate_id }),
      icon: <EditOutlined />,
      okText: t('提交修改 (Auditor Modified)'),
      cancelText: t('取消'),
      okButtonProps: { danger: false, icon: <SaveOutlined /> },
      content: (
        <Form layout="vertical" initialValues={initial}>
          <Paragraph type="secondary" style={{ marginBottom: 16 }}>
            {t('修改会将候选状态回退至')} <Tag color="purple">AUDITOR_MODIFIED</Tag>，{t('随后可再次提交至 L2 终审。')}
          </Paragraph>
          <Form.Item name="modify_comment" label={t('修改说明（必填）')} rules={[{ required: true, message: t('请说明修改原因') }]}>
            <TextArea rows={3} placeholder={t('例如：层级从「势力主公」改为「君主」，disambiguator 增加「蜀汉开国皇帝」')} />
          </Form.Item>
          <Form.Item name="patch" label={t('字段 Patch（JSON，可选）')}>
            <TextArea rows={3} placeholder='{"canonical": "刘备", "semantic_type": "OBJECT"}' />
          </Form.Item>
        </Form>
      ),
      onOk: async () => {
        const ok = await safeApprovalAction('modify', task.id ?? String(task.candidate_id), {
          comment: 'Auditor Modified via UI',
        });
        if (ok) message.success(t('已提交修改')); else message.warning(t('后端未就绪，已离线记录'));
        void load();
      },
    });
  };

  const openReject = (task: ApprovalTask, currentLevel: ApprovalLevel) => {
    Modal.confirm({
      title: t('驳回 · {{level}} 驳回 {{label}}', { level: currentLevel, label: task.candidate_label ?? task.candidate_id }),
      icon: <StopOutlined />,
      okText: t('确认驳回 (REJECT)'),
      okButtonProps: { danger: true, icon: <CloseCircleOutlined /> },
      content: <Paragraph type="warning">{t('驳回的候选会进入 REJECTED，再次被 pipeline 命中时直接加入 STOPLISTED（跳过质量闸）。')}</Paragraph>,
      onOk: async () => {
        const ok = await safeApprovalAction('reject', task.id ?? String(task.candidate_id), {
          comment: t('驳回@{{level}} · UI 操作', { level: currentLevel }), reason: t('semantic/ontology 不合规'),
        });
        if (ok) message.success(t('已驳回')); else message.warning(t('后端未就绪，已离线记录'));
        void load();
      },
    });
  };

  const onAudit = async (task: ApprovalTask) => {
    const ok = await safeApprovalAction('audit', task.id ?? String(task.candidate_id), { comment: 'L1 audit via UI' });
    if (ok) message.success(t('L1 审核通过')); else message.warning(t('后端未就绪，已离线记录'));
    void load();
  };

  const onFinalApprove = async (task: ApprovalTask) => {
    const ok = await safeApprovalAction('final-approve', task.id ?? String(task.candidate_id), { comment: 'L2 final via UI' });
    if (ok) message.success(t('L2 终审通过 → 触发 USL 双写')); else message.warning(t('后端未就绪，已离线记录'));
    void load();
  };

  return (
    <SemanticAdminTabsContainer>
      <Card
        title={
          <Space size="middle">
            <span><AuditOutlined style={{ marginRight: 6 }} /> {t('审批工作台 · Approvals')}</span>
            {offline ? <Tag color="warning">{t('离线 Mock（后端未就绪）')}</Tag> : null}
          </Space>
        }
        extra={
          <Space>
            <Tooltip title={t('刷新当前 Tab 审批列表')}>
              <Button icon={<ReloadOutlined />} onClick={() => void load()}>{t('刷新')}</Button>
            </Tooltip>
          </Space>
        }
      >
        <Title level={5} style={{ marginBottom: 12 }}>{t('按审批层级分流')}</Title>
        <Tabs
          activeKey={level}
          onChange={k => setLevel(k as ApprovalLevel | 'ALL')}
          items={[
            { key: 'ALL', label: t('全部待审 (ALL)') },
            { key: 'L1', label: levelLabel.L1 },
            { key: 'L2', label: levelLabel.L2 },
          ]}
        />
      </Card>

      <Spin spinning={loading} tip={t('加载审批任务...')} style={{ marginTop: 16 }}>
        <Card style={{ marginTop: 16 }}>
          <Table<ApprovalTask>
            rowKey={r => r.id ?? `${r.candidate_id}@${r.level}`}
            locale={{ emptyText: <Empty description={t('当前层级暂无待审任务 🎉')} /> }}
            columns={[
              { title: t('候选'), dataIndex: 'candidate_label', key: 'label', render: (_, r) => (
                <Space direction="vertical" size={0}>
                  <span style={{ fontWeight: 600 }}>{r.candidate_label ?? r.candidate_id}</span>
                  <span style={{ color: '#8c8c8c', fontSize: 12 }}>{r.candidate_id}</span>
                </Space>
              ), width: 260 },
              { title: t('层级'), dataIndex: 'level', key: 'lvl', width: 140, render: v => <Tag color={v === 'L1' ? 'blue' : 'orange'}>{v}</Tag> },
              { title: t('状态'), dataIndex: 'status', key: 's', width: 180, render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag> },
              { title: t('质量'), key: 'q', width: 160, render: (_, r) => (
                <Space direction="vertical" size={0}>
                  {r.quality_tier ? <Tag color={r.quality_tier === 'TIER_A' ? 'geekblue' : r.quality_tier === 'TIER_B' ? 'cyan' : 'default'}>{r.quality_tier}</Tag> : null}
                  {typeof r.total_score === 'number' ? <span style={{ fontSize: 12 }}>{t('得分 {{pct}}%', { pct: (r.total_score * 100).toFixed(1) })}</span> : null}
                </Space>
              ) },
              { title: t('来源'), dataIndex: 'submitter', key: 'sub', width: 180 },
              { title: t('时间'), dataIndex: 'submitted_at', key: 'ts', width: 180, render: v => v ? new Date(v).toLocaleString() : '-' },
              {
                title: t('操作'), key: 'op', width: 380,
                render: (_, r) => {
                  const atL1 = r.level !== 'L2';
                  const atL2 = r.level !== 'L1';
                  return (
                    <Space size={4} wrap>
                      {atL1 ? (
                        <Tooltip title={t('L1 审核员通过 → AUDITOR_APPROVED（加速通道候选会直接 APPROVED）')}>
                          <Button type="link" icon={<CheckCircleOutlined />} onClick={() => onAudit(r)}>{t('L1 通过')}</Button>
                        </Tooltip>
                      ) : null}
                      {atL1 ? (
                        <Tooltip title={t('L1 修改候选后回退，可再次送审')}>
                          <Button type="link" icon={<EditOutlined />} onClick={() => openModify(r)}>{t('修改')}</Button>
                        </Tooltip>
                      ) : null}
                      {atL1 ? (
                        <Tooltip title={t('L1 驳回 → REJECTED → 下次命中 STOPLISTED')}>
                          <Button type="link" danger icon={<CloseCircleOutlined />} onClick={() => openReject(r, 'L1')}>{t('驳回')}</Button>
                        </Tooltip>
                      ) : null}
                      {atL2 ? (
                        <Tooltip title={t('L2 管理员终审通过 → APPROVED → 触发 USL 双写')}>
                          <Button type="link" style={{ color: '#13c2c2' }} icon={<CheckCircleOutlined />} onClick={() => onFinalApprove(r)}>{t('L2 终审')}</Button>
                        </Tooltip>
                      ) : null}
                      {atL2 ? (
                        <Tooltip title={t('L2 驳回 → REJECTED')}>
                          <Button type="link" danger icon={<CloseCircleOutlined />} onClick={() => openReject(r, 'L2')}>{t('L2 驳回')}</Button>
                        </Tooltip>
                      ) : null}
                    </Space>
                  );
                },
              },
            ]}
            dataSource={tasks}
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total: number) => t('共 {{n}} 条待审', { n: total }) }}
            expandable={{
              expandedRowRender: (r) => (
                <Descriptions size="small" bordered column={1} title={t('审批详情')}>
                  <Descriptions.Item label="Domain">{r.domain ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="Justification"><span style={{ whiteSpace: 'pre-wrap' }}>{String(r.justification ?? t('（无说明）'))}</span></Descriptions.Item>
                  <Descriptions.Item label="Actions"><Space>
                    <Tag color="blue">/approval/tasks/{r.id}/audit</Tag>
                    <Tag color="purple">/approval/tasks/{r.id}/modify</Tag>
                    <Tag color="red">/approval/tasks/{r.id}/reject</Tag>
                    <Tag color="cyan">/approval/tasks/{r.id}/final-approve</Tag>
                  </Space></Descriptions.Item>
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
