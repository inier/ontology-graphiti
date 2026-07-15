import { useEffect, useCallback } from 'react';
import { Collapse, Space, Button, Spin, Alert, Typography } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { HistoryOutlined, SettingOutlined } from '@ant-design/icons';
import { useConfigStore } from '../stores/configStore';
import { ConfigGroup } from '../components/ConfigGroup';
import { ConfigHistoryDrawer } from '../components/ConfigHistoryDrawer';
import { ConfigImportExport } from '../components/ConfigImportExport';
import { useGlobalLoading } from '@/modules/shared/stores/globalLoadingStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ServiceCategory } from '../types';

const { Title } = Typography;

export default function SettingsPage() {
  const { t } = useI18n('settings');
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
      showGlobalLoading(t('loading'));
    } else {
      hideGlobalLoading();
    }
  }, [loading, categories.length, showGlobalLoading, hideGlobalLoading, t]);

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
    <div>
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
              {t('title')}
            </Title>
          </Space>
          <Space>
            <ConfigImportExport onImportComplete={handleImportComplete} />
            <Button
              icon={<HistoryOutlined />}
              onClick={() => toggleHistoryDrawer(true)}
            >
              {t('changeHistory')}
            </Button>
          </Space>
        </div>

        {error && (
          <Alert
            type="error"
            title={error}
            closable={{ onClose: clearError }}
            
            style={{ marginBottom: 16 }}
          />
        )}

        {loading && categories.length === 0 ? (
          <div style={{ minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" description={t('loading')} />
          </div>
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
