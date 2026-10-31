/** 渠道配置类型定义 */
import type { IconRole } from '@/modules/shared/components/iconRegistry';

export type ChannelType =
  | 'telegram'
  | 'slack'
  | 'discord'
  | 'feishu'
  | 'dingtalk'
  | 'email'
  | 'qq'
  | 'matrix'
  | 'whatsapp'
  | 'mochat';

export type ChannelStatus = 'disconnected' | 'connected' | 'error';

export interface ChannelConfig {
  id: string;
  workspace_id: string;
  channel_type: ChannelType;
  name: string;
  enabled: boolean;
  allow_from: string[];
  config: Record<string, unknown>;
  status: ChannelStatus;
  has_credentials: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateChannelRequest {
  channel_type: ChannelType;
  name: string;
  workspace_id: string;
  enabled?: boolean;
  allow_from?: string[];
  config: Record<string, unknown>;
}

export interface UpdateChannelRequest {
  name?: string;
  config?: Record<string, unknown>;
  enabled?: boolean;
  allow_from?: string[];
}

export interface ChannelListResponse {
  channels: ChannelConfig[];
  total: number;
}

export interface ChannelTypeInfo {
  type: ChannelType;
  name: string;
  required_fields: string[];
  optional_fields: string[];
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
}

export interface EnableDisableResponse {
  status: string;
  message: string;
  channel?: ChannelConfig;
}

// 渠道名称映射
export const CHANNEL_TYPE_NAMES: Record<ChannelType, string> = {
  telegram: 'Telegram',
  slack: 'Slack',
  discord: 'Discord',
  feishu: '飞书',
  dingtalk: '钉钉',
  email: '邮件',
  qq: 'QQ',
  matrix: 'Matrix',
  whatsapp: 'WhatsApp',
  mochat: 'Mochat',
};

// 渠道图标语义角色映射（P0-1：禁止 emoji 作功能图标）
// 设计侧 §5.2 未单列渠道族图标，本轮统一使用已登记的 `channel` 语义角色；
// 若要按渠道区分图标，须走「提交 → 设计终审 → 回签」后再扩充注册表。
export const CHANNEL_ICON_ROLES: Record<ChannelType, IconRole> = {
  telegram: 'channel',
  slack: 'channel',
  discord: 'channel',
  feishu: 'channel',
  dingtalk: 'channel',
  email: 'channel',
  qq: 'channel',
  matrix: 'channel',
  whatsapp: 'channel',
  mochat: 'channel',
};


/** @deprecated 使用 CHANNEL_ICON_ROLES + <Icon role={...} /> */
export const CHANNEL_ICONS = CHANNEL_ICON_ROLES;
