import React from 'react';
import { AIChatPanel } from '@/modules/ai-assistant';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/**
 * QAPage — 智能问答页面
 *
 * 统一使用 AIChatPanel full 模式。
 * 不再使用独立的 QAChatPage 实现，所有 AI 助手功能共享同一份代码。
 */
export function QAPage({ agentId }: { agentId?: string }) {
  const { t } = useI18n();
  return (
    <AIChatPanel
      mode="full"
      title={t('智能问答')}
      workspaceId="default"
      context={agentId ? { agent_id: agentId } : undefined}
    />
  );
}
