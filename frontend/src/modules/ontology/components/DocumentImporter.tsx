import { useState } from 'react';
import { Upload, Button, Card, Select, Space, Typography, Descriptions, Tag, Alert, message } from 'antd';
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
  const { t } = useI18n();
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
      message.warning(t('ontology.selectDocument') || '请先选择文件');
      return;
    }

    setImporting(true);
    setError(null);

    try {
      await apiClient.post('/api/ontology/documents/import', preview);
      message.success(t('ontology.importSuccess') || '导入成功');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    if (!preview) {
      message.warning(t('ontology.selectDocument') || '请先选择文件');
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
      message.success(t('ontology.exportSuccess') || '导出成功');
    } catch (e) {
      setError((e as Error).message);
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
    <Card title={t('ontology.documentImport') || '本体文档导入/导出'} style={{ borderRadius: 8 }}>
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
            {t('ontology.dragDocument') || '点击或拖拽 JSON 文件到此区域上传'}
          </p>
          <p className="ant-upload-hint">OntologyDocument JSON</p>
        </Dragger>

        {error && (
          <Alert type="error" message={t('ontology.parseError') || '解析错误'} description={error} showIcon closable onClose={() => setError(null)} />
        )}

        {preview && (
          <Card size="small" title={t('ontology.preview') || '文档预览'} style={{ borderRadius: 6 }}>
            <Descriptions variant="bordered" column={2} size="small">
              <Descriptions.Item label="ID">{preview.id || '-'}</Descriptions.Item>
              <Descriptions.Item label={t('ontology.name') || '名称'}>{preview.name}</Descriptions.Item>
              <Descriptions.Item label={t('ontology.version') || '版本'}>{preview.version}</Descriptions.Item>
              <Descriptions.Item label={t('ontology.objectTypes') || '对象类型'}>
                <Tag color="blue">{preview.object_types?.length ?? 0}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('ontology.actionTypes') || '动作类型'}>
                <Tag color="green">{preview.action_types?.length ?? 0}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('ontology.relations') || '关系'}>
                <Tag color="orange">{preview.relations?.length ?? 0}</Tag>
              </Descriptions.Item>
            </Descriptions>

            {preview.object_types?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>{t('ontology.objectTypes') || '对象类型'}:</Text>
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
                <Text strong>{t('ontology.relations') || '关系'}:</Text>
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
            {t('ontology.import') || '导入'}
          </Button>

          <Select
            value={exportFormat}
            onChange={setExportFormat}
            style={{ width: 120 }}
            options={[
              { value: 'json', label: 'JSON' },
              { value: 'owl', label: 'OWL' },
              { value: 'rdf', label: 'RDF' },
            ]}
          />

          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
            loading={exporting}
            disabled={!preview}
          >
            {t('ontology.export') || '导出'}
          </Button>
        </Space>
      </Space>
    </Card>
  );
}
