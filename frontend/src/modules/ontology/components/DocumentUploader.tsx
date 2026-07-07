/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Upload, Button, Space, Alert, Progress, message,
} from 'antd';
import {
  InboxOutlined, FileTextOutlined, ClearOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';

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
  const [fileList, setFileList] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  const handleBeforeUpload = useCallback((file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_FORMATS.includes(ext)) {
      message.error(`不支持的文件格式: ${ext}，仅支持 ${ACCEPTED_FORMATS.join(', ')}`);
      return Upload.LIST_IGNORE;
    }
    if (file.size / 1024 / 1024 > MAX_FILE_SIZE_MB) {
      message.error(`文件大小不能超过 ${MAX_FILE_SIZE_MB}MB`);
      return Upload.LIST_IGNORE;
    }
    return false;
  }, []);

  const handleUpload = useCallback(async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件');
      return;
    }

    setUploading(true);
    setProgress({ current: 0, total: fileList.length });

    try {
      const results: any[] = [];
      for (let i = 0; i < fileList.length; i++) {
        const formData = new FormData();
        formData.append('ontology_id', ontologyId);
        formData.append('file', fileList[i].originFileObj || fileList[i]);

        const result = await ontologyApi.extraction.extractDocument(formData);
        results.push(result);
        setProgress({ current: i + 1, total: fileList.length });
      }

      message.success(`文档提取完成，共处理 ${fileList.length} 个文件`);
      onExtractionComplete?.(results.length === 1 ? results[0] : results);
    } catch (e) {
      message.error(`文档提取失败: ${(e as Error).message}`);
    } finally {
      setUploading(false);
    }
  }, [fileList, ontologyId, onExtractionComplete]);

  const handleClear = useCallback(() => {
    setFileList([]);
    setProgress({ current: 0, total: 0 });
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Alert
        type="info"
        showIcon
        message="上传文档进行知识提取"
        description={`支持格式：PDF / Word / TXT / Markdown / CSV / Excel / JSON / XML / 图片。单文件最大 ${MAX_FILE_SIZE_MB}MB。`}
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
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">支持批量上传，系统将自动解析文档内容并提取知识结构</p>
      </Dragger>

      {uploading && progress.total > 0 && (
        <Progress
          percent={Math.round((progress.current / progress.total) * 100)}
          status="active"
          format={() => `已处理 ${progress.current}/${progress.total} 个文件`}
        />
      )}

      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
            disabled={uploading || fileList.length === 0}
          >
            清空
          </Button>
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={handleUpload}
            loading={uploading}
            disabled={fileList.length === 0}
            size="large"
          >
            开始提取
          </Button>
        </Space>
      </div>
    </div>
  );
}

export default DocumentUploader;
