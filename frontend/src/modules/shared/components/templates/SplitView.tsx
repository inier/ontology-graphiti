import type { FC, ReactNode, CSSProperties } from 'react';
import { useState, useCallback, useRef, useEffect } from 'react';

interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
  defaultSplit?: number;
  minLeft?: number;
  minRight?: number;
  direction?: 'horizontal' | 'vertical';
  className?: string;
  style?: CSSProperties;
}

const SplitView: FC<SplitViewProps> = ({
  left,
  right,
  defaultSplit = 50,
  minLeft = 100,
  minRight = 100,
  direction = 'horizontal',
  className,
  style,
}) => {
  const [splitPercent, setSplitPercent] = useState(defaultSplit);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  }, [direction]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      let percent: number;

      if (direction === 'horizontal') {
        percent = ((e.clientX - rect.left) / rect.width) * 100;
      } else {
        percent = ((e.clientY - rect.top) / rect.height) * 100;
      }

      const minLeftPercent = minLeft / (direction === 'horizontal' ? rect.width : rect.height) * 100;
      const minRightPercent = minRight / (direction === 'horizontal' ? rect.width : rect.height) * 100;

      percent = Math.max(minLeftPercent, Math.min(100 - minRightPercent, percent));
      setSplitPercent(percent);
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [direction, minLeft, minRight]);

  const isHorizontal = direction === 'horizontal';

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        display: 'flex',
        flexDirection: isHorizontal ? 'row' : 'column',
        height: '100%',
        ...style,
      }}
    >
      <div style={{ [isHorizontal ? 'width' : 'height']: `${splitPercent}%`, overflow: 'auto' }}>
        {left}
      </div>
      <div
        onMouseDown={handleMouseDown}
        style={{
          [isHorizontal ? 'width' : 'height']: 4,
          cursor: isHorizontal ? 'col-resize' : 'row-resize',
          backgroundColor: '#f0f0f0',
          transition: 'background-color 0.2s',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.backgroundColor = '#1677ff'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.backgroundColor = '#f0f0f0'; }}
      />
      <div style={{ flex: 1, overflow: 'auto' }}>
        {right}
      </div>
    </div>
  );
};

export default SplitView;
