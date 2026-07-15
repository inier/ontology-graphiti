import type { FC, CSSProperties } from 'react';
import adapter from '../adapter';
import type { ButtonProps } from '../adapter';

interface AtomButtonProps extends Omit<ButtonProps, 'className' | 'style'> {
  className?: string;
  style?: CSSProperties;
}

const AdapterButton = adapter.getButton();

const Button: FC<AtomButtonProps> = (props) => {
  return <AdapterButton {...props} />;
};

export default Button;
