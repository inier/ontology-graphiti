/**
 * QACopilotDemoPage — AG-UI 三大能力演示页
 *
 * 整合：
 * - useAGUI Hook（流式对话 + tool_call）
 * - HITLPanel（人工确认/输入）
 * - StatePanel（Shared State）
 * - CardRegistry（Generative UI）
 *
 * 路由：/qa/copilot（待 Phase 5 注册）
 */

import React, { useState } from 'react';
import { Button, Input, Layout, Space, Typography } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { SendOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { AGUIProvider, useAGUIContext } from './AGUIProvider';
import { HITLPanel } from './HITLPanel';
import { StatePanel } from './StatePanel';
import { CardRenderer } from './CardRegistry';
import type { CardMetadata } from './agui_types';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

function CopilotInner() {
  const { flatMessages, toolCalls, status, send, cancel, pendingInterrupts, error } = useAGUIContext();
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim()) {
      send(input.trim());
      setInput('');
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 16px', display: 'flex', alignItems: 'center' }}>
        <ThunderboltOutlined style={{ color: '#faad14', fontSize: 20, marginRight: 8 }} />
        <Text style={{ color: '#fff' }} strong>
          AG-UI Copilot Demo
        </Text>
        <Text style={{ color: '#fff', marginLeft: 'auto' }} type="secondary">
          Status: {status} {pendingInterrupts.length > 0 && `· ${pendingInterrupts.length} interrupts`}
        </Text>
      </Header>

      <Layout>
        <Sider width={320} style={{ background: '#fff', padding: 16, overflow: 'auto' }}>
          <StatePanel watchPath="/memory/facts" />
          <Card title="🔧 Tool Calls" size="small" style={{ marginTop: 16 }}>
            {toolCalls.length === 0 ? (
              <Text type="secondary">(无)</Text>
            ) : (
              toolCalls.map((tc) => (
                <Card key={tc.id} size="small" type="inner" style={{ marginBottom: 4 }}>
                  <Text code>{tc.name}</Text>
                  {tc.result && (
                    <pre style={{ fontSize: 11, marginTop: 4, maxHeight: 80, overflow: 'auto' }}>
                      {tc.result}
                    </pre>
                  )}
                </Card>
              ))
            )}
          </Card>
        </Sider>

        <Content style={{ padding: 16, overflow: 'auto' }}>
          <Space orientation="vertical" style={{ width: '100%' }}>
            {flatMessages.map((msg) => (
              <Card
                key={msg.id}
                size="small"
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '70%',
                  background: msg.role === 'user' ? '#e6f7ff' : '#fff',
                }}
              >
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {msg.role}
                </Text>
                <div style={{ marginTop: 4 }}>{msg.content}</div>
                {/* Generative UI 示例：在 assistant 消息后渲染示例卡片 */}
                {msg.role === 'assistant' && msg.id.endsWith('-demo') && (
                  <CardRenderer
                    metadata={
                      {
                        card_type: 'chart',
                        card_props: {
                          chart_type: 'line',
                          title: '示例图表',
                          data: {
                            categories: ['1月', '2月', '3月', '4月'],
                            values: [10, 25, 18, 32],
                          },
                        },
                      } as CardMetadata
                    }
                  />
                )}
              </Card>
            ))}

            {error && (
              <Card size="small" style={{ background: '#fff1f0' }}>
                <Text type="danger">Error: {error.message}</Text>
              </Card>
            )}
          </Space>
        </Content>
      </Layout>

      {/* 底部输入栏 + HITL Panel */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 320,
          right: 0,
          padding: 12,
          background: '#fff',
          borderTop: '1px solid #e5e7eb',
        }}
      >
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSend}
            placeholder="输入消息（试试 '查询本月销售数据' 或 '删除文件'）"
            disabled={status === 'streaming'}
          />
          {status === 'streaming' ? (
            <Button onClick={cancel}>取消</Button>
          ) : (
            <Button type="primary" icon={<SendOutlined />} onClick={handleSend}>
              发送
            </Button>
          )}
        </Space.Compact>
      </div>

      <HITLPanel />
    </Layout>
  );
}

export interface QACopilotDemoPageProps {
  apiBase?: string;
  token?: string;
  workspaceId?: string;
}

export function QACopilotDemoPage({ apiBase, token, workspaceId }: QACopilotDemoPageProps) {
  return (
    <AGUIProvider apiBase={apiBase} token={token} workspaceId={workspaceId}>
      <CopilotInner />
    </AGUIProvider>
  );
}

export default QACopilotDemoPage;
