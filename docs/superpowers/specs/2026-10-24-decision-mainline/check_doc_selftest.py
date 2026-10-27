#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_doc.py 的深度自测：变异测试 + 转义保护。

与 check_doc.py 自带 self_check() 的分工：
  - **用例只有一份**，在 check_doc.SELF_CHECK / BLIND_SPOTS 里。本文件不另抄一遍。
    同一份内容写两处，早晚会改一处忘另一处——这是本项目已经发生过两次的错。
  - check_doc.main() 每次运行都先跑 self_check()，不通过就 EXIT=2 拒绝出报告。
  - 本文件做的是**证明那个自检有牙**：故意改坏判据，看它会不会变红。

为什么"自检全绿"还不够：
  自测全绿也可能是自测根本没在断言。所以本文件 --mutate 模式把每个判据逐一改坏
  （`>` 变 `>=`、判据恒 False、丢转义保护、恢复跳空行老 bug……），要求自测必须变红。
  **不能被改坏的自测，等于没有自测。**

用法：
  python check_doc_selftest.py            # 跑自检 + 转义保护
  python check_doc_selftest.py --mutate   # 变异测试：证明自检会红
"""
import contextlib
import io
import re
import sys

import check_doc


def run():
    fails = []
    print("=" * 68)
    print("check_doc 自检（用例来自 check_doc.SELF_CHECK，不在此重复定义）")
    print("=" * 68)

    # 逐例打印，便于定位是哪一条坏了
    for name, text, expect in check_doc.SELF_CHECK:
        res = check_doc.check_tables(text.strip("\n").split("\n"))
        got = {k: len(v) for k, v in res.items()}
        problems = ["%s 期望 %d 实得 %d" % (k, w, got[k])
                    for k, w in expect.items() if got[k] != w]
        nz = {k: v for k, v in got.items() if v}
        print("%s %-30s %s" % ("OK  " if not problems else "FAIL", name,
                               nz or "全 0" if not problems else " ".join(problems)))
        if problems:
            fails.append((name, problems))

    for name, text, why in check_doc.BLIND_SPOTS:
        res = check_doc.check_tables(text.strip("\n").split("\n"))
        hit = {k: len(v) for k, v in res.items() if isinstance(v, list) and v}
        ok = not hit
        print("%s %-30s %s" % ("OK  " if ok else "FAIL", name,
                               "确实抓不到（盲区，需人工/写作规范）" if ok else "被检出了 %s" % hit))
        if ok:
            # 盲区理由必须写清"哪一层没有残差"，否则下一个人会以为努力不够去加码
            print("      └ %s" % why)
        else:
            fails.append((name, ["已知盲区却被检出 %s" % hit]))

    print("-" * 68)

    # split_row 的转义保护单独测：它是最容易把**好文档报成坏**的地方。
    # 误报比漏报更糟 —— 它会逼人去改本来写对了的东西。
    esc = [
        ("| GET\\|POST | x |", 2),
        ("| system \\| user | y |", 2),
        ("| e.name \\|\\| id | z |", 2),
        ("| 普通 | 三列 | 好 |", 3),
    ]
    for raw, want in esc:
        got = len(check_doc.split_row(raw))
        ok = got == want
        print("%s split_row 转义保护  %-24s 期望 %d 实得 %d"
              % ("OK  " if ok else "FAIL", raw, want, got))
        if not ok:
            fails.append(("split_row: " + raw, ["期望 %d 实得 %d" % (want, got)]))

    print("-" * 68)
    # 再跑一遍门禁自己的聚合判断，确认两条路径结论一致
    agg = check_doc.self_check()
    if agg and not fails:
        fails.append(("check_doc.self_check()", agg))

    if fails:
        print("自测结论: FAIL —— 检查器不可信，先修 check_doc.py 再信它的输出")
        for name, p in fails:
            print("  ✗ %s: %s" % (name, " / ".join(p)))
        return 1

    clean = len([1 for _, _, e in check_doc.SELF_CHECK if not any(e.values())])
    print("自测结论: PASS —— %d 例（%d 缺陷必抓 + %d 正常必不报）+ %d 例盲区确认抓不到 + %d 例转义保护"
          % (len(check_doc.SELF_CHECK), len(check_doc.SELF_CHECK) - clean, clean,
             len(check_doc.BLIND_SPOTS), len(esc)))
    return 0


# ---------------------------------------------------------------- 变异测试
# 每条：(变异名, 正则/正则列表, 替换)。要求：变异后自测**必须变红**。
# 存活 = 这条判据实际上没被测试看着，等于没测。
MUTATIONS = [
    ("TRUNCATED 判据改坏(> 变 >=)",
     r"if cells > ncol:", "if cells >= ncol:"),
    ("UNDERFILL 判据失效",
     r"elif cells < ncol:", "elif cells < 0:"),
    ("UNCLOSED 判据失效",
     r'if not row\.endswith\("\|"\):', "if False:"),
    ("SEP_MISMATCH 判据失效",
     r"if nsep != ncol:", "if False:"),
    ("SPILLED 判据失效",
     r'if nxt\.endswith\("\|"\):', "if False:"),
    ("SPILLED_WEAK 判据失效",
     r'elif "\|" in nxt:', "elif False:"),
    ("GLUED 判据失效",
     r"                    glued\.append", "                    pass  # glued.append"),
    ("BROKEN_CODE 判据失效",
     r'if c\.count\("`"\) % 2 == 1:', "if False:"),
    # 代码块跳过有**两层**且互相兜底（外层 `if mask[i]` 拦表头、内层 `while ... not mask[j]`
    # 拦数据行）。只打掉一层是**等价变异体**——另一层仍拦着，结果不变，存活不代表测试有缺口。
    # 必须同时打掉两层才验证得出。
    ("去掉代码块跳过(两层同时,制造误报)",
     [(r"        if mask\[i\]:\n            i \+= 1\n            continue",
       "        if False:\n            i += 1\n            continue"),
      (r'while j < len\(lines\) and not mask\[j\] and lines\[j\]\.strip\(\)\.startswith\("\|"\):',
       r'while j < len(lines) and lines[j].strip().startswith("|"):')]),
    # 恢复上一版的误报 bug：块后**跳过空行**再看。这会让"表格→空行→说明段"的每张表
    # 都命中，在 uiux.md 上曾产生 9/9 误报。用例「表格后空行接说明段」应杀死它。
    ("恢复跳空行的老 bug(制造误报)",
     r'nxt = lines\[j\]\.strip\(\) if j < len\(lines\) else ""',
     'k = j\n            while k < len(lines) and lines[k].strip() == "":\n                k += 1\n            nxt = lines[k].strip() if k < len(lines) else ""'),
    ("split_row 丢转义保护",
     r'tmp = row\.strip\(\)\.replace\("\\\\\|", "\\x00"\)',
     "tmp = row.strip()"),
]


def mutate():
    src = io.open(check_doc.__file__, encoding="utf-8").read()
    print("=" * 68)
    print("变异测试：故意改坏 check_doc.py，要求自检**必须变红**")
    print("（改坏了还是绿 → 说明自检没有真的在断言）")
    print("=" * 68)
    survivors = []
    for item in MUTATIONS:
        name, pat = item[0], item[1]
        repl = item[2] if len(item) > 2 else None
        pairs = list(pat) if isinstance(pat, list) else [(pat, repl)]

        mutated, missed = src, []
        for p, r in pairs:
            if not re.search(p, mutated):
                missed.append(p)
                continue
            mutated = re.sub(p, r, mutated, count=1)
        if missed:
            print("SKIP     %-38s 正则未命中（check_doc 已改写，需同步本表）" % name)
            survivors.append(name + "（变异体未生效 = 没测到）")
            continue

        backup = {m: getattr(check_doc, m) for m in dir(check_doc) if not m.startswith("__")}
        try:
            exec(compile(mutated, "<mutant>", "exec"), check_doc.__dict__)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = run()
            killed = rc != 0
        finally:
            check_doc.__dict__.update(backup)
        print("%s %-38s %s" % ("KILLED  " if killed else "SURVIVED", name,
                               "" if killed else "← 自检没抓到，这条判据等于没测"))
        if not killed:
            survivors.append(name)

    print("-" * 68)
    if survivors:
        print("变异测试结论: FAIL —— %d 个变异体存活" % len(survivors))
        for s in survivors:
            print("  ✗", s)
        return 1
    print("变异测试结论: PASS —— %d 个变异体全部被自检杀死" % len(MUTATIONS))
    return 0


if __name__ == "__main__":
    sys.exit(mutate() if "--mutate" in sys.argv else run())
