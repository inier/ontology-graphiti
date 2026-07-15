import React, { useEffect, useRef, useCallback, useState } from 'react';
import { Tag, Tooltip, message } from 'antd';
import { LockOutlined, UnlockOutlined } from '@ant-design/icons';

interface EditLockIndicatorProps {
  ontologyId: string;
  userId: string;
  /** 是否正在编辑（为 true 时自动获取锁） */
  editing?: boolean;
}

interface LockInfo {
  ontology_id: string;
  user_id: string;
  session_id: string;
  acquired_at: string;
  last_heartbeat: string;
}

const WS_BASE = (() => {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
})();

const EditLockIndicator: React.FC<EditLockIndicatorProps> = ({
  ontologyId,
  userId,
  editing = false,
}) => {
  const [lockHolder, setLockHolder] = useState<string | null>(null);
  const [lockAcquiredAt, setLockAcquiredAt] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const disconnectWs = useCallback(() => {
    clearHeartbeat();
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'release' }));
      } catch {
        // ignore
      }
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [clearHeartbeat]);

  const connectWs = useCallback(() => {
    if (!ontologyId || !userId) return;

    // 先断开旧连接
    disconnectWs();

    const url = `${WS_BASE}/ws/ontology/edit-lock/${ontologyId}?user_id=${encodeURIComponent(userId)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // 启动心跳，每 15 秒发送一次
      clearHeartbeat();
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'heartbeat' }));
        }
      }, 15000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'lock_acquired') {
          setLockHolder(userId);
          setLockAcquiredAt(new Date().toISOString());
        } else if (msg.type === 'lock_denied') {
          const data = msg.data || {};
          setLockHolder(data.locked_by || 'unknown');
          setLockAcquiredAt(data.locked_at || null);
          message.warning(`本体正在被用户 ${data.locked_by || '他人'} 编辑，暂时无法获取编辑锁`);
        } else if (msg.type === 'lock_expired') {
          setLockHolder(null);
          setLockAcquiredAt(null);
          message.info('编辑锁已过期');
        } else if (msg.type === 'lock_released') {
          setLockHolder(null);
          setLockAcquiredAt(null);
        } else if (msg.type === 'heartbeat_ack') {
          // 心跳确认，无需处理
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setLockHolder(null);
      setLockAcquiredAt(null);
      clearHeartbeat();
    };

    ws.onerror = () => {
      message.error('编辑锁连接失败');
    };
  }, [ontologyId, userId, disconnectWs, clearHeartbeat]);

  // 编辑状态变化时连接/断开 WebSocket
  useEffect(() => {
    if (editing && ontologyId && userId) {
      connectWs();
    } else {
      disconnectWs();
      setLockHolder(null);
      setLockAcquiredAt(null);
    }

    return () => {
      disconnectWs();
    };
  }, [editing, ontologyId, userId, connectWs, disconnectWs]);

  // 组件卸载时释放锁
  useEffect(() => {
    return () => {
      disconnectWs();
    };
  }, [disconnectWs]);

  const isLockedByOther = lockHolder !== null && lockHolder !== userId;
  const isLockedByMe = lockHolder === userId;

  const lockTag = isLockedByMe ? (
    <Tooltip title={`你正在编辑（获取于 ${lockAcquiredAt ? new Date(lockAcquiredAt).toLocaleTimeString() : ''}）`}>
      <Tag icon={<LockOutlined />} color="blue">
        编辑中
      </Tag>
    </Tooltip>
  ) : isLockedByOther ? (
    <Tooltip title={`用户 ${lockHolder} 正在编辑（获取于 ${lockAcquiredAt ? new Date(lockAcquiredAt).toLocaleTimeString() : ''}）`}>
      <Tag icon={<LockOutlined />} color="red">
        已锁定 - {lockHolder}
      </Tag>
    </Tooltip>
  ) : (
    <Tooltip title="无人编辑">
      <Tag icon={<UnlockOutlined />} color="default">
        未锁定
      </Tag>
    </Tooltip>
  );

  return <span data-testid="edit-lock-indicator">{lockTag}</span>;
};

export default EditLockIndicator;
