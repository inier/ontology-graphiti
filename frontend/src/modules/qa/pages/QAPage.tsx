import React from 'react';
import { QAChatPage } from './QAChatPage';

export function QAPage({ agentId }: { agentId?: string }) {
  return <QAChatPage agentId={agentId} />;
}
