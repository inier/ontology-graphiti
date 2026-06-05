import type { FC, ReactNode, CSSProperties } from 'react';
import adapter from '../adapter';
import type { ModalProps } from '../adapter';

interface MoleculeModalProps extends Omit<ModalProps, 'className'> {
  okText?: string;
  cancelText?: string;
  footer?: ReactNode;
  destroyOnClose?: boolean;
  className?: string;
  style?: CSSProperties;
}

const AdapterModal = adapter.getModal();

const Modal: FC<MoleculeModalProps> = ({
  okText,
  cancelText,
  footer,
  destroyOnClose,
  className,
  style,
  ...rest
}) => {
  void okText;
  void cancelText;
  void footer;
  void destroyOnClose;
  void style;
  return <AdapterModal {...rest} className={className} />;
};

export default Modal;
