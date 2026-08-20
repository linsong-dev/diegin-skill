import sys, json, os, datetime
from typing import Dict, List, Optional

class EvidenceVault:
    """去伪存真·证据库 - 追踪每条规则的证据链"""

    def __init__(self):
        self._log_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            os.path.pardir,
            "var", "state", "evidence_trail.json"
        )
        self._trail = []
        self._load()
        # P0 #6: 归因正确率回溯
        self._attribution_log = []        # 归因追踪
        self._attribution_max = 200       # 最多保留200条

    def _load(self):
        if os.path.exists(self._log_path):
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._trail = data if isinstance(data, list) else []
            except Exception:
                self._trail = []

    def _save(self):
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        with open(self._log_path, "w", encoding="utf-8") as f:
            json.dump(self._trail[-500:], f, ensure_ascii=False, indent=2)

    def _is_valid_evidence(self, rule_id: str, verdict: str, reason: str, source: str) -> bool:
        """去伪存真·证据有效性门（v3.8.1）：
        拒绝无实质内容的 pass 记录（post_tool 钩子把工具名当 rule_id 写空壳 reason 的污染源）。
        保留：fail/block 真实失败、quarterly_falsification 内置审计、skip 审计、
        引用真实规则/模式 id 且有实质 reason 的 pass。
        """
        if verdict in ("fail", "block", "pending"):
            return True  # 失败/阻断证据必须保留（即使 rule_id 是工具名）
        if source == "quarterly_falsification":
            return True  # 内置季度证伪审计
        r = (reason or "").strip()
        _r_compact = r.replace(" ", "").replace(chr(0x3000), "")
        if len(_r_compact) < 6:
            return False  # 空壳 reason
        if r.startswith("tool=") and "exit=" in r:
            # tool=Bash exit=0 纯工具名模板（无实质内容）→ 拒绝
            return False
        if verdict in ("pass", "allow"):
            # pass 必须引用真实规则/模式 id（证必可验）
            try:
                from evo.main import _get_engine
                _eng = _get_engine()
                if _eng.get_interception_by_id(rule_id) or _eng.get_pattern_by_id(rule_id):
                    return True
            except Exception:
                pass
            return False
        return True  # skip 等其他审计记录

    def record(self, rule_id: str, verdict: str, reason: str,
               source: str = "auto", context: dict = None):
        """记录一条证据判定（v3.8.1 前置有效性门，拒绝污染）"""
        if not self._is_valid_evidence(rule_id, verdict, reason, source):
            return {
                "ts": datetime.datetime.now().isoformat(),
                "rule_id": rule_id,
                "verdict": verdict,
                "reason": reason[:200],
                "source": source,
                "rejected": True,
                "reject_reason": "evidence_validity_gate: 空壳 pass 或非真实规则 id 记录被拒绝",
            }
        # 定稿第五章：谱系距离衰减——泛化规则验证 pass 时按推导链级数衰减证据权重，
        # 支撑度<0.5 强制判定「暂存」（等待独立实证）
        try:
            _v = self.verify_with_genealogy(rule_id, verdict)
            if _v != verdict:
                verdict = _v
        except Exception:
            pass
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "rule_id": rule_id,
            "verdict": verdict,  # pass | fail | skip | pending
            "reason": reason[:200],
            "source": source,
            "context": context or {}
        }
        # 定稿第五章：暂存区条目默认保留期 50轮/7天（先到者），超时未验证自动淘汰；
        # 保留期内获得外部新证据可重置计时器一次
        if verdict == "pending":
            entry["stage"] = "staging"
            entry["staging_created_at"] = entry["ts"]
            entry["staging_round"] = self._bump_round()
            entry["reset_count"] = 0
            entry["expired"] = False
        else:
            # 非暂存判定（pass/fail/skip）= 该规则获得外部新证据 → 重置暂存计时器一次
            try:
                self.reset_staging_timer(rule_id)
            except Exception:
                pass
        self._trail.append(entry)
        self._save()
        return entry

    def _bump_round(self) -> int:
        """暂存区轮次计数（近似操作轮，用于 50 轮淘汰）"""
        try:
            _rp = os.path.join(os.path.dirname(self._log_path), "staging_round.json")
            _r = 0
            if os.path.exists(_rp):
                with open(_rp, "r", encoding="utf-8") as f:
                    _r = int(json.load(f).get("round", 0) or 0)
            _r += 1
            os.makedirs(os.path.dirname(_rp), exist_ok=True)
            with open(_rp, "w", encoding="utf-8") as f:
                json.dump({"round": _r}, f)
            return _r
        except Exception:
            return 0

    def staging_ttl_check(self, max_rounds: int = 50, max_days: int = 7) -> int:
        """定稿第五章：暂存区 50轮/7天（先到者）超时自动淘汰"""
        now = datetime.datetime.now()
        _round = self._bump_round()
        expired = 0
        for e in self._trail:
            if e.get("verdict") != "pending" or e.get("expired"):
                continue
            _expired = False
            try:
                _created = datetime.datetime.fromisoformat(e.get("staging_created_at", e.get("ts", "")))
                if (now - _created).total_seconds() > max_days * 86400:
                    _expired = True
            except Exception:
                pass
            _sr = int(e.get("staging_round", 0) or 0)
            if not _expired and _sr and (_round - _sr) >= max_rounds:
                _expired = True
            if _expired:
                e["expired"] = True
                e["expired_at"] = now.isoformat()
                expired += 1
        if expired:
            self._save()
        return expired

    def reset_staging_timer(self, rule_id: str) -> bool:
        """定稿第五章：保留期内获得外部新证据 → 重置计时器一次（仅一次）"""
        for e in reversed(self._trail):
            if e.get("rule_id") == rule_id and e.get("verdict") == "pending" and not e.get("expired"):
                if int(e.get("reset_count", 0) or 0) >= 1:
                    return False
                e["reset_count"] = int(e.get("reset_count", 0) or 0) + 1
                e["staging_created_at"] = datetime.datetime.now().isoformat()
                e["staging_round"] = self._bump_round()
                self._save()
                return True
        return False

    def generalization_depth(self, rule_id: str, engine=None) -> int:
        """去伪存真·谱系距离（定稿第五章）：泛化推导链级数
        0=非泛化；1=直接泛化产物（generalize_from_patterns/cross_domain）；
        2=二级泛化（源本身是泛化产物）"""
        depth = 0
        try:
            if engine is None:
                from evo.main import _get_engine
                engine = _get_engine()
            if engine is None:
                return 0
            r = engine.get_interception_by_id(rule_id) or engine.get_pattern_by_id(rule_id)
            if r is None:
                return 0
            src = str(getattr(r, "source_review", "") or "")
            rid = str(getattr(r, "id", "") or "")
            is_gen = ("generalize_from_patterns" in src or "跨域" in src or "cross_domain" in src
                      or rid.startswith("xdomain_") or rid.startswith("pat_rule_"))
            if not is_gen:
                return 0
            depth = 1
            _src_id = src.split(":")[-1].strip() if ":" in src else ""
            if _src_id:
                _src_r = engine.get_interception_by_id(_src_id) or engine.get_pattern_by_id(_src_id)
                if _src_r is not None:
                    _src_src = str(getattr(_src_r, "source_review", "") or "")
                    if "generalize" in _src_src or "跨域" in _src_src:
                        depth = 2
        except Exception:
            depth = 0
        return depth

    def verify_with_genealogy(self, rule_id: str, raw_verdict: str, engine=None) -> str:
        """谱系距离衰减（定稿第五章）：泛化每+1级证据权重×0.8；
        衰减后支撑度<0.5 → 强制判定「暂存」（等待独立实证）"""
        if raw_verdict != "pass":
            return raw_verdict
        depth = self.generalization_depth(rule_id, engine=engine)
        if depth <= 0:
            return raw_verdict
        weight = 0.8 ** depth
        trail = [e for e in self._trail if e.get("rule_id") == rule_id]
        passes = sum(1 for e in trail if e.get("verdict") == "pass")
        total = sum(1 for e in trail if e.get("verdict") in ("pass", "fail"))
        if total == 0:
            return "pending"  # 无历史对比证据 → 支撑度不足 → 暂存
        support = (passes * weight) / total
        return raw_verdict if support >= 0.5 else "pending"

    def get_recent(self, limit: int = 20) -> List[Dict]:
        return self._trail[-limit:]

    def get_stats(self) -> Dict:
        total = len(self._trail)
        verdicts = {}
        for e in self._trail:
            v = e.get("verdict", "unknown")
            verdicts[v] = verdicts.get(v, 0) + 1
        return {
            "principle": "去伪存真·证据库",
            "total_verdicts": total,
            "by_verdict": verdicts,
            "recent": self._trail[-5:] if self._trail else []
        }

    def classify_failure(self, error_type: str = "", detail: str = "") -> str:
        """归类失败类型: internal | external | uncertain"""
        ex_keywords = [
            "network","timeout","connection","refused","permission",
            "rate limit","not found","no such file","disk full",
            "too many open","authentication","unauthorized",
            "429","502","503","econnrefused","etimedout",
            "git clone","git fetch","pip install","npm install",
        ]
        in_keywords = [
            "encoding","write error","syntax","compile",
            "indentation","typeerror","valueerror","keyerror",
            "logic","import","nameerror","attributeerror",
        ]
        dl = (detail or "").lower()
        el = (error_type or "").lower()
        for kw in ex_keywords:
            if kw in el or kw in dl:
                return "external"
        for kw in in_keywords:
            if kw in el or kw in dl:
                return "internal"
        return "uncertain"

    def route_verdict(self, rule_id: str, verdict: str, reason: str,
                      source: str = "auto", context: dict = None) -> dict:
        """去伪存真·路由: 记录证据并将裁决路由到对应原则"""
        entry = self.record(rule_id, verdict, reason, source, context)

        # P0 #6: 记录归因
        if verdict in ("fail", "block"):
            _error_type = (context or {}).get("error_type", rule_id)
            _detail = (context or {}).get("detail", reason)
            _classified = self.classify_failure(_error_type, _detail)
            self._attribution_log.append({
                "ts": entry["ts"],
                "rule_id": rule_id,
                "verdict": verdict,
                "classified_as": _classified,
                "proven_correct": None,
                "error_type": str(_error_type)[:40],
                "detail": str(_detail)[:80],
            })
            if len(self._attribution_log) > self._attribution_max:
                self._attribution_log = self._attribution_log[-self._attribution_max:]

        
        # 提取error_type用于分类
        error_type = (context or {}).get("error_type", rule_id)
        detail = (context or {}).get("detail", reason)
        
        failure_type = self.classify_failure(error_type, detail)
        
        routing = {
            "verdict": verdict,
            "failure_type": failure_type,
            "entry_ts": entry["ts"],
            "rule_id": rule_id,
        }
        
        if verdict in ("fail", "block"):
            if failure_type == "internal":
                routing["route_to"] = "shousan"
                routing["route_reason"] = "内部惯性错误 → 路由到守三做复盘改进"
            elif failure_type == "external":
                routing["route_to"] = "huanjvlu"
                routing["route_reason"] = "外部环境错误 → 路由到缓急律做策略调整"
            else:
                routing["route_to"] = "staging"
                routing["route_reason"] = "原因不确定 → 暂存到staging等待更多数据"
        elif verdict in ("pass", "allow"):
            routing["route_to"] = "gongqi"
            routing["route_reason"] = "通过验证 → 路由到攻七强化成功模式"
        else:
            routing["route_to"] = "monitor"
            routing["route_reason"] = "其他裁决 → 监控跟踪"
        
        print(f"[EVIDENCE_ROUTE] {verdict} | {failure_type} | -> {routing['route_to']} | {reason[:40]}")
        return routing


    def run_quarterly_falsification(self) -> dict:
        """去伪存真·季度证伪: 扫描反例与失效场景
        若连续三次遭遇同一失效，则触发原则修订建议。
        依据元原则: '每季度对所有元原则进行一次证伪测试'
        """
        from collections import Counter
        
        now = datetime.datetime.now()
        
        # 按 quarter key 分组 (YYYY-Qn)
        quarter_key = f"{now.year}-Q{(now.month - 1) // 3 + 1}"
        
        # 扫描最近一个季度的所有 fail/block 裁决
        quarter_start = now - datetime.timedelta(days=90)
        quarter_entries = [
            e for e in self._trail
            if e.get('verdict') in ('fail', 'block')
            and e.get('ts', '')
        ]
        # 过滤本季度内的
        recent_fails = []
        for e in quarter_entries:
            try:
                ts = datetime.datetime.fromisoformat(e['ts'])
                if ts >= quarter_start:
                    recent_fails.append(e)
            except Exception:
                pass
        
        # 统计失败模式
        patterns = Counter()
        rule_fails = Counter()
        for e in recent_fails:
            rid = e.get('rule_id', 'unknown')
            reason = e.get('reason', '')
            patterns[reason[:60]] += 1
            rule_fails[rid] += 1
        
        # 检测连续三次同一失效
        repeated_failures = []
        for pattern, count in patterns.most_common(10):
            if count >= 3:
                repeated_failures.append({
                    'pattern': pattern,
                    'count': count,
                    'severity': 'high' if count >= 5 else 'medium',
                })
        
        # 检测规则级别重复失效
        repeated_rules = []
        for rid, count in rule_fails.most_common(10):
            if count >= 3:
                repeated_rules.append({
                    'rule_id': rid,
                    'count': count,
                })
        
        result = {
            'quarter': quarter_key,
            'scanned_entries': len(recent_fails),
            'unique_patterns': len(patterns),
            'repeated_failures': repeated_failures,
            'repeated_rules': repeated_rules,
            'needs_revision': len(repeated_failures) > 0 or len(repeated_rules) > 0,
        }
        
        # 记录证伪日志
        self.record(
            rule_id='_quarterly_falsification',
            verdict='review' if result['needs_revision'] else 'pass',
            reason=f"季度证伪: Q={quarter_key}, 扫描{len(recent_fails)}条, "
                   f"重复模式{len(repeated_failures)}个, 重复规则{len(repeated_rules)}条",
            source='quarterly_falsification',
            context=result
        )
        
        if repeated_failures:
            print(f"[FALSIFICATION] 季度证伪({quarter_key}): 发现 {len(repeated_failures)} 个重复失效模式")
            for rf in repeated_failures[:3]:
                print(f"  [REPEATED] {rf['pattern'][:50]} (x{rf['count']})")
        if repeated_rules:
            print(f"[FALSIFICATION] 重复失效规则: {len(repeated_rules)} 条")
            for rr in repeated_rules[:3]:
                print(f"  [RULE] {rr['rule_id']} (x{rr['count']})")
        if not result['needs_revision']:
            print(f"[FALSIFICATION] 季度证伪({quarter_key}): 无重复失效，系统健康")
        
        return result



    def get_recent_attributions(self, limit=10):
        return self._attribution_log[-limit:]

    def verify_attribution(self, rule_id="", max_check=20):
        import datetime as _dt
        now = _dt.datetime.now()
        recent = [a for a in self._attribution_log[-max_check:] if a["proven_correct"] is None]
        misattributed = []
        verified = []
        groups = {}
        for a in recent:
            et = a.get("error_type", "")
            if et:
                if et not in groups:
                    groups[et] = []
                groups[et].append(a)
        for et, entries in groups.items():
            internal_count = sum(1 for e in entries if e.get("classified_as") == "internal")
            external_count = sum(1 for e in entries if e.get("classified_as") == "external")
            total = len(entries)
            if total >= 3:
                if internal_count > 0 and external_count > internal_count:
                    for e in entries:
                        if e["classified_as"] == "internal":
                            e["proven_correct"] = False
                            e["proven_at"] = now.isoformat()
                            e["proven_reason"] = "同类多数归因为external"
                            misattributed.append(e)
                elif internal_count >= external_count and internal_count >= 2:
                    for e in entries:
                        if e["proven_correct"] is None:
                            e["proven_correct"] = True
                            e["proven_at"] = now.isoformat()
                            e["proven_reason"] = "同类归因一致"
                            verified.append(e)
        result = {
            "checked": len(recent),
            "verified": len(verified),
            "misattributed": len(misattributed),
            "attribution_count": len(self._attribution_log),
            "suggestions": []
        }
        if misattributed:
            affected_rules = set(e.get("rule_id", "") for e in misattributed)
            for rid in affected_rules:
                result["suggestions"].append(
                    "归因重审: " + rid + " 被判定为internal但同类事件多为external"
                )
        return result


    def explain_last(self, n: int = 1) -> dict:
        """P0 #3: 裁决追溯 - 输出最近n次裁决的完整推理链"""
        if not self._trail:
            return {"status": "empty", "message": "尚无裁决记录"}
        
        recent = self._trail[-n:]
        result = {
            "status": "ok",
            "total_trail": len(self._trail),
            "explanations": []
        }
        
        for entry in reversed(recent):
            rule_id = entry.get("rule_id", "?")
            verdict = entry.get("verdict", "?")
            reason = entry.get("reason", "?")
            source = entry.get("source", "?")
            ts = entry.get("ts", "?")
            ctx = entry.get("context", {}) or {}
            
            # 分类原因
            classification = "未知"
            if verdict in ("block", "fail"):
                if "internal" in reason:
                    classification = "归因: 内生惯性 → 路由守三"
                elif "external" in reason:
                    classification = "归因: 外生变量 → 路由缓急律"
                else:
                    classification = "归因: 不确定 → 暂存staging"
            elif verdict in ("pass", "allow"):
                classification = "通过验证 → 路由攻七"
            
            # 关联归因记录（如果有）
            attribution_info = None
            for a in self._attribution_log:
                if a.get("rule_id") == rule_id and a.get("ts","").startswith(ts[:19]):
                    attribution_info = {
                        "classified_as": a.get("classified_as"),
                        "proven_correct": a.get("proven_correct"),
                    }
                    break
            
            exp = {
                "ts": ts,
                "rule_id": rule_id,
                "verdict": verdict,
                "reason": reason[:100],
                "source": source,
                "classification": classification,
                "attribution": attribution_info,
            }
            result["explanations"].append(exp)
        
        return result


_inst = None

def get_vault():
    global _inst
    if _inst is None:
        _inst = EvidenceVault()
    return _inst
