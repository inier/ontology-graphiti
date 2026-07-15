import { useState } from 'react';
import { Input, Tag, Space, Button } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  EyeOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface PolicyEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  compileStatus?: {
    status: string;
    errors?: string[];
  };
  readOnly?: boolean;
}

export function PolicyEditor({
  value = '',
  onChange,
  compileStatus,
  readOnly = false,
}: PolicyEditorProps) {
  const { t } = useI18n('config');
  const [preview, setPreview] = useState(false);

  const renderCompileStatus = () => {
    if (!compileStatus) return null;

    const isSuccess = compileStatus.status === 'compiled' || compileStatus.status === 'success';
    return (
      <Space style={{ marginBottom: 8 }}>
        <Tag
          icon={isSuccess ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          color={isSuccess ? 'success' : 'error'}
        >
          {isSuccess ? t('policy.compileSuccess') : t('policy.compileFailed')}
        </Tag>
        {compileStatus.errors && compileStatus.errors.length > 0 && (
          <span style={{ fontSize: 12, color: '#ff4d4f' }}>
            {t('policy.errorCount', { count: compileStatus.errors.length })}
          </span>
        )}
      </Space>
    );
  };

  const renderPreview = (markdown: string) => {
    const lines = markdown.split('\n');
    return (
      <div style={{ padding: 12, minHeight: 200 }}>
        {lines.map((line, index) => {
          if (line.startsWith('# ')) {
            return (
              <h2 key={index} style={{ fontSize: 20, fontWeight: 700, margin: '16px 0 8px' }}>
                {line.slice(2)}
              </h2>
            );
          }
          if (line.startsWith('## ')) {
            return (
              <h3 key={index} style={{ fontSize: 16, fontWeight: 600, margin: '12px 0 6px' }}>
                {line.slice(3)}
              </h3>
            );
          }
          if (line.startsWith('- ')) {
            return (
              <div key={index} style={{ paddingLeft: 16, fontSize: 13, lineHeight: 2 }}>
                • {line.slice(2)}
              </div>
            );
          }
          if (line.trim() === '') {
            return <div key={index} style={{ height: 8 }} />;
          }
          return (
            <div key={index} style={{ fontSize: 13, lineHeight: 2 }}>
              {line}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <Card
      title={t('policy.content')}
      size="small"
      extra={
        <Space>
          <Button
            size="small"
            type={preview ? 'default' : 'primary'}
            icon={<EditOutlined />}
            onClick={() => setPreview(false)}
          >
            {t('policy.edit')}
          </Button>
          <Button
            size="small"
            type={preview ? 'primary' : 'default'}
            icon={<EyeOutlined />}
            onClick={() => setPreview(true)}
          >
            {t('policy.preview')}
          </Button>
        </Space>
      }
    >
      {renderCompileStatus()}
      {preview ? (
        renderPreview(value)
      ) : (
        <Input.TextArea
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          rows={16}
          readOnly={readOnly}
          style={{ fontFamily: 'monospace', fontSize: 13 }}
          placeholder={t('policy.contentPlaceholderEn')}
        />
      )}
      {compileStatus?.errors && compileStatus.errors.length > 0 && (
        <div style={{ marginTop: 8, padding: 8, background: '#fff2f0', borderRadius: 4 }}>
          {compileStatus.errors.map((error, index) => (
            <div key={index} style={{ fontSize: 12, color: '#ff4d4f', lineHeight: 1.8 }}>
              {error}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
