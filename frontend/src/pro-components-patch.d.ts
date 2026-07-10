declare module '@ant-design/pro-components' {
  export { ProTable } from '@ant-design/pro-components/es/table';
  export type {
    ActionType,
    ProColumns,
    ProColumnType,
    ProTableProps,
    RequestData,
  } from '@ant-design/pro-components/es/table';
  export type { OptionConfig } from '@ant-design/pro-components/es/table/components/ToolBar';

  export { ProCard, CheckCard } from '@ant-design/pro-components/es/card';
  export type { ProCardProps, CheckCardProps } from '@ant-design/pro-components/es/card';

  export { ProDescriptions } from '@ant-design/pro-components/es/descriptions';
  export type { ProDescriptionsProps } from '@ant-design/pro-components/es/descriptions';

  export {
    ProForm,
    ProFormGroup,
    ModalForm,
    DrawerForm,
    QueryFilter,
    LightFilter,
    LoginForm,
    StepsForm,
    LoginFormPage,
  } from '@ant-design/pro-components/es/form';
  export type {
    ProFormProps,
    ModalFormProps,
    DrawerFormProps,
    QueryFilterProps,
    LightFilterProps,
    LoginFormProps,
    StepsFormProps,
    StepFormProps,
  } from '@ant-design/pro-components/es/form';

  export {
    DrawerForm as DrawerFormInner,
    LightFilter as LightFilterInner,
    LoginForm as LoginFormInner,
    LoginFormPage as LoginFormPageInner,
    ModalForm as ModalFormInner,
    QueryFilter as QueryFilterInner,
    StepsForm as StepsFormInner,
  } from '@ant-design/pro-components/es/form/layouts';
}
