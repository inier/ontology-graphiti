/**
 * ExtractorModeCard —— 提取模式切换卡（ADR-089 子项目 C C-D12）。
 *
 * 挂载于缺口统计页顶部：显示当前生效 mode、可选 mode 语义、最近修改人/时间，
 * 切换后提示重跑回归集。不改动 7 个顶层 Tab。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Card, Segmented, Space, Tag, Alert, Typography, message } from 'antd';
import {
  extractorModeApi,
  type ExtractorMode,
  type ExtractorModeInfo,
} from '../services/extractorModeApi';

const { Text } = Typography;

const LABELS: Record<ExtractorMode, string> = {
  off: '关闭（原词直通）',
  inject: '全量注入',
  query: '按需查询（默认）',
};

export const ExtractorModeCard: React.FC = () => {
  const [info, setInfo] = useState<ExtractorModeInfo | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setInfo(await extractorModeApi.getExtractorMode());
    } catch (e) {
      message.error((e as Error).message || '加载提取模式失败');
    }
  }, []);

  useEffect(() => {   void (async () => {
    void load();
  })(); }, [load]);

  const onChange = useCallback(async (mode: ExtractorMode) => {
    if (!info || mode === info.effective_mode) return;
    setSaving(true);
    try {
      const next = await extractorModeApi.setExtractorMode(mode);
      setInfo(next);
      message.success(`提取模式已切换为「${LABELS[mode]}」`);
    } catch (e) {
      message.error((e as Error).message || '切换失败');
    } finally {
      setSaving(false);
    }
  }, [info]);

  if (!info) return null;

  return (
    <Card
      title="实体提取模式"
      style={{ marginBottom: 16 }}
      data-testid="extractor-mode-card"
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space wrap>
          <Segmented<ExtractorMode>
            value={info.effective_mode}
            disabled={saving}
            onChange={(v) => void onChange(v)}
            options={info.available_modes.map((m) => ({ label: LABELS[m], value: m }))}
            data-testid="extractor-mode-segmented"
          />
          <Tag color="blue">当前生效：{LABELS[info.effective_mode]}</Tag>
          {info.default_mode && (
            <Tag>默认：{LABELS[info.default_mode]}</Tag>
          )}
        </Space>

        <Space direction="vertical" size={2}>
          {info.available_modes.map((m) => (
            <Text key={m} type="secondary" style={{ fontSize: 12 }}>
              <b>{LABELS[m]}</b>：{info.descriptions[m]}
            </Text>
          ))}
        </Space>

        <Text type="secondary" style={{ fontSize: 12 }}>
          最近修改：{info.updated_by || '—'} @ {info.updated_at || '—'}
        </Text>

        {info.effective_mode === 'query' && (
          <Alert
            type="info"
            showIcon
            message="按需查询模式已启用：实体归一化 + 幻觉过滤生效。切换模式后建议在 12 小时内重跑缺口回归集以刷新 paired 报告（ADR-088）。"
          />
        )}
      </Space>
    </Card>
  );
};

export default ExtractorModeCard;
