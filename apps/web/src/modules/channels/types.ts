/** 渠道配置类型定义 */

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
  config: Record<string, any>;
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
  config: Record<string, any>;
}

export interface UpdateChannelRequest {
  name?: string;
  config?: Record<string, any>;
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
  email: 'Email',
  qq: 'QQ',
  matrix: 'Matrix',
  whatsapp: 'WhatsApp',
  mochat: 'Mochat',
};

// 渠道图标映射
export const CHANNEL_ICONS: Record<ChannelType, string> = {
  telegram: '📱',
  slack: '💬',
  discord: '🎮',
  feishu: '✈️',
  dingtalk: '💬',
  email: '📧',
  qq: '🐧',
  matrix: '💭',
  whatsapp: '📞',
  mochat: '💼',
};
