/**
 * 决策智能页面（ADR-076 Phase 1 前端三块）
 * 左：决策查询 + 因果链图（G6）；右：先例参考卡片 + 影响分析面板
 */
import React, { useCallback, useState } from 'react';
import { App, Button, Card, Col, Descriptions, Input, Row, Space, Tag, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { DecisionChain, DecisionImpact } from '../types';
import { OUTCOME_META } from '../types';
import { analyzeDecisionImpact, getDecisionChain } from '../services/decisionApi';
import { DecisionChainGraph } from '../components/DecisionChainGraph';
import { PrecedentSearch } from '../components/PrecedentSearch';
import { ImpactPanel } from '../components/ImpactPanel';

const { Title, Text } = Typography;

export default function DecisionIntelligencePage() {
  const { message } = App.useApp();
  const [decisionId, setDecisionId] = useState('');
  const [loading, setLoading] = useState(false);
  const [chain, setChain] = useState<DecisionChain | null>(null);
  const [impact, setImpact] = useState<DecisionImpact | null>(null);

  const loadDecision = useCallback(
    async (id: string) => {
      if (!id.trim()) {
        message.warning('请输入决策 ID');
        return;
      }
      setLoading(true);
      try {
        const chainData = await getDecisionChain(id.trim());
        setChain(chainData);
        setDecisionId(id.trim());
        try {
          const impactData = await analyzeDecisionImpact(id.trim());
          setImpact(impactData);
        } catch {
          setImpact(null);
        }
      } catch (e: any) {
        message.error(`加载决策失败: ${e?.message || e}`);
        setChain(null);
        setImpact(null);
      } finally {
        setLoading(false);
      }
    },
    [message],
  );

  const decision = chain?.decision;
  const outcomeMeta = decision ? OUTCOME_META[decision.outcome] : null;

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginTop: 0 }}>
        决策智能
        <Text type="secondary" style={{ fontSize: 14, marginLeft: 12, fontWeight: 'normal' }}>
          决策溯源 · 先例参考 · 影响分析（ADR-076）
        </Text>
      </Title>

      <Space.Compact style={{ width: 480, marginBottom: 16 }}>
        <Input
          placeholder="输入决策 ID（dec_xxxxxxxxxxxx）"
          value={decisionId}
          onChange={(e) => setDecisionId(e.target.value)}
          onPressEnter={() => loadDecision(decisionId)}
        />
        <Button
          type="primary"
          icon={<SearchOutlined />}
          loading={loading}
          onClick={() => loadDecision(decisionId)}
        >
          查询
        </Button>
      </Space.Compact>

      <Row gutter={16}>
        <Col span={14}>
          <Card title="决策溯源因果链" size="small" style={{ marginBottom: 16 }}>
            <DecisionChainGraph chain={chain} />
          </Card>

          {decision && (
            <Card title="决策详情" size="small">
              <Descriptions size="small" column={2} bordered>
                <Descriptions.Item label="决策 ID">{decision.decision_id}</Descriptions.Item>
                <Descriptions.Item label="结果">
                  {outcomeMeta && <Tag color={outcomeMeta.color}>{outcomeMeta.label}</Tag>}
                </Descriptions.Item>
                <Descriptions.Item label="选定方案" span={2}>
                  {decision.recommended_option || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="置信度">
                  {(decision.confidence * 100).toFixed(0)}%
                </Descriptions.Item>
                <Descriptions.Item label="OPA 门禁">
                  {decision.opa_approved === null || decision.opa_approved === undefined
                    ? '未校验'
                    : decision.opa_approved
                      ? '通过'
                      : '拒绝'}
                </Descriptions.Item>
                <Descriptions.Item label="决策方法">{decision.decision_method}</Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {decision.created_at ? new Date(decision.created_at).toLocaleString() : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="推理摘要" span={2}>
                  {decision.reasoning || '—'}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          )}
        </Col>

        <Col span={10}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <PrecedentSearch onSelectDecision={loadDecision} />
            <ImpactPanel impact={impact} onSelectDecision={loadDecision} />
          </Space>
        </Col>
      </Row>
    </div>
  );
}
