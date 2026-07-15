"""Dashboard Query Service（C3 契约 + 3 视图支持）。

对应 API 契约：
  C3 GET /quality-gate/dashboard (summary / terms-trend / approvals-breakdown)

视图：
  view="summary"            → 原有 DashboardResponse 字段
  view="terms_trend"        → {range, workspace_id, days, domain_id, daily_points,
                               accumulative_new}
  view="approvals_breakdown"→ {range, workspace_id, by_role, by_decision, by_outcome,
                               avg_l1_seconds, avg_l2_seconds}

所有方法返回 Dict[str, Any]，错误格式 {"status": "error", "code": XXX_4xx, "message": "..."}。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
        SQLiteCandidateStorage,
    )


_VALID_RANGES = {"range_7d", "range_30d", "all_time"}
_VALID_VIEWS = {"summary", "terms_trend", "approvals_breakdown"}


# ======================================================================
# 辅助函数
# ======================================================================

def _parse_dt(s: Any) -> Optional[datetime]:
    """把 ISO 字符串 parse 为 datetime，失败返回 None。"""
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        txt = str(s).strip()
        if not txt:
            return None
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        return datetime.fromisoformat(txt)
    except Exception:
        return None


def _in_range(dt: Optional[datetime], since: Optional[datetime]) -> bool:
    """dt 在 [since, now] 区间？ since=None 表示不设下界。"""
    if dt is None:
        return True
    if since is None:
        return True
    return dt >= since


def _overall_label(total_score: Optional[float]) -> str:
    """PASS>=0.8, REVIEW 0.5-0.8, FAIL<0.5（与 quality_gate_service 对齐）。"""
    try:
        s = float(total_score)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "FAIL"
    if s >= 0.8:
        return "PASS"
    if s >= 0.5:
        return "REVIEW"
    return "FAIL"


def _empty_metrics() -> Dict[str, Any]:
    """空 dashboard skeleton（view=summary 基础数据）。"""
    return {
        "range": "all_time",
        "total_candidates": 0,
        "by_status": {
            "DRAFT": 0, "QUALITY_REVIEW": 0, "REVIEW": 0,
            "PENDING_L1": 0, "PENDING_L2": 0,
            "APPROVED": 0, "REJECTED": 0, "OTHER": 0,
        },
        "by_tier": {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0, "UNRATED": 0},
        "by_quality_gate": {"PASS": 0, "REVIEW": 0, "FAIL": 0},
        "avg_gate_scores": {
            "gate1_avg": 0.0, "gate2_avg": 0.0,
            "gate3_avg": 0.0, "total_avg": 0.0,
        },
        "approval_times": {
            "l1_avg_secs": 0, "l2_avg_secs": 0, "total_avg_secs": 0,
            "l1_samples": 0, "l2_samples": 0, "total_samples": 0,
        },
        # --- view 扩展字段（默认空，保证 DashboardResponse 校验通过）---
        "days": None,
        "workspace_id": None,
        "domain_id": None,
        "daily_points": [],
        "accumulative_new": [],
        "by_role": {},
        "by_decision": {},
        "by_outcome": {},
        "avg_l1_seconds": 0,
        "avg_l2_seconds": 0,
    }


def _date_key(dt: Optional[datetime]) -> str:
    """date -> YYYY-MM-DD。"""
    if dt is None:
        return ""
    return dt.date().isoformat()


# ======================================================================
# DashboardQueryService 主类
# ======================================================================

class DashboardQueryService:
    """QualityGate Dashboard 聚合查询服务（C3 + 3 视图）。

    扫描范围：
      - all_time:  无时间过滤
      - range_7d:  candidate.created_at >= now-7d
      - range_30d: candidate.created_at >= now-30d
    """

    def __init__(
        self,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
    ) -> None:
        if candidate_storage is None:
            from odap.biz.semantic_admin.candidate_store.storage import (
                Storage as _CS,
            )
            candidate_storage = _CS()
        self.candidate_storage = candidate_storage

    # ------------------------------------------------------------------
    # 公共：3 视图入口
    # ------------------------------------------------------------------

    def get_dashboard(
        self,
        *,
        dimension: str = "all_time",
        workspace_id: Optional[str] = None,
        view: str = "summary",
        days: Optional[int] = None,
        domain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """返回质量仪表盘（3 视图：summary / terms_trend / approvals_breakdown）。"""
        try:
            # 基础校验
            dim = str(dimension or "all_time").strip().lower()
            if dim not in _VALID_RANGES:
                return {
                    "status": "error",
                    "code": "INVALID_DIMENSION_400",
                    "message": (
                        f"dimension 必须是 {sorted(_VALID_RANGES)}，"
                        f"当前={dim!r}"
                    ),
                }
            vw = str(view or "summary").strip().lower()
            if vw not in _VALID_VIEWS:
                return {
                    "status": "error",
                    "code": "INVALID_VIEW_400",
                    "message": (
                        f"view 必须是 {sorted(_VALID_VIEWS)}，当前={vw!r}"
                    ),
                }

            # since 时间窗口（terms_trend 视图下，优先使用 days 参数）
            now = datetime.now()
            if vw == "terms_trend" and days:
                effective_days = max(1, int(days))
                since: Optional[datetime] = now - timedelta(days=effective_days)
                eff_dim = dim if dim != "all_time" else f"range_{effective_days}d"
            else:
                effective_days = int(days) if days else None
                since = None
                if dim == "range_7d":
                    since = now - timedelta(days=7)
                elif dim == "range_30d":
                    since = now - timedelta(days=30)
                eff_dim = dim

            # 公共：扫描 candidate（最多 10000 条，够用）
            scan_page, scan_per = 1, 500
            max_scan_pages = 20
            all_cands: List[Dict[str, Any]] = []

            for _p in range(1, max_scan_pages + 1):
                filters: Dict[str, Any] = {}
                if domain_id:
                    filters["domain_id"] = domain_id
                list_result = self.candidate_storage.list_candidates(
                    page=scan_page, page_size=scan_per, **filters
                )
                cands = (
                    list_result.get("items") or []
                    if isinstance(list_result, dict) else list_result
                )
                if not cands:
                    break
                for c in cands:
                    created = _parse_dt(c.get("created_at"))
                    if _in_range(created, since):
                        if workspace_id and str(c.get("workspace_id") or "") != str(workspace_id):
                            continue
                        all_cands.append(c)
                if len(cands) < scan_per:
                    break
                scan_page += 1

            # 分发到视图
            generated_at = now.isoformat()
            if vw == "summary":
                out = self._view_summary(
                    all_cands, eff_dim, workspace_id,
                )
                out["generated_at"] = generated_at
                return out
            elif vw == "terms_trend":
                out = self._view_terms_trend(
                    all_cands,
                    dimension=eff_dim,
                    workspace_id=workspace_id,
                    days=effective_days,
                    domain_id=domain_id,
                )
                out["generated_at"] = generated_at
                return out
            else:  # approvals_breakdown
                out = self._view_approvals_breakdown(
                    all_cands, eff_dim, workspace_id,
                )
                out["generated_at"] = generated_at
                return out
        except Exception as e:
            return {
                "status": "error",
                "message": f"get_dashboard 失败: {e}",
            }

    # ------------------------------------------------------------------
    # view=summary（原逻辑，代码精简）
    # ------------------------------------------------------------------

    def _view_summary(
        self,
        cands: List[Dict[str, Any]],
        dimension: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        out = _empty_metrics()
        out["range"] = dimension
        out["workspace_id"] = workspace_id
        if workspace_id is not None:
            out["workspace_id"] = workspace_id

        submit_dt: Dict[str, datetime] = {}
        l1_dt: Dict[str, datetime] = {}
        l2_dt: Dict[str, datetime] = {}
        gate1s: list[float] = []
        gate2s: list[float] = []
        gate3s: list[float] = []
        totals: list[float] = []

        total_scanned = 0
        for c in cands:
            total_scanned += 1
            st_raw = str(c.get("status") or "").upper()
            status_key = st_raw if st_raw in out["by_status"] else "OTHER"
            out["by_status"][status_key] = out["by_status"].get(status_key, 0) + 1

            tier = str(c.get("quality_tier") or "").upper() or "UNRATED"
            tier_key = tier if tier in out["by_tier"] else "UNRATED"
            out["by_tier"][tier_key] = out["by_tier"].get(tier_key, 0) + 1

            cid = str(c.get("id"))
            qr = None
            try:
                qr = self.candidate_storage.get_quality_report_by_candidate(cid)
            except Exception:
                qr = None
            if qr:
                g1 = float(qr.get("gate1_score") or 0)
                g2 = float(qr.get("gate2_score") or 0)
                g3 = float(qr.get("gate3_score") or 0)
                total = float(qr.get("total_score") or 0)
                label = _overall_label(total)
                out["by_quality_gate"][label] = (
                    out["by_quality_gate"].get(label, 0) + 1
                )
                gate1s.append(g1); gate2s.append(g2); gate3s.append(g3)
                totals.append(total)

            try:
                logs = self.candidate_storage.list_approvals_by_candidate(cid)
            except Exception:
                logs = []
            for lg in logs:
                lvl = str(lg.get("level") or "").upper()
                dec = str(lg.get("decision") or "").upper()
                dt = _parse_dt(lg.get("created_at"))
                if not dt:
                    continue
                if lvl == "SUBMIT" or dec == "SUBMIT":
                    submit_dt[cid] = dt
                elif lvl in ("L1", "AUDIT") and dec == "APPROVE":
                    l1_dt[cid] = dt
                elif lvl in ("L2", "FINAL_APPROVE") and dec == "APPROVE":
                    l2_dt[cid] = dt

        out["total_candidates"] = total_scanned

        def _avg(xs: list[float]) -> float:
            return round(sum(xs) / len(xs), 4) if xs else 0.0
        out["avg_gate_scores"]["gate1_avg"] = _avg(gate1s)
        out["avg_gate_scores"]["gate2_avg"] = _avg(gate2s)
        out["avg_gate_scores"]["gate3_avg"] = _avg(gate3s)
        out["avg_gate_scores"]["total_avg"] = _avg(totals)

        l1_deltas: list[int] = []
        l2_deltas: list[int] = []
        total_deltas: list[int] = []
        for cid, sdt in submit_dt.items():
            l1d = l1_dt.get(cid)
            l2d = l2_dt.get(cid)
            if l1d and l1d >= sdt:
                l1_deltas.append(int((l1d - sdt).total_seconds()))
            if l1d and l2d and l2d >= l1d:
                l2_deltas.append(int((l2d - l1d).total_seconds()))
            if sdt and l2d and l2d >= sdt:
                total_deltas.append(int((l2d - sdt).total_seconds()))
        at = out["approval_times"]
        at["l1_samples"] = len(l1_deltas)
        at["l2_samples"] = len(l2_deltas)
        at["total_samples"] = len(total_deltas)
        at["l1_avg_secs"] = int(sum(l1_deltas) / len(l1_deltas)) if l1_deltas else 0
        at["l2_avg_secs"] = int(sum(l2_deltas) / len(l2_deltas)) if l2_deltas else 0
        at["total_avg_secs"] = (
            int(sum(total_deltas) / len(total_deltas)) if total_deltas else 0
        )
        # 同步 avg_l1_seconds / avg_l2_seconds 别名
        out["avg_l1_seconds"] = at["l1_avg_secs"]
        out["avg_l2_seconds"] = at["l2_avg_secs"]
        return out

    # ------------------------------------------------------------------
    # view=terms_trend
    # ------------------------------------------------------------------

    def _view_terms_trend(
        self,
        cands: List[Dict[str, Any]],
        *,
        dimension: str,
        workspace_id: Optional[str],
        days: Optional[int],
        domain_id: Optional[str],
    ) -> Dict[str, Any]:
        """按日期聚合 daily_points（new/approved/rejected）+ accumulative_new。"""
        out = _empty_metrics()
        out["range"] = dimension
        out["workspace_id"] = workspace_id
        out["days"] = days
        out["domain_id"] = domain_id

        # ---- daily 聚合：new（新增）/ approved（审批通过）/ rejected（驳回） ----
        daily_new: Dict[str, int] = defaultdict(int)
        daily_approved: Dict[str, int] = defaultdict(int)
        daily_rejected: Dict[str, int] = defaultdict(int)

        for c in cands:
            created_dt = _parse_dt(c.get("created_at"))
            dk = _date_key(created_dt)
            if dk:
                daily_new[dk] += 1
            # 通过/驳回状态统计当日最后变更
            st = str(c.get("status") or "").upper()
            # 从 approval_log 中查最后决定时间
            cid = str(c.get("id"))
            final_dec_at: Optional[datetime] = None
            final_dec: Optional[str] = None
            try:
                logs = self.candidate_storage.list_approvals_by_candidate(cid)
            except Exception:
                logs = []
            for lg in logs:
                dec = str(lg.get("decision") or "").upper()
                lvl = str(lg.get("level") or "").upper()
                if dec in ("APPROVE",) and lvl in ("L2", "FINAL_APPROVE"):
                    t = _parse_dt(lg.get("created_at"))
                    if t:
                        final_dec_at = t
                        final_dec = "APPROVED"
                elif dec in ("REJECT",) and lvl in ("L1", "L2", "REJECT", "AUDIT"):
                    t = _parse_dt(lg.get("created_at"))
                    if t:
                        # 最近一次决定为准
                        final_dec_at = t
                        final_dec = "REJECTED"
            # 兜底：直接看 candidate.status
            if final_dec is None:
                if st in ("APPROVED", "WRITTEN_BACK", "ADMIN_APPROVED", "AUDITOR_APPROVED"):
                    final_dec = "APPROVED"
                    final_dec_at = created_dt or final_dec_at
                elif st in ("REJECTED", "REVIEWER_REJECTED", "ADMIN_REJECTED", "STOPLISTED"):
                    final_dec = "REJECTED"
                    final_dec_at = created_dt or final_dec_at
            if final_dec == "APPROVED" and final_dec_at:
                daily_approved[_date_key(final_dec_at)] += 1
            elif final_dec == "REJECTED" and final_dec_at:
                daily_rejected[_date_key(final_dec_at)] += 1

        # 日期区间：若有 days 参数，生成从 today - (days-1) ~ today 的连续序列
        if days:
            eff_days = max(1, int(days))
            today = date.today()
            date_seq: List[str] = []
            for i in range(eff_days - 1, -1, -1):
                d = today - timedelta(days=i)
                date_seq.append(d.isoformat())
        else:
            all_dates = set(daily_new.keys()) | set(daily_approved.keys()) | set(
                daily_rejected.keys()
            )
            date_seq = sorted(d for d in all_dates if d)

        daily_points: List[Dict[str, Any]] = []
        for d in date_seq:
            daily_points.append({
                "date": d,
                "new": daily_new.get(d, 0),
                "approved": daily_approved.get(d, 0),
                "rejected": daily_rejected.get(d, 0),
            })

        # accumulative_new：累加 new 数
        accumulative_new: List[Dict[str, Any]] = []
        total_acc = 0
        for dp in daily_points:
            total_acc += int(dp["new"] or 0)
            accumulative_new.append({
                "date": dp["date"],
                "total": total_acc,
            })

        out["daily_points"] = daily_points
        out["accumulative_new"] = accumulative_new
        # candidate 总数
        out["total_candidates"] = sum(int(dp["new"] or 0) for dp in daily_points)
        return out

    # ------------------------------------------------------------------
    # view=approvals_breakdown
    # ------------------------------------------------------------------

    def _view_approvals_breakdown(
        self,
        cands: List[Dict[str, Any]],
        dimension: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        """审批按角色/决定/结果 分类聚合 + avg L1/L2 时长。"""
        out = _empty_metrics()
        out["range"] = dimension
        out["workspace_id"] = workspace_id

        by_role: Dict[str, int] = defaultdict(int)
        by_decision: Dict[str, int] = defaultdict(int)
        by_outcome: Dict[str, int] = defaultdict(int)

        l1_deltas: List[int] = []
        l2_deltas: List[int] = []

        # 遍历每个 candidate，查 approval_log
        for c in cands:
            cid = str(c.get("id"))
            # candidate.outcome（终态）
            st = str(c.get("status") or "").upper()
            if st in ("APPROVED", "WRITTEN_BACK", "ADMIN_APPROVED", "AUDITOR_APPROVED"):
                by_outcome["APPROVED"] += 1
            elif st in ("REJECTED", "REVIEWER_REJECTED", "ADMIN_REJECTED", "STOPLISTED"):
                by_outcome["REJECTED"] += 1
            else:
                # 非终态或在审批中：不计算 outcome（或 MODIFIED 若检测到 MODIFY 流水
                pass

            submit_dt_val: Optional[datetime] = None
            l1_dt_val: Optional[datetime] = None
            l2_dt_val: Optional[datetime] = None

            try:
                logs = self.candidate_storage.list_approvals_by_candidate(cid)
            except Exception:
                logs = []
            for lg in logs:
                lvl = str(lg.get("level") or "").upper()
                dec = str(lg.get("decision") or "").upper()
                rev = str(lg.get("reviewer") or "")
                cr = lg.get("created_at")
                dt = _parse_dt(cr)

                # ---- by_decision：按 decision 分 SUBMIT/APPROVE/REJECT/MODIFY/AUDIT ----
                if dec in ("SUBMIT", "APPROVE", "REJECT", "MODIFY", "AUDIT"):
                    by_decision[dec] += 1
                elif lvl in ("SUBMIT", "AUDIT", "MODIFY", "REJECT", "FINAL_APPROVE"):
                    by_decision[lvl] += 1

                # ---- by_role：按 level（L1/AUDIT→schema_auditor；L2/FINAL→admin；SUBMIT→submitter；MODIFY→editor）
                if lvl in ("L1", "AUDIT"):
                    by_role["schema_auditor"] += 1
                elif lvl in ("L2", "FINAL_APPROVE"):
                    by_role["admin"] += 1
                elif lvl == "SUBMIT" or dec == "SUBMIT":
                    by_role["submitter"] += 1
                elif lvl == "MODIFY":
                    by_role["editor"] += 1
                elif lvl == "REJECT":
                    # REJECT 可能发生在 L1/L2
                    by_role["rejector"] += 1

                # ---- MODIFY → outcome:MODIFIED 计数 ----
                if lvl == "MODIFY" or dec == "MODIFY":
                    by_outcome["MODIFIED"] += 1

                # ---- approval times（SUBMIT→L1/L1→L2）时长秒 ----
                if dt:
                    if lvl == "SUBMIT" or dec == "SUBMIT":
                        submit_dt_val = dt
                    elif (lvl in ("L1", "AUDIT")) and dec == "APPROVE":
                        l1_dt_val = dt
                    elif (lvl in ("L2", "FINAL_APPROVE")) and dec == "APPROVE":
                        l2_dt_val = dt

            # 计算本 candidate 的 L1/L2 时长（若完整链条存在）
            if submit_dt_val and l1_dt_val and l1_dt_val >= submit_dt_val:
                l1_deltas.append(int((l1_dt_val - submit_dt_val).total_seconds()))
            if l1_dt_val and l2_dt_val and l2_dt_val >= l1_dt_val:
                l2_deltas.append(int((l2_dt_val - l1_dt_val).total_seconds()))

        # 写入结果
        out["by_role"] = dict(by_role)
        out["by_decision"] = dict(by_decision)
        out["by_outcome"] = {
            "APPROVED": by_outcome.get("APPROVED", 0),
            "REJECTED": by_outcome.get("REJECTED", 0),
            "MODIFIED": by_outcome.get("MODIFIED", 0),
        }
        out["avg_l1_seconds"] = (
            int(sum(l1_deltas) / len(l1_deltas)) if l1_deltas else 0
        )
        out["avg_l2_seconds"] = (
            int(sum(l2_deltas) / len(l2_deltas)) if l2_deltas else 0
        )
        # 同步 approval_times 别名（供 summary 视图的字段保留）
        out["approval_times"]["l1_avg_secs"] = out["avg_l1_seconds"]
        out["approval_times"]["l2_avg_secs"] = out["avg_l2_seconds"]
        out["approval_times"]["l1_samples"] = len(l1_deltas)
        out["approval_times"]["l2_samples"] = len(l2_deltas)
        return out


__all__ = ["DashboardQueryService"]
