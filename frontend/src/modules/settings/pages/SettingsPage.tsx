import { useEffect, useCallback } from 'react';
import { Collapse, Space, Button, Spin, Alert, Typography } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { HistoryOutlined, SettingOutlined } from '@ant-design/icons';
import { useConfigStore } from '../stores/configStore';
import { ConfigGroup } from '../components/ConfigGroup';
import { ConfigHistoryDrawer } from '../components/ConfigHistoryDrawer';
import { ConfigImportExport } from '../components/ConfigImportExport';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import type { ServiceCategory } from '../types';

const { Title } = Typography;

export default function SettingsPage() {
  const {
    categories,
    loading,
    error,
    historyDrawerOpen,
    fetchConfigs,
    updateConfig,
    toggleHistoryDrawer,
    clearError,
  } = useConfigStore();
  const { show: showGlobalLoading, hide: hideGlobalLoading } = useGlobalLoading();

  useEffect(() => {
    if (loading && categories.length === 0) {
      showGlobalLoading('加载配置中...');
    } else {
      hideGlobalLoading();
    }
  }, [loading, categories.length, showGlobalLoading, hideGlobalLoading]);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  const handleSave = useCallback(
    async (category: ServiceCategory, items: Array<{ key: string; value: string }>) => {
      await updateConfig({ items, test_connection: true });
    },
    [updateConfig],
  );

  const handleImportComplete = useCallback(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  const handleRollback = useCallback(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  // Sort categories by a defined order
  const categoryOrder: ServiceCategory[] = [
    'llm',
    'graph_db',
    'object_storage',
    'search',
    'mcp',
    'crawl',
    'policy_engine',
    'cache',
    'oauth',
    'auth',
    'general',
  ];

  const sortedCategories = [...categories].sort((a, b) => {
    const idxA = categoryOrder.indexOf(a.category);
    const idxB = categoryOrder.indexOf(b.category);
    return (idxA === -1 ? 999 : idxA) - (idxB === -1 ? 999 : idxB);
  });

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      <Card>
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
            <Title level={4} style={{ margin: 0 }}>
              系统配置
            </Title>
          </Space>
          <Space>
            <ConfigImportExport onImportComplete={handleImportComplete} />
            <Button
              icon={<HistoryOutlined />}
              onClick={() => toggleHistoryDrawer(true)}
            >
              变更历史
            </Button>
          </Space>
        </div>

        {error && (
          <Alert
            type="error"
            message={error}
            closable
            onClose={clearError}
            style={{ marginBottom: 16 }}
          />
        )}

        {loading && categories.length === 0 ? (
          <div style={{ minHeight: 200 }} />
        ) : (
          <Collapse
            defaultActiveKey={sortedCategories.map((c) => c.category)}
            style={{ background: 'transparent' }}
            items={sortedCategories.map((config) => (
              <ConfigGroup
                key={config.category}
                config={config}
                onSave={handleSave}
                saving={loading}
              />
            ))}
          />
        )}
      </Card>

      <ConfigHistoryDrawer
        open={historyDrawerOpen}
        onClose={() => toggleHistoryDrawer(false)}
        onRollback={handleRollback}
      />
    </div>
  );
}
