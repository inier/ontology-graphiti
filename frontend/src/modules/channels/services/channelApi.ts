/** 渠道配置 API 服务 */

import { fetchJson, apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type {
  ChannelConfig,
  ChannelListResponse,
  ChannelTypeInfo,
  CreateChannelRequest,
  EnableDisableResponse,
  TestConnectionResponse,
  UpdateChannelRequest,
} from '../types';

const BASE_URL = `${API_BASE}/api/channels`;

/** 获取工作空间的所有渠道配置 */
export async function listChannels(
  workspaceId: string,
  channelType?: string
): Promise<ChannelListResponse> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (channelType) {
    params.append('channel_type', channelType);
  }
  return fetchJson<ChannelListResponse>(`${BASE_URL}?${params.toString()}`);
}

/** 获取单个渠道配置 */
export async function getChannel(channelId: string): Promise<ChannelConfig> {
  return fetchJson<ChannelConfig>(`${BASE_URL}/${channelId}`);
}

/** 创建渠道配置 */
export async function createChannel(
  request: CreateChannelRequest
): Promise<ChannelConfig> {
  return fetchJson<ChannelConfig>(BASE_URL, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/** 更新渠道配置 */
export async function updateChannel(
  channelId: string,
  request: UpdateChannelRequest
): Promise<ChannelConfig> {
  return fetchJson<ChannelConfig>(`${BASE_URL}/${channelId}`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
}

/** 删除渠道配置 */
export async function deleteChannel(channelId: string): Promise<void> {
  await fetchJson(`${BASE_URL}/${channelId}`, { method: 'DELETE' });
}

/** 测试渠道连接 */
export async function testConnection(
  channelId: string
): Promise<TestConnectionResponse> {
  return fetchJson<TestConnectionResponse>(`${BASE_URL}/${channelId}/test`, {
    method: 'POST',
  });
}

/** 启用渠道 */
export async function enableChannel(
  channelId: string
): Promise<EnableDisableResponse> {
  return fetchJson<EnableDisableResponse>(`${BASE_URL}/${channelId}/enable`, {
    method: 'POST',
  });
}

/** 停用渠道 */
export async function disableChannel(
  channelId: string
): Promise<EnableDisableResponse> {
  return fetchJson<EnableDisableResponse>(`${BASE_URL}/${channelId}/disable`, {
    method: 'POST',
  });
}

/** 获取所有支持的渠道类型 */
export async function listChannelTypes(): Promise<ChannelTypeInfo[]> {
  return fetchJson<ChannelTypeInfo[]>(`${BASE_URL}/types`);
}
