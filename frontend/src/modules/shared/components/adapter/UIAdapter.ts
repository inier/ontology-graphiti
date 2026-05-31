import type { ComponentType, ReactElement, ReactNode } from 'react';

export interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link';
  disabled?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  size?: 'small' | 'middle' | 'large';
  danger?: boolean;
  className?: string;
}

export interface InputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  size?: 'small' | 'middle' | 'large';
  status?: 'error' | 'warning';
  className?: string;
}

export interface TableProps<T = any> {
  columns: any[];
  dataSource: T[];
  loading?: boolean;
  pagination?: any;
  onChange?: (pagination: any, filters: any, sorter: any) => void;
  rowKey?: string | ((record: T) => string);
  className?: string;
}

export interface ModalProps {
  open: boolean;
  title?: string;
  onOk?: () => void;
  onCancel?: () => void;
  children: ReactNode;
  width?: number;
  confirmLoading?: boolean;
  className?: string;
}

export interface FormProps {
  onFinish?: (values: any) => void;
  children: ReactNode;
  layout?: 'horizontal' | 'vertical' | 'inline';
  className?: string;
}

export interface SelectProps {
  value?: any;
  onChange?: (value: any) => void;
  options: { label: string; value: any }[];
  placeholder?: string;
  disabled?: boolean;
  mode?: 'multiple' | 'tags';
  className?: string;
}

export interface MessageInstance {
  success: (content: string) => void;
  error: (content: string) => void;
  warning: (content: string) => void;
  info: (content: string) => void;
}

export interface NotificationInstance {
  success: (args: { message: string; description?: string }) => void;
  error: (args: { message: string; description?: string }) => void;
  warning: (args: { message: string; description?: string }) => void;
  info: (args: { message: string; description?: string }) => void;
}

export interface UIAdapter {
  getButton(): ComponentType<ButtonProps>;
  getInput(): ComponentType<InputProps>;
  getTable(): <T = any>(props: TableProps<T>) => ReactElement;
  getModal(): ComponentType<ModalProps>;
  getForm(): ComponentType<FormProps>;
  getSelect(): ComponentType<SelectProps>;
  getMessage(): MessageInstance;
  getNotification(): NotificationInstance;
}
