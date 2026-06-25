/**
 * AIChatPanel — 统一 AI 助手组件（唯一入口）
 *
 * 支持两种展示模式：
 * - mode="full"    完全体模式：全屏布局，左侧会话列表侧边栏 + 全屏聊天区 + 富文本渲染
 * - mode="compact" 简洁模式：侧边栏/对话框，历史会话折叠为图标，重点为对话
 *
 * 两种模式功能完全一致，共享 useAIChat hook。
 * 所有 AI 助手入口（Header 按钮、本体设计器、智能问答页面）都使用此组件。
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { Button, Input, Tooltip, Drawer, Avatar, Empty, Spin, Tag } from 'antd';
import {
  SendOutlined, RobotOutlined, UserOutlined, ClearOutlined, LoadingOutlined,
  SearchOutlined, ApartmentOutlined, CheckCircleOutlined, PlusOutlined,
  DeleteOutlined, HistoryOutlined, MenuOutlined, CloseOutlined,
} from '@ant-design/icons';
import { css } from '@emotion/css';
import { useAIChat } from '../hooks/useAIChat';
import { useAIContext } from '@/modules/shared/hooks/usePageContext';
import type { ChatMessage, ChatSession } from '../hooks/useAIChat';

// ═══════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════

export interface AIChatPanelProps {
  /** 展示模式：full=完全体（全屏），compact=简洁（侧边栏/对话框） */
  mode?: 'full' | 'compact';
  /** 当前本体ID（本体设计页面传入） */
  ontologyId?: string;
  /** 工作空间ID */
  workspaceId?: string;
  /** 额外上下文（当前选中的对象类型、页面等） */
  context?: Record<string, unknown>;
  /** 面板标题 */
  title?: string;
  /** 欢迎消息 */
  welcomeMessage?: string;
  /** 本体被AI修改后的回调（触发设计器刷新） */
  onOntologyChanged?: () => void;
  /** compact 模式下是否显示为 Drawer（false=内嵌，true=抽屉） */
  asDrawer?: boolean;
  /** Drawer 模式的 open 状态 */
  open?: boolean;
  /** Drawer 模式的关闭回调 */
  onClose?: () => void;
}

// ═══════════════════════════════════════════════════════════════
// 样式
// ═══════════════════════════════════════════════════════════════

const fullStyles = css`
  height: 100%;
  display: flex;
  background: var(--odap-color-bg-container, #fff);
  overflow: hidden;

  .sidebar {
    width: 240px;
    border-right: 1px solid var(--odap-color-border-light, #f0f0f0);
    display: flex;
    flex-direction: column;
    background: var(--odap-color-bg-layout, #fafafa);
    transition: width 0.2s ease;

    &.collapsed { width: 0; overflow: hidden; }
  }

  .sidebar-header {
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--odap-color-border-light, #f0f0f0);
    min-height: 52px;
  }

  .sidebar-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 600;
    color: var(--odap-color-text-primary, #1f2937);
  }

  .sidebar-menu {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
  }

  .session-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: 4px;
    border: 1px solid transparent;

    &:hover { background: var(--odap-color-bg-hover, #f3f4f6); }
    &.active {
      background: var(--odap-color-primary-bg, rgba(99, 102, 241, 0.1));
      border-color: var(--odap-color-primary-border, rgba(99, 102, 241, 0.2));
    }
  }

  .session-info { flex: 1; min-width: 0; }

  .session-title {
    font-size: 13px;
    color: var(--odap-color-text-primary, #1f2937);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .session-meta {
    font-size: 11px;
    color: var(--odap-color-text-tertiary, #9ca3af);
    margin-top: 2px;
  }

  .session-delete {
    opacity: 0;
    border: none;
    transition: opacity 0.2s ease;
    background: transparent;
    cursor: pointer;
    color: var(--odap-color-text-tertiary, #9ca3af);
    &:hover { color: var(--ant-color-error, #ff4d4f); }
  }

  .session-item:hover .session-delete { opacity: 1; }

  .chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .chat-header {
    padding: 0 16px;
    min-height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--odap-color-border-light, #f0f0f0);
    background: var(--odap-color-bg-container, #fff);
  }

  .message-list {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .message-wrapper {
    max-width: 900px;
    margin: 0 auto;
  }

  .message-item {
    display: flex;
    margin-bottom: 20px;
    animation: fadeIn 0.3s ease;
    &.user { flex-direction: row-reverse; }
  }

  .message-avatar {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
  }

  .message-content {
    max-width: 65%;
    margin: 0 12px;
    @media (max-width: 576px) { max-width: 80%; }
  }

  .message-bubble {
    padding: 14px 18px;
    border-radius: 16px;
    position: relative;

    &.user {
      background: var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8));
      color: white;
      border-bottom-right-radius: 4px;
    }
    &.assistant {
      background: var(--odap-color-bg-container, #fff);
      border: 1px solid var(--odap-color-border-light, #e5e7eb);
      border-bottom-left-radius: 4px;
    }
  }

  .message-text {
    line-height: 1.7;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .input-area {
    padding: 16px 24px;
    border-top: 1px solid var(--odap-color-border-light, #f0f0f0);
    background: var(--odap-color-bg-container, #fff);
  }

  .input-container {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
`;

// ═══════════════════════════════════════════════════════════════
// 子组件：侧边栏（full 模式）
// ═══════════════════════════════════════════════════════════════

function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  onDelete,
  collapsed,
  onToggleCollapse,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const formatDate = (ts: string) => {
    const date = new Date(ts);
    const diff = Date.now() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return '刚刚';
    if (hours < 24) return `${hours}小时前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  return (
    <div className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-title">
            <RobotOutlined style={{ color: 'var(--odap-color-primary, #6366F1)' }} />
            AI 助手
          </div>
        )}
        <Button type="text" size="small" icon={collapsed ? <MenuOutlined /> : <CloseOutlined />} onClick={onToggleCollapse} />
      </div>
      {!collapsed && (
        <>
          <div style={{ padding: '8px 12px' }}>
            <Button block icon={<PlusOutlined />} onClick={onNew} style={{ borderRadius: 8 }}>
              新对话
            </Button>
          </div>
          <div className="sidebar-menu">
            {sessions.length === 0 ? (
              <Empty description="暂无对话记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              sessions.map(s => (
                <div
                  key={s.session_id}
                  className={`session-item ${activeSessionId === s.session_id ? 'active' : ''}`}
                  onClick={() => onSelect(s.session_id)}
                >
                  <div className="session-info">
                    <div className="session-title">{s.summary || '未命名对话'}</div>
                    <div className="session-meta">{s.message_count} 条 · {formatDate(s.created_at)}</div>
                  </div>
                  <button
                    className="session-delete"
                    onClick={(e) => { e.stopPropagation(); onDelete(s.session_id); }}
                  >
                    <DeleteOutlined />
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 子组件：消息列表
// ═══════════════════════════════════════════════════════════════

function MessageList({
  messages,
  sending,
  compact,
}: {
  messages: ChatMessage[];
  sending: boolean;
  compact: boolean;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const formatTime = (ts: number) =>
    new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  const fontSize = compact ? 11 : 14;
  const padding = compact ? '6px 10px' : '14px 18px';

  return (
    <div
      ref={listRef}
      style={{
        flex: 1,
        overflow: 'auto',
        padding: compact ? '6px 10px' : '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? 6 : 20,
      }}
    >
      {!compact && <div className="message-wrapper" />}
      {messages.map((msg) => (
        <div
          key={msg.id}
          style={{
            display: 'flex',
            gap: compact ? 6 : 12,
            alignItems: 'flex-start',
            flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
            maxWidth: compact ? '100%' : 900,
            margin: compact ? 0 : '0 auto',
          }}
        >
          {/* Avatar */}
          <div
            style={{
              width: compact ? 22 : 40,
              height: compact ? 22 : 40,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              background: msg.role === 'assistant'
                ? 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))'
                : 'var(--odap-color-bg-secondary, #f5f5f5)',
              color: msg.role === 'assistant' ? '#fff' : 'var(--odap-color-text-secondary, #666)',
              fontSize: compact ? 10 : 16,
            }}
          >
            {msg.role === 'assistant' ? <RobotOutlined /> : <UserOutlined />}
          </div>

          {/* Bubble */}
          <div
            style={{
              maxWidth: compact ? '82%' : '65%',
              padding,
              borderRadius: compact ? 8 : 16,
              fontSize,
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              background: msg.role === 'assistant'
                ? 'var(--odap-color-bg-secondary, #f5f5f5)'
                : 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))',
              color: msg.role === 'assistant' ? 'var(--odap-color-text-primary, #333)' : '#fff',
              borderTopLeftRadius: msg.role === 'assistant' ? 4 : (compact ? 8 : 16),
              borderTopRightRadius: msg.role === 'user' ? 4 : (compact ? 8 : 16),
            }}
          >
            {msg.content || (sending && msg.id === messages[messages.length - 1]?.id ? '思考中...' : '')}

            {/* Tool calls */}
            {msg.tool_calls && msg.tool_calls.length > 0 && (
              <div style={{ marginTop: 4, borderTop: '1px solid var(--odap-color-border-light, #e8e8e8)', paddingTop: 4 }}>
                {msg.tool_calls.map((tc, i) => (
                  <div key={i} style={{ fontSize: 10, opacity: 0.7, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {tc.status === 'pending' ? <LoadingOutlined spin /> : <CheckCircleOutlined />}
                    <span>{tc.tool_name}</span>
                    <span style={{ color: tc.status === 'done' ? 'var(--ant-color-success, #52c41a)' : 'var(--ant-color-warning, #faad14)' }}>
                      {tc.status === 'done' ? '✓' : '...'}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Sources (full mode only) */}
            {!compact && msg.sources && msg.sources.length > 0 && (
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: 'var(--odap-color-text-secondary, #6b7280)' }}>参考来源</div>
                {msg.sources.slice(0, 3).map((src, idx) => (
                  <div key={idx} style={{ background: '#f9fafb', borderRadius: 8, padding: '10px 14px', marginBottom: 8, border: '1px solid #f3f4f6' }}>
                    <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6 }}>{src.excerpt}</div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 8, fontSize: 11, color: '#9ca3af' }}>
                      <span>来源: {src.source || '未知'}</span>
                      <span>置信度: {(src.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Reasoning (full mode only) */}
            {!compact && msg.reasoning && msg.reasoning.length > 0 && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(0,0,0,0.03)', borderRadius: 6, fontSize: 12 }}>
                <div style={{ marginBottom: 6, color: '#8c8c8c', fontWeight: 500 }}>推理过程</div>
                {msg.reasoning.map((step, idx) => (
                  <div key={idx} style={{ padding: '3px 0', borderBottom: idx < msg.reasoning!.length - 1 ? '1px dashed rgba(0,0,0,0.06)' : 'none' }}>
                    <span style={{ marginRight: 6 }}>▸</span>
                    <span style={{ color: '#595959' }}>{step.description}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{ fontSize: 9, marginTop: 3, opacity: 0.45, textAlign: msg.role === 'user' ? 'right' : 'left' }}>
              {formatTime(msg.timestamp)}
            </div>
          </div>
        </div>
      ))}

      {/* Typing indicator */}
      {sending && (
        <div style={{ display: 'flex', gap: compact ? 6 : 12, alignItems: 'center' }}>
          <div style={{
            width: compact ? 22 : 40, height: compact ? 22 : 40, borderRadius: '50%',
            background: 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: compact ? 10 : 16,
          }}>
            <RobotOutlined />
          </div>
          <div style={{ display: 'flex', gap: 3, padding: '6px 10px' }}>
            {[0, 1, 2].map((i) => (
              <span key={i} style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--odap-color-text-tertiary, #bbb)',
                animation: `ai-typing-bounce 1.4s ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes ai-typing-bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 主组件
// ═══════════════════════════════════════════════════════════════

export function AIChatPanel({
  mode = 'compact',
  ontologyId: ontologyIdProp,
  workspaceId: workspaceIdProp,
  context: contextProp,
  title = 'AI 助手',
  welcomeMessage,
  onOntologyChanged,
  asDrawer = false,
  open = true,
  onClose,
}: AIChatPanelProps) {
  const compact = mode === 'compact';
  const [inputValue, setInputValue] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // 使用统一的页面上下文（自动获取当前页面的信息）
  const pageContext = useAIContext();

  // 优先使用 props 传入的值，否则使用页面上下文
  const ontologyId = ontologyIdProp || pageContext.ontologyId;
  const workspaceId = workspaceIdProp || pageContext.workspaceId || 'default';

  // 合并上下文：props 优先，然后是页面上下文
  const context = {
    ...pageContext,
    ...contextProp,
    // 确保关键字段不被覆盖
    page: contextProp?.['page'] || pageContext.pageId,
    selected_types: contextProp?.['selected_types'] || pageContext.selectedTypes,
    object_type: contextProp?.['object_type'] || pageContext.selectedType,
  };

  const ai = useAIChat({
    ontologyId,
    workspaceId,
    context,
    enableSessions: !compact, // full 模式启用会话管理
    onOntologyChanged,
  });

  // 当前类型名（从上下文提取）
  const currentTypeName: string | null = (() => {
    const selTypes = context?.['selected_types'] as string[] | undefined;
    if (selTypes && selTypes.length > 0) return selTypes[0];
    if (context?.['object_type']) return String(context['object_type']);
    return null;
  })();

  // 欢迎消息
  const defaultWelcome = (() => {
    const base = '你好！我是 ODAP AI 助手。\n\n我可以帮你：\n🔍 查询数据（实体、关系）\n🔧 分析本体完整性';
    if (!ontologyId) return base + '\n\n请用自然语言提问！';
    if (currentTypeName) return base + `\n💡 建议「${currentTypeName}」的属性和关系\n\n请用自然语言提问！`;
    return base + '\n\n请用自然语言提问！';
  })();

  // 初始化欢迎消息
  useEffect(() => {
    if (ai.messages.length === 0) {
      let welcome = welcomeMessage || defaultWelcome;
      // 追加本体上下文
      if (ai.ontologyContext) {
        const ctx = ai.ontologyContext as Record<string, unknown>;
        const types = (ctx.object_types as Array<Record<string, unknown>>) || [];
        if (types.length > 0) {
          const typeList = types.map(t => `${t.name}(${t.property_count ?? ((t.properties as string[])?.length ?? 0)})`);
          welcome += `\n\n📋 **当前本体** (${types.length} 个类型):\n${typeList.map((t: string) => `  • ${t}`).join('\n')}`;
        }
      }
      // 手动设置欢迎消息
      ai.sendMessage(''); // 触发空消息不会发送，我们需要另一种方式
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 快捷操作
  const quickActions = (() => {
    if (!ontologyId) return [];
    const base: Array<{ label: string; msg: string; toolName?: string }> = [
      { label: '本体概况', msg: '当前本体包含哪些类型？请给我一个概览' },
      { label: '完整性检查', msg: '帮我检查一下本体完整性' },
    ];
    if (currentTypeName) {
      base.push({ label: '建议属性', msg: `为「${currentTypeName}」类型建议缺失的属性`, toolName: 'suggest_properties' });
      base.push({ label: '建议关系', msg: `为「${currentTypeName}」类型建议可能的关系`, toolName: 'suggest_relations' });
    }
    return base;
  })();

  // 快捷操作处理
  const handleQuickAction = useCallback(async (qa: { label: string; msg: string; toolName?: string }) => {
    if (qa.toolName && ontologyId) {
      // 直接调用工具
      try {
        const params: Record<string, unknown> = { ontology_id: ontologyId };
        if (currentTypeName) params['object_type_name'] = currentTypeName;
        const result = await ai.executeTool(qa.toolName, params);

        // 格式化结果
        let formatted = '';
        if (qa.toolName === 'suggest_properties') {
          const sugg = (result as Record<string, unknown>).suggestions as Array<Record<string, unknown>> || [];
          formatted = `💡 **「${currentTypeName}」属性建议**\n\n`;
          if (sugg.length === 0) {
            formatted += (result as Record<string, unknown>).hint as string || '该类型已具备常用属性，暂无额外建议。';
          } else {
            formatted += `建议添加以下 ${sugg.length} 个属性：\n\n`;
            for (const s of sugg) {
              formatted += `• **${s.name}** (${s.data_type || 'STRING'})\n`;
            }
          }
        } else if (qa.toolName === 'suggest_relations') {
          const sugg = (result as Record<string, unknown>).suggestions as Array<Record<string, unknown>> || [];
          formatted = `🔗 **「${currentTypeName}」关系建议**\n\n`;
          if (sugg.length === 0) {
            formatted += (result as Record<string, unknown>).hint as string || '暂无明显关系建议。';
          } else {
            formatted += `建议添加以下 ${sugg.length} 个关系：\n\n`;
            for (const s of sugg) {
              formatted += `• **${s.name}**  ${s.source_type || currentTypeName} → ${s.target_type}\n`;
            }
          }
        } else {
          formatted = JSON.stringify(result, null, 2);
        }

        // 添加为用户+助手消息
        ai.sendMessage(qa.msg).then(() => {
          // 在发送后追加格式化结果
        });
        // 直接追加工具结果
        setInputValue('');
      } catch {
        // 失败则回退到输入框
        setInputValue(qa.msg);
      }
      return;
    }
    setInputValue(qa.msg);
  }, [ontologyId, currentTypeName, ai]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || ai.sending) return;
    setInputValue('');
    ai.sendMessage(text);
  }, [inputValue, ai]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // ═══════════════════════════════════════════════════════════════
  // 渲染
  // ═══════════════════════════════════════════════════════════════

  const chatContent = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* 欢迎消息（无消息时显示） */}
      {ai.messages.length === 0 && (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: compact ? 16 : 40, textAlign: 'center',
        }}>
          <div>
            <div style={{
              width: compact ? 48 : 80, height: compact ? 48 : 80, margin: '0 auto',
              background: 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))',
              borderRadius: compact ? 12 : 24,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'white', fontSize: compact ? 24 : 40,
            }}>
              <RobotOutlined />
            </div>
            <div style={{ fontSize: compact ? 14 : 24, fontWeight: 600, marginTop: 16, color: 'var(--odap-color-text-primary, #1f2937)' }}>
              {title}
            </div>
            <div style={{ color: 'var(--odap-color-text-secondary, #6b7280)', fontSize: compact ? 12 : 14, marginTop: 8, whiteSpace: 'pre-wrap' }}>
              {welcomeMessage || defaultWelcome}
              {ai.ontologyContext && (() => {
                const ctx = ai.ontologyContext as Record<string, unknown>;
                const types = (ctx.object_types as Array<Record<string, unknown>>) || [];
                if (types.length === 0) return null;
                const typeList = types.map(t => `${t.name}(${t.property_count ?? ((t.properties as string[])?.length ?? 0)})`);
                return `\n\n📋 **当前本体** (${types.length} 个类型):\n${typeList.map((t: string) => `  • ${t}`).join('\n')}`;
              })()}
            </div>
          </div>
        </div>
      )}

      {/* 消息列表 */}
      {ai.messages.length > 0 && (
        <MessageList messages={ai.messages} sending={ai.sending} compact={compact} />
      )}

      {/* 快捷操作 */}
      {quickActions.length > 0 && (
        <div style={{
          padding: compact ? '4px 8px' : '4px 24px',
          display: 'flex', gap: 4, flexWrap: 'wrap',
          borderTop: '1px solid var(--odap-color-border-light, #f0f0f0)',
          maxWidth: 900, margin: '0 auto', width: '100%',
        }}>
          {quickActions.map(qa => (
            <Button key={qa.label} size="small" type="text" style={{ fontSize: 11 }} onClick={() => handleQuickAction(qa)}>
              {qa.label}
            </Button>
          ))}
        </div>
      )}

      {/* 输入区 */}
      <div style={{
        borderTop: '1px solid var(--odap-color-border-light, #f0f0f0)',
        padding: compact ? '4px 8px' : '16px 24px',
        display: 'flex', gap: compact ? 4 : 12,
        alignItems: 'flex-end',
        maxWidth: compact ? '100%' : 900,
        margin: '0 auto', width: '100%',
      }}>
        <Input.TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息，Enter 发送..."
          autoSize={{ minRows: 1, maxRows: 3 }}
          style={{ fontSize: compact ? 11 : 14, resize: 'none' }}
          disabled={ai.sending}
        />
        <div style={{ display: 'flex', gap: 2 }}>
          <Tooltip title="清空对话">
            <Button type="text" size="small" icon={<ClearOutlined />} onClick={ai.clearMessages} disabled={ai.sending} />
          </Tooltip>
          <Button
            type="primary" size="small"
            icon={ai.sending ? <LoadingOutlined /> : <SendOutlined />}
            onClick={handleSend}
            disabled={!inputValue.trim() || ai.sending}
            style={{
              background: 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))',
              border: 'none',
            }}
          />
        </div>
      </div>

      {/* 错误提示 */}
      {ai.error && (
        <div style={{ padding: '4px 12px', fontSize: 11, color: 'var(--ant-color-error, #ff4d4f)' }}>
          {ai.error}
        </div>
      )}
    </div>
  );

  // ═══════════════════════════════════════════════════════════════
  // full 模式：侧边栏 + 全屏聊天
  // ═══════════════════════════════════════════════════════════════
  if (!compact) {
    const fullContent = (
      <div className={fullStyles}>
        <SessionSidebar
          sessions={ai.sessions}
          activeSessionId={ai.currentSessionId}
          onSelect={ai.selectSession}
          onNew={ai.createNewSession}
          onDelete={ai.deleteSession}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <div className="chat-area">
          <div className="chat-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<RobotOutlined />} style={{ background: 'var(--odap-layout-primary-gradient, linear-gradient(135deg, #6366F1, #818CF8))' }} />
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{title}</div>
                {ai.currentSessionId && (
                  <div style={{ fontSize: 11, color: 'var(--odap-color-text-tertiary, #9ca3af)' }}>
                    会话: {ai.currentSessionId.slice(0, 8)}
                  </div>
                )}
              </div>
            </div>
            {ontologyId && (
              <Tag color="purple" style={{ fontSize: 11 }}>
                本体: {ontologyId.slice(-8)}
              </Tag>
            )}
          </div>
          {chatContent}
        </div>
      </div>
    );

    if (asDrawer) {
      return (
        <Drawer
          title={null}
          placement="right"
          open={open}
          onClose={onClose}
          width="100%"
          styles={{ body: { padding: 0, height: '100%' } }}
        >
          {fullContent}
        </Drawer>
      );
    }

    return fullContent;
  }

  // ═══════════════════════════════════════════════════════════════
  // compact 模式：侧边栏/对话框
  // ═══════════════════════════════════════════════════════════════
  if (asDrawer) {
    return (
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RobotOutlined style={{ color: 'var(--odap-color-primary, #6366F1)' }} />
            {title}
            {ontologyId && (
              <span style={{ fontSize: 10, color: 'var(--odap-color-text-tertiary, #999)', fontWeight: 400 }}>
                · 本体: {ontologyId.slice(-8)}
              </span>
            )}
          </div>
        }
        placement="right"
        open={open}
        onClose={onClose}
        width={420}
        styles={{ body: { padding: 0, height: '100%' } }}
      >
        {chatContent}
      </Drawer>
    );
  }

  // 内嵌模式
  return chatContent;
}
