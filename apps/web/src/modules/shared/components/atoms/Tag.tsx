import type { FC, CSSProperties } from 'react';
import adapter from '../adapter';
import type { TagProps } from '../adapter';

interface AtomTagProps extends Omit<TagProps, 'className'> {
  className?: string;
  style?: CSSProperties;
}

const AdapterTag = adapter.getTag();

const Tag: FC<AtomTagProps> = (props) => {
  return <AdapterTag {...props} />;
};

export default Tag;
