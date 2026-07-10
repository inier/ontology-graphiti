/** 渠道卡片组件 */

import React from 'react';
import { Card, Button, Space, Tag, Tooltip, Popconfirm, message } from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  StopOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import type { ChannelConfig } from '../types';
import { CHANNEL_TYPE_NAMES, CHANNEL_ICONS } from '../types';

interface ChannelCardProps {
  channel: ChannelConfig;
  onEdit: (channel: ChannelConfig) => void;
  onDelete: (channelId: string) => void;
  onEnable: (channelId: string) => void;
  onDisable: (channelId: string) => void;
  onTest: (channelId: string) => void;
}

export const ChannelCard: React.FC<ChannelCardProps> = ({
  channel,
  onEdit,
  onDelete,
  onEnable,
  onDisable,
  onTest,
}) => {
  const statusColor = {
    connected: 'green',
    disconnected: 'default',
    error: 'red',
  };

  const statusText = {
    connected: '已连接',
    disconnected: '已断开',
    error: '错误',
  };

  const handleEnableDisable = async () => {
    try {
      if (channel.enabled) {
        await onDisable(channel.id);
      } else {
        await onEnable(channel.id);
      }
    } catch {
      message.error('操作失败');
    }
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 12 }}
      title={
        <Space>
          <span style={{ fontSize: 18 }}>{CHANNEL_ICONS[channel.channel_type]}</span>
          <span>{channel.name}</span>
          <Tag color={channel.enabled ? 'green' : 'default'}>
            {channel.enabled ? '已启用' : '已停用'}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Tooltip title={channel.enabled ? '停用' : '启用'}>
            <Button
              type="text"
              icon={channel.enabled ? <StopOutlined /> : <PlayCircleOutlined />}
              onClick={handleEnableDisable}
            />
          </Tooltip>
          <Tooltip title="测试连接">
            <Button
              type="text"
              icon={<ApiOutlined />}
              onClick={() => onTest(channel.id)}
              disabled={!channel.has_credentials}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => onEdit(channel)}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除此渠道配置吗？"
            onConfirm={() => onDelete(channel.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      }
    >
      <Space orientation="vertical" style={{ width: '100%' }}>
        <div>
          <span style={{ color: '#888' }}>类型：</span>
          <span>{CHANNEL_TYPE_NAMES[channel.channel_type]}</span>
        </div>
        <div>
          <span style={{ color: '#888' }}>状态：</span>
          <Tag color={statusColor[channel.status]}>{statusText[channel.status]}</Tag>
        </div>
        <div>
          <span style={{ color: '#888' }}>凭证：</span>
          <Tag color={channel.has_credentials ? 'green' : 'orange'}>
            {channel.has_credentials ? '已配置' : '未配置'}
          </Tag>
        </div>
        <div>
          <span style={{ color: '#888' }}>允许访问：</span>
          <span>
            {channel.allow_from.includes('*')
              ? '所有人'
              : `${channel.allow_from.length} 个用户`}
          </span>
        </div>
      </Space>
    </Card>
  );
};
