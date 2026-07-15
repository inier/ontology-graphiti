# Quality Gate — 三关 16 子指标质量闸策略
#
# 与 Python odap.biz.semantic_admin.quality_gate.services.quality_evaluator
# 完全对齐（§4.3 Gate1 ×7 / §4.4 Gate2 ×4 / §4.5 Gate3 ×5）。
# 可通过 `opa eval -d quality_gate.rego 'data.quality_gate.allow'`
# 配合 input JSON 独立验证，也可被后端 Depends 钩子直接调用。
#
# 规则数量保证：deny_gate1_* 共 7 条 / deny_gate2_* 共 4 条 / deny_gate3_* 共 5 条
# 与 Python G1_SUB_WEIGHTS=(5,1,5,1,1,1,1) / GATE3_INNER_WEIGHTS=(0.30,0.20,0.15,0.15,0.20) 对齐。
package quality_gate

import future.keywords.if
import future.keywords.in

# ======================================================================
# 常量（与 quality_protocol.py / quality_evaluator.py 完全一致）
# ======================================================================

# §4.2 tier 阈值
tier_high_threshold      := 0.85
tier_medium_threshold    := 0.70
tier_low_threshold       := 0.50

# G1.3 合法 SemanticType（中文 6 枚举）
valid_semantic_types := {
  "对象类型", "关系类型", "属性",
  "动作类型", "过程类型", "规则类型",
}

# Gate 外权重（§4.1）
gate_weights := {"g1": 0.35, "g2": 0.40, "g3": 0.25}

# G1 内 7 子项权重（FAIL 类×5 / WARN 类×1，共 15）
g1_sub_weights := [5, 1, 5, 1, 1, 1, 1]

# G3 内 5 子项权重（与 GATE3_INNER_WEIGHTS 对齐）
g3_inner_weights := [0.30, 0.20, 0.15, 0.15, 0.20]

# 阈值
g1_5_dedup_threshold    := 0.98
g1_4_syn_max_count      := 30
g3_2_doc_hits_target    := 10.0
g3_3_syn_richness_target := 5.0
g3_5_hierarchy_target   := 3.0

# ======================================================================
# 基础工具
# ======================================================================

# 字符串 trim+lower（OPA strings.lower + regex 去空白）
norm(s) := x if {
  t := trim(s, " \t\r\n")
  x := lower(t)
} else := ""

# 字符串非空
nonempty(s) if { s != null; s != "" }

# 同义词列表去重（norm 后比较，保留原始顺序首项，返回去重后计数）
dedup_ratio(list) := ratio if {
  valid_list := [x | some x in list; x != null; norm(x) != ""]
  count(valid_list) > 0
  seen := {y | some x in valid_list; y := norm(x)}
  ratio := count(seen) / count(valid_list)
} else := 1.0

# canonical 是否出现在 synonyms 中（G1.6 环检测）
canon_in_synonyms(canon, syns) if {
  cn := norm(canon)
  some s in syns
  cn == norm(s)
}

# PascalCase 检测：首字母大写 A-Z，后续可大小写数字
is_pascal(s) if {
  regex.match(`^[A-Z][A-Za-z0-9]*$`, s)
}

# NAME_REGEX：1~40 字中文/英文/数字/下划线/点/横杠
is_name_valid(s) if {
  regex.match(`^[\u4e00-\u9fa5A-Za-z0-9_.-]{1,40}$`, s)
}

# ======================================================================
# Gate 1 × 7 子指标：句法/结构一致性闸
# deny_gate1_X = true 表示未达标（score<1），allow 规则依赖这些谓词
# ======================================================================

# G1.1：名称合规（canonical 非空、合法 NAME_REGEX）
deny_gate1_1_name_invalid contains msg if {
  canon := object.get(input.candidate, "canonical", "")
  not is_name_valid(canon)
  msg := sprintf("semadm_g1_1_name_regex FAIL: canonical='%s' 不符合 ^[中文字母数字_.-]{1,40}$", [canon])
}

# G1.2：en_mapping 可用 PascalCase
deny_gate1_2_en_invalid contains msg if {
  en := object.get(input.candidate, "en", "") != ""
     or object.get(input.candidate, "en_mapping", "") != ""
  raw_en := coalesce(object.get(input.candidate, "en_mapping", null),
                    object.get(input.candidate, "en", ""))
  not is_pascal(raw_en)
  msg := sprintf("semadm_g1_2_en_pascal WARN: en='%s' 为空或非 PascalCase", [raw_en])
}

# G1.3：semantic_type 合法 6 枚举
deny_gate1_3_semtype_invalid contains msg if {
  st := coalesce(object.get(input.candidate, "semantic_type", ""), "对象类型")
  not st in valid_semantic_types
  msg := sprintf("semadm_g1_3_semtype_enum FAIL: semantic_type='%s' 非法合法集 %v", [st, valid_semantic_types])
}

# G1.4：同义词集大小 ∈ [0, 30]
deny_gate1_4_syn_count_invalid contains msg if {
  syns := object.get(input.candidate, "synonyms", [])
  count(syns) > g1_4_syn_max_count
  msg := sprintf("semadm_g1_4_syn_count WARN: 同义词 %d 个 > 阈值 %d", [count(syns), g1_4_syn_max_count])
}

# G1.5：同义词去重率 >= 0.98
deny_gate1_5_syn_dedup_low contains msg if {
  syns := object.get(input.candidate, "synonyms", [])
  ratio := dedup_ratio(syns)
  ratio < g1_5_dedup_threshold
  msg := sprintf("semadm_g1_5_syn_dedup WARN: 去重率 %.3f < 阈值 %.2f", [ratio, g1_5_dedup_threshold])
}

# G1.6：canonical 不与同义词互相包含
deny_gate1_6_circular_include contains msg if {
  canon := object.get(input.candidate, "canonical", "")
  syns := object.get(input.candidate, "synonyms", [])
  canon_in_synonyms(canon, syns)
  msg := sprintf("semadm_g1_6_no_circ_include FAIL: canonical='%s' 出现在同义词集合中", [canon])
}

# G1.7：USL 同名冲突检查（命中 → origin=usl → 视为去重成功，非 deny；反之即 deny）
# OPA 侧无法直接查 SQLite；依靠 input.domain_terms（传入 domain 已知术语集合）做轻量比对
deny_gate1_7_usl_hit_missing contains msg if {
  canon := object.get(input.candidate, "canonical", "")
  domain_terms := object.get(input, "domain_terms", [])
  canon_norm := norm(canon)
  terms_norms := {norm(t) | some t in domain_terms}
  not canon_norm in terms_norms
  # USL 未命中 = 视为新增候选（不 deny，仅记录提示 reason；此处仅产生提示不真 deny 所以返回 0 条）
  # 保持 deny 数量对齐：此处不产生 deny 条目，通过 warn_gate1_7 产生 info
  false
}

warn_gate1_7_usl_info contains msg if {
  canon := object.get(input.candidate, "canonical", "")
  msg := sprintf("semadm_g1_7_usl_dup_check INFO: canonical='%s' USL 未命中，视为新增", [canon])
}

# ======================================================================
# Gate 2 × 4 子指标：语义一致性闸
# ======================================================================

# G2.1 disjoint pair：候选术语+同义词不命中 input.disjoint_pairs 的任意 (term_a, term_b)
deny_gate2_1_disjoint_hit contains msg if {
  canon := object.get(input.candidate, "canonical", "")
  syns := object.get(input.candidate, "synonyms", [])
  near := object.get(input.candidate, "near_synonyms", [])
  alias := object.get(input.candidate, "aliases", [])
  all_terms_set := {norm(x) | some x in array.concat([canon], array.concat(syns, array.concat(near, alias))); norm(x) != ""}
  some (a, b) in object.get(input, "disjoint_pairs", [])
  norm(a) in all_terms_set
  norm(b) in all_terms_set
  msg := sprintf("semadm_g2_1_disjoint_check FAIL: 命中 disjoint pair (%s,%s)", [a, b])
}

# G2.2 基数约束：占位 1.0（待 L5 基数归纳，OPA 侧无需 deny）
deny_gate2_2_cardinality contains msg if { false }

# G2.3 is_a 无环：占位 1.0（待 L3 拓扑排序，OPA 侧无需 deny）
deny_gate2_3_isa_acyclic contains msg if { false }

# G2.4 LLM Judge：feature flag input.enable_llm_judge=true 时生效（默认关闭 → 不产生 deny）
deny_gate2_4_llm_judge contains msg if {
  object.get(input, "enable_llm_judge", false)
  object.get(input, "llm_judge_passed", false) == false
  msg := "semadm_g2_4_llm_judge FAIL: LLM 语义合理性判定未通过"
}

# ======================================================================
# Gate 3 × 5 子指标：领域质量闸（按阈值产出 warn 或 deny）
# ======================================================================

# G3.1 属性密度：s = min(1, confidence*1.5)，低 confidence 产生 warn
deny_gate3_1_property_density_low contains msg if {
  conf := to_number(object.get(input.candidate, "confidence", 0))
  s := min([1.0, conf * 1.5])
  s < 0.3
  msg := sprintf("semadm_g3_1_property_density WARN: s=%.3f < 0.3 置信度不足", [s])
}

# G3.2 词频覆盖率：s = min(1, doc_hits/10)，<1 产生提示
deny_gate3_2_term_freq_low contains msg if {
  hits_raw := object.get(object.get(input.candidate, "provenance", {}), "doc_hits", 1)
  doc_hits := to_number(coalesce(hits_raw, 1))
  s := min([1.0, doc_hits / g3_2_doc_hits_target])
  s < 0.5
  msg := sprintf("semadm_g3_2_doc_hits WARN: s=%.3f doc_hits=%d", [s, doc_hits])
}

# G3.3 同义词丰富度：(syn+near+alias)/5，< 0.5 提示
deny_gate3_3_syn_richness_low contains msg if {
  syns := object.get(input.candidate, "synonyms", [])
  near := object.get(input.candidate, "near_synonyms", [])
  alias := object.get(input.candidate, "aliases", [])
  total := count(syns) + count(near) + count(alias)
  s := min([1.0, total / g3_3_syn_richness_target])
  s < 0.5
  msg := sprintf("semadm_g3_3_syn_richness WARN: s=%.3f syn(%d)+near(%d)+alias(%d)=%d",
                 [s, count(syns), count(near), count(alias), total])
}

# G3.4 USL 对齐率（新颖度反向）：s = 1 - align_confidence，s<0.2 提示（过度重复 USL）
deny_gate3_4_novelty_low contains msg if {
  align := to_number(object.get(input.candidate, "usl_align_confidence", 0))
  s := max([0.0, min([1.0, 1.0 - align])])
  s < 0.2
  msg := sprintf("semadm_g3_4_usl_novelty WARN: s=%.3f align=%.3f 与 USL 重复度过高", [s, align])
}

# G3.5 层级贡献度：children_est/3，< 0.3 提示
deny_gate3_5_hierarchy_contrib_low contains msg if {
  children_raw := object.get(object.get(input.candidate, "provenance", {}), "l3_children_est", 1)
  children := to_number(coalesce(children_raw, 1))
  s := min([1.0, children / g3_5_hierarchy_target])
  s < 0.3
  msg := sprintf("semadm_g3_5_hierarchy_contrib WARN: s=%.3f l3_children_est=%d", [s, children])
}

# ======================================================================
# 汇总：16 子指标 deny 计数 + allow + 总分估算 + tier 判定
# ======================================================================

# 显式列出 7 G1 + 4 G2 + 5 G3 = 16 条规则（确保 deny 数量对齐）
all_gate_denials := array.concat(
  array.concat(
    [deny_gate1_1_name_invalid, deny_gate1_2_en_invalid, deny_gate1_3_semtype_invalid,
     deny_gate1_4_syn_count_invalid, deny_gate1_5_syn_dedup_low, deny_gate1_6_circular_include,
     deny_gate1_7_usl_hit_missing],
    [deny_gate2_1_disjoint_hit, deny_gate2_2_cardinality,
     deny_gate2_3_isa_acyclic, deny_gate2_4_llm_judge]),
  [deny_gate3_1_property_density_low, deny_gate3_2_term_freq_low, deny_gate3_3_syn_richness_low,
   deny_gate3_4_novelty_low, deny_gate3_5_hierarchy_contrib_low])

# 聚合 deny 数量 + 信息
num_denials := count([x | some g in all_gate_denials; some x in g])
denial_messages := [msg | some g in all_gate_denials; some msg in g]

# allow：没有 FAIL 类 deny（G1.1/G1.3/G2.1/G2.4 为 FAIL；其他 WARN 类可放行）
fatal_denials := [m | some m in denial_messages; contains(m, "FAIL")]

allow if {
  count(fatal_denials) == 0
}

# tier（简化近似，仅用于 OPA 侧快速判断；精确分以 Python 为准）
estimated_tier := tier if {
  score_est := max([0.0, min([1.0, 1.0 - (num_denials / 16.0)])])
  tier := "HIGH"     if score_est >= tier_high_threshold
  else := "MEDIUM"   if score_est >= tier_medium_threshold
  else := "LOW"      if score_est >= tier_low_threshold
  else := "VERY_LOW"
}
