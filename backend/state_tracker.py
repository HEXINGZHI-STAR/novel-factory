# -*- coding: utf-8 -*-
"""
盘古AI 状态追踪系统
负责管理章节状态、叙事记忆、情感锚点等
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any


class ChapterState:
    """章节状态管理器"""
    
    def __init__(self):
        self.state = {
            "chapter_num": 0,
            "title": "",
            "mode": "general",
            "platform": "fanqie",
            "word_count": 3000,
            "total_chapters": 0,
            
            # 人物状态
            "characters": {},
            
            # 场景状态
            "current_scene": "",
            "location_history": [],
            
            # 剧情进度
            "plot_progress": 0.0,
            "foreshadowing_active": [],
            "foreshadowing_resolved": [],
            
            # 情感状态
            "emotion_level": 0.5,
            "emotion_trend": "stable",
            "emotion_history": [],
            
            # 写作统计
            "words_written": 0,
            "chapters_completed": 0,
            "writing_speed": 0,
            
            # 时间线
            "story_time": "",
            "story_date": "",
        }
    
    def update(self, key: str, value: Any):
        """更新状态"""
        if key in self.state:
            self.state[key] = value
    
    def get(self, key: str, default=None):
        """获取状态值"""
        return self.state.get(key, default)
    
    def to_dict(self):
        """转换为字典"""
        return self.state.copy()
    
    def load_from_dict(self, data: dict):
        """从字典加载状态"""
        self.state.update(data)


class NarrativeMemory:
    """叙事记忆系统 - 追踪故事发展和上下文"""
    
    def __init__(self):
        self.memory = {
            # 长期记忆 - 故事核心设定
            "long_term": {
                "world_setting": "",
                "core_concept": "",
                "main_characters": [],
                "major_plot_points": [],
                "themes": [],
                "style_guidelines": "",
            },
            
            # 中期记忆 - 当前卷/篇的状态
            "medium_term": {
                "current_arc": "",
                "arc_progress": 0.0,
                "arc_conflicts": [],
                "arc_resolutions": [],
            },
            
            # 短期记忆 - 最近章节的上下文
            "short_term": {
                "last_chapter_summary": "",
                "recent_events": [],
                "active_characters": [],
                "current_relationships": {},
                "unresolved_cliffhangers": [],
            },
            
            # 工作记忆 - 当前章节的临时状态
            "working": {
                "current_task": "",
                "focus_character": "",
                "scene_objectives": [],
                "emotional_goal": "",
                "plot_twists_planned": [],
            }
        }
    
    def add_recent_event(self, event: str):
        """添加近期事件到短期记忆"""
        self.memory["short_term"]["recent_events"].append({
            "event": event,
            "timestamp": datetime.now().isoformat()
        })
        # 保持最多10个近期事件
        if len(self.memory["short_term"]["recent_events"]) > 10:
            self.memory["short_term"]["recent_events"].pop(0)
    
    def update_working_memory(self, key: str, value: Any):
        """更新工作记忆"""
        if key in self.memory["working"]:
            self.memory["working"][key] = value
    
    def get_context(self, scope: str = "all") -> str:
        """获取记忆上下文字符串"""
        if scope == "long_term":
            return self._format_long_term()
        elif scope == "medium_term":
            return self._format_medium_term()
        elif scope == "short_term":
            return self._format_short_term()
        elif scope == "working":
            return self._format_working()
        else:
            return "\n\n".join([
                self._format_long_term(),
                self._format_short_term(),
                self._format_working()
            ])
    
    def _format_long_term(self) -> str:
        """格式化长期记忆"""
        lt = self.memory["long_term"]
        return f"""【长期记忆 - 故事设定】
世界设定: {lt['world_setting'][:200] if lt['world_setting'] else '未设定'}
核心概念: {lt['core_concept'][:100] if lt['core_concept'] else '未设定'}
主题思想: {', '.join(lt['themes']) if lt['themes'] else '未设定'}
主要人物: {', '.join([c.get('name', '') for c in lt['main_characters']])[:100] if lt['main_characters'] else '未设定'}
风格指南: {lt['style_guidelines'][:150] if lt['style_guidelines'] else '未设定'}"""
    
    def _format_medium_term(self) -> str:
        """格式化中期记忆"""
        mt = self.memory["medium_term"]
        return f"""【中期记忆 - 当前故事弧】
故事弧: {mt['current_arc']}
进度: {int(mt['arc_progress'] * 100)}%
当前冲突: {', '.join(mt['arc_conflicts'])[:100] if mt['arc_conflicts'] else '无'}"""
    
    def _format_short_term(self) -> str:
        """格式化短期记忆"""
        st = self.memory["short_term"]
        events = "\n".join([f"- {e['event'][:50]}" for e in st["recent_events"][-5:]])
        return f"""【短期记忆 - 近期事件】
上章摘要: {st['last_chapter_summary'][:150] if st['last_chapter_summary'] else '无'}
近期事件:
{events if events else '无'}
活跃人物: {', '.join(st['active_characters'])[:100] if st['active_characters'] else '无'}
未解决悬念: {len(st['unresolved_cliffhangers'])} 个"""
    
    def _format_working(self) -> str:
        """格式化工作记忆"""
        w = self.memory["working"]
        objectives = "\n".join([f"- {o}" for o in w["scene_objectives"]])
        return f"""【工作记忆 - 当前任务】
当前任务: {w['current_task'][:100] if w['current_task'] else '无'}
焦点人物: {w['focus_character'] if w['focus_character'] else '无'}
场景目标:
{objectives if objectives else '无'}
情感目标: {w['emotional_goal'] if w['emotional_goal'] else '无'}"""
    
    def to_dict(self):
        """转换为字典"""
        return self.memory.copy()
    
    def load_from_dict(self, data: dict):
        """从字典加载"""
        self.memory.update(data)


class EmotionTracker:
    """情感追踪器 - 追踪故事情感曲线"""
    
    def __init__(self):
        self.timeline = []
        self.current_emotion = "neutral"
        self.emotion_history = []
        
    def record_emotion(self, chapter: int, emotion: str, intensity: float, context: str = ""):
        """记录情感状态"""
        entry = {
            "chapter": chapter,
            "emotion": emotion,
            "intensity": intensity,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        self.timeline.append(entry)
        self.emotion_history.append(emotion)
        self.current_emotion = emotion
        
    def get_emotion_trend(self, window: int = 5) -> str:
        """获取情感趋势"""
        recent = self.emotion_history[-window:]
        if not recent:
            return "stable"
        
        positive = sum(1 for e in recent if e in ["happy", "excited", "hopeful", "romantic"])
        negative = sum(1 for e in recent if e in ["sad", "angry", "fearful", "tense"])
        
        if positive > negative + 1:
            return "rising"
        elif negative > positive + 1:
            return "falling"
        else:
            return "stable"
    
    def get_chapter_emotion_summary(self, chapter: int) -> str:
        """获取章节情感摘要"""
        entries = [e for e in self.timeline if e["chapter"] == chapter]
        if not entries:
            return "无情感记录"
        
        emotions = [e["emotion"] for e in entries]
        avg_intensity = sum(e["intensity"] for e in entries) / len(entries)
        
        return f"章节{chapter}情感: {', '.join(set(emotions))} (强度: {avg_intensity:.2f})"
    
    def validate_emotion_curve(self, chapter_content: str) -> dict:
        """验证情感曲线是否符合要求"""
        # 简单的情感曲线验证
        sentences = chapter_content.split('。')
        if len(sentences) < 3:
            return {"pass": False, "reason": "内容过短"}
        
        # 检查情感起伏
        emotion_words = {
            "happy": ["笑", "喜", "乐", "欢", "爽", "甜", "暖"],
            "sad": ["哭", "泪", "悲", "伤", "痛", "愁", "苦"],
            "tense": ["紧", "急", "险", "惊", "慌", "怕", "疑"],
            "calm": ["静", "缓", "平", "安", "舒", "悠"]
        }
        
        emotion_counts = {}
        for emotion, words in emotion_words.items():
            emotion_counts[emotion] = sum(chapter_content.count(w) for w in words)
        
        total = sum(emotion_counts.values())
        if total == 0:
            return {"pass": True, "reason": "情感中性", "score": 75}
        
        # 检查情感多样性
        active_emotions = sum(1 for c in emotion_counts.values() if c > 0)
        if active_emotions >= 2:
            return {"pass": True, "reason": f"情感丰富 ({active_emotions}种)", "score": min(95, 75 + active_emotions * 10)}
        else:
            return {"pass": True, "reason": f"单一情感", "score": 70}


class ForeshadowingManager:
    """伏笔管理器 - 追踪和管理故事伏笔"""
    
    def __init__(self):
        self.hooks = []  # 活跃的伏笔
        self.resolved = []  # 已回收的伏笔
        self.orphaned = []  # 未回收的过期伏笔
    
    def add_hook(self, chapter: int, hook_type: str, description: str, target_chapter: Optional[int] = None):
        """添加伏笔"""
        hook = {
            "id": f"hook_{len(self.hooks) + 1}",
            "chapter": chapter,
            "type": hook_type,
            "description": description,
            "target_chapter": target_chapter,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "clues": []
        }
        self.hooks.append(hook)
        return hook["id"]
    
    def add_clue(self, hook_id: str, chapter: int, clue_text: str):
        """为伏笔添加线索"""
        for hook in self.hooks:
            if hook["id"] == hook_id:
                hook["clues"].append({
                    "chapter": chapter,
                    "text": clue_text,
                    "timestamp": datetime.now().isoformat()
                })
                return True
        return False
    
    def resolve_hook(self, hook_id: str, chapter: int, resolution: str):
        """回收伏笔"""
        for i, hook in enumerate(self.hooks):
            if hook["id"] == hook_id:
                hook["status"] = "resolved"
                hook["resolved_at"] = datetime.now().isoformat()
                hook["resolved_chapter"] = chapter
                hook["resolution"] = resolution
                self.resolved.append(hook)
                del self.hooks[i]
                return True
        return False
    
    def check_expired(self, current_chapter: int, max_chapters: int = 10):
        """检查过期伏笔"""
        to_remove = []
        for i, hook in enumerate(self.hooks):
            if hook["target_chapter"] and current_chapter > hook["target_chapter"] + max_chapters:
                hook["status"] = "orphaned"
                hook["orphaned_at"] = datetime.now().isoformat()
                self.orphaned.append(hook)
                to_remove.append(i)
        
        for i in reversed(to_remove):
            del self.hooks[i]
    
    def get_active_hooks_summary(self) -> str:
        """获取活跃伏笔摘要"""
        if not self.hooks:
            return "当前无活跃伏笔"
        
        lines = []
        for hook in self.hooks:
            target_info = f" (预计{hook['target_chapter']}章回收)" if hook['target_chapter'] else ""
            lines.append(f"- [{hook['type']}] {hook['description'][:30]}...{target_info}")
        
        return "\n".join(lines)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "active": self.hooks,
            "resolved": self.resolved,
            "orphaned": self.orphaned
        }


class WritingStats:
    """写作统计器"""
    
    def __init__(self):
        self.stats = {
            "total_words": 0,
            "total_chapters": 0,
            "avg_words_per_chapter": 0,
            "writing_sessions": [],
            "daily_stats": {},
            "genre_distribution": {},
            "platform_distribution": {},
            "completion_rate": 0.0
        }
    
    def record_chapter(self, word_count: int, chapter_num: int, genre: str, platform: str):
        """记录章节写作"""
        self.stats["total_words"] += word_count
        self.stats["total_chapters"] = max(self.stats["total_chapters"], chapter_num)
        self.stats["avg_words_per_chapter"] = self.stats["total_words"] / max(1, self.stats["total_chapters"])
        
        # 更新题材分布
        self.stats["genre_distribution"][genre] = self.stats["genre_distribution"].get(genre, 0) + 1
        
        # 更新平台分布
        self.stats["platform_distribution"][platform] = self.stats["platform_distribution"].get(platform, 0) + 1
        
        # 记录写作会话
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {"words": 0, "chapters": 0}
        self.stats["daily_stats"][today]["words"] += word_count
        self.stats["daily_stats"][today]["chapters"] += 1
    
    def get_summary(self) -> str:
        """获取统计摘要"""
        s = self.stats
        return f"""【写作统计】
总字数: {s['total_words']:,}
总章节: {s['total_chapters']}
平均每章: {int(s['avg_words_per_chapter'])}字
题材分布: {', '.join([f'{k}:{v}' for k, v in s['genre_distribution'].items()])}"""


class StateTracker:
    """综合状态追踪器"""
    
    def __init__(self):
        self.chapter_state = ChapterState()
        self.narrative_memory = NarrativeMemory()
        self.emotion_tracker = EmotionTracker()
        self.foreshadowing_manager = ForeshadowingManager()
        self.writing_stats = WritingStats()
    
    def initialize_from_project(self, project_data: dict):
        """从项目数据初始化"""
        self.chapter_state.load_from_dict({
            "title": project_data.get("title", ""),
            "mode": project_data.get("mode", "general"),
            "platform": project_data.get("platform", "fanqie"),
            "total_chapters": project_data.get("total_chapters", 0),
            "genre": project_data.get("genre", "都市")
        })
        
        self.narrative_memory.update_working_memory("current_task", project_data.get("chapter_task", ""))
        self.narrative_memory.memory["long_term"]["core_concept"] = project_data.get("cold_storage", "")[:200]
    
    def update_after_chapter(self, chapter_num: int, content: str, chapter_summary: str):
        """章节完成后更新状态"""
        # 更新章节状态
        self.chapter_state.update("chapter_num", chapter_num)
        self.chapter_state.update("words_written", len(content.replace("\n", "").replace(" ", "")))
        self.chapter_state.update("chapters_completed", chapter_num)
        
        # 更新叙事记忆
        self.narrative_memory.update_working_memory("last_chapter_summary", chapter_summary)
        self.narrative_memory.add_recent_event(f"第{chapter_num}章完成")
        
        # 更新情感追踪
        emotion_result = self.emotion_tracker.validate_emotion_curve(content)
        self.emotion_tracker.record_emotion(chapter_num, "neutral", emotion_result.get("score", 50) / 100)
        
        # 更新写作统计
        self.writing_stats.record_chapter(
            len(content.replace("\n", "").replace(" ", "")),
            chapter_num,
            self.chapter_state.get("mode", "general"),
            self.chapter_state.get("platform", "fanqie")
        )
        
        # 检查过期伏笔
        self.foreshadowing_manager.check_expired(chapter_num)
    
    def get_full_context(self) -> str:
        """获取完整上下文"""
        parts = [
            self.narrative_memory.get_context("long_term"),
            self.narrative_memory.get_context("short_term"),
            self.narrative_memory.get_context("working"),
            f"【伏笔状态】\n{self.foreshadowing_manager.get_active_hooks_summary()}"
        ]
        return "\n\n".join(parts)
    
    def to_dict(self) -> dict:
        """转换为字典用于持久化"""
        return {
            "chapter_state": self.chapter_state.to_dict(),
            "narrative_memory": self.narrative_memory.to_dict(),
            "emotion_tracker": {
                "timeline": self.emotion_tracker.timeline,
                "current_emotion": self.emotion_tracker.current_emotion
            },
            "foreshadowing": self.foreshadowing_manager.to_dict(),
            "writing_stats": self.writing_stats.stats,
            "saved_at": datetime.now().isoformat()
        }
    
    def save_to_file(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str):
        """从文件加载"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.chapter_state.load_from_dict(data.get("chapter_state", {}))
            self.narrative_memory.load_from_dict(data.get("narrative_memory", {}))
            
            emotion_data = data.get("emotion_tracker", {})
            self.emotion_tracker.timeline = emotion_data.get("timeline", [])
            self.emotion_tracker.current_emotion = emotion_data.get("current_emotion", "neutral")
            
            foreshadow_data = data.get("foreshadowing", {})
            self.foreshadowing_manager.hooks = foreshadow_data.get("active", [])
            self.foreshadowing_manager.resolved = foreshadow_data.get("resolved", [])
            self.foreshadowing_manager.orphaned = foreshadow_data.get("orphaned", [])
            
            self.writing_stats.stats = data.get("writing_stats", {})
            return True
        except Exception:
            return False