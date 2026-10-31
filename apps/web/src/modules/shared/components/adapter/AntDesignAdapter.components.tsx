import type { ReactElement } from 'react';
import { Button, Input, Modal, Form, Select, Tag, Tooltip } from 'antd';
import type {
  ButtonProps,
  InputProps,
  TableProps,
  ModalProps,
  FormProps,
  SelectProps,
  TagProps,
  TooltipProps,
} from './UIAdapter.ts';
import { AdvancedTable } from '@/modules/shared';

/**
 * antd 适配用的展示组件集合。
 *
 * 单独成文件的原因：`AntDesignAdapter.tsx` 只导出适配器类（非组件），
 * 若把组件定义混在同一模块，react-refresh 会退化为整页刷新。
 */

export function AntButton(props: ButtonProps) {
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

export function AntInput(props: InputProps) {
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

export function AntTable<T extends object = Record<string, unknown>>(props: TableProps<T>): ReactElement {
  const { columns, dataSource, loading, pagination, onChange, rowKey, className } = props;
  return (
    <AdvancedTable<T>
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      pagination={pagination}
      onChange={onChange}
      rowKey={rowKey}
      className={className}
    />
  );
}

export function AntModal(props: ModalProps) {
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

export function AntForm(props: FormProps) {
  const { onFinish, children, layout, className } = props;
  return (
    <Form onFinish={onFinish} layout={layout} className={className}>
      {children}
    </Form>
  );
}

export function AntSelect(props: SelectProps) {
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

export function AntTag(props: TagProps) {
  const { color, children, className } = props;
  return (
    <Tag color={color} className={className}>
      {children}
    </Tag>
  );
}

export function AntTooltip(props: TooltipProps) {
  const { title, children, placement } = props;
  return (
    <Tooltip title={title} placement={placement}>
      {children}
    </Tooltip>
  );
}
