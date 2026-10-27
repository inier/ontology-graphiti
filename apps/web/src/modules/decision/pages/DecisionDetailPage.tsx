/**
 * 决策详情页（`/decisions/detail/:decisionId`）
 *
 * 布局沿用原 `Row gutter=16` + `Col 14/10`（左：这条决策怎么来的；右：它影响了什么）。
 * 三个只读端点 `/chain` `/impact` `/similar` 本期行为不变，直接消费。
 *
 * 空态口径（E26）：跨工作空间与不存在**一律按 404**，文案统一，不区分措辞 ——
 * 403 会泄露「这条决策存在、只是你没权限」，配合跨空间读就是可枚举攻击面。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { App, Button, Card, Col, Row, Skeleton, Space, Typography } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ApartmentOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  PartitionOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { DecisionChain, DecisionImpact } from '../types';
import { analyzeDecisionImpact, getDecisionChain, resolveDecision } from '../services/decisionApi';
import { describeActionError, describeError, errorStatus } from '../services/decisionRequest';
import { DecisionChainGraph } from '../components/DecisionChainGraph';
import { DecisionDetailDescriptions } from '../components/DecisionDetailDescriptions';
import { DecisionDetailHeader } from '../components/DecisionDetailHeader';
import { DecisionErrorState } from '../components/DecisionErrorState';
import { DecisionReasoningPath } from '../components/DecisionReasoningPath';
import { DecisionSyncState } from '../components/DecisionSyncState';
import { ImpactPanel } from '../components/ImpactPanel';
import { PrecedentSearch } from '../components/PrecedentSearch';

const { Text } = Typography;

function hasReasoningSteps(chain: DecisionChain | null): boolean {
  return Boolean(chain?.reasoning_trace?.length || chain?.decision?.reasoning_trace?.length);
}

export default function DecisionDetailPage() {
  const { decisionId = '' } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();

  const [chain, setChain] = useState<DecisionChain | null>(null);
  const [chainError, setChainError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [impact, setImpact] = useState<DecisionImpact | null>(null);
  const [impactError, setImpactError] = useState<unknown>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  // 无裁决权限：按钮禁用 + Tooltip，**不整页 403**（服务端 403 才降级到这里）
  const [permissionDenied, setPermissionDenied] = useState(false);

  const loadChain = useCallback(async () => {
    if (!decisionId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await getDecisionChain(decisionId);
      setChain(data);
      setChainError(null);
    } catch (e) {
      setChainError(e);
      setChain(null);
    } finally {
      setLoading(false);
    }
  }, [decisionId]);

  const loadImpact = useCallback(async () => {
    if (!decisionId) return;
    setImpactLoading(true);
    try {
      const data = await analyzeDecisionImpact(decisionId);
      setImpact(data);
      setImpactError(null);
    } catch (e) {
      // 局部错误：不阻断因果链与详情（旧实现静默 setImpact(null) 把失败伪装成未加载）
      setImpactError(e);
      setImpact(null);
    } finally {
      setImpactLoading(false);
    }
  }, [decisionId]);

  useEffect(() => {
    void loadChain();
    void loadImpact();
  }, [loadChain, loadImpact]);

  const copyId = useCallback(
    (id: string) => {
      void navigator.clipboard?.writeText(id);
      message.success('已复制决策 ID');
    },
    [message],
  );

  const submitResolve = useCallback(
    async (action: 'approve' | 'reject', reason?: string) => {
      setBusy(true);
      try {
        await resolveDecision(decisionId, reason ? { action, reason } : { action });
        message.success(action === 'approve' ? '已采纳' : '已驳回');
        void loadChain();
      } catch (e) {
        // 文案统一由 `decisionRequest` 出（`code` 优先于状态码），不在页面里再拼一遍
        const status = errorStatus(e);
        if (status === 403) {
          setPermissionDenied(true);
          message.warning(describeActionError(e));
        } else if (status === 409) {
          message.warning(describeActionError(e));
          void loadChain();
        } else if (status === 404) {
          message.error(describeActionError(e));
        } else {
          message.error(describeActionError(e));
        }
      } finally {
        setBusy(false);
      }
    },
    [decisionId, loadChain, message],
  );

  const status = errorStatus(chainError);

  if (chainError && (status === 404 || status === 403)) {
    // 404 与 403 文案分开：404 不泄露存在性，403 仅在服务端确认同空间时才出现
    return (
      <DecisionErrorState
        kind={status === 404 ? 'not-found' : 'forbidden'}
        status={status}
        onBack={() => navigate('/decisions/ledger')}
      />
    );
  }

  if (chainError) {
    return (
      <div role="alert" style={{ padding: 'var(--odap-spacing-xl)', textAlign: 'center' }}>
        <CloseCircleOutlined style={{ fontSize: 24, color: 'var(--odap-color-error)' }} />
        <div style={{ margin: '8px 0' }}>
          <Text strong>决策详情加载失败</Text>
        </div>
        {/* 暴露 HTTP 状态 + 后端 detail，不许笼统「加载失败」 */}
        <Text type="secondary">{describeError(chainError)}</Text>
        <div style={{ marginTop: 12 }}>
          <Button icon={<ReloadOutlined />} onClick={() => void loadChain()}>
            重试
          </Button>
        </div>
      </div>
    );
  }

  const decision = chain?.decision;

  return (
    <div style={{ padding: 'var(--odap-spacing-md)' }}>
      <DecisionDetailHeader
        decisionId={decisionId}
        decision={decision}
        loading={loading}
        busy={busy}
        permissionDenied={permissionDenied}
        onBack={() => navigate('/decisions/ledger')}
        onCopyId={copyId}
        onApprove={() => void submitResolve('approve')}
        onReject={(reason) => void submitResolve('reject', reason)}
      />

      {/* E41：status=executing 时先说明「同步中/可能未同步」，避免把残留态读成「执行中」 */}
      {decision && (
        <DecisionSyncState
          status={decision.status}
          updatedAt={decision.updated_at}
          actionRecordId={decision.action_record_id}
        />
      )}

      <Row gutter={16}>
        <Col span={14}>
          <Card
            title={
              <Space size={8}>
                <PartitionOutlined style={{ fontSize: 24 }} />
                决策溯源因果链
              </Space>
            }
            size="small"
            style={{ marginBottom: 16 }}
          >
            <DecisionChainGraph chain={chain} loading={loading} />
          </Card>

          {/* 无推理步骤 → 整块卡片都不渲染（不留空壳、不写「暂无」） */}
          {hasReasoningSteps(chain) && (
            <Card
              title={
                <Space size={8}>
                  <ThunderboltOutlined style={{ fontSize: 24 }} />
                  推理路径
                </Space>
              }
              size="small"
              style={{ marginBottom: 16 }}
            >
              <DecisionReasoningPath
                steps={chain?.reasoning_trace ?? decision?.reasoning_trace}
              />
            </Card>
          )}

          {decision ? (
            <Card title="决策详情" size="small">
              <DecisionDetailDescriptions decision={decision} onCopyId={copyId} />
            </Card>
          ) : (
            loading && <Skeleton active paragraph={{ rows: 6 }} />
          )}
        </Col>

        <Col span={10}>
          <Space orientation="vertical" size={16} style={{ width: '100%' }}>
            {/* 两个面板自带 Card，不再外层套 Card（卡片内嵌卡片是绝对反模式） */}
            <div>
              <Space size={8} style={{ marginBottom: 8 }}>
                <HistoryOutlined style={{ fontSize: 24 }} />
                <Text strong>先例参考</Text>
              </Space>
              <PrecedentSearch
                onSelectDecision={(id) => navigate(`/decisions/detail/${id}`)}
                initialQuery={decision?.context_summary}
                autoSearch={Boolean(decision?.context_summary)}
              />
            </div>

            <div>
              <Space size={8} style={{ marginBottom: 8 }}>
                <ApartmentOutlined style={{ fontSize: 24 }} />
                <Text strong>影响分析</Text>
              </Space>
              <ImpactPanel
                impact={impact}
                loading={impactLoading}
                error={impactError}
                onRetry={() => void loadImpact()}
                onSelectDecision={(id) => navigate(`/decisions/detail/${id}`)}
              />
            </div>
          </Space>
        </Col>
      </Row>
    </div>
  );
}
