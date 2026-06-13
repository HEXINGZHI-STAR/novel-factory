#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI · 长期记忆三层系统
从 webnovel-writer memory/ (orchestrator + budget + compactor) 移植并适配盘古架构

三层记忆模型：
  Working层  (45%) — 当前章节上下文（热库+前3章摘要+角色当前状态）
  Episodic层 (30%) — 近期事件序列（状态变化+角色出场+关系变化）
  Semantic层 (25%) — 世界规则+核心实体+未闭合伏笔

盘古适配要点：
  - 复用盘古 MemoryBank 的 8类提取逻辑
  - 基于 state.json 的 characters/foreshadowing/setting_log 构建
  - 支持 scratchpad 持久化 + 自动压缩
  - 注入到 build_smart_prompt() 第11层（L11:记忆包）
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# 预算分配（从 webnovel budget.py 移植）
# ============================================================

DEFAULT_BUDGET = {
    "write":  {"max_items": 30, "working_ratio": 0.45, "episodic_ratio": 0.30, "semantic_ratio": 0.25},
    "review": {"max_items": 40, "working_ratio": 0.35, "episodic_ratio": 0.35, "semantic_ratio": 0.30},
    "query":  {"max_items": 25, "working_ratio": 0.30, "episodic_ratio": 0.45, "semantic_ratio": 0.25},
}


def allocate_limits(max_items: int = 30, task_type: str = "write") -> Dict[str, int]:
    """按任务类型分配 working/episodic/semantic 的条目预算"""
    max_items = max(1, int(max_items or 1))
    budget = DEFAULT_BUDGET.get(task_type, DEFAULT_BUDGET["write"])
    wr = float(budget.get("working_ratio", 0.45))
    er = float(budget.get("episodic_ratio", 0.30))
    sr = float(budget.get("semantic_ratio", 0.25))

    total_ratio = wr + er + sr
    if total_ratio <= 0:
        wr, er, sr = 0.45, 0.30, 0.25
        total_ratio = 1.0
    wr, er, sr = wr / total_ratio, er / total_ratio, sr / total_ratio

    w = int(max_items * wr)
    e = int(max_items * er)
    s = int(max_items * sr)
    used = w + e + s
    while used < max_items:
        if s <= w:
            s += 1
        elif w <= e:
            w += 1
        else:
            e += 1
        used += 1

    return {"working": w, "episodic": e, "semantic": s}


# ============================================================
# 记忆项数据结构
# ============================================================

class MemoryItem:
    """单个记忆项"""
    __slots__ = ("id", "layer", "category", "subject", "field", "value",
                 "source_chapter", "status", "updated_at")

    def __init__(
        self,
        id: str = "",
        layer: str = "semantic",
        category: str = "story_fact",
        subject: str = "",
        field: str = "",
        value: str = "",
        source_chapter: int = 0,
        status: str = "active",
        updated_at: str = "",
    ):
        self.id = id
        self.layer = layer
        self.category = category
        self.subject = subject
        self.field = field
        self.value = value
        self.source_chapter = source_chapter
        self.status = status
        self.updated_at = updated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "layer": self.layer, "category": self.category,
            "subject": self.subject, "field": self.field, "value": self.value,
            "source_chapter": self.source_chapter, "status": self.status,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryItem":
        return cls(
            id=d.get("id", ""), layer=d.get("layer", "semantic"),
            category=d.get("category", "story_fact"),
            subject=d.get("subject", ""), field=d.get("field", ""),
            value=d.get("value", ""), source_chapter=d.get("source_chapter", 0),
            status=d.get("status", "active"), updated_at=d.get("updated_at", ""),
        )


def _now_iso() -> str:
    """当前时间的 ISO 格式"""
    from datetime import datetime
    return datetime.now().isoformat()[:19]


# ============================================================
# Scratchpad 持久化
# ============================================================

class ScratchpadManager:
    """记忆草稿板管理器 - 持久化到 memory_scratchpad.json"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.scratchpad_file = project_dir / "memory_scratchpad.json"
        self._items: List[MemoryItem] = []
        self._load()

    def _load(self) -> None:
        """从文件加载记忆项"""
        if not self.scratchpad_file.is_file():
            self._items = []
            return
        try:
            data = json.loads(self.scratchpad_file.read_text(encoding="utf-8"))
            self._items = [MemoryItem.from_dict(d) for d in data if isinstance(d, dict)]
        except (json.JSONDecodeError, OSError):
            self._items = []

    def _save(self) -> None:
        """持久化到文件"""
        data = [item.to_dict() for item in self._items]
        self.scratchpad_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def query(self, status: str = "active", category: str = "",
              layer: str = "", source_chapter_min: int = 0) -> List[MemoryItem]:
        """查询记忆项"""
        results = []
        for item in self._items:
            if status and item.status != status:
                continue
            if category and item.category != category:
                continue
            if layer and item.layer != layer:
                continue
            if source_chapter_min > 0 and item.source_chapter < source_chapter_min:
                continue
            results.append(item)
        return results

    def upsert(self, item: MemoryItem) -> None:
        """插入或更新记忆项"""
        # 按 id 查找已有项
        for i, existing in enumerate(self._items):
            if existing.id == item.id:
                self._items[i] = item
                self._save()
                return
        self._items.append(item)
        self._save()

    def mark_outdated(self, item_id: str) -> None:
        """将记忆项标记为过时"""
        for item in self._items:
            if item.id == item_id:
                item.status = "outdated"
                item.updated_at = _now_iso()
        self._save()

    def conflicts(self) -> List[Dict[str, Any]]:
        """检测记忆冲突（同 subject 不同 value）"""
        subject_map: Dict[str, List[MemoryItem]] = {}
        for item in self._items:
            if item.status != "active" or not item.subject:
                continue
            subject_map.setdefault(item.subject, []).append(item)

        conflicts = []
        for subject, items in subject_map.items():
            values = set(item.value for item in items if item.value)
            if len(values) > 1:
                conflicts.append({
                    "subject": subject,
                    "conflicting_values": list(values),
                    "items": [item.to_dict() for item in items],
                })
        return conflicts

    @property
    def total_items(self) -> int:
        return len(self._items)

    @property
    def active_items(self) -> int:
        return sum(1 for item in self._items if item.status == "active")


# ============================================================
# 压缩器（从 webnovel compactor.py 移植）
# ============================================================

def compact_scratchpad(items: List[MemoryItem], max_items: int = 500) -> List[MemoryItem]:
    """
    压缩过时的记忆项

    策略（来自 webnovel compactor.py）：
    1. 同 key 的 outdated 只保留最新
    2. 清理已回收伏笔（status=closed 且 category=open_loop）
    3. 50章以上的 timeline 压缩
    4. 总量超限时按状态和新鲜度截断
    """
    if len(items) <= max_items:
        return items

    # 1. 同 key outdated 只保留最新
    active = [item for item in items if item.status != "outdated"]
    outdated = [item for item in items if item.status == "outdated"]

    outdated_by_key: Dict[Tuple, MemoryItem] = {}
    for item in outdated:
        key = (item.layer, item.category, item.subject, item.field)
        prev = outdated_by_key.get(key)
        if prev is None or (item.updated_at or "") >= (prev.updated_at or ""):
            outdated_by_key[key] = item

    items = active + list(outdated_by_key.values())

    # 2. 清理已回收伏笔
    items = [item for item in items
             if not (item.category == "open_loop" and item.status in ("resolved", "closed", "done"))]

    # 3. 50章以上的 timeline 压缩
    timeline_items = [item for item in items if item.category == "timeline"]
    other_items = [item for item in items if item.category != "timeline"]

    if timeline_items:
        latest_chapter = max(item.source_chapter for item in timeline_items)
        old = [item for item in timeline_items if (latest_chapter - item.source_chapter) > 50]
        fresh = [item for item in timeline_items if (latest_chapter - item.source_chapter) <= 50]

        if len(old) > 1:
            # 压缩旧 timeline 为摘要
            samples = [item.value or item.subject or item.field
                       for item in old[:8] if (item.value or item.subject or item.field)]
            if samples:
                summary = MemoryItem(
                    id=f"timeline-summary-upto-{old[-1].source_chapter}",
                    layer="semantic",
                    category="story_fact",
                    subject="timeline_summary",
                    field=f"<=ch{old[-1].source_chapter}",
                    value=f"[早期事件摘要] {'; '.join(samples)}",
                    source_chapter=old[-1].source_chapter,
                    status="active",
                )
                # 替换已有摘要或新增
                replaced = False
                for i, item in enumerate(other_items):
                    if item.subject == "timeline_summary":
                        other_items[i] = summary
                        replaced = True
                        break
                if not replaced:
                    other_items.append(summary)

        timeline_items = fresh

    items = other_items + timeline_items

    # 4. 全局截断
    if len(items) > max_items:
        items.sort(key=lambda item: (
            0 if item.status == "active" else 1,
            -int(item.source_chapter or 0),
            item.updated_at or "",
        ))
        items = items[:max_items]

    return items


# ============================================================
# 长期记忆编排器（核心类）
# ============================================================

class PanguMemoryOrchestrator:
    """
    盘古长期记忆编排器

    合并盘古 MemoryBank(8类提取) + webnovel MemoryOrchestrator(三层预算)
    """

    CATEGORY_PRIORITY = {
        "world_rule": 0,
        "character_state": 1,
        "relationship": 2,
        "story_fact": 3,
        "open_loop": 4,
        "reader_promise": 5,
        "timeline": 6,
        "emotion_anchor": 7,
    }

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.state_file = project_dir / "state.json"
        self.scratchpad = ScratchpadManager(project_dir)

    # ---- 核心：构建三层记忆包 ----

    def build_memory_pack(self, chapter: int, task_type: str = "write") -> Dict[str, Any]:
        """
        构建三层记忆包

        Working层: 当前章节上下文（大纲+近3章摘要+角色状态）
        Episodic层: 近期事件序列（状态变化+角色出场+关系变化）
        Semantic层: 世界规则+核心实体+未闭合伏笔
        """
        limits = allocate_limits(max_items=30, task_type=task_type)

        working = self._build_working_memory(chapter)[:limits["working"]]
        episodic = self._build_episodic_memory(chapter)[:limits["episodic"]]
        semantic = self._build_semantic_memory(chapter)[:limits["semantic"]]

        # 检测冲突
        conflicts = self.scratchpad.conflicts()
        warnings = []
        if conflicts:
            warnings.append({"type": "memory_conflict", "count": len(conflicts)})

        return {
            "working_memory": working,
            "episodic_memory": episodic,
            "semantic_memory": semantic,
            "long_term_facts": [item.to_dict() for item in semantic],
            "active_constraints": [item.to_dict() for item in semantic
                                   if item.category in ("world_rule", "open_loop")],
            "warnings": warnings,
            "stats": {
                "total_scratchpad": self.scratchpad.total_items,
                "active_scratchpad": self.scratchpad.active_items,
                "working_injected": len(working),
                "episodic_injected": len(episodic),
                "semantic_injected": len(semantic),
            },
        }

    def _build_working_memory(self, chapter: int) -> List[Dict[str, Any]]:
        """Working层: 当前章节上下文"""
        result = []
        state = self._load_state()
        if state is None:
            return result

        # 本章任务
        chapter_meta = state.get("chapter_meta", {})
        ch_key = f"chapter_{chapter}"
        meta = chapter_meta.get(ch_key, {})
        task = meta.get("task", "")
        if task:
            result.append({
                "layer": "working", "source": "chapter_task",
                "chapter": chapter, "content": task[:500],
            })

        # 近3章摘要
        for i in range(max(1, chapter - 3), chapter):
            key = f"chapter_{i}"
            m = chapter_meta.get(key, {})
            t = m.get("task", "")
            if t:
                result.append({
                    "layer": "working", "source": "recent_summary",
                    "chapter": i, "content": t[:300],
                })

        # 角色当前状态
        characters = state.get("characters", {})
        if isinstance(characters, dict):
            for name, info in list(characters.items())[:5]:
                if isinstance(info, dict):
                    result.append({
                        "layer": "working", "source": "character_state",
                        "chapter": chapter,
                        "content": f"{name}({info.get('role', '')}): {info.get('personality', '')[:100]}",
                    })

        return result

    def _build_episodic_memory(self, chapter: int) -> List[Dict[str, Any]]:
        """Episodic层: 近期事件序列"""
        result = []

        # 从 scratchpad 获取近期记忆项
        recent_items = self.scratchpad.query(
            status="active",
            source_chapter_min=max(1, chapter - 20),
        )
        for item in recent_items[:15]:
            result.append({
                "layer": "episodic", "source": item.category,
                "chapter": item.source_chapter,
                "subject": item.subject,
                "content": item.value[:200] if item.value else item.subject,
            })

        # 从 foreshadowing 获取近期伏笔
        state = self._load_state()
        if state is not None:
            foreshadowing = state.get("foreshadowing", [])
            if isinstance(foreshadowing, list):
                for f in foreshadowing:
                    if isinstance(f, dict) and f.get("status") == "active":
                        result.append({
                            "layer": "episodic", "source": "foreshadowing",
                            "chapter": f.get("planted_chapter", 0),
                            "content": f"[{f.get('id', '')}] {f.get('content', '')}",
                        })

        result.sort(key=lambda x: int(x.get("chapter") or 0), reverse=True)
        return result

    def _build_semantic_memory(self, chapter: int) -> List[MemoryItem]:
        """Semantic层: 世界规则+核心实体+未闭合伏笔"""
        result = []
        state = self._load_state()
        if state is None:
            return result

        # 世界规则
        setting_log = state.get("setting_log", [])
        if isinstance(setting_log, list):
            for s in setting_log[:10]:
                if isinstance(s, dict):
                    item = MemoryItem(
                        id=f"rule-{hash(s.get('rule', '')) % 10000:04d}",
                        layer="semantic",
                        category="world_rule",
                        subject="world_rule",
                        field="locked_rule",
                        value=s.get("rule", ""),
                        source_chapter=0,
                        status="active",
                    )
                    result.append(item)

        # 活跃伏笔
        foreshadowing = state.get("foreshadowing", [])
        if isinstance(foreshadowing, list):
            for f in foreshadowing:
                if isinstance(f, dict) and f.get("status") in ("active", "planned"):
                    item = MemoryItem(
                        id=f.get("id", ""),
                        layer="semantic",
                        category="open_loop",
                        subject="foreshadowing",
                        field=f.get("id", ""),
                        value=f.get("content", ""),
                        source_chapter=f.get("planted_chapter", 0),
                        status="active",
                    )
                    result.append(item)

        # 角色核心状态
        characters = state.get("characters", {})
        if isinstance(characters, dict):
            for name, info in characters.items():
                if isinstance(info, dict) and info.get("role") in ("主角", "女主", "主要反派"):
                    item = MemoryItem(
                        id=f"char-{name}",
                        layer="semantic",
                        category="character_state",
                        subject=name,
                        field="core_trait",
                        value=info.get("personality", ""),
                        source_chapter=0,
                        status="active",
                    )
                    result.append(item)

        # 按优先级排序
        result.sort(key=lambda x: self.CATEGORY_PRIORITY.get(x.category, 99))
        return result

    # ---- 记忆写入 ----

    def commit_memory(self, chapter: int, content: str, extraction: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        写入记忆项

        1. 从 extraction 中提取 MemoryItem 列表
        2. 写入 scratchpad
        3. 如超限则压缩
        """
        extraction = extraction or {}
        new_items = []

        # 从伏笔提取
        for f in extraction.get("foreshadowing", []):
            if isinstance(f, dict):
                item = MemoryItem(
                    id=f.get("id", f"fs-ch{chapter}-{len(new_items)}"),
                    layer="semantic",
                    category="open_loop",
                    subject="foreshadowing",
                    field=f.get("id", ""),
                    value=f.get("content", ""),
                    source_chapter=chapter,
                    status=f.get("status", "active"),
                )
                new_items.append(item)

        # 从角色提取
        for name, info in extraction.get("characters", {}).items():
            if isinstance(info, dict):
                item = MemoryItem(
                    id=f"char-ch{chapter}-{name}",
                    layer="working",
                    category="character_state",
                    subject=name,
                    field="state_update",
                    value=str(info)[:200],
                    source_chapter=chapter,
                    status="active",
                )
                new_items.append(item)

        # 从设定提取
        for rule in extraction.get("setting_log", []):
            if isinstance(rule, dict):
                item = MemoryItem(
                    id=f"rule-ch{chapter}-{hash(str(rule)) % 10000:04d}",
                    layer="semantic",
                    category="world_rule",
                    subject="new_rule",
                    field="rule",
                    value=rule.get("rule", str(rule))[:200],
                    source_chapter=chapter,
                    status="active",
                )
                new_items.append(item)

        # 写入 scratchpad
        for item in new_items:
            self.scratchpad.upsert(item)

        # 压缩检查
        if self.scratchpad.total_items > 500:
            all_items = compact_scratchpad(
                [item for item in self.scratchpad._items], max_items=400
            )
            self.scratchpad._items = all_items
            self.scratchpad._save()

        return {"new_items": len(new_items), "total_items": self.scratchpad.total_items}

    # ---- 辅助 ----

    def _load_state(self) -> Optional[Dict[str, Any]]:
        """读取 state.json"""
        if not self.state_file.is_file():
            return None
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


# ============================================================
# Prompt 注入（第11层）
# ============================================================

def build_memory_injection(memory_pack: Dict[str, Any]) -> str:
    """
    将记忆包转换为 Prompt 注入文本
    用于 build_smart_prompt() 第11层注入
    """
    if not memory_pack:
        return ""

    parts = ["[L11:长期记忆包]"]

    # Working层
    working = memory_pack.get("working_memory", [])
    if working:
        parts.append("--当前上下文--")
        for w in working[:5]:
            content = w.get("content", "")
            if isinstance(content, str):
                parts.append(f"  ch{w.get('chapter', '?')}: {content[:100]}")

    # Episodic层
    episodic = memory_pack.get("episodic_memory", [])
    if episodic:
        parts.append("--近期事件--")
        for e in episodic[:5]:
            parts.append(f"  ch{e.get('chapter', '?')} [{e.get('source', '')}]: {str(e.get('content', ''))[:80]}")

    # Semantic层
    semantic = memory_pack.get("semantic_memory", [])
    if semantic:
        parts.append("--核心约束--")
        for s in semantic[:8]:
            if isinstance(s, dict):
                s = MemoryItem.from_dict(s)
            parts.append(f"  [{s.category}] {s.subject}: {s.value[:60]}")

    return "\n".join(parts)


# ============================================================
# 便捷函数
# ============================================================

def build_and_inject_memory(
    project_dir: str | Path,
    chapter: int,
    task_type: str = "write",
) -> str:
    """
    一站式函数：构建记忆包 → 返回 Prompt 注入文本

    用于 build_smart_prompt() 第11层注入：
        from pangu_core.memory_layers import build_and_inject_memory
        memory_text = build_and_inject_memory(project_dir, chapter, ...)
    """
    project_path = Path(project_dir).expanduser().resolve()
    orchestrator = PanguMemoryOrchestrator(project_path)
    memory_pack = orchestrator.build_memory_pack(chapter, task_type=task_type)
    return build_memory_injection(memory_pack)
