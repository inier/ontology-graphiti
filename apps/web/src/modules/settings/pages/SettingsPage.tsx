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

// P4-1: 常量移到组件外，避免每次渲染重建
const CATEGORY_ORDER: ServiceCategory[] = [
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

export default function SettingsPage() {
  const { t, instance } = useI18n('settings');
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

  // P4-1: useMemo/useEffect 依赖用 instance.language 而非 t，避免每次渲染都重跑
  useEffect(() => {
    if (loading && categories.length === 0) {
      showGlobalLoading(t('加载配置中...'));
    } else {
      hideGlobalLoading();
    }
  }, [loading, categories.length, showGlobalLoading, hideGlobalLoading, instance.language]);

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

  // P4-1: 使用组件外常量 CATEGORY_ORDER
  const sortedCategories = [...categories].sort((a, b) => {
    const idxA = CATEGORY_ORDER.indexOf(a.category);
    const idxB = CATEGORY_ORDER.indexOf(b.category);
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
              {t('系统设置')}
            </Title>
          </Space>
          <Space>
            <ConfigImportExport onImportComplete={handleImportComplete} />
            <Button
              icon={<HistoryOutlined />}
              onClick={() => toggleHistoryDrawer(true)}
            >
              {t('变更历史')}
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
          <div style={{ minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" tip={t('加载配置中...')} />
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
