# Contract: OlPipelineService + PipelineOrchestrator — 6 方法签名

**Location**:
- `OlPipelineService`: `odap/biz/semantic_admin/ol_pipeline/services/pipeline_service.py`
- `PipelineOrchestrator`: `odap/biz/semantic_admin/ol_pipeline/impl/pipeline_orchestrator.py`
- `SqlitePipelineStorage`: `odap/biz/semantic_admin/ol_pipeline/storage/sqlite_pipeline_storage.py`（3 张运行表）

**依赖关系**: `OlPipelineService` → `PipelineOrchestrator`（asyncio 编排 L1→L2→QUALITY→WRITEBACK）→ `SqlitePipelineStorage`（写 `pipeline_runs` / `schema_candidates` / `pipeline_layer_snapshots`）→ `CandidateDualWriter`（双写 Neo4j `USL__Candidate` 节点）→ `QualityGateService`（QUALITY 层调用 `evaluate` 批量）。

---

## Section 0: 公共数据类型

```python
from typing import Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# ============= 枚举 =============
class PipelineStatus(str, Enum):
    PENDING              = "pending"
    RUNNING_L1           = "running_l1"
    RUNNING_L2           = "running_l2"
    RUNNING_QUALITY      = "running_quality"
    RUNNING_WRITEBACK    = "running_writeback"
    COMPLETED            = "completed"
    FAILED               = "failed"
    CANCELLED            = "cancelled"

class PipelineTrigger(str, Enum):
    MANUAL          = "manual"
    SCHEDULED       = "scheduled"
    INGEST_HOOK     = "ingest_hook"
    REBUILD_INDEX   = "rebuild_index"

class TargetLayer(str, Enum):
    L1   = "L1"     # 只跑到 L1 一级分类
    L2   = "L2"     # L1→L2 二级分类（默认）
    FULL = "FULL"   # L1→L2→QUALITY 质量闸评估（不写回，写回由 approval 触发）

class LayerCode(str, Enum):
    L1        = "L1"
    L2        = "L2"
    QUALITY   = "QUALITY"
    WRITEBACK = "WRITEBACK"

# ============= 核心 Pydantic =============
class OLPipelineConfig(BaseModel):
    """一次 pipeline 运行的配置快照（可复现实验）。存 JSON TEXT 列。"""
    target_layer: TargetLayer = TargetLayer.L2
    l1_enabled_layers: list[str] = Field(default_factory=lambda: ["usl_align", "normalize", "pos_filter"])
    l2_embedding_model: str = "bge-large-zh-v1.5"
    l2_cluster_algo: str = "hdbscan"
    l2_min_cluster_size: int = 3
    l2_similarity_threshold: float = 0.82
    quality_gate_enabled: bool = True
    quality_batch_size: int = 50
    dedup_similarity_cutoff: float = 0.92
    stopword_blacklist: list[str] = Field(default_factory=list)
    max_candidates_per_run: Optional[int] = None   # None = 无上限
    enabled_extract_types: list[str] = Field(default_factory=lambda: ["term", "synonym", "hierarchy", "property", "cross_mapping"])

class PipelineRun(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    domain_id: str
    source_batch_id: Optional[str] = None
    source_description: Optional[str] = None
    trigger_type: PipelineTrigger
    status: PipelineStatus
    target_layer: TargetLayer
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    progress_percent: int = Field(ge=0, le=100, default=0)
    total_input_chars: int = 0
    total_input_tokens: int = 0
    l1_candidate_count: int = 0
    l2_candidate_count: int = 0
    quality_pass_count: int = 0
    writeback_written_count: int = 0
    writeback_failed_count: int = 0
    writeback_started_at: Optional[datetime] = None
    writeback_finished_at: Optional[datetime] = None
    error_summary: list[dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str
    created_at: datetime

class PipelineLayerSnapshot(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    run_id: str
    layer_code: LayerCode
    layer_version: str = "1.0.0"
    step_name: str
    status: PipelineStatus
    input_count: int = 0
    output_count: int = 0
    filtered_count: int = 0
    duration_ms: int = 0
    peak_memory_mb: Optional[int] = None
    metrics: dict[str, Any] = Field(default_factory=dict)   # precision/recall/f1 等（有标注集时）
    error: Optional[dict[str, Any]] = None
    outputs_sample: list[dict[str, Any]] = Field(default_factory=list)  # 最多保留最近 N=50 条，方便肉眼排查
    started_at: datetime
    completed_at: Optional[datetime] = None
```

---

## Section 1: OlPipelineService 6 方法签名

```python
class OlPipelineService:
    """OL 流水线业务门面。6 方法：submit/schedule_run/cancel_run/get_run_status/list_runs/resume_from_failed_step。
    编排委托给 PipelineOrchestrator（asyncio.create_task 异步执行，不阻塞 HTTP 响应）。
    """

    def __init__(self,
                 orchestrator: "PipelineOrchestrator",
                 storage: "SqlitePipelineStorage",
                 dual_writer: "CandidateDualWriter",
                 quality_gate: Optional["QualityGateService"] = None):
        ...

    # ============= M1: submit（手动/ingest_hook 触发） =============
    def submit(self,
               domain_id: str,
               input_source: str | list[str],
               created_by: str,
               *,
               trigger_type: PipelineTrigger = PipelineTrigger.MANUAL,
               source_batch_id: Optional[str] = None,
               source_description: Optional[str] = None,
               config: Optional[OLPipelineConfig] = None,
               wait_for_start: bool = False,
               start_timeout_sec: int = 5) -> PipelineRun:
        """M1: 提交一次 OL 流水线执行请求 → 创建 pipeline_runs 行 → 异步编排任务入队。

        Args:
            domain_id:            目标语义域（抽取结果写入此域的候选表）
            input_source:         单个文档路径(str) 或 文档路径列表；可含 MinIO object key
            created_by:           user_id（JWT sub）
            trigger_type:         触发类型（默认 MANUAL）
            source_batch_id:      来源 Hyper-Extract 批次 ID / ingest session id
            source_description:   人类可读说明，如 "001-三国第一章-简体.txt"
            config:               运行级配置覆盖（None → 使用 domain 级默认 config_snapshot）
            wait_for_start:       True → 阻塞等待 run 进入 RUNNING_L1（最多 start_timeout_sec）再返回
            start_timeout_sec:    wait_for_start=True 时的超时秒数

        Returns:
            PipelineRun（含新 run_id + 当前 status）

        Raises:
            DomainNotFoundError:     domain_id 在 usl_domains 中不存在或 is_active=0
            ValueError:               input_source 为空列表 / config 字段非法（如 target_layer 非枚举）
            PipelineStartTimeoutError: wait_for_start=True 但 start_timeout_sec 内 run 未启动
        """

    # ============= M2: schedule_run（定时 / Cron 触发） =============
    def schedule_run(self,
                     domain_id: str,
                     cron_expression: str,
                     created_by: str,
                     *,
                     input_source_provider: str = "latest_ingest",   # 如何取 input_source
                     config: Optional[OLPipelineConfig] = None,
                     timezone: str = "Asia/Shanghai",
                     is_active: bool = True) -> dict[str, Any]:
        """M2: 注册一次定时任务（定时执行 submit 等价动作）。
        调度执行委托给 odap/infra/config/cron.py（如果项目已有），或简化为：本方法仅记录 cron 元数据，
        实际触发由外部 cronjob 调 OlPipelineService.submit 实现。

        Args:
            domain_id:              目标域
            cron_expression:        标准 5 段 cron: "分 时 日 月 周"，如 "0 2 * * *" = 每日 02:00
            created_by:             创建者 user_id（必须 schema_auditor 以上）
            input_source_provider:  "latest_ingest" / "all_docs" / "modified_last_24h"，决定 run 启动时如何组装 input_source
            config:                 每次 run 的默认配置
            timezone:               cron 时区
            is_active:              True=生效 False=暂停调度

        Returns:
            {"schedule_id": str, "next_run_at": datetime, "cron": str, "is_active": bool}

        Raises:
            ValueError:   cron_expression 解析失败 / timezone 非法
            ForbiddenError: created_by 角色 < schema_auditor
        """

    # ============= M3: cancel_run =============
    def cancel_run(self, run_id: str, operator_id: str, *,
                   reason: Optional[str] = None,
                   force_kill_after_sec: int = 30) -> PipelineRun:
        """M3: 取消正在运行或 pending 的 run。
        步骤：标记 run.status → CANCELLED；若 orchestrator 有正在执行的任务 → 发送取消信号；force_kill_after_sec 后强杀。

        Args:
            run_id:                pipeline_runs.id
            operator_id:           操作人 user_id（必须 run.created_by 或 schema_auditor+）
            reason:                取消原因（可选，记录到 error_summary[0].cancel_reason）
            force_kill_after_sec:  软信号发送后，超过此时长仍未停止则强制取消

        Returns:
            PipelineRun（status=CANCELLED 或之前已经是终态则直接幂等返回）

        Raises:
            RunNotFoundError:       run_id 不存在
            ForbiddenError:         operator_id 无权限（非创建者且非管理员）
            RunAlreadyFinalError:   run 已是 COMPLETED/FAILED → 取消无意义（但幂等返回，不抛错）
        """

    # ============= M4: get_run_status =============
    def get_run_status(self, run_id: str, *,
                       include_layer_snapshots: bool = True,
                       include_candidate_preview: int = 0) -> dict[str, Any]:
        """M4: 查询单次 run 详情。

        Args:
            run_id:                    pipeline_runs.id
            include_layer_snapshots:   True → 附加 pipeline_layer_snapshots 列表（按 layer_code+step_name 排序）
            include_candidate_preview: >0 → 取前 N 个 schema_candidates（按 id LIMIT N）作为示例

        Returns:
            {
              "run": PipelineRun,
              "layer_snapshots": list[PipelineLayerSnapshot],   # include_layer_snapshots=True 时
              "candidate_preview": list[dict],                   # include_candidate_preview>0 时，candidate_type/origin_layer/quality_total_score
              "progress": {
                  "overall_percent": int,
                  "current_layer": LayerCode | None,
                  "current_step": str | None,
                  "eta_seconds": int | None
              }
            }

        Raises:
            RunNotFoundError: run_id 不存在
        """

    # ============= M5: list_runs（分页 + 多过滤） =============
    def list_runs(self, *,
                  domain_id: Optional[str] = None,
                  status: Optional[PipelineStatus | list[PipelineStatus]] = None,
                  trigger_type: Optional[PipelineTrigger] = None,
                  created_by: Optional[str] = None,
                  source_batch_id: Optional[str] = None,
                  created_after: Optional[datetime] = None,
                  created_before: Optional[datetime] = None,
                  has_errors_only: bool = False,
                  page: int = 1,
                  page_size: int = 50,
                  order_by: str = "created_at",
                  order_desc: bool = True) -> tuple[int, list[PipelineRun]]:
        """M5: run 列表（分页 + 多维筛选）。是前端 /semantic-admin/pipeline 页面主数据源。

        Args:
            domain_id:          按域过滤
            status:             单状态或状态列表（如 [RUNNING_L1, RUNNING_L2] = 任何正在运行中）
            trigger_type:       触发类型过滤
            created_by:         创建人过滤
            source_batch_id:    来源批次过滤
            created_after/before: 创建时间窗口
            has_errors_only:    True → 仅返回 error_summary 非空的 run
            page/page_size:     分页（page 从 1 开始）
            order_by:           允许的排序字段: created_at / started_at / completed_at / progress_percent
            order_desc:         默认降序（最近的在前）

        Returns:
            (total_count, items)

        Raises:
            ValueError: order_by 不在允许集合 / page<=0 / page_size 超过 500 的硬上限
        """

    # ============= M6: resume_from_failed_step（失败后断点恢复） =============
    def resume_from_failed_step(self, run_id: str, operator_id: str, *,
                                skip_failed_step: bool = False,
                                override_config: Optional[OLPipelineConfig] = None) -> PipelineRun:
        """M6: 对失败（status=FAILED）的 run 断点恢复。
        读取 pipeline_layer_snapshots：跳过所有 status=COMPLETED 的 step → 从第一个 status=FAILED 或后续 step 重新执行。

        Args:
            run_id:             pipeline_runs.id（status 必须 = FAILED，否则幂等返回或抛错）
            operator_id:        操作人
            skip_failed_step:   True → 直接跳过失败 step（以 step 前的 output 作为输入），用于"该 step 已知 bug 已修复但结果可人工确认"
            override_config:    恢复时替换部分 config（如换 embedding 模型、调大 cluster 阈值）

        Returns:
            PipelineRun（status 重置为 RUNNING_<下一个将执行的 layer>；新的 started_at/error_summary 清空）

        Raises:
            RunNotFoundError:     run_id 不存在
            RunNotFailedError:    run.status != FAILED
            ResumeBlockedError:   失败 step 之后无任何已完成 step（即第一步就失败），且 skip_failed_step=False → 无法断点，只能 submit 新 run
        """
```

---

## Section 2: 快速 6 方法索引表

| # | 方法 | 核心操作 | 对应 SQL 表写入 |
|---|------|---------|---------------|
| M1 | `submit(domain_id, input_source, created_by, ...)` | 新建 run + 提交编排任务 | INSERT pipeline_runs |
| M2 | `schedule_run(domain_id, cron_expr, created_by, ...)` | 注册 cron 元数据（可选） | schedule 元数据表（或简化：内存 dict） |
| M3 | `cancel_run(run_id, operator_id, ...)` | 标记 CANCELLED + 发取消信号 | UPDATE pipeline_runs.status |
| M4 | `get_run_status(run_id, ...)` | run 详情 + 分层进度 + 候选预览 | SELECT runs + snapshots + candidates |
| M5 | `list_runs(*filters, page, page_size)` | 列表分页搜索 | SELECT pipeline_runs WHERE ... ORDER BY ... LIMIT ? |
| M6 | `resume_from_failed_step(run_id, operator_id, ...)` | 失败断点恢复 | UPDATE runs.status + INSERT layer_snapshots(新) |

**性能目标（对齐 plan.md Complexity Tracking §Performance Goals）**：
- `submit()` HTTP 返回 ≤ 200ms（实际 run 异步执行）；
- `list_runs(page_size=50)` ≤ 80ms（基于 domain_id+status+created_at 复合索引）；
- `get_run_status(include_layer_snapshots=True)` ≤ 60ms（run_id + layer_snapshots.run_id 外键索引）。
