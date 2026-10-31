/**
 * 条目状态徽标
 *
 * 状态是文本可读的，不依赖颜色单独传达（无障碍冗余编码）；
 * 配色来自 wikiStatusMeta.ts 的语义 Token 映射。
 */
import { Tag } from 'antd';
import type { WikiEntryStatus } from '../services/wikiTypes';
import { STATUS_TONES } from './wikiStatusMeta';

export function WikiStatusBadge({ status }: { status: WikiEntryStatus }) {
  const tone = STATUS_TONES[status] ?? STATUS_TONES.draft;
  return (
    <Tag
      style={{
        background: tone.bg,
        color: tone.fg,
        borderColor: tone.border,
        marginInlineEnd: 0,
      }}
    >
      {tone.label}
    </Tag>
  );
}
