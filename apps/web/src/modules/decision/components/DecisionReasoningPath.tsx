/**
 * 推理路径区块（详情页左栏，因果链图下方）
 *
 * 数据来源：`GET /{id}/chain` 已含 `decision.reasoning_trace`（api-spec `DecisionRecord`
 * `:738-741`），因此**不需要**额外端点，零新增请求。
 * 相位配色：`act`（执行）用品牌色而非错误色 —— 执行动作本身不是错误。
 */
import React from 'react';
import { Space, Tag, Typography } from 'antd';
import {
  ExperimentOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

interface RawStep {
  step_id?: string;
  phase?: string;
  description?: string;
  timestamp?: string;
}

interface Props {
  steps: Array<Record<string, unknown>> | null | undefined;
}

const PHASE_META: Record<string, { label: string; icon: React.ReactNode; token: string }> = {
  observe: { label: '观察', icon: <ExperimentOutlined />, token: 'var(--odap-color-info)' },
  orient: { label: '判断', icon: <QuestionCircleOutlined />, token: 'var(--odap-color-warning)' },
  decide: { label: '决策', icon: <ThunderboltOutlined />, token: 'var(--odap-color-success)' },
  act: { label: '执行', icon: <PlayCircleOutlined />, token: 'var(--odap-color-primary)' },
};

function formatTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString();
}

export function DecisionReasoningPath({ steps }: Props) {
  const list = (steps ?? []) as unknown as RawStep[];
  // 本期「推理路径」没有稳定的后端数据源：**无数据就整块不渲染**。
  // 不渲染空壳骨架、不写「暂无推理路径」——那是在用界面噪音承认一个功能没做完。
  if (list.length === 0) return null;

  return (
    <Space orientation="vertical" size={12} style={{ width: '100%' }}>
      {list.map((step, index) => {
        const phase = PHASE_META[String(step.phase)] ?? {
          label: '未标注相位',
          icon: <QuestionCircleOutlined />,
          token: 'var(--odap-color-text-secondary)',
        };
        return (
          <div key={String(step.step_id || index)} style={{ display: 'flex', gap: 8 }}>
            <Tag
              style={{
                color: phase.token,
                borderColor: 'currentColor',
                background: 'var(--odap-color-bg-tertiary)',
                height: 22,
                lineHeight: '20px',
              }}
              icon={phase.icon}
            >
              {phase.label}
            </Tag>
            <div style={{ flex: 1 }}>
              <div style={{ color: 'var(--odap-color-text-primary)' }}>
                {String(step.description || '该步骤未填写说明')}
              </div>
              <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
                {formatTime(step.timestamp)}
              </Text>
            </div>
          </div>
        );
      })}
    </Space>
  );
}

export default DecisionReasoningPath;
