"""Tests for evo.claim_checker —— 去伪存真·声明核验
声明提取 / 矛盾检测（否定记忆+实体重叠）/ 无记忆不可验证
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine", "evo"))
from claim_checker import ClaimChecker


def _make_checker():
    return ClaimChecker(top_k=3, threshold=0.75)


def test_extract_claims_paths_and_numbers():
    c = _make_checker()
    claims = c._extract_claims("已完成规则更新，文件位于 E:\\项目\\rules.json，共 3 条规则")
    joined = " | ".join(claims)
    assert any("rules.json" in cl for cl in claims)
    assert any("3" in cl or "条" in cl for cl in claims)


def test_extract_claims_empty():
    c = _make_checker()
    assert c._extract_claims("") == []
    assert c._extract_claims(None) == []


def test_contradiction_detected():
    c = _make_checker()
    conflict = c._check_contradiction(
        "文件存在 3 个",
        [{"text": "文件不存在 3 个", "score": 0.9}],
    )
    assert conflict is not None
    assert conflict["conflict"]


def test_contradiction_no_overlap():
    c = _make_checker()
    conflict = c._check_contradiction(
        "端口 8080 已开启",
        [{"text": "服务不存在 9090", "score": 0.95}],
    )
    assert conflict is None


def test_verify_output_no_text():
    c = _make_checker()
    r = c.verify_output("")
    assert r["total_claims"] == 0
    assert r["contradicted"] == 0


def test_verify_output_unverifiable_without_memory():
    c = _make_checker()
    r = c.verify_output("修改了 3 条规则，规则文件位于 E:\\项目\\rules.json")
    assert r["total_claims"] >= 1
    assert r["verdict"] == "UNVERIFIED"
