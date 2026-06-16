import { useState } from 'react';
import { Upload, Table, Progress, Alert, Button, Card, Select, Space, Typography, message } from 'antd';
import { UploadOutlined, InboxOutlined, DeleteOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Dragger } = Upload;
const { Text } = Typography;

interface BatchImporterProps {
  workspaceId: string;
  scenarioId: string;
}

interface ImportError {
  row: number;
  index?: number;
  error: string;
}

interface ImportResult {
  status: string;
  success_count: number;
  fail_count: number;
  errors: ImportError[];
  format: string;
  entity_type_id: string;
  workspace_id: string;
}

export default function BatchImporter({ workspaceId, scenarioId }: BatchImporterProps) {
  const { t } = useI18n();
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const [fileList, setFileList] = useState<any[]>([]);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning(t('ingest.selectFile') || '请先选择文件');
      return;
    }

    setImporting(true);
    setProgress(0);
    setResult(null);
    setError(null);

    try {
      const file = fileList[0].originFileObj || fileList[0];
      const text = await file.text();

      setProgress(30);

      const formData = new FormData();
      formData.append('data', text);
      formData.append('format', format);
      formData.append('workspace_id', workspaceId);

      setProgress(60);

      const res = await apiClient.post<ImportResult>(
        `/api/ingest/batch?scenario_id=${scenarioId}`,
        { data: text, format, workspace_id: workspaceId, entity_type_id: scenarioId }
      );

      setProgress(100);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
      setProgress(100);
    } finally {
      setImporting(false);
    }
  };

  const handleRemoveFile = () => {
    setFileList([]);
    setResult(null);
    setError(null);
    setProgress(0);
  };

  const errorColumns = [
    {
      title: t('ingest.row') || '行号',
      dataIndex: 'row',
      key: 'row',
      width: 80,
      render: (row: number, record: ImportError) => row ?? record.index ?? '-',
    },
    {
      title: t('ingest.errorDetail') || '错误详情',
      dataIndex: 'error',
      key: 'error',
    },
  ];

  return (
    <Card title={t('ingest.batchImport') || '批量导入'} style={{ borderRadius: 8 }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Space>
          <Text>{t('ingest.format') || '格式'}:</Text>
          <Select
            value={format}
            onChange={setFormat}
            style={{ width: 120 }}
            options={[
              { value: 'csv', label: 'CSV' },
              { value: 'json', label: 'JSON' },
            ]}
          />
        </Space>

        <Dragger
          accept={format === 'csv' ? '.csv' : '.json'}
          maxCount={1}
          fileList={fileList}
          beforeUpload={(file) => {
            setFileList([file]);
            return false;
          }}
          onRemove={handleRemoveFile}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            {t('ingest.dragFile') || '点击或拖拽文件到此区域上传'}
          </p>
          <p className="ant-upload-hint">
            {format === 'csv' ? 'CSV' : 'JSON'} {t('ingest.formatOnly') || '格式文件'}
          </p>
        </Dragger>

        <Space>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={handleUpload}
            loading={importing}
            disabled={fileList.length === 0}
          >
            {t('ingest.startImport') || '开始导入'}
          </Button>
          {fileList.length > 0 && (
            <Button icon={<DeleteOutlined />} onClick={handleRemoveFile}>
              {t('ingest.clear') || '清除'}
            </Button>
          )}
        </Space>

        {progress > 0 && progress < 100 && (
          <Progress percent={Math.round(progress)} status="active" />
        )}

        {error && (
          <Alert type="error" message={t('ingest.importFailed') || '导入失败'} description={error} showIcon />
        )}

        {result && (
          <>
            <Alert
              type={result.fail_count > 0 ? 'warning' : 'success'}
              message={
                <Space>
                  <Text>
                    {t('ingest.successCount') || '成功'}: {result.success_count}
                  </Text>
                  <Text type="danger">
                    {t('ingest.failCount') || '失败'}: {result.fail_count}
                  </Text>
                </Space>
              }
              showIcon
            />
            {result.errors.length > 0 && (
              <Table
                dataSource={result.errors}
                columns={errorColumns}
                rowKey={(_, idx) => String(idx)}
                pagination={{ pageSize: 5 }}
                size="small"
                title={() => (
                  <Text strong>
                    {t('ingest.errorDetails') || '错误详情'} ({result.errors.length})
                  </Text>
                )}
              />
            )}
          </>
        )}
      </Space>
    </Card>
  );
}
