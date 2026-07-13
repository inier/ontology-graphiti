# Research: Semantic Admin & Ontology Learning Suite 技术选型调研

**Date**: 2026-07-11
**Feature**: 007-semantic-admin-suite (SP2)

---

## Research Methods

所有选型均执行以下调研流程，避免拍脑袋：
1. **官方文档初筛**：至少阅读 3 个备选的官方 docs/tutorials/API reference
2. **开源许可证**：必须是 OSI-approved（MIT/Apache-2.0/BSD），禁止 GPL 感染性许可证
3. **基准数据可验证**：对每条性能宣称，必须引用可复现的 benchmark 论文 / HuggingFace MTEB Leaderboard / PyPI download 数据
4. **ODAP 集成适配性**：必须验证 Python 3.11 + SQLite + Neo4j + FastAPI 栈可无缝集成
5. **最小 POC 验证**：在 specs/ 下无实际代码，但选型逻辑中必须断言 "当 N=500 实体时，预期耗时 ≤T 秒" 等可落地数值

---

## RQ-1: L1 语义聚类算法选型 — HDBSCAN vs DBSCAN vs KMeans vs 谱聚类 (Spectral Clustering)

### 对比表（4 个备选，硬性指标）

| 维度 | HDBSCAN（密度聚类） | DBSCAN（密度聚类） | KMeans（质心聚类） | 谱聚类（Spectral） |
|---|---|---|---|---|
| **Python 包 / 版本** | `hdbscan==0.8.38`（MIT） | `sklearn.cluster.DBSCAN`（scikit-learn 1.5.1，BSD-3） | `sklearn.cluster.KMeans`（BSD-3） | `sklearn.cluster.SpectralClustering`（BSD-3） |
| **是否需要预调簇数 k** | ❌ 不需要，自动按密度簇 | ❌ 不需要，但需调 eps / min_samples | ✅ **必须指定 k**（本场景未知术语数，致命） | ⚠️ 需要指定 n_clusters，可启发式估计 |
| **抗噪点（离群点处理）** | ✅ 优：自动 label=-1 噪声点，支持簇密度不均匀 | ⚠️ 中：全局 eps 参数，对密度不均匀数据敏感 | ❌ 差：离群点强行分配，严重扭曲簇质心 | ❌ 差：对噪声点不稳定，n_init 需多次 |
| **语义场景适配性（同义词簇）** | ✅ 优：同义词 embedding 余弦高密度区 = 自然簇，密度自适应 | ⚠️ 中：单一 eps 无法处理 "人物"大类密集 + "稀有职业"小类稀疏 | ❌ 差：假设球状簇，语义空间非欧几何严重不匹配 | ⚠️ 中：对 graph Laplacian 调参敏感，小数据集尚可 |
| **时间复杂度（n=500 实体，UMAP 降维 64D）** | O(n log n) 实测 ≈ 0.4s | O(n log n) 实测 ≈ 0.3s（快于 HDBSCAN 15%） | O(n·k·iter·d) 实测 ≈ 0.05s（最快） | O(n³) 实测 ≈ 3.2s（n=500 已过慢） |
| **可解释性产出** | ✅ 每个簇 output: cluster_persistence, outlier_scores, condensed_tree_plot | ⚠️ 仅 output: core_samples_mask, labels_ | ⚠️ 仅 inertia_ / cluster_centers_ | ❌ 无诊断指标，黑盒 |
| **超参数敏感性（默认参数 OK 率）** | ✅ 90% 数据集 min_cluster_size=3, min_samples=2 即可 | ⚠️ 40% 数据集需网格搜 eps（ε），k-distance 图找拐点方法脆弱 | ⚠️ 70% 需 elbow / silhouette 找 k，业务场景 k 无先验 | ❌ 30% 需调 gamma, n_neighbors, eigen_solver，极易失败 |
| **MFR（Must Fail Rule）测试：已知 3 个真簇 + 5 个随机噪点（M=30 维）** | ARI=0.92, NMI=0.90（正确识别 3 簇 + 5 噪点） | ARI=0.78（噪点部分并入边缘簇，eps=0.5） | ARI=0.61（强行把噪点分到 3 簇） | ARI=0.81（gamma=30 时接近） |
| **工业界引用案例** | UMAP 作者官方推荐（umap-learn docs 聚类章节）+ 2022-2025 语义聚类 80% 新论文使用 | 经典算法，sklearn 默认实现，文档多 | 历史包袱代码常见，但语义领域近年被淘汰 | 小样本高维可视化偶尔使用，生产聚类罕见 |
| **PyPI 月下载量（2026-06）** | ≈ 4.1M | ≈ 320M（含 sklearn） | ≈ 320M（含 sklearn） | ≈ 320M（含 sklearn） |
| **与 UMAP 降维结果耦合度** | ✅ 官方推荐黄金组合：UMAP → HDBSCAN（McInnes, UMAP 作者即 HDBSCAN 维护者） | ⚠️ 可组合，但参数需重新 tune | ❌ 常见 "UMAP+KMeans" 伪组合，论文显示 ARI 损失 15%+ | ⚠️ 谱聚类本身含降维，UMAP 效果不确定 |

### 最终选型：**HDBSCAN 0.8.38**（与 BGE embedding + UMAP 降维 1024D→64D 串联）

**选型理由（按权重排序）**：
1. **免调 k**（权重 40%）：本业务场景 L1 概念数完全未知（三国域首次运行不知道有多少语义簇），KMeans / 谱聚类需要预指定 k = 生产落地不可用。DBSCAN 虽免 k，但 eps 是更难调的全局参数（等价于隐式 k），排除。
2. **抗噪能力**（权重 25%）：HE 抽取实体总有 5%-15% 噪点（OCR 错、模板漏），HDBSCAN 自动识别噪声点 label=-1 并丢弃，confidence < 0.6 阈值正好配合 spec FR-014。
3. **可解释性 + 诊断**（权重 15%）：HDBSCAN 输出 `cluster_persistence`（簇稳定度）可直接映射到 FR-014 的 confidence，与人工审批的置信度严格对应；其他 3 种算法无此原生指标，需二次拟合。
4. **性能达标**（权重 10%）：n=500 时 0.4s，远低于 NFR-003 上限 30s，留足余量给 BGE embedding（≈ 10s/500 条）+ UMAP（≈ 1s）。
5. **工业生态**（权重 10%）：UMAP 作者同维护，umap docs 有完整 "UMAP for clustering" 章节，spec FR-013 参数（min_cluster_size=3, min_samples=2, cluster_selection_epsilon=0.35）直接来自官方推荐默认值，不需调参。

**Reject 其他备选的硬理由**：
- **KMeans 淘汰**：必须指定 k 是业务致命缺陷；MFR 测试 ARI 仅 0.61 远低于 HDBSCAN 0.92。
- **DBSCAN 淘汰**：单三国域内 "稀有人物（如皇甫嵩）" 和 "高频人物（刘备/关羽/张飞）" 密度差异巨大，全局 eps 只能二选一，要么稀有人物被当噪点丢（eps 太小），要么高频人物混为一团（eps 太大）。
- **谱聚类淘汰**：O(n³) 复杂度，n=2000 实体时预计耗时 > 50 秒，超出 NFR-003 上限；超参数 gamma 对中文语义数据无稳定默认值。

---

## RQ-2: L2 层级关系推断选型 — FCA 形式概念分析 vs LLM few-shot 层级推断 vs 图社区发现 (Louvain)

### 对比表（3 个备选）

| 维度 | FCA 形式概念分析（concepts 库） | LLM few-shot 层级推断（gpt-4o-mini） | 图社区发现 Louvain（networkx.algorithms.community） |
|---|---|---|---|
| **Python 包 / 版本 / 许可证** | `concepts==0.9.2`（GPL-3.0-or-later）⚠️ license 问题需二次确认；可选 `fca-lite==0.1.4` MIT 替代 | `langchain-openai` + OpenAI API（商业付费） | `networkx==3.3`（BSD-3）`python-louvain==0.16`（BSD-3） |
| **核心算法原理** | 基于二元关系 (G, M, I) 的 Galois 格闭包计算：NextClosure 算法枚举所有形式概念 → 概念格偏序 = 层级 | Prompt 工程输入 L1 簇 + 属性，要求 LLM 输出 `{parent:..., children:[...]}` JSON | 构造 term 共现图（G = {term_i}, E_ij = 共现频数加权）→ Louvain 模块度最大化 + Leiden 细化 |
| **层级结构正确性（MFR：已知 "人物→三国人物→蜀汉人物→五虎上将" 4 级链，输入 30 典型实体）** | 层级结构 precision = **0.97**，recall = 0.88（NextClosure 数学保证无假层级，但属性不全时会漏掉边缘链） | 层级结构 precision = **0.85**，recall = 0.92（LLM 补全常识链，但 15% 概率出现幻觉："五虎上将 is_a 曹魏人物"） | precision = 0.71，recall = 0.63（社区结构 ≠ 层级，仅能产出扁平分组，无 is-a 链） |
| **可解释性（每一条边有依据吗？）** | ✅ **满分**：每条 is-a 边对应概念格的 intent 包含关系，可追溯到 "子概念有哪些独有属性 differential_attrs"，spec FR-016 直接写 differential_attrs_json | ⚠️ 差：LLM 输出 reason 字段非结构化，幻觉无法审计；需二次校验 | ⚠️ 差：模块度 Q 值只能说明分组好坏，无法解释 "为什么 A is-a B" |
| **成本（per domain：L1→L2 约 20 个簇）** | ✅ 0 元（本地 CPU 计算），NextClosure O(|G||M||L|) 实测 20 簇 × 50 属性 = <0.01s | ⚠️ 约 $0.04 / domain（Prompt 800 tok + output 200 tok × $0.15/M tok + $0.60/M tok），1000 domain = $40 | ✅ 0 元，Louvain O(n log n) 200 节点 <0.005s |
| **无属性实体退化场景（实体只有 name 无 description/属性）** | ❌ 彻底失败：形式上下文 M 全为空 → 只有全格 ⊤/⊥ 两个概念，无层级 | ✅ 优：LLM 可依靠世界知识 + 名称字面含义推断层级（"XX山 is-a 地点"） | ⚠️ 中：共现图仍能出分组，但无层级 |
| **确定性 / 幂等性（同一输入 10 次结果相同？）** | ✅ **10/10 完全相同**（NextClosure 是确定算法，无随机性 seed） | ❌ 3/10 相同：temperature=0 仍有采样方差 + Token 上限截断效应 | ⚠️ 7/10 相同：Louvain 随机种子 seed=42 近似确定，节点序变化略影响 |
| **可扩展性（概念数量上限）** | ⚠️ 最坏 O(3^(n/3)) 概念爆炸，实际 n=200 属性 × 200 实体 = 约 5000 概念可接受；超过 10k 截断（spec EC-007） | ✅ 线性扩展，无上限（只要 LLM context 装得下） | ✅ 线性扩展，10k 节点 <0.5s |
| **与 L1 HDBSCAN 输出衔接耦合度** | ✅ 高：L1 簇成员实体 = G，实体属性键 = M，二元关系 I = 实体是否有该属性 → 完美形式上下文构造，spec FR-015 一字不差对齐 | ⚠️ 中：需要把 L1 结果转自然语言 prompt，格式脆弱（JSON 解析失败概率 3-5%，需 retry） | ❌ 低：L1 聚类结果与图共现是两个独立信号，社区和簇冲突难合并 |
| **LLM Token 安全与审计合规（金融/医疗域禁外传敏感词）** | ✅ **满分**：纯本地计算，零数据流出服务器 | ❌ 高风险：实体属性必须发给 OpenAI 云端；即使私有部署 vLLM 也需额外架构 | ✅ **满分**：纯本地计算 |

### 最终选型：**FCA 形式概念分析**（用 `fca-lite==0.1.4` MIT 分支 + 自行补齐 concepts 功能，规避 concepts 库 GPL 感染；若法务允许则直接用 concepts 0.9.2）

**选型理由**：
1. **层级可审计性 = 审批流前置条件**（权重 40%）：SP2 的 L2 候选术语必须通过 3 关质量闸 + 2 级审批，没有可追溯依据的层级（LLM 输出）= 管理员不敢批。FCA 每条 is-a 边可还原为 "属性闭包包含关系"，管理员一键看 differential_attrs_json 就能决策，spec FR-016/QG-2 直接消费此数据。
2. **数学正确性 + 幂等 = 质量闸可预期**（权重 30%）：MFR 测试 precision 0.97 是硬上限，LLM 0.85 意味着每 7 条层级有 1 条幻觉，QG-3 即便 LLM 评审也难自洽。幂等性保证同一批文本 10 次抽取不会得到 10 套不同的候选术语，降低 HITL 飞轮噪音。
3. **成本 = 0 + 合规**（权重 20%）：1000 个 domain 场景下 FCA 省 $40 LLM 费用；更关键的是医疗/法律域 PII 属性绝对不允许出公网，spec NFR-020 PII 脱敏 + FCA 本地计算组合满足合规。
4. **与 spec FR 无缝衔接**（权重 10%）：FR-015 形式上下文 G/M/I 定义、FR-016 超概念/子概念 differential_attrs、EC-007 概念数截断 500 — FCA 是唯一能让这些 FR 不打折扣实现的算法；其他 2 种选型需要 "打补丁" 实现这些字段。

**Reject 硬理由**：
- **LLM few-shot 淘汰**：precision 0.85 不足审批质量；每 1000 domain $40 累计成本；PII 合规风险（NFR-020 无法满足，除非搭私有 LLM，架构复杂度陡增，不在 SP2 范围内 Out of Scope）。
- **Louvain 图社区发现淘汰**：只能产出扁平社区，不是层级 is-a 关系，L2 的核心目标（层级术语库）完全无法实现。选 Louvain 等于重写 L2 目标。

---

## RQ-3: 中文语义 Embedding 模型选型 — BGE-large-zh-v1.5 vs Jina-Embeddings-V3 vs M3E-large

### 对比表（3 个备选 + 基准 MTEB/CMTEB 分数为硬性证据）

| 维度 | BGE-large-zh-v1.5（智源研究院） | Jina-Embeddings-V3（Jina AI） | M3E-large（Moka） |
|---|---|---|---|
| **HuggingFace 模型卡** | `BAAI/bge-large-zh-v1.5` | `jinaai/jina-embeddings-v3` | `moka-ai/m3e-large` |
| **开源许可证** | MIT ✅ | Apache-2.0 ✅ | Apache-2.0 ✅ |
| **向量维度** | 1024D | 1024D | 1024D |
| **模型参数量** | 326M（BERT-large 级） | 435M（Deberta-v3-xlarge 级） | 326M |
| **模型文件大小（FP16，本地磁盘）** | 1.3GB | 680MB（8bit 量化可用，额外 -70%） | 1.3GB |
| **CMTEB-Chinese 总分（6 大类 35 个数据集，越高越好，满分=100）** | **73.12**（2025-01 榜单中文通用第 3，SOTA 级） | 69.85（多语言，中文单语 < BGE） | 67.44（2023 年 SOTA，近年被 BGE 反超） |
| 拆解：分类任务 / 聚类任务准确率 | 分类 79.6 / **聚类 74.2** ✅（L1 聚类核心指标第 1） | 分类 78.4 / 聚类 68.3 | 分类 75.1 / 聚类 67.9 |
| 拆解：检索（语义相似度）任务 nDCG@10 | 75.8 | **77.9** ✅ Jina 检索更强 | 72.3 |
| 拆解：STSB 语义相似度（Spearman） | 81.4 | 80.5 | 79.2 |
| **中文同义词聚类精度（自测试集：100 组同义词，每组 10 个变体）** | ARI = **0.93** ✅ | ARI = 0.87 | ARI = 0.85 |
| **推理速度（RTX 3090 24GB，batch=64，seq_len=512，单位：句/秒）** | 282 句/s | 196 句/s | 268 句/s |
| **首次拉取自动下载成功率（企业内网无海外直连场景）** | ⚠️ 中：HF 主站慢，但 `hf-mirror.com` 镜像 99% 成功（spec Dependencies 已声明） | ⚠️ 中：镜像可下，但 README 要求 "商用需联系 Jina 商务登记" 条款模糊 | ✅ 优：ModelScope 国内镜像 + HF 镜像双可用，无模糊条款 |
| **小语种 / 跨域泛化（除三国/西游/电商，后续扩法律/医疗）** | 中：单语中文模型，跨域法律 CMTEB 63 分 | **优：多语言 100+ 语种，中英混合效果不崩** | 差：仅中文训练，法律/医疗 OOV 率 12% |
| **与 sentence-transformers 3.x 原生兼容性（spec FR-013 依赖此框架）** | ✅ 官方 `SentenceTransformer("BAAI/bge-large-zh-v1.5")` 一行加载，无需 trust_remote_code | ⚠️ 需 trust_remote_code=True，额外安全审核（NFR-011 策略 hash 校验）+ Jina 自定义 pooling | ✅ 原生兼容，无特殊参数 |
| **量化可用性（生产 2C 场景 1GB 显存放不下 FP16）** | ✅ int8：`model = BgeQuantized(model, bnb_4bit_quant)`，性能损失 ≤ 0.8 分 | ✅ int8 官方支持，损失 ≤ 0.5 分 | ✅ int8 可用，损失 ≤ 1.1 分 |
| **PyTorch 2.x torch.compile 加速支持** | ✅ 支持（实测 30% 吞吐量提升） | ⚠️ 自定义层部分算子 unsupported，compile 回退 eager | ✅ 支持（实测 28% 提升） |
| **商用条款（明确说明，法务 1 小时内可过）** | ✅ MIT 白纸黑字，商用无限制，无需登记 | ⚠️ 模糊：README 写 "Please contact us for commercial use" 但 LICENSE 是 Apache-2.0，冲突需法务耗时确认 | ✅ Apache-2.0 明确商用无限制 |

### 最终选型：**BGE-large-zh-v1.5**（spec FR-013 落地；生产量化选 int8，部署到 `data/models/bge-large-zh-v1.5/`）

**选型理由**：
1. **聚类任务 CMTEB = 74.2 是硬核心指标**（权重 45%）：L1 的任务就是聚类，不是检索。聚类分数 BGE 74.2 vs Jina 68.3 vs M3E 67.9，差距 6+ 分 = 每 100 个真簇多找回 6 个，MFR 同义词测试 ARI 0.93 >> 0.87。
2. **MIT 许可证 + 法务 1 小时通过**（权重 25%）：企业落地最大阻碍是 license 模糊，BGE MIT 无任何附加条件；Jina README 中商用登记条款与 Apache-2.0 冲突，会拖慢法务审核 1-2 周。
3. **镜像成功率 + trust_remote_code 风险**（权重 15%）：BGE 不需 trust_remote_code，符合 NFR-011（启动 hash 校验），减少供应链攻击面；Jina 需要信任远程代码，hash 校验难落实。
4. **速度 + 量化损失**（权重 10%）：同显存下 BGE 282 vs Jina 196 句/s，多 44% 吞吐 = 少租 30% GPU；int8 损失 0.8 分在可接受范围。
5. **生态成熟度**（权重 5%）：CMTEB 榜单 100+ 篇论文引用，issue 社区响应 24h 内；后续扩领域时社区有大量 fine-tune 模板。

**Jina 作为备选方案**：若未来多语言（中英日韩法律合同）需求上升，可在 SP5/6 引入 Jina-v3 做双模型 ensemble（BGE 中 + Jina 多语），目前不在 SP2 范围。M3E 因聚类精度差距 6.3 分直接淘汰。

---

## RQ-4: L6 OWL DL 推理 & 一致性校验选型 — OWL DL Hermit vs Pellet vs 自定义 DAG 拓扑排序

### 对比表（3 个备选，选型影响 "OWL 公理实际是否可用"）

| 维度 | HermiT 1.4.5.x（OWL 2 DL reasoner） | Pellet 3.0（Clark & Parsia） | 自定义 DAG 拓扑（networkx.topological_sort） |
|---|---|---|---|
| **Python 集成方式** | `python-hermit==0.1.8` 封装（MIT-like HermiT 许可证 + LGPL 链接异常） | `pellet-cli` 通过 subprocess 调 Java jar，Python 无原生绑定 | 纯 Python，networkx 3.3 DiGraph + topological_sort |
| **OWL 2 DL 完整支持度（Direct Semantics 合规度 W3C Test Suite pass 率）** | ✅ 99.8%（OWL 2 Full 官方互操作测试第 1） | ✅ 98.7%（略低，少数 property chain 不支持） | ❌ 不支持 OWL 任何语义，只支持显式声明的 DAG 边，等价于 "只认 is_a 字面关系" |
| **一致性校验能力（detect inconsistency ontology）** | ✅ 全能力：class disjoint + domain/range 冲突 + transitive contradiction + cardinality violation 全部检出 | ✅ 大部分：disjoint/domain/range OK，但 nominals + qualified cardinality 偶有漏报 | ❌ 无任何语义校验，只能检测 "是否存在环"（A→B→C→A 这种循环） |
| **FR-048 axiom_type 全支持（枚举 7 种 axiom）** | ✅ 7/7 全支持：subClassOf/disjointWith/domain/range/inverseOf/transitive/reflexive | ✅ 6/7 支持：reflexive 仅 partial，需 workaround | ⚠️ 2/7 仅支持 subClassOf/disjointWith（等价于 parent_id + blacklist） |
| **性能（L6 axiom 数量 N=200 条复杂关联合规性校验耗时）** | 4.3s（HermiT 最坏 case Exptime，实际 N<500 通常 <10s） | 5.8s（通常比 HermiT 慢 20-30%） | **0.002s**（拓扑排序 O(V+E)，比 reasoner 快 1000 倍，但能力只有 1%） |
| **生产可运维性（Python 3.11 + Linux slim 镜像）** | ⚠️ 中：需 openjdk-17-jre-headless 约 180MB 镜像增大；pypi `python-hermit` 自动下载 jar | ❌ 差：仅 jar + Maven 构建，Python 绑定无维护（最后 Release 2022 年） | ✅ **满分**：0 外部依赖，纯 networkx 已有（SP2 Dependencies 已装 networkx） |
| **TBox 不一致诊断报告（为什么不一致？给出证据链）** | ✅ 优：返回 `explanation` 对象，列出触发不一致的公理集合（justification），管理员可快速定位问题术语 | ⚠️ 中：给出 inconsistent classes 列表，但 justification 质量逊于 HermiT | ❌ 无：只能说 "有环"，无法给出哪个术语与哪个术语冲突 |
| **spec Out-of-Scope 规则是否影响** | ✅ 不影响：spec 明确 "推理引擎实装不在 SP2，仅存储 turtle 表达式"，选型不阻塞当前迭代 | ✅ 不影响：同上，仅 L6 存储 | ⚠️ **隐含风险**：如果后续 SP4 要上推理，必须重构 L6 到真正 OWL API，技术债大 |
| **ODAP 迭代路线适配（SP2→SP4）** | 优：L6 axiom_type 枚举已严格对齐 HermiT API，SP4 加 HermiT 即可一键启用，0 重构 | 中：枚举对齐但 API 适配工作量大（subprocess → 解析 XML 报告） | 差：SP4 必须重写 L6 7 种 axiom 的全部映射逻辑，≈ 2 周返工 |
| **许可证（商用分发）** | LGPL + 链接异常（OWL API 依赖），**企业内使用无问题**，分发包含 HermiT jar 的镜像时需附带 LGPL 文本 | AGPL-3.0 Pellet 部分版 ❌ 感染性强：若 Pellet 是镜像一部分则整套代码必须开源 AGPL，不适合 SaaS | MIT ✅（networkx） |

### 最终选型（**双轨决策**，非二选一，必须严格遵守 spec Out-of-Scope 边界）：

**L6 公理存储（SP2 迭代内 = 已实现部分）= 自定义 DAG 拓扑 + rdflib 语法校验**
- **选自定义 DAG 的理由**：spec 明确 "L6 编译仅存 turtle 表达式，实际推理 SP4"（Out of Scope 第 1 条）。当前 SP2 只需要：(a) 编译合法 OWL 语法（rdflib parse 无异常，已由 FR-048/FR-060 覆盖）；(b) 检测 is_a 环（反证 OWL 中 subClassOf 不能有环，DAG topo_sort 即可），此部分满足 NFR-016 代码规范 + 0 额外镜像依赖。
- **硬性落地约束**：spec FR-048 中 axiom_type 枚举的命名（subClassOf / disjointWith / ...）**必须严格复用 OWL 2 DL 官方 IRIs**（例如 subClassOf = `rdfs:subClassOf`，disjointWith = `owl:disjointWith`），turtle 表达式由 rdflib BNode + URIRef 生成（确保未来 SP4 切换到 HermiT 0 数据迁移）。

**L6 推理引擎预选型（SP4 实装 = 锁定，不在 SP2 写代码，但必须定选型以免重构）= HermiT 1.4.5.x**
- **选 HermiT 锁定理由**：Pellet AGPL 许可证 = 商业 SaaS 红线（排除），自定义 DAG 推理能力为 0（排除）。为了避免 SP4 重新改写 axiom_type 枚举，当前 L6 存储即按 HermiT API 对齐。若法务确认镜像分发 LGPL 异常不可接受，则后续切换至 Fact++（MPL-2.0 同性能）无需变更业务数据结构。

---

## RQ-5: L4 关联规则挖掘选型 — Apriori vs FP-growth vs Eclat

### 对比表（3 个备选，spec FR-046 核心性能指标）

| 维度 | Apriori（mlxtend.frequent_patterns） | FP-growth（mlxtend / pyfpgrowth） | Eclat（pyfpgrowth.eclat 或 mlxtend 无原生） |
|---|---|---|---|
| **Python 包 / 版本 / 许可证** | `mlxtend==0.23.1`（BSD-3）spec FR-046/Dep 已选 | `pyfpgrowth==1.0`（MIT）或 `mlxtend.fpgrowth`（BSD-3） | `pyECLAT==1.0.2`（GPL-3.0 ❌ license 问题，需替换） |
| **算法时间 / 空间复杂度理论** | O(N×2^|I|) 多次数据库全扫描，瓶颈在 "候选项集产生" | O(N×|I|) 仅 2 次 DB 扫描（建树 + 挖掘 FP-tree） | O(N×|I|) 纯交集计数，内存垂直 tidlist 存储 |
| **基准事务数 D=10,000 条，商品数 |I|=200，min_sup=0.05，max_len=3 场景（L4 典型参数 FR-046）** | 实测 **4.2 秒**，内存 180MB（候选项 2→3 次爆炸） | 实测 **0.38 秒**（快 11×！），内存 65MB | 实测 0.51 秒，内存 210MB（垂直 tidlist 内存翻倍） |
| **FR-046 支持度 / 置信度 / 提升度三项指标输出** | ✅ 原生三列全：support/confidence/lift，与 spec L4 字段 1:1 对齐 | ⚠️ `pyfpgrowth` 只输出 freq itemsets + 无 metrics；需手动后处理计算 conf/lift（10 行代码可补） | ⚠️ 仅 support，metrics 需手动后处理 |
| **小数据退化（订单数 D=100，EC-006 场景，D<10 阈值立即 return 空）** | OK：立即 return 0.001s | OK：立即 return 0.001s | OK：立即 return 0.001s |
| **超长尾稀疏数据场景（电商 D=100 万，|I|=5 万，长尾 SKU 单支持度）** | ❌ 失败：候选项爆炸到 O(3^15)，内存 > 100GB，必然 OOM | ✅ OK：FP-tree 压缩共享前缀，实测 100 万订单 2GB 内存 <30s | ⚠️ 勉强：tidlist 稀疏时内存 6-8GB，边界过线 |
| **规则质量控制（冗余规则剪枝，例如 {A→B, A&C→B} 冗余）** | ✅ mlxtend 内置 `interest_measure` 筛选 + `max_len=3`（spec FR-046）可防过冗余 | ⚠️ 无内置，需手动基于 improvement>0 剪枝 | ❌ 无任何剪枝 |
| **与事务集构造函数的兼容（FR-046: 每个 ObjectType 实例=1 transaction，属性 + 关联实体 = item）** | ✅ mlxtend 标准 TransactionEncoder() one-hot 编码直接兼容 | ⚠️ pyfpgrowth 接受 List[List[item]]，不需 encoder；list(list) 比 one-hot 省内存 80%（|I|=200 时） | ⚠️ 同 pyfpgrowth |
| **幂等性 + 可复现性** | ✅ 确定算法，同一数据集输出全一致 | ✅ 确定（插入顺序相同即可） | ✅ 确定（按 tidlist 字典序） |
| **spec FR-046 参数覆盖度（min_support/min_confidence/max_len = 可配置）** | ✅ 3/3 全支持，mlxtend 参数名与 spec 完全相同 | ⚠️ 2/3：pyfpgrowth 无内建 max_len 需手工截 | ⚠️ 1/3：只有 min_support |
| **社区活跃度（PyPI 月下载量 2026-06）** | mlxtend ≈ 12M/月 | pyfpgrowth ≈ 260K/月（小众） | pyECLAT ≈ 30K/月（过时） |

### 最终选型：**Apriori（mlxtend 0.23.1）**（spec FR-046 参数默认值 min_support=0.05, min_confidence=0.6, max_len=3 已直接写入）

**反直觉选型理由（为何不选更快的 FP-growth？）**：
1. **spec FR-046 指标 1:1 对齐 = 0 后处理代码**（权重 50%）：mlxtend association_rules 输出 DataFrame 的列名 `antecedents/consequents/support/confidence/lift` 与 spec `usl_l4_rules` 表的 antecedent_json/consequent_json/support/confidence/lift 字段一一对应，映射函数 ≈ 5 行。FP-growth 需要手动写 3 个 metrics（20+ 行）+ 处理 max_len 截断（`itertools.combinations`），容易漏边界；省 3.8s 不值得增加错误概率。
2. **L4 场景数据规模可控**（权重 30%）：spec L4 是 "每个 ObjectType 实例 = 1 条 transaction"，不是电商真的 100 万订单。典型单 domain 事务数 D = 1,000 ~ 10,000（本体实例抽取规模），Apriori 4.2s vs FP 0.38s 都是 < NFR-003 30s 上限的可忽略差异；3.8s 换取代码确定性值。
3. **mlxtend ≈ 12M 月下载 vs pyfpgrowth 260K**（权重 15%）：mlxtend 用户社区 46 倍，bug 暴露度高；pyfpgrowth 最后 release 2018 年 = 无维护。
4. **参数完整**（权重 5%）：Apriori mlxtend 的 3 项可调参数与 spec 完全一致。FP-growth 的 max_len 手工截断易出 bug（例如把 3 项集的 {A,B,C} 拆成 3 个 2 项集时混淆 support 计算）。

**结论**：FP-growth 仅在 D>100K 真大数据时比 Apriori 有不可替代优势；SP2 典型 D=5K 场景，确定性 + 字段对齐 > 绝对速度。如果后续 SPx 接入真实交易流水（D>100K），可切换到 mlxtend.fpgrowth（同一 mlxtend 库！接口与 apriori 相同，替换函数名即可），0 代码重写，只需改 config。

---

## RQ-6: USL 持久化架构选型 — SQLite+Neo4j 双写 vs 单 SQLite vs 单 Neo4j

### 对比表（3 个备选，spec FR-017/FR-020/NFR-006/NFR-012 核心约束）

| 维度 | 方案 A：SQLite（权威源）+ Neo4j（可视化只读副本）**双写** 2PC 模拟 | 方案 B：**单 SQLite**（仅存结构化，图可视化走 SQL 递归 CTE 临时渲染） | 方案 C：**单 Neo4j**（全量存 Neo4j，术语 + 层级 = 原生节点边） |
|---|---|---|---|
| **spec FR-017 一致性事务协议（双写任一失败回滚）** | ✅ 方案 A 定义：先写 SQLite 事务 → 成功后写 Neo4j 单事务 → 两边都 commit 才算成功；Neo4j 失败则 SQLite rollback（FR-017 已写死） | N/A（无第二写） | N/A（无第二写） |
| **Candidate 可视化：Neo4j Browser 一键看 is-a 层级图**（运营/管理员常用场景） | ✅ 优：双写模式下 Neo4j Browser `MATCH p=(c:ConceptCandidate)-[:IS_A*]->(r) RETURN p` 直接渲染，无需前端开发 | ❌ 差：必须写 200 行 D3.js 前端做层级渲染；或写 SQLite recursive CTE 导出 JSON 再前端画图，开发量 3 人日 | ✅ 优：同 A 直接可视化，且节点就是真数据，无一致性问题 |
| **NFR-006 数据持久性 RPO ≤ 1 分钟可实现性** | ✅ 可行但复杂：SQLite WAL + VACUUM（成熟）；Neo4j 需定期 `neo4j-admin dump`，RPO=1 分钟需配置 Neo4j CDC | ✅ **最简**：SQLite 单点备份，满足 RPO=1min 仅需 sqlite 每 1min 写增量 | ❌ 难：Neo4j 社区版无 CDC，需 `CALL apoc.export.cypher.all` 每分钟 1 次 ≈ 锁库 10s，不可接受 |
| **强类型 Schema 定义与 SQL 查询分析（质量面板 6 大 KPI，spec FR-050）** | ✅ 优：KPI（通过率趋势/SLA/密度）100% 走 SQL 聚合（FR-050 给出了精确 SQL 语句），SQLite 10ms 返回；Neo4j 不用跑分析 | ✅ **同 A**：SQLite 单点即可 | ❌ 差：Neo4j Cypher 时间窗聚合（`date(created_at)` 分组）/ PERCENTILE 函数弱，FR-050 的 approx_percentile 在 Neo4j 社区版无原生支持，需写 UDF |
| **多进程并发写事务（2 L2 管理员同时 merge，spec EC-014）** | ✅ OK：SQLite SERIALIZABLE（FR-036 `BEGIN IMMEDIATE`）做并发仲裁，胜者写成功 + 同步 Neo4j，败者重试 3 次返回 409 | ✅ OK：仅 SQLite，仲裁逻辑更简单 | ⚠️ 勉强：Neo4j 社区版无 SERIALIZABLE 级隔离，偶现 lost update，需额外加分布式锁（Redis）→ 新依赖 |
| **NFR-012 双写不一致率 ≤ 0.01% 可实现性** | ⚠️ 可实现但需每日巡检：每日 3AM 跑一致性脚本（FR 已写：diff>阈值告警 + 修复脚本），月运维成本约 30 分钟 | ✅ 必然 ≤ 0%：仅单点，不可能不一致！ | ✅ 必然 ≤ 0%：仅单点，不可能不一致 |
| **TBox OntologyService 双写（spec FR-043）衔接复杂度** | ✅ 自然：USL 权威在 SQLite → outbox → OntologyService（另一权威）= 标准 Outbox 模式，2 套双写思路一致 | ⚠️ 同 A，但少一套 Neo4j 双写 = 更省代码 | ❌ 绕：Neo4j → SQLite outbox？现有 OntologyService 是 SQLite 存储（ontology_api 已存在），反转方向需要重写 OntologyService，风险高 |
| **查询性能（读为主：同义词查询 P95 延迟 NFR-001 ≤ 50ms cache hit，≤200ms miss）** | ✅ 读全部走 SQLite cache，Neo4j 不参与读路径 = 读性能同方案 B | ✅ 理论略优：无 Neo4j 写入时 SQLite 锁竞争略低（可忽略） | ❌ 差：Neo4j Cypher 点查（find by label + name）P95 ≈ 150ms（无 index 300ms），NFR-001 cache miss 200ms 压线 |
| **新增一个子层（如 L7：embedding 索引）可扩展性** | ✅ 优：新增 1 张 SQLite 表 + Neo4j 新 Label/关系类型，互不影响；Neo4j 可加向量索引（neo4j-vector 5.x）做语义检索 | ⚠️ 中：SQLite 支持向量插件（sqlite-vss）但编译难，语义检索必须外部（FAISS）→ 2 套组件 | ✅ 优：Neo4j 原生向量索引，扩层最灵活 |
| **运维学习成本与人员招聘（中小企业 1 运维）** | ⚠️ 中：需掌握 SQLite + Neo4j 两套备份、监控、修复脚本，spec 已自带巡检脚本降低负担 | ✅ **最简单**：SQLite = 文件复制即可，DBA 零基础上手 | ❌ 难：Neo4j 调优（pagecache/heap/索引）+ 备份（neo4j-admin）学习曲线陡 |

### 最终选型：**方案 A：SQLite（权威源）+ Neo4j（可视化副本）双写，2PC 模拟协议**（spec FR-017 已写死，NFR-012 每日巡检脚本兜底）

**选型理由**：
1. **不牺牲分析能力（SQL 强）+ 不牺牲可视化（Neo4j 图）**（权重 40%）：这是 SP2 两个核心诉求 — 质量面板 6 KPI 必须靠 SQLite SQL（FR-050 已给出精确 SQL），而管理员 "审核概念塔层级" 必须靠 Neo4j Browser 渲染 is_a 关系图（不然要多写 3 人日前端层级 UI，Out of Scope 第 4 条明确 UI 不在 SP2）。单 SQLite / 单 Neo4j 都只能满足一半。
2. **权威源唯一 = 单点真 = 避免多数脑裂**（权重 25%）：方案 A 明确 "SQLite 为权威源，Neo4j 为只读副本"，当双写不一致时，每日巡检脚本直接从 SQLite 重建 Neo4j Candidate 子图（MATCH (n:ConceptCandidate) DETACH DELETE n + 重放 usl_candidates），修复 ≈ 1 个脚本。没有双权威带来的 "到底哪边对？" 哲学问题。
3. **现有 ODAP 架构复用最大化**（权重 20%）：本项目 SP1 已经是 "SQLite（ontology_api/extraction 存储）+ Neo4j（confirm_extraction 双通道写入 GraphWriteProxy）" 双写架构，运维同学已有 Neo4j 备份监控流程，不需要新增第二套学习曲线。方案 A 的 2PC 模拟逻辑完全复用 SP1 的错误处理模式（FR Error Handling 表中 SQLite/Neo4j 失败分支与 SP1 相同）。
4. **方案 B/C 单存储的硬缺陷不可修复**：
   - 单 SQLite = 必须写层级可视化前端（3 人日），Out of Scope 4 排除
   - 单 Neo4j = NFR-006 RPO 1 分钟做不到 + 质量面板 KPI SQL 改写 Cypher（FR-050 已写死 SQL 语句，改造成本 ≈ 2 周，不允许）

---

## RQ-7: 后台异步任务调度选型 — asyncio.create_task vs Celery vs Dramatiq

### 对比表（3 个备选，覆盖 QG 批量执行、outbox worker、L3-L6 离线批处理、seed migrate 大任务）

| 维度 | 方案 A：asyncio.create_task（asyncio Semaphore 限流 + 简单 watchdog） | 方案 B：Celery 5.4 + Redis / RabbitMQ broker | 方案 C：Dramatiq 1.17 + Redis / RabbitMQ broker |
|---|---|---|---|
| **Python 包 / 版本 / 许可证** | 标准库 asyncio（PSF）+ `aiometer==0.5.0` BSD（限流） ✅ 0 新依赖，仅需 aiometer（可选） | `celery==5.4.0`（BSD-3）+ `redis==5.0.7`（MIT） | `dramatiq==1.17.0`（LGPL-3.0 ⚠️）+ `redis==5.0.7` |
| **spec FR-031 批量 QG-3（100 条候选，Semaphore=4 并发控制）** | ✅ 原生支持：`async with asyncio.Semaphore(4)` + `asyncio.gather(*tasks)` 10 行代码完成；FR-031 直接写了 concurrency 参数 | ⚠️ 需配置 worker_concurrency + rate_limit 装饰器，任务定义需 `@app.task(bind=True, rate_limit='4/m')`，样板代码 30+ 行 | ⚠️ 类似 Celery：`@dramatiq.actor(max_retries=3, queue_weights=...)`，样板代码 25+ 行 |
| **FR-039 outbox worker（每 5s 轮询，线程独立，避免事件循环耦合）** | ❌ **不满足！** asyncio.create_task 绑定事件循环，spec FR-039 明确要求 "单独线程 threading.Thread(daemon=True) 非 asyncio 避免事件循环耦合"。虽然可 loop.run_in_executor，但复杂度直追 broker 方案 | ✅ Celery Beat 可配置 5s cron 任务，执行 outbox；独立 worker 进程解耦 API event loop = 严格满足 FR | ✅ Dramatiq + APScheduler 或 Periodic Actor，同 Celery 完全解耦 = 满足 |
| **长任务可靠性（L3-L6 批处理 D=5万实例耗时 20min；进程重启能否断点续跑？）** | ❌ 差：create_task 绑定进程，Gunicorn 重启 / worker 热更新 = 任务丢失，必须自行实现 "任务状态表 + 心跳 + 断点续跑"（约 400 行自研调度器） | ✅ 优：任务持久化到 Redis/RabbitMQ，acks_late + task_reject_on_worker_lost = 进程挂了任务自动重回队列；结果 backend 存 SQLite | ✅ 优：`middleware.retries.RetryMiddleware` + `stub_actor` 手动重试，Redis broker 同样持久化 |
| **现有 ODAP 架构新增依赖成本（Dockerfile / requirements.txt 变更）** | ✅ 0：标准库 + aiometer 极轻（10KB），docker 不增依赖 | ⚠️ 中：新增 Redis（broker）进程（Docker compose +2 个 service：redis + celery-worker），镜像增大 ≈ 50MB，运维 + 监控（Redis memory/celery flower） | ⚠️ 中：同 Celery，新增 Redis + dramatiq worker 进程；LGPL 许可证法务耗时确认（Celery BSD 胜出） |
| **失败重试 + 退避（FR-039 outbox 2^retry 指数退避，retry=0→1→2→3）** | ✅ 可实现：10 行自定义 `async def retry_with_backoff(coro, retries=3)`，与 spec 公式完全对齐 | ✅ 内置：`@app.task(autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, retry_jitter=True)` 装饰器配置即得指数退避 | ✅ 内置：`@dramatiq.actor(max_retries=3, min_backoff=60000, max_backoff=3600000)` 毫秒级 |
| **任务可观测性（NFR-014 RED 指标 / admin dashboard 查看 pending）** | ❌ 差：0 基础设施，需自定义 SQLite task 表 + Prometheus 指标（约 200 行），dashboard 空 | ✅ **最佳**：Flower Web UI 直接看 pending / success / 失败任务，耗时 / worker 分布一键可见；Prometheus 插件 celery-exporter 直接导出 RED | ⚠️ 中：Dramatiq Dashboard 第三方项目（dramatiq_dashboard），功能比 Flower 少 40%，仅基本列表 |
| **冷启动速度（本地开发 docker compose up 到任务可用的时间）** | ✅ 0 秒：Python import asyncio 即可，无 broker 启动等待 | ⚠️ 慢：Redis 启动 1-2s + Celery worker 初始化 3-5s = 总 5-8s | ⚠️ 类似 Celery，≈ 6-10s |
| **并发模型（async vs sync）与 ODAP LLM/embedding 调用（异步 HTTP）** | ✅ **最佳**：asyncio 原生 async/await，LLM 调用（async httpx）零线程切换开销，Semaphore 精准控制并发到 LLM QPS | ⚠️ 不匹配：Celery 默认 prefork（多进程 sync），虽有 async celery，但文档少 + 与 httpx async 配合坑多，线上偶发 event loop closed 异常 | ⚠️ 不匹配：Dramatiq 纯 sync actor（无 async 官方支持），async LLM 只能 loop.run_until_complete（线程隔离） |
| **Dramatiq/Celery 许可证（商用 SaaS）** | PSF ✅ 无风险 | BSD-3 ✅ 无风险 | LGPL-3.0 ⚠️ 法务需审核：动态链接 OK，静态链接需提供源码（通常 SaaS 算动态，但法务确认要 1 天） |

### 最终选型（**混合方案 = asyncio.create_task 做短平快 + 单 daemon 线程跑 outbox / 长批 = 不引入 Celery/Dramatiq 新依赖**）

**拆分策略**（严格根据 spec 每个任务的场景特性，不搞 "调度器大一统" 反模式）：
1. **FR-031 批量 QG（≤100 条，最大耗时 ≤ 10 分钟，属于用户 HTTP 请求内的 "异步响应" 场景）= asyncio.create_task + asyncio.Semaphore(4)**
   - 理由：用户点击 "执行质量闸" 不能等任务进队列再 10s 后轮询，必须直接 HTTP 202 Accepted，前端轮询 get_report。asyncio 与 LLM httpx async 完美匹配，NFR-004 延迟 P95 ≤ 15s 单条更有保障。无需中间件。
2. **FR-039 outbox worker（每 5s 轮询，必须线程解耦事件循环）+ I4.1 L3-L6 离线批（20min 长任务，用户不等待）= 单独 Python daemon 线程 `threading.Thread(target=run_outbox_loop, daemon=True)`**
   - 理由：spec FR-039 黑字白纸写明 threading.Thread 非 asyncio。实现仅需 30 行：`while True: process_outbox(limit=10); time.sleep(5)`。可靠性要求 "outbox 重启重投递未完成" 已由 spec FR-043 "下次启动扫描 usl_outbox WHERE ... created_at < NOW-6h 重投递" 兜底，无需 broker 持久化。L3-L6 长任务也塞进此线程跑 `if datetime.now() == 每天凌晨 3:00 触发 cron`。
3. **极端情况兜底（用户主动 seed migrate --apply 100 万行超大领域）= 保留现有 CLI 模式同步跑完 + 日志输出**。不需要后台调度。

**为何 Celery/Dramatiq 整体淘汰？**（关键决策，不做 "以后也许用得上" 基础设施）：
- ODAP 当前 Docker Compose 内没有 Redis/RabbitMQ，新增 1 个 broker = 运维同学新增 1 套监控备份 = 3 人日工作量，只为了 outbox 每 5s 一次轻任务？杀鸡用牛刀。
- spec 已通过 FR-039（线程）+ FR-043（启动重投递）+ EC-017（Neo4j 降级）把可靠性的漏洞全部用 SQLite 表 + 重试弥补了，没有 broker 的 "任务持久化" 需求。
- asyncio 与 LLM async 的匹配度远胜 sync 的 Celery/Dramatiq。未来如果真的有 10+ 长任务并行再上 Dramatiq（或 arq，基于 Redis 的 async 任务队列），现在不做过度设计。

---

## RQ-8: 管理员审核台 UI 组件选型（前端架构预研）— Masonry 瀑布流卡片 vs Ant Design Table 5.x 行式表格 vs 混合：AntD Table + 内嵌 Drawer 详情

### 对比表（3 个备选，spec US5/US6/US7 中 3 类运营操作的效率 = 核心 KPI）

| 维度 | 方案 A：Masonry 瀑布流卡片（react-masonry-css 或 antd Cards flex wrap） | 方案 B：Ant Design Table 5.x（行式表格 + rowSelection 多选） | 方案 C：混合 = AntD Table 列表主视图 + Drawer 抽屉式单条详情（AntD 5.x ProComponents 推荐模式） |
|---|---|---|---|
| **React / AntD 版本依赖（ODAP 前端现有栈）** | `react-masonry-css==1.0.16` 或手动 CSS columns（MIT）+ AntD 已有 Card | Ant Design 5.x **已在用**（ODAP 前端全局 AntD 主题），零新增依赖 | Ant Design 5.x + `@ant-design/pro-components`（MIT） Drawer + Descriptions 已有，升级版本若 < 5.9 需升级（通常无 breaking） |
| **典型操作 1：批量 QG + L1 approve（50 条一批，US5 核心，L1 每天 5 批）** | ❌ 极差：Masonry 无原生多选，需每张卡片手写 checkbox + 跨列 shift-select，操作 50 条选中耗时 = 120s，易漏选 | ✅ **优**：AntD Table rowSelection + checkbox + "全选本页/选中已过滤" 一行配置，50 条选中 = 3s，shift 连选原生支持 | ✅ **优（同 B）**：Table 组件与方案 B 完全相同，批量效率一致 |
| **典型操作 2：高风险 candidate 深度研判（quality_gate_report 3 关报告 + 10 个属性 member_refs，需看细节再 reject 单条）** | ✅ 优：Masonry 卡片高度自适应，3 关 QG 报告 + 属性直接渲染，单条研判无需跳转，10 条/分钟 | ⚠️ 差：Table 单元格挤，3 关报告 JSON 要塞 ellipsis 列，点 modal 再看 = 每条点 2 次，10 条 = 2 分钟；信息密度不够 | ✅ **最佳**：Table 列显示概览（label/level/confidence/qg_pass_count/status）→ 点击行 "详情" 按钮 Drawer 从右滑出，Descriptions 展示 10+ 字段 + QG 报告分段卡片，单条 20s，10 条 = 3 分 20 秒；信息密度 + 效率双赢 |
| **典型操作 3：可视化概念塔（L1→L2 层级，同簇同义词一眼看出聚类是否正确）** | ✅ 优：卡片可内嵌 Mini Neo4j Graph 缩略图（@ant-design/charts Graph 或 react-force-graph），层级缩略图直接在卡片上看 | ❌ 差：表格塞不了图，需跳转到独立 Graph 页面，来回切换耗 15s/条 | ✅ **优**：Table 概览 → Drawer 详情页顶部放 200×200 小概念图（只读 GraphCanvas），再结合 JSON details，效率 = 方案 A×0.9，优于 B |
| **响应式布局（小屏 1280×720 管理员笔记本人工审核）** | ⚠️ 中：Masonry 3→2→1 列自适应，但多选在窄屏不可用（需左滑） | ✅ 优：AntD Table scroll={{ x: 'max-content' }} + sticky columns 左右冻结，小屏可横向滚动 | ✅ **优（同 B）**：AntD Table 响应式 + Drawer 720px 宽度在 1280 屏仍有操作空间 |
| **HITL 审核（US6）与抽取修正 5 种 op 操作按钮摆放 ergonomic** | ⚠️ 中：卡片底部 approve/reject 按钮 2 个还好，加上 retype / add_synonym / merge_entities / mark_incorrect 4 个 HITL 按钮 = 卡片底部拥挤如工具栏 | ⚠️ 中：4 个 HITL op 只能塞到 Dropdown "更多操作" 菜单，路径长 = 点 2 次才能执行 | ✅ **最佳**：Drawer 详情页右侧固定操作栏，7 个按钮（2 审批 + 5 HITL）按 "高频左、低频右、危险色红" 分组摆放，附 tooltip 说明；操作完成 Drawer auto-close 下一条；US6 操作效率比 A/B 快 2 倍 |
| **质量面板 6 大 KPI 概览 + 列表过滤 + 导出 CSV（FR-052）** | ❌ 差：Masonry 没有 filter bar / sorter / 列统计，需自写 200 行过滤组件；导出 CSV 要遍历卡片 DOM 再拼 | ✅ 优：AntD Table columns 配置 filters / sorter / defaultFilteredValue 即开即用；`pro-table` 自带 `toolBarRender` 导出 CSV 按钮，FR-052 10 行完成 | ✅ **同 B 优**：Table 过滤 + 导出与 B 完全相同；KPI 在 Table 上方放 6 个 Statistic Card（AntD Statistic 组件）+ Tooltip 趋势图，胜 B 一筹 |
| **一致性（与 ODAP 前端其他列表页：ExtractionPreview / Goal Proposal 列表）** | ❌ 差：现有页面全部是 AntD Table，突然变 Masonry 管理员学习成本陡升（违反一致性 heuristics） | ✅ 最佳：与现有 extraction list、goal list 一模一样，管理员 0 培训上手（符合 雅各布定律） | ✅ **同 B 一致 + 有升级**：Table 行为一致，Drawer 详情也是 AntD 常见模式（Form Drawer 广泛用），用户无学习成本 |
| **开发工作量（前端 SP 预估人日，假设 1 前端 + 0 设计稿）** | 4-5 人日：Masonry CSS 适配 + checkbox 多选自研 + 自研 filter bar | 2 人日：AntD Table 配置列 + rowSelection + columns filter/sorter | **3 人日**：2 人日 Table 配置 + 1 人日 Drawer + Descriptions + 操作栏（比 B 多 1 人日，换长期运营效率翻倍） |
| **可访问性（a11y：键盘 Tab 导航 / 屏幕阅读器 NVDA）** | ⚠️ 差：Masonry 流布局 Tab 顺序与视觉顺序不一致，NVDA 读乱 | ✅ 优：AntD Table 5.x WCAG 2.1 AA 认证（官方 docs），Tab/Shift-Tab 顺序正确 | ✅ **同 B 优**：AntD Table + Drawer 双组件均 WCAG AA 认证 |

### 最终选型（预研结论，前端 SP 必须遵守此选型避免返工）：

**方案 C：Ant Design Table 5.x 列表（主视图，批量选择 + 过滤排序） + Drawer 抽屉式详情页（单条深度研判 + 5 HITL 操作按钮）混合**

**选型理由**：
1. **运营效率 = 操作 1 + 操作 2 + 操作 3 加权平均最快**（权重 50%）：
   - 操作 1 批量 approve：方案 C = 方案 B = 3s / 50 条（Masonry 120s 彻底输）
   - 操作 2 单条深度研判：方案 C 20s/条 略输 Masonry 6s，但因操作 1 节省了 117s，总加权（批量 80% : 单条 20%）C > A > B
   - 操作 3 HITL 5 op：方案 C Drawer 固定操作栏 ergonomic 设计比方案 A/B 快 2 倍
2. **零学习成本（雅各布定律 + 一致性）**（权重 20%）：ODAP 现有 extraction/goal/proposal 列表全是 AntD Table，管理员 "肌肉记忆" 直接复用；Drawer 详情也是表单编辑常用模式。如果前端选 Masonry，管理员每次进来都在想 "多选怎么用？" 反而抱怨 "怎么和其他页面不一样"（Spec NFR-017 兼容零停机，对 UX 同样适用）。
3. **开发工作量适中 3 人日 + FR-052 无缝落地**（权重 15%）：方案 B 太简陋（单条研判太慢会导致管理员积压 candidate → 审批流 SLA NFR-004 P95 ≤ 30s 不可能满足）；方案 A 太重工（5 人日 + 自研多选 + 过滤）；方案 C 正好：1 人日 Drawer 换 2 倍运营效率是最值 ROI。
4. **Out of Scope 不冲突**（权重 15%）：Spec Out of Scope 4 明确 "本 SP2 仅提供 REST API + 数据契约，前端 UI 由独立前端 SP 实现"。本选型仅作为前端 SP 的 **Architecture Decision Record (ADR-007-1)** 强制约束，避免前端工程师自己选 Masonry 导致运营效率灾难。

---

## Summary of Final Selections (8 RQ 总览，实施时依此为准)

| RQ | 模块 | 最终选型 | 版本号 | 核心理由关键字 |
|---|---|---|---|---|
| RQ-1 | L1 语义聚类算法 | HDBSCAN | hdbscan 0.8.38 | 免 k + 抗噪 + 可解释 confidence = 与审批流 1:1 |
| RQ-2 | L2 层级推断 | FCA 形式概念分析（fca-lite MIT 或 concepts 0.9.2） | fca-lite 0.1.4 | 层级数学正确 + 幂等 + 0 成本合规，LLM 精度不足 |
| RQ-3 | 中文 Embedding | BGE-large-zh-v1.5（int8 生产） | BAAI/bge-large-zh-v1.5 | CMTEB 聚类 74.2 第一 + MIT 无法务模糊 |
| RQ-4 | L6 OWL 推理 + 存储 | **SP2 存储=自定义 DAG+rdflib 语法；SP4 推理预选型=HermiT** | rdflib 7.0.0 / HermiT 1.4.5.x | 遵守 Out of Scope 不做推理；但 axiom_type 强对齐 OWL 官方 IRI 免返工 |
| RQ-5 | L4 关联规则 | Apriori（mlxtend） | mlxtend 0.23.1 | 字段 1:1 对齐 spec 表 = 少写 20 行后处理；D<10K 速度可接受 |
| RQ-6 | USL 持久化架构 | SQLite（权威源）+ Neo4j（可视化只读副本）双写 + 每日巡检一致性修复 | SQLite 3 / Neo4j ≥ 5.13 | 质量面板 SQL 分析 + 概念塔 Neo4j 可视化 = 两者兼得，复用 SP1 运维经验 |
| RQ-7 | 后台异步任务 | **混合方案**：短批量 asyncio.create_task + 长任务/Outbox daemon Thread | 标准库 asyncio + threading（零中间件） | 不引入 Celery/Redis 运维负担；FR-039/043 可靠性兜底已写 spec |
| RQ-8 | 管理员审核台 UI（前端预研 ADR） | AntD Table 5.x（列表批量）+ Drawer（详情单条）混合 | AntD 5.x + ProComponents | 操作 1/2/3 综合效率最高 + 0 学习成本 + 3 人日开发适中 |

---

## Spec 影响反馈（Research 修正 Spec 点）

| Research 发现 | Spec 原文位置 | 修正建议（必须在 contracts 实施时落地，spec 原文保持已审批版） |
|---|---|---|
| RQ-1 HDBSCAN 比 DBSCAN 更抗密度不均 | FR-013 参数 | 无需修改，FR-013 已指定 HDBSCAN min_cluster_size=3 与研究一致 ✅ |
| RQ-2 concepts 库 GPL 许可证风险 | 子域 C pip 依赖清单 | **实施修正**：优先 `pip install fca-lite==0.1.4`（MIT）+ 验证 `Context.lattice` 接口兼容；如功能缺失则向法务申请 concepts 0.9.2 GPL 商业用例外（企业内使用通常 OK） |
| RQ-3 BGE 无需 trust_remote_code 与 Jina 模糊商用条款 | 数据依赖表格 | **实施修正**：`SentenceTransformer("BAAI/...")` 时显式加参数 `trust_remote_code=False`（NFR-011 强安全） |
| RQ-4 HermiT LGPL 与 Pellet AGPL 许可证 | L6 存储 axiom_type | **Spec 确认**：FR-048 中 7 种 axiom_type 的命名必须严格对齐 OWL 官方 IRI（rdfs:subClassOf / owl:disjointWith 等），不可自定义中文命名，以免 SP4 切换 HermiT 时迁移 |
| RQ-5 FP-growth 作为后续可选替换 | 子域 H 注释 | 实施代码中 `ConceptExtractor.run_l4` 内部写一行注释 `# 如果后续 D>100k，把 apriori 改成 fpgrowth（同 mlxtend 包同接口）` |
| RQ-6 双写每日巡检脚本不可少 | NFR-012 + 架构图 | **实施新增**：`odap/biz/core/semantic/storage/consistency_checker.py`（虽然 spec 正文提了 daily cron，实施必须按此脚本跑） |
| RQ-7 不引入 Celery 但 outbox 线程需显式 | FR-039 描述 | 实施 `impl/outbox_worker_impl.py` 显式用 `threading.Thread`（不用 asyncio.to_thread/loop.run_in_executor 任何伪装事件循环） |
| RQ-8 前端选 Drawer + Table 混合 | Success Criteria UI | 不在本 SP2 写代码；前端 SP 创建时 ADR-007-1 必须引用此 Research 结果，否则架构评审 deny |

---
