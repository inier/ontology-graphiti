/** 渠道列表组件 */

import React, { useState } from 'react';
import { Collapse, Button, Empty, Spin } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { ChannelCard } from './ChannelCard';
import type { ChannelConfig } from '../types';
import { CHANNEL_TYPE_NAMES, CHANNEL_ICONS } from '../types';

interface ChannelListProps {
  channels: ChannelConfig[];
  loading: boolean;
  onEdit: (channel: ChannelConfig) => void;
  onDelete: (channelId: string) => void;
  onEnable: (channelId: string) => void;
  onDisable: (channelId: string) => void;
  onTest: (channelId: string) => void;
  onAdd: () => void;
}

// 按渠道类型分组
const groupChannelsByType = (
  channels: ChannelConfig[]
): Record<string, ChannelConfig[]> => {
  return channels.reduce(
    (acc, channel) => {
      const type = channel.channel_type;
      if (!acc[type]) {
        acc[type] = [];
      }
      acc[type].push(channel);
      return acc;
    },
    {} as Record<string, ChannelConfig[]>
  );
};

export const ChannelList: React.FC<ChannelListProps> = ({
  channels,
  loading,
  onEdit,
  onDelete,
  onEnable,
  onDisable,
  onTest,
  onAdd,
}) => {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);

  if (loading && channels.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  const groupedChannels = groupChannelsByType(channels);
  const channelTypes = Object.keys(groupedChannels).sort();

  const collapseItems = channelTypes.map((type) => ({
    key: type,
    label: (
      <span>
        <span style={{ marginRight: 8 }}>{CHANNEL_ICONS[type as keyof typeof CHANNEL_ICONS]}</span>
        <span>{CHANNEL_TYPE_NAMES[type as keyof typeof CHANNEL_TYPE_NAMES]}</span>
        <span style={{ color: '#888', marginLeft: 8 }}>
          ({groupedChannels[type].length})
        </span>
      </span>
    ),
    children: (
      <div>
        {groupedChannels[type].map((channel) => (
          <ChannelCard
            key={channel.id}
            channel={channel}
            onEdit={onEdit}
            onDelete={onDelete}
            onEnable={onEnable}
            onDisable={onDisable}
            onTest={onTest}
          />
        ))}
      </div>
    ),
  }));

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={onAdd}>
          添加渠道
        </Button>
      </div>

      {channels.length === 0 ? (
        <Empty
          description="暂无渠道配置"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={onAdd}>
            添加第一个渠道
          </Button>
        </Empty>
      ) : (
        <Collapse
          activeKey={activeKeys}
          onChange={(keys) => setActiveKeys(keys as string[])}
          items={collapseItems}
        />
      )}
    </div>
  );
};
