import React, { useCallback, useEffect, useState } from 'react';
import {
  Row, Col, Select, InputNumber, Input, Button, Space,
  message, Modal, Form, Tabs, Drawer, Tag,
} from 'antd';
import type { CandidateFilters } from '../store/useSemanticAdminStore';
import {
  ReloadOutlined, ClearOutlined, CheckOutlined, CloseOutlined,
  RadarChartOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import CandidatesTable from '../components/CandidatesTable';
import QualityRadarPanel from '../components/QualityRadarPanel';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';
import { SEMANTIC_ADMIN_TAB_ITEMS, TOP_TAB_TO_PATH } from '../constants';
import { useAuthStore } from '@/modules/shared/stores/authStore';
import type { Candidate } from '../services/pipelineApi';
import {
  listCandidates, approveCandidate, rejectCandidate, deleteCandidate,
} from '../services/pipelineApi';

const SEMANTIC_TYPES = ['对象类型', '关系类型', '属性', '动作类型', '过程类型', '规则类型'];
const STATUSES: Array<Candidate['status']> = [
  'new', 'gated', 'approved', 'rejected', 'written',
  'auditor_approved', 'admin_pending', 'written_back', 'stoplisted',
];

interface ReviewFormData {
  reviewer: string;
  comment?: string;
}

const CandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const { canWrite } = useUslPermissions();
  const authUser = useAuthStore((s) => s.user);
  const candidateFilters = useSemanticAdminStore((s) => s.candidateFilters);
  const setCF = useSemanticAdminStore((s) => s.setCandidateFilters);
  const resetCF = useSemanticAdminStore((s) => s.resetCandidateFilters);
  const selectedIds = useSemanticAdminStore((s) => s.selectedCandidateIds);
  const setAllSelected = useSemanticAdminStore((s) => s.setAllCandidateSelected);
  const clearSelected = useSemanticAdminStore((s) => s.clearCandidateSelected);

  const [data, setData] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [bulk, setBulk] = useState(false);
  const [reviewModal, setReviewModal] = useState<{
    open: boolean;
    mode: 'approve' | 'reject';
    level: 1 | 2;
    candidate?: Candidate;
  }>({ open: false, mode: 'approve', level: 1 });
  const [reviewForm] = Form.useForm<ReviewFormData>();
  const [submitting, setSubmitting] = useState(false);
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await listCandidates({
        pipeline_run_id: candidateFilters.pipeline_run_id,
        domain_id: candidateFilters.domain_id,
        status: (candidateFilters.status as Candidate['status']) || undefined,
        semantic_type: candidateFilters.semantic_type || undefined,
        min_confidence: candidateFilters.min_confidence,
        keyword: candidateFilters.keyword || undefined,
        page: candidateFilters.page,
        page_size: candidateFilters.page_size,
      });
      setData(resp.items || []);
      setTotal(resp.total ?? 0);
    } catch (e) {
      message.error((e as Error).message || 'Failed to load candidates');
      setData([]); setTotal(0);
    } finally { setLoading(false); }
  }, [candidateFilters]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchData(); }, [fetchData]);

  const onFilterChange = (patch: Partial<CandidateFilters>) => {
    setCF({ ...patch, page: 1 });
  };

  const openReview = (mode: 'approve' | 'reject', level: 1 | 2, c?: Candidate) => {
    reviewForm.setFieldsValue({ reviewer: authUser?.username ?? '', comment: '' });
    setBulk(!c);
    setReviewModal({ open: true, mode, level, candidate: c });
  };

  const submitReview = async () => {
    const values = await reviewForm.validateFields();
    setSubmitting(true);
    try {
      const payload = { reviewer: values.reviewer, comment: values.comment, level: reviewModal.level };
      if (bulk) {
        let ok = 0;
        const ids = selectedIds.slice();
        for (const id of ids) {
          try {
            if (reviewModal.mode === 'approve') {
              await approveCandidate(id, payload);
            } else {
              await rejectCandidate(id, payload);
            }
            ok += 1;
          } catch { /* skip */ }
        }
        message.success(`${reviewModal.mode === 'approve' ? 'Approved' : 'Rejected'} ${ok}/${ids.length}`);
      } else if (reviewModal.candidate) {
        if (reviewModal.mode === 'approve') {
          await approveCandidate(reviewModal.candidate.id, payload);
        } else {
          await rejectCandidate(reviewModal.candidate.id, payload);
        }
        message.success(`${reviewModal.mode === 'approve' ? 'Approved' : 'Rejected'} successfully`);
      }
      setReviewModal({ open: false, mode: 'approve', level: 1 });
      clearSelected();
      fetchData();
    } catch (e) {
      message.error((e as Error).message || 'Operation failed');
    } finally { setSubmitting(false); }
  };

  const onDelete = async (c: Candidate) => {
    try { await deleteCandidate(c.id); message.success('Deleted'); fetchData(); }
    catch (e) { message.error((e as Error).message || 'Delete failed'); }
  };

  return (
    <div style={{ padding: 16 }}>
      <Tabs
        activeKey="candidates"
        onChange={(k) => { const p = TOP_TAB_TO_PATH[k as keyof typeof TOP_TAB_TO_PATH]; if (p) { navigate(p); } }}
        items={SEMANTIC_ADMIN_TAB_ITEMS}
        style={{ marginBottom: 8 }}
      />
      <Row gutter={[12, 12]} align="middle" style={{ marginBottom: 12 }}>
        <Col span={5}>
          <Select mode="multiple" allowClear style={{ width: '100%' }} placeholder="Semantic Type"
            value={candidateFilters.semantic_type ? [candidateFilters.semantic_type] : []}
            maxTagCount="responsive"
            onChange={(v) => onFilterChange({ semantic_type: v.length ? v[0] : '' })}
            options={SEMANTIC_TYPES.map((x) => ({ label: x, value: x }))} />
        </Col>
        <Col span={4}>
          <Select allowClear style={{ width: '100%' }} placeholder="Status"
            value={candidateFilters.status || undefined}
            onChange={(v) => onFilterChange({ status: v ?? '' })}
            options={STATUSES.map((x) => ({ label: x, value: x }))} />
        </Col>
        <Col span={3}>
          <InputNumber style={{ width: '100%' }} min={0} max={1} step={0.05}
            placeholder="Confidence ≥"
            value={candidateFilters.min_confidence}
            onChange={(v) => onFilterChange({ min_confidence: v == null ? undefined : v })} />
        </Col>
        <Col span={5}>
          <Input allowClear placeholder="Keyword (canonical / synonym)"
            value={candidateFilters.keyword || ''}
            onChange={(e) => onFilterChange({ keyword: e.target.value })} />
        </Col>
        <Col span={7} style={{ textAlign: 'right' }}>
          <Space>
            <Button icon={<ClearOutlined />} onClick={() => { resetCF(); fetchData(); }}>Reset</Button>
            <Button type="primary" icon={<ReloadOutlined />} onClick={() => fetchData()}>Refresh</Button>
            <Button type="primary" ghost icon={<CheckOutlined />}
              disabled={!canWrite || selectedIds.length === 0}
              onClick={() => openReview('approve', 1)}>
              Approve ({selectedIds.length})
            </Button>
            <Button danger ghost icon={<CloseOutlined />}
              disabled={!canWrite || selectedIds.length === 0}
              onClick={() => openReview('reject', 1)}>
              Reject ({selectedIds.length})
            </Button>
          </Space>
        </Col>
      </Row>
      <CandidatesTable
        data={data} loading={loading} total={total}
        page={candidateFilters.page} pageSize={candidateFilters.page_size}
        selectedIds={selectedIds} canWrite={canWrite}
        onPageChange={(page, page_size) => setCF({ page, page_size })}
        onSelectionChange={setAllSelected}
        onApproveL1={(c) => openReview('approve', 1, c)}
        onApproveL2={(c) => openReview('approve', 2, c)}
        onReject={(c) => openReview('reject', 1, c)}
        onDelete={onDelete}
        onRowClick={(c) => setActiveCandidate(c)}
      />
      <Modal
        open={reviewModal.open}
        title={`${bulk ? `Bulk ${reviewModal.mode} (${selectedIds.length})` : `${reviewModal.mode} L${reviewModal.level} — ${reviewModal.candidate?.canonical ?? ''}`}`}
        onCancel={() => setReviewModal({ open: false, mode: 'approve', level: 1 })}
        onOk={submitReview}
        okText={reviewModal.mode === 'approve' ? 'Approve' : 'Reject'}
        okButtonProps={reviewModal.mode === 'reject' ? { danger: true } : {}}
        cancelText="Cancel" confirmLoading={submitting} destroyOnClose
      >
        <Form form={reviewForm} layout="vertical">
          <Form.Item label="Reviewer" name="reviewer"
            rules={[{ required: true, message: 'Please enter reviewer name' }]}>
            <Input placeholder="e.g. admin" />
          </Form.Item>
          <Form.Item label="Comment" name="comment">
            <Input.TextArea rows={3} placeholder="Optional comment..." />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={
          <Space>
            <RadarChartOutlined style={{ color: '#1677ff' }} />
            <span>质量雷达 · 16 子指标</span>
            {activeCandidate ? (
              <>
                <Tag color="blue">{activeCandidate.semantic_type}</Tag>
                <Tag>{activeCandidate.status}</Tag>
                <strong>{activeCandidate.canonical}</strong>
              </>
            ) : null}
          </Space>
        }
        placement="right"
        width={640}
        open={!!activeCandidate}
        onClose={() => setActiveCandidate(null)}
        destroyOnClose
      >
        <QualityRadarPanel
          candidate={activeCandidate}
          candidateId={activeCandidate?.id}
          inlineReport={(activeCandidate as any)?.quality_report}
          canWrite={canWrite}
          onModified={() => void fetchData()}
        />
      </Drawer>
    </div>
  );
};

export default CandidatesPage;
