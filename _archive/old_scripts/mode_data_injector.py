#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI 模式数据注入器 v1.0
按模式加载 w1-w4_special 配置 + CSV数据 + 风格指纹 + 平台配置 + 战斗参考
将盘古的"弹药库"真正注入到车间流水线中

核心设计:
    ModeDataInjector.get_injection(stage_id, mode, platform, chapter_task, ...)
    → 返回该车间该模式下应该注入的所有数据（纯文本，可直接拼入prompt）
"""

import json
import csv
import os
from pathlib import Path
from typing import Dict, Optional

# ============ 路径配置 ============
BASE_DIR = Path(__file__).parent
MODES_DIR = BASE_DIR / "modes"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REFERENCES_DIR = KNOWLEDGE_DIR / "references"
CSV_DIR = REFERENCES_DIR / "csv"
WRITING_DIR = REFERENCES_DIR / "writing"
PLAN_DIR = REFERENCES_DIR / "plan"
# webnovel-writer 数据扩充（CSV 9表 + 37题材MD模板）
WEBNOVEL_CSV_DIR = REFERENCES_DIR / "webnovel_csv"
WEBNOVEL_GENRES_DIR = REFERENCES_DIR / "webnovel_genres"

# 统一从 pangu_core.prompts 导入模式映射（唯一真值来源）
try:
    from pangu_core.prompts import MODE_TO_GENRE
except ImportError:
    # 降级：使用内嵌副本（应尽快修复导入路径）
    MODE_TO_GENRE = {
        "urban_power": "都市",
        "general": "通用",
        "female_solo": "都市",
        "romance": "都市",
        "mystery": "悬疑/无限流",
        "rule_mystery": "悬疑/无限流",
        "history_scholar": "历史/权谋",
        "military": "军事",
        "xianxia": "玄幻/仙侠",
        "xuanhuan": "玄幻/仙侠",
        "scifi": "科幻/都市科技",
        "fantasy": "西方奇幻",
        "sports": "体育/爽文",
        "crazy_lit": "都市",
        "folk_horror": "悬疑/无限流",
        "healing_life": "治愈",
        "healing_life_v2": "治愈",
        "reality_revenge": "都市",
        "retro_life": "都市",
    }


class ModeDataInjector:
    """
    模式数据注入器 — 盘古弹药库到车间的桥梁

    每个车间需要的注入内容:
    - W0: 模式专属锚定规则
    - W1: w1_special配置 + CSV桥段 + 平台配置 + 人物战斗卡
    - W2: w2_special配置 + 场景写法参考 + 风格锚点 + 创作引擎策略
    - W3: w3_special配置 + 扩展质检维度
    - W4: w4_special配置 + combat-scenes参考 + 氛围技法
    """

    # 题材→CSV文件映射
    GENRE_CSV_MAP = {
        "玄幻/仙侠": ["金手指与设定.csv", "桥段套路.csv"],
        "历史/权谋": ["人设与关系.csv", "命名规则.csv"],
        "悬疑/无限流": ["裁决规则.csv", "爽点与节奏.csv"],
        "军事": ["场景写法.csv", "金手指与设定.csv"],
        "体育/爽文": ["爽点与节奏.csv", "场景写法.csv"],
        "西方奇幻": ["金手指与设定.csv", "场景写法.csv"],
        "科幻/都市科技": ["金手指与设定.csv", "写作技法.csv"],
        "都市": ["桥段套路.csv", "爽点与节奏.csv"],
        "治愈": ["桥段套路.csv", "写作技法.csv"],
        "通用": ["桥段套路.csv", "写作技法.csv"],
    }

    # 题材→战斗参考映射
    COMBAT_GENRES = {"玄幻/仙侠", "体育/爽文", "军事", "西方奇幻", "都市"}

    # 缓存
    _mode_cache: Dict[str, dict] = {}
    _csv_cache: Dict[str, list] = {}
    _platform_cache: Optional[dict] = None
    _fingerprint_cache: Optional[dict] = None
    _combat_ref_cache: Optional[str] = None

    @classmethod
    def get_genre(cls, mode: str) -> str:
        """根据模式获取题材"""
        return MODE_TO_GENRE.get(mode, MODE_TO_GENRE.get(mode.split('_')[0], "通用"))

    # ============ 核心接口 ============

    @classmethod
    def get_injection(cls, stage_id: int, mode: str, platform: str = "qimao",
                      chapter_task: str = "", chapter_num: int = 1,
                      project_dir: str = None) -> str:
        """
        获取指定车间+模式下的全部注入内容
        返回可直接拼入prompt的纯文本
        """
        genre = cls.get_genre(mode)
        parts = []

        if stage_id == 0:
            parts.append(cls._get_w0_injection(mode, genre, chapter_task))
        elif stage_id == 1:
            parts.append(cls._get_w1_injection(mode, genre, platform, chapter_task, chapter_num, project_dir))
        elif stage_id == 2:
            parts.append(cls._get_w2_injection(mode, genre, platform, chapter_task, chapter_num, project_dir))
        elif stage_id == 3:
            parts.append(cls._get_w3_injection(mode, genre))
        elif stage_id == 4:
            parts.append(cls._get_w4_injection(mode, genre, platform, chapter_task))

        return "\n\n".join(p for p in parts if p and p.strip())

    # ============ W0 注入 ============

    @classmethod
    def _get_w0_injection(cls, mode: str, genre: str, chapter_task: str) -> str:
        """W0: 模式专属锚定规则"""
        mode_config = cls._load_mode_config(mode)
        if not mode_config:
            return ""

        parts = []
        # 从w1_special中提取与锚定相关的信息
        w1 = mode_config.get("w1_special", {})
        if w1:
            # 情绪起点
            if "情绪起点" in str(w1):
                parts.append(f"【模式锚定·{mode_config.get('name', mode)}】")
            # 提取extra_fields中的锚定相关字段
            extra_fields = w1.get("extra_fields", [])
            if extra_fields:
                anchor_fields = [f for f in extra_fields
                                 if any(kw in str(f) for kw in ["情绪", "冲突", "矛盾", "禁忌", "锚点", "触发"])]
                if anchor_fields:
                    parts.append("【模式专属锚定维度】")
                    for f in anchor_fields[:5]:
                        parts.append(f"  - {f}")

        return "\n".join(parts)

    # ============ W1 注入 ============

    @classmethod
    def _get_w1_injection(cls, mode: str, genre: str, platform: str,
                          chapter_task: str, chapter_num: int,
                          project_dir: str = None) -> str:
        """W1: 模式配置 + CSV桥段 + 平台配置 + 人物战斗卡"""
        parts = []

        # 1. 模式w1_special配置
        mode_config = cls._load_mode_config(mode)
        if mode_config:
            w1 = mode_config.get("w1_special", {})
            if w1:
                parts.append(cls._format_mode_special("W1设定预处理", mode_config.get("name", mode), w1))

        # 2. CSV桥段检索
        csv_data = cls._search_csv(genre, chapter_task, max_items=3)
        if csv_data:
            parts.append("【桥段套路参考】（来自真人网文数据分析）")
            for item in csv_data:
                parts.append(f"  {item}")

        # 3. 平台配置（详细版）
        platform_detail = cls._get_platform_detail(platform)
        if platform_detail:
            parts.append(platform_detail)

        # 4. 记忆银行上下文
        memory_ctx = cls._get_memory_context(mode, chapter_num, project_dir)
        if memory_ctx:
            parts.append(memory_ctx)

        # 5. 角色情感锚点
        emotional_anchors = cls._get_emotional_anchors(project_dir, chapter_num)
        if emotional_anchors:
            parts.append(emotional_anchors)

        # 6. 人格模型注入（Big Five+VIA）
        try:
            from knowledge.personality_model import get_mode_personality_prompt
            personality_prompt = get_mode_personality_prompt(mode, "主角")
            if personality_prompt:
                parts.append(personality_prompt)
        except ImportError:
            pass

        # 7. EvolvTrip心理图谱注入（4维ToM）
        try:
            from knowledge.psychological_graph import generate_tom_prompt_for_chapter
            # 从记忆银行获取角色名列表
            char_names = []
            if project_dir:
                try:
                    from memory_bank import MemoryBank
                    mb = MemoryBank(project_dir)
                    char_names = list(mb._data.get("character_states", {}).keys())
                except Exception:
                    pass
            if not char_names:
                char_names = ["主角"]
            tom_prompt = generate_tom_prompt_for_chapter(char_names, chapter_num)
            if tom_prompt:
                parts.append(tom_prompt)
        except ImportError:
            pass

        # 8. webnovel题材MD模板注入（37个题材的专业指导）
        genre_md = cls._load_webnovel_genre_template(mode)
        if genre_md:
            parts.append(genre_md)

        return "\n\n".join(parts)

    @classmethod
    def _get_w2_injection(cls, mode: str, genre: str, platform: str,
                          chapter_task: str, chapter_num: int,
                          project_dir: str = None) -> str:
        """W2: 模式配置 + 场景写法 + 风格锚点 + 创作引擎策略"""
        parts = []

        # 1. 模式w2_special配置
        mode_config = cls._load_mode_config(mode)
        if mode_config:
            w2 = mode_config.get("w2_special", {})
            if w2:
                parts.append(cls._format_mode_special("W2正文初稿", mode_config.get("name", mode), w2))

        # 2. 场景写法参考
        scene_data = cls._search_csv_data("场景写法.csv", chapter_task, max_items=2)
        if scene_data:
            parts.append("【场景写法参考】")
            for item in scene_data:
                parts.append(f"  {item}")

        # 3. 风格指纹锚点
        style_anchor = cls._get_style_anchor(genre)
        if style_anchor:
            parts.append(style_anchor)

        # 4. 创作引擎策略
        strategy = cls._get_creative_strategy(mode, chapter_num)
        if strategy:
            parts.append(strategy)

        # 5. 战斗场景参考（如果章节任务涉及战斗）
        if cls._is_combat_scene(chapter_task, genre):
            combat_ref = cls._get_combat_reference()
            if combat_ref:
                parts.append(combat_ref)

        # 6. 前文关键事件提示
        callback_hints = cls._get_callback_hints(project_dir, chapter_num)
        if callback_hints:
            parts.append(callback_hints)

        # 7. 反套路注入提示
        anti_cliche = cls._get_anti_cliche_prompt(mode)
        if anti_cliche:
            parts.append(anti_cliche)

        # 8. Wildcard反转注入（打破AI的'最可能路径'）
        try:
            from knowledge.quality_8d import generate_wildcard_reversal
            wildcard = generate_wildcard_reversal(mode)
            if wildcard:
                parts.append(f"【Wildcard反转——本章必须融入以下意外元素】\n{wildcard}")
        except ImportError:
            pass

        # 9. MECoT情绪链注入（马尔可夫情绪转移）
        try:
            from knowledge.emotion_chain import get_emotion_chain_prompt
            # 默认从"紧张"开始，实际应从记忆银行读取
            emotion_prompt, next_emotion = get_emotion_chain_prompt("紧张", mode)
            if emotion_prompt:
                parts.append(emotion_prompt)
        except ImportError:
            pass

        # 10. 古诗词意象注入（初稿阶段用意象思维写作）
        try:
            from knowledge.poetry_injector import get_poetry_prompt
            poetry_prompt = get_poetry_prompt(mode, scene_type=chapter_task)
            if poetry_prompt:
                parts.append(poetry_prompt)
        except ImportError:
            pass

        # 11. webnovel题材MD模板（精简版，仅提取写作要点）
        genre_md_brief = cls._load_webnovel_genre_template(mode)
        if genre_md_brief:
            # W2只需要精简版（最多800字，避免prompt过长）
            if len(genre_md_brief) > 800:
                genre_md_brief = genre_md_brief[:800] + "\n...(更多题材指导见W1注入)"
            parts.append(genre_md_brief)

        return "\n\n".join(parts)

    # ============ W3 注入 ============

    @classmethod
    def _get_w3_injection(cls, mode: str, genre: str) -> str:
        """W3: 模式配置 + 扩展质检维度"""
        parts = []

        mode_config = cls._load_mode_config(mode)
        if mode_config:
            w3 = mode_config.get("w3_special", {})
            if w3:
                parts.append(cls._format_mode_special("W3逻辑质检", mode_config.get("name", mode), w3))

        return "\n\n".join(parts)

    # ============ W4 注入 ============

    @classmethod
    def _get_w4_injection(cls, mode: str, genre: str, platform: str,
                          chapter_task: str) -> str:
        """W4: 模式配置 + combat-scenes参考 + 氛围技法"""
        parts = []

        # 1. 模式w4_special配置（最重要的注入）
        mode_config = cls._load_mode_config(mode)
        if mode_config:
            w4 = mode_config.get("w4_special", {})
            if w4:
                parts.append(cls._format_w4_special(mode_config.get("name", mode), w4))

        # 2. 战斗场景参考
        if cls._is_combat_scene(chapter_task, genre):
            combat_ref = cls._get_combat_reference()
            if combat_ref:
                parts.append(combat_ref)

        # 3. 爽点节奏参考
        payoff_data = cls._search_csv_data("爽点与节奏.csv", chapter_task, max_items=2)
        if payoff_data:
            parts.append("【爽点节奏参考】")
            for item in payoff_data:
                parts.append(f"  {item}")

        # 4. 古诗词意象注入（替代AI味模板词）
        try:
            from knowledge.poetry_injector import get_poetry_prompt
            poetry_prompt = get_poetry_prompt(mode)
            if poetry_prompt:
                parts.append(poetry_prompt)
        except ImportError:
            pass

        return "\n\n".join(parts)

    # ============ 格式化方法 ============

    @classmethod
    def _format_mode_special(cls, stage_name: str, mode_name: str, special: dict) -> str:
        """将模式special配置格式化为可注入的文本"""
        parts = [f"【{stage_name}·{mode_name}模式专属配置】"]

        # 氛围技法
        atmosphere = special.get("atmosphere_techniques", [])
        if atmosphere:
            parts.append("  氛围技法：")
            for tech in atmosphere[:5]:
                parts.append(f"    - {tech}")

        # 感官优先级
        sensory = special.get("sensory_priority", [])
        if sensory:
            parts.append(f"  感官优先级：{' > '.join(sensory)}")

        # 镜头类型
        shots = special.get("shot_types", [])
        if shots:
            parts.append("  镜头语言：")
            for shot in shots[:5]:
                parts.append(f"    - {shot}")

        # 钩子类型
        hooks = special.get("hook_types", special.get("forbidden_hooks", []))
        if hooks:
            hook_label = "禁用钩子" if "forbidden_hooks" in special else "可用钩子"
            parts.append(f"  {hook_label}：{', '.join(str(h) for h in hooks[:6])}")

        # 禁忌
        taboo = special.get("taboo", [])
        if taboo:
            parts.append("  禁忌：")
            for t in taboo[:5]:
                parts.append(f"    - {t}")

        # 放松/严格检查
        relax = special.get("relax_checks", [])
        if relax:
            parts.append("  放松检查：")
            for r in relax[:3]:
                parts.append(f"    - {r}")

        strict = special.get("strict_checks", [])
        if strict:
            parts.append("  严格检查：")
            for s in strict[:3]:
                parts.append(f"    - {s}")

        # extra_fields
        extra = special.get("extra_fields", [])
        if extra:
            parts.append("  额外设定字段：")
            for e in extra[:6]:
                parts.append(f"    - {e}")

        # temperature
        temp = special.get("temperature")
        if temp is not None:
            parts.append(f"  建议temperature: {temp}")

        # 动作风格
        action = special.get("action_style", "")
        if action:
            parts.append(f"  动作风格: {action}")

        # 对话优先级
        dialogue = special.get("dialogue_priority", "")
        if dialogue:
            parts.append(f"  对话优先级: {dialogue}")

        return "\n".join(parts)

    @classmethod
    def _format_w4_special(cls, mode_name: str, w4: dict) -> str:
        """W4特殊格式化——包含更丰富的精修指导"""
        parts = [f"【W4精修·{mode_name}模式专属配置】"]

        # 氛围技法（W4最重要的配置）
        atmosphere = w4.get("atmosphere_techniques", [])
        if atmosphere:
            parts.append("【氛围渲染技法】（必须使用至少2种）")
            for i, tech in enumerate(atmosphere[:7], 1):
                parts.append(f"  {i}. {tech}")

        # 感官优先级
        sensory = w4.get("sensory_priority", [])
        if sensory:
            parts.append(f"【感官通道优先级】{' > '.join(sensory)}")
            parts.append(f"  → 优先写{sensory[0]}细节，最后写{sensory[-1]}")

        # 镜头语言
        shots = w4.get("shot_types", [])
        if shots:
            parts.append("【镜头语言】（每3段切换一次机位）")
            for shot in shots[:5]:
                parts.append(f"  - {shot}")

        # 禁忌
        taboo = w4.get("taboo", [])
        if taboo:
            parts.append("【本模式禁忌】")
            for t in taboo[:5]:
                parts.append(f"  ❌ {t}")

        # temperature
        temp = w4.get("temperature")
        if temp is not None:
            parts.append(f"【创作温度】{temp}（{'高温=大胆创新' if temp >= 0.8 else '中温=稳定输出' if temp >= 0.6 else '低温=精准控制'}）")

        return "\n".join(parts)

    # ============ 数据加载方法 ============

    @classmethod
    def _load_mode_config(cls, mode: str) -> dict:
        """加载模式配置JSON"""
        if mode in cls._mode_cache:
            return cls._mode_cache[mode]

        mode_file = MODES_DIR / f"{mode}.json"
        if mode_file.exists():
            try:
                data = json.loads(mode_file.read_text(encoding='utf-8'))
                cls._mode_cache[mode] = data
                return data
            except (json.JSONDecodeError, Exception):
                pass

        cls._mode_cache[mode] = {}
        return {}

    @classmethod
    def _search_csv(cls, genre: str, chapter_task: str, max_items: int = 3) -> list:
        """按题材搜索CSV数据"""
        results = []
        csv_files = cls.GENRE_CSV_MAP.get(genre, ["桥段套路.csv"])

        for csv_file in csv_files:
            data = cls._search_csv_data(csv_file, chapter_task, max_items)
            results.extend(data)

        return results[:max_items]

    @classmethod
    def _search_csv_data(cls, csv_file: str, query: str, max_items: int = 3) -> list:
        """在指定CSV文件中搜索相关数据（支持盘古原CSV + webnovel扩充CSV）"""
        cache_key = csv_file
        if cache_key not in cls._csv_cache:
            # 优先搜索盘古原CSV，回退到webnovel_csv
            csv_path = CSV_DIR / csv_file
            if not csv_path.exists():
                csv_path = WEBNOVEL_CSV_DIR / csv_file
            if not csv_path.exists():
                return []
            try:
                rows = []
                with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动处理BOM
                    reader = csv.DictReader(f)
                    for row in reader:
                        rows.append(row)
                cls._csv_cache[cache_key] = rows
            except Exception:
                cls._csv_cache[cache_key] = []
                return []

        rows = cls._csv_cache.get(cache_key, [])
        if not rows:
            return []

        # 关键词匹配
        query_lower = query.lower() if query else ""
        query_words = set(query_lower.replace("，", " ").replace("、", " ").split())

        scored = []
        for row in rows:
            text = " ".join(str(v) for v in row.values()).lower()
            score = sum(1 for w in query_words if w and w in text) if query_words else 1
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: -x[0])

        results = []
        for score, row in scored[:max_items]:
            # 提取最有用的字段
            item_parts = []
            for key in ["桥段名称", "场景类型", "技法名称", "分类", "设定类型", "人设类型", "编号"]:
                if key in row and row[key]:
                    item_parts.append(row[key])
            # 提取核心内容
            for key in ["核心爽点", "说明", "适用场景", "前置铺垫", "行为逻辑", "与剧情交互方式"]:
                if key in row and row[key]:
                    item_parts.append(f"{key}: {row[key][:80]}")
            if item_parts:
                results.append(" | ".join(item_parts))

        return results

    @classmethod
    def _get_platform_detail(cls, platform: str) -> str:
        """获取平台详细配置"""
        if cls._platform_cache is None:
            profile_file = KNOWLEDGE_DIR / "platform_writing_profiles.json"
            if profile_file.exists():
                try:
                    cls._platform_cache = json.loads(profile_file.read_text(encoding='utf-8'))
                except Exception:
                    cls._platform_cache = {}

        profiles = cls._platform_cache.get("profiles", {})
        profile = profiles.get(platform, {})
        if not profile:
            return ""

        parts = [f"【平台配置·{profile.get('name', platform)}】"]
        parts.append(f"  核心逻辑: {profile.get('core_logic', '')}")
        parts.append(f"  关键指标: {profile.get('key_metric', '')}")

        # 开篇规则
        opening = profile.get("opening", {})
        if opening:
            parts.append(f"  开篇钩子位置: {opening.get('hook_position', '')}")
            parts.append(f"  开篇规则: {opening.get('rules', '')}")

        # 对话规则
        dialogue = profile.get("dialogue_rules", {})
        if dialogue:
            parts.append(f"  对话率下限: {dialogue.get('min_ratio', 0)*100:.0f}%")

        # 段落规则
        para = profile.get("paragraph_rules", {})
        if para:
            parts.append(f"  每段最多: {para.get('max_lines_per_para', 5)}行")

        # 情绪delivery
        emotion = profile.get("emotion_delivery", {})
        if emotion:
            parts.append(f"  情绪风格: {emotion.get('style', '')}")

        # 禁忌
        taboo = profile.get("taboo", [])
        if taboo:
            parts.append(f"  平台禁忌: {', '.join(taboo[:5])}")

        # AI高危词
        ai_words = profile.get("ai_high_risk_words", [])
        if ai_words:
            parts.append(f"  AI高危词: {', '.join(ai_words[:5])}")

        return "\n".join(parts)

    @classmethod
    def _get_style_anchor(cls, genre: str) -> str:
        """从1330条风格指纹中获取题材锚点"""
        if cls._fingerprint_cache is None:
            fp_file = KNOWLEDGE_DIR / "style_fingerprints.json"
            if fp_file.exists():
                try:
                    cls._fingerprint_cache = json.loads(fp_file.read_text(encoding='utf-8'))
                except Exception:
                    cls._fingerprint_cache = {}

        if not cls._fingerprint_cache:
            return ""

        fingerprints = cls._fingerprint_cache.get("fingerprints", {})
        if not fingerprints:
            return ""

        # fingerprints 是 dict: {作品名_作者: {title, author, genre, syntax, dialogue, ...}}
        # 按题材匹配最相关的指纹
        genre_keywords = {
            "玄幻/仙侠": ["玄幻", "仙侠", "修仙", "斗破", "凡人"],
            "都市": ["都市", "赘婿", "重生", "大医"],
            "悬疑/无限流": ["悬疑", "诡秘", "无限", "规则"],
            "历史/权谋": ["历史", "权谋", "庆余年", "大明"],
            "体育/爽文": ["体育", "竞技", "热血"],
            "军事": ["军事", "战争"],
            "西方奇幻": ["奇幻", "魔法", "龙"],
            "科幻/都市科技": ["科幻", "三体", "末世"],
            "通用": [],
        }

        keywords = genre_keywords.get(genre, [])
        matched = []
        for key, fp in fingerprints.items():
            if isinstance(fp, dict):
                title = fp.get("title", "").lower()
                fp_genre = fp.get("genre", "").lower()
                if any(kw in title for kw in keywords) or any(kw in fp_genre for kw in keywords):
                    matched.append(fp)

        # 如果没匹配到，取前3个非AI模板的
        if not matched:
            for key, fp in fingerprints.items():
                if isinstance(fp, dict) and not fp.get("is_ai_templated", True):
                    matched.append(fp)
                    if len(matched) >= 3:
                        break

        if not matched:
            return ""

        # 格式化锚点
        parts = ["【风格锚点】（来自真人网文风格指纹数据）"]
        for fp in matched[:2]:
            title = fp.get("title", "未知作品")
            author = fp.get("author", "")
            syntax = fp.get("syntax", {})
            dialogue = fp.get("dialogue", {})
            parts.append(f"  参考《{title}》({author}):")
            if syntax:
                parts.append(f"    平均句长: {syntax.get('avg_sentence_len', '?')}字")
            if dialogue:
                parts.append(f"    对话率: {dialogue.get('ratio', '?')}")
            deep = fp.get("deep_score", {})
            if deep:
                parts.append(f"    动作密度: {deep.get('action_density', '?')}")

        return "\n".join(parts)

    @classmethod
    def _get_creative_strategy(cls, mode: str, chapter_num: int) -> str:
        """获取创作引擎策略建议"""
        try:
            sys.path.insert(0, str(KNOWLEDGE_DIR))
            from creative_engine import CreativeEngine
            engine = CreativeEngine()
            strategy = engine.recommend_strategy(chapter_num, mode=mode)
            if strategy:
                prompt = engine.get_strategy_prompt(strategy, mode=mode)
                if prompt:
                    return f"【创作策略】\n{prompt[:300]}"
        except Exception:
            pass
        return ""

    @classmethod
    def _get_combat_reference(cls) -> str:
        """获取战斗场景写作参考"""
        if cls._combat_ref_cache is not None:
            return cls._combat_ref_cache

        combat_file = WRITING_DIR / "combat-scenes.md"
        if not combat_file.exists():
            cls._combat_ref_cache = ""
            return ""

        try:
            full_text = combat_file.read_text(encoding='utf-8')
            # 提取核心部分（前1500字，包含五阶段结构和节奏控制）
            # 找到第一个##标题后的内容
            lines = full_text.split('\n')
            core_lines = []
            capture = True
            for line in lines:
                if capture:
                    core_lines.append(line)
                if len(core_lines) > 60:
                    break

            result = "【战斗场景写作参考】\n" + "\n".join(core_lines)
            # 限制长度
            if len(result) > 1500:
                result = result[:1500] + "\n...(更多战斗技法见combat-scenes.md)"
            cls._combat_ref_cache = result
            return result
        except Exception:
            cls._combat_ref_cache = ""
            return ""

    @classmethod
    def _get_memory_context(cls, mode: str, chapter_num: int,
                            project_dir: str = None) -> str:
        """获取记忆银行上下文"""
        if not project_dir:
            return ""
        try:
            sys.path.insert(0, str(BASE_DIR))
            from memory_bank import MemoryBank
            mb = MemoryBank(project_dir)
            ctx = mb.get_context_for_chapter(chapter_num)
            if ctx and ctx.strip():
                return f"【记忆银行·前文追踪】\n{ctx[:500]}"
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_emotional_anchors(project_dir, chapter_num):
        """获取角色情感锚点"""
        if not project_dir:
            return ""
        try:
            from memory_bank import MemoryBank
            mb = MemoryBank(project_dir)
            return mb.get_emotional_anchors(chapter_num)
        except Exception:
            return ""

    @staticmethod
    def _get_callback_hints(project_dir, chapter_num):
        """获取前文关键事件提示"""
        if not project_dir:
            return ""
        try:
            from memory_bank import MemoryBank
            mb = MemoryBank(project_dir)
            return mb.get_callback_hints(chapter_num)
        except Exception:
            return ""

    @staticmethod
    def _get_anti_cliche_prompt(mode):
        """获取反套路注入提示"""
        anti_cliche = {
            "crazy_lit": "【反套路要求】禁止'突然暴怒→砸东西→冷静下来'三段式；发疯必须有具体触发物（一个物件/一句话/一个气味）",
            "urban_power": "【反套路要求】禁止'扮猪吃虎→众人震惊→对手不服→再打脸'循环；每次打脸必须伴随1个等价代价",
            "female_solo": "【反套路要求】禁止'所有男人都爱我'；女主的每个决定必须有理性基础，不能靠运气",
            "reality_revenge": "【反套路要求】禁止'主角突然获得证据→当众揭穿→反派崩溃'；复仇必须付出代价，每步都有风险",
            "folk_horror": "【反套路要求】禁止'鬼怪出现→逃跑→再出现'循环；恐怖必须来自日常细节的异常",
            "rule_mystery": "【反套路要求】禁止'规则突然改变→主角适应→再改变'；规则变化必须有逻辑前兆",
            "healing_life": "【反套路要求】禁止'遇到困难→被温暖→立刻好起来'；治愈必须有反复，不能一步到位",
            "healing_life_v2": "【反套路要求】禁止'遇到困难→被温暖→立刻好起来'；治愈必须有反复，不能一步到位",
            "romance": "【反套路要求】禁止'误会→解释→和好'三段式；感情进展必须有具体事件推动",
            "history_scholar": "【反套路要求】禁止'主角用现代知识碾压古人'；考据优势必须有限制条件",
            "retro_life": "【反套路要求】禁止'穿越者用未来知识发财'；年代感必须来自细节而非知识点",
            "general": "【反套路要求】禁止'主角无代价获得好处'；每个收获必须有等价付出",
        }
        return anti_cliche.get(mode, anti_cliche["general"])

    @classmethod
    def _is_combat_scene(cls, chapter_task: str, genre: str) -> bool:
        """判断是否是战斗/高燃场景"""
        combat_keywords = ["战斗", "打", "杀", "对决", "交锋", "交手", "比武", "挑战",
                          "反击", "逆袭", "爆发", "燃", "热血", "冲突", "对抗", "出手"]
        task_lower = (chapter_task or "").lower()
        if any(kw in task_lower for kw in combat_keywords):
            return True
        if genre in cls.COMBAT_GENRES:
            # 玄幻/仙侠等题材，超过5章后默认可能涉及战斗
            return True
        return False

    @classmethod
    def get_all_mode_names(cls) -> list:
        """获取所有可用模式名"""
        if not MODES_DIR.exists():
            return []
        return [p.stem for p in MODES_DIR.glob("*.json")]

    @classmethod
    def get_mode_info(cls, mode: str) -> dict:
        """获取模式摘要信息"""
        config = cls._load_mode_config(mode)
        if not config:
            return {}
        return {
            "name": config.get("name", mode),
            "description": config.get("description", "")[:100],
            "has_w1_special": bool(config.get("w1_special")),
            "has_w2_special": bool(config.get("w2_special")),
            "has_w3_special": bool(config.get("w3_special")),
            "has_w4_special": bool(config.get("w4_special")),
            "genre": cls.get_genre(mode),
        }

    # ============ webnovel题材MD模板 ============

    # 盘古模式→webnovel题材MD文件名映射
    MODE_TO_WEBNOVEL_GENRE = {
        "xianxia": "修仙.md",
        "xuanhuan": "修仙.md",
        "mystery": "悬疑灵异.md",
        "rule_mystery": "规则怪谈.md",
        "urban_power": "都市异能.md",
        "romance": "狗血言情.md",
        "female_solo": "都市日常.md",
        "historical": "历史古代.md",
        "history_scholar": "历史古代.md",
        "military": "抗战谍战.md",
        "scifi": "科幻.md",
        "fantasy": "西幻.md",
        "sports": "游戏体育.md",
        "healing_life": "都市日常.md",
        "healing_life_v2": "都市日常.md",
        "folk_horror": "悬疑灵异.md",
        "crazy_lit": "都市脑洞.md",
        "reality_revenge": "都市异能.md",
        "retro_life": "年代.md",
        "general": None,  # 通用模式无特定题材模板
    }

    @classmethod
    def _load_webnovel_genre_template(cls, mode: str) -> str:
        """加载webnovel的题材MD模板，作为W1的补充知识注入。
        
        webnovel-writer有37个题材MD模板，每个约4-8KB，
        包含该题材的核心要素、常见桥段、人设范式、节奏要点等。
        这些知识比盘古现有的CSV数据更结构化、更完整。
        """
        # 1. 确定题材文件名
        genre_file = cls.MODE_TO_WEBNOVEL_GENRE.get(mode)
        if not genre_file:
            # 尝试用genre名匹配
            genre = cls.get_genre(mode)
            genre_to_file = {
                "玄幻/仙侠": "修仙.md",
                "历史/权谋": "历史古代.md",
                "悬疑/无限流": "规则怪谈.md",
                "军事": "抗战谍战.md",
                "体育/爽文": "游戏体育.md",
                "西方奇幻": "西幻.md",
                "科幻/都市科技": "科幻.md",
                "都市": "都市日常.md",
                "治愈": "都市日常.md",
            }
            genre_file = genre_to_file.get(genre)
        
        if not genre_file:
            return ""

        # 2. 读取MD文件
        md_path = WEBNOVEL_GENRES_DIR / genre_file
        if not md_path.exists():
            return ""

        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            return ""

        if not content or len(content.strip()) < 100:
            return ""

        # 3. 截取关键部分（最多2000字，避免prompt过长）
        # 优先提取"核心要素"、"常见桥段"、"人设"等结构化段落
        sections = cls._extract_genre_sections(content, max_chars=2000)
        if not sections:
            # 降级：取前2000字
            sections = content[:2000]

        return f"【webnovel题材指导·{genre_file.replace('.md', '')}】\n{sections}"

    @classmethod
    def _extract_genre_sections(cls, content: str, max_chars: int = 2000) -> str:
        """从题材MD中提取关键段落"""
        # 关键段落标题
        key_headers = ["核心要素", "核心设定", "常见桥段", "经典桥段", "人设", "角色",
                        "节奏", "爽点", "金手指", "写作要点", "注意事项", "套路"]
        
        lines = content.split("\n")
        extracted = []
        capturing = False
        captured_text = []

        for line in lines:
            stripped = line.strip()

            # 检查是否是关键标题
            if stripped.startswith("#") or stripped.startswith("##"):
                header_text = stripped.lstrip("#").strip()
                is_key = any(kw in header_text for kw in key_headers)
                if is_key:
                    # 保存之前捕获的内容
                    if capturing and captured_text:
                        extracted.append("\n".join(captured_text))
                    capturing = True
                    captured_text = [stripped]
                elif capturing:
                    # 遇到非关键标题，停止捕获
                    if captured_text:
                        extracted.append("\n".join(captured_text))
                    capturing = False
                    captured_text = []
            elif capturing:
                captured_text.append(stripped)

        # 最后一组
        if capturing and captured_text:
            extracted.append("\n".join(captured_text))

        # 如果没有提取到关键段落，取前N字
        if not extracted:
            return content[:max_chars]

        # 按优先级合并，不超过max_chars
        result_parts = []
        total_len = 0
        for part in extracted:
            if total_len + len(part) > max_chars:
                # 截断最后一个
                remaining = max_chars - total_len
                if remaining > 50:
                    result_parts.append(part[:remaining] + "...")
                break
            result_parts.append(part)
            total_len += len(part)

        return "\n\n".join(result_parts)
