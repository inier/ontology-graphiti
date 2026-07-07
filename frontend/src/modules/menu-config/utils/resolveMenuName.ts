/**
 * Menu name resolution: database stores i18n key, frontend resolves via t().
 *
 * Architecture:
 *   DB name field = "menu.ontology.designer" (i18n key in menu-names namespace)
 *   Frontend calls resolveMenuName(t, item.name) → "本体设计器" (zh) / "Ontology Designer" (en)
 *   Fallback: if key not found, show raw value (backward compatible with legacy data)
 */

export function resolveMenuName(
  t: (key: string, options?: Record<string, any>) => string,
  name?: string,
): string {
  if (!name) return '';
  // Try as i18n key in menu-names namespace
  const translated = t(name, { ns: 'menu-names', defaultValue: '' });
  // If translation returns empty/unchanged key, fallback to raw name
  if (!translated || translated === name) return name;
  return translated;
}
