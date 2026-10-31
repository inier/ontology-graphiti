#!/usr/bin/env node
/**
 * check-i18n-keys.mjs — 国际化方案不变量（中文为 key 的项目约定）
 *
 * 项目约定（2026-10-17 确认）：**以项目原始中文为 key，其他语言是对该 key 的翻译**。
 * 由约定推导出四条硬不变量，本脚本逐条校验：
 *
 *  (1) 占位译文零容忍：任何语言里 `"a.b": "a b"`（值 = 键把点换成空格）都是机器填充的垃圾，
 *      运行时会把这段垃圾显示给用户。必须删掉（删掉后 i18next 会回落到 zh-CN 中文）。
 *  (2) 幽灵键零容忍：en/ja 里不允许出现 zh-CN 没有的键——zh-CN 是唯一真相源。
 *  (3) 冗余点号键（WARN 级）：若点号键的值恰好等于某个既有中文键，说明它是重复键。
 *      用户看不到任何差异，属于维护成本而非功能缺陷；且跨命名空间引用时直接合并会破坏解析，
 *      因此只作为警示项逐命名空间报告，不阻断 CI。
 *  (4) 代码引用必须可解析：`t('a.b')` 必须能在「本模块命名空间 或 fallbackNS=common」中解析
 *      （`modules/shared/stores/i18nStore.ts` 已配置 fallbackNS: 'common'），
 *      否则界面会原样显示 "a.b"。既存欠债登记在 `scripts/i18n-key-baseline.json`，
 *      基线只允许减少：新增缺失立即失败。
 *  (5) 占位符必须对得上（**最隐蔽的一类**，2026-10-19 新增）：调用处传了参数、但译文里没有
 *      对应的 `{{x}}`，参数会被 i18next 静默丢弃 —— 界面不报错、信息永久丢失。
 *      反向（译文里有 `{{x}}` 但调用处没传）则会把 `{{x}}` 原样显示给用户。
 *      两种情况都是阻断级。实例：`result.resultCount` 只显示「结果数」不带数字；
 *      `editLock.editingTooltip` 的「自 {{time}}」整段丢失。
 *
 * 阻断项（FAIL）：占位译文 / 幽灵键 / 引用缺失 / 占位符不匹配
 * 警示项（WARN）：冗余点号键
 *
 * 退出码：0 = 通过；1 = 有阻断项被破坏。
 */
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB_ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(WEB_ROOT, 'src');
const LOCALES_ROOT = join(SRC, 'modules');
const BASELINE_PATH = join(WEB_ROOT, 'scripts', 'i18n-key-baseline.json');
const CODE_EXT = /\.(tsx?|jsx?)$/;

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry.startsWith('.')) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else acc.push(full);
  }
  return acc;
}

const rel = (p) => relative(WEB_ROOT, p).split(sep).join('/');

// ─── 收集所有命名空间的 zh-CN 键（真相源） ───
/** @type {Map<string, {path: string, data: Record<string,string>}>} */
const sources = new Map();
for (const file of walk(LOCALES_ROOT)) {
  if (!/[\\/]locales[\\/]zh-CN[\\/][^\\/]+\.json$/.test(file)) continue;
  const ns = file.split(/[\\/]/).pop().replace(/\.json$/, '');
  sources.set(ns, { path: file, data: JSON.parse(readFileSync(file, 'utf8')) });
}

const failures = [];
const warnings = [];
const notes = [];
/** 违规项的唯一 ID，用于与基线比对（格式：类型|命名空间/语言|键） */
const violations = new Set();
const fail = (type, loc, key, message) => {
  violations.add(`${type}|${loc}|${key}`);
  failures.push(message);
};
const warn = (message) => warnings.push(message);

// ─── (1)(2)(3) 逐命名空间、逐语言校验 ───
for (const [ns, { data: zh }] of sources) {
  const zhKeys = new Set(Object.keys(zh));
  const identity = new Set([...zhKeys].filter((k) => !k.includes('.')));

  // (3) 冗余点号键 —— 警示项
  let redundant = 0;
  for (const k of zhKeys) {
    if (k.includes('.') && identity.has(zh[k])) redundant += 1;
  }
  if (redundant) {
    warn(`${ns}/zh-CN 有 ${redundant} 个点号键的值与某个既有中文键重复（合并可去掉重复，注意跨命名空间引用）`);
  }

  const langDir = dirname(sources.get(ns).path);
  const moduleLocales = dirname(langDir);
  for (const lang of readdirSync(moduleLocales)) {
    if (lang === 'zh-CN') continue;
    const path = join(moduleLocales, lang, `${ns}.json`);
    if (!existsSync(path)) continue;
    const data = JSON.parse(readFileSync(path, 'utf8'));
    for (const [k, v] of Object.entries(data)) {
      // (1) 占位译文
      if (k.includes('.') && v === k.replaceAll('.', ' ')) {
        fail('占位译文', `${ns}/${lang}`, k, `[占位译文] ${ns}/${lang}「${k}」= 「${v}」（应删除该键，回落到中文）`);
      }
      // (2) 幽灵键
      if (!zhKeys.has(k)) {
        fail('幽灵键', `${ns}/${lang}`, k, `[幽灵键] ${ns}/${lang}「${k}」在 zh-CN 中不存在`);
      }
    }
  }
}

// ─── (4) 代码里的点号键必须能在「本模块 ns 或 fallbackNS=common」中解析 ───
const commonZh = sources.get('common')?.data ?? {};
const resolvable = (nsData, key) => Object.hasOwn(nsData, key) || Object.hasOwn(commonZh, key);

const baseline = existsSync(BASELINE_PATH) ? JSON.parse(readFileSync(BASELINE_PATH, 'utf8')) : {};
const knownDebt = new Set(baseline.missingKeys ?? []);
const stillMissing = new Set();

for (const file of walk(SRC)) {
  if (!CODE_EXT.test(file)) continue;
  const parts = rel(file).split('/');
  const moduleName = parts[2]; // src / modules / <module> / ...
  if (!moduleName) continue;
  const zh = sources.get(moduleName);
  if (!zh) continue;
  const text = readFileSync(file, 'utf8');
  // 前面不能是标识符字符或点：排除 getByText('x') / i18n.t('x') 这类误匹配
  const re = /(?<![\w$.])t\(\s*['"]([\w.]+)['"]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const key = m[1];
    if (!key.includes('.') || key === '.') continue; // 非点号键 = 中文原文，缺条目属正常回落
    if (resolvable(zh.data, key)) continue;
    stillMissing.add(`${moduleName}::${key}`);
    if (knownDebt.has(`${moduleName}::${key}`)) continue;
    const line = text.slice(0, m.index).split('\n').length;
    // 引用缺失单独用 missingKeys 基线比对（不混进 violations，避免同一问题记两遍）
    failures.push(`[引用缺失] ${rel(file)}:${line} t('${key}') 在 ${moduleName}/zh-CN 与 common 中都不存在，界面会显示原始键名`);
  }
}

// ─── (5) 占位符必须对得上（调用处传的参数 vs 译文里的 {{x}}） ───
const PLACEHOLDER = /\{\{\s*([\w.]+)\s*\}\}/g;
const placeholdersOf = (value) => new Set([...String(value ?? '').matchAll(PLACEHOLDER)].map((mm) => mm[1]));

/** 从 `{ a, b: 1, c: x ? 1 : 2 }` 里抠出参数名 */
function paramNames(objectLiteral) {
  const names = new Set();
  for (const piece of objectLiteral.split(',')) {
    const kv = piece.match(/^\s*([A-Za-z_$][\w$]*)\s*:/);
    if (kv) { names.add(kv[1]); continue; }
    const short = piece.match(/^\s*([A-Za-z_$][\w$]*)\s*$/);
    if (short) names.add(short[1]);
  }
  return names;
}

// 形如 t('key', { a, b: ... }) —— 只处理字面量键，动态拼键无法静态判定
const CALL_WITH_PARAMS = /(?<![\w$.])t\(\s*['"]([\w.]+)['"]\s*,\s*\{([\s\S]{0,300}?)\}\s*[,)]/g;

for (const file of walk(SRC)) {
  if (!CODE_EXT.test(file)) continue;
  const parts = rel(file).split('/');
  const moduleName = parts[2];
  if (!moduleName) continue;
  const zh = sources.get(moduleName);
  if (!zh) continue;
  const text = readFileSync(file, 'utf8');
  let m;
  while ((m = CALL_WITH_PARAMS.exec(text)) !== null) {
    const key = m[1];
    const passed = paramNames(m[2]);
    // 该键可能在 common 里（fallbackNS）
    const value = Object.hasOwn(zh.data, key) ? zh.data[key] : commonZh[key];
    if (value === undefined) continue; // 引用缺失由 (4) 负责
    const declared = placeholdersOf(value);
    const line = text.slice(0, m.index).split('\n').length;

    const dropped = [...passed].filter((p) => !declared.has(p));
    if (dropped.length) {
      fail(
        '占位符多余参数',
        moduleName,
        key,
        `[占位符多余参数] ${rel(file)}:${line} t('${key}') 传了 {${dropped.join(', ')}}，但译文「${value}」里没有对应 {{…}} —— 参数会被静默丢弃`,
      );
    }
    const unfilled = [...declared].filter((p) => !passed.has(p));
    if (unfilled.length) {
      fail(
        '占位符未传值',
        moduleName,
        key,
        `[占位符未传值] ${rel(file)}:${line} t('${key}') 译文要求 {{${unfilled.join('}}, {{')}}}，但调用处没传 —— 界面会显示原始 {{…}}`,
      );
    }
  }
}

// ─── 基线比对与输出 ───
const knownViolations = new Set(baseline.violations ?? []);
const fixedDebt = [...knownDebt].filter((k) => !stillMissing.has(k));
const newViolations = [...violations].filter((v) => !knownViolations.has(v));
const fixedViolations = [...knownViolations].filter((v) => !violations.has(v));

if (process.argv.includes('--list')) {
  // 全量明细（默认只打印 40 条，排查时用这个看全）
  failures.forEach((f) => console.log(f));
  process.exit(0);
}

if (process.argv.includes('--update-baseline')) {
  const sortedViolations = [...violations].sort();
  const payload = {
    _comment:
      'i18n 既存欠债基线。violations = 阻断级语言包违规（占位译文 / 幽灵键）；missingKeys = 代码引用了但本模块命名空间与 common 都缺失的点号键。' +
      '两者都只允许减少：新增即 CI 失败。修复后请用 `node scripts/check-i18n-keys.mjs --update-baseline` 重生成，并在提交信息里写明减少量。',
    violations: sortedViolations,
    missingKeys: [...stillMissing].sort(),
  };
  writeFileSync(BASELINE_PATH, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  console.log(`[i18n] 基线已更新：violations ${sortedViolations.length} 条，missingKeys ${stillMissing.size} 条`);
  process.exit(0);
}

const stats = [...sources].map(([ns, { data }]) => `${ns}:${Object.keys(data).length}`).join(' ');
console.log(`[i18n] 命名空间 ${sources.size} 个（zh-CN 键数 ${stats}）`);
console.log(
  `[i18n] 现状：阻断违规 ${violations.size} 条（基线 ${knownViolations.size}），缺失引用 ${stillMissing.size} 条（基线 ${knownDebt.size}），冗余点号键警示 ${warnings.length} 处`,
);
if (fixedViolations.length) notes.push(`基线中 ${fixedViolations.length} 条违规已修复，可重生成基线以缩小欠债`);
if (fixedDebt.length) notes.push(`基线中 ${fixedDebt.length} 条缺失引用已补齐，可重生成基线以缩小欠债`);
notes.forEach((n) => console.log(`[提示] ${n}`));
warnings.slice(0, 10).forEach((w) => console.log(`[警示] ${w}`));
if (warnings.length > 10) console.log(`[警示] … 其余 ${warnings.length - 10} 处省略`);

if (newViolations.length) {
  console.error(`\n[i18n] 新增违规 ${newViolations.length} 处（基线外，必须修）：`);
  for (const v of newViolations.slice(0, 40)) {
    const hit = failures.find((f) => f.includes(v.split('|')[2]));
    console.error(`  - ${hit ?? v}`);
  }
  if (newViolations.length > 40) console.error(`  … 其余 ${newViolations.length - 40} 处省略`);
  process.exit(1);
}
console.log('[i18n] ✅ 无新增阻断项（占位译文 / 幽灵键 / 引用缺失 均未增加）');
