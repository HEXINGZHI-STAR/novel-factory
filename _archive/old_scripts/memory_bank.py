"""
长篇小说记忆银行 - 解决长篇写作中人物性格漂移、伏笔遗忘、设定矛盾的问题

核心思路：从每章中提取5类关键信息（伏笔、角色状态、设定变更、关系变化、时间线事件），
按衰减策略为新章节提供上下文，确保长篇一致性。
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# AI提取用的prompt模板
EXTRACT_PROMPT = """请从以下章节内容中提取8类关键信息，输出JSON格式：
1. foreshadowing: 本章埋下的伏笔或悬念（列表）
2. characters: 本章出场角色的状态变化（位置、情绪、能力等）
3. settings: 本章新增或变更的世界观设定
4. relationships: 本章中人物关系的变化
5. events: 本章发生的关键事件（按重要性排序）
6. chapter_summary: 本章200字摘要（概括主线进展）
7. subplots: 本章推进的支线（支线名称+当前状态）
8. personality_hints: 角色人格线索（从行为/对话/内心独白推断Big Five维度变化，如{"角色名": {"开放性": 7, "尽责性": 5, "外向性": 3, "宜人性": 6, "神经质": 4, "via": ["勇气", "判断力"]}}）

章节内容：
{chapter_content}

输出格式：
{{
  "foreshadowing": [{{"description": "...", "status": "open"}}],
  "characters": {{"角色名": {{"location": "...", "mood": "...", "key_action": "..."}}}},
  "settings": [{{"description": "...", "type": "locked"}}],
  "relationships": [{{"from": "A", "to": "B", "type": "...", "detail": "..."}}}],
  "events": [{{"event": "...", "significance": "high"}}],
  "chapter_summary": "200字摘要...",
  "subplots": [{{"name": "支线名", "status": "当前状态描述"}}],
  "personality_hints": {{"角色名": {{"开放性": 5, "尽责性": 5, "外向性": 5, "宜人性": 5, "神经质": 5, "via": []}}}}
}}"""

# 规则提取用的关键词
_FORESHADOWING_KEYWORDS = ["暗道", "心中", "却不知道", "殊不知", "没注意到", "浑然不觉", "殊不知", "暗自", "隐隐", "殊不知"]
_RELATIONSHIP_KEYWORDS = ["师徒", "敌人", "朋友", "恋人", "盟友", "仇人", "师兄", "师妹", "师姐", "师弟", "结拜", "对手", "搭档"]


class MemoryBank:
    """长篇小说记忆银行 - 解决长篇一致性问题"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.memory_file = self.project_dir / "memory_bank.json"
        self._data = self._load()

    def _default_structure(self) -> dict:
        """返回默认的记忆银行数据结构"""
        return {
            "version": 1,
            "project_dir": str(self.project_dir),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chapters": {},
            "active_foreshadowing": [],
            "character_states": {},
            "setting_log": {
                "locked_rules": [],
                "pending_rules": []
            },
            "chapter_summaries": {},
            "subplot_board": {},
            "character_cognition": {},
            "character_personality": {},  # 角色人格数据 {name: {big_five, via, derived}}
            "emotional_states": {},  # 角色情绪状态 {name: {current_emotion, history: [...]}}
            "relationship_graph": [],
            "timeline": [],
            "psychological_states": {},  # EvolvTrip心理图谱 {chapter_num: [triplet_dicts]}
        }

    def _load(self) -> dict:
        """从JSON加载记忆"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"记忆银行已加载: {self.memory_file}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"记忆银行加载失败，使用默认结构: {e}")
        return self._default_structure()

    def save(self):
        """保存记忆到JSON"""
        self._data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        logger.info(f"记忆银行已保存: {self.memory_file}")

    def extract_from_chapter(self, chapter_num: int, chapter_content: str, call_ai_func: Optional[Callable] = None) -> dict:
        """
        从完成的章节中提取关键信息（W5记忆提取步骤）
        返回提取结果并自动更新记忆银行

        提取5类信息：
        1. active_foreshadowing: 活跃伏笔
        2. character_states: 角色状态
        3. setting_changes: 设定变更
        4. relationship_changes: 关系变化
        5. timeline_events: 时间线事件
        """
        if call_ai_func:
            extracted = self._extract_with_ai(chapter_content, call_ai_func)
        else:
            extracted = self._extract_with_rules(chapter_content)

        # 写入章节记录
        chapter_key = str(chapter_num)
        self._data["chapters"][chapter_key] = {
            "foreshadowing": extracted.get("foreshadowing", []),
            "characters": extracted.get("characters", {}),
            "settings": extracted.get("settings", []),
            "relationships": extracted.get("relationships", []),
            "events": extracted.get("events", []),
            "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 更新全局活跃伏笔
        for fs in extracted.get("foreshadowing", []):
            fs_id = f"f{len(self._data['active_foreshadowing']) + 1:03d}"
            self._data["active_foreshadowing"].append({
                "id": fs_id,
                "planted_ch": chapter_num,
                "description": fs.get("description", ""),
                "status": fs.get("status", "open"),
                "resolved_ch": None
            })

        # 更新角色状态
        for char_name, char_info in extracted.get("characters", {}).items():
            state = {
                "location": char_info.get("location", ""),
                "mood": char_info.get("mood", ""),
                "power_level": char_info.get("power_level", ""),
                "last_chapter": chapter_num,
                "key_action": char_info.get("key_action", "")
            }
            self._data["character_states"][char_name] = state

        # 更新设定日志
        for setting in extracted.get("settings", []):
            entry = {
                "chapter": chapter_num,
                "description": setting.get("description", ""),
                "type": setting.get("type", "pending")
            }
            if setting.get("type") == "locked":
                self._data["setting_log"]["locked_rules"].append(entry)
            else:
                self._data["setting_log"]["pending_rules"].append(entry)

        # 更新关系图
        for rel in extracted.get("relationships", []):
            self._data["relationship_graph"].append({
                "from": rel.get("from", ""),
                "to": rel.get("to", ""),
                "type": rel.get("type", ""),
                "changed_ch": chapter_num,
                "detail": rel.get("detail", "")
            })

        # 更新章节摘要
        chapter_summary = extracted.get("chapter_summary", "")
        if chapter_summary:
            self._data["chapter_summaries"][chapter_key] = chapter_summary

        # 更新支线进度板
        for subplot in extracted.get("subplots", []):
            subplot_name = subplot.get("name", "")
            subplot_status = subplot.get("status", "")
            if subplot_name:
                self._data["subplot_board"][subplot_name] = subplot_status

        # 更新时间线
        for evt in extracted.get("events", []):
            self._data["timeline"].append({
                "chapter": chapter_num,
                "event": evt.get("event", ""),
                "significance": evt.get("significance", "medium")
            })

        self.save()
        return extracted

    def _extract_with_ai(self, chapter_content: str, call_ai_func: Callable) -> dict:
        """用AI提取记忆"""
        prompt = EXTRACT_PROMPT.format(chapter_content=chapter_content)
        try:
            response = call_ai_func(prompt)
            # 尝试从AI回复中解析JSON
            if isinstance(response, dict):
                return response
            # 尝试从文本中提取JSON
            json_match = re.search(r'\{[\s\S]*\}', str(response))
            if json_match:
                return json.loads(json_match.group())
            logger.warning("AI返回内容无法解析为JSON，降级为规则提取")
            return self._extract_with_rules(chapter_content)
        except Exception as e:
            logger.warning(f"AI提取失败，降级为规则提取: {e}")
            return self._extract_with_rules(chapter_content)

    def _extract_with_rules(self, chapter_content: str) -> dict:
        """规则提取（无AI时的降级方案）"""
        result = {
            "foreshadowing": [],
            "characters": {},
            "settings": [],
            "relationships": [],
            "events": [],
            "chapter_summary": "",
            "subplots": []
        }

        # 伏笔：检测暗示性关键词
        for kw in _FORESHADOWING_KEYWORDS:
            # 找到包含关键词的句子
            sentences = re.findall(rf'[^。！？]*{re.escape(kw)}[^。！？]*[。！？]?', chapter_content)
            for s in sentences[:2]:  # 每个关键词最多取2句
                s = s.strip()
                if s and len(s) > 5:
                    result["foreshadowing"].append({
                        "description": s,
                        "status": "open"
                    })

        # 角色状态：检测"他/她+动作"模式
        char_patterns = [
            r'([\u4e00-\u9fff]{2,4})([走跑站坐躺飞到在]了?[^\u4e00-\u9fff]*[\u4e00-\u9fff]+)',
        ]
        seen_chars = set()
        for pattern in char_patterns:
            matches = re.findall(pattern, chapter_content)
            for name, action in matches[:10]:
                if name not in seen_chars and len(name) >= 2:
                    result["characters"][name] = {
                        "location": "",
                        "mood": "",
                        "key_action": action[:30]
                    }
                    seen_chars.add(name)

        # 关系变化：检测关系词
        for kw in _RELATIONSHIP_KEYWORDS:
            rel_sentences = re.findall(rf'([\u4e00-\u9fff]{{2,4}}).{{0,5}}{re.escape(kw)}.{{0,5}}([\u4e00-\u9fff]{{2,4}})', chapter_content)
            for a, b in rel_sentences[:3]:
                result["relationships"].append({
                    "from": a,
                    "to": b,
                    "type": kw,
                    "detail": ""
                })

        # 时间线事件：取段落首句作为关键事件（简化策略）
        paragraphs = [p.strip() for p in chapter_content.split('\n') if p.strip() and len(p.strip()) > 20]
        for i, para in enumerate(paragraphs[:5]):
            first_sentence = re.match(r'[^。！？]+[。！？]', para)
            if first_sentence:
                result["events"].append({
                    "event": first_sentence.group().strip(),
                    "significance": "high" if i == 0 else "medium"
                })

        # 章节摘要：取前3个关键事件拼接为简化摘要
        if result["events"]:
            summary_events = [e["event"] for e in result["events"][:3]]
            result["chapter_summary"] = "；".join(summary_events)[:200]

        # 支线检测：检测"线索""秘密""计划"等支线关键词
        _SUBPLOT_KEYWORDS = ["线索", "秘密", "计划", "阴谋", "任务", "使命", "调查", "寻找", "追踪"]
        seen_subplots = set()
        for kw in _SUBPLOT_KEYWORDS:
            subplot_sentences = re.findall(rf'([\u4e00-\u9fff]{{2,6}}的?{re.escape(kw)})[^。！？]*[。！？]?', chapter_content)
            for s in subplot_sentences[:2]:
                s = s.strip()
                if s and s not in seen_subplots:
                    result["subplots"].append({
                        "name": s,
                        "status": "进行中"
                    })
                    seen_subplots.add(s)

        return result

    def build_context_package(self, chapter_num, token_budget=2000):
        """
        三层记忆体系（对标AI_NovelGenerator分层向量知识库）

        短期记忆：最近3章原文片段（最精准，直接引用）
        中期记忆：全部章节摘要（覆盖面广，不遗漏）
        长期记忆：向量检索/关键词检索（按需精准，解决长尾问题）
        """
        package = []
        remaining = token_budget

        # === 第一层：Canon正史规则（不可违背，最高优先级）===
        locked_settings = self._data.get("setting_log", {}).get("locked_rules", [])
        if locked_settings:
            chunk = "【锁定设定（不可违背）】\n"
            for s in locked_settings[:5]:
                chunk += f"- {s.get('rule', '')}: {s.get('detail', '')[:50]}\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # === 第二层：角色人格+状态 ===
        # 2a. 角色人格数据
        personalities = self._data.get("character_personality", {})
        if personalities:
            chunk = "【角色人格画像】\n"
            for name, p in list(personalities.items())[:3]:
                if isinstance(p, dict):
                    derived = p.get("derived", {})
                    chunk += f"- {name}: {derived.get('stress_response', '未知')}\n"
                    chunk += f"  触发器: {'、'.join(derived.get('emotional_triggers', [])[:2])}\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # 2b. 角色当前状态
        char_states = self._data.get("character_states", {})
        if char_states:
            chunk = "【角色当前状态】\n"
            for name, state in list(char_states.items())[:5]:
                if isinstance(state, dict):
                    chunk += f"- {name}: {state.get('emotion', '未知')}，位置:{state.get('location', '未知')}\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # === 第三层：短期记忆（最近3章原文片段）===
        chapters = self._data.get("chapters", {})
        if chapters:
            recent_keys = sorted([k for k in chapters.keys() if int(k) >= chapter_num - 3], reverse=True)
            if recent_keys:
                chunk = "【短期记忆——最近章节关键内容（可直接引用具体细节）】\n"
                for k in recent_keys[:3]:
                    ch_data = chapters.get(k, {})
                    content = ch_data.get("content", "")
                    # 取每章最后200字（最接近当前章节的内容）
                    snippet = content[-200:] if len(content) > 200 else content
                    chunk += f"第{k}章末尾: ...{snippet}\n"
                if len(chunk) <= remaining:
                    package.append(chunk)
                    remaining -= len(chunk)

        # === 第四层：伏笔状态 ===
        foreshadowing = self._data.get("active_foreshadowing", [])
        if foreshadowing:
            chunk = "【伏笔状态】\n"
            for fs in foreshadowing[:5]:
                status = fs.get("status", "planted")
                chunk += f"- [{status}] {fs.get('content', '')[:40]}（第{fs.get('planted_chapter', '?')}章）\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # === 第五层：中期记忆（全部章节摘要）===
        summaries = self._data.get("chapter_summaries", {})
        if summaries:
            chunk = "【中期记忆——章节摘要】\n"
            sorted_keys = sorted(summaries.keys(), key=lambda x: int(x), reverse=True)
            for k in sorted_keys[:10]:  # 最近10章摘要
                summary = summaries[k][:60]
                chunk += f"第{k}章: {summary}\n"
                if len(chunk) > remaining * 0.4:
                    break
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # === 第六层：关系图+支线 ===
        relationships = self._data.get("relationship_graph", [])
        if relationships:
            chunk = "【人物关系】\n"
            for rel in relationships[:5]:
                if isinstance(rel, dict):
                    chunk += f"- {rel.get('pair', '')}: {rel.get('relation', '')[:40]}\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        subplots = self._data.get("subplot_board", {})
        if subplots and remaining > 100:
            chunk = "【支线进度】\n"
            for name, status in list(subplots.items())[:3]:
                chunk += f"- {name}: {status[:40]}\n"
            if len(chunk) <= remaining:
                package.append(chunk)
                remaining -= len(chunk)

        # === 第七层：长期记忆（向量检索/关键词检索）===
        if remaining > 200:
            try:
                from unified_bridge import get_bridge
                bridge = get_bridge(str(self.project_dir))
                rag_result = bridge.search_knowledge("", max_results=3)
                if rag_result:
                    chunk = "【长期记忆——知识库检索】\n"
                    chunk += rag_result[:remaining]
                    package.append(chunk)
            except Exception:
                pass

        return "\n".join(package)

    def get_short_term_memory(self, chapter_num, n=3, max_chars=800):
        """获取短期记忆（最近n章原文片段）"""
        chapters = self._data.get("chapters", {})
        if not chapters:
            return ""
        recent_keys = sorted([k for k in chapters.keys() if int(k) >= chapter_num - n], reverse=True)
        parts = []
        total = 0
        for k in recent_keys[:n]:
            ch_data = chapters.get(k, {})
            content = ch_data.get("content", "")
            snippet = content[-300:] if len(content) > 300 else content
            if total + len(snippet) > max_chars:
                break
            parts.append(f"第{k}章: ...{snippet}")
            total += len(snippet)
        return "\n".join(parts)

    def get_mid_term_memory(self, max_chapters=10, max_chars=600):
        """获取中期记忆（章节摘要）"""
        summaries = self._data.get("chapter_summaries", {})
        if not summaries:
            return ""
        sorted_keys = sorted(summaries.keys(), key=lambda x: int(x), reverse=True)
        parts = []
        total = 0
        for k in sorted_keys[:max_chapters]:
            summary = summaries[k][:80]
            if total + len(summary) > max_chars:
                break
            parts.append(f"第{k}章: {summary}")
            total += len(summary)
        return "\n".join(parts)

    def get_long_term_memory(self, query, max_chars=400):
        """获取长期记忆（向量检索）"""
        try:
            from unified_bridge import get_bridge
            bridge = get_bridge(str(self.project_dir))
            return bridge.search_knowledge(query, max_results=3)[:max_chars]
        except Exception:
            return ""

    def get_context_for_chapter(self, chapter_num: int, max_chars: int = 1500) -> str:
        """
        为新章节生成上下文摘要
        优先使用 build_context_package()（QMAI优先级策略），
        如果返回为空则降级为原拼接逻辑
        """
        # 优先使用优先级组装的上下文包
        context_package = self.build_context_package(chapter_num, token_budget=max_chars)
        if context_package.strip():
            return context_package

        # 降级：原拼接逻辑
        sections = []

        # 1. 活跃伏笔预警
        open_fs = [f for f in self._data["active_foreshadowing"] if f["status"] == "open"]
        if open_fs:
            fs_lines = ["【待回收伏笔】"]
            for fs in open_fs:
                fs_lines.append(f"  - [{fs['id']}] 第{fs['planted_ch']}章埋下: {fs['description']}")
            sections.append('\n'.join(fs_lines))

        # 2. 角色当前状态
        if self._data["character_states"]:
            char_lines = ["【角色当前状态】"]
            for name, state in self._data["character_states"].items():
                parts = [f"最后出场: 第{state['last_chapter']}章"]
                if state.get("location"):
                    parts.append(f"位置: {state['location']}")
                if state.get("mood"):
                    parts.append(f"情绪: {state['mood']}")
                if state.get("power_level"):
                    parts.append(f"能力: {state['power_level']}")
                if state.get("key_action"):
                    parts.append(f"关键行为: {state['key_action']}")
                char_lines.append(f"  {name}: {', '.join(parts)}")
            sections.append('\n'.join(char_lines))

        # 3. 关系图摘要
        if self._data["relationship_graph"]:
            rel_lines = ["【人物关系】"]
            for rel in self._data["relationship_graph"]:
                rel_lines.append(f"  {rel['from']} ↔ {rel['to']}: {rel['type']}" +
                                 (f"（第{rel['changed_ch']}章变更: {rel['detail']}）" if rel.get('detail') else ""))
            sections.append('\n'.join(rel_lines))

        # 4. 已锁定设定
        if self._data["setting_log"]["locked_rules"]:
            set_lines = ["【已锁定设定（不可违反）】"]
            for s in self._data["setting_log"]["locked_rules"]:
                set_lines.append(f"  - 第{s['chapter']}章确立: {s['description']}")
            sections.append('\n'.join(set_lines))

        # 5. 近期章节详细摘要（最近3章）
        all_chapters = sorted(self._data["chapters"].keys(), key=int)
        recent_chapters = [ch for ch in all_chapters if int(ch) >= chapter_num - 3 and int(ch) < chapter_num]
        if recent_chapters:
            recent_lines = ["【近期章节详情】"]
            for ch in recent_chapters:
                ch_data = self._data["chapters"][ch]
                recent_lines.append(f"\n--- 第{ch}章 ---")
                if ch_data.get("events"):
                    for evt in ch_data["events"]:
                        recent_lines.append(f"  事件: {evt['event']}（{evt['significance']}）")
                if ch_data.get("foreshadowing"):
                    for fs in ch_data["foreshadowing"]:
                        recent_lines.append(f"  伏笔: {fs['description']}")
            sections.append('\n'.join(recent_lines))

        # 6. 中期章节摘要（4-10章前）
        mid_chapters = [ch for ch in all_chapters if chapter_num - 10 <= int(ch) < chapter_num - 3]
        if mid_chapters:
            mid_lines = ["【中期章节摘要（4-10章前）】"]
            for ch in mid_chapters:
                ch_data = self._data["chapters"][ch]
                # 只保留关键事件
                high_events = [e for e in ch_data.get("events", []) if e.get("significance") == "high"]
                if high_events:
                    mid_lines.append(f"  第{ch}章: {'; '.join(e['event'] for e in high_events)}")
            sections.append('\n'.join(mid_lines))

        # 7. 远期章节（10章以上）只保留重大设定变更
        far_chapters = [ch for ch in all_chapters if int(ch) < chapter_num - 10]
        if far_chapters:
            far_lines = ["【远期重大设定】"]
            for ch in far_chapters:
                ch_data = self._data["chapters"][ch]
                locked = [s for s in ch_data.get("settings", []) if s.get("type") == "locked"]
                if locked:
                    for s in locked:
                        far_lines.append(f"  第{ch}章设定: {s['description']}")
            if len(far_lines) > 1:
                sections.append('\n'.join(far_lines))

        # 拼接并截断
        full_context = '\n\n'.join(sections)
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars - 3] + "..."

        return full_context

    def check_foreshadowing_warnings(self, current_chapter: int, threshold: int = 15) -> list:
        """
        检查是否有伏笔超期未回收
        超过threshold章未回收的伏笔返回警告
        """
        warnings = []
        for fs in self._data["active_foreshadowing"]:
            if fs["status"] == "open":
                gap = current_chapter - fs["planted_ch"]
                if gap >= threshold:
                    warnings.append({
                        "id": fs["id"],
                        "planted_ch": fs["planted_ch"],
                        "description": fs["description"],
                        "gap": gap,
                        "message": f"伏笔[{fs['id']}]已{gap}章未回收（第{fs['planted_ch']}章埋下）: {fs['description']}"
                    })
        return warnings

    def resolve_foreshadowing(self, foreshadowing_id: str, resolved_chapter: int):
        """标记伏笔已回收"""
        for fs in self._data["active_foreshadowing"]:
            if fs["id"] == foreshadowing_id:
                fs["status"] = "resolved"
                fs["resolved_ch"] = resolved_chapter
                logger.info(f"伏笔[{foreshadowing_id}]已在第{resolved_chapter}章回收")
                break
        self.save()

    def update_character(self, name: str, updates: dict):
        """更新角色状态"""
        if name not in self._data["character_states"]:
            self._data["character_states"][name] = {
                "location": "", "mood": "", "power_level": "", "last_chapter": 0, "key_action": ""
            }
        self._data["character_states"][name].update(updates)
        self.save()

    def get_character_state(self, name: str) -> dict:
        """获取角色当前状态"""
        return self._data["character_states"].get(name, {})

    def get_summary(self) -> str:
        """获取记忆银行摘要（用于调试）"""
        total_chapters = len(self._data["chapters"])
        open_fs = len([f for f in self._data["active_foreshadowing"] if f["status"] == "open"])
        resolved_fs = len([f for f in self._data["active_foreshadowing"] if f["status"] == "resolved"])
        total_chars = len(self._data["character_states"])
        total_rels = len(self._data["relationship_graph"])
        locked_settings = len(self._data["setting_log"]["locked_rules"])
        total_events = len(self._data["timeline"])

        lines = [
            f"记忆银行摘要",
            f"  项目目录: {self._data.get('project_dir', '')}",
            f"  最后更新: {self._data.get('last_updated', '')}",
            f"  已提取章节: {total_chapters}",
            f"  活跃伏笔: {open_fs} (已回收: {resolved_fs})",
            f"  追踪角色: {total_chars}",
            f"  关系记录: {total_rels}",
            f"  锁定设定: {locked_settings}",
            f"  时间线事件: {total_events}",
        ]
        return '\n'.join(lines)

    def get_emotional_anchors(self, chapter_num):
        """获取角色情感锚点（用于W1/W2注入）"""
        char_states = self._data.get("character_states", {})
        if not char_states:
            return ""
        anchors = ["【角色当前情感状态——写作时请引用具体细节】"]
        for name, state in char_states.items():
            if isinstance(state, dict):
                emotion = state.get("mood", "未知")
                key_event = state.get("key_action", state.get("mood", ""))
                anchors.append(f"{name}：当前{emotion}（因为：{key_event[:50]}）")
        return "\n".join(anchors)

    def get_callback_hints(self, chapter_num):
        """获取前文关键事件提示（用于W2注入，强制AI引用具体细节）"""
        timeline = self._data.get("timeline", [])
        if not timeline:
            return ""
        recent = timeline[-5:]
        hints = ["【前文关键事件——写作时请引用具体细节，不要用模糊概括】"]
        for event in recent:
            ch = event.get("chapter", "?")
            desc = event.get("event", "")[:60]
            hints.append(f"第{ch}章：{desc}")
        return "\n".join(hints)

    def get_character_cognition(self):
        """获取角色认知系统（knows/does_not_know，防止信息泄露）"""
        cognition = self._data.get("character_cognition", {})
        if not cognition:
            return ""
        lines = ["【角色认知边界——角色不应知道标记为'不知道'的信息】"]
        for name, cog in cognition.items():
            knows = cog.get("knows", [])
            does_not_know = cog.get("does_not_know", [])
            if knows or does_not_know:
                lines.append(f"{name}：")
                if knows:
                    lines.append(f"  已知: {', '.join(knows[:3])}")
                if does_not_know:
                    lines.append(f"  未知: {', '.join(does_not_know[:3])}")
        return "\n".join(lines)

    def update_character_personality(self, name: str, big_five: dict, via: list):
        """更新角色人格数据"""
        from knowledge.personality_model import derive_from_big_five
        derived = derive_from_big_five(big_five)
        self._data["character_personality"][name] = {
            "big_five": big_five,
            "via": via,
            "derived": derived,
        }
        self.save()

    def get_character_personality_prompt(self, name: str) -> str:
        """获取角色人格注入prompt"""
        personality = self._data.get("character_personality", {}).get(name)
        if not personality:
            return ""
        from knowledge.personality_model import generate_personality_prompt
        return generate_personality_prompt(
            personality["big_five"], personality["via"], name
        )

    def update_psychological_states(self, chapter_num, triplets_data):
        """更新心理图谱（EvolvTrip驱动）"""
        if "psychological_states" not in self._data:
            self._data["psychological_states"] = {}
        self._data["psychological_states"][str(chapter_num)] = triplets_data
        self.save()

    def get_psychological_states(self, chapter_num=None):
        """获取心理图谱"""
        states = self._data.get("psychological_states", {})
        if chapter_num is not None:
            return states.get(str(chapter_num), [])
        return states

    def get_all_triplets(self):
        """获取所有心理三元组（用于构建EvolvTrip图谱）"""
        all_triplets = []
        for ch, triplets in self._data.get("psychological_states", {}).items():
            all_triplets.extend(triplets)
        return all_triplets

    def update_emotional_state(self, character_name, emotion, chapter_num):
        """更新角色情绪状态（MECoT驱动）"""
        if "emotional_states" not in self._data:
            self._data["emotional_states"] = {}

        if character_name not in self._data["emotional_states"]:
            self._data["emotional_states"][character_name] = {
                "current_emotion": emotion,
                "history": []
            }

        state = self._data["emotional_states"][character_name]
        state["history"].append({
            "chapter": chapter_num,
            "emotion": state["current_emotion"]
        })
        state["current_emotion"] = emotion
        # 只保留最近20条
        if len(state["history"]) > 20:
            state["history"] = state["history"][-20:]
        self.save()

    def get_current_emotion(self, character_name):
        """获取角色当前情绪"""
        state = self._data.get("emotional_states", {}).get(character_name)
        if state:
            return state.get("current_emotion", "平静")
        return "平静"
