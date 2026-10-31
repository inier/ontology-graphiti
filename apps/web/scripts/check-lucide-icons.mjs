#!/usr/bin/env node
/**
 * check-lucide-icons.mjs — 图标系统 CI 不变量（ADR-092 第 11 条 / SPEC AC-51~AC-54）
 *
 * 四校验：
 *   (a) 白名单        源码 `from 'lucide-react'` 的具名导入必须 ∈ pinned 版本全量导出清单
 *   (b) emoji 扫描    全前端源码零 emoji 功能图标（防迁移期回灌 P0-1）
 *   (c) 语义角色表    注册表 role → 图标名必须与设计侧 §5.2 终裁表逐条一致 + minSize 门禁
 *   (d) 直连禁令      除 Icon 模块外禁止 from 'lucide-react'；禁止 import *；strokeWidth 仅 Icon.tsx
 *
 * 用法：pnpm --filter @odap/web run check:icons
 * 退出码：0 = 通过；1 = 有违反项
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep, dirname } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { PINNED_VERSION, EXPECTED } from './lucide-role-expectations.mjs';

const WEB_ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(WEB_ROOT, 'src');
const REGISTRY = join(SRC, 'modules/shared/components/iconRegistry.ts');
const ICON_ALLOWED_FILES = new Set([
  'src/modules/shared/components/Icon.tsx',
  'src/modules/shared/components/iconRegistry.ts',
]);
const STROKE_ALLOWED_FILES = new Set(['src/modules/shared/components/Icon.tsx']);

/**
 * 非图标 SVG 描边豁免：这些是图谱/图表画布的"边/节点轮廓"描边（消费 --odap-graph-* / --odap-chart-*），
 * 与图标描边规格（1.5 / round cap / fill:none）无关，属两种不同语义。
 * 豁免必须逐文件登记并写明理由，禁止用通配符。
 */
const SVG_GRAPHIC_STROKE_ALLOWLIST = new Map([
  ['src/modules/ontology/components/blueprint/BlueprintEdge.tsx', 'xyflow 边描边（--odap-graph-edge-width-emphasis）'],
  ['src/modules/semantic-admin/pages/PipelineRunsPage.tsx', '内联 SVG 气泡轮廓（--odap-graph-node-* 分类色描边）'],
]);

const violations = [];
const fail = (check, msg) => violations.push(`[${check}] ${msg}`);

/** 测试文件：门禁的"被测对象"本身，尺寸/strokeWidth 断言需刻意越界 */
function isTestFile(file) {
  return /[\\/](__tests__|test)[\\/]/.test(file) || /\.test\.(tsx?|jsx?)$/.test(file);
}

/* ── 工具 ─────────────────────────────────────────────────────────── */
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

/* ── 0. pinned 版本与导出白名单 ───────────────────────────────────── */
function loadExportWhitelist() {
  const pkg = JSON.parse(readFileSync(join(WEB_ROOT, 'package.json'), 'utf8'));
  const declared = pkg.dependencies?.['lucide-react'];
  if (!declared) throw new Error('package.json 未声明 lucide-react 依赖（ADR-092 要求 pinned）');
  const pinned = declared.replace(/^[^0-9]*/, '');
  if (pinned !== PINNED_VERSION) {
    fail('a', `package.json 的 lucide-react 为 ${declared}，与脚本冻结版本 ${PINNED_VERSION} 不一致；改版本须同步重冻语义角色表`);
  }
  const require = createRequire(join(WEB_ROOT, 'package.json'));
  let dts;
  try {
    const pkgJson = require.resolve('lucide-react/package.json');
    const actualVersion = JSON.parse(readFileSync(pkgJson, 'utf8')).version;
    if (actualVersion !== PINNED_VERSION) {
      fail('a', `已安装的 lucide-react 为 ${actualVersion}，与脚本冻结版本 ${PINNED_VERSION} 不一致（改名风险，须重冻）`);
    }
    dts = join(dirname(pkgJson), 'dist/lucide-react.d.ts');
  } catch {
    throw new Error('未解析到 lucide-react 包，请先 pnpm install（白名单来自 pinned 版本导出清单）');
  }
  if (!existsSync(dts)) {
    throw new Error(`未找到 ${dts}，请确认 lucide-react 安装完整`);
  }
  const src = readFileSync(dts, 'utf8');
  const names = new Set();
  const blockRe = /export\s*\{([^}]*)\}/g;
  let m;
  while ((m = blockRe.exec(src))) {
    for (const part of m[1].split(',')) {
      const p = part.trim();
      if (!p) continue;
      const asParts = p.split(/\s+as\s+/);
      const name = (asParts[1] || asParts[0]).trim();
      if (/^[A-Za-z0-9_]+$/.test(name)) names.add(name);
    }
  }
  return names;
}

/* ── 1. 收集源码中所有 from 'lucide-react' 的具名导入 ─────────────── */
// 行首锚定，避免把文档注释里的 `import * as Icons` 反例当成真实代码
const IMPORT_RE = /^[ \t]*import\s+(type\s+)?([\s\S]*?)\s+from\s+['"]lucide-react['"];?[ \t]*$/gm;

const isCommentLine = (line) => {
  const t = line.trimStart();
  return t.startsWith('//') || t.startsWith('*') || t.startsWith('/*');
};

function collectLucideImports(files) {
  const records = [];
  for (const file of files) {
    if (!/\.(tsx?|jsx?)$/.test(file)) continue;
    const text = readFileSync(file, 'utf8');
    IMPORT_RE.lastIndex = 0;
    let m;
    while ((m = IMPORT_RE.exec(text))) {
      records.push({ file, spec: m[2].replace(/\s+/g, ' ').trim(), typeOnly: Boolean(m[1]) });
    }
  }
  return records;
}

function checkWhitelist(records, whitelist) {
  for (const { file, spec, typeOnly } of records) {
    if (typeOnly) continue;
    if (/^\*/.test(spec)) {
      fail('d', `${rel(file)} 使用 import * as ... from 'lucide-react'（破坏 tree-shaking，ADR-092 第 12 条禁止）`);
      continue;
    }
    const named = spec.replace(/^[A-Za-z0-9_$]+\s*,?\s*/, '');
    if (!named.startsWith('{')) continue;
    const names = named
      .replace(/[{}]/g, '')
      .split(',')
      .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
      .filter(Boolean);
    for (const name of names) {
      if (!whitelist.has(name)) {
        fail('a', `${rel(file)} 导入的 "${name}" 不在 lucide-react@${PINNED_VERSION} 导出清单内（禁止静默降级/就近改选）`);
      }
    }
  }
}

/* ── 2. emoji 扫描 ────────────────────────────────────────────────── */
const EMOJI_RE = /[\u{1F000}-\u{1F0FF}\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;

function checkEmoji(files) {
  for (const file of files) {
    if (!/\.(tsx?|jsx?|html)$/.test(file)) continue;
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      if (EMOJI_RE.test(line)) {
        fail('b', `${rel(file)}:${i + 1} 含 emoji 字符，禁止作为功能图标（P0-1）`);
      }
    });
  }
}

/* ── 3. 语义角色表 + minSize ──────────────────────────────────────── */
const ROLE_RE =
  /^\s{2}([A-Za-z0-9]+):\s*\{\s*icon:\s*([A-Za-z0-9]+),\s*iconName:\s*'([A-Za-z0-9]+)',\s*minSize:\s*(16|20|24)\s*\},?$/;

function parseRegistry() {
  const text = readFileSync(REGISTRY, 'utf8');
  const roles = new Map();
  for (const line of text.split('\n')) {
    const m = ROLE_RE.exec(line);
    if (m) roles.set(m[1], { icon: m[2], iconName: m[3], minSize: Number(m[4]) });
  }
  return roles;
}

function checkRoleTable(roles) {
  for (const [role, [expectedIcon, expectedMin]] of Object.entries(EXPECTED)) {
    const actual = roles.get(role);
    if (!actual) {
      fail('c', `语义角色 "${role}" 缺失（§5.2 终裁要求绑定 ${expectedIcon}）`);
      continue;
    }
    if (actual.iconName !== expectedIcon || actual.icon !== expectedIcon) {
      fail('c', `角色 "${role}" 绑定为 ${actual.iconName}，§5.2 终裁为 ${expectedIcon}（同名不同语义视为违规）`);
    }
    if (actual.minSize !== expectedMin) {
      fail('c', `角色 "${role}" 的 minSize=${actual.minSize}，门禁要求 ${expectedMin}`);
    }
  }
  for (const role of roles.keys()) {
    if (!(role in EXPECTED)) {
      fail('c', `角色 "${role}" 未在 §5.2 终裁表登记；新语义须走「提交→终审→回签」`);
    }
  }
}

function checkRoleUsage(files, roles) {
  const USAGE_RE = /<Icon\b[^>]*?role=["']([A-Za-z0-9]+)["'][^>]*?>/g;
  for (const file of files) {
    if (!/\.tsx$/.test(file)) continue;
    // 测试文件刻意构造越界用法以验证门禁本身（如 size=16 触发自动升档），不参与尺寸断言
    if (isTestFile(file)) continue;
    const text = readFileSync(file, 'utf8');
    USAGE_RE.lastIndex = 0;
    let m;
    while ((m = USAGE_RE.exec(text))) {
      const role = m[1];
      const spec = roles.get(role);
      if (!spec) {
        fail('c', `${rel(file)} 使用未登记角色 "${role}"`);
        continue;
      }
      const sizeMatch = /size=\{(\d+)\}/.exec(m[0]);
      if (sizeMatch) {
        const size = Number(sizeMatch[1]);
        if (![16, 20, 24].includes(size)) {
          fail('c', `${rel(file)} 角色 "${role}" 使用 size={${size}}，尺寸仅允许 16/20/24（AC-54）`);
        }
        if (size < spec.minSize) {
          fail('c', `${rel(file)} 角色 "${role}" 使用 ${size}px < minSize ${spec.minSize}px，须退用简化图标或升档`);
        }
      }
    }
  }
}

/* ── 4. 直连导入禁令 + strokeWidth 单点校验 ───────────────────────── */
function checkDirectImport(files, records) {
  for (const { file } of records) {
    const r = rel(file);
    if (!ICON_ALLOWED_FILES.has(r)) {
      fail('d', `${r} 直接 from 'lucide-react'；业务侧必须经 shared/components/Icon（ADR-092 第 12 条）`);
    }
  }
  for (const file of files) {
    if (!/\.(tsx?|jsx?)$/.test(file)) continue;
    // 测试文件需要断言"strokeWidth 恒为 1.5"这一规格，允许出现该字面量；
    // 但仍禁止测试文件直连 lucide-react（上面的 records 检查照常生效）。
    if (isTestFile(file)) continue;
    const r = rel(file);
    if (STROKE_ALLOWED_FILES.has(r)) continue;
    if (SVG_GRAPHIC_STROKE_ALLOWLIST.has(r)) continue;
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      if (isCommentLine(line)) return;
      if (/strokeWidth/.test(line)) {
        fail('d', `${r}:${i + 1} 出现 strokeWidth；该属性只允许在 Icon.tsx 设置（"唯一位置"约束）`);
      }
    });
  }
}

/* ── main ─────────────────────────────────────────────────────────── */
try {
  const whitelist = loadExportWhitelist();
  const files = walk(SRC);
  const records = collectLucideImports(files);

  checkWhitelist(records, whitelist);
  checkEmoji(files);
  const roles = parseRegistry();
  checkRoleTable(roles);
  checkRoleUsage(files, roles);
  checkDirectImport(files, records);

  const scanned = files.length;
  if (violations.length > 0) {
    console.error(`check-lucide-icons: ${violations.length} 项违反（扫描 ${scanned} 个文件）`);
    for (const v of violations) console.error('  ' + v);
    process.exit(1);
  }
  console.log(
    `check-lucide-icons: PASS（lucide-react@${PINNED_VERSION}，白名单 ${whitelist.size} 个导出，` +
      `语义角色 ${roles.size} 个，扫描 ${scanned} 个文件）`,
  );
} catch (err) {
  console.error('check-lucide-icons: ERROR ' + (err && err.message ? err.message : String(err)));
  process.exit(1);
}
