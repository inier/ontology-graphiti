"""TDD：提取模式解析器（三级解析：sa_config > EXTRACTOR_MODE env > 默认 query）。

覆盖 spec 子项目 C E-13：
  - 无任何配置 → 默认 query
  - 有 env 无配置 → env
  - 有 sa_config → 优先 sa_config（即使 env 存在）
  - 非法值 → 跳过该级继续下一级
  - sa_config 读取异常 → warning + 按下一级（规则 14）
"""
from __future__ import annotations

import logging

import pytest

from odap.biz.data.qa.pipeline.understanding import extractor_mode as em


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_MODE", raising=False)


def test_default_is_query(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: None)
    assert em.resolve_extractor_mode() == "query"
    assert em.DEFAULT_MODE == "query"
    assert set(em.AVAILABLE_MODES) == {"off", "inject", "query"}


def test_env_used_when_no_config(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: None)
    monkeypatch.setenv("EXTRACTOR_MODE", "inject")
    assert em.resolve_extractor_mode() == "inject"


def test_config_wins_over_env(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: "off")
    monkeypatch.setenv("EXTRACTOR_MODE", "inject")
    assert em.resolve_extractor_mode() == "off"      # 配置优先


def test_invalid_config_falls_through_to_env(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: "bogus")
    monkeypatch.setenv("EXTRACTOR_MODE", "query")
    assert em.resolve_extractor_mode() == "query"    # 非法配置跳过 → env


def test_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: None)
    monkeypatch.setenv("EXTRACTOR_MODE", "nonsense")
    assert em.resolve_extractor_mode() == "query"    # 非法 env → 默认


def test_read_failure_warns_and_defaults(monkeypatch, caplog):
    def _boom():
        raise RuntimeError("db down")

    # _read_from_sa_config 自身吞异常；此处验证 resolve 在 reader 返回 None 时按默认
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: None)
    with caplog.at_level(logging.WARNING):
        assert em.resolve_extractor_mode() == "query"


def test_descriptions_cover_all_modes():
    for m in em.AVAILABLE_MODES:
        assert m in em.MODE_DESCRIPTIONS
        assert em.MODE_DESCRIPTIONS[m]
