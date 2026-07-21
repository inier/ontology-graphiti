/** 渠道管理页面 */

import React, { useEffect, useState, useContext } from 'react';
import {
  Card,
  Button,
  Modal,
  Space,
  Breadcrumb,
  Alert,
  message,
} from 'antd';
import {
  SettingOutlined,
  RollbackOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { ProCard } from '@ant-design/pro-components';
import { ChannelList } from '../components/ChannelList';
import { ChannelConfigForm } from '../components/ChannelConfigForm';
import { useChannelStore } from '../stores/channelStore';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import { WorkspaceContext } from '@/modules/shared/components/LayoutContexts';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ChannelConfig, CreateChannelRequest } from '../types';

export const ChannelManagementPage: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { workspaceId } = useParams<{ workspaceId: string }>();
  
  const workspaceCtx = useContext(WorkspaceContext);
  const currentWorkspaceId = workspaceCtx.currentWorkspace;
  
  const effectiveWorkspaceId = workspaceId === 'default' || !workspaceId 
    ? currentWorkspaceId 
    : workspaceId;

  const {
    channels,
    channelTypes,
    loading,
    error,
    fetchChannels,
    fetchChannelTypes,
    createChannel,
    updateChannel,
    deleteChannel,
    enableChannel,
    disableChannel,
    testConnection,
    clearError,
  } = useChannelStore();

  const { show: showLoading, hide: hideLoading } = useGlobalLoading();

  const [modalVisible, setModalVisible] = useState(false);
  const [editingChannel, setEditingChannel] = useState<ChannelConfig | null>(null);

  useEffect(() => {
    if (effectiveWorkspaceId) {
      showLoading(t('加载渠道配置中...'));
      Promise.all([
        fetchChannels(effectiveWorkspaceId),
        fetchChannelTypes(),
      ]).finally(() => {
        hideLoading();
      });
    }
  }, [effectiveWorkspaceId, fetchChannels, fetchChannelTypes, showLoading, hideLoading]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  const handleAdd = () => {
    setEditingChannel(null);
    setModalVisible(true);
  };

  const handleEdit = (channel: ChannelConfig) => {
    setEditingChannel(channel);
    setModalVisible(true);
  };

  const handleDelete = async (channelId: string) => {
    try {
      await deleteChannel(channelId);
      message.success(t('删除成功'));
    } catch {
      // error handled by store
    }
  };

  const handleEnable = async (channelId: string) => {
    try {
      await enableChannel(channelId);
      message.success(t('启用成功'));
    } catch {
      // error handled by store
    }
  };

  const handleDisable = async (channelId: string) => {
    try {
      await disableChannel(channelId);
      message.success(t('停用成功'));
    } catch {
      // error handled by store
    }
  };

  const handleTest = async (channelId: string) => {
    const result = await testConnection(channelId);
    if (result.success) {
      message.success(result.message);
    } else {
      message.error(result.message);
    }
  };

  const handleSubmit = async (values: {
    name: string;
    channel_type: any;
    enabled: boolean;
    allow_from: string[];
    config: Record<string, any>;
  }) => {
    if (!effectiveWorkspaceId) return;

    if (editingChannel) {
      await updateChannel(editingChannel.id, {
        name: values.name,
        config: values.config,
        enabled: values.enabled,
        allow_from: values.allow_from,
      });
    } else {
      const request: CreateChannelRequest = {
        name: values.name,
        channel_type: values.channel_type,
        workspace_id: effectiveWorkspaceId,
        enabled: values.enabled,
        allow_from: values.allow_from,
        config: values.config,
      };
      await createChannel(request);
    }
    setModalVisible(false);
  };

  const handleCancel = () => {
    setModalVisible(false);
    setEditingChannel(null);
  };

  return (
    <div>
      <ProCard>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 24,
          }}
        >
          <Space>
            <SettingOutlined style={{ fontSize: 20 }} />
            <h2 style={{ margin: 0 }}>{t('渠道管理')}</h2>
          </Space>
          <Space>
            <Button
              icon={<RollbackOutlined />}
              onClick={() => navigate('/settings')}
            >
              {t('返回设置')}
            </Button>
            <Button
              type="primary"
              icon={<LinkOutlined />}
              onClick={() => window.open('/settings/channels', '_blank')}
            >
              {t('新窗口打开')}
            </Button>
          </Space>
        </div>

        <Alert
          title={t('渠道配置说明')}
          description={t('配置 IM 渠道后，用户可以通过对应的聊天平台与 AI 助手交互。凭证信息会被加密存储，AI/Agent 无法读取实际凭证值。')}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <ChannelList
          channels={channels}
          loading={loading}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onEnable={handleEnable}
          onDisable={handleDisable}
          onTest={handleTest}
          onAdd={handleAdd}
        />
      </ProCard>

      <Modal
        title={editingChannel ? t('编辑渠道配置') : t('添加渠道配置')}
        open={modalVisible}
        onCancel={handleCancel}
        footer={null}
        width={600}
        destroyOnHidden
      >
        <ChannelConfigForm
          channelTypes={channelTypes}
          initialValues={
            editingChannel
              ? {
                  name: editingChannel.name,
                  channel_type: editingChannel.channel_type,
                  enabled: editingChannel.enabled,
                  allow_from: editingChannel.allow_from,
                  config: editingChannel.config,
                }
              : undefined
          }
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          loading={loading}
        />
      </Modal>
    </div>
  );
};
