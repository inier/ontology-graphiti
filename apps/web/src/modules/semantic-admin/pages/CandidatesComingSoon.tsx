/**
 * Iter 3 占位页：候选审核台
 * 内容：AntD Result status="warning"
 *       + 进度条式文案"3 关质量闸 + 2 级审批"的流程预览
 *       + 低饱和 Candidate 列表骨架（灰字/灰边，不请求数据）
 */
import React, { useMemo } from 'react';
import {
  Result,
  Steps,
  Table,
  Tag,
  Space,
  Typography,
  Card,
  Divider,
  Tooltip,
} from 'antd';
import {
  SafetyCertificateOutlined,
  CheckCircleTwoTone,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface CandidatePreview {
  key: string;
  canonical: string;
  en: string;
  semanticType: string;
  gateScore: number;
  origin: string;
  status: string;
}

export function CandidatesComingSoon() {
  const { t } = useI18n();

  const previewColumns: ColumnsType<CandidatePreview> = useMemo(() => [
    {
      title: t('规范词'),
      dataIndex: 'canonical',
      width: 140,
      render: (v: string, r) => (
        <Space>
          <Text strong>{v}</Text>
          <Tag color="blue">{r.semanticType}</Tag>
        </Space>
      ),
    },
    { title: t('英文映射'), dataIndex: 'en', width: 140, render: (v: string) => <Text code>{v}</Text> },
    {
      title: t('来源'),
      dataIndex: 'origin',
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: t('质量闸总分'),
      dataIndex: 'gateScore',
      width: 180,
      render: (n: number) => (
        <Space>
          <Text>{n.toFixed(2)}</Text>
          {n >= 0.8 ? (
            <Tooltip title={t('≥ 0.8，可直接进入 1 级审批')}>
              <CheckCircleTwoTone twoToneColor="#52c41a" />
            </Tooltip>
          ) : (
            <Tooltip title={t('< 0.8，需 schema_auditor 修改后重评分')}>
              <ClockCircleOutlined style={{ color: '#faad14' }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: t('状态预览'),
      dataIndex: 'status',
      width: 160,
      render: (v: string) => <Tag color="default">{v}</Tag>,
    },
  ], [t]);

  const previewData: CandidatePreview[] = useMemo(() => [
    {
      key: '1',
      canonical: t('五虎将'),
      en: 'FiveTigerGenerals',
      semanticType: t('对象类型'),
      gateScore: 0.87,
      origin: 'LLM(L2)',
      status: 'PENDING_AUDIT_1',
    },
    {
      key: '2',
      canonical: t('主公'),
      en: 'Lord',
      semanticType: t('对象类型'),
      gateScore: 0.78,
      origin: t('USL 对齐'),
      status: 'GATE_WARN_REVIEW',
    },
    {
      key: '3',
      canonical: t('三顾茅庐'),
      en: 'VisitThatchedCottage',
      semanticType: t('过程类型'),
      gateScore: 0.72,
      origin: 'LLM(L4)',
      status: 'AUDITOR_MODIFY',
    },
  ], [t]);

  return (
    <SemanticAdminTabsContainer>
      <Result
        icon={<SafetyCertificateOutlined />}
        status="warning"
        title="Coming soon in Iteration 3"
        subTitle={t('候选审核台 · 3 关质量闸 (G1/G2/G3) + 2 级审批流 (schema_auditor → final_approver)')}
      />
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <Card size="small" title={t('3 关质量闸 + 2 级审批流程（预览）')}>
          <Steps
            direction="vertical"
            size="small"
            items={[
              {
                title: t('G1 · 基础格式闸'),
                description:
                  t('canonical 非空、en PascalCase 合法、semantic_type ∈ 6 种枚举。失败直接打回 Draft。'),
                status: 'process',
              },
              {
                title: t('G2 · 一致性闸'),
                description:
                  t('USL Disjoint 不相交检查、is_a 无环检查、(可选) LLM Judge 语义矛盾检查。不通过 → AUDITOR_MODIFY。'),
                status: 'wait',
              },
              {
                title: t('G3 · 信号闸'),
                description:
                  t('聚类置信度 / USL 对齐置信度 / 文档证据覆盖率 / (反向) 新颖度，综合加权 ≥0.8 直接过。'),
                status: 'wait',
              },
              {
                title: t('审批 1 · schema_auditor'),
                description:
                  t('可编辑 canonical/semantic_type/同义词，附 comment；触发 G2/G3 重新评分；REJECT 时写 USL stoplist。'),
                status: 'wait',
              },
              {
                title: t('审批 2 · final_approver'),
                description:
                  t('最终批准（多人角色禁止同一人终审）；APPROVED 走写回 USL + Ontology TBox Hook；REJECT 写回 stoplist。'),
                status: 'wait',
              },
            ]}
          />
        </Card>
        <Divider />
        <Table
          size="small"
          columns={previewColumns}
          dataSource={previewData}
          pagination={false}
          bordered
          title={() => (
            <Text type="secondary">
              {t('候选列表预览（Iter 3 真实数据将来自 Candidate Store SQLite + Neo4j _schema_graph）')}
            </Text>
          )}
        />
      </div>
    </SemanticAdminTabsContainer>
  );
}
