/**
 * ChangeProposalCard 组件 —— Change Proposal 详情卡片 + 影响分析可视化（FR-037 / T429）
 *
 * 卡片头部：标题 + 状态徽章 + proposed_by + created_at
 * 卡片主体：Tabs（Details / Changes / Impact Analysis）
 *   - Details: description, estimated_benefit, estimated_cost
 *   - Changes: JSON Patch 列表，每条 op 用不同颜色 badge
 *   - Impact Analysis: 3 个 KPI + Migration Cost 等级条 + Risk Level 等级条 + Breaking Changes
 * 卡片底部 Actions：Approve / Reject（仅 draft/submitted）+ View Source JSON
 *
 * 对应后端：
 *   GET  /api/ontology/goals/proposals/{id}
 *   POST /api/ontology/goals/proposals/{id}/review
 *   GET  /api/ontology/goals/impacts/{id}    （可选：拉取 ImpactAnalysis）
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Tabs, Tag, Space, Button, Modal, Input, Alert, Drawer, Empty, Spin, Statistic, message, Row, Col, Typography,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  CheckOutlined, CloseOutlined, FileTextOutlined, AlertOutlined, RiseOutlined,
} from '@ant-design/icons';
import { goalApi, type ChangeProposal, type ImpactAnalysis, type ProposalStatus } from '../services/goalApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface JsonPatch {
  op: string;
  path: string;
  value?: unknown;
  from?: string;
}

const STATUS_META: Record<ProposalStatus, { color: string; label: string }> = {
  draft: { color: 'default', label: 'draft' },
  submitted: { color: 'blue', label: 'submitted' },
  'under-review': { color: 'gold', label: 'under-review' },
  approved: { color: 'green', label: 'approved' },
  rejected: { color: 'red', label: 'rejected' },
  implemented: { color: 'purple', label: 'implemented' },
};

const OP_META: Record<string, { color: string; label: string }> = {
  add: { color: 'green', label: 'add' },
  remove: { color: 'red', label: 'remove' },
  replace: { color: 'blue', label: 'replace' },
  move: { color: 'purple', label: 'move' },
  copy: { color: 'cyan', label: 'copy' },
  test: { color: 'orange', label: 'test' },
};

const COST_COLOR: Record<string, string> = {
  low: '#52c41a',
  medium: '#faad14',
  high: '#ff4d4f',
};

const RISK_COLOR: Record<string, string> = {
  low: '#52c41a',
  medium: '#faad14',
  high: '#ff7a45',
  critical: '#ff4d4f',
};

export interface ChangeProposalCardProps {
  proposalId: string;
  onReview?: (decision: 'approve' | 'reject') => void;
}

export function ChangeProposalCard({ proposalId, onReview }: ChangeProposalCardProps) {
  const { t } = useI18n('ontology');
  const [proposal, setProposal] = useState<ChangeProposal | null>(null);
  const [impact, setImpact] = useState<ImpactAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [decision, setDecision] = useState<'approve' | 'reject'>('approve');
  const [reviewForm] = Form.useForm<{ reviewer_notes?: string }>();
  const [reviewing, setReviewing] = useState(false);
  const [jsonOpen, setJsonOpen] = useState(false);

  const fetchProposal = useCallback(async () => {
    setLoading(true);
    try {
      const p = await goalApi.getProposal(proposalId);
      setProposal(p);
      if (p.impact_analysis_id) {
        try {
          const imp = await goalApi.getImpact(p.impact_analysis_id);
          setImpact(imp);
        } catch {
          setImpact(null);
        }
      } else {
        setImpact(null);
      }
    } catch (e) {
      message.error(t('changeProposalCard.loadFailed', { msg: (e as Error).message }));
    } finally {
      setLoading(false);
    }
  }, [proposalId, t]);

  useEffect(() => { void fetchProposal(); }, [fetchProposal]);

  const openReview = useCallback((d: 'approve' | 'reject') => {
    setDecision(d);
    reviewForm.resetFields();
    setReviewOpen(true);
  }, [reviewForm]);

  const handleReview = useCallback(async () => {
    try {
      const v = await reviewForm.validateFields();
      setReviewing(true);
      await goalApi.reviewProposal(proposalId, {
        decision,
        reviewer_notes: v.reviewer_notes || '',
      });
      message.success(decision === 'approve' ? t('changeProposalCard.approved') : t('changeProposalCard.rejected'));
      setReviewOpen(false);
      onReview?.(decision);
      void fetchProposal();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(t('changeProposalCard.operationFailed', { msg: (e as Error).message }));
    } finally {
      setReviewing(false);
    }
  }, [reviewForm, decision, proposalId, onReview, fetchProposal, t]);

  const changes: JsonPatch[] = useMemo(() => {
    if (!proposal?.changes) return [];
    return proposal.changes as unknown as JsonPatch[];
  }, [proposal]);

  const canReview = useMemo(() => {
    if (!proposal) return false;
    return proposal.status === 'draft' || proposal.status === 'submitted';
  }, [proposal]);

  if (!proposal) {
    return (
      <Card size="small">
        <Spin spinning={loading}>
          <Empty description={t('changeProposalCard.loading')} />
        </Spin>
      </Card>
    );
  }

  const statusMeta = STATUS_META[proposal.status] || STATUS_META.draft;
  const costColor = impact ? (COST_COLOR[impact.estimated_migration_cost] || '#999') : '#999';
  const riskColor = impact ? (RISK_COLOR[impact.risk_level] || '#999') : '#999';

  return (
    <div data-testid="change-proposal-card">
      <Card
        size="small"
        title={
          <Space>
            <FileTextOutlined />
            <Text strong>{proposal.title}</Text>
            <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {proposal.proposed_by} · {new Date(proposal.created_at).toLocaleString()}
            </Text>
          </Space>
        }
      >
        <Tabs
          defaultActiveKey="details"
          items={[
            {
              key: 'details',
              label: t('changeProposalCard.tabDetails'),
              children: (
                <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                  <div>
                    <Text type="secondary">{t('changeProposalCard.description')}</Text>
                    <div style={{ marginTop: 4 }}>
                      {proposal.description || <Text type="secondary">-</Text>}
                    </div>
                  </div>
                  <div>
                    <Text type="secondary">{t('changeProposalCard.estimatedBenefit')}</Text>
                    <div style={{ marginTop: 4 }}>
                      {proposal.estimated_benefit || <Text type="secondary">-</Text>}
                    </div>
                  </div>
                  <div>
                    <Text type="secondary">{t('changeProposalCard.estimatedCost')}</Text>
                    <div style={{ marginTop: 4 }}>
                      {proposal.estimated_cost || <Text type="secondary">-</Text>}
                    </div>
                  </div>
                  {proposal.reviewed_at && (
                    <Alert
                      type="info"
                      showIcon
                      title={t('changeProposalCard.reviewedAt', { time: new Date(proposal.reviewed_at).toLocaleString() })}
                      description={proposal.reviewer_notes || t('changeProposalCard.noReviewerNotes')}
                    />
                  )}
                </Space>
              ),
            },
            {
              key: 'changes',
              label: t('changeProposalCard.tabChanges', { count: changes.length }),
              children: changes.length === 0 ? (
                <Empty description={t('changeProposalCard.noChanges')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Space orientation="vertical" style={{ width: '100%' }} size={4}>
                  {changes.map((c, i) => {
                    const meta = OP_META[c.op] || { color: 'default', label: c.op };
                    return (
                      <Card key={i} size="small" style={{ background: '#fafafa' }}>
                        <Space wrap>
                          <Tag color={meta.color}>{meta.label}</Tag>
                          <Text code style={{ fontSize: 12 }}>{c.path}</Text>
                          {c.value !== undefined && (
                            <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                              → {JSON.stringify(c.value)}
                            </Text>
                          )}
                          {c.from && (
                            <Text type="secondary" style={{ fontSize: 12 }}>{t('changeProposalCard.fromPrefix')} {c.from}</Text>
                          )}
                        </Space>
                      </Card>
                    );
                  })}
                </Space>
              ),
            },
            {
              key: 'impact',
              label: t('changeProposalCard.tabImpact'),
              children: !impact ? (
                <Empty description={t('changeProposalCard.noImpactData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                  <Row gutter={12}>
                    <Col xs={24} sm={8}>
                      <Card size="small">
                        <Statistic
                          title={t('changeProposalCard.affectedObjectTypes')}
                          value={impact.affected_object_types.length}
                          prefix={<AlertOutlined />}
                        />
                      </Card>
                    </Col>
                    <Col xs={24} sm={8}>
                      <Card size="small">
                        <Statistic
                          title={t('changeProposalCard.affectedActionTypes')}
                          value={impact.affected_action_types.length}
                        />
                      </Card>
                    </Col>
                    <Col xs={24} sm={8}>
                      <Card size="small">
                        <Statistic
                          title={t('changeProposalCard.affectedInstances')}
                          value={impact.affected_instances_count}
                          prefix={<RiseOutlined />}
                        />
                      </Card>
                    </Col>
                  </Row>

                  <Card size="small" title={t('changeProposalCard.migrationCost')}>
                    <Space>
                      <Tag color={impact.estimated_migration_cost === 'low' ? 'green' : impact.estimated_migration_cost === 'medium' ? 'orange' : 'red'}>
                        {impact.estimated_migration_cost.toUpperCase()}
                      </Tag>
                      <div style={{ flex: 1, minWidth: 200, height: 8, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: impact.estimated_migration_cost === 'low' ? '33%' : impact.estimated_migration_cost === 'medium' ? '66%' : '100%',
                            height: '100%',
                            background: costColor,
                            transition: 'width 0.3s',
                          }}
                        />
                      </div>
                    </Space>
                  </Card>

                  <Card size="small" title={t('changeProposalCard.riskLevel')}>
                    <Space>
                      <Tag color={impact.risk_level === 'low' ? 'green' : impact.risk_level === 'medium' ? 'orange' : impact.risk_level === 'high' ? 'volcano' : 'red'}>
                        {impact.risk_level.toUpperCase()}
                      </Tag>
                      <div style={{ flex: 1, minWidth: 200, height: 8, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: impact.risk_level === 'low' ? '25%' : impact.risk_level === 'medium' ? '50%' : impact.risk_level === 'high' ? '75%' : '100%',
                            height: '100%',
                            background: riskColor,
                            transition: 'width 0.3s',
                          }}
                        />
                      </div>
                    </Space>
                  </Card>

                  {impact.breaking_changes.length > 0 && (
                    <Card size="small" title={t('changeProposalCard.breakingChangesWithCount', { count: impact.breaking_changes.length })}>
                      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                        {impact.breaking_changes.map((bc, i) => (
                          <Alert key={i} type="error" title={bc} showIcon />
                        ))}
                      </Space>
                    </Card>
                  )}
                </Space>
              ),
            },
          ]}
        />

        <div style={{ marginTop: 12, textAlign: 'right' }} data-testid="proposal-actions">
          <Space>
            <Button size="small" onClick={() => setJsonOpen(true)}>
              {t('changeProposalCard.viewSourceJson')}
            </Button>
            {canReview && (
              <>
                <Button
                  size="small"
                  danger
                  icon={<CloseOutlined />}
                  onClick={() => openReview('reject')}
                >
                  {t('changeProposalCard.rejectBtn')}
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<CheckOutlined />}
                  onClick={() => openReview('approve')}
                >
                  {t('changeProposalCard.approveBtn')}
                </Button>
              </>
            )}
          </Space>
        </div>
      </Card>

      <Modal
        title={decision === 'approve' ? t('changeProposalCard.approveTitle') : t('changeProposalCard.rejectTitle')}
        open={reviewOpen}
        onOk={() => void handleReview()}
        onCancel={() => setReviewOpen(false)}
        confirmLoading={reviewing}
        okText={decision === 'approve' ? t('changeProposalCard.approveOk') : t('changeProposalCard.rejectOk')}
        cancelText={t('changeProposalCard.cancelOk')}
        destroyOnHidden
      >
        <Form form={reviewForm} layout="vertical">
          <Form.Item name="reviewer_notes" label={t('changeProposalCard.reviewerNotesLabel')}>
            <Input.TextArea rows={4} placeholder={t('changeProposalCard.reviewerNotesPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={t('changeProposalCard.sourceJsonTitle')}
        open={jsonOpen}
        onClose={() => setJsonOpen(false)}
        width={560}
      >
        <pre style={{ background: '#fafafa', padding: 12, borderRadius: 4, maxHeight: '100%', overflow: 'auto' }}>
          {JSON.stringify(proposal, null, 2)}
        </pre>
      </Drawer>
    </div>
  );
}

export default ChangeProposalCard;
