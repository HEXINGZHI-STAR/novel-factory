"""
盘古AI · State 校验器

在加载 state.json 时统一校验和规范化数据形状。
解决 'list' object has no attribute 'get' 的根本原因。

用法:
    from pangu_core.state_validator import validate_state
    state = validate_state(raw_dict)
    # state 的所有字段现在保证是正确类型
"""

from __future__ import annotations

from typing import Dict, List, Any


def validate_state(raw: dict) -> dict:
    """校验并规范化 state.json 的数据形状。返回安全的副本。"""
    if not isinstance(raw, dict):
        return _default_state()

    state = {
        "project_info": _safe_dict(raw.get("project_info")),
        "progress": _safe_dict(raw.get("progress")),
        "characters": _normalize_characters(raw.get("characters")),
        "foreshadowing": _normalize_foreshadowing(raw.get("foreshadowing")),
        "setting_log": _normalize_setting_log(raw.get("setting_log")),
        "review_checkpoints": _safe_list(raw.get("review_checkpoints")),
        "chapter_meta": _safe_dict(raw.get("chapter_meta")),
        "lorebook": _safe_dict(raw.get("lorebook")),
    }
    return state


def _safe_dict(val: Any) -> dict:
    """确保返回 dict。list → 空dict, None → 空dict。"""
    if isinstance(val, dict):
        return val
    return {}


def _safe_list(val: Any) -> list:
    """确保返回 list。dict → [], None → []。"""
    if isinstance(val, list):
        return val
    return []


def _normalize_characters(val: Any) -> dict:
    """字符数据标准化：可能是 dict(protagonist+key_characters) 或纯 list。"""
    if isinstance(val, dict):
        result = {}
        # protagonist: 确保是 dict
        protag = val.get("protagonist", {})
        result["protagonist"] = protag if isinstance(protag, dict) else {}
        # key_characters: 确保是 list of dict
        kc = val.get("key_characters", [])
        result["key_characters"] = [
            c for c in (kc if isinstance(kc, list) else [])
            if isinstance(c, dict)
        ]
        return result
    if isinstance(val, list):
        return {"protagonist": {}, "key_characters": [
            c for c in val if isinstance(c, dict)
        ]}
    return {"protagonist": {}, "key_characters": []}


def _normalize_foreshadowing(val: Any) -> dict:
    """伏笔数据标准化：可能是 dict(active_threads) 或纯 list。"""
    if isinstance(val, dict):
        threads = val.get("active_threads", [])
        return {"active_threads": threads if isinstance(threads, list) else []}
    if isinstance(val, list):
        return {"active_threads": [t for t in val if isinstance(t, dict)]}
    return {"active_threads": []}


def _normalize_setting_log(val: Any) -> dict:
    """设定日志标准化：可能是 dict(locked_rules) 或纯 list。"""
    if isinstance(val, dict):
        rules = val.get("locked_rules", [])
        return {"locked_rules": rules if isinstance(rules, list) else []}
    if isinstance(val, list):
        return {"locked_rules": [str(r) for r in val]}
    return {"locked_rules": []}


def _default_state() -> dict:
    return {
        "project_info": {},
        "progress": {},
        "characters": {"protagonist": {}, "key_characters": []},
        "foreshadowing": {"active_threads": []},
        "setting_log": {"locked_rules": []},
        "review_checkpoints": [],
        "chapter_meta": {},
        "lorebook": {},
    }
