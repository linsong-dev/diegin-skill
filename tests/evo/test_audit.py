# Tests for evo.main.audit_strike_summary —— audit 标准审核口径回归测试
#
# v3.8.3 回归：
# - audit「一二不过三」与 principle_health 同口径：fix_status=verified 视为
#   已修复闭环，不再误报「已达阈值」（修复前 count>=3 恒红）。
# - 同时修复 audit「去伪存真」证据链读取：统一走 get_vault（原读 var/state
#   错误路径恒显 0 条）。
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'engine'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'engine', 'evo'))

import evo.main as main


def test_all_verified_no_pending():
    # 全部 verified → 无待干预（修复前误报红）
    s = main.audit_strike_summary({
        'command_failure': {'count': 3, 'fix_status': 'verified'},
        'tool_error_Bash': {'count': 3, 'fix_status': 'verified'},
        'image_url': {'count': 1, 'fix_status': 'verified'},
    })
    assert s['total'] == 3
    assert len(s['verified']) == 3
    assert s['pending_high'] == []
    assert s['pending_warn'] == []
    assert s['pending_ok'] == []


def test_mixed_verified_and_pending():
    # verified + 未修复 → 仅未修复按级别分类
    s = main.audit_strike_summary({
        'command_failure': {'count': 3, 'fix_status': 'verified'},
        'new_critical': {'count': 3},
        'mid': {'count': 2},
        'low': {'count': 1},
    })
    assert len(s['verified']) == 1
    assert [x['error_type'] for x in s['pending_high']] == ['new_critical']
    assert [x['error_type'] for x in s['pending_warn']] == ['mid']
    assert [x['error_type'] for x in s['pending_ok']] == ['low']


def test_missing_fix_status_treated_pending():
    # 无 fix_status 字段 → 视为未修复待干预
    s = main.audit_strike_summary({'x': {'count': 3}})
    assert len(s['pending_high']) == 1
    assert s['verified'] == []


def test_empty_and_malformed():
    # 空库/非 dict 条目不崩溃
    assert main.audit_strike_summary({})['total'] == 0
    assert main.audit_strike_summary({'bad': 'string', 'none': None})['total'] == 0
