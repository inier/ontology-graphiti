/**
 * 证据计数（台账列 / 队列卡片 / 详情页三处共用，避免三处措辞不一致）
 *
 * **三个零/空必须区分**（uiux §6.6 + AC-13）：
 * - `undefined / null` = **数据不可得** → 「证据数未知」
 *   （不可得 ≠ 0：硬写成 0 是把「没拿到数」冒充成「一条都没有」，用户会据此得出错误结论）
 * - `实体 0`          = 真的没证据 → 「该决策未关联证据实体」
 * - `出处 0 且实体>0` = 出处层缺失 → 显式提示，**不能只给 Tooltip**
 *   （只给 Tooltip 等于隐藏：截图、打印、键盘操作下全部丢失）
 */
import React from 'react';
import { Tooltip, Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface Props {
  /** `undefined` / `null` 表示后端未给，渲染为「未知」而非 0 */
  entityCount?: number | null;
  episodeCount?: number | null;
  /** `inline` = 台账/队列紧凑版；`detailed` = 详情页带完整说明 */
  variant?: 'inline' | 'detailed';
}

const EPISODE_HINT = '该决策的实体证据未经 add_episode 管线写入，无法追溯到原始数据源（覆盖率受限）';

export function EvidenceCount({ entityCount, episodeCount, variant = 'inline' }: Props) {
  if (entityCount === undefined || entityCount === null) {
    return <Text type="secondary">证据数未知</Text>;
  }

  const noEntity = entityCount <= 0;
  const episodeUnknown = episodeCount === undefined || episodeCount === null;
  const episodeMissing = !episodeUnknown && episodeCount <= 0;

  if (noEntity) {
    return <Text type="secondary">该决策未关联证据实体</Text>;
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--odap-spacing-xs)' }}>
      <Text style={{ fontVariantNumeric: 'tabular-nums' }}>{`实体 ${entityCount}`}</Text>
      <Text type="secondary" style={{ fontVariantNumeric: 'tabular-nums' }}>
        {episodeUnknown ? '+ 出处未知' : `+ 出处 ${episodeCount}`}
      </Text>
      {episodeMissing &&
        (variant === 'detailed' ? (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--odap-spacing-xs)',
              color: 'var(--odap-color-text-secondary)',
            }}
          >
            <WarningOutlined style={{ fontSize: 16, color: 'var(--odap-color-warning)' }} />
            <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
              {`证据出处层不完整：${EPISODE_HINT}`}
            </Text>
          </span>
        ) : (
          <Tooltip title={`出处层证据缺失（${EPISODE_HINT}）`}>
            <WarningOutlined
              style={{ fontSize: 16, color: 'var(--odap-color-warning)' }}
              aria-label="证据出处层不完整"
            />
          </Tooltip>
        ))}
    </span>
  );
}

export default EvidenceCount;
