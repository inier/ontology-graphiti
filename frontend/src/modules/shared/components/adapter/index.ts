export type { UIAdapter, ButtonProps, InputProps, TableProps, ModalProps, FormProps, SelectProps, TagProps, TooltipProps, MessageInstance, NotificationInstance } from './UIAdapter.ts';
export { AntDesignAdapter } from './AntDesignAdapter.tsx';

import { AntDesignAdapter } from './AntDesignAdapter.tsx';

const adapter = new AntDesignAdapter();
export default adapter;
