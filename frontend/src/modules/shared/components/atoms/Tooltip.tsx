import type { FC, CSSProperties } from 'react';
import adapter from '../adapter';
import type { TooltipProps } from '../adapter';

interface AtomTooltipProps extends Omit<TooltipProps, never> {
  className?: string;
  style?: CSSProperties;
}

const AdapterTooltip = adapter.getTooltip();

const Tooltip: FC<AtomTooltipProps> = (props) => {
  return <AdapterTooltip {...props} />;
};

export default Tooltip;
