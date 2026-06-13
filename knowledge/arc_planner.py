#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 叙事弧线规划器
批量生成前先规划多章叙事弧线，确保节奏递进、爽点升级、伏笔有计划。
"""

import json
from pathlib import Path
from typing import Optional, Callable, List, Dict


# 叙事节奏模板
RHYTHM_TEMPLATES = {
    "standard": [
        {"phase": "压", "intensity": 0.3, "type": "铺垫"},
        {"phase": "扬", "intensity": 0.6, "type": "小爽"},
        {"phase": "压", "intensity": 0.5, "type": "波折"},
        {"phase": "扬", "intensity": 0.8, "type": "大爽"},
        {"phase": "压", "intensity": 0.4, "type": "余波+新悬念"},
    ],
    "fast": [
        {"phase": "扬", "intensity": 0.7, "type": "开局即爽"},
        {"phase": "压", "intensity": 0.5, "type": "反转"},
        {"phase": "扬", "intensity": 0.9, "type": "绝地反击"},
    ],
    "slow": [
        {"phase": "压", "intensity": 0.2, "type": "日常铺垫"},
        {"phase": "压", "intensity": 0.3, "type": "暗流涌动"},
        {"phase": "压", "intensity": 0.5, "type": "矛盾积累"},
        {"phase": "扬", "intensity": 0.7, "type": "爆发"},
        {"phase": "扬", "intensity": 0.5, "type": "余韵"},
    ],
}

# 爽点升级路径
PAYOFF_LADDER = {
    "都市": ["小聪明得逞", "打脸小人物", "打脸权威", "行业震动", "格局颠覆"],
    "玄幻/仙侠": ["初窥门径", "小胜同辈", "越级挑战", "宗门震动", "天下闻名"],
    "悬疑/无限流": ["发现线索", "解开小谜", "识破阴谋", "绝境翻盘", "真相大白"],
    "通用": ["小试牛刀", "初露锋芒", "一鸣惊人", "大获全胜", "登峰造极"],
}


def plan_arc(
    start_chapter: int,
    num_chapters: int,
    mode: str = "general",
    platform: str = "qimao",
    outline: str = "",
    call_ai_func: Optional[Callable] = None,
) -> List[Dict]:
    """
    规划多章叙事弧线。
    
    参数:
        start_chapter: 起始章节号
        num_chapters: 规划章数
        mode: 写作模式
        platform: 目标平台
        outline: 大纲摘要
        call_ai_func: AI调用函数（可选，用于生成更精准的弧线）
    
    返回:
        [{"chapter": 1, "phase": "压", "intensity": 0.3, "type": "铺垫",
          "conflict": "...", "payoff": "...", "foreshadow": "...", "task": "..."}]
    """
    # 选择节奏模板
    if platform in ("fanqie", "qimao"):
        rhythm = RHYTHM_TEMPLATES["fast"]
    elif mode in ("healing_life", "novel_writer"):
        rhythm = RHYTHM_TEMPLATES["slow"]
    else:
        rhythm = RHYTHM_TEMPLATES["standard"]
    
    # 选择爽点升级路径
    genre = _mode_to_genre(mode)
    payoff_ladder = PAYOFF_LADDER.get(genre, PAYOFF_LADDER["通用"])
    
    # 如果有AI函数，用AI生成更精准的弧线
    if call_ai_func:
        return _plan_with_ai(start_chapter, num_chapters, mode, platform, outline, call_ai_func, rhythm, payoff_ladder)
    
    # 否则用规则生成
    return _plan_with_rules(start_chapter, num_chapters, rhythm, payoff_ladder, outline)


def _plan_with_rules(start_chapter, num_chapters, rhythm, payoff_ladder, outline):
    """规则版弧线规划"""
    chapters = []
    rhythm_len = len(rhythm)
    
    for i in range(num_chapters):
        ch = start_chapter + i
        r = rhythm[i % rhythm_len]
        
        # 爽点升级：根据章节位置选择不同层级的爽点
        payoff_idx = min(i // max(num_chapters // len(payoff_ladder), 1), len(payoff_ladder) - 1)
        
        # 伏笔计划：每2-3章埋一个伏笔，5章内回收
        foreshadow = ""
        if i % 3 == 0:
            foreshadow = f"埋伏笔（预计第{ch+3}章回收）"
        elif i % 3 == 2:
            foreshadow = "回收前期伏笔"
        
        chapter_plan = {
            "chapter": ch,
            "phase": r["phase"],
            "intensity": r["intensity"],
            "type": r["type"],
            "conflict": f"第{ch}章核心冲突（{r['phase']}阶段）",
            "payoff": payoff_ladder[payoff_idx],
            "foreshadow": foreshadow,
            "task": f"{r['type']}，{r['phase']}阶段，爽点：{payoff_ladder[payoff_idx]}",
        }
        chapters.append(chapter_plan)
    
    return chapters


def _plan_with_ai(start_chapter, num_chapters, mode, platform, outline, call_ai_func, rhythm, payoff_ladder):
    """AI版弧线规划"""
    system = f"""你是{platform}网文的叙事弧线规划专家。根据大纲和节奏要求，为每章设计冲突、爽点和伏笔。
规则：
1. 压-扬-压-扬-大扬 的节奏递进
2. 爽点必须逐章升级，不能重复同一层级
3. 每2-3章埋一个伏笔，5章内必须回收
4. 输出JSON数组"""

    rhythm_desc = " → ".join(f"{r['phase']}({r['type']})" for r in rhythm)
    payoff_desc = " → ".join(payoff_ladder)
    
    user = f"""请为第{start_chapter}-{start_chapter+num_chapters-1}章规划叙事弧线。

大纲摘要：{outline[:500] if outline else '（无大纲）'}
节奏模板：{rhythm_desc}
爽点升级路径：{payoff_desc}

输出JSON数组，每章一个对象：
[{{"chapter": 1, "phase": "压/扬", "conflict": "核心冲突", "payoff": "爽点描述", "foreshadow": "伏笔计划（埋/收/无）", "task": "章节任务描述"}}]"""

    try:
        result = call_ai_func(user, system_msg=system)
        if result:
            # 提取JSON
            import re
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                plans = json.loads(json_match.group())
                # 补充缺失字段
                for i, p in enumerate(plans):
                    p.setdefault("chapter", start_chapter + i)
                    p.setdefault("phase", rhythm[i % len(rhythm)]["phase"])
                    p.setdefault("intensity", rhythm[i % len(rhythm)]["intensity"])
                    p.setdefault("type", rhythm[i % len(rhythm)]["type"])
                    p.setdefault("payoff", payoff_ladder[min(i, len(payoff_ladder)-1)])
                    p.setdefault("foreshadow", "")
                    p.setdefault("task", p.get("conflict", ""))
                return plans
    except Exception:
        pass
    
    # AI失败则降级到规则版
    return _plan_with_rules(start_chapter, num_chapters, rhythm, payoff_ladder, outline)


def save_arc(project_dir: Path, arc: List[Dict]):
    """保存弧线规划到项目目录"""
    arc_file = project_dir / "arc_plan.json"
    with open(arc_file, 'w', encoding='utf-8') as f:
        json.dump(arc, f, ensure_ascii=False, indent=2)


def load_arc(project_dir: Path) -> List[Dict]:
    """加载已保存的弧线规划"""
    arc_file = project_dir / "arc_plan.json"
    if arc_file.exists():
        with open(arc_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def get_chapter_task(arc: List[Dict], chapter_num: int) -> str:
    """从弧线规划中获取指定章节的任务描述"""
    for ch in arc:
        if ch.get("chapter") == chapter_num:
            return ch.get("task", "")
    return ""


def _mode_to_genre(mode: str) -> str:
    """模式名转题材名"""
    try:
        from pangu_core.prompts import get_genre_for_mode
        return get_genre_for_mode(mode)
    except ImportError:
        mapping = {
            "urban_power": "都市", "general": "通用", "xianxia": "玄幻/仙侠",
            "xuanhuan": "玄幻/仙侠", "rule_mystery": "悬疑/无限流",
            "romance": "都市", "folk_horror": "悬疑/无限流",
        }
        return mapping.get(mode, "通用")
