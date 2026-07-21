/**
 * Iter 2 占位页：本体学习（OL）流水线
 * 内容：AntD Result "success" 风格，"Coming soon in Iteration 2 · L1-L2 Concept + Candidate Store"
 *       再配以 Empty 插图 + 规划表格做低饱和预览
 */
import React, { useMemo } from 'react';
import { Result, Empty, Table, Tag, Space, Typography, Progress } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Paragraph } = Typography;

interface PipelineStagePreview {
  key: string;
  stage: string;
  description: string;
  progress: number;
  planned: string;
}

export function PipelineComingSoon() {
  const { t } = useI18n();

  const previewColumns: ColumnsType<PipelineStagePreview> = useMemo(() => [
    {
      title: t('阶段'),
      dataIndex: 'stage',
      width: 200,
      render: (stageName: string, r) => (
        <Space>
          <Tag color={r.progress >= 100 ? 'green' : 'default'}>{stageName}</Tag>
        </Space>
      ),
    },
    {
      title: t('说明'),
      dataIndex: 'description',
      render: (v: string) => <Text type="secondary">{v}</Text>,
    },
    {
      title: t('进度（Iter 2 交付）'),
      dataIndex: 'progress',
      width: 240,
      render: (n: number) => <Progress percent={n} size="small" status={n >= 100 ? 'success' : 'active'} />,
    },
    {
      title: t('计划里程碑'),
      dataIndex: 'planned',
      width: 160,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
  ], [t]);

  const previewData: PipelineStagePreview[] = useMemo(() => [
    {
      key: 'L1',
      stage: t('L1 术语抽取'),
      description: t('分词 + 查 USL 表 (B 树同义词匹配) 直接对齐，未命中的 token 留作 L2 聚类种子'),
      progress: 0,
      planned: 'Iter 2 Week 1',
    },
    {
      key: 'L2',
      stage: t('L2 概念聚合'),
      description: t('BGE-M3 embedding 余弦聚类 + 簇中心生成 canonical / semantic_type (LLM)'),
      progress: 0,
      planned: 'Iter 2 Week 2',
    },
    {
      key: 'L3',
      stage: t('L3 层级草稿'),
      description: t('is_a / part_of 草稿边，LLM 层级 Prompt + USL 对齐'),
      progress: 0,
      planned: 'Iter 2 Week 3',
    },
    {
      key: 'L4-6',
      stage: t('L4~L6 关系/动作/公理'),
      description: t('关系抽取 + 动作类型 + 规则/公理归纳（可选，默认关闭）'),
      progress: 0,
      planned: 'Iter 2 Week 4',
    },
  ], [t]);

  return (
    <SemanticAdminTabsContainer>
      <Result
        icon={<ThunderboltOutlined />}
        status="info"
        title="Coming soon in Iteration 2"
        subTitle={t('L1-L2 Concept Extraction + Candidate Store（L1 术语 / L2 概念聚类 / 6 层流水线监控）')}
        extra={
          <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Empty
                description={
                  <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    {t('OL 流水线执行视图将在这里呈现：文件上传 → 6 层进度 → 候选 Tab 跳转。')}
                  </Paragraph>
                }
              />
            </div>
            <Table
              size="small"
              columns={previewColumns}
              dataSource={previewData}
              pagination={false}
              bordered
              title={() => (
                <Text type="secondary">
                  {t('预览：Iter 2 将交付的 4 个阶段（里程碑规划，非真实数据）')}
                </Text>
              )}
            />
          </Space>
        }
      />
    </SemanticAdminTabsContainer>
  );
}
