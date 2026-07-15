import type { ReactElement } from 'react';
import { Button, Input, Modal, Form, Select, Tag, Tooltip, message, notification } from 'antd';
import type { UIAdapter, ButtonProps, InputProps, TableProps, ModalProps, FormProps, SelectProps, TagProps, TooltipProps, MessageInstance, NotificationInstance } from './UIAdapter.ts';
import { AdvancedTable } from '@/modules/shared';

function AntButton(props: ButtonProps) {
  const { children, onClick, type, disabled, loading, icon, size, danger, className, style } = props;
  return (
    <Button
      onClick={onClick as React.MouseEventHandler}
      type={type}
      disabled={disabled}
      loading={loading}
      icon={icon}
      size={size}
      danger={danger}
      className={className}
      style={style}
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
    <AdvancedTable<T>
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

function AntTag(props: TagProps) {
  const { color, children, className } = props;
  return (
    <Tag color={color} className={className}>
      {children}
    </Tag>
  );
}

function AntTooltip(props: TooltipProps) {
  const { title, children, placement } = props;
  return (
    <Tooltip title={title} placement={placement}>
      {children}
    </Tooltip>
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

  getTable(): <T = any>(props: TableProps<T>) => ReactElement {
    return <T = any>(props: TableProps<T>) => AntTable<T>(props);
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

  getTag() {
    return AntTag;
  }

  getTooltip() {
    return AntTooltip;
  }

  getMessage(): MessageInstance {
    return antMessage;
  }

  getNotification(): NotificationInstance {
    return antNotification;
  }
}
