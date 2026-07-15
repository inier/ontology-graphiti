/**
 * Iter 2 占位页：本体学习（OL）流水线
 * 内容：AntD Result "success" 风格，"Coming soon in Iteration 2 · L1-L2 Concept + Candidate Store"
 *       再配以 Empty 插图 + 规划表格做低饱和预览
 */
import React from 'react';
import { Result, Empty, Table, Tag, Space, Typography, Progress } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';

const { Text, Paragraph } = Typography;

interface PipelineStagePreview {
  key: string;
  stage: string;
  description: string;
  progress: number;
  planned: string;
}

const PREVIEW_COLUMNS: ColumnsType<PipelineStagePreview> = [
  {
    title: '阶段',
    dataIndex: 'stage',
    width: 200,
    render: (t: string, r) => (
      <Space>
        <Tag color={r.progress >= 100 ? 'green' : 'default'}>{t}</Tag>
      </Space>
    ),
  },
  {
    title: '说明',
    dataIndex: 'description',
    render: (v: string) => <Text type="secondary">{v}</Text>,
  },
  {
    title: '进度（Iter 2 交付）',
    dataIndex: 'progress',
    width: 240,
    render: (n: number) => <Progress percent={n} size="small" status={n >= 100 ? 'success' : 'active'} />,
  },
  {
    title: '计划里程碑',
    dataIndex: 'planned',
    width: 160,
    render: (v: string) => <Tag color="geekblue">{v}</Tag>,
  },
];

const PREVIEW_DATA: PipelineStagePreview[] = [
  {
    key: 'L1',
    stage: 'L1 术语抽取',
    description: '分词 + 查 USL 表 (B 树同义词匹配) 直接对齐，未命中的 token 留作 L2 聚类种子',
    progress: 0,
    planned: 'Iter 2 Week 1',
  },
  {
    key: 'L2',
    stage: 'L2 概念聚合',
    description: 'BGE-M3 embedding 余弦聚类 + 簇中心生成 canonical / semantic_type (LLM)',
    progress: 0,
    planned: 'Iter 2 Week 2',
  },
  {
    key: 'L3',
    stage: 'L3 层级草稿',
    description: 'is_a / part_of 草稿边，LLM 层级 Prompt + USL 对齐',
    progress: 0,
    planned: 'Iter 2 Week 3',
  },
  {
    key: 'L4-6',
    stage: 'L4~L6 关系/动作/公理',
    description: '关系抽取 + 动作类型 + 规则/公理归纳（可选，默认关闭）',
    progress: 0,
    planned: 'Iter 2 Week 4',
  },
];

export function PipelineComingSoon() {
  return (
    <SemanticAdminTabsContainer>
      <Result
        icon={<ThunderboltOutlined />}
        status="info"
        title="Coming soon in Iteration 2"
        subTitle="L1-L2 Concept Extraction + Candidate Store（L1 术语 / L2 概念聚类 / 6 层流水线监控）"
        extra={
          <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Empty
                description={
                  <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    OL 流水线执行视图将在这里呈现：文件上传 → 6 层进度 → 候选 Tab 跳转。
                  </Paragraph>
                }
              />
            </div>
            <Table
              size="small"
              columns={PREVIEW_COLUMNS}
              dataSource={PREVIEW_DATA}
              pagination={false}
              bordered
              title={() => (
                <Text type="secondary">
                  预览：Iter 2 将交付的 4 个阶段（里程碑规划，非真实数据）
                </Text>
              )}
            />
          </Space>
        }
      />
    </SemanticAdminTabsContainer>
  );
}
