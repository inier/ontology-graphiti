#!/usr/bin/env node
/**
 * check-no-emoji.mjs — P0-1 独立门禁：前端源码零 emoji 功能图标
 *
 * 与 check-lucide-icons.mjs 的 (b) 校验同源，但单独成一个可独立调度的脚本，
 * 便于在 CI 里把「emoji 回灌」这一步单独失败、单独定位。
 *
 * 退出码：0 = 通过；1 = 命中 emoji
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB_ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(WEB_ROOT, 'src');
const CODE_EXT = /\.(tsx?|jsx?|vue|svelte|html)$/;

const EMOJI_RE =
  /[\u{1F000}-\u{1F0FF}\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/u;

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry.startsWith('.')) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else acc.push(full);
  }
  return acc;
}

const hits = [];
let scanned = 0;
for (const file of walk(SRC)) {
  if (!CODE_EXT.test(file)) continue;
  scanned += 1;
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    const m = EMOJI_RE.exec(line);
    if (m) {
      hits.push(`${relative(WEB_ROOT, file).split(sep).join('/')}:${i + 1} 含 emoji "${m[0]}"`);
    }
  });
}

if (hits.length > 0) {
  console.error(`check-no-emoji: ${hits.length} 处 emoji（扫描 ${scanned} 个文件，P0-1 禁止 emoji 作功能图标）`);
  for (const h of hits) console.error('  ' + h);
  process.exit(1);
}
console.log(`check-no-emoji: PASS（扫描 ${scanned} 个文件，零 emoji）`);
