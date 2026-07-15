import { useState, useEffect } from 'react';

export type DeviceType = 'mobile' | 'tablet' | 'desktop';

export interface Breakpoint {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isLargeDesktop: boolean;
  deviceType: DeviceType;
  width: number;
}

export function useBreakpoint(): Breakpoint {
  const [width, setWidth] = useState(
    typeof window !== 'undefined' ? window.innerWidth : 1280
  );

  useEffect(() => {
    const handleResize = () => {
      setWidth(window.innerWidth);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isMobile = width < 576;
  const isTablet = width >= 576 && width < 1024;
  const isDesktop = width >= 1024 && width < 1440;
  const isLargeDesktop = width >= 1440;

  let deviceType: DeviceType = 'desktop';
  if (isMobile) deviceType = 'mobile';
  else if (isTablet) deviceType = 'tablet';

  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeDesktop,
    deviceType,
    width,
  };
}

export const BREAKPOINTS = {
  xs: 375,
  sm: 576,
  md: 768,
  lg: 1024,
  xl: 1280,
  xxl: 1440,
  xxxl: 1920,
} as const;

export const RESPONSE_SAFE_AREA = {
  mobile: 16,
  tablet: 24,
  desktop: 32,
} as const;
