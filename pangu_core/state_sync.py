#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - State↔DB 双向同步

核心职责:
  1. sync_to_db(): 将state.json数据同步到5张DB表
  2. sync_from_db(): 从DB读取数据构建DbContext
  3. DbContext: 供PromptBuilder L08/L09/L15使用的上下文对象

设计原则:
  - state.json是唯一真值来源（Single Source of Truth）
  - DB是state.json的索引化/结构化镜像
  - sync_to_db()在每次写作完成后调用
  - sync_from_db()在Pipeline初始化时调用
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .db import DatabaseManager


@dataclass
class DbContext:
    """DB上下文，供PromptBuilder使用"""
    character_states: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_threads: List[Dict[str, Any]] = field(default_factory=list)
    setting_constraints: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_entries: List[Dict[str, Any]] = field(default_factory=list)
    ref_chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_prompt_text(self) -> str:
        """格式化为Prompt文本（L15注入）"""
        parts = []
        if self.character_states:
            parts.append(f"角色状态(DB): {len(self.character_states)}条记录")
        if self.foreshadowing_threads:
            active = [t for t in self.foreshadowing_threads if t.get("status") in ("open", "active")]
            parts.append(f"活跃伏笔(DB): {len(active)}条")
        if self.setting_constraints:
            parts.append(f"锁定设定(DB): {len(self.setting_constraints)}条")
        if self.knowledge_entries:
            parts.append(f"知识词条(DB): {len(self.knowledge_entries)}条")
        if self.ref_chapters:
            parts.append(f"参考章节(DB): {len(self.ref_chapters)}条")
        return "\n".join(parts) if parts else ""


class StateSync:
    """state.json ↔ DB 双向同步"""
    
    def __init__(self, project_dir: str, db: DatabaseManager):
        self.project_dir = project_dir
        self.project_name = Path(project_dir).name
        self.db = db
    
    def sync_to_db(self, state: Dict[str, Any]) -> Dict[str, int]:
        """state.json → DB（写入5张表）"""
        counts = {}
        counts["character_states"] = self._sync_characters(state)
        counts["foreshadowing_threads"] = self._sync_foreshadowing(state)
        counts["setting_constraints"] = self._sync_settings(state)
        counts["knowledge_entries"] = self._sync_knowledge(state)
        counts["ref_chapters"] = self._sync_ref_chapters(state)
        self.db.commit()
        return counts
    
    def sync_from_db(self) -> DbContext:
        """DB → DbContext（供PromptBuilder使用）"""
        ctx = DbContext()
        ctx.character_states = self._load_character_states()
        ctx.foreshadowing_threads = self._load_foreshadowing()
        ctx.setting_constraints = self._load_settings()
        ctx.knowledge_entries = self._load_knowledge()
        ctx.ref_chapters = self._load_ref_chapters()
        return ctx
    
    # ---- 写入实现 ----
    
    def _sync_characters(self, state: Dict) -> int:
        """同步角色状态"""
        characters = state.get("characters", {})
        if not isinstance(characters, dict):
            return 0
        count = 0
        for name, info in characters.items():
            if not isinstance(info, dict):
                continue
            self.db.execute(
                """INSERT OR REPLACE INTO character_states 
                   (project_name, name, role, current_state, location, last_chapter, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (self.project_name, name,
                 info.get("role", ""), info.get("current_state", ""),
                 info.get("location", ""), info.get("last_chapter", 0))
            )
            count += 1
        return count
    
    def _sync_foreshadowing(self, state: Dict) -> int:
        """同步伏笔线索"""
        foreshadow = state.get("foreshadowing", {})
        threads = []
        if isinstance(foreshadow, list):
            threads = foreshadow
        elif isinstance(foreshadow, dict):
            threads = foreshadow.get("active_threads", [])
        
        count = 0
        for t in threads:
            if not isinstance(t, dict):
                continue
            thread_id = t.get("id", f"fs-{count}")
            self.db.execute(
                """INSERT OR REPLACE INTO foreshadowing_threads
                   (project_name, thread_id, description, status, planted_ch, resolved_ch, priority, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (self.project_name, thread_id,
                 t.get("description", ""), t.get("status", "open"),
                 t.get("planted_ch", 0), t.get("resolved_ch"),
                 t.get("priority", 5))
            )
            count += 1
        return count
    
    def _sync_settings(self, state: Dict) -> int:
        """同步设定约束"""
        setting_log = state.get("setting_log", {})
        rules = []
        if isinstance(setting_log, list):
            rules = setting_log
        elif isinstance(setting_log, dict):
            rules = setting_log.get("locked_rules", [])
        
        count = 0
        for rule in rules:
            if isinstance(rule, str):
                rule_text = rule
            elif isinstance(rule, dict):
                rule_text = rule.get("rule", str(rule))
            else:
                continue
            self.db.execute(
                """INSERT OR REPLACE INTO setting_constraints
                   (project_name, rule, category, status, source_chapter, locked_at)
                   VALUES (?, ?, 'general', 'locked', 0, datetime('now'))""",
                (self.project_name, rule_text)
            )
            count += 1
        return count
    
    def _sync_knowledge(self, state: Dict) -> int:
        """同步知识词条(Lorebook)"""
        lorebook = state.get("lorebook", {})
        if not isinstance(lorebook, dict):
            return 0
        count = 0
        for name, entry in lorebook.items():
            if not isinstance(entry, dict):
                continue
            triggers = json.dumps(entry.get("triggers", [name]), ensure_ascii=False)
            self.db.execute(
                """INSERT OR REPLACE INTO knowledge_entries
                   (project_name, name, category, content, triggers, priority, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (self.project_name, name, entry.get("category", "general"),
                 entry.get("description", ""), triggers, entry.get("priority", 5))
            )
            count += 1
        return count
    
    def _sync_ref_chapters(self, state: Dict) -> int:
        """同步参考章节"""
        progress = state.get("progress", {})
        current_ch = progress.get("current_chapter", 0)
        if current_ch <= 0:
            return 0
        
        chapter_meta = state.get("chapter_meta", {})
        count = 0
        for ch_key, meta in chapter_meta.items():
            if not isinstance(meta, dict):
                continue
            ch_num = meta.get("chapter_num", 0)
            if ch_num <= 0:
                try:
                    ch_num = int(ch_key.replace("chapter_", ""))
                except ValueError:
                    continue
            self.db.execute(
                """INSERT OR REPLACE INTO ref_chapters
                   (project_name, chapter_num, title, content, word_count, summary, created_at)
                   VALUES (?, ?, ?, '', ?, ?, datetime('now'))""",
                (self.project_name, ch_num,
                 meta.get("title", ""), meta.get("word_count", 0),
                 meta.get("summary", meta.get("task", "")))
            )
            count += 1
        return count
    
    # ---- 读取实现 ----
    
    def _load_character_states(self) -> List[Dict]:
        return self.db.query_all(
            "SELECT * FROM character_states WHERE project_name = ? ORDER BY last_chapter DESC",
            (self.project_name,)
        )
    
    def _load_foreshadowing(self) -> List[Dict]:
        return self.db.query_all(
            """SELECT * FROM foreshadowing_threads 
               WHERE project_name = ? AND status IN ('open', 'active')
               ORDER BY priority ASC, planted_ch ASC""",
            (self.project_name,)
        )
    
    def _load_settings(self) -> List[Dict]:
        return self.db.query_all(
            "SELECT * FROM setting_constraints WHERE project_name = ? AND status = 'locked'",
            (self.project_name,)
        )
    
    def _load_knowledge(self) -> List[Dict]:
        return self.db.query_all(
            "SELECT * FROM knowledge_entries WHERE project_name = ? ORDER BY priority ASC",
            (self.project_name,)
        )
    
    def _load_ref_chapters(self) -> List[Dict]:
        return self.db.query_all(
            """SELECT * FROM ref_chapters 
               WHERE project_name = ? ORDER BY chapter_num DESC LIMIT 5""",
            (self.project_name,)
        )
