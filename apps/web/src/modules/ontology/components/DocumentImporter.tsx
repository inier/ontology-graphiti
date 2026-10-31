/**
 * DocumentImporter —— 本体文档级导入 / 导出（非抽取，抽取见 NLExtractor / DatabaseExtractor）
 *
 * 真实契约（apps/api/odap/biz/core/ontology/design/model/api/routes.py）：
 *   POST /api/ontology/model/documents                        → CreateDocumentRequest{id?, name, version, object_types, action_types, relations, metadata} → {id, name}
 *   POST /api/ontology/model/documents/{ontology_id}/export   → OntologyDocument.to_palantir()（无 format 参数）
 *
 * 已移除的虚构能力：
 *   - `POST /api/ontology/documents/import`（不存在）
 *   - `POST /api/ontology/documents/{id}/export?format=owl|rdf`（不存在）
 *   - OWL / RDF 导出格式选择（后端只产出 Palantir 风格 JSON）
 */
import { useMemo, useState } from 'react';
import { Upload, Button, Space, Typography, Tag, Alert, message } from 'antd';
import type { UploadFile } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { UploadOutlined, DownloadOutlined, InboxOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Dragger } = Upload;
const { Text } = Typography;

const DOCUMENTS_URL = `${API_BASE}/api/ontology/model/documents`;

/** 导入文件里的类型/关系条目：结构随来源文档而变，只约定 name 用于预览 */
type DocumentTypeEntry = { name?: unknown } & Record<string, unknown>;

/** 与后端 CreateDocumentRequest 对齐的文档载荷 */
interface OntologyDocumentData {
  id?: string;
  name: string;
  version: string;
  object_types: DocumentTypeEntry[];
  action_types: DocumentTypeEntry[];
  relations: DocumentTypeEntry[];
  metadata: Record<string, unknown>;
}

interface DocumentImporterProps {
  /** 当前正在编辑的本体文档 ID；提供后即使未导入文件也可直接导出该文档 */
  ontologyId?: string;
}

/** 把任意 JSON 归一化为后端可接受的载荷，避免把无关字段透传到 Pydantic */
function toPayload(raw: unknown): OntologyDocumentData {
  const src = (raw ?? {}) as Record<string, unknown>;
  const asArray = (v: unknown): DocumentTypeEntry[] => (Array.isArray(v) ? (v as DocumentTypeEntry[]) : []);
  const asRecord = (v: unknown): Record<string, unknown> =>
    v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
  return {
    ...(typeof src.id === 'string' && src.id ? { id: src.id } : {}),
    name: typeof src.name === 'string' && src.name ? src.name : 'imported_ontology',
    version: typeof src.version === 'string' && src.version ? src.version : '1.0.0',
    object_types: asArray(src.object_types),
    action_types: asArray(src.action_types),
    relations: asArray(src.relations),
    metadata: asRecord(src.metadata),
  };
}

export default function DocumentImporter({ ontologyId }: DocumentImporterProps) {
  const { t } = useI18n('ontology');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [preview, setPreview] = useState<OntologyDocumentData | null>(null);
  const [importedId, setImportedId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** 导出目标：优先刚导入的服务端文档，其次当前编辑的本体，最后文件自带 id */
  const exportTargetId = useMemo(
    () => importedId ?? ontologyId ?? preview?.id ?? null,
    [importedId, ontologyId, preview],
  );

  const handleFileRead = async (file: File) => {
    try {
      const text = await file.text();
      setPreview(toPayload(JSON.parse(text)));
      setImportedId(null);
      setError(null);
    } catch (e) {
      setError(`${t('文件解析失败')}: ${e instanceof Error ? e.message : String(e)}`);
      setPreview(null);
    }
  };

  const handleImport = async () => {
    if (!preview) {
      message.warning(t('请先选择一个本体文档文件'));
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const created = await apiClient.post<{ id?: string; name?: string }>(DOCUMENTS_URL, preview);
      if (created?.id) setImportedId(created.id);
      message.success(t('文档已导入'));
    } catch (e) {
      setError(`${t('导入失败')}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    if (!exportTargetId) {
      message.warning(t('无可导出的文档'));
      return;
    }
    setExporting(true);
    setError(null);
    try {
      const res = await apiClient.post<unknown>(`${DOCUMENTS_URL}/${exportTargetId}/export`, {});
      const content = JSON.stringify(res, null, 2);
      const blob = new Blob([content], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${preview?.name || exportTargetId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      message.success(t('导出成功'));
    } catch (e) {
      setError(`${t('导出失败')}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setExporting(false);
    }
  };

  const handleRemoveFile = () => {
    setFileList([]);
    setPreview(null);
    setImportedId(null);
    setError(null);
  };

  return (
    <Card title={t('本体文档导入导出')} style={{ borderRadius: 8 }}>
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Text type="secondary">{t('导入 = 以 JSON 文件新建一份本体文档；导出 = 取服务端文档的 Palantir 风格 JSON 快照。')}</Text>

        <Dragger
          accept=".json"
          maxCount={1}
          fileList={fileList}
          beforeUpload={(file) => {
            setFileList([file]);
            void handleFileRead(file);
            return false;
          }}
          onRemove={handleRemoveFile}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">{t('拖入或点击选择本体 JSON 文件')}</p>
          <p className="ant-upload-hint">
            {t('文件需包含 name / version / object_types / action_types / relations / metadata')}
          </p>
        </Dragger>

        {error && (
          <Alert type="error" title={t('操作失败')} description={error} showIcon closable={{ onClose: () => setError(null) }} />
        )}

        {preview && (
          <Card size="small" title={t('导入预览')} style={{ borderRadius: 6 }}>
            <Descriptions column={2}>
              <Descriptions.Item label="ID">{preview.id || importedId || '-'}</Descriptions.Item>
              <Descriptions.Item label={t('名称')}>{preview.name}</Descriptions.Item>
              <Descriptions.Item label={t('版本')}>{preview.version}</Descriptions.Item>
              <Descriptions.Item label={t('对象类型数')}>
                <Tag color="blue">{preview.object_types.length}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('动作类型数')}>
                <Tag color="green">{preview.action_types.length}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('关系数')}>
                <Tag color="orange">{preview.relations.length}</Tag>
              </Descriptions.Item>
            </Descriptions>

            {preview.object_types.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>{t('对象类型')}:</Text>
                <div style={{ marginTop: 4 }}>
                  {preview.object_types.map((ot, i) => (
                    <Tag key={i} color="blue" style={{ marginBottom: 4 }}>
                      {typeof ot.name === 'string' && ot.name ? ot.name : `Type ${i + 1}`}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {preview.relations.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>{t('关系')}:</Text>
                <div style={{ marginTop: 4 }}>
                  {preview.relations.map((rel, i) => (
                    <Tag key={i} color="orange" style={{ marginBottom: 4 }}>
                      {typeof rel.name === 'string' && rel.name ? rel.name : `Relation ${i + 1}`}
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
            onClick={() => void handleImport()}
            loading={importing}
            disabled={!preview}
          >
            {t('导入为新文档')}
          </Button>

          <Button
            icon={<DownloadOutlined />}
            onClick={() => void handleExport()}
            loading={exporting}
            disabled={!exportTargetId}
          >
            {t('导出 JSON')}
          </Button>

          {exportTargetId && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('导出目标')}: {exportTargetId}
            </Text>
          )}
        </Space>
      </Space>
    </Card>
  );
}
