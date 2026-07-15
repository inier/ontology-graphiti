import type { FC, ReactNode, CSSProperties } from 'react';
import adapter from '../adapter';

interface FormFieldConfig {
  name: string;
  label: string;
  type?: 'input' | 'select' | 'textarea' | 'password';
  required?: boolean;
  message?: string;
  options?: { label: string; value: string | number }[];
  placeholder?: string;
  defaultValue?: string | number;
}

interface FormPanelProps {
  fields: FormFieldConfig[];
  onFinish?: (values: Record<string, unknown>) => void;
  layout?: 'horizontal' | 'vertical' | 'inline';
  title?: string;
  submitText?: string;
  loading?: boolean;
  extra?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const AdapterForm = adapter.getForm();
const AdapterInput = adapter.getInput();
const AdapterSelect = adapter.getSelect();
const AdapterButton = adapter.getButton();

const FormPanel: FC<FormPanelProps> = ({
  fields,
  onFinish,
  layout = 'vertical',
  title,
  submitText = 'Submit',
  loading = false,
  extra,
  className,
  style,
}) => {
  return (
    <div className={className} style={style}>
      {title && <h3 style={{ marginBottom: 16 }}>{title}</h3>}
      <AdapterForm onFinish={onFinish} layout={layout}>
        {fields.map((field) => {
          return (
            <div key={field.name} style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
                {field.label}
                {field.required && <span style={{ color: 'red', marginLeft: 4 }}>*</span>}
              </label>
              {field.type === 'select' ? (
                <AdapterSelect
                  options={field.options || []}
                  placeholder={field.placeholder}
                />
              ) : (
                <AdapterInput
                  placeholder={field.placeholder}
                />
              )}
            </div>
          );
        })}
        <div style={{ display: 'flex', gap: 8 }}>
          <AdapterButton type="primary" loading={loading}>
            {submitText}
          </AdapterButton>
          {extra}
        </div>
      </AdapterForm>
    </div>
  );
};

export default FormPanel;
