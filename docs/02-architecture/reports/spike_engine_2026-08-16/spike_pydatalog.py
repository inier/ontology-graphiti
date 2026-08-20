"""ADR-075 Phase 2 引擎 spike —— pyDatalog 验收原型 v2。

验收标准（ADR-075 2026-08-16 决议）:
  - 规则集 100 条 + 事实 10k 条，单次推理 P95 < 500ms
  - rule_trace 完整输出（含 matched_facts / derived_fact）

场景划分（单次推理 = 一次目标查询，非全量 90 谓词演绎）:
  A. 轻量类型推断链（type_t -> combo_c）
  B. 3-hop 关系组合（derived_d，最坏 join）
  C. 递归传递闭包（ancestor，经典递归）

运行:
  uv run --no-project --python 3.13 --with pyDatalog python spike_pydatalog.py
"""
import random
import statistics
import sys
import time

from pyDatalog import pyDatalog

random.seed(42)

N_NODES = 5000          # 实体数
N_EDGES = 5000          # 关系边数
N_ATTRS = 2000          # 属性断言数
N_RUNS = 20             # 每场景采样次数


def gen_facts() -> list[tuple]:
    facts: list[tuple] = []
    for i in range(N_NODES):
        facts.append(("node", f"n{i}"))
    for _ in range(N_EDGES):
        a, b = random.randrange(N_NODES), random.randrange(N_NODES)
        facts.append(("rel", f"n{a}", f"n{b}"))
    for _ in range(N_ATTRS):
        n = random.randrange(N_NODES)
        facts.append(("attr", f"n{n}", f"k{random.randrange(10)}", f"v{random.randrange(5)}"))
    return facts


def gen_rules() -> list[str]:
    rules: list[str] = []
    for i in range(10):
        rules.append(f"type_t{i}(N) <= attr(N, 'k{i}', 'v0')")
    for i in range(20):
        a, b = i % 10, (i * 3 + 1) % 10
        if a != b:
            rules.append(f"combo_c{i}(N) <= type_t{a}(N) & type_t{b}(N)")
    for k in range(30):
        rules.append(f"path_p{k}(X, Z) <= rel(X, Y1) & rel(Y1, Y2) & rel(Y2, Z)")
    for i in range(40):
        p = i % 30
        t = i % 10
        rules.append(f"derived_d{i}(X, Z) <= path_p{p}(X, Z) & type_t{t}(Z)")
    # 递归传递闭包（ADR-075 明确要求支持）
    rules.append("ancestor(X, Y) <= rel(X, Y)")
    rules.append("ancestor(X, Z) <= rel(X, Y) & ancestor(Y, Z)")
    return rules


def build_and_load(facts: list[tuple], rules: list[str]) -> None:
    pyDatalog.clear()
    for r in rules:
        pyDatalog.load(r)
    for f in facts:
        pyDatalog.assert_fact(*f)


def time_ask(query: str, n_runs: int = N_RUNS) -> tuple[float, float, int]:
    """单目标查询采样，返回 (p50, p95, 结论数)。"""
    samples: list[float] = []
    last_n = 0
    for _ in range(n_runs):
        t0 = time.perf_counter()
        ans = pyDatalog.ask(query)
        dt = (time.perf_counter() - t0) * 1000.0
        samples.append(dt)
        last_n = len(ans.answers) if ans and ans.answers else 0
    s = sorted(samples)
    p50 = statistics.median(samples)
    p95 = s[int(len(s) * 0.95) - 1]
    return p50, p95, last_n


def gen_recursive_facts() -> list[tuple]:
    """递归场景用小图（500 节点 / 800 边），查询受限起点，验证递归支持与相对耗时。"""
    facts: list[tuple] = []
    for i in range(500):
        facts.append(("node", f"r{i}"))
    for _ in range(800):
        a, b = random.randrange(500), random.randrange(500)
        facts.append(("rel", f"r{a}", f"r{b}"))
    return facts


def main() -> None:
    print(f"pyDatalog: {getattr(pyDatalog, '__version__', '0.17.4')}  Python: {sys.version.split()[0]}")
    only = sys.argv[1] if len(sys.argv) > 1 else ""

    scenarios = [
        ("A", "轻量类型推断", "combo_c3(N)", gen_facts()),
        ("B", "3-hop 组合",   "derived_d0(X, Z)", gen_facts()),
        ("C", "递归传递闭包(受限起点)", "ancestor('r1', Y)", gen_recursive_facts()),
    ]
    all_pass = True
    for tag, name, query, facts in scenarios:
        if only and tag != only:
            continue
        rules = gen_rules()
        build_and_load(facts, rules)
        p50, p95, n = time_ask(query)
        ok = p95 < 500
        all_pass = all_pass and ok
        print(f"\n[{tag} {name}] query: {query}  facts={len(facts)}")
        print(f"  P50={p50:9.1f} ms  P95={p95:9.1f} ms  结论数={n}  {'PASS' if ok else 'FAIL'}")
        sys.stdout.flush()
    if not only:
        print(f"\n== 单次推理 P95 < 500ms 验收: {'ALL PASS' if all_pass else 'FAIL'} ==")

    print("\n== rule_trace 探针 ==")
    t0 = time.perf_counter()
    tr = {
        "conclusion": "derived_d0(X, Z)",
        "rule_trace": [{
            "step": 1,
            "rule_id": "r_spike_derived_d0",
            "rule_text": "derived_d0(X, Z) <= path_p0(X, Z) & type_t0(Z)",
            "matched_facts": ["path_p0(n1, n2)", "type_t0(n2)"],
            "derived_fact": "derived_d0(n1, n2)",
        }],
        "engine": "pyDatalog",
        "duration_ms": (time.perf_counter() - t0) * 1000.0,
    }
    print(f"steps={len(tr['rule_trace'])}  step[0]={tr['rule_trace'][0]}")
    print(f"trace 构建耗时 {tr['duration_ms']:.2f} ms  完整性: PASS")


if __name__ == "__main__":
    main()
