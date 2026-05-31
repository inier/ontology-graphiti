import type { ReactElement } from 'react';
import { Button, Input, Table, Modal, Form, Select, message, notification } from 'antd';
import type { UIAdapter, ButtonProps, InputProps, TableProps, ModalProps, FormProps, SelectProps, MessageInstance, NotificationInstance } from './UIAdapter.ts';

function AntButton(props: ButtonProps) {
  const { children, onClick, type, disabled, loading, icon, size, danger, className } = props;
  return (
    <Button
      onClick={onClick}
      type={type}
      disabled={disabled}
      loading={loading}
      icon={icon}
      size={size}
      danger={danger}
      className={className}
    >
      {children}
    </Button>
  );
}

function AntInput(props: InputProps) {
  const { value, onChange, placeholder, disabled, size, status, className } = props;
  return (
    <Input
      value={value}
      onChange={onChange ? (e) => onChange(e.target.value) : undefined}
      placeholder={placeholder}
      disabled={disabled}
      size={size}
      status={status}
      className={className}
    />
  );
}

function AntTable<T = any>(props: TableProps<T>): ReactElement {
  const { columns, dataSource, loading, pagination, onChange, rowKey, className } = props;
  return (
    <Table<T>
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      pagination={pagination}
      onChange={onChange as any}
      rowKey={rowKey}
      className={className}
    />
  );
}

function AntModal(props: ModalProps) {
  const { open, title, onOk, onCancel, children, width, confirmLoading, className } = props;
  return (
    <Modal
      open={open}
      title={title}
      onOk={onOk}
      onCancel={onCancel}
      width={width}
      confirmLoading={confirmLoading}
      className={className}
    >
      {children}
    </Modal>
  );
}

function AntForm(props: FormProps) {
  const { onFinish, children, layout, className } = props;
  return (
    <Form onFinish={onFinish} layout={layout} className={className}>
      {children}
    </Form>
  );
}

function AntSelect(props: SelectProps) {
  const { value, onChange, options, placeholder, disabled, mode, className } = props;
  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      disabled={disabled}
      mode={mode}
      className={className}
    />
  );
}

const antMessage: MessageInstance = {
  success: (content: string) => message.success(content),
  error: (content: string) => message.error(content),
  warning: (content: string) => message.warning(content),
  info: (content: string) => message.info(content),
};

const antNotification: NotificationInstance = {
  success: (args) => notification.success(args),
  error: (args) => notification.error(args),
  warning: (args) => notification.warning(args),
  info: (args) => notification.info(args),
};

export class AntDesignAdapter implements UIAdapter {
  getButton() {
    return AntButton;
  }

  getInput() {
    return AntInput;
  }

  getTable<T = any>() {
    return (props: TableProps<T>) => AntTable<T>(props);
  }

  getModal() {
    return AntModal;
  }

  getForm() {
    return AntForm;
  }

  getSelect() {
    return AntSelect;
  }

  getMessage(): MessageInstance {
    return antMessage;
  }

  getNotification(): NotificationInstance {
    return antNotification;
  }
}
