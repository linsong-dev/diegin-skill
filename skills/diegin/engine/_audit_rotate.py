# -*- coding: utf-8 -*-
"""审计日志共享轮转助手（内容治理 2026-08-24）
所有写 diegin_audit.log 的入口统一调用 rotate_audit_log，
超过 max_bytes 时轮转（保留 keep 份），防止单文件无限膨胀。
"""
import os

MAX_BYTES = 8 * 1024 * 1024   # 8MB
KEEP = 3


def rotate_audit_log(log_path: str, max_bytes: int = MAX_BYTES, keep: int = KEEP) -> None:
    try:
        if not os.path.isfile(log_path):
            return
        if os.path.getsize(log_path) < max_bytes:
            return
        # 轮转：log -> log.1 -> log.2 ...，删除最旧
        for i in range(keep - 1, 0, -1):
            src = f"{log_path}.{i}"
            dst = f"{log_path}.{i + 1}"
            if os.path.isfile(src):
                os.replace(src, dst)
        if os.path.isfile(log_path):
            os.replace(log_path, f"{log_path}.1")
        open(log_path, "w", encoding="utf-8").close()
    except Exception:
        pass
