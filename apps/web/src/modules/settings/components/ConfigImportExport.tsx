import { useState } from 'react';
import { Button, Space, Upload, message } from 'antd';
import {
  ExportOutlined,
  ImportOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { configApi } from '../services/configApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface ConfigImportExportProps {
  onImportComplete?: () => void;
}

export function ConfigImportExport({ onImportComplete }: ConfigImportExportProps) {
  const { t } = useI18n('settings');
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await configApi.exportConfigs();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `odap-config-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      message.success(t('配置已导出'));
    } catch {
      message.error(t('导出配置失败'));
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (file: File) => {
    setImporting(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);

      // Support both { items: [...] } and bare [...] formats
      const items = Array.isArray(parsed)
        ? parsed
        : parsed.items || [];

      if (items.length === 0) {
        message.warning(t('导入文件中没有配置项'));
        return false;
      }

      const result = await configApi.importConfigs(items);
      message.success(
        t('importSuccess', { count: result.saved_count, version: result.revision_number }),
      );
      onImportComplete?.();
    } catch (e) {
      if (e instanceof SyntaxError) {
        message.error(t('导入文件格式错误，请检查 JSON 格式'));
      } else {
        message.error(t('导入配置失败'));
      }
    } finally {
      setImporting(false);
    }
    return false; // Prevent default upload behavior
  };

  return (
    <Space>
      <Button
        icon={<ExportOutlined />}
        onClick={handleExport}
        loading={exporting}
      >
        {t('导出配置')}
      </Button>
      <Upload
        accept=".json"
        showUploadList={false}
        beforeUpload={handleImport}
        disabled={importing}
      >
        <Button icon={<ImportOutlined />} loading={importing}>
          {t('导入配置')}
        </Button>
      </Upload>
    </Space>
  );
}
