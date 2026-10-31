import type { ReactElement } from 'react';
import { message, notification } from 'antd';
import type {
  UIAdapter,
  TableProps,
  MessageInstance,
  NotificationInstance,
} from './UIAdapter.ts';
import {
  AntButton,
  AntInput,
  AntTable,
  AntModal,
  AntForm,
  AntSelect,
  AntTag,
  AntTooltip,
} from './AntDesignAdapter.components';

/**
 * antd 实现的 UI 适配器。
 *
 * 展示组件放在 `AntDesignAdapter.components.tsx`，本文件不声明组件，
 * 只在 `getXxx()` 里返回它们，保证 react-refresh 边界清晰。
 */

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

  getTable(): <T extends object = Record<string, unknown>>(props: TableProps<T>) => ReactElement {
    return <T extends object = Record<string, unknown>>(props: TableProps<T>) => AntTable<T>(props);
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
