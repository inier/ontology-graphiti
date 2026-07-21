import fs from 'fs';
import path from 'path';
import process from 'process';

const SRC_DIR = path.resolve(__dirname, '../src');
const CHINESE_REGEX = /[\u4e00-\u9fa5]+/g;

interface LocaleEntry {
  key: string;
  zh: string;
  en: string;
}

interface ModuleLocale {
  namespace: string;
  entries: Map<string, LocaleEntry>;
  zhPath: string;
  enPath: string;
}

function parseArgs(): {
  target: string;
  dryRun: boolean;
  module: string | null;
} {
  const args = process.argv.slice(2);
  const target = args.find((a) => a.startsWith('--target='))?.split('=')[1] || 'modules/ontology';
  const dryRun = args.includes('--dry-run');
  const module = args.find((a) => a.startsWith('--module='))?.split('=')[1] || null;
  return { target, dryRun, module };
}

function getModuleFromPath(filePath: string): string | null {
  const relativePath = path.relative(SRC_DIR, filePath);
  const match = relativePath.match(/^modules\/([^/]+)/);
  return match ? match[1] : null;
}

function getNamespaceFromModule(module: string): string {
  const namespaceMap: Record<string, string> = {
    'shared': 'common',
    'menu-config': 'menu-config',
    'i18n-admin': 'i18n-admin',
  };
  return namespaceMap[module] || module;
}

function camelCase(str: string): string {
  return str
    .replace(/[\u4e00-\u9fa5]+/g, (match) => match)
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+(.)/g, (_, c) => c.toUpperCase())
    .replace(/^[^a-zA-Z]+/, '');
}

function generateKey(baseKey: string, existingKeys: Set<string>, counter: number): string {
  if (!existingKeys.has(baseKey)) return baseKey;
  const newKey = `${baseKey}_${counter}`;
  return existingKeys.has(newKey) ? generateKey(baseKey, existingKeys, counter + 1) : newKey;
}

function extractChineseStrings(content: string): string[] {
  const matches = content.match(CHINESE_REGEX);
  if (!matches) return [];
  const filtered = matches.filter((m) => {
    if (m.length < 2) return false;
    if (/^[一二三四五六七八九十]+$/.test(m)) return false;
    return true;
  });
  return [...new Set(filtered)];
}

function loadLocaleFile(filePath: string): Record<string, unknown> {
  if (!fs.existsSync(filePath)) return {};
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch {
    return {};
  }
}

function saveLocaleFile(filePath: string, data: Record<string, unknown>): void {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
}

function mergeEntries(
  existing: Record<string, unknown>,
  entries: Map<string, LocaleEntry>,
  language: 'zh' | 'en',
): Record<string, unknown> {
  const result = { ...existing };
  entries.forEach((entry) => {
    const current = result[entry.key];
    if (current === undefined) {
      result[entry.key] = language === 'zh' ? entry.zh : entry.en;
    }
  });
  return result;
}

function scanFiles(targetPath: string): string[] {
  const results: string[] = [];
  const fullPath = path.resolve(SRC_DIR, targetPath);

  function walk(dir: string): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullEntryPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'locales') continue;
        if (entry.name.startsWith('.')) continue;
        walk(fullEntryPath);
      } else if (entry.name.endsWith('.tsx')) {
        results.push(fullEntryPath);
      }
    }
  }

  walk(fullPath);
  return results;
}

function main(): void {
  const { target, dryRun, module: targetModule } = parseArgs();
  console.log(`Scanning i18n strings in: ${target}`);
  console.log(`Dry run: ${dryRun}`);

  const files = scanFiles(target);
  console.log(`Found ${files.length} TSX files\n`);

  const moduleLocales = new Map<string, ModuleLocale>();

  for (const file of files) {
    const module = getModuleFromPath(file);
    if (!module) continue;
    if (targetModule && module !== targetModule) continue;

    const namespace = getNamespaceFromModule(module);

    if (!moduleLocales.has(module)) {
      const zhPath = path.resolve(SRC_DIR, `modules/${module}/locales/zh-CN/${namespace}.json`);
      const enPath = path.resolve(SRC_DIR, `modules/${module}/locales/en-US/${namespace}.json`);
      moduleLocales.set(module, {
        namespace,
        entries: new Map(),
        zhPath,
        enPath,
      });
    }

    const locale = moduleLocales.get(module)!;
    const content = fs.readFileSync(file, 'utf-8');

    if (content.includes('useI18n') && content.includes('t(')) {
      const existingKeys = new Set<string>();
      const zhData = loadLocaleFile(locale.zhPath);
      Object.keys(zhData).forEach((k) => existingKeys.add(k));

      const chineseStrings = extractChineseStrings(content);
      for (const str of chineseStrings) {
        if (str.length < 2) continue;
        if (content.includes(`t('${str}')`) || content.includes(`t("${str}")`)) continue;

        let baseKey = camelCase(str);
        if (!baseKey) baseKey = str.replace(/[\u4e00-\u9fa5]/g, (c) => c.charCodeAt(0).toString(16));

        const key = generateKey(baseKey, existingKeys, 1);
        existingKeys.add(key);

        if (!locale.entries.has(key)) {
          locale.entries.set(key, {
            key,
            zh: str,
            en: `[EN] ${str}`,
          });
        }
      }
    }
  }

  let totalAdded = 0;
  let totalModules = 0;

  moduleLocales.forEach((locale, module) => {
    if (locale.entries.size === 0) return;

    totalModules++;
    totalAdded += locale.entries.size;

    console.log(`=== Module: ${module} (namespace: ${locale.namespace}) ===`);
    console.log(`New entries: ${locale.entries.size}`);

    locale.entries.forEach((entry) => {
      console.log(`  ${entry.key}: "${entry.zh}" -> "${entry.en}"`);
    });
    console.log();

    if (!dryRun) {
      const zhDir = path.dirname(locale.zhPath);
      const enDir = path.dirname(locale.enPath);
      if (!fs.existsSync(zhDir)) fs.mkdirSync(zhDir, { recursive: true });
      if (!fs.existsSync(enDir)) fs.mkdirSync(enDir, { recursive: true });

      const zhData = loadLocaleFile(locale.zhPath);
      const enData = loadLocaleFile(locale.enPath);

      const newZhData = mergeEntries(zhData, locale.entries, 'zh');
      const newEnData = mergeEntries(enData, locale.entries, 'en');

      saveLocaleFile(locale.zhPath, newZhData);
      saveLocaleFile(locale.enPath, newEnData);

      console.log(`  Saved: ${locale.zhPath}`);
      console.log(`  Saved: ${locale.enPath}`);
      console.log();
    }
  });

  console.log(`\n=== Summary ===`);
  console.log(`Modules processed: ${totalModules}`);
  console.log(`Total entries added: ${totalAdded}`);
  console.log(dryRun ? '(Dry run - no files modified)' : '(Files updated)');
}

if (require.main === module) {
  main();
}