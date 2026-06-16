/**
 * 评估管理页面 - 评估仪表盘 + 基准测试
 */
import React, { useEffect } from 'react';
import { Card, Button, Space, Typography, Statistic, Row, Col, Tag, Divider, Spin, Empty, Progress } from 'antd';
import {
  PlayCircleOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  ApiOutlined,
  BranchesOutlined,
} from '@ant-design/icons';
import { OverlaySpin } from '@/modules/shared/components/OverlaySpin';
import { useNLQueryStore } from '../stores/nlQueryStore';

const { Text, Title } = Typography;

export function EvaluationPage() {
  const {
    evalLoading,
    evalResult,
    evalError,
    executeEvaluation,
    auditStats,
    fetchAuditStats,
  } = useNLQueryStore();

  useEffect(() => {
    fetchAuditStats();
  }, [fetchAuditStats]);

  const renderMetrics = (metrics: Record<string, number>, title: string) => {
    const entries = Object.entries(metrics);
    if (entries.length === 0) return null;

    return (
      <Card size="small" title={title} style={{ marginBottom: 12 }}>
        <Row gutter={[16, 12]}>
          {entries.map(([key, value]) => (
            <Col span={8} key={key}>
              <Statistic
                title={key.toUpperCase()}
                value={value * 100}
                precision={1}
                suffix="%"
                styles={{
                  content: {
                    color: value > 0.7 ? '#52c41a' : value > 0.4 ? '#faad14' : '#ff4d4f',
                    fontSize: 20,
                  },
                }}
              />
            </Col>
          ))}
        </Row>
      </Card>
    );
  };

  const renderPillarUsage = (usage: Record<string, number>) => {
    const total = Object.values(usage).reduce((a, b) => a + b, 0) || 1;
    const pillarConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
      bm25: { icon: <SearchOutlined />, color: '#1890ff', label: 'BM25' },
      vector: { icon: <ApiOutlined />, color: '#52c41a', label: 'Vector' },
      graph: { icon: <BranchesOutlined />, color: '#fa8c16', label: 'Graph' },
    };

    return (
      <Card size="small" title="支柱使用分布" style={{ marginBottom: 12 }}>
        <Space orientation="vertical" style={{ width: '100%' }} size={8}>
          {Object.entries(usage).map(([pillar, count]) => {
            const config = pillarConfig[pillar] || { icon: null, color: '#999', label: pillar };
            const pct = Math.round((count / total) * 100);
            return (
              <div key={pillar}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <Space size={4}>
                    <span style={{ color: config.color }}>{config.icon}</span>
                    <Text style={{ fontSize: 12 }}>{config.label}</Text>
                  </Space>
                  <Text style={{ fontSize: 12, color: '#999' }}>{count} 次 ({pct}%)</Text>
                </div>
                <Progress percent={pct} showInfo={false} strokeColor={config.color} size="small" />
              </div>
            );
          })}
        </Space>
      </Card>
    );
  };

  return (
    <div style={{ padding: 20, maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <TrophyOutlined /> 查询服务评估
        </Title>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={executeEvaluation}
          loading={evalLoading}
        >
          运行基准测试
        </Button>
      </div>

      {/* 错误提示 */}
      {evalError && (
        <Card size="small" style={{ marginBottom: 12, borderColor: '#ff4d4f' }}>
          <Text type="danger">{evalError}</Text>
        </Card>
      )}

      {/* 加载中 - overlay 遮罩，不占空间 */}
      {evalLoading && (
        <OverlaySpin spinning tip="正在运行基准测试..." />
      )}

      {/* 评估结果 */}
      {evalResult && !evalLoading && (
        <>
          {/* 概览 */}
          <Card size="small" style={{ marginBottom: 12 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="测试用例"
                  value={evalResult.total_cases}
                  prefix={<CheckCircleOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="P50 延迟"
                  value={evalResult.latency_p50_ms}
                  suffix="ms"
                  prefix={<ClockCircleOutlined />}
                  styles={{ content: { color: evalResult.latency_p50_ms < 1000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="P95 延迟"
                  value={evalResult.latency_p95_ms}
                  suffix="ms"
                  prefix={<ThunderboltOutlined />}
                  styles={{ content: { color: evalResult.latency_p95_ms < 3000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="数据集"
                  value={evalResult.dataset_name || '默认'}
                />
              </Col>
            </Row>
          </Card>

          {/* 检索指标 */}
          {renderMetrics(evalResult.retrieval_metrics, '检索质量指标 (MRR / NDCG / Recall)')}

          {/* QA 指标 */}
          {renderMetrics(evalResult.qa_metrics, '问答质量指标 (EM / F1 / Faithfulness)')}

          {/* 支柱使用 */}
          {renderPillarUsage(evalResult.pillar_usage)}
        </>
      )}

      {/* 无结果 */}
      {!evalResult && !evalLoading && !evalError && (
        <Empty
          description='点击"运行基准测试"开始评估查询服务质量'
          style={{ padding: 40 }}
        />
      )}

      {/* 审计统计 */}
      {auditStats && (
        <>
          <Divider>历史统计</Divider>
          <Card size="small">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总查询次数" value={auditStats.total_queries} />
              </Col>
              <Col span={8}>
                <Statistic
                  title="平均耗时"
                  value={auditStats.avg_time_ms}
                  suffix="ms"
                  styles={{ content: { color: auditStats.avg_time_ms < 1000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={8}>
                <Space orientation="vertical" size={2}>
                  <Text type="secondary" style={{ fontSize: 12 }}>支柱使用</Text>
                  {Object.entries(auditStats.pillar_usage).map(([p, c]) => (
                    <Tag key={p} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'} style={{ fontSize: 11 }}>
                      {p}: {c}
                    </Tag>
                  ))}
                </Space>
              </Col>
            </Row>
          </Card>
        </>
      )}
    </div>
  );
}
