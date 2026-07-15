/** 渠道配置状态管理 */

import { create } from 'zustand';
import type {
  ChannelConfig,
  ChannelTypeInfo,
  CreateChannelRequest,
  UpdateChannelRequest,
} from '../types';
import * as channelApi from '../services/channelApi';

interface ChannelState {
  // 数据
  channels: ChannelConfig[];
  channelTypes: ChannelTypeInfo[];
  currentWorkspaceId: string | null;

  // 状态
  loading: boolean;
  error: string | null;

  // 操作
  fetchChannels: (workspaceId: string) => Promise<void>;
  fetchChannelTypes: () => Promise<void>;
  createChannel: (request: CreateChannelRequest) => Promise<ChannelConfig>;
  updateChannel: (
    channelId: string,
    request: UpdateChannelRequest
  ) => Promise<ChannelConfig>;
  deleteChannel: (channelId: string) => Promise<void>;
  testConnection: (channelId: string) => Promise<{ success: boolean; message: string }>;
  enableChannel: (channelId: string) => Promise<void>;
  disableChannel: (channelId: string) => Promise<void>;
  setCurrentWorkspace: (workspaceId: string) => void;
  clearError: () => void;
}

export const useChannelStore = create<ChannelState>((set, get) => ({
  // 初始状态
  channels: [],
  channelTypes: [],
  currentWorkspaceId: null,
  loading: false,
  error: null,

  // 获取渠道列表
  fetchChannels: async (workspaceId: string) => {
    set({ loading: true, error: null });
    try {
      const response = await channelApi.listChannels(workspaceId);
      set({
        channels: response.channels,
        currentWorkspaceId: workspaceId,
        loading: false,
      });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '获取渠道列表失败',
        loading: false,
      });
    }
  },

  // 获取渠道类型列表
  fetchChannelTypes: async () => {
    try {
      const types = await channelApi.listChannelTypes();
      set({ channelTypes: types });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '获取渠道类型失败',
      });
    }
  },

  // 创建渠道
  createChannel: async (request: CreateChannelRequest) => {
    set({ loading: true, error: null });
    try {
      const channel = await channelApi.createChannel(request);
      set((state) => ({
        channels: [...state.channels, channel],
        loading: false,
      }));
      return channel;
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '创建渠道失败',
        loading: false,
      });
      throw error;
    }
  },

  // 更新渠道
  updateChannel: async (
    channelId: string,
    request: UpdateChannelRequest
  ) => {
    set({ loading: true, error: null });
    try {
      const channel = await channelApi.updateChannel(channelId, request);
      set((state) => ({
        channels: state.channels.map((c) =>
          c.id === channelId ? channel : c
        ),
        loading: false,
      }));
      return channel;
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '更新渠道失败',
        loading: false,
      });
      throw error;
    }
  },

  // 删除渠道
  deleteChannel: async (channelId: string) => {
    set({ loading: true, error: null });
    try {
      await channelApi.deleteChannel(channelId);
      set((state) => ({
        channels: state.channels.filter((c) => c.id !== channelId),
        loading: false,
      }));
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '删除渠道失败',
        loading: false,
      });
      throw error;
    }
  },

  // 测试连接
  testConnection: async (channelId: string) => {
    try {
      const result = await channelApi.testConnection(channelId);
      return result;
    } catch (error: any) {
      return {
        success: false,
        message: error.response?.data?.detail || '测试连接失败',
      };
    }
  },

  // 启用渠道
  enableChannel: async (channelId: string) => {
    try {
      const result = await channelApi.enableChannel(channelId);
      if (result.channel) {
        set((state) => ({
          channels: state.channels.map((c) =>
            c.id === channelId ? result.channel! : c
          ),
        }));
      }
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '启用渠道失败',
      });
      throw error;
    }
  },

  // 停用渠道
  disableChannel: async (channelId: string) => {
    try {
      const result = await channelApi.disableChannel(channelId);
      if (result.channel) {
        set((state) => ({
          channels: state.channels.map((c) =>
            c.id === channelId ? result.channel! : c
          ),
        }));
      }
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || '停用渠道失败',
      });
      throw error;
    }
  },

  // 设置当前工作空间
  setCurrentWorkspace: (workspaceId: string) => {
    set({ currentWorkspaceId: workspaceId });
  },

  // 清除错误
  clearError: () => {
    set({ error: null });
  },
}));
