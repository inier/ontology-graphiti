/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Upload, Button, Space, Alert, Progress, message, Card, Spin,
} from 'antd';
import {
  InboxOutlined, FileTextOutlined, ClearOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { ontologyApi } from '../services/ontologyApi';
import { useExtractionProgress } from '../hooks/useExtractionProgress';

const { Dragger } = Upload;

export interface DocumentUploaderProps {
  ontologyId: string;
  onExtractionComplete?: (result: any) => void;
}

const ACCEPTED_FORMATS = [
  '.pdf', '.doc', '.docx', '.txt', '.md',
  '.csv', '.xlsx', '.xls',
  '.json', '.xml',
  '.jpg', '.jpeg', '.png', '.tiff',
];

const MAX_FILE_SIZE_MB = 100;

export function DocumentUploader({ ontologyId, onExtractionComplete }: DocumentUploaderProps) {
  const { t } = useI18n('ontology');
  const [fileList, setFileList] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [sessionId, setSessionId] = useState<string>('');

  const { progress } = useExtractionProgress(sessionId || null);

  const handleBeforeUpload = useCallback((file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_FORMATS.includes(ext)) {
      message.error(t('extraction.unsupportedFormat', { format: ext, formats: ACCEPTED_FORMATS.join(', ') }));
      return Upload.LIST_IGNORE;
    }
    if (file.size / 1024 / 1024 > MAX_FILE_SIZE_MB) {
      message.error(t('extraction.fileSizeExceeded', { size: MAX_FILE_SIZE_MB }));
      return Upload.LIST_IGNORE;
    }
    return false;
  }, [t]);

  const handleUpload = useCallback(async () => {
    if (fileList.length === 0) {
      message.warning(t('请输入自然语言描述'));
      return;
    }

    setUploading(true);
    setCurrentFileIndex(0);
    setSessionId('');

    try {
      const results: any[] = [];
      for (let i = 0; i < fileList.length; i++) {
        setCurrentFileIndex(i);
        const formData = new FormData();
        formData.append('ontology_id', ontologyId);
        formData.append('file', fileList[i].originFileObj || fileList[i]);

        const result = await ontologyApi.extraction.extractDocument(formData);
        setSessionId(result?.session_id || '');
        results.push(result);
      }

      message.success(t('extraction.documentExtractComplete', { count: fileList.length }));
      onExtractionComplete?.(results.length === 1 ? results[0] : results);
    } catch (e) {
      message.error(t('extraction.documentExtractFailed', { msg: (e as Error).message }));
    } finally {
      setUploading(false);
    }
  }, [fileList, ontologyId, onExtractionComplete, t]);

  const handleClear = useCallback(() => {
    setFileList([]);
    setCurrentFileIndex(0);
    setSessionId('');
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Alert
        type="info"
        showIcon
        title={t('上传文档进行知识提取')}
        description={`${t('支持格式：PDF / Word / TXT / Markdown / CSV / Excel / JSON / XML / 图片')} ${t('单文件最大 100MB')}`}
      />

      <Dragger
        multiple
        fileList={fileList}
        beforeUpload={handleBeforeUpload}
        onChange={({ fileList: newFileList }) => setFileList(newFileList)}
        onRemove={() => true}
        accept={ACCEPTED_FORMATS.join(',')}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">{t('点击或拖拽文件到此区域上传')}</p>
        <p className="ant-upload-hint">{t('支持批量上传，系统将自动解析文档内容并提取知识结构')}</p>
      </Dragger>

      {uploading && (
        <Card title={t('提取进度')} size="small">
          <div style={{ marginBottom: 16 }}>
            <Progress
              percent={Math.round(((currentFileIndex) / fileList.length) * 100)}
              showInfo={true}
              status="active"
              format={() => `文件 ${currentFileIndex + 1}/${fileList.length}`}
            />
          </div>
          <Progress
            percent={progress?.progress_percent || 0}
            showInfo={true}
            strokeColor={{
              '0%': '#10B981',
              '100%': '#3B82F6',
            }}
            status="active"
          />
          <div style={{ marginTop: 12, color: '#666' }}>
            {progress?.stage || t('初始化')}
            {progress?.message && ` - ${progress.message}`}
          </div>
        </Card>
      )}

      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
            disabled={uploading || fileList.length === 0}
          >
            {t('清空')}
          </Button>
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={handleUpload}
            loading={uploading}
            disabled={fileList.length === 0}
            size="large"
          >
            {t('开始提取')}
          </Button>
        </Space>
      </div>
    </div>
  );
}

export default DocumentUploader;
