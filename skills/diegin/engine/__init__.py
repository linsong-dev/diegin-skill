"""
迭进·DGEN 认知进化系统

强制初始化规则：任何使用本模块的对话，
在首次用户输入前必须先完成迭进预检初始化。

初始化命令：python call_diegin.py activate
预检命令：python call_diegin.py check {"task_type": "session_init"}
"""
import os, sys

# 标记变量，确保每轮对话只初始化一次
_DGEN_INITIALIZED = False


def dgen_init_required() -> bool:
    """返回当前对话是否需要迭进初始化"""
    global _DGEN_INITIALIZED
    return not _DGEN_INITIALIZED


def dgen_mark_initialized():
    """标记当前对话已初始化"""
    global _DGEN_INITIALIZED
    _DGEN_INITIALIZED = True

