"""仓库 front-matter status ↔ 产品 DocStatus 映射与元数据往返（跨模块契约）。

覆盖三件事，都是「假打通」会立刻暴露的地方：
1. **全量导入不吃 400**：拿真实 `docs/` 里全部 md 跑 `import_from_repo`，一份都不许报错
   （映射前 277 份里 273 份会 400）；
2. **7 种权威度词全部映射正确**：authoritative/active/reference/proposed/superseded/
   archived/vendor 各自落到产品状态，并带上 `authority:<值>` tag；
3. **回写不丢字段**：`layer/concern/lifecycle` 在 import → export 往返后必须仍在
   （回归红线，防的就是 `MANAGED_FIELDS` 漏键导致静默抹掉仓库元数据）。

映射表只从 `docs/DOC-GOVERNANCE-POLICY.yaml` 读，因此这里也断言「改 policy 即生效」——
代码里另抄一份映射表会漂，而且漂了没人发现。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from odap.biz.knowledge.governance.services import frontmatter_bridge as bridge
from odap.biz.knowledge.governance.services.frontmatter import parse_document
from odap.common.api_errors import ApiError

REPO = Path(__file__).resolve().parents[6]
POLICY = REPO / "docs" / "DOC-GOVERNANCE-POLICY.yaml"
ALL_DOCS = sorted((REPO / "docs").rglob("*.md"))
AUTHORITY_WORDS = (
    "authoritative", "active", "reference", "proposed", "superseded", "archived", "vendor",
)
EXPECTED_PRODUCT_STATUS = {
    "authoritative": "published",
    "active": "published",
    "reference": "published",
    "proposed": "draft",
    "superseded": "superseded",
    "archived": "archived",
    "vendor": "published",
}


def _front_matter(path: Path) -> dict:
    try:
        data, _body = parse_document(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 无 front-matter 的 md 不参与本测试
        return {}
    return data


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _doc_with_status(word: str) -> Path:
    for path in ALL_DOCS:
        fm = _front_matter(path)
        if str(fm.get("status") or "").strip() == word:
            return path
    pytest.skip(f"真实仓库里没有 status={word} 的文档")


class TestPolicySourcing:
    def test_mapping_is_read_from_policy_file(self):
        """代码里的映射必须等于 policy 第八节的表，不允许另抄一份。"""
        policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        assert bridge.status_mapping() == policy["status_mapping_to_product"]
        assert bridge.authority_tag_prefix() == policy["authority_tag_prefix"]

    def test_mapping_follows_policy_change(self, tmp_path, monkeypatch):
        """改 policy → 映射立即生效（证明没有硬编码副本）。"""
        payload = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        payload["status_mapping_to_product"] = {"authoritative": "review", "active": "draft"}
        override = tmp_path / "policy.yaml"
        override.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
        monkeypatch.setenv(bridge.POLICY_ENV, str(override))

        assert bridge.status_mapping()["authoritative"] == "review"
        status, tag = bridge.to_product_status("authoritative")
        assert status.value == "review"
        assert tag == "authority:authoritative"

    def test_every_status_word_in_corpus_is_mappable(self):
        """真实语料里出现的每个 status 都要能映射，否则导入必然 400。"""
        mapping = bridge.status_mapping()
        seen = {
            str(_front_matter(path).get("status") or "").strip()
            for path in ALL_DOCS
        }
        unmapped = {word for word in seen if word and word not in mapping}
        assert not unmapped, f"语料里有未映射的 status：{sorted(unmapped)}"

    def test_unknown_status_reports_value_allowed_and_policy(self):
        with pytest.raises(ApiError) as excinfo:
            bridge.to_product_status("已归档", source_path="docs/02-architecture/x.md")
        error = excinfo.value
        assert error.error_code == "DOC_STATUS_INVALID"
        assert error.status_code == 400
        assert "已归档" in error.message
        assert str(POLICY) in error.message  # 指向 policy，方便改表
        assert set(error.detail["allowed"]) >= set(AUTHORITY_WORDS)

    def test_product_vocabulary_passes_through_without_tag(self):
        """历史文档用产品词表写 status，不造 authority tag（否则会污染 tag）。"""
        status, tag = bridge.to_product_status("published")
        assert status.value == "published"
        assert tag is None

    def test_empty_status_defaults_to_draft(self):
        status, tag = bridge.to_product_status("")
        assert status.value == "draft" and tag is None


class TestRealRepoImport:
    def test_all_repo_docs_import_without_400(self, sync_service):
        """真实 docs/ 全量导入：一份都不许 400（映射前 273/277 会失败）。"""
        failures = []
        for path in ALL_DOCS:
            try:
                sync_service.import_from_repo(_rel(path), actor_id="u-importer")
            except ApiError as exc:  # noqa: PERF203 - 需要逐份归因
                failures.append((_rel(path), exc.error_code, exc.message[:80]))
        assert not failures, f"{len(failures)} 份导入失败，示例：{failures[:3]}"
        assert len(ALL_DOCS) >= 277

        governed = sync_service.docs.list_all()
        assert len(governed) == len(ALL_DOCS)

    def test_each_authority_word_maps_with_tag(self, sync_service):
        """7 种权威度词逐一验证：产品状态正确 + authority tag 正确。"""
        for word in AUTHORITY_WORDS:
            path = _doc_with_status(word)
            result = sync_service.import_from_repo(_rel(path), actor_id="u-importer")
            assert result["status"] == EXPECTED_PRODUCT_STATUS[word], word
            assert f"authority:{word}" in result["tags"], (word, result["tags"])

    def test_layer_concern_lifecycle_carried_as_tags(self, sync_service):
        """仓库侧三元元数据不能丢弃，导入时以 tag 承载（回写时还原）。"""
        path = _doc_with_status("active")
        fm = _front_matter(path)
        result = sync_service.import_from_repo(_rel(path), actor_id="u-importer")
        sidecar = bridge.read_sidecar(result["tags"])
        for key in bridge.SIDECAR_KEYS:
            expected = str(fm.get(key) or "").strip()
            if expected:
                assert sidecar.get(key) == expected, (key, sidecar, expected)


class TestRoundTrip:
    """import → export 往返：layer/concern/lifecycle 与权威度词必须原样回来。"""

    def _one_adr(self) -> Path:
        for path in ALL_DOCS:
            fm = _front_matter(path)
            if fm.get("layer") == "L7" and fm.get("lifecycle") == "frozen":
                return path
        pytest.skip("仓库里没有 L7 + lifecycle=frozen 的文档")

    def test_roundtrip_preserves_governance_keys(self, sync_service, repo_root):
        source = self._one_adr()
        original = _front_matter(source)
        target_rel = _rel(source)
        target = repo_root / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        imported = sync_service.import_from_repo(target_rel, actor_id="u-importer")
        sync_service.export_to_repo(
            entry_id=imported["id"], target_path=target_rel,
            approval_id="apr-roundtrip", user={"sub": "u-editor", "roles": ["editor"]},
        )

        written, _body = parse_document(target.read_text(encoding="utf-8"))
        for key in ("layer", "concern", "lifecycle"):
            assert written.get(key) == original.get(key), (key, written.get(key))
        assert written.get("status") == original.get("status")
        assert "authority:" not in str(written.get("tags") or "")

    def test_export_of_product_only_entry_still_has_layer(self, sync_service,
                                                          entry_service, repo_root):
        """产品侧自建条目（没有 sidecar tag）回写时按 policy layers 补出 layer，
        否则写出的文档过不了审计（layer 是必需字段）。"""
        entry = entry_service.create(
            title="退货率口径补充说明", content="退货率按签收日期归集。\n", owner="u-owner",
        )
        published = entry_service.publish(entry.id, actor_id="u-owner")
        target = "docs/02-architecture/return-rate-note.md"
        sync_service.export_to_repo(
            entry_id=published.id, target_path=target,
            approval_id="apr-export", user={"sub": "u-editor", "roles": ["editor"]},
        )
        written, _body = parse_document((repo_root / target).read_text(encoding="utf-8"))
        assert written["layer"] == "L2"
        assert written["concern"] == "architecture"
        assert written["status"] in set(AUTHORITY_WORDS) | {"draft", "review", "published"}
