import { useState } from 'react';
import { Upload, Button, Select, Space, Typography, Tag, Alert, message } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { UploadOutlined, DownloadOutlined, InboxOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Dragger } = Upload;
const { Text } = Typography;

interface OntologyDocumentData {
  id: string;
  name: string;
  version: string;
  object_types: Array<Record<string, any>>;
  action_types: Array<Record<string, any>>;
  relations: Array<Record<string, any>>;
  metadata: Record<string, any>;
}

type ExportFormat = 'json' | 'owl' | 'rdf';

export default function DocumentImporter() {
  const { t } = useI18n('ontology');
  const [fileList, setFileList] = useState<any[]>([]);
  const [preview, setPreview] = useState<OntologyDocumentData | null>(null);
  const [importing, setImporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat>('json');
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileRead = async (file: File) => {
    try {
      const text = await file.text();
      const data = JSON.parse(text) as OntologyDocumentData;
      setPreview(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setPreview(null);
    }
  };

  const handleImport = async () => {
    if (!preview) {
      message.warning(t('documentImport.selectDocument'));
      return;
    }

    setImporting(true);
    setError(null);

    try {
      await apiClient.post('/api/ontology/documents/import', preview);
      message.success(t('documentImport.importSuccess'));
    } catch (e) {
      setError(t('documentImport.importFailed', { msg: (e as Error).message }));
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    if (!preview) {
      message.warning(t('documentImport.selectDocument'));
      return;
    }

    setExporting(true);
    setError(null);

    try {
      const res = await apiClient.post<string>(
        `/api/ontology/documents/${preview.id}/export?format=${exportFormat}`,
        {}
      );

      const content = typeof res === 'string' ? res : JSON.stringify(res, null, 2);
      const blob = new Blob([content], {
        type: exportFormat === 'json' ? 'application/json' : exportFormat === 'owl' ? 'application/rdf+xml' : 'text/turtle',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${preview.name || 'ontology'}.${exportFormat === 'json' ? 'json' : exportFormat === 'owl' ? 'owl' : 'rdf'}`;
      a.click();
      URL.revokeObjectURL(url);
      message.success(t('documentImport.exportSuccess'));
    } catch (e) {
      setError(t('documentImport.exportFailed', { msg: (e as Error).message }));
    } finally {
      setExporting(false);
    }
  };

  const handleRemoveFile = () => {
    setFileList([]);
    setPreview(null);
    setError(null);
  };

  return (
    <Card title={t('documentImport.title')} style={{ borderRadius: 8 }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Dragger
          accept=".json"
          maxCount={1}
          fileList={fileList}
          beforeUpload={(file) => {
            setFileList([file]);
            handleFileRead(file as unknown as File);
            return false;
          }}
          onRemove={handleRemoveFile}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            {t('documentImport.dragDocument')}
          </p>
          <p className="ant-upload-hint">{t('documentImport.fileTypeHint')}</p>
        </Dragger>

        {error && (
          <Alert type="error" title={t('documentImport.parseError')} description={error} showIcon closable onClose={() => setError(null)} />
        )}

        {preview && (
          <Card size="small" title={t('documentImport.preview')} style={{ borderRadius: 6 }}>
            <Descriptions variant="bordered" column={2} size="small">
              <Descriptions.Item label="ID">{preview.id || '-'}</Descriptions.Item>
              <Descriptions.Item label={t('documentImport.name')}>{preview.name}</Descriptions.Item>
              <Descriptions.Item label={t('documentImport.version')}>{preview.version}</Descriptions.Item>
              <Descriptions.Item label={t('documentImport.objectTypes')}>
                <Tag color="blue">{preview.object_types?.length ?? 0}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('documentImport.actionTypes')}>
                <Tag color="green">{preview.action_types?.length ?? 0}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('documentImport.relations')}>
                <Tag color="orange">{preview.relations?.length ?? 0}</Tag>
              </Descriptions.Item>
            </Descriptions>

            {preview.object_types?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>{t('documentImport.objectTypes')}:</Text>
                <div style={{ marginTop: 4 }}>
                  {preview.object_types.map((ot, i) => (
                    <Tag key={i} color="blue" style={{ marginBottom: 4 }}>
                      {ot.name || `Type ${i + 1}`}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {preview.relations?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>{t('documentImport.relations')}:</Text>
                <div style={{ marginTop: 4 }}>
                  {preview.relations.map((rel, i) => (
                    <Tag key={i} color="orange" style={{ marginBottom: 4 }}>
                      {rel.name || `Relation ${i + 1}`}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        <Space>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={handleImport}
            loading={importing}
            disabled={!preview}
          >
            {t('documentImport.import')}
          </Button>

          <Select
            value={exportFormat}
            onChange={setExportFormat}
            style={{ width: 120 }}
            options={[
              { value: 'json', label: t('documentImport.formatJson') },
              { value: 'owl', label: t('documentImport.formatOwl') },
              { value: 'rdf', label: t('documentImport.formatRdf') },
            ]}
          />

          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
            loading={exporting}
            disabled={!preview}
          >
            {t('documentImport.export')}
          </Button>
        </Space>
      </Space>
    </Card>
  );
}
