import { useState, useEffect, useCallback } from 'react';
import { Card, Tag, Modal, Form, Input, Select as AntSelect, Space, Button as AntButton, Row, Col, Popconfirm, Alert, Typography, Divider, Upload } from 'antd';
import { CheckOutlined, RobotOutlined, PlusOutlined, ImportOutlined, ScanOutlined, DeleteOutlined, ExportOutlined, DownloadOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import adapter from '@/modules/shared/components/adapter';
import { PageHeader } from '@/modules/shared/components/PageHeader';
import { useI18nAdminStore } from '../stores/i18nAdminStore';
import { i18nApi } from '../services/i18nApi';
import type { TranslationEntry, ScanMissingResult } from '../services/i18nApi';
import { AdvancedTable } from '@/modules/shared';

const Button = adapter.getButton();
const { Text } = Typography;

const PRESET_LOCALES = [
  { code: 'ja-JP', name: 'Japanese', native_name: '日本語' },
  { code: 'ko-KR', name: 'Korean', native_name: '한국어' },
  { code: 'fr-FR', name: 'French', native_name: 'Français' },
  { code: 'de-DE', name: 'German', native_name: 'Deutsch' },
  { code: 'es-ES', name: 'Spanish', native_name: 'Español' },
  { code: 'ru-RU', name: 'Russian', native_name: 'Русский' },
  { code: 'pt-BR', name: 'Portuguese (Brazil)', native_name: 'Português' },
  { code: 'ar-SA', name: 'Arabic', native_name: 'العربية' },
  { code: 'it-IT', name: 'Italian', native_name: 'Italiano' },
  { code: 'th-TH', name: 'Thai', native_name: 'ไทย' },
];

export function I18nAdminPage() {
  const { t } = useTranslation('i18n-admin');
  const {
    translations,
    modules,
    locales,
    total,
    loading,
    loadTranslations,
    saveTranslation,
    saveTranslationsBulk,
    deleteTranslation,
    autoTranslate,
    scanMissing,
    loadModules,
    loadLocales,
  } = useI18nAdminStore();

  // Edit modal
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [currentPage, setCurrentPage] = useState(1);
  const [currentPageSize, setCurrentPageSize] = useState(20);

  // Filter
  const [filterModule, setFilterModule] = useState<string | undefined>();
  const [filterLocale, setFilterLocale] = useState<string | undefined>();

  // Auto translate modal
  const [autoTranslateModalVisible, setAutoTranslateModalVisible] = useState(false);
  const [autoTranslateForm] = Form.useForm();

  // Add locale modal
  const [addLocaleModalVisible, setAddLocaleModalVisible] = useState(false);
  const [addLocaleForm] = Form.useForm();

  // Bulk import modal
  const [bulkImportModalVisible, setBulkImportModalVisible] = useState(false);
  const [bulkImportForm] = Form.useForm();

  // Scan missing modal
  const [scanMissingModalVisible, setScanMissingModalVisible] = useState(false);
  const [scanMissingForm] = Form.useForm();
  const [scanResult, setScanResult] = useState<ScanMissingResult | null>(null);

  // Export modal
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportForm] = Form.useForm();

  useEffect(() => {
    loadModules();
    loadLocales();
    loadTranslations({ module: filterModule, locale: filterLocale, page: 1, page_size: currentPageSize });
    setCurrentPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFilter = useCallback(() => {
    setCurrentPage(1);
    loadTranslations({ module: filterModule, locale: filterLocale, page: 1, page_size: currentPageSize });
  }, [filterModule, filterLocale, currentPageSize, loadTranslations]);

  const handleEdit = useCallback((entry: TranslationEntry) => {
    editForm.setFieldsValue({
      key: entry.key,
      module: entry.module,
      locale: entry.locale,
      value: entry.value,
    });
    setEditModalVisible(true);
  }, [editForm]);

  const handleEditSubmit = useCallback(async () => {
    try {
      const values = await editForm.validateFields();
      await saveTranslation(values);
      setEditModalVisible(false);
      editForm.resetFields();
      adapter.getMessage().success(t('saveSuccess'));
      handleFilter();
    } catch {
      // validation error
    }
  }, [editForm, saveTranslation, handleFilter, t]);

  const handleDelete = useCallback(async (entry: TranslationEntry) => {
    await deleteTranslation({
      key: entry.key,
      module: entry.module,
      locale: entry.locale,
    });
    adapter.getMessage().success(t('deleted'));
  }, [deleteTranslation, t]);

  const handleReview = useCallback(async (entry: TranslationEntry, approved: boolean) => {
    await i18nApi.reviewTranslation(entry.key, entry.module, entry.locale, approved);
    adapter.getMessage().success(approved ? t('approved') : t('deactivate'));
    handleFilter();
  }, [handleFilter, t]);

  const handleAutoTranslate = useCallback(async () => {
    try {
      const values = await autoTranslateForm.validateFields();
      await autoTranslate(values.module, values.source_locale, values.target_locale);
      setAutoTranslateModalVisible(false);
      autoTranslateForm.resetFields();
      adapter.getMessage().success(t('autoTranslateTitle'));
      handleFilter();
    } catch {
      // validation error
    }
  }, [autoTranslateForm, autoTranslate, handleFilter, t]);

  // Add locale
  const handleAddLocale = useCallback(async () => {
    try {
      const values = await addLocaleForm.validateFields();
      const success = await useI18nAdminStore.getState().addLocale({
        code: values.code,
        name: values.name,
        native_name: values.native_name,
      });
      if (success) {
        adapter.getMessage().success(t('addLocaleSuccess', { code: values.code }));
        setAddLocaleModalVisible(false);
        addLocaleForm.resetFields();
      } else {
        adapter.getMessage().error(t('addFailed'));
      }
    } catch {
      // validation error
    }
  }, [addLocaleForm, t]);

  const handlePresetLocale = useCallback((code: string) => {
    const preset = PRESET_LOCALES.find((p) => p.code === code);
    if (preset) {
      addLocaleForm.setFieldsValue({
        code: preset.code,
        name: preset.name,
        native_name: preset.native_name,
      });
    }
  }, [addLocaleForm]);

  // Bulk import
  const handleBulkImport = useCallback(async () => {
    try {
      const values = await bulkImportForm.validateFields();
      const lines = (values.data as string).trim().split('\n');
      const items: Array<{ key: string; module: string; locale: string; value: string }> = [];
      for (const line of lines) {
        const parts = line.split('\t');
        if (parts.length >= 4) {
          items.push({
            module: parts[0].trim(),
            key: parts[1].trim(),
            locale: parts[2].trim(),
            value: parts.slice(3).join('\t').trim(),
          });
        }
      }
      if (items.length === 0) {
        adapter.getMessage().error(t('noValidData'));
        return;
      }
      const count = await saveTranslationsBulk(items);
      if (count > 0) {
        adapter.getMessage().success(t('bulkImportSuccess', { count }));
        setBulkImportModalVisible(false);
        bulkImportForm.resetFields();
        handleFilter();
      } else {
        adapter.getMessage().error(t('importFailed'));
      }
    } catch {
      // validation error
    }
  }, [bulkImportForm, saveTranslationsBulk, handleFilter, t]);

  // Scan missing
  const handleScanMissing = useCallback(async () => {
    try {
      const values = await scanMissingForm.validateFields();
      const result = await scanMissing(values.module, values.locale);
      if (result) {
        setScanResult(result);
      } else {
        adapter.getMessage().error(t('scanFailed'));
      }
    } catch {
      // validation error
    }
  }, [scanMissingForm, scanMissing, t]);

  // Export: 打开导出对话框
  const handleExportOpen = useCallback(() => {
    if (!filterModule) {
      adapter.getMessage().warning(t('selectModuleRequired'));
      return;
    }
    exportForm.setFieldsValue({
      locale: filterLocale || 'zh-CN',
      module: filterModule,
    });
    setExportModalVisible(true);
  }, [filterModule, filterLocale, exportForm, t]);

  // Export: 确认导出
  const handleExportConfirm = useCallback(async () => {
    try {
      const values = await exportForm.validateFields();
      const result = await i18nApi.getBundle(values.module, values.locale);
      const blob = new Blob([JSON.stringify(result.bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${values.module}-${values.locale}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      adapter.getMessage().success(t('saveSuccess'));
      setExportModalVisible(false);
    } catch {
      adapter.getMessage().error(t('importFailed'));
    }
  }, [exportForm, t]);

  // 下载导入模板（Excel 友好格式：4 列）
  const handleDownloadTemplate = useCallback(() => {
    // 用换行分隔行，用 Tab 分隔列，加 BOM 让 Excel 自动识别 UTF-8
    const header = 'module\tkey\tlocale\tvalue';
    const sample1 = 'core\tcommon.save\tzh-CN\t保存';
    const sample2 = 'core\tcommon.save\ten-US\tSave';
    const sample3 = 'core\tcommon.cancel\tzh-CN\t取消';
    const sample4 = 'workspace\tconfirmDelete\ten-US\tAre you sure you want to delete?';
    const content = [header, sample1, sample2, sample3, sample4].join('\n');
    const blob = new Blob(['\uFEFF' + content], { type: 'text/tab-separated-values;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'i18n_import_template.tsv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    adapter.getMessage().success(t('templateDownloaded'));
  }, [t]);

  const localeOptions = locales.map((l) => ({
    label: `${l.code} (${l.native_name})`,
    value: l.code,
  }));

  const moduleOptions = modules.map((m) => ({
    label: `${m.name} (${m.key_count})`,
    value: m.name,
  }));

  const columns = [
    {
      title: t('key'),
      dataIndex: 'key',
      key: 'key',
      width: 200,
      render: (key: string) => <code style={{ fontSize: 12 }}>{key}</code>,
    },
    {
      title: t('module'),
      dataIndex: 'module',
      key: 'module',
      width: 120,
      render: (module: string) => <Tag>{module}</Tag>,
    },
    {
      title: t('locale'),
      dataIndex: 'locale',
      key: 'locale',
      width: 80,
    },
    {
      title: t('value'),
      dataIndex: 'value',
      key: 'value',
      ellipsis: true,
    },
    {
      title: t('updatedAt'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: t('delete'),
      key: 'action',
      width: 180,
      render: (_: unknown, record: TranslationEntry) => (
        <Space size="small">
          <AntButton
            type="link"
            size="small"
            onClick={() => handleEdit(record)}
          >
            {t('edit')}
          </AntButton>
          {record.status === 'draft' && (
            <AntButton
              type="link"
              size="small"
              icon={<CheckOutlined />}
              style={{ color: '#52c41a' }}
              onClick={() => handleReview(record, true)}
            >
              {t('approved')}
            </AntButton>
          )}
          <Popconfirm
            title={t('confirmDeleteTranslation')}
            onConfirm={() => handleDelete(record)}
            okText={t('delete')}
            cancelText={t('cancel')}
          >
            <AntButton
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              {t('delete')}
            </AntButton>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={t('title')}
        actions={
          <Space>
            <Button
              icon={<PlusOutlined />}
              onClick={() => setAddLocaleModalVisible(true)}
            >
              {t('addLocale')}
            </Button>
            <Button
              icon={<ImportOutlined />}
              onClick={() => setBulkImportModalVisible(true)}
            >
              {t('bulkImport')}
            </Button>
            <Button
              icon={<ExportOutlined />}
              onClick={handleExportOpen}
            >
              {t('export')}
            </Button>
            <Button
              icon={<ScanOutlined />}
              onClick={() => {
                setScanResult(null);
                setScanMissingModalVisible(true);
              }}
            >
              {t('scanMissing')}
            </Button>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={() => setAutoTranslateModalVisible(true)}
            >
              {t('autoTranslate')}
            </Button>
          </Space>
        }
      />

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Space>
              <span>{t('filterModule')}:</span>
              <AntSelect
                value={filterModule}
                onChange={setFilterModule}
                options={moduleOptions}
                placeholder={t('allModules')}
                allowClear
                style={{ width: 200 }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <span>{t('filterLocale')}:</span>
              <AntSelect
                value={filterLocale}
                onChange={setFilterLocale}
                options={localeOptions}
                placeholder={t('allLocales')}
                allowClear
                style={{ width: 200 }}
              />
            </Space>
          </Col>
          <Col>
            <Button type="primary" onClick={handleFilter}>
              {t('filter')}
            </Button>
          </Col>
        </Row>
      </Card>

      <Card>
        <AdvancedTable
          columns={columns}
          dataSource={translations}
          rowKey={(record) => `${record.key}-${record.module}-${record.locale}`}
          loading={loading}
          pagination={{
            current: currentPage,
            pageSize: currentPageSize,
            total,
            showSizeChanger: true,
            showTotal: (total) => t('totalItems', { count: total }),
          }}
          onChange={(pagination) => {
            const page = pagination.current || 1;
            const pageSize = pagination.pageSize || 20;
            setCurrentPage(page);
            setCurrentPageSize(pageSize);
            loadTranslations({
              module: filterModule,
              locale: filterLocale,
              page,
              page_size: pageSize,
            });
          }}
        />
      </Card>

      {/* Edit Translation Modal */}
      <Modal
        title={t('editTranslation')}
        open={editModalVisible}
        onOk={handleEditSubmit}
        onCancel={() => {
          setEditModalVisible(false);
          editForm.resetFields();
        }}
        okText={t('save')}
        cancelText={t('cancel')}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="key" label={t('key')}>
            <Input disabled />
          </Form.Item>
          <Form.Item name="module" label={t('module')}>
            <Input disabled />
          </Form.Item>
          <Form.Item name="locale" label={t('locale')}>
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="value"
            label={t('translationContent')}
            rules={[{ required: true, message: t('translationRequired') }]}
          >
            <Input.TextArea rows={4} placeholder={t('enterTranslation')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Auto Translate Modal */}
      <Modal
        title={t('autoTranslateTitle')}
        open={autoTranslateModalVisible}
        onOk={handleAutoTranslate}
        onCancel={() => {
          setAutoTranslateModalVisible(false);
          autoTranslateForm.resetFields();
        }}
        okText={t('startTranslate')}
        cancelText={t('cancel')}
      >
        <Alert
          message={t('autoTranslateHint')}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form form={autoTranslateForm} layout="vertical">
          <Form.Item
            name="module"
            label={t('module')}
            rules={[{ required: true, message: t('selectModuleRequired') }]}
          >
            <AntSelect
              options={moduleOptions}
              placeholder={t('selectModule')}
            />
          </Form.Item>
          <Form.Item
            name="source_locale"
            label={t('sourceLocale')}
            rules={[{ required: true, message: t('selectSourceRequired') }]}
            initialValue="zh-CN"
          >
            <AntSelect
              options={localeOptions}
              placeholder={t('selectSourceLocale')}
            />
          </Form.Item>
          <Form.Item
            name="target_locale"
            label={t('targetLocale')}
            rules={[{ required: true, message: t('selectTargetRequired') }]}
            initialValue="en-US"
          >
            <AntSelect
              options={localeOptions}
              placeholder={t('selectTargetLocale')}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Add Locale Modal */}
      <Modal
        title={t('addLocaleTitle')}
        open={addLocaleModalVisible}
        onOk={handleAddLocale}
        onCancel={() => {
          setAddLocaleModalVisible(false);
          addLocaleForm.resetFields();
        }}
        okText={t('addLocale')}
        cancelText={t('cancel')}
        width={520}
      >
        <Alert
          message={t('addLocaleHint')}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Text type="secondary">{t('quickSelect')}</Text>
        <div style={{ margin: '8px 0 16px' }}>
          <AntSelect
            placeholder={t('quickSelect')}
            style={{ width: '100%' }}
            onChange={handlePresetLocale}
            options={PRESET_LOCALES.map((p) => ({
              label: `${p.code} — ${p.name} (${p.native_name})`,
              value: p.code,
            }))}
          />
        </div>
        <Divider>{t('orManualInput')}</Divider>
        <Form form={addLocaleForm} layout="vertical">
          <Form.Item
            name="code"
            label={t('bcp47Code')}
            rules={[{ required: true, message: t('codeRequired') }]}
          >
            <Input placeholder={t('codePlaceholder')} />
          </Form.Item>
          <Form.Item
            name="name"
            label={t('englishName')}
            rules={[{ required: true, message: t('englishNameRequired') }]}
          >
            <Input placeholder={t('englishNamePlaceholder')} />
          </Form.Item>
          <Form.Item
            name="native_name"
            label={t('nativeName')}
            rules={[{ required: true, message: t('nativeNameRequired') }]}
          >
            <Input placeholder={t('nativeNamePlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Bulk Import Modal */}
      <Modal
        title={t('bulkImportTitle')}
        open={bulkImportModalVisible}
        onOk={handleBulkImport}
        onCancel={() => {
          setBulkImportModalVisible(false);
          bulkImportForm.resetFields();
        }}
        okText={t('bulkImport')}
        cancelText={t('cancel')}
        width={640}
      >
        <Alert
          message={t('bulkFormatHint')}
          description={
            <div>
              <div style={{ fontFamily: 'monospace', fontSize: 12, marginTop: 4 }}>
                {t('bulkFormatExample')}
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#999', marginTop: 2 }}>
                {t('bulkSampleLine')}
              </div>
              <AntButton
                type="link"
                size="small"
                icon={<DownloadOutlined />}
                onClick={handleDownloadTemplate}
                style={{ padding: 0, marginTop: 8 }}
              >
                {t('downloadTemplate')}
              </AntButton>
            </div>
          }
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form form={bulkImportForm} layout="vertical">
          <Form.Item label={t('uploadFile')}>
            <Upload.Dragger
              accept=".tsv,.txt,.csv"
              showUploadList={false}
              beforeUpload={(file) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                  const text = e.target?.result as string;
                  bulkImportForm.setFieldsValue({ data: text });
                  adapter.getMessage().info(t('fileLoaded'));
                };
                reader.readAsText(file, 'UTF-8');
                return false; // 阻止自动上传
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">{t('uploadHint')}</p>
              <p className="ant-upload-hint">{t('uploadHintSub')}</p>
            </Upload.Dragger>
          </Form.Item>
          <Form.Item
            name="data"
            label={t('orPasteData')}
            rules={[{ required: true, message: t('dataRequired') }]}
          >
            <Input.TextArea
              rows={10}
              placeholder={t('pasteData')}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Export Modal */}
      <Modal
        title={t('exportTitle')}
        open={exportModalVisible}
        onOk={handleExportConfirm}
        onCancel={() => {
          setExportModalVisible(false);
          exportForm.resetFields();
        }}
        okText={t('export')}
        cancelText={t('cancel')}
      >
        <Form form={exportForm} layout="vertical">
          <Form.Item name="module" label={t('module')}>
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="locale"
            label={t('locale')}
            rules={[{ required: true, message: t('localeRequired') }]}
          >
            <AntSelect
              options={localeOptions}
              placeholder={t('selectExportLocale')}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Scan Missing Modal */}
      <Modal
        title={t('scanMissingTitle')}
        open={scanMissingModalVisible}
        onCancel={() => {
          setScanMissingModalVisible(false);
          scanMissingForm.resetFields();
          setScanResult(null);
        }}
        footer={[
          <AntButton key="cancel" onClick={() => {
            setScanMissingModalVisible(false);
            scanMissingForm.resetFields();
            setScanResult(null);
          }}>
            {t('cancel')}
          </AntButton>,
          <AntButton key="scan" type="primary" onClick={handleScanMissing} loading={loading}>
            {t('scan')}
          </AntButton>,
        ]}
        width={520}
      >
        <Form form={scanMissingForm} layout="vertical">
          <Form.Item
            name="module"
            label={t('module')}
            rules={[{ required: true, message: t('selectModuleRequired') }]}
          >
            <AntSelect
              options={moduleOptions}
              placeholder={t('selectModule')}
            />
          </Form.Item>
          <Form.Item
            name="locale"
            label={t('targetLocale')}
            rules={[{ required: true, message: t('selectTargetRequired') }]}
          >
            <AntSelect
              options={localeOptions}
              placeholder={t('selectTargetLocale')}
            />
          </Form.Item>
        </Form>
        {scanResult && (
          <div style={{ marginTop: 16 }}>
            {scanResult.missing === 0 ? (
              <Alert title={t('noMissing')} type="success" showIcon />
            ) : (
              <div>
                <Alert
                  title={t('scanComplete', { total: scanResult.total, missing: scanResult.missing })}
                  type="warning"
                  showIcon
                  style={{ marginBottom: 12 }}
                />
                <Text type="secondary">{t('missingKey')}:</Text>
                <div style={{ marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
                  {scanResult.missing_keys.map((key) => (
                    <Tag key={key} style={{ marginBottom: 4 }}>
                      <code style={{ fontSize: 12 }}>{key}</code>
                    </Tag>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
