# 杩繘DGEN 寮曟搸鍏ュ彛(鍘讳吉瀛樼湡鐪熶吉闂? 瑷€蹇呮湁璇?>璇佸繀鍙獙->楠岃瘉涓虹湡)
"""
杩繘 路 DGEN 瀹炴垬璋冪敤鍏ュ彛
杩繘寮曟搸鍏ュ彛
"""
import sys, json, os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evo.main import (get_rules_for_task, arbitrate, full_review, record_behavior,
                      health_check, run_maintenance, dgen_archive, mempalace_search,
                      auto_sandwich, record_user_feedback, auto_sandwich_trigger, generalize_rule)


def pre_check(context: dict) -> dict:
    """浠诲姟鍓嶉妫€ - 妫€绱㈣鍒?+ 浠茶锛堝榻?AGENTS.md 瑁佸喅鏍煎紡锛?""
    rules = get_rules_for_task(context)
    result = arbitrate(rules["interceptions"], rules["patterns"])
    return {
        "matched_interceptions": len(rules["interceptions"]),
        "matched_patterns": len(rules["patterns"]),
        "decision": result["decision"],
        "display_line": result.get("display_line", ""),
        "reason": result["reason"],
        "winning_rule_id": result.get("winning_rule_id"),
    }
def post_review(task_context: dict, task_result: dict) -> dict:
    """浠诲姟鍚庡鐩?""
    result = full_review(task_context, task_result)
    return result


def system_health() -> dict:
    """绯荤粺鍋ュ悍搴?""
    return health_check()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("鐢ㄦ硶: python call_diegin.py <check|review|health|maintain|archive|search> [args...]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "check" or mode == "stdin":
        if len(sys.argv) > 2:
            raw = sys.argv[2]
        else:
            raw = sys.stdin.read().strip()
        ctx = json.loads(raw)
        result = pre_check(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "check_file":
        fp = sys.argv[2]
        with open(fp, 'r', encoding='utf-8-sig') as f:
            ctx = json.loads(f.read())  # Handle BOM
        result = pre_check(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "review":
        ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"task_id": "unknown"}
        result = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {"status": "completed"}
        result = post_review(ctx, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "health":
        import io
        old_out = sys.stdout
        sys.stdout = io.StringIO()
        result = system_health()
        sys.stdout = old_out
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "maintain":
        run_maintenance()

    elif mode == "archive":
        content = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        source = sys.argv[3] if len(sys.argv) > 3 else "dgen_cli"
        ok = dgen_archive(content, source)
        print(json.dumps({"ok": ok}, ensure_ascii=False))

    elif mode == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        results = mempalace_search(query)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif mode == "feedback":
        """鐢ㄦ埛鍙嶉涓夋€佹ā鍨?""
        rule_id = sys.argv[2] if len(sys.argv) > 2 else ""
        feedback = sys.argv[3] if len(sys.argv) > 3 else "silent"
        user_action = sys.argv[4] if len(sys.argv) > 4 else None
        result = record_user_feedback(rule_id, feedback, user_action)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "sandwich":
        """瀹堜笁鏀讳竷澶嶇洏锛堣嚜鍔ㄩ挬瀛愮増锛夛細python call_diegin.py sandwich <task_type> '<pos_json>' '<neg_json>'"""
        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"
        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
        result = auto_sandwich_trigger(task_type, positive, negative)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    
    elif mode == "suggest":
        """鏀讳竷锛氳繑鍥炰笌褰撳墠涓婁笅鏂囧尮閰嶇殑鎴愬姛妯″紡寤鸿锛堜緵 PreReply 閽╁瓙娉ㄥ叆锛?
        鐢ㄦ硶: python call_diegin.py suggest <context_text>
        鏁堟灉: AI 鍥炲鍓嶇湅鍒?杩欑鍦烘櫙鎺ㄨ崘鐢?xxx 宸ュ叿"
        """
        context_text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        from evo.main import _get_engine
        engine = _get_engine()
        patterns = engine.get_patterns(active_only=True)
        # 鎸夊叧閿瘝鍖归厤鎺掑簭
        keywords = context_text.lower().split()
        scored = []
        for p in patterns:
            scenario = (getattr(p, 'trigger_scenario', '') or '').lower()
            decision = (getattr(p, 'decision_logic', '') or '').lower()
            id_str = (getattr(p, 'id', '') or '').lower()
            score = sum(1 for kw in keywords if kw in scenario or kw in decision or kw in id_str)
            if score > 0:
                scored.append((score, {
                    "id": getattr(p, 'id', ''),
                    "scenario": getattr(p, 'trigger_scenario', ''),
                    "decision": getattr(p, 'decision_logic', ''),
                    "confidence": getattr(p, 'confidence', 0),
                }))
        scored.sort(key=lambda x: -x[0])
        suggestions = [s[1] for s in scored[:5]]
        result = {"suggestions": suggestions, "count": len(suggestions), "total_patterns": len(patterns)}
        print(json.dumps(result, ensure_ascii=False, indent=2))




    elif mode == "record_success":
        """鏀讳竷锛氳褰曚竴娆℃垚鍔熺殑宸ュ叿璋冪敤锛堢畝鍖栫増锛岃嚜鍔ㄦ彁鍙栨垚鍔熸ā寮忥級
        鐢ㄦ硶: python call_diegin.py record_success <tool_name>
        """
        tool_name = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        from evo.main import auto_sandwich_trigger
        result = auto_sandwich_trigger(f"tool_{tool_name.replace('.','_')}", positive=[tool_name], negative=[])
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "generalize":
        """涓句竴鍙嶄笁锛氫粠鍗曟潯鎴栨墍鏈夎鍒欐帹瀵艰法鍦烘櫙鍊欓€夎鍒?""
        rule_id = sys.argv[2] if len(sys.argv) > 2 else None
        result = generalize_rule(rule_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif mode == "sandwich_legacy":
        """瀹堜笁鏀讳竷澶嶇洏锛堟棫鐗堟棤閽╁瓙锛夛細python call_diegin.py sandwich_legacy <task_type> '<pos_json>' '<neg_json>'"""
        task_type = sys.argv[2] if len(sys.argv) > 2 else "general"
        positive = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
        negative = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
        result = auto_sandwich(positive, negative, task_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "dgen_check":
        """鍏ㄩ噺棰勬锛氭绱?浠茶+褰掓。鍒癕emPalace锛堜竴娆℃€у畬鏁磋皟鐢級"""
        ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = pre_check(ctx)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif mode == "activate":
        """
        缁熶竴鎺ュ叆鍏ュ彛锛氫换浣曞璇濅腑鎵ц姝ゅ懡浠ゅ疄鐜拌凯杩涙帴鍏ャ€?
        鏁堟灉锛氬姞杞借鍒欏簱 鈫?鍋ュ悍妫€鏌?鈫?杈撳嚭鎺ュ叆鎽樿
        """
        from evo.main import self_check
        from datetime import datetime
        
        # 鍔犺浇骞惰嚜妫€
        check_ok = self_check()
        import io
        _old_stdout, sys.stdout = sys.stdout, io.StringIO()
        health = system_health()
        sys.stdout = _old_stdout
        
        # 缁勮鎺ュ叆鎶ュ憡
        report = {
            "status": "activated" if check_ok else "failed",
            "activated_at": datetime.now().isoformat(),
            "engine": "杩繘-diegin",
            "interception_rules": health.get("interception_rules", 0),
            "success_patterns": health.get("success_patterns", 0),
            "meta_experiences": health.get("meta_experiences", 0),
            "precedents": health.get("precedents", 0),
            "health_summary": health,
            "note": "杩繘宸插氨缁€備娇鐢ㄨ鍒? 瀹堜笁鏀讳竷+涓€浜屼笉杩囦笁+涓夋€佸弽棣?
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))





