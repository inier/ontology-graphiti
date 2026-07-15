/**
 * 评估管理页面 - 评估仪表盘 + 基准测试
 */
import React, { useEffect } from 'react';
import { Button, Space, Typography, Statistic, Row, Col, Tag, Divider, Spin, Empty, Progress } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
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
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { useNLQueryStore } from '../stores/nlQueryStore';

const { Text, Title } = Typography;

export function EvaluationPage() {
  const { t } = useI18n('qa');
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
      <Card size="small" title={t('evaluation.pillarUsage')} style={{ marginBottom: 12 }}>
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
                  <Text style={{ fontSize: 12, color: '#999' }}>{t('evaluation.usageCount', { count, pct })}</Text>
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
          <TrophyOutlined /> {t('evaluation.title')}
        </Title>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={executeEvaluation}
          loading={evalLoading}
        >
          {t('evaluation.runBenchmark')}
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
        <OverlaySpin spinning tip={t('evaluation.running')} />
      )}

      {/* 评估结果 */}
      {evalResult && !evalLoading && (
        <>
          {/* 概览 */}
          <Card size="small" style={{ marginBottom: 12 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title={t('evaluation.testCases')}
                  value={evalResult.total_cases}
                  prefix={<CheckCircleOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title={t('evaluation.p50Latency')}
                  value={evalResult.latency_p50_ms}
                  suffix="ms"
                  prefix={<ClockCircleOutlined />}
                  styles={{ content: { color: evalResult.latency_p50_ms < 1000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title={t('evaluation.p95Latency')}
                  value={evalResult.latency_p95_ms}
                  suffix="ms"
                  prefix={<ThunderboltOutlined />}
                  styles={{ content: { color: evalResult.latency_p95_ms < 3000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title={t('evaluation.dataset')}
                  value={evalResult.dataset_name || t('evaluation.defaultDataset')}
                />
              </Col>
            </Row>
          </Card>

          {/* 检索指标 */}
          {renderMetrics(evalResult.retrieval_metrics, t('evaluation.retrievalMetrics'))}

          {/* QA 指标 */}
          {renderMetrics(evalResult.qa_metrics, t('evaluation.qaMetrics'))}

          {/* 支柱使用 */}
          {renderPillarUsage(evalResult.pillar_usage)}
        </>
      )}

      {/* 无结果 */}
      {!evalResult && !evalLoading && !evalError && (
        <Empty
          description={t('evaluation.emptyHint')}
          style={{ padding: 40 }}
        />
      )}

      {/* 审计统计 */}
      {auditStats && (
        <>
          <Divider>{t('evaluation.historyStats')}</Divider>
          <Card size="small">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title={t('evaluation.totalQueries')} value={auditStats.total_queries} />
              </Col>
              <Col span={8}>
                <Statistic
                  title={t('evaluation.avgLatency')}
                  value={auditStats.avg_time_ms}
                  suffix="ms"
                  styles={{ content: { color: auditStats.avg_time_ms < 1000 ? '#52c41a' : '#faad14' } }}
                />
              </Col>
              <Col span={8}>
                <Space orientation="vertical" size={2}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{t('evaluation.pillarUsageLabel')}</Text>
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
