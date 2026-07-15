import { useState } from 'react';
import { Button, Tag, Spin, Space } from 'antd';
import {
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { configApi } from '../services/configApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ServiceCategory, ConfigValidationResult } from '../types';

interface ConnectionTestButtonProps {
  category: ServiceCategory;
  items: Array<{ key: string; value: string }>;
  onTestComplete?: (results: ConfigValidationResult[]) => void;
}

export function ConnectionTestButton({
  category,
  items,
  onTestComplete,
}: ConnectionTestButtonProps) {
  const { t } = useI18n('settings');
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ConfigValidationResult | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      const response = await configApi.testConnection({
        items,
        test_connection: true,
      });
      const categoryResult = response.validation_results?.find(
        (r) => r.category === category,
      );
      setResult(categoryResult || null);
      onTestComplete?.(response.validation_results || []);
    } catch {
      setResult({
        category,
        success: false,
        message: t('connectionRequestFailed'),
        response_time_ms: 0,
        tested_at: new Date().toISOString(),
      });
    } finally {
      setTesting(false);
    }
  };

  const renderResultTag = () => {
    if (!result) return null;
    if (result.success) {
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          {t('connectionSuccess', { ms: result.response_time_ms })}
        </Tag>
      );
    }
    return (
      <Tag icon={<CloseCircleOutlined />} color="error">
        {result.message
          ? t('connectionFailedWithMsg', { msg: result.message })
          : t('connectionFailed')}
      </Tag>
    );
  };

  return (
    <Space>
      <Button
        icon={<ApiOutlined />}
        onClick={handleTest}
        loading={testing}
        disabled={testing || items.length === 0}
        size="small"
      >
        {testing ? t('testing') : t('connectionTest')}
      </Button>
      {testing && <Spin size="small" />}
      {renderResultTag()}
    </Space>
  );
}
