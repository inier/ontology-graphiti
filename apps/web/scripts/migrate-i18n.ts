import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_DIR = path.resolve(__dirname, '../src');

interface LocaleMapping {
  zh: Record<string, string>;
  en: Record<string, string>;
}

function parseArgs(): {
  modules: string[];
  dryRun: boolean;
} {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const moduleArg = args.find((a) => a.startsWith('--modules='));
  const modules = moduleArg ? moduleArg.split('=')[1].split(',') : ['shared', 'ontology'];
  return { modules, dryRun };
}

function flattenObject(obj: Record<string, unknown>, prefix: string = ''): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value as Record<string, unknown>, newKey));
    } else if (typeof value === 'string') {
      result[newKey] = value;
    }
  }
  return result;
}

function loadLocaleMapping(module: string, namespace: string): LocaleMapping | null {
  const zhPath = path.resolve(SRC_DIR, `modules/${module}/locales/zh-CN/${namespace}.json`);
  const enPath = path.resolve(SRC_DIR, `modules/${module}/locales/en-US/${namespace}.json`);

  if (!fs.existsSync(zhPath) || !fs.existsSync(enPath)) {
    return null;
  }

  const zhData = JSON.parse(fs.readFileSync(zhPath, 'utf-8'));
  const enData = JSON.parse(fs.readFileSync(enPath, 'utf-8'));

  return {
    zh: flattenObject(zhData),
    en: flattenObject(enData),
  };
}

function buildGlobalMapping(modules: string[]): Record<string, string> {
  const mapping: Record<string, string> = {};
  const namespaceMap: Record<string, string> = {
    'shared': 'common',
    'menu-config': 'menu-config',
    'i18n-admin': 'i18n-admin',
  };

  for (const module of modules) {
    const namespace = namespaceMap[module] || module;
    const localeMapping = loadLocaleMapping(module, namespace);
    if (localeMapping) {
      for (const [fullKey, zhValue] of Object.entries(localeMapping.zh)) {
        mapping[fullKey] = zhValue;
        if (fullKey.startsWith(`${namespace}.`)) {
          const shortKey = fullKey.substring(namespace.length + 1);
          if (!mapping[shortKey]) {
            mapping[shortKey] = zhValue;
          }
        }
      }
    }
  }

  return mapping;
}

function getNamespaceFromFile(filePath: string): string | null {
  const content = fs.readFileSync(filePath, 'utf-8');
  const match = content.match(/useI18n\(['"]([^'"]+)['"]\)/);
  if (match) {
    return match[1];
  }
  return null;
}

function scanTSXFiles(targetPath: string): string[] {
  const results: string[] = [];

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

  walk(path.resolve(SRC_DIR, targetPath));
  return results;
}

function replaceTCall(content: string, mapping: Record<string, string>, namespace: string | null): {
  newContent: string;
  changes: { oldKey: string; newKey: string; line: number }[];
} {
  const changes: { oldKey: string; newKey: string; line: number }[] = [];
  let newContent = content;

  const lines = content.split('\n');
  let offset = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const tCallRegex = /t\(['"]([^'"]+)['"]\)/g;
    let match;

    while ((match = tCallRegex.exec(line)) !== null) {
      const oldKey = match[1];
      let fullKey = oldKey;
      if (namespace && !oldKey.includes('.') && !mapping[oldKey]) {
        fullKey = `${namespace}.${oldKey}`;
      }

      const newKey = mapping[fullKey] || mapping[oldKey];

      if (newKey && newKey !== oldKey) {
        const start = offset + match.index;
        const end = start + match[0].length;

        const newCall = `t('${newKey}')`;
        newContent = newContent.substring(0, start) + newCall + newContent.substring(end);

        changes.push({
          oldKey,
          newKey,
          line: i + 1,
        });

        offset += newCall.length - match[0].length;
      }
    }

    offset += line.length + 1;
  }

  return { newContent, changes };
}

function updateLocaleJSON(module: string, namespace: string, mapping: LocaleMapping): void {
  const zhPath = path.resolve(SRC_DIR, `modules/${module}/locales/zh-CN/${namespace}.json`);
  const enPath = path.resolve(SRC_DIR, `modules/${module}/locales/en-US/${namespace}.json`);

  const zhResources: Record<string, unknown> = {};
  const enResources: Record<string, unknown> = {};

  for (const [oldKey, zhValue] of Object.entries(mapping.zh)) {
    zhResources[zhValue] = zhValue;
    const enValue = mapping.en[oldKey];
    if (enValue) {
      enResources[zhValue] = enValue;
    }
  }

  fs.writeFileSync(zhPath, JSON.stringify(zhResources, null, 2) + '\n', 'utf-8');
  fs.writeFileSync(enPath, JSON.stringify(enResources, null, 2) + '\n', 'utf-8');
}

function main(): void {
  const { modules, dryRun } = parseArgs();
  console.log(`Migrating i18n for modules: ${modules.join(', ')}`);
  console.log(`Dry run: ${dryRun}\n`);

  const mapping = buildGlobalMapping(modules);
  console.log(`Built mapping with ${Object.keys(mapping).length} entries\n`);

  const namespaceMap: Record<string, string> = {
    'shared': 'common',
    'menu-config': 'menu-config',
    'i18n-admin': 'i18n-admin',
  };

  for (const module of modules) {
    console.log(`=== Processing module: ${module} ===`);
    const tsxFiles = scanTSXFiles(`modules/${module}`);
    console.log(`Found ${tsxFiles.length} TSX files\n`);

    let totalChanges = 0;

    for (const file of tsxFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      if (!content.includes('useI18n') || !content.includes('t(')) continue;

      const namespace = getNamespaceFromFile(file);
      const { newContent, changes } = replaceTCall(content, mapping, namespace);

      if (changes.length > 0) {
        console.log(`  File: ${path.relative(SRC_DIR, file)}`);
        console.log(`  Namespace: ${namespace || 'default'}`);
        for (const change of changes) {
          console.log(`    Line ${change.line}: t('${change.oldKey}') -> t('${change.newKey}')`);
        }
        console.log();

        totalChanges += changes.length;

        if (!dryRun) {
          fs.writeFileSync(file, newContent, 'utf-8');
        }
      }
    }

    console.log(`  Total changes: ${totalChanges}`);
    console.log();

    const namespace = namespaceMap[module] || module;
    const localeMapping = loadLocaleMapping(module, namespace);
    if (localeMapping && !dryRun) {
      updateLocaleJSON(module, namespace, localeMapping);
      console.log(`  Updated locale files: zh-CN/${namespace}.json, en-US/${namespace}.json`);
    }

    console.log();
  }

  console.log('=== Done ===');
  console.log(dryRun ? '(Dry run - no files modified)' : '(Files updated)');
}

main();