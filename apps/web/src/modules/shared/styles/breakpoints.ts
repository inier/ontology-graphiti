export const BREAKPOINTS = {
  xs: 0,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
} as const;

export type BreakpointKey = keyof typeof BREAKPOINTS;

export const BREAKPOINT_NAMES: BreakpointKey[] = ['xs', 'sm', 'md', 'lg', 'xl', 'xxl'];

export const mediaQueries = {
  xs: `@media (max-width: ${BREAKPOINTS.sm - 1}px)`,
  sm: `@media (min-width: ${BREAKPOINTS.sm}px)`,
  md: `@media (min-width: ${BREAKPOINTS.md}px)`,
  lg: `@media (min-width: ${BREAKPOINTS.lg}px)`,
  xl: `@media (min-width: ${BREAKPOINTS.xl}px)`,
  xxl: `@media (min-width: ${BREAKPOINTS.xxl}px)`,
} as const;
