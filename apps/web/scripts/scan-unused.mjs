#!/usr/bin/env node
/**
 * scan-unused.mjs — 零引用组件扫描（符号级）
 *
 * 为什么不能用 `grep import 文件路径` 了事：
 *  1. barrel（`index.ts`）转出会制造假引用 —— 只看「文件被谁 import」会把
 *     「从 barrel 里只取了一个符号」误判成「barrel 转出的所有文件都活着」；
 *  2. 只被 `*.test.tsx` 引用属「测试空转」，产品里其实已死；
 *  3. 漏掉路由表当根集合，会把全站页面判成死代码（本脚本第一版就踩过）。
 *
 * 因此做成最小符号图：
 *  - 解析每个文件 exports（本地声明 / `export {A} from` / `export * from` / default）与
 *    imports（default / named / namespace / 副作用 / 动态 import() / lazy()）
 *  - 根集合 = 入口 + 整张路由表（`main.tsx`/`App.tsx`/`src/routes/**`/`modules/*\/routes.tsx`）
 *  - 沿 import 边 BFS：barrel 上的符号回代到真正的定义文件
 *  - 文件活着 ⇔ 至少一个导出符号被消费，或被副作用 import，或本身是根
 *
 * 输出两档：
 *  A. 零引用（无人 import）
 *  B. 被 import 但导出符号从未被消费（通常是「只被死文件引用」）
 *
 * ⚠️ 判定「可删」前必须再查一次非 import 接入方式：
 *    动态 import、字符串映射表、WebSocket、路由清单。上一轮 EditLockIndicator
 *    走 WebSocket，`grep apiClient` 完全看不到它。
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep, dirname, resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB_ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(WEB_ROOT, 'src');
const CODE = /\.(tsx?|jsx?)$/;

const walk = (dir, acc = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, acc);
    else acc.push(f);
  }
  return acc;
};

const files = walk(SRC).filter((f) => CODE.test(f));
const rel = (p) => relative(SRC, p).split(sep).join('/');

function resolveSpec(spec, fromFile) {
  let base;
  if (spec.startsWith('@/')) base = join(SRC, spec.slice(2));
  else if (spec.startsWith('.')) base = resolve(dirname(fromFile), spec);
  else return null;
  for (const c of [base, `${base}.ts`, `${base}.tsx`, join(base, 'index.ts'), join(base, 'index.tsx')]) {
    if (existsSync(c) && statSync(c).isFile()) return c;
  }
  return null;
}

/** @type {Map<string, {text:string, exports:Map<string,{kind:'local'|'reexport'|'star',from?:string,as?:string}>, imports:Array<{spec:string,names:string[],ns?:boolean,def?:boolean,sideEffect?:boolean}>}>} */
const mods = new Map();

const RE = {
  // export function/const/class/enum/interface/type Name
  localExport: /export\s+(?:async\s+)?(?:function|const|let|var|class|enum|interface|type|declare\s+const)\s+([A-Za-z_$][\w$]*)/g,
  defaultExport: /export\s+default\s+(?:async\s+)?(?:function|class)?\s*([A-Za-z_$][\w$]*)?/g,
  namedLocalExport: /export\s*\{([^}]*)\}\s*(?!from)/g,
  reexportNamed: /export\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]/g,
  starExport: /export\s*\*\s*from\s*['"]([^'"]+)['"]/g,
  importNamed: /import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]/g,
  importDefault: /import\s+(?:type\s+)?([A-Za-z_$][\w$]*)\s*(?:,\s*\{[^}]*\})?\s*from\s*['"]([^'"]+)['"]/g,
  importNs: /import\s+\*\s+as\s+[A-Za-z_$][\w$]*\s+from\s*['"]([^'"]+)['"]/g,
  importSide: /import\s+['"]([^'"]+)['"]/g,
  dynImport: /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  lazyImport: /lazy\s*\(\s*(?:async\s*)?\(\s*\)\s*=>\s*import\s*\(\s*['"]([^'"]+)['"]/g,
};

/** 解析 `A, B as C, type D` → ['A','B','D']（取对外名 = as 后的名字用于 import；as 前用于 export 源名） */
function splitNames(raw, takeAlias) {
  return raw
    .split(',')
    .map((s) => s.replace(/\btype\b/g, '').trim())
    .filter(Boolean)
    .map((s) => {
      const m = s.match(/^([A-Za-z_$][\w$]*)\s+as\s+([A-Za-z_$][\w$]*)$/);
      if (m) return takeAlias ? m[2] : m[1];
      return s;
    })
    .filter((s) => /^[A-Za-z_$][\w$]*$/.test(s));
}

for (const f of files) {
  const text = readFileSync(f, 'utf8');
  /** @type {Map<string, any>} */
  const exports = new Map();
  const imports = [];

  for (const m of text.matchAll(RE.localExport)) exports.set(m[1], { kind: 'local' });
  for (const m of text.matchAll(RE.defaultExport)) exports.set(m[1] || 'default', { kind: 'local', isDefault: !m[1] });
  if (/export\s+default\b/.test(text)) exports.set('default', { kind: 'local' });
  for (const m of text.matchAll(RE.namedLocalExport)) {
    for (const n of splitNames(m[1], true)) exports.set(n, { kind: 'local' });
  }
  for (const m of text.matchAll(RE.reexportNamed)) {
    for (const n of splitNames(m[1], true)) exports.set(n, { kind: 'reexport', from: m[2] });
  }
  for (const m of text.matchAll(RE.starExport)) exports.set(`*:${m[1]}`, { kind: 'star', from: m[1] });

  for (const m of text.matchAll(RE.importNamed)) imports.push({ spec: m[2], names: splitNames(m[1], true) });
  for (const m of text.matchAll(RE.importDefault)) imports.push({ spec: m[2], names: [], def: true });
  for (const m of text.matchAll(RE.importNs)) imports.push({ spec: m[1], names: [], ns: true });
  for (const m of text.matchAll(RE.importSide)) imports.push({ spec: m[1], names: [], sideEffect: true });
  for (const m of text.matchAll(RE.dynImport)) imports.push({ spec: m[1], names: [], ns: true });
  for (const m of text.matchAll(RE.lazyImport)) imports.push({ spec: m[1], names: [], def: true });

  mods.set(f, { text, exports, imports });
}

/** 保守兜底：export * 链上的模块，符号可能在任一被星号转出的目标里 */
function markAllExportsAlive(file, alive, depth = 0) {
  if (depth > 6) return;
  const mod = mods.get(file);
  if (!mod) return;
  const entry = alive.get(file) ?? new Set();
  for (const [name, e] of mod.exports) {
    if (e.kind === 'star') {
      const target = resolveSpec(e.from, file);
      if (target) markAllExportsAlive(target, alive, depth + 1);
      continue;
    }
    entry.add(name);
    if (e.kind === 'reexport') {
      const target = resolveSpec(e.from, file);
      if (target) {
        const set = alive.get(target) ?? new Set();
        set.add(name);
        alive.set(target, set);
        markAllExportsAlive(target, alive, depth + 1);
      }
    }
  }
  alive.set(file, entry);
}

// ─── 根集合 ───
const ROOTS = files.filter((f) => {
  const r = rel(f);
  // 入口 + 整张路由表：路由表是「页面活着的唯一证据」，漏了它会把全站页面判死
  return (
    r === 'main.tsx' ||
    r === 'App.tsx' ||
    /^app\//.test(r) ||
    /^routes\//.test(r) ||
    /(^|\/)routes\.tsx?$/.test(r)
  );
});
const alive = new Map(); // file -> Set(symbol)
/** 沿 barrel 回代，**同时对中间跳标活**（barrel 自己也是被消费的） */
function consume(file, symbol) {
  const mod = mods.get(file);
  if (!mod) return;
  requestVisit(file);
  const set = alive.get(file) ?? new Set();
  if (set.has(symbol)) return;
  set.add(symbol);
  alive.set(file, set);

  const e = mod.exports.get(symbol);
  if (e?.kind === 'reexport' || e?.kind === 'star') {
    const target = resolveSpec(e.from, file);
    if (target) consume(target, symbol);
    return;
  }
  if (e) return; // local：到此为止
  // 符号不在本文件 exports 里 —— 可能在 `export * from` 链的某个目标中
  for (const [, se] of mod.exports) {
    if (se.kind !== 'star') continue;
    const target = resolveSpec(se.from, file);
    if (target && mods.get(target)?.exports.has(symbol)) {
      consume(target, symbol);
      return;
    }
  }
}

/** 待遍历文件队列：某文件一旦有符号被消费，就要展开它的 import */
const fileQueue = [];
const visitedFiles = new Set();
const requestVisit = (f) => {
  if (visitedFiles.has(f)) return;
  visitedFiles.add(f);
  fileQueue.push(f);
};

for (const r of ROOTS) {
  markAllExportsAlive(r, alive);
  requestVisit(r);
}

while (fileQueue.length) {
  const file = fileQueue.shift();
  const mod = mods.get(file);
  if (!mod) continue;
  for (const imp of mod.imports) {
    const target = resolveSpec(imp.spec, file);
    if (!target || !mods.has(target)) continue;
    if (imp.sideEffect || imp.ns) {
      markAllExportsAlive(target, alive);
      requestVisit(target);
      continue;
    }
    if (imp.def) { consume(target, 'default'); requestVisit(target); }
    for (const n of imp.names) { consume(target, n); requestVisit(target); }
  }
}

const isTest = (f) => /\.(test|spec)\.tsx?$/.test(f) || /__tests__[\\/]/.test(f);
const isEntry = (f) => {
  const r = rel(f);
  return (
    r === 'main.tsx' ||
    r === 'App.tsx' ||
    r === 'vite-env.d.ts' ||
    /^app\//.test(r) ||
    /^routes\//.test(r) ||
    /^test\//.test(r) ||
    /\.d\.ts$/.test(r) ||
    /setupTests|test-utils|testUtils|(^|\/)mocks?\//.test(r)
  );
};
const lineCount = (f) => readFileSync(f, 'utf8').split('\n').length;
const fmt = (f) => `${rel(f)} (${lineCount(f)} 行)`;

/** 有 import 关系但符号没被消费 → 最可疑 */
const importedBy = new Map();
for (const f of files) {
  for (const imp of mods.get(f).imports) {
    const t = resolveSpec(imp.spec, f);
    if (!t || isTest(f)) continue;
    const set = importedBy.get(t) ?? new Set();
    set.add(f);
    importedBy.set(t, set);
  }
}

const dead = [];
const deadTestOnly = [];
const deadWithImportButNoSymbol = [];
for (const f of files) {
  if (isTest(f) || isEntry(f)) continue;
  const mod = mods.get(f);
  // 无导出 = 纯副作用模块（如 css-in-js 注册、polyfill），按「是否被 import」判
  const hasExports = mod.exports.size > 0;
  const isAlive = hasExports ? alive.has(f) && alive.get(f).size > 0 : importedBy.has(f);
  if (isAlive) continue;

  const consumers = [...(importedBy.get(f) ?? [])];
  if (consumers.length === 0) dead.push(f);
  else deadWithImportButNoSymbol.push({ f, consumers });
}

console.log(`扫描 ${files.length} 个源文件，根集合 ${ROOTS.length} 个（${ROOTS.map(rel).join(', ')}）\n`);

console.log(`A. 零引用 —— 无人 import（${dead.length}）`);
dead.sort().forEach((f) => console.log(`   ${fmt(f)}`));

console.log(`\nB. 被 import 但符号从未被消费（${deadWithImportButNoSymbol.length}）`);
deadWithImportButNoSymbol
  .sort((x, y) => x.f.localeCompare(y.f))
  .forEach(({ f, consumers }) =>
    console.log(`   ${fmt(f)}\n       ← ${consumers.map(rel).join(', ')}`),
  );

console.log(`\n存活：${files.filter((f) => !isTest(f) && !isEntry(f)).length - dead.length - deadWithImportButNoSymbol.length} 个`);
