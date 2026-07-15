/* ============================================================
 * Color Theme CSS Variable Manager
 *
 * Sets ODAP custom CSS properties on <html> (inline style)
 * when colorTheme changes. Only manages --odap-color-* and
 * --odap-gradient-* variables used by global.css overrides.
 *
 * Ant Design 6 components are themed via ConfigProvider
 * with cssVar: true + token.colorPrimary (official approach).
 * ============================================================ */

interface ColorPalette {
  primary: Record<string, string>;
  accent: Record<string, string>;
  glowRgba: string;
  sidebar: { gradientStart: string; gradientEnd: string };
  logoAccent: { light: string; dark: string };
}

const PALETTES: Record<string, ColorPalette> = {
  indigo: {
    primary: {
      '50': '#EEF2FF', '100': '#E0E7FF', '200': '#C7D2FE',
      '300': '#A5B4FC', '400': '#818CF8', '500': '#6366F1',
      '600': '#4F46E5', '700': '#4338CA', '800': '#3730A3',
      '900': '#312E81',
    },
    accent: {
      '50': '#F5F3FF', '100': '#EDE9FE', '200': '#DDD6FE',
      '300': '#C4B5FD', '400': '#A78BFA', '500': '#8B5CF6',
      '600': '#7C3AED',
    },
    glowRgba: '99,102,241',
    sidebar: { gradientStart: '#1E1B4B', gradientEnd: '#0F0F1A' },
    logoAccent: { light: '#818CF8', dark: '#A78BFA' },
  },
  blue: {
    primary: {
      '50': '#EFF6FF', '100': '#DBEAFE', '200': '#BFDBFE',
      '300': '#93C5FD', '400': '#60A5FA', '500': '#3B82F6',
      '600': '#2563EB', '700': '#1D4ED8', '800': '#1E40AF',
      '900': '#1E3A8A',
    },
    accent: {
      '50': '#ECFEFF', '100': '#CFFAFE', '200': '#A5F3FC',
      '300': '#67E8F9', '400': '#22D3EE', '500': '#06B6D4',
      '600': '#0891B2',
    },
    glowRgba: '59,130,246',
    sidebar: { gradientStart: '#172554', gradientEnd: '#0F1729' },
    logoAccent: { light: '#60A5FA', dark: '#38BDF8' },
  },
  green: {
    primary: {
      '50': '#ECFDF5', '100': '#D1FAE5', '200': '#A7F3D0',
      '300': '#6EE7B7', '400': '#34D399', '500': '#10B981',
      '600': '#059669', '700': '#047857', '800': '#065F46',
      '900': '#064E3B',
    },
    accent: {
      '50': '#F0FDFA', '100': '#CCFBF1', '200': '#99F6E4',
      '300': '#5EEAD4', '400': '#2DD4BF', '500': '#14B8A6',
      '600': '#0D9488',
    },
    glowRgba: '16,185,129',
    sidebar: { gradientStart: '#022C22', gradientEnd: '#001210' },
    logoAccent: { light: '#34D399', dark: '#2DD4BF' },
  },
  violet: {
    primary: {
      '50': '#F5F3FF', '100': '#EDE9FE', '200': '#DDD6FE',
      '300': '#C4B5FD', '400': '#A78BFA', '500': '#8B5CF6',
      '600': '#7C3AED', '700': '#6D28D9', '800': '#5B21B6',
      '900': '#4C1D95',
    },
    accent: {
      '50': '#FDF4FF', '100': '#FAE8FF', '200': '#F5D0FE',
      '300': '#F0ABFC', '400': '#E879F9', '500': '#D946EF',
      '600': '#C026D3',
    },
    glowRgba: '139,92,246',
    sidebar: { gradientStart: '#2B0B3A', gradientEnd: '#15081E' },
    logoAccent: { light: '#A78BFA', dark: '#E879F9' },
  },
  amber: {
    primary: {
      '50': '#FFFBEB', '100': '#FEF3C7', '200': '#FDE68A',
      '300': '#FCD34D', '400': '#FBBF24', '500': '#F59E0B',
      '600': '#D97706', '700': '#B45309', '800': '#92400E',
      '900': '#78350F',
    },
    accent: {
      '50': '#FFF7ED', '100': '#FFEDD5', '200': '#FED7AA',
      '300': '#FDBA74', '400': '#FB923C', '500': '#F97316',
      '600': '#EA580C',
    },
    glowRgba: '245,158,11',
    sidebar: { gradientStart: '#271A00', gradientEnd: '#141000' },
    logoAccent: { light: '#FBBF24', dark: '#FB923C' },
  },
};

const THEME_DARK_BRIGHTER: Record<string, string> = {
  '500': '500',
  '600': '500',
};

/**
 * Apply the current color theme by setting CSS custom properties
 * on <html> (inline style).
 *
 * Only manages --odap-color-* and --odap-gradient-* variables
 * used by custom global.css overrides.
 *
 * Ant Design 6 components are themed via ConfigProvider
 * with cssVar: true + token.colorPrimary, which generates
 * scoped --ant-* variables automatically.
 */
export function applyColorTheme(colorTheme: string, isDark: boolean): void {
  const palette = PALETTES[colorTheme];
  if (!palette) return;

  const root = document.documentElement;
  const { primary, accent, glowRgba, sidebar, logoAccent } = palette;

  const p = (shade: string) =>
    isDark ? primary[THEME_DARK_BRIGHTER[shade] || shade] : primary[shade];

  // Set primary shades
  Object.entries(primary).forEach(([shade]) => {
    root.style.setProperty(`--odap-color-primary-${shade}`, p(shade));
  });

  // Set accent shades
  Object.entries(accent).forEach(([shade, value]) => {
    root.style.setProperty(`--odap-color-accent-${shade}`, value);
  });

  // Derived aliases
  root.style.setProperty('--odap-color-primary', p('600'));
  root.style.setProperty('--odap-shadow-glow', `0 0 0 3px rgba(${glowRgba},0.12)`);
  root.style.setProperty('--odap-gradient-brand',
    `linear-gradient(135deg, ${p('600')} 0%, ${accent['500']} 100%)`
  );
  root.style.setProperty('--odap-gradient-brand-hover',
    `linear-gradient(135deg, ${p('700')} 0%, ${accent['600']} 100%)`
  );

  // Sidebar
  root.style.setProperty('--odap-sidebar-bg',
    `linear-gradient(180deg, ${sidebar.gradientStart} 0%, ${sidebar.gradientEnd} 100%)`
  );
  root.style.setProperty('--odap-sidebar-logo-bg',
    `linear-gradient(135deg, ${logoAccent.light}33, ${logoAccent.dark}1A)`
  );
  root.style.setProperty('--odap-sidebar-logo-text',
    `linear-gradient(135deg, ${logoAccent.light}, ${logoAccent.dark})`
  );
  root.style.setProperty('--odap-sidebar-logo-color', logoAccent.light);
  root.style.setProperty('--odap-sidebar-border', '1px solid rgba(255,255,255,0.06)');
  root.style.setProperty('--odap-sidebar-border-strong', '1px solid rgba(255,255,255,0.1)');
  root.style.setProperty('--odap-sidebar-text', 'rgba(255,255,255,0.4)');
  root.style.setProperty('--odap-sidebar-text-hover', 'rgba(255,255,255,0.75)');
}
