"""
盘古AI · Stage 数据契约

用强类型 dataclass 替换 PipelineContext 的 Dict[str, Any] 大口袋。
借鉴 Rust 的所有权模型：每个 Stage 的输出是不可变的，下一 Stage 只读。

设计原则:
  - Output<T>: 带校验的不可变输出
  - Stage 声明依赖: requires = ["anchor_data", "state"]
  - 类型不匹配在开发期暴露，不是运行时崩溃
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# ================================================================
# W0 输出: 锚定数据
# ================================================================

@dataclass(frozen=True)
class AnchorData:
    """W0 主旨锚定的不可变输出"""
    title: str = ""
    genre: str = "general"
    platform: str = "qimao"
    protagonist_name: str = ""
    protagonist_state: str = ""
    key_characters: List[str] = field(default_factory=list)
    active_threads: List[dict] = field(default_factory=list)
    locked_rules: List[str] = field(default_factory=list)
    anchor_summary: str = ""

    @classmethod
    def from_state(cls, state: dict, chapter_num: int, chapter_task: str):
        info = state.get("project_info", {})
        chars = state.get("characters", {})
        if isinstance(chars, list):
            chars = {}

        protagonist = chars.get("protagonist", {})
        key_chars = chars.get("key_characters", [])

        foreshadow = state.get("foreshadowing", {})
        if isinstance(foreshadow, list):
            threads = foreshadow
        else:
            threads = foreshadow.get("active_threads", [])

        setting_log = state.get("setting_log", {})
        if isinstance(setting_log, list):
            rules = setting_log
        else:
            rules = setting_log.get("locked_rules", [])

        return cls(
            title=info.get("title", ""),
            genre=info.get("genre", "general"),
            platform=info.get("platform", "qimao"),
            protagonist_name=protagonist.get("name", ""),
            protagonist_state=protagonist.get("current_state", ""),
            key_characters=[c.get("name", "") for c in key_chars if c.get("name")],
            active_threads=threads,
            locked_rules=[str(r) for r in rules[-30:]] if rules else [],
            anchor_summary=f"第{chapter_num}章 | 任务: {chapter_task[:50]} | 主角: {protagonist.get('name', '?')}",
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ================================================================
# W1 输出: 章节热库
# ================================================================

@dataclass(frozen=True)
class HotLib:
    """W1 设置的不可变输出: 本章热库 (~500字紧凑信息)"""
    hotlib_text: str = ""
    gate_passed: bool = True
    is_opening: bool = False
    has_combat: bool = False
    has_dialogue: bool = False

    @classmethod
    def from_anchor(cls, anchor: AnchorData, chapter_task: str, chapter_num: int):
        parts = []
        if anchor.protagonist_name:
            parts.append(f"主角: {anchor.protagonist_name}，{anchor.protagonist_state}")
        for name in anchor.key_characters[:3]:
            parts.append(f"  角色: {name}")
        for t in anchor.active_threads:
            if isinstance(t, dict) and t.get("status") == "open":
                parts.append(f"伏笔(Ch{t.get('planted_ch','?')}): {t.get('description','?')[:40]}")
        for rule in anchor.locked_rules[-5:]:
            parts.append(f"设定: {rule}")
        parts.append(f"本章任务: {chapter_task}")

        return cls(
            hotlib_text="\n".join(parts),
            gate_passed=True,
            is_opening=chapter_num <= 3,
            has_dialogue=any(kw in chapter_task for kw in ["对话","谈","说","问","答"]),
            has_combat=any(kw in chapter_task for kw in ["战斗","打","杀"]),
        )


# ================================================================
# W3 输出: 质检报告
# ================================================================

@dataclass(frozen=True)
class QCReport:
    """W3 质量检查的不可变输出"""
    passed: bool = True
    score: float = 1.0
    issues: List[str] = field(default_factory=list)
    dialogue_ratio: float = 0.0
    avg_sentence_length: float = 0.0
    fixed_skeleton: str = ""
    retry_hint: str = ""


# ================================================================
# 输出容器: 带校验
# ================================================================

@dataclass
class StageOutput:
    """Stage 执行结果。data 类型随 stage 不同。"""
    stage_id: str
    success: bool
    data: Any = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def get_typed(self, expected_type: type):
        """类型安全获取。类型不匹配时抛出 TypeError。"""
        if not isinstance(self.data, expected_type):
            raise TypeError(
                f"Stage {self.stage_id}: expected {expected_type.__name__}, "
                f"got {type(self.data).__name__}"
            )
        return self.data


# ================================================================
# 阶段依赖声明
# ================================================================

STAGE_REQUIRES = {
    "W0": ["state", "chapter_num", "chapter_task"],
    "W1": ["state", "anchor_data"],
    "W2": ["state", "chapter_task", "chapter_num", "anchor_data"],
    "W3": ["draft_content", "state"],
    "W4": ["draft_content", "qc_report"],
    "W5": ["final_content", "state", "project_dir"],
}

STAGE_PRODUCES = {
    "W0": AnchorData,
    "W1": HotLib,
    "W2": str,       # draft content
    "W3": QCReport,
    "W4": str,       # final content
    "W5": dict,      # export metadata
}
