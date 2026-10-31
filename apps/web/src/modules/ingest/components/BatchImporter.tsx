/**
 * 结构化数据批量导入（CSV / JSON → 指定对象类型）。
 *
 * 修复记录：
 *   - 端点：`/api/ingest/batch?scenario_id=...`（不存在）→ `POST /api/ontology/ingestion/batch`；
 *   - 语义：原来把 `scenarioId` 当 `entity_type_id` 传，现在由用户显式选择对象类型；
 *   - 死代码：原来构造了 `FormData` 却未使用，已删除；
 *   - i18n：`t('X') || 'X'` 的兜底是多余的（中文即 key，缺键时本就返回 key 本身），已去掉。
 */
import { useCallback, useEffect, useState } from 'react';
import { Upload, Progress, Alert, Button, Card, Select, Space, Typography, message } from 'antd';
import type { UploadFile } from 'antd';
import { UploadOutlined, InboxOutlined, DeleteOutlined } from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';
import {
  batchImport,
  listObjectTypeOptions,
  type BatchImportError,
  type BatchImportResult,
  type ObjectTypeOption,
} from '../services/batchImportApi';

const { Dragger } = Upload;
const { Text } = Typography;

export interface BatchImporterProps {
  workspaceId?: string;
}

export default function BatchImporter({ workspaceId }: BatchImporterProps) {
  const { t } = useI18n('ingest');
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const [objectTypes, setObjectTypes] = useState<ObjectTypeOption[]>([]);
  const [objectTypesError, setObjectTypesError] = useState<string | null>(null);
  const [entityTypeId, setEntityTypeId] = useState<string | undefined>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  /** 原始 File：beforeUpload 拿到的是 RcFile，单独留存，避免再从未知形状的 UploadFile 里取 */
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<BatchImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  /**
   * 只做 I/O、不写状态：effect 里直接调用「内部会 setState 的函数」会同步写状态，
   * 触发级联渲染（react-hooks/set-state-in-effect）。状态落到 promise 回调里，
   * 并用 ignore 丢弃卸载后的响应。
   */
  const requestObjectTypes = useCallback(() => listObjectTypeOptions(), []);

  useEffect(() => {
    let ignore = false;
    requestObjectTypes()
      .then((options) => { if (!ignore) { setObjectTypes(options); setObjectTypesError(null); } })
      .catch((e: Error) => { if (!ignore) setObjectTypesError(e.message); });
    return () => { ignore = true; };
  }, [requestObjectTypes]);

  /** 重试来自按钮事件，不属于 effect，可以直接写状态 */
  const handleRetryObjectTypes = () => {
    setObjectTypesError(null);
    requestObjectTypes()
      .then((options) => { setObjectTypes(options); })
      .catch((e: Error) => { setObjectTypesError(e.message); });
  };

  const handleUpload = async () => {
    if (!entityTypeId) {
      message.warning(t('请选择目标对象类型'));
      return;
    }
    if (fileList.length === 0) {
      message.warning(t('请先选择文件'));
      return;
    }

    setImporting(true);
    setProgress(0);
    setResult(null);
    setError(null);

    try {
      const file = rawFile ?? fileList[0]?.originFileObj;
      if (!file) {
        setError(t('文件未就绪，请重新选择'));
        return;
      }
      const text = await file.text();
      setProgress(40);

      const res = await batchImport({ entityTypeId, data: text, format, workspaceId });
      setProgress(100);
      setResult(res);
      if (res.fail_count > 0) {
        message.warning(t('导入完成，但有 {{n}} 行失败', { n: res.fail_count }));
      } else {
        message.success(t('导入完成'));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const handleRemoveFile = () => {
    setFileList([]);
    setRawFile(null);
    setResult(null);
    setError(null);
    setProgress(0);
  };

  const errorColumns = [
    {
      title: t('行号'),
      dataIndex: 'row',
      key: 'row',
      width: 80,
      render: (row: number | undefined, record: BatchImportError) => row ?? record.index ?? '-',
    },
    { title: t('错误详情'), dataIndex: 'error', key: 'error' },
  ];

  return (
    <Card title={t('结构化批量导入')} style={{ borderRadius: 8 }} data-testid="batch-importer">
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Space wrap>
          <Text>{t('目标对象类型')}:</Text>
          <Select
            aria-label={t('目标对象类型')}
            value={entityTypeId}
            onChange={setEntityTypeId}
            style={{ width: 240 }}
            placeholder={t('选择要导入的对象类型')}
            loading={objectTypes.length === 0 && !objectTypesError}
            options={objectTypes.map((o) => ({
              value: o.type_id,
              label: `${o.name} (${o.type_id} · ${t('{{n}} 个属性', { n: o.property_count })})`,
            }))}
          />
          <Text>{t('格式')}:</Text>
          <Select
            aria-label={t('格式')}
            value={format}
            onChange={setFormat}
            style={{ width: 120 }}
            options={[
              { value: 'csv', label: 'CSV' },
              { value: 'json', label: 'JSON' },
            ]}
          />
        </Space>

        {objectTypesError && (
          <Alert
            type="warning"
            showIcon
            title={t('对象类型列表拉取失败')}
            description={objectTypesError}
            action={
              <Button size="small" onClick={handleRetryObjectTypes}>
                {t('重试')}
              </Button>
            }
          />
        )}
        {!objectTypesError && objectTypes.length === 0 && (
          <Alert
            type="info"
            showIcon
            title={t('尚无可导入的对象类型')}
            description={t('请先在本体建模中创建对象类型，再回到这里批量导入实例')}
          />
        )}

        <Dragger
          accept={format === 'csv' ? '.csv' : '.json'}
          maxCount={1}
          fileList={fileList}
          beforeUpload={(file) => {
            setFileList([file]);
            setRawFile(file);
            return false;
          }}
          onRemove={handleRemoveFile}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">{t('点击或拖拽文件到此区域上传')}</p>
          <p className="ant-upload-hint">
            {format === 'csv' ? 'CSV' : 'JSON'} {t('格式文件')}
          </p>
        </Dragger>

        <Space>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => void handleUpload()}
            loading={importing}
            disabled={fileList.length === 0 || !entityTypeId}
          >
            {t('开始导入')}
          </Button>
          {fileList.length > 0 && (
            <Button icon={<DeleteOutlined />} onClick={handleRemoveFile}>
              {t('清除')}
            </Button>
          )}
        </Space>

        {progress > 0 && progress < 100 && <Progress percent={Math.round(progress)} status="active" />}

        {error && <Alert type="error" title={t('导入失败')} description={error} showIcon />}

        {result && (
          <>
            <Alert
              type={result.fail_count > 0 ? 'warning' : 'success'}
              title={
                <Space>
                  <Text>
                    {t('成功')}: {result.success_count}
                  </Text>
                  <Text type="danger">
                    {t('失败')}: {result.fail_count}
                  </Text>
                </Space>
              }
              showIcon
            />
            {result.errors.length > 0 && (
              <AdvancedTable
                dataSource={result.errors}
                columns={errorColumns}
                rowKey={(_, idx) => String(idx)}
                pagination={{ pageSize: 5 }}
                size="small"
                title={() => (
                  <Text strong>
                    {t('错误详情')} ({result.errors.length})
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
