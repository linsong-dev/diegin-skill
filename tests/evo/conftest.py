"""Pytest 共享配置：隔离 CODEX_HOME，防止测试污染真实 Mindol 记忆库。
引擎 v3.6+ 以 Mindol 为权威存储（RuleEngine.__init__ → _init_mindol 读取
CODEX_HOME/mindol/memory.db）。若会话内共享同一 CODEX_HOME，测试间会通过
Mindol 数据泄漏（JSON 从 Mindol 重建），因此每个测试使用独立临时目录，结束即清理。
同时豁免生产级写保护（MIN_RULES 最小条数门槛），测试小数据集可正常写入。

注意：测试文件混用 `from rule_engine import` 与 `from evo.rule_engine import`
两种导入路径，会加载同一文件的多个模块副本，因此补丁需覆盖 sys.modules 中
所有 RuleEngine 类。"""
import gc
import os
import shutil
import sys
import tempfile
import time

import pytest

_ENGINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)
_EVO_DIR = os.path.join(_ENGINE_DIR, "evo")
if _EVO_DIR not in sys.path:
    sys.path.insert(0, _EVO_DIR)

_TEST_MIN_RULES = {"interception_rules.json": 0, "success_patterns.json": 0}


def _patch_all_rule_engines() -> int:
    """对所有已加载的 RuleEngine 类注入测试态 MIN_RULES（覆盖双模块副本）。"""
    patched = 0
    for _name, _mod in list(sys.modules.items()):
        if _name not in ("rule_engine", "evo.rule_engine") and not _name.endswith(".rule_engine"):
            continue
        _cls = getattr(_mod, "RuleEngine", None)
        if _cls is None:
            continue
        _cur = _cls.__init__
        if getattr(_cur, "_dgen_test_wrapper", False):
            continue
        _orig = _cur

        def _mk_wrapper(_orig_init):
            def _wrapper(self, *args, **kwargs):
                _orig_init(self, *args, **kwargs)
                self.MIN_RULES = dict(_TEST_MIN_RULES)
            _wrapper._dgen_test_wrapper = True
            return _wrapper

        _cls.__init__ = _mk_wrapper(_orig)
        patched += 1
    return patched


@pytest.fixture(autouse=True)
def _isolated_codex_home():
    """每个测试独立的 CODEX_HOME：测试结束释放 SQLite 连接后清理临时目录。"""
    _patch_all_rule_engines()
    home = tempfile.mkdtemp(prefix="dgen_test_home_")
    os.environ["CODEX_HOME"] = home
    yield
    gc.collect()
    for _attempt in range(10):
        try:
            shutil.rmtree(home)
            break
        except PermissionError:
            time.sleep(0.3)