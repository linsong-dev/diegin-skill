# -*- coding: utf-8 -*-
"""
claim_checker.py - 去伪存真·实质验证（v3.5）
输出自洽性检验：提取输出中的可验证声明，与 Shalou 已知记忆交叉核对
言必有证 → 证必可验 → 验证为真（语义级验证，超越格式标记验证）
"""
import io, sys, os, re, json
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class ClaimChecker:
    """去伪存真·输出声明验证器"""

    def __init__(self, top_k: int = 5, threshold: float = 0.75):
        self.top_k = top_k
        self.threshold = threshold
        # 声明提取规则：包含明确断言动词/数字/路径/文件名的句子
        self._claim_patterns = [
            r"(?:已经|完成|成功|存在|不存在|是|包含|位于|大小|数量|数量为|耗时|用时|版本|修改了|创建了|删除了|修复了|安装了|卸载了)[^。\n！？]{2,80}",
            r"[A-Za-z]:[\\/][^\s,;。]{3,80}",           # Windows 路径
            r"(?:/[\w\-./]+){2,}",                        # Unix 路径
            r"\b\d+(?:\.\d+)?\s*(?:MB|GB|KB|ms|秒|分钟|小时|天|条|个|次|行|文件|规则)\b",
            r"(?:规则|文件|版本|端口|进程|服务|接口|函数|模块)\s*[:：]\s*[\w\-./]{2,60}",
        ]

    def _extract_claims(self, text: str) -> List[str]:
        """提取可验证声明"""
        if not text:
            return []
        claims = []
        seen = set()
        for pat in self._claim_patterns:
            for m in re.finditer(pat, text):
                c = m.group(0).strip()
                # 去重 + 长度过滤
                key = c[:40]
                if c not in seen and 4 <= len(c) <= 120:
                    seen.add(c)
                    claims.append(c)
        return claims[:10]  # 最多验证10条

    def _check_contradiction(self, claim: str, related: List[Dict]) -> Optional[Dict]:
        """与已知记忆交叉核对，返回矛盾证据或 None"""
        for r in related:
            mem_text = str(r.get("text", ""))[:200]
            score = float(r.get("score", 0) or 0)
            if score < self.threshold:
                continue
            # 提取记忆中的关键实体（数字、路径、规则ID）做矛盾检测
            claim_nums = set(re.findall(r"\d+(?:\.\d+)?", claim))
            mem_nums = set(re.findall(r"\d+(?:\.\d+)?", mem_text))
            # 如果记忆文本包含明确否定词而声明是肯定断言
            neg_in_mem = any(k in mem_text for k in ("不存在", "失败", "未", "没有", "no ", "not ", "failed", "missing"))
            pos_in_claim = any(k in claim for k in ("存在", "完成", "成功", "已", "是", "exists", "done", "ok"))
            if pos_in_claim and neg_in_mem and claim_nums & mem_nums:
                return {"memory": mem_text, "score": score, "conflict": "声明肯定 vs 记忆否定，且数字实体重叠"}
        return None

    def verify_output(self, output_text: str, context: Dict = None) -> Dict:
        """验证输出文本中的可验证声明"""
        result = {
            "principle": "去伪存真·实质验证",
            "verified_at": datetime.now().isoformat(),
            "total_claims": 0,
            "consistent": 0,
            "contradicted": 0,
            "unverifiable": 0,
            "details": [],
        }
        if not output_text:
            return result

        claims = self._extract_claims(output_text)
        result["total_claims"] = len(claims)

        # Shalou 检索
        try:
            from shalou.diegin_integration import memory_search
        except Exception:
            memory_search = None

        for claim in claims:
            entry = {"claim": claim, "status": "unverifiable", "evidence": []}
            if memory_search is None:
                result["unverifiable"] += 1
                entry["reason"] = "Shalou 不可用"
                result["details"].append(entry)
                continue
            try:
                related = memory_search(claim, max_results=self.top_k) or []
            except Exception:
                related = []
            if not related:
                result["unverifiable"] += 1
                entry["reason"] = "无相关记忆"
                result["details"].append(entry)
                continue
            conflict = self._check_contradiction(claim, related)
            if conflict:
                result["contradicted"] += 1
                entry["status"] = "contradicted"
                entry["evidence"] = conflict
                entry["reason"] = f"与已知记忆矛盾 ({conflict['score']:.0%})"
            else:
                result["consistent"] += 1
                entry["status"] = "consistent"
                entry["evidence"] = [{"memory": str(r.get("text", ""))[:120], "score": float(r.get("score", 0) or 0)} for r in related[:2]]
            result["details"].append(entry)

        # 总体判定
        if result["contradicted"] > 0:
            result["verdict"] = "FAIL"
            result["message"] = f"发现 {result['contradicted']} 条声明与已知记忆矛盾，输出需修正"
        elif result["total_claims"] > 0 and result["consistent"] / result["total_claims"] >= 0.6:
            result["verdict"] = "PASS"
            result["message"] = "声明与已知记忆一致，通过实质验证"
        else:
            result["verdict"] = "UNVERIFIED"
            result["message"] = "多数声明无法验证（可能是新信息），记录但不阻断"

        # 归档验证记录
        try:
            from evidence_vault import get_vault
            get_vault().record(
                rule_id="_claim_checker",
                verdict="pass" if result["verdict"] == "PASS" else ("fail" if result["verdict"] == "FAIL" else "skip"),
                reason=f"claim_checker: {result['total_claims']}条声明, {result['contradicted']}条矛盾",
                source="claim_checker",
                context={"verdict": result["verdict"]},
            )
        except Exception:
            pass
        return result


_inst = None


def get_checker():
    global _inst
    if _inst is None:
        _inst = ClaimChecker()
    return _inst


if __name__ == "__main__":
    # CLI: python claim_checker.py "<output_text>"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    text = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    print(json.dumps(get_checker().verify_output(text), ensure_ascii=False, indent=2))
