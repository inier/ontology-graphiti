import type { FC, ReactNode, CSSProperties } from 'react';
import { Form } from 'antd';
import adapter from '../adapter';
import type { InputProps, SelectProps } from '../adapter';

interface FormFieldProps {
  label?: string;
  name?: string;
  required?: boolean;
  message?: string;
  type?: 'input' | 'select' | 'textarea' | 'password';
  inputProps?: InputProps;
  selectProps?: SelectProps;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

const AdapterInput = adapter.getInput();
const AdapterSelect = adapter.getSelect();

const FormField: FC<FormFieldProps> = ({
  label,
  name,
  required,
  message,
  type = 'input',
  inputProps,
  selectProps,
  className,
  style,
  children,
}) => {
  const rules = required ? [{ required: true, message: message || `${label || name || 'Field'} is required` }] : undefined;

  const renderControl = () => {
    if (children) return children;

    if (type === 'select') {
      return <AdapterSelect {...selectProps} options={selectProps?.options ?? []} />;
    }

    return <AdapterInput {...inputProps} />;
  };

  return (
    <Form.Item label={label} name={name} rules={rules} className={className} style={style}>
      {renderControl()}
    </Form.Item>
  );
};

export default FormField;
