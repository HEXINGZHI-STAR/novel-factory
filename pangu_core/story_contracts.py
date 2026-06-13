#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI · Story System 合同链
从 webnovel-writer story_system_engine + story_contracts 移植并适配盘古项目结构

合同链层级：
  MASTER_SETTING  → 全书总约束（题材/调性/节奏/核心规则）
  VolumeBrief     → 卷级约束（卷核心事件/卷弧光）
  ChapterBrief    → 章级约束（必写节点/禁写区域/上章承接）
  ReviewContract  → 审校合同（质检标准/改写要求）

盘古适配要点：
  - 读取 state.json（project_info/characters/foreshadowing/setting_log）构建 MASTER_SETTING
  - 读取 大纲/ 目录构建 VolumeBrief
  - 读取前章摘要 + chapter_meta 构建 ChapterBrief
  - 注入到 build_smart_prompt() 第10层（L10:Story合同）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# 合同路径管理（适配盘古项目结构）
# ============================================================

class PanguContractPaths:
    """盘古合同文件路径管理器"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._story_dir = project_dir / ".story-system"

    @property
    def master_setting_json(self) -> Path:
        return self._story_dir / "MASTER_SETTING.json"

    @property
    def master_setting_md(self) -> Path:
        return self._story_dir / "MASTER_SETTING.md"

    @property
    def anti_patterns_json(self) -> Path:
        return self._story_dir / "anti_patterns.json"

    def chapter_brief_json(self, chapter: int) -> Path:
        return self._story_dir / "chapters" / f"chapter_{chapter:03d}.json"

    def volume_brief_json(self, volume: int) -> Path:
        return self._story_dir / "volumes" / f"volume_{volume:03d}.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """安全读取 JSON 文件"""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, data: Any) -> None:
    """安全写入 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(project_dir: Path) -> Optional[Dict[str, Any]]:
    """读取项目 state.json"""
    return _read_json(project_dir / "state.json")


# ============================================================
# 合同构建：MASTER_SETTING
# ============================================================

def build_master_setting(project_dir: Path, mode: str = "", platform: str = "") -> Dict[str, Any]:
    """
    从 state.json + 项目设定 构建 MASTER_SETTING 合同

    数据来源：
      1. state.json.project_info → 题材/模式/平台
      2. state.json.characters → 核心角色锁定
      3. state.json.setting_log → 世界规则锁定
      4. state.json.foreshadowing → 未闭合伏笔列表
    """
    state = _load_state(project_dir)
    if state is None:
        return _empty_master_setting(mode, platform)

    proj_info = state.get("project_info", {})
    mode = mode or proj_info.get("mode", "general")
    platform = platform or proj_info.get("platform", "qimao")
    title = proj_info.get("title", "未命名")
    genre = _mode_to_genre(mode)

    # 核心约束
    master_constraints = {
        "core_tone": _genre_tone(genre),
        "pacing_strategy": _platform_pacing(platform, genre),
        "locked_rules": [],  # 将从 setting_log 中提取
    }

    # 世界规则锁定
    setting_log = state.get("setting_log", [])
    if isinstance(setting_log, list):
        locked_rules = [s.get("rule", "") for s in setting_log
                        if isinstance(s, dict) and s.get("status") == "locked"]
        master_constraints["locked_rules"] = locked_rules

    # 核心角色
    characters = state.get("characters", {})
    core_characters = {}
    if isinstance(characters, dict):
        for name, info in characters.items():
            if isinstance(info, dict):
                core_characters[name] = {
                    "role": info.get("role", ""),
                    "signature": info.get("signature_move", "") or info.get("combat_style", ""),
                    "personality": info.get("personality", ""),
                    "rage_trigger": info.get("rage_trigger", ""),
                }

    # 未闭合伏笔
    foreshadowing = state.get("foreshadowing", [])
    active_foreshadowing = []
    if isinstance(foreshadowing, list):
        for f in foreshadowing:
            if isinstance(f, dict) and f.get("status") in ("active", "planned"):
                active_foreshadowing.append({
                    "id": f.get("id", ""),
                    "content": f.get("content", ""),
                    "status": f.get("status", ""),
                })

    return {
        "meta": {
            "schema_version": "pangu-story-system/v1",
            "contract_type": "MASTER_SETTING",
            "title": title,
            "genre": genre,
            "mode": mode,
            "platform": platform,
        },
        "master_constraints": master_constraints,
        "core_characters": core_characters,
        "active_foreshadowing": active_foreshadowing,
        "override_policy": {
            "locked": ["meta.genre", "master_constraints.core_tone"],
            "append_only": ["active_foreshadowing"],
            "override_allowed": ["master_constraints.pacing_strategy"],
        },
    }


def _empty_master_setting(mode: str, platform: str) -> Dict[str, Any]:
    """空 MASTER_SETTING（降级模式）"""
    genre = _mode_to_genre(mode)
    return {
        "meta": {
            "schema_version": "pangu-story-system/v1",
            "contract_type": "MASTER_SETTING",
            "genre": genre,
            "mode": mode,
            "platform": platform,
        },
        "master_constraints": {
            "core_tone": _genre_tone(genre),
            "pacing_strategy": _platform_pacing(platform, genre),
            "locked_rules": [],
        },
        "core_characters": {},
        "active_foreshadowing": [],
        "override_policy": {
            "locked": ["meta.genre"],
            "append_only": ["active_foreshadowing"],
            "override_allowed": [],
        },
    }


# ============================================================
# 合同构建：ChapterBrief
# ============================================================

def build_chapter_brief(
    project_dir: Path,
    chapter: int,
    chapter_task: str = "",
    master_setting: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    为指定章节构建 ChapterBrief 合同

    数据来源：
      1. MASTER_SETTING → 继承核心约束
      2. state.json.chapter_meta → 本章任务
      3. state.json.foreshadowing → 本章应埋/收的伏笔
      4. state.json.progress → 前章上下文
    """
    state = _load_state(project_dir)

    # 如果没有传入 MASTER_SETTING，从 state 重新构建
    if master_setting is None:
        master_setting = build_master_setting(project_dir)

    # 本章任务
    if not chapter_task and state is not None:
        chapter_meta = state.get("chapter_meta", {})
        chapter_key = f"chapter_{chapter}"
        meta = chapter_meta.get(chapter_key, {})
        chapter_task = meta.get("task", "")

    # 伏笔分配
    foreshadowing_plan = _plan_foreshadowing(state, chapter) if state else {}

    # 上章承接
    dynamic_context = _build_dynamic_context(state, chapter) if state else {}

    return {
        "meta": {
            "schema_version": "pangu-story-system/v1",
            "contract_type": "CHAPTER_BRIEF",
            "chapter": chapter,
        },
        "chapter_directive": {
            "must_cover_nodes": foreshadowing_plan.get("must_plant", []),
            "forbidden_zones": foreshadowing_plan.get("must_not_write", []),
            "chapter_focus": chapter_task[:200] if chapter_task else "",
        },
        "dynamic_context": dynamic_context,
        "override_allowed": {
            "chapter_focus": chapter_task[:100] if chapter_task else "",
        },
    }


def _plan_foreshadowing(state: Dict[str, Any], chapter: int) -> Dict[str, Any]:
    """规划本章应埋/收的伏笔"""
    foreshadowing = state.get("foreshadowing", [])
    if not isinstance(foreshadowing, list):
        return {"must_plant": [], "must_not_write": []}

    must_plant = []
    must_not_write = []

    for f in foreshadowing:
        if not isinstance(f, dict):
            continue
        planted = f.get("planted_chapter", 0)
        status = f.get("status", "")
        content = f.get("content", "")
        f_id = f.get("id", "")

        # planned 状态且未到本章之前 → 本章应埋
        if status == "planned" and planted == 0:
            must_plant.append(f"[{f_id}] {content}")

        # planned 状态且已到回收章 → 本章应收（标记为 must_cover）
        # （简化版：不做自动回收规划，由 chapter_meta 手动指定）

    return {"must_plant": must_plant, "must_not_write": must_not_write}


def _build_dynamic_context(state: Dict[str, Any], chapter: int) -> Dict[str, Any]:
    """构建动态上下文（前章关键事实摘要）"""
    progress = state.get("progress", {})
    current = progress.get("current_chapter", 0)

    # 简化版：提取最近的章节摘要
    chapter_meta = state.get("chapter_meta", {})
    recent_summaries = []
    for i in range(max(1, chapter - 3), chapter):
        key = f"chapter_{i}"
        meta = chapter_meta.get(key, {})
        task = meta.get("task", "")
        if task:
            recent_summaries.append(f"第{i}章: {task[:100]}")

    # 活跃伏笔
    active_f = []
    for f in state.get("foreshadowing", []):
        if isinstance(f, dict) and f.get("status") == "active":
            active_f.append(f.get("content", ""))

    return {
        "recent_chapters": recent_summaries,
        "active_foreshadowing": active_f[:5],
        "total_words": progress.get("total_words", 0),
    }


# ============================================================
# 合同注入：转换为 Prompt 文本（第10层注入）
# ============================================================

def inject_contract_to_prompt(chapter_brief: Dict[str, Any]) -> str:
    """
    将 ChapterBrief 合同转换为 Prompt 注入文本
    这是 build_smart_prompt() 第10层注入的内容

    格式化规则：
      - 必写节点：必须出现在本章中的情节点
      - 禁写区域：本章不得触碰的内容
      - 上章承接：前章关键事实，确保连续性
    """
    if not chapter_brief:
        return ""

    parts = ["【Story System合同·本章】"]

    # 必写节点
    directive = chapter_brief.get("chapter_directive", {})
    must_cover = directive.get("must_cover_nodes", [])
    if must_cover:
        parts.append("必写:")
        for node in must_cover[:5]:
            parts.append(f"  [MUST] {node}")

    # 禁写区域
    forbidden = directive.get("forbidden_zones", [])
    if forbidden:
        parts.append("禁写:")
        for zone in forbidden[:3]:
            parts.append(f"  [BAN] {zone}")

    # 章节焦点
    focus = directive.get("chapter_focus", "")
    if focus:
        parts.append(f"本章焦点: {focus}")

    # 上章承接
    dynamic = chapter_brief.get("dynamic_context", {})
    recent = dynamic.get("recent_chapters", [])
    if recent:
        parts.append("上章承接:")
        for r in recent[-3:]:
            parts.append(f"  [LINK] {r}")

    # 活跃伏笔提醒
    active_f = dynamic.get("active_foreshadowing", [])
    if active_f:
        parts.append("未闭合伏笔（注意回收或推进）:")
        for f in active_f[:3]:
            parts.append(f"  [OPEN] {f}")

    return "\n".join(parts)


# ============================================================
# 合同持久化
# ============================================================

def persist_contracts(
    project_dir: Path,
    chapter: int,
    master_setting: Dict[str, Any],
    chapter_brief: Dict[str, Any],
) -> None:
    """将合同写入 .story-system/ 目录"""
    paths = PanguContractPaths(project_dir)

    # 写入 MASTER_SETTING
    _write_json(paths.master_setting_json, master_setting)

    # 写入 MASTER_SETTING.md（可读版本）
    md_content = _render_master_setting_md(master_setting)
    paths._story_dir.mkdir(parents=True, exist_ok=True)
    paths.master_setting_md.write_text(md_content, encoding="utf-8")

    # 写入 ChapterBrief
    _write_json(paths.chapter_brief_json(chapter), chapter_brief)


def _render_master_setting_md(master: Dict[str, Any]) -> str:
    """将 MASTER_SETTING 渲染为 Markdown"""
    meta = master.get("meta", {})
    constraints = master.get("master_constraints", {})
    lines = [
        "# MASTER_SETTING",
        f"- 书名: {meta.get('title', '')}",
        f"- 题材: {meta.get('genre', '')}",
        f"- 模式: {meta.get('mode', '')}",
        f"- 平台: {meta.get('platform', '')}",
        f"- 调性: {constraints.get('core_tone', '')}",
        f"- 节奏策略: {constraints.get('pacing_strategy', '')}",
    ]

    # 核心角色
    chars = master.get("core_characters", {})
    if chars:
        lines.append("\n## 核心角色")
        for name, info in chars.items():
            lines.append(f"- **{name}** ({info.get('role', '')}): {info.get('personality', '')}")

    # 世界规则
    locked = constraints.get("locked_rules", [])
    if locked:
        lines.append("\n## 锁定规则")
        for rule in locked:
            lines.append(f"- 🔒 {rule}")

    # 活跃伏笔
    active_f = master.get("active_foreshadowing", [])
    if active_f:
        lines.append("\n## 活跃伏笔")
        for f in active_f:
            lines.append(f"- [{f.get('id', '')}] {f.get('content', '')} ({f.get('status', '')})")

    return "\n".join(lines)


# ============================================================
# 辅助函数
# ============================================================

def _mode_to_genre(mode: str) -> str:
    """模式名 → 题材名（复用盘古 prompts.py 的映射）"""
    try:
        from pangu_core.prompts import MODE_TO_GENRE
        return MODE_TO_GENRE.get(mode, MODE_TO_GENRE.get(mode.split('_')[0], "通用"))
    except ImportError:
        genre_map = {
            "urban_power": "都市", "general": "通用", "mystery": "悬疑/无限流",
            "rule_mystery": "悬疑/无限流", "historical": "历史/权谋",
            "military": "军事", "xianxia": "玄幻/仙侠", "xuanhuan": "玄幻/仙侠",
            "scifi": "科幻/都市科技", "fantasy": "西方奇幻",
            "sports": "体育/爽文", "healing_life": "治愈",
        }
        return genre_map.get(mode, "通用")


def _genre_tone(genre: str) -> str:
    """题材 → 核心调性"""
    tones = {
        "玄幻/仙侠": "热血升级+世界观探索，爽感与悬念交替",
        "历史/权谋": "深沉厚重+智谋博弈，慢热但层层推进",
        "悬疑/无限流": "紧张压迫+规则推理，恐惧与好奇并存",
        "军事": "铁血硬核+家国大义，高潮与低谷分明",
        "体育/爽文": "燃爽节奏+实力碾压，情绪持续高涨",
        "西方奇幻": "史诗感+冒险精神，世界观与角色并重",
        "科幻/都市科技": "理性推理+科技奇观，设定与情节交织",
        "都市": "现实感+爽感节奏，代入感强",
        "治愈": "温暖治愈+日常细节，慢节奏情感流",
        "通用": "平衡节奏，爽感与悬念交替",
    }
    return tones.get(genre, "平衡节奏，爽感与悬念交替")


def _platform_pacing(platform: str, genre: str) -> str:
    """平台+题材 → 节奏策略"""
    pacing = {
        "fanqie": "极速节奏：300字出冲突，800字一爽点，段落1-2句，零慢热",
        "qimao": "快节奏：500字入戏，章末强钩子，爽感>悬念>情感",
        "qidian": "稳健节奏：允许慢热但需长线钩子，设定严谨逻辑自洽",
    }
    return pacing.get(platform, "通用节奏：爽感与悬念交替")


# ============================================================
# 便捷函数
# ============================================================

def build_and_inject_chapter_contract(
    project_dir: str | Path,
    chapter: int,
    chapter_task: str = "",
    mode: str = "",
    platform: str = "",
) -> str:
    """
    一站式函数：构建合同 → 持久化 → 返回 Prompt 注入文本

    用于 build_smart_prompt() 第10层注入：
        from pangu_core.story_contracts import build_and_inject_chapter_contract
        contract_text = build_and_inject_chapter_contract(project_dir, chapter, ...)
    """
    project_path = Path(project_dir).expanduser().resolve()

    # 构建 MASTER_SETTING
    master_setting = build_master_setting(project_path, mode=mode, platform=platform)

    # 构建 ChapterBrief
    chapter_brief = build_chapter_brief(
        project_path, chapter, chapter_task=chapter_task, master_setting=master_setting,
    )

    # 持久化
    try:
        persist_contracts(project_path, chapter, master_setting, chapter_brief)
    except Exception:
        pass  # 持久化失败不影响注入

    # 返回注入文本
    return inject_contract_to_prompt(chapter_brief)


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        project = Path(sys.argv[1])
        chapter = int(sys.argv[2])
        mode = sys.argv[3] if len(sys.argv) > 3 else ""
        platform = sys.argv[4] if len(sys.argv) > 4 else ""

        # 构建 MASTER_SETTING
        master = build_master_setting(project, mode=mode, platform=platform)
        print("=== MASTER_SETTING ===")
        print(json.dumps(master, ensure_ascii=False, indent=2))

        # 构建 ChapterBrief
        brief = build_chapter_brief(project, chapter, master_setting=master)
        print("\n=== CHAPTER_BRIEF ===")
        print(json.dumps(brief, ensure_ascii=False, indent=2))

        # Prompt 注入
        injection = inject_contract_to_prompt(brief)
        print("\n=== PROMPT INJECTION (L10) ===")
        print(injection)
    else:
        print("用法: python story_contracts.py <项目目录> <章节号> [模式] [平台]")
        print("示例: python story_contracts.py projects/深渊猎人 1 urban_power qimao")
