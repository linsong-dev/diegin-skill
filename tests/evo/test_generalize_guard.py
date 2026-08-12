"""Tests for evo.main._is_pseudo_generalization —— 举一反三·语义阈值（定稿第四章）
余弦相似度≥0.7 判伪泛化（复制而非泛化），<0.7 放行
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from evo import main


class _FakeVectorizer:
    """可编程相似度向量器"""

    def __init__(self, sim):
        self._sim = sim

    def calc_similarity(self, a, b):
        return self._sim


def test_no_vectorizer_returns_none(monkeypatch):
    monkeypatch.setattr(main, "_get_vectorizer", lambda: None)
    assert main._is_pseudo_generalization("候选规则A", ["既有规则B"]) is None


def test_similar_above_threshold_is_pseudo(monkeypatch):
    monkeypatch.setattr(main, "_get_vectorizer", lambda: _FakeVectorizer(0.85))
    existing = "既有规则文本"
    hit = main._is_pseudo_generalization("候选规则文本", [existing])
    assert hit == existing  # ≥0.7 → 判伪泛化，返回相似源


def test_dissimilar_below_threshold_allowed(monkeypatch):
    monkeypatch.setattr(main, "_get_vectorizer", lambda: _FakeVectorizer(0.5))
    assert main._is_pseudo_generalization("候选规则文本", ["既有规则文本"]) is None  # <0.7 → 放行


def test_empty_candidate_allowed(monkeypatch):
    monkeypatch.setattr(main, "_get_vectorizer", lambda: _FakeVectorizer(0.99))
    assert main._is_pseudo_generalization("", ["既有"]) is None
