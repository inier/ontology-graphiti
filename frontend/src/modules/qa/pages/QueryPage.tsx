/**
 * NL 本体查询页面 - 统一查询入口
 * 整合三检索支柱 + 五阶段管线
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Layout, message } from 'antd';
import { useWorkspace, useScenario } from '@/modules/shared';
import { QueryInput } from '../components/QueryInput';
import { QueryResultList } from '../components/QueryResultList';
import { QueryPlanViewer } from '../components/QueryPlanViewer';
import { PillarStatusPanel } from '../components/PillarStatusPanel';
import { QueryAuditTimeline } from '../components/QueryAuditTimeline';
import { CypherPreview } from '../components/CypherPreview';
import { useNLQueryStore } from '../stores/nlQueryStore';
import type { QueryMode } from '../services/nlQueryApi';

const { Sider, Content } = Layout;

export function QueryPage() {
  const [input, setInput] = useState('');
  const { currentWorkspace } = useWorkspace();
  const { currentScenario } = useScenario();

  const {
    queryLoading,
    queryResult,
    queryError,
    searchLoading,
    searchResult,
    searchError,
    explainLoading,
    explainResult,
    explainError,
    pillarStatus,
    auditRecords,
    auditTotal,
    auditStats,
    auditLoading,
    currentMode,
    topK,
    executeQuery,
    executeExplain,
    fetchPillarStatus,
    fetchAuditRecords,
    fetchAuditStats,
    setMode,
    setTopK,
  } = useNLQueryStore();

  // 初始化加载支柱状态和审计记录
  useEffect(() => {
    fetchPillarStatus();
    fetchAuditRecords({ limit: 10 });
    fetchAuditStats();
  }, [fetchPillarStatus, fetchAuditRecords, fetchAuditStats]);

  const handleSearch = useCallback(() => {
    if (!input.trim()) {
      message.warning('请输入查询内容');
      return;
    }
    executeQuery(input, currentWorkspace, currentScenario);
  }, [input, currentWorkspace, currentScenario, executeQuery]);

  const handleExplain = useCallback(() => {
    if (!input.trim()) {
      message.warning('请输入查询内容');
      return;
    }
    executeExplain(input, currentWorkspace, currentScenario);
  }, [input, currentWorkspace, currentScenario, executeExplain]);

  const handleModeChange = useCallback((mode: QueryMode) => {
    setMode(mode);
  }, [setMode]);

  const handleAuditPageChange = useCallback((offset: number) => {
    fetchAuditRecords({ limit: 10, offset });
  }, [fetchAuditRecords]);

  // 从审计记录中提取 Cypher
  const latestCypher = auditRecords.length > 0 ? auditRecords[0].cypher_generated : null;

  return (
    <Layout style={{ height: '100%', background: '#fff' }}>
      {/* 左侧：支柱状态 + 审计时间线 */}
      <Sider
        width={280}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
          padding: '8px',
        }}
      >
        <PillarStatusPanel
          pillars={pillarStatus?.pillars || []}
          loading={!pillarStatus}
        />
        <QueryAuditTimeline
          records={auditRecords}
          total={auditTotal}
          loading={auditLoading}
          onPageChange={handleAuditPageChange}
        />
        {auditStats && (
          <div style={{ padding: '4px 8px', fontSize: 11, color: '#999' }}>
            总查询: {auditStats.total_queries} | 平均耗时: {auditStats.avg_time_ms.toFixed(0)}ms
          </div>
        )}
      </Sider>

      {/* 主区域：查询输入 + 结果 */}
      <Content style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* 查询输入 */}
        <QueryInput
          value={input}
          onChange={setInput}
          onSearch={handleSearch}
          onExplain={handleExplain}
          mode={currentMode}
          onModeChange={handleModeChange}
          topK={topK}
          onTopKChange={setTopK}
          loading={queryLoading || searchLoading}
        />

        {/* 查询计划 / 解释 */}
        <QueryPlanViewer
          understanding={queryResult?.understanding || explainResult?.understanding}
          plan={queryResult?.plan || explainResult?.plan}
          explanation={explainResult?.explanation}
          loading={explainLoading}
        />

        {/* Cypher 预览 */}
        <CypherPreview cypher={latestCypher} validated source="审计记录" />

        {/* 结果列表 */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <QueryResultList
            queryResult={queryResult}
            searchResult={searchResult}
            loading={queryLoading || searchLoading}
            error={queryError || searchError || explainError}
          />
        </div>
      </Content>
    </Layout>
  );
}
