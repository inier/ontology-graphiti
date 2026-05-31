import { useState, useEffect, useCallback } from 'react';
import { Card, Table, Tag, Modal, Form, Input, Select as AntSelect, Space, Button as AntButton, Row, Col, message } from 'antd';
import { TranslationOutlined, CheckOutlined, CloseOutlined, RobotOutlined } from '@ant-design/icons';
import adapter from '../../shared/components/adapter';
import { PageHeader } from '../../shared/components/PageHeader';
import { useI18nAdminStore } from '../stores/i18nAdminStore';
import type { TranslationEntry } from '../services/i18nApi';

const Button = adapter.getButton();

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  reviewed: 'blue',
  approved: 'green',
};

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  reviewed: '已审核',
  approved: '已批准',
};

export function I18nAdminPage() {
  const {
    translations,
    modules,
    locales,
    currentLocale,
    total,
    loading,
    loadTranslations,
    saveTranslation,
    autoTranslate,
    loadModules,
    loadLocales,
    setCurrentLocale,
  } = useI18nAdminStore();

  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingEntry, setEditingEntry] = useState<TranslationEntry | null>(null);
  const [editForm] = Form.useForm();
  const [filterModule, setFilterModule] = useState<string | undefined>();
  const [filterLocale, setFilterLocale] = useState<string | undefined>();
  const [autoTranslateModalVisible, setAutoTranslateModalVisible] = useState(false);
  const [autoTranslateForm] = Form.useForm();

  useEffect(() => {
    loadModules();
    loadLocales();
    loadTranslations({ module: filterModule, locale: filterLocale });
  }, []);

  const handleFilter = useCallback(() => {
    loadTranslations({ module: filterModule, locale: filterLocale });
  }, [filterModule, filterLocale, loadTranslations]);

  const handleEdit = useCallback((entry: TranslationEntry) => {
    setEditingEntry(entry);
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
      setEditingEntry(null);
      adapter.getMessage().success('保存成功');
      handleFilter();
    } catch {
      // validation error
    }
  }, [editForm, saveTranslation, handleFilter]);

  const handleReview = useCallback(async (entry: TranslationEntry, approved: boolean) => {
    await saveTranslation({
      key: entry.key,
      module: entry.module,
      locale: entry.locale,
      value: entry.value,
    });
    adapter.getMessage().success(approved ? '已批准' : '已拒绝');
    handleFilter();
  }, [saveTranslation, handleFilter]);

  const handleAutoTranslate = useCallback(async () => {
    try {
      const values = await autoTranslateForm.validateFields();
      await autoTranslate(values.module, values.source_locale, values.target_locale);
      setAutoTranslateModalVisible(false);
      autoTranslateForm.resetFields();
      adapter.getMessage().success('自动翻译完成');
      handleFilter();
    } catch {
      // validation error
    }
  }, [autoTranslateForm, autoTranslate, handleFilter]);

  const columns = [
    {
      title: 'Key',
      dataIndex: 'key',
      key: 'key',
      width: 200,
      render: (key: string) => <code style={{ fontSize: 12 }}>{key}</code>,
    },
    {
      title: '模块',
      dataIndex: 'module',
      key: 'module',
      width: 120,
      render: (module: string) => <Tag>{module}</Tag>,
    },
    {
      title: '语言',
      dataIndex: 'locale',
      key: 'locale',
      width: 80,
    },
    {
      title: '翻译内容',
      dataIndex: 'value',
      key: 'value',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={STATUS_COLORS[status] || 'default'}>
          {STATUS_LABELS[status] || status}
        </Tag>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: TranslationEntry) => (
        <Space size="small">
          <AntButton
            type="link"
            size="small"
            onClick={() => handleEdit(record)}
          >
            编辑
          </AntButton>
          {record.status === 'draft' && (
            <>
              <AntButton
                type="link"
                size="small"
                icon={<CheckOutlined />}
                style={{ color: '#52c41a' }}
                onClick={() => handleReview(record, true)}
              >
                批准
              </AntButton>
              <AntButton
                type="link"
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={() => handleReview(record, false)}
              >
                拒绝
              </AntButton>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <PageHeader
        title="i18n 管理"
        actions={
          <Button
            type="primary"
            icon={<RobotOutlined />}
            onClick={() => setAutoTranslateModalVisible(true)}
          >
            LLM 自动翻译
          </Button>
        }
      />

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Space>
              <span>模块:</span>
              <AntSelect
                value={filterModule}
                onChange={setFilterModule}
                options={modules.map((m) => ({ label: m.name, value: m.name }))}
                placeholder="全部模块"
                allowClear
                style={{ width: 160 }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <span>语言:</span>
              <AntSelect
                value={filterLocale}
                onChange={setFilterLocale}
                options={locales.map((l) => ({ label: l, value: l }))}
                placeholder="全部语言"
                allowClear
                style={{ width: 120 }}
              />
            </Space>
          </Col>
          <Col>
            <Button type="primary" onClick={handleFilter}>
              筛选
            </Button>
          </Col>
        </Row>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={translations}
          rowKey={(record) => `${record.key}-${record.module}-${record.locale}`}
          loading={loading}
          pagination={{
            total,
            pageSize: 20,
            showTotal: (t) => `共 ${t} 条`,
          }}
          onChange={(pagination) => {
            loadTranslations({
              module: filterModule,
              locale: filterLocale,
              page: pagination.current,
              page_size: pagination.pageSize,
            });
          }}
        />
      </Card>

      <Modal
        title="编辑翻译"
        open={editModalVisible}
        onOk={handleEditSubmit}
        onCancel={() => {
          setEditModalVisible(false);
          editForm.resetFields();
          setEditingEntry(null);
        }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="key" label="Key">
            <Input disabled />
          </Form.Item>
          <Form.Item name="module" label="模块">
            <Input disabled />
          </Form.Item>
          <Form.Item name="locale" label="语言">
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="value"
            label="翻译内容"
            rules={[{ required: true, message: '请输入翻译内容' }]}
          >
            <Input.TextArea rows={4} placeholder="请输入翻译内容" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="LLM 自动翻译"
        open={autoTranslateModalVisible}
        onOk={handleAutoTranslate}
        onCancel={() => {
          setAutoTranslateModalVisible(false);
          autoTranslateForm.resetFields();
        }}
        okText="开始翻译"
        cancelText="取消"
      >
        <Form form={autoTranslateForm} layout="vertical">
          <Form.Item
            name="module"
            label="模块"
            rules={[{ required: true, message: '请选择模块' }]}
          >
            <AntSelect
              options={modules.map((m) => ({ label: m.name, value: m.name }))}
              placeholder="选择模块"
            />
          </Form.Item>
          <Form.Item
            name="source_locale"
            label="源语言"
            rules={[{ required: true, message: '请选择源语言' }]}
            initialValue="zh-CN"
          >
            <AntSelect
              options={locales.map((l) => ({ label: l, value: l }))}
              placeholder="选择源语言"
            />
          </Form.Item>
          <Form.Item
            name="target_locale"
            label="目标语言"
            rules={[{ required: true, message: '请选择目标语言' }]}
            initialValue="en-US"
          >
            <AntSelect
              options={locales.map((l) => ({ label: l, value: l }))}
              placeholder="选择目标语言"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
