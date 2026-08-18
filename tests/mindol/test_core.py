"""Tests for mindol core modules"""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "engine"))

from mindol.vectorizer import SimpleVectorizer
from mindol.models import MemoryUnit, MemorySpace, SemanticRelation
from mindol.core import Mindol
from mindol.codex_adapter import CodexMemoryAdapter
from mindol.diegin_integration import memory_search, memory_archive, get_memory_stats, close_memory

DB = os.path.join(os.path.dirname(__file__), "_test_db")

def clean():
    for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
        p = os.path.join(DB, f)
        if os.path.exists(p): os.remove(p)

def test_vectorizer():
    v = SimpleVectorizer()
    v1 = v.embed("hello world")
    v2 = v.embed("hello world again")
    v3 = v.embed("")
    assert v1.shape == (256,)
    assert v.embedding_dim() == 256
    assert abs(np.linalg.norm(v1) - 1.0) < 0.001
    assert np.linalg.norm(v3) == 0
    assert float(v1 @ v2) > 0.5
    print("  [PASS] vectorizer")

def test_models():
    mu = MemoryUnit(uid="t1", text="test", source="chat")
    assert mu.to_dict()["uid"] == "t1"
    ms = MemorySpace(name="test")
    assert ms.size == 0
    sr = SemanticRelation("a", "b", "similar", 0.8)
    assert sr.weight == 0.8
    print("  [PASS] models")

def test_core():
    clean()
    core = Mindol(storage_path=DB, persist=False)
    assert len(core.space_stats()) == 8
    assert "codex" in core.space_stats()
    assert "state" in core.space_stats()
    u1 = core.add_unit(text="test data 123", source="chat", uid="t1", space="codex")
    assert core.get_unit("t1") is not None
    r = core.retrieve("test", top_k=3)
    assert len(r) >= 1
    core.close()
    print("  [PASS] core lifecycle")

def test_persistence():
    clean()
    core = Mindol(storage_path=DB, persist=True)
    core.add_unit(text="persist test", source="chat", uid="p1", space="codex")
    core.save(); core.close()
    core2 = Mindol(storage_path=DB, persist=True)
    assert core2.get_unit("p1") is not None
    core2.close(); clean()
    print("  [PASS] persistence")

def test_adapter():
    clean()
    mem = CodexMemoryAdapter(storage_path=DB)
    uid = mem.save_context("adapter test content", source="chat", space="codex")
    assert uid is not None
    r = mem.search("test", top_k=5)
    assert len(r) >= 1
    ok = mem.archive("test_key", "archive content")
    assert ok == True
    mem.close(); clean()
    print("  [PASS] codex adapter")

def test_integration():
    clean()
    ok = memory_archive("rule_001", "integration test", {"source": "test"})
    assert ok == True
    r = memory_search("integration", max_results=3)
    assert len(r) >= 1
    stats = get_memory_stats()
    assert isinstance(stats, dict)
    close_memory()
    import shutil
    shutil.rmtree(os.path.join(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")), "mindol"), ignore_errors=True)
    print("  [PASS] mindol integration")


def test_state_dynamics_v37():
    """v3.7 最小步：四字段 + 强度权重 + 休眠过滤 + 老库迁移"""
    import sqlite3, shutil
    clean()
    core = Mindol(storage_path=DB, persist=True)
    # 强度初始（importance 驱动）
    u1 = core.add_unit(text="high importance rec", source="chat", uid="s1", space="codex", metadata={"importance": 0.9})
    u2 = core.add_unit(text="normal rec", source="chat", uid="s2", space="codex")
    assert abs(u1.strength - 0.95) < 1e-6
    assert u2.strength == 1.0 and u2.status == "active"
    assert u1.access_count == 0 and u1.last_accessed > 0
    core.save(); core.close()
    # 重载保持
    core = Mindol(storage_path=DB, persist=True)
    assert abs(core.get_unit("s1").strength - 0.95) < 1e-6
    # 强度权重排序 + 使用痕迹
    core.add_unit(text="term zzzqqq high", source="chat", uid="s3", space="codex", metadata={"importance": 1.0})
    core.add_unit(text="term zzzqqq low", source="chat", uid="s4", space="codex", metadata={"importance": 0.1})
    r = core.retrieve("zzzqqq", top_k=3)
    assert len(r) >= 2
    assert r[0][0].uid == "s3"
    assert core.get_unit("s3").access_count == 1
    # 休眠过滤
    d = core.get_unit("s4"); d.status = "dormant"
    core._persist_unit(d, "codex"); core.save()
    r2 = core.retrieve("zzzqqq", top_k=5)
    assert all(u.uid != "s4" for u, _ in r2)
    # 提取即刷新（v3.7.1）：命中即 strength+0.05，上限对齐 1.0
    core.add_unit(text="term boost_kw_rf 低强度", source="chat", uid="s5", space="codex", metadata={"importance": 0.2})
    assert abs(core.get_unit("s5").strength - 0.6) < 1e-6
    core.retrieve("boost_kw_rf", top_k=3)
    assert abs(core.get_unit("s5").strength - 0.65) < 1e-6
    cap = core.get_unit("s5"); cap.strength = 0.98
    core._persist_unit(cap, "codex"); core.save()
    core.retrieve("boost_kw_rf", top_k=3)
    assert abs(core.get_unit("s5").strength - 1.0) < 1e-6
    core.close(); clean()
    # 老库迁移
    legacy_dir = os.path.join(os.path.dirname(__file__), "_legacy_db")
    if os.path.exists(legacy_dir): shutil.rmtree(legacy_dir, ignore_errors=True)
    os.makedirs(legacy_dir, exist_ok=True)
    c = sqlite3.connect(os.path.join(legacy_dir, "memory.db"))
    c.execute("CREATE TABLE memory_units (uid TEXT PRIMARY KEY, space TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, path TEXT DEFAULT '', metadata TEXT DEFAULT '{}', timestamp REAL DEFAULT 0, embedding BLOB)")
    c.execute("INSERT INTO memory_units (uid, space, text, source, timestamp) VALUES ('old1','codex','legacy rec','chat',1000.0)")
    c.execute("CREATE TABLE relations (source_uid TEXT NOT NULL, target_uid TEXT NOT NULL, relation_type TEXT NOT NULL, weight REAL DEFAULT 1.0, PRIMARY KEY (source_uid, target_uid, relation_type))")
    c.commit(); c.close()
    core = Mindol(storage_path=legacy_dir, persist=True)
    old = core.get_unit("old1")
    assert old is not None and old.strength == 1.0 and old.status == "active" and old.last_accessed == 1000.0
    core.close()
    shutil.rmtree(legacy_dir, ignore_errors=True)
    print("  [PASS] state dynamics v3.7")

if __name__ == "__main__":
    print("=== Mindol Test Suite ===\n")
    for fn in [test_vectorizer, test_models, test_core, test_persistence, test_adapter, test_integration, test_state_dynamics_v37]:
        fn()
    print("\n=== ALL TESTS PASSED ===")
