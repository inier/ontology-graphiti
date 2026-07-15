import { useState, useEffect } from 'react';
import { BREAKPOINTS, BREAKPOINT_NAMES } from '../styles/breakpoints.ts';
import type { BreakpointKey } from '../styles/breakpoints.ts';

interface ResponsiveState {
  breakpoint: BreakpointKey;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isXs: boolean;
  isSm: boolean;
  isMd: boolean;
  isLg: boolean;
  isXl: boolean;
  isXxl: boolean;
}

function getCurrentBreakpoint(): BreakpointKey {
  const width = window.innerWidth;
  let current: BreakpointKey = 'xs';
  for (const key of BREAKPOINT_NAMES) {
    if (width >= BREAKPOINTS[key]) {
      current = key;
    }
  }
  return current;
}

export function useResponsive(): ResponsiveState {
  const [breakpoint, setBreakpoint] = useState<BreakpointKey>(getCurrentBreakpoint);

  useEffect(() => {
    const handleResize = () => {
      setBreakpoint(getCurrentBreakpoint());
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    breakpoint,
    isMobile: breakpoint === 'xs' || breakpoint === 'sm',
    isTablet: breakpoint === 'md',
    isDesktop: breakpoint === 'lg' || breakpoint === 'xl' || breakpoint === 'xxl',
    isXs: breakpoint === 'xs',
    isSm: breakpoint === 'sm',
    isMd: breakpoint === 'md',
    isLg: breakpoint === 'lg',
    isXl: breakpoint === 'xl',
    isXxl: breakpoint === 'xxl',
  };
}
