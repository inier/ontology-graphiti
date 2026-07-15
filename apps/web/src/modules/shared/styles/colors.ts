/* ============================================================
   ODAP v2 Color Constants
   Mirrors the design token system from global.css
   ============================================================ */

export const colors = {
  /* Primary: Indigo scale */
  primary:       '#4F46E5',
  primaryLight:  '#818CF8',
  primaryLighter:'#C7D2FE',
  primaryDark:   '#4338CA',

  /* Accent: Violet scale */
  accent:        '#8B5CF6',
  accentLight:   '#A78BFA',

  /* Semantic */
  secondary:     '#10B981',
  warning:       '#F59E0B',
  danger:        '#EF4444',
  info:          '#06B6D4',

  /* Brand gradient */
  gradientBrand: 'linear-gradient(135deg, #4F46E5, #8B5CF6)',

  /* Backgrounds */
  background:    '#F8F9FC',
  darkSidebar:   'linear-gradient(180deg, #1E1B4B, #0F0F1A)',

  /* Text */
  textPrimary:   '#1F2937',
  textSecondary: '#6B7280',
  textTertiary:  '#9CA3AF',

  /* Borders */
  border:        '#E5E7EB',
  borderDark:    '#2D2D4A',

  /* Base */
  white:         '#FFFFFF',
  black:         '#0F0F1A',
} as const;

export const entityColors: Record<string, string> = {
  Unit:         '#4F46E5',  /* Indigo */
  Equipment:    '#10B981',  /* Emerald */
  Location:     '#F59E0B',  /* Amber */
  Event:        '#EF4444',  /* Red */
  Organization: '#8B5CF6',  /* Violet */
};

export const relationColors: Record<string, string> = {
  located_at:         '#6B7280',  /* Gray */
  engaged_with:       '#EF4444',  /* Red */
  supports:           '#10B981',  /* Emerald */
  opposes:            '#EF4444',  /* Red */
  attached_to:        '#4F46E5',  /* Indigo */
  communicates_with:  '#8B5CF6',  /* Violet */
};

export const sideColors: Record<string, string> = {
  red:     '#EF4444',
  blue:    '#4F46E5',
  neutral: '#6B7280',
};
