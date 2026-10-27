#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uiux.md 交付门禁。

设计原则（写下来因为踩过）：
  1. 命名必须说真话。上一版把"不在本文档标题里"的引用命名为 broken，
     导致 §0/§13 这类**跨文档有效引用**被报成断链，读的人以为有 13 条失效引用。
     —— 一个说谎的变量名，比没有检查更危险。
  2. 跨文档引用要去目标文件核实，不能只扫本文档。
  3. 能用行号的给行号，不给"存在/不存在"这种需要二次求证的说法。
  4. **闸门数必须等于入口数**。本脚本有 `单文件` 与 `--all` 两条入口，
     第一版只给前者加了自检闸 —— 后果是"单文件拒绝出报告、汇总表照样全 0"，
     而人往往只看汇总表。同一项目里这条规律已出现第二次（架构的 AC-17 门禁
     只扫 `decision_hub/`，而 AC-17 的文字覆盖三个模块）。
     一般化：**覆盖范围比规范窄时，绿是判据的属性，不是被检查对象的属性。**
  5. **集合要和结论一起报**。"比对 73 张表 / 0 缺陷"会让读者以为压根没有第 74 个块，
     而缺陷常常就在被跳过的那个里 —— `spec.md` 有 8 条 AC 因为无分隔行从未进入比对，
     三轮检查都报"0"，那不是通过，是没查到。

用法：python check_doc.py [--verbose] [--all]
退出码：0 全绿，1 文档有缺陷，2 门禁自身不可信（自检失败，拒绝出报告）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "uiux.md")
# 跨文档引用可能指向的兄弟文档
SIBLINGS = ["prd.md", "architecture.md", "spec.md", "api-spec.yaml"]

# 允许只写编号不写名称的 EARS 项（团队词），其余编号引用必须带名称
NAMED_IDS = {
    "E33": "状态矩阵服务端强制",
    "E34": "写入原子",
    "E35": "裁决不得改选",
    "E36": "执行幂等与失败回写",
}
# 跨文档检索键：已成团队词，允许只写编号
RETRIEVAL_KEYS = {"E26", "E27"}

EMOJI = re.compile(r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
HEX_ALLOW = {"#fff", "#000", "#ffffff", "#000000"}
BOUNCE = re.compile(r"cubic-bezier\(\s*0?\.68")
HEADING = re.compile(r"^(#{1,4})\s+(\d+)\.", re.M)
SEC_REF = re.compile(r"§(\d+)(?![\d.])")
AC_REF = re.compile(r"AC-(\d+)")


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def heading_map(text):
    """{编号: 行号}，只收 `# 1. xx` 这种带编号的标题。"""
    out = {}
    for m in HEADING.finditer(text):
        out.setdefault(int(m.group(2)), text[: m.start()].count("\n") + 1)
    return out


def line_of_index(text, idx):
    return text[:idx].count("\n") + 1


def split_row(row):
    """按 `|` 切单元格，但保护转义的 `\\|`。

    不处理转义会把 `GET\\|POST`、`system \\| user`、`a \\|\\| b` 这类**写法正确**的
    单元格切成多列，从而把好文档报成坏的 —— 这比漏报更糟，因为它会逼人去改
    本来没写错的地方。第一版检查器就踩了这个坑（8 处全是误报）。
    """
    tmp = row.strip().replace("\\|", "\x00")
    if tmp.startswith("|"):
        tmp = tmp[1:]
    if tmp.endswith("|"):
        tmp = tmp[:-1]
    return tmp.split("|")


def fenced_mask(lines):
    """标记 fenced code block 内的行。

    为什么必须跳：代码块里的 `|` **不是**表格分隔符。prd.md 的 §3.1 目标链路
    是一张 ASCII 流程图（L110-129），里面 7 行只有孤零零一个 `|` 当箭头用。
    不跳代码块的话，这 7 行会被报成"表格列数不一致"——然后有人会去把那张
    **本来完全正确**的流程图改掉。
    误报的代价从来不是"多看一眼"，是逼人去动没写坏的地方。
    """
    mask = [False] * len(lines)
    infence = False
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("```") or s.startswith("~~~"):
            infence = not infence
            mask[i] = True
            continue
        mask[i] = infence
    return mask


def odd_backtick_cell(row):
    """返回第一个反引号数为奇数的单元格（说明行内代码被 `|` 切断了）。

    反引号**不保护** `|`。`decided|failed` 就算写在反引号里，GFM 也照样
    按 `|` 切列，于是 `decided` 和 `failed` 分到两个单元格，整行右移，
    最后一列被截断丢弃。正确写法是 `decided\\|failed`。

    这个判据比"列数超出"更精确：它不依赖列数是否刚好对上。
    """
    for c in split_row(row):
        if c.count("`") % 2 == 1:
            return c.strip()[:50] or "(空)"
    return None


def check_tables(lines):
    """表格结构问题，按后果严重度分开报。

    **所有比较的基准都是表头（header），不是相邻行。**
    这一点是本文件第二个"踩过才知道"的原则：

      拿实例跟实例比，在所有实例一致地错时永远通过。
      —— 一张表"整表一致地多一列"（表头 3 列、每行 4 个单元格）时，
         行与行完全一致，行间互比的门禁 100% 通过，而 GFM 会把每行第 4 个
         单元格**静默丢弃**（PM 在 prd.md §4.2 丢掉的 6 行解释文字就是这么没的）。
         基准必须是规范源（表头），不能是同侪实例。

    A. 单元格数 > 表头  → GFM **截断并静默丢弃**超出部分。内容真的没了，且不报错。
                           **ERROR**。最阴的一条，渲染出来只是"少了一句话"。
    B. 单元格数 < 表头  → 只是末尾空列，最多难看。**WARN**，不必拦。
    C. 数据行未以 `|` 收尾 → 表格被裸换行撑断。**ERROR**。
    D. 表头列数 ≠ 分隔行列数 → 按 GFM 规范**整张表都不成立**，全部退化成段落文字
       （每个 `|` 都裸露在正文里）。比 A 更糟：不是少一句，是整块塌掉。**ERROR**。
       这是上一版的盲区：只比数据行，从不比 header 与 separator。
    E. 单元格内反引号数为奇数 → **行内代码被 `|` 切断了**。
       反引号**不保护** `|`：`decided|failed` 写在反引号里一样会被当列分隔，
       GFM 于是把 `decided` 和 `failed` 拆成两列，整行右移，最后一列被丢弃。
       必须写成 `decided\\|failed`。**ERROR**。
       （architecture.md L918/L919 就是这么坏掉的，丢的正好是最后一列。）

    能力边界（写下来免得别人高估它）：
      列数检查**抓不到"内容错位"**。表头 4 列、某行也是 4 个单元格、但内容整体
      左移一列——列数完全正确，语义全错。那种只能靠表头与内容的语义核对，
      脚本没有判断力。别把"TABLE_* 全绿"读成"表格内容全对"。
    """
    mask = fenced_mask(lines)
    truncated, underfill, unclosed, sep_bad = [], [], [], []
    spilled, spilled_weak, glued, broken_code = [], [], [], []
    orphan_row = []
    n_tables = 0
    i = 0
    while i < len(lines):
        if mask[i]:
            i += 1
            continue
        head = lines[i].strip()
        sep = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if head.startswith("|") and re.match(r"^\|[\s:\-|]+\|$", sep):
            n_tables += 1
            ncol = len(split_row(head))          # 基准 = 表头，不是任何数据行
            nsep = len(split_row(sep))
            if nsep != ncol:
                sep_bad.append((i + 2, nsep, ncol))
            # 数据行从 i+2 起扫：表头(i)与分隔行(i+1)是**结构行**，不是内容行。
            # 让分隔行参与"单元格 vs 表头"比较，会把"整表不成立"误报成
            # "内容被截断"——两件事的后果完全不同（前者整块塌、后者少一句），
            # 而误报会让人去改分隔行的字数，南辕北辙。
            j = i + 2
            last_row = i + 1
            while j < len(lines) and not mask[j] and lines[j].strip().startswith("|"):
                row = lines[j].strip()
                cells = len(split_row(row))
                if cells > ncol:
                    truncated.append((j + 1, cells, ncol))
                elif cells < ncol:
                    underfill.append((j + 1, cells, ncol))
                if not row.endswith("|"):
                    unclosed.append((j + 1, row[:50]))
                last_row = j
                j += 1
            # E：行内代码被 `|` 切断。抽查表头与每一行（含分隔行，无副作用）。
            for k in range(i, j):
                bad = odd_backtick_cell(lines[k])
                if bad:
                    broken_code.append((k + 1, bad))
            # --- 表格是否被切断 ---
            # 第一版判据是"块后（跳过空行）第一个非空行不以 | 开头，且本节内又出现表格"。
            # 实测在 uiux.md 上命中 9 次，**9 次全是误报** —— 命中的是
            # "表格 → 空行 → 加粗小标题 → 空行 → 另一张表"这种完全正常的写法。
            # 误报的代价不是"多看一眼"，而是**教会读的人忽略整个门禁**。
            # 所以判据改成只在结构上可判的地方报警：
            #
            #   S1 紧跟表格的第一行（**不跳空行**）以 `|` 收尾
            #      → 这一行几乎必然是**从表格里掉出来的内容行**（成因：单元格内裸换行）。
            #        正文极少以 `|` 结尾。**ERROR**。
            #   S2 紧跟表格的第一行非空、不含 `|`
            #      → 可能是正常分段，也可能漏了 `|`。**WARN**，需人工看。
            #   S3 紧跟表格的是空行 → 正常分段，不报。
            nxt = lines[j].strip() if j < len(lines) else ""
            if nxt and not nxt.startswith("|"):
                if nxt.endswith("|"):
                    spilled.append((j + 1, nxt[:60]))
                elif "|" in nxt:
                    spilled_weak.append((j + 1, nxt[:60]))
                else:
                    glued.append((j + 1, nxt[:40]))
            i = last_row + 1
        elif head.startswith("|"):
            # F：以 `|` 开头、但块的第 2 行不是分隔行 → 按 GFM **不构成表格**，
            # 整块会渲染成正文，`|` 裸在页面上。
            #
            # 这一类必须报，不能跳。跳过等于把它从"被检查的集合"里剔除，
            # 而它几乎总是"想写表、漏了表头/分隔行"的手误 ——
            # **跳过之后它永远不会被修掉，因为没有任何检查知道它存在。**
            # （实证：prd.md §13.1 一个空行把表切成两块，后三行裸奔三轮检查；
            #   本文档 L1032 也有两行同款。）
            j = i
            while j < len(lines) and not mask[j] and lines[j].strip().startswith("|"):
                j += 1
            orphan_row.append((i + 1, j - i, head[:60]))
            i = j
        else:
            i += 1
    # 返回 dict 而非 tuple：键名自解释，调用方想取哪一类就取哪一类。
    # tuple 解包顺序一错，多个检测器的结果会互相冒充，而且不报错。
    return {
        "truncated": truncated,
        "underfill": underfill,
        "unclosed": unclosed,
        "sep_mismatch": sep_bad,
        "spilled": spilled,
        "spilled_weak": spilled_weak,
        "glued": glued,
        "broken_code": broken_code,
        "orphan_row": orphan_row,
        # stats 不是缺陷，是"判据覆盖了多少"——单独放，别混进缺陷列表。
        # PM 的判据：**集合和结论要分开报**。只报"进入比对 73 张、0 缺陷"，
        # 读者会以为压根没有第 74 个块，而缺陷往往就藏在被跳过的那个里。
        "stats": {"tables": n_tables, "orphan": len(orphan_row)},
    }


def check_orphan_lists(lines):
    """表格块之后紧跟缩进列表项：内容可能从表格里掉出来了。"""
    out = []
    mask = fenced_mask(lines)
    i = 0
    while i < len(lines):
        if mask[i]:
            i += 1
            continue
        head = lines[i].strip()
        sep = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if head.startswith("|") and re.match(r"^\|[\s:\-|]+\|$", sep):
            j = i + 1
            while j < len(lines) and not mask[j] and lines[j].strip().startswith("|"):
                j += 1
            k = j
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k < len(lines) and re.match(r"^\s{1,4}([-*]|\d+\.) ", lines[k]):
                out.append((k + 1, lines[k].strip()[:50]))
            i = j
        else:
            i += 1
    return out


# ---------------------------------------------------------------- 自检
# 「检查器报 0」有两种可能：文档真的干净，或者检查器根本没在跑。
# 只有用**已知缺陷样例**喂它、并要求它必须抓到，才能区分这两者。
#
# 所以自检不是可选的开发工具，它是门禁的一部分：main() 第一件事就跑它，
# 不通过就 EXIT=2 且**拒绝出报告**。理由：
#   判据被改坏后，扫文档仍然是 0，而且没人知道。
#   没有红样例的 0，等于没有 0。
SELF_CHECK = [
    # (名称, 文本, 期望命中数)
    ("正常 3 列表格", """
| 列A | 列B | 列C |
|---|---|---|
| 1 | 2 | 3 |
""", {"truncated": 0, "underfill": 0, "unclosed": 0, "sep_mismatch": 0}),
    ("整表一致多一列(>表头)", """
| 列A | 列B | 列C |
|---|---|---|
| 1 | 2 | 3 | 第四格被 GFM 丢弃 |
| 4 | 5 | 6 | 这行也会丢 |
""", {"truncated": 2}),
    ("少一列(<表头)", """
| 列A | 列B | 列C | 列D |
|---|---|---|---|
| 1 | 2 | 3 |
""", {"underfill": 1}),
    # PM 象限①：表头 3 列、7 行只有 2 格。真实发生过（prd.md §4.2 修前）。
    ("7 行少一格(PM 象限①)", """
| 列A | 列B | 列C |
|---|---|---|
| 1 | 2 |
| 1 | 2 |
| 1 | 2 |
| 1 | 2 |
| 1 | 2 |
| 1 | 2 |
| 1 | 2 |
""", {"underfill": 7}),
    ("单元格内裸换行", """
| 列A | 列B |
|---|---|
| 1 | 长文本我在单元格里换行
第二段 |
""", {"unclosed": 1, "spilled": 1}),
    ("表头与分隔行不符", """
| 列A | 列B | 列C |
|---|---|---|---|
| 1 | 2 | 3 |
""", {"sep_mismatch": 1}),
    ("反引号内裸|切断单元", """
| # | 迁移 | 同 patch |
|---|---|---|
| 3 | `decided|failed → executing` | 顶层 action_record_id |
""", {"truncated": 1, "broken_code": 1}),
    ("反引号内用\\\\|转义(正确)", """
| # | 迁移 | 同 patch |
|---|---|---|
| 3 | `decided\\|failed → executing` | 顶层 action_record_id |
""", {"broken_code": 0, "truncated": 0}),
    # PM 象限②：ASCII 流程图，必须静默。
    ("ASCII 流程图(PM 象限②)", """
```
[1] 场景/问答发起
      |
      |  用户可以选择「仅记录待决策」
      v
[2] 待决策队列
      |
      v
```
""", {"truncated": 0, "underfill": 0, "sep_mismatch": 0}),
    ("代码块内markdown表(正常)", """
```
| 列A | 列B | 列C |
|---|---|---|
| 1 | 2 | 3 | 会被丢弃 |
```
""", {"truncated": 0}),
    ("表格后空行接说明段(正常)", """
| 列A | 列B |
|---|---|
| 1 | 2 |

**为什么不这么做**（记录理由）：

批次数据来自上游。
""", {"glued": 0, "spilled": 0}),
    # 下面两条覆盖 glued / spilled_weak —— 没有它们，这两个检测器就没人看着了
    # （变异测试会报 SURVIVED；这是"砍用例砍过头"的实测教训）。
    ("块后紧贴正文(弱提示)", """
| 列A | 列B |
|---|---|
| 1 | 2 |
以上为概要，详见下节。
""", {"glued": 1}),
    ("块后行含|未收尾(更弱)", """
| 列A | 列B |
|---|---|
| 1 | 2 |
第三行的内容丢了分隔符 | 但也可能只是正文
""", {"spilled_weak": 1}),
    # PM 象限⑤（他后来补的实证）：以 | 开头但块内没有分隔行 → 按 GFM 不成表，
    # 整块渲染成裸文本。prd.md §13.1 与本文档 L1032 都是这个形态。
    ("孤立表格行(无分隔行)", """
**正文段落**：下面是应为表格的两行。

| `PrecedentSearch` | 复用，需加 2 个可选 prop | 见 §6.1 |
| `ImpactPanel` | 复用，需改完整度文案 | 见 §6.3 |

**正文继续**。
""", {"orphan_row": 1}),
    ("正常表格不该被当成孤立行", """
| 列A | 列B |
|---|---|
| 1 | 2 |
""", {"orphan_row": 0}),
]

# PM 象限③④：这两类**必须抓不到**，而且要写进文档的盲区清单。
# 自检断言它们命中数为 0 —— 不是为了证明"没问题"，是为了证明"我们没在假装能判"。
# 如果哪天判据改进到能抓到它们，本用例会红，提示把条目从盲区清单里删掉（而不是留着
# 一个已经不需要的人工核对动作）。
#
# **每条必须写清"哪一层没有残差"**，不能只写"抓不到"。
# 只写"抓不到"，下一个人会当成"实现不够努力"，于是去加强判据 —— 而按定义不会有结果，
# 结局是加出一条误报，并顺手把真缺陷埋掉。写清哪一层无残差，才能让人知道该换一层
# （渲染层 / 语义层），而不是加码。
BLIND_SPOTS = [
    # ③ 真实发生过：prd.md §2.1 上一版整行左移一列。
    ("内容错位（列数全对）", """
| # | 用户在哪里遇到它 | 用户能做什么 | 数据存在哪里 |
|---|---|---|---|
| 1 | Agent 页 | 浏览列表 | 内存字典 |
| 2 | 智能页 | 输入 ID | Neo4j 节点 |
""", "**计数层无残差**：列数完全正确、每格都在，残差只存在于『表头语义 ↔ 单元格内容』之间。"
     "要判它得比对列语义，那是语义层，正则没有判断力。改用人工对表头读一遍。"),
    # ④ 计数抵消：一处裸管道多切一格 + 别处少一个真分隔符。
    ("计数抵消（裸管道补齐缺格）", """
| 列A | 列B | 列C |
|---|---|---|
| 1 | 2 | 3 |
| 4 | 状态: decided | failed |
""", "**计数层无残差**：裸管道与真分隔符在字节层等价，两处错误抵消后 cells 数恰好等于表头。"
     "要判它只能换到**渲染层**（渲染成 HTML 后比对 DOM 单元格数），代价是引入会升级的第三方。"
     "改用写作规范预防：单元格内需字面管道一律写 \\|。"),
]


def self_check():
    """返回失败信息列表；空列表表示判据今天仍然认得出已知缺陷。"""
    bad = []
    for name, text, expect in SELF_CHECK:
        res = check_tables(text.strip("\n").split("\n"))
        got = {k: len(v) for k, v in res.items() if isinstance(v, list)}
        for k, want in expect.items():
            if got[k] != want:
                bad.append("%s: %s 期望 %d 实得 %d" % (name, k, want, got[k]))
    for name, text, why in BLIND_SPOTS:
        res = check_tables(text.strip("\n").split("\n"))
        got = {k: len(v) for k, v in res.items() if isinstance(v, list)}
        hit = {k: v for k, v in got.items() if v}
        if hit:
            bad.append("%s: 已知盲区却被检出 %s —— 若判据确实变强了，"
                       "请从文档盲区清单删掉该条并更新本用例（原盲区理由：%s）"
                       % (name, hit, why))
    return bad


def scan_all():
    """扫整个规格目录，用**同一套判据**给四份文档出表格健康度。

    为什么要在脚本里做，而不是命令行一行流：
      `python -c "...$..."` 里的 `$` 会被 shell 先吃掉，正则静默失效，
      于是每份文档都"干净"。**报数和判据必须住在同一个进程里**，
      否则你永远不知道那个 0 是文档的 0 还是 shell 的 0。

    另外：跨文档一致性只能这样看。四份文档各跑各的门禁时，
    "PRD 有 7 行、UIUX 有 0 行"这种差异永远不会自己冒出来。
    """
    print("=" * 68)
    print("全目录表格结构扫描（基准 = 表头列数）")
    print("=" * 68)
    # --all 也必须先自检。否则它就是一条绕过闸门的路：
    # 判据坏了的时候，单文件模式拒绝出报告，--all 却照样给你一张全 0 的表。
    # 一个能绕过的闸门，等于没有闸门。
    bad = self_check()
    if bad:
        print("self-check        FAIL —— 门禁自身不可信，拒绝出报告")
        for b in bad:
            print("   ✗", b)
        print("-" * 68)
        print("结论： 不可用（EXIT=2）。先修 check_doc.py，不要相信它报出的任何数字。")
        return 2
    print("self-check        OK（%d 例自检 + %d 例盲区确认）" % (len(SELF_CHECK), len(BLIND_SPOTS)))
    total_bad = 0
    for name in ["uiux.md", "spec.md", "prd.md", "architecture.md", "api-spec.yaml"]:
        p = os.path.join(HERE, name)
        if not os.path.exists(p):
            print("%-16s (缺失)" % name)
            continue
        lines = load(p).split("\n")
        t = check_tables(lines)
        mask = fenced_mask(lines)
        n_tables = t["stats"]["tables"]
        n_orphan = t["stats"]["orphan"]
        # 代码块里"长得像表头"的块：不参与比对，但也要**报出数量**。
        n_fenced = sum(1 for i in range(len(lines) - 1)
                       if mask[i] and lines[i].strip().startswith("|")
                       and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()))
        bad_keys = ("truncated", "underfill", "unclosed", "sep_mismatch",
                    "spilled", "broken_code", "orphan_row")
        bad = sum(len(t[k]) for k in bad_keys)
        total_bad += bad
        # **集合和结论分开报**：只报"比对 73 张 / 0 缺陷"，读者会以为压根没有第 74 个块。
        # 缺陷常常就在被跳过的那个里（prd.md §13.1 就是这样活过三轮检查的）。
        print("%-16s 比对 %-3d ｜ 跳过 %d（无分隔行 %d / 代码块内 %d）｜ 缺陷 %-3d %s"
              % (name, n_tables, n_orphan + n_fenced, n_orphan, n_fenced, bad,
                 {k: len(v) for k, v in t.items() if isinstance(v, list) and v} or "clean"))
        for k in bad_keys:
            for x in t[k][:6]:
                print("      %-13s L%d %s" % (k.upper(), x[0], x[1:]))
    print("-" * 68)
    print("合计缺陷行 %d" % total_bad)
    return 1 if total_bad else 0


def main(verbose=False):
    if "--all" in sys.argv:
        return scan_all()

    # 第一步永远是自检：判据今天还认不认得出已知缺陷？
    # 不通过就**拒绝出报告**——否则下面的"全 0"会被人当成"文档没问题"。
    bad = self_check()
    if bad:
        print("=" * 66)
        print("uiux.md 交付门禁")
        print("=" * 66)
        print("self-check        FAIL —— 门禁自身不可信，拒绝出报告")
        for b in bad:
            print("   ✗", b)
        print("-" * 66)
        print("结论： 不可用（EXIT=2）。先修 check_doc.py，不要相信它报出的任何数字。")
        return 2

    text = load(TARGET)
    lines = text.split("\n")
    fail = []

    print("=" * 66)
    print("uiux.md 交付门禁")
    print("=" * 66)
    clean_cases = len([1 for _, _, e in SELF_CHECK if not any(e.values())])
    print("self-check        OK（%d 例自检：%d 例已知缺陷必抓 + %d 例正常写法必不报；"
          "另 %d 例已知盲区确实抓不到）"
          % (len(SELF_CHECK), len(SELF_CHECK) - clean_cases, clean_cases, len(BLIND_SPOTS)))
    print("lines             %d" % len(lines))

    # --- 硬规则 ---
    n = len(EMOJI.findall(text))
    print("emoji             %d" % n)
    if n:
        fail.append("emoji %d" % n)
        if verbose:
            for m in EMOJI.finditer(text):
                print("   L%d %s" % (line_of_index(text, m.start()), m.group()))

    bad_hex = [h for h in HEX.findall(text) if h.lower() not in HEX_ALLOW]
    print("hex(非白名单)     %d" % len(bad_hex))
    if bad_hex:
        fail.append("hex %d" % len(bad_hex))
        if verbose:
            print("   ", bad_hex[:10])

    n = len(BOUNCE.findall(text))
    print("bounce 缓动       %d" % n)
    if n:
        fail.append("bounce %d" % n)

    # --- 表格结构 ---
    t = check_tables(lines)
    truncated = t["truncated"]
    print("TABLE_TRUNCATED   %d   (单元格 > 表头 → GFM 静默丢弃内容，ERROR)" % len(truncated))
    if truncated:
        fail.append("表格内容被截断 %d" % len(truncated))
        for x in truncated[:8]:
            print("   L%d 有 %d 个单元格但表头 %d 列 → 第 %d 列起被丢弃" % (x[0], x[1], x[2], x[2] + 1))

    print("TABLE_UNDERFILL   %d   (单元格 < 表头 → 仅末尾空列，WARN)" % len(t["underfill"]))
    for x in t["underfill"][:8]:
        print("   L%d 有 %d 个单元格但表头 %d 列（可接受，确认不是漏写）" % x)

    print("TABLE_UNCLOSED    %d   (数据行未以 | 收尾 → 表格被撑断)" % len(t["unclosed"]))
    if t["unclosed"]:
        fail.append("表格被撑断 %d" % len(t["unclosed"]))
        for x in t["unclosed"][:5]:
            print("   L%d 未以 | 收尾: %s" % x)

    print("TABLE_SEP_MISMATCH %d  (表头列数 ≠ 分隔行列数 → 整表不成立，全部退化成段落，ERROR)" % len(t["sep_mismatch"]))
    if t["sep_mismatch"]:
        fail.append("表头与分隔行列数不符 %d" % len(t["sep_mismatch"]))
        for x in t["sep_mismatch"][:5]:
            print("   L%d 分隔行 %d 列 ≠ 表头 %d 列" % x)

    print("TABLE_SPILLED     %d   (紧跟表格的行以 | 收尾 → 单元格内裸换行把内容挤出了表格，ERROR)" % len(t["spilled"]))
    if t["spilled"]:
        fail.append("表格行掉出表格 %d" % len(t["spilled"]))
        for x in t["spilled"][:5]:
            print("   L%d 紧跟表格却以 | 收尾: %s" % x)

    print("TABLE_BROKEN_CODE %d   (单元格内反引号数为奇数 → 行内代码被 | 切断，整行右移，末列被丢弃，ERROR)"
          % len(t["broken_code"]))
    if t["broken_code"]:
        fail.append("行内代码被竖线切断 %d" % len(t["broken_code"]))
        for x in t["broken_code"][:6]:
            print("   L%d 反引号不成对（应写 \\|）: %s" % x)

    print("TABLE_SPILLED_WEAK %d  (紧跟表格的行含 | 但未收尾 → 疑似掉出，需人工确认)" % len(t["spilled_weak"]))
    for x in t["spilled_weak"][:5]:
        print("   L%d %s" % x)

    print("TABLE_GLUED      %d   (紧跟表格的非空行不含 | → 多为正常分段，仅提示)" % len(t["glued"]))
    for x in t["glued"][:3]:
        print("   L%d %s" % x)

    print("TABLE_ORPHAN_ROW %d   (以 | 开头但块内无分隔行 → GFM 不成表，整块渲染成裸文本，ERROR)"
          % len(t["orphan_row"]))
    if t["orphan_row"]:
        fail.append("孤立表格行 %d" % len(t["orphan_row"]))
        for x in t["orphan_row"][:6]:
            print("   L%d 起 %d 行没有分隔行: %s" % x)

    orphan = check_orphan_lists(lines)
    print("TABLE_ORPHAN_LIST %d   (表格后紧跟缩进列表，需人工确认)" % len(orphan))
    for x in orphan[:5]:
        print("   L%d %s" % x)

    # --- 引用：本文档 / 跨文档 分开算 ---
    own = heading_map(text)
    refs = {}
    for m in SEC_REF.finditer(text):
        k = int(m.group(1))
        refs.setdefault(k, []).append(line_of_index(text, m.start()))

    own_broken = sorted(k for k in refs if k not in own)
    external = {}
    for k in own_broken:
        for sib in SIBLINGS:
            p = os.path.join(HERE, sib)
            if not os.path.exists(p):
                continue
            h = heading_map(load(p))
            if k in h:
                external[k] = (sib, h[k])
                break
    # 关键：真断链 = 本文档没有 **且** 兄弟文档也没有。
    # 第一版把"不在本文档"直接叫 broken，导致 §0/§13 这类跨文档有效引用
    # 被报成断链，读的人以为有一堆失效引用。变量名说谎比不检查更危险。
    truly_broken = [k for k in own_broken if k not in external]

    print("-" * 66)
    print("§ 引用总数        %d 处 / %d 个编号" % (sum(len(v) for v in refs.values()), len(refs)))
    print("  ├ 本文档内有效   %d 个编号" % len([k for k in refs if k in own]))
    print("  ├ 跨文档有效     %d 个编号" % len(external))
    print("  │   " + ("; ".join("§%d→%s:%d" % (k, v[0], v[1]) for k, v in sorted(external.items())) or "无"))
    print("  └ 真断链         %d 个编号 %s" % (len(truly_broken), truly_broken or ""))
    if truly_broken:
        fail.append("断链引用 %s" % truly_broken)
        for k in truly_broken:
            print("   §%d 本文档与兄弟文档均无此编号。引用处 L%s" % (k, refs[k]))

    # --- AC-xx 引用：指向 spec.md 的验收编号 ---
    ac_refs = sorted({int(m.group(1)) for m in AC_REF.finditer(text)})
    ac_defined = set()
    spec_path = os.path.join(HERE, "spec.md")
    if os.path.exists(spec_path):
        ac_defined = {int(m.group(1)) for m in AC_REF.finditer(load(spec_path))}
    ac_missing = [k for k in ac_refs if ac_defined and k not in ac_defined]
    print("AC 引用           %s ｜ spec.md 已定义 %d 条 ｜ 缺失 %s"
          % (ac_refs or "无", len(ac_defined), ac_missing or "无"))
    if ac_missing:
        fail.append("AC 编号缺失 %s" % ac_missing)

    # --- 裸编号（团队词必须带名称）---
    bare = []
    for idx, line in enumerate(lines, 1):
        for key, name in NAMED_IDS.items():
            if key in line and name not in line:
                bare.append((idx, key))
    print("BARE_ID_REFS      %d" % len(bare))
    if bare:
        fail.append("裸编号 %d" % len(bare))
        for x in bare[:5]:
            print("   L%d %s 缺名称" % x)

    # --- 降 P1 项必须写明"不渲染"，不能只说降级 ---
    print("-" * 66)
    print("结论：", "PASS" if not fail else "FAIL")
    if fail:
        for f in fail:
            print("  ✗", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(verbose="--verbose" in sys.argv))
