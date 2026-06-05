import type { FC, CSSProperties } from 'react';
import adapter from '../adapter';
import type { InputProps } from '../adapter';

interface AtomInputProps extends Omit<InputProps, 'className'> {
  className?: string;
  style?: CSSProperties;
}

const AdapterInput = adapter.getInput();

const Input: FC<AtomInputProps> = (props) => {
  return <AdapterInput {...props} />;
};

export default Input;
