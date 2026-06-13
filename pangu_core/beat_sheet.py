#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI Beat Sheet — 章节级故事节拍约束模块

受 Sudowrite Story Engine 启发，将章节拆为3-5个beat（故事节拍），
每个beat有明确的目标、情绪、字数，确保AI按节拍逐段生成，避免跑偏。

核心区别：
  - 大纲："这章要写什么"（一句话）
  - Beat Sheet："这章每200-500字要达成什么"（3-5条结构化指令）

来源：从 pangu_optimized.py 的 _generate_beat_sheet / _inject_beat_sheet 提取重构，
增加：多模式模板、平台适配、伏笔联动、自动持久化。

使用方式：
  from pangu_core.beat_sheet import generate_beat_sheet, inject_beat_sheet

  # 生成节拍（会自动持久化到 state.json）
  beats = generate_beat_sheet(project_dir, chapter_num, chapter_task, mode, call_ai_func=...)

  # 注入到 prompt
  injection = inject_beat_sheet(state, chapter_num)
  system_msg += injection
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


# ============================================================
# 多模式 Beat 模板库
# ============================================================

# 四阶段结构模板（黄金三章 / 前期 / 中期 / 后期）
# 每个模板包含 3-5 个 beat

TEMPLATES = {
    "golden_three": [
        {"beat": "开场冲击", "goal": "以动作/对话/冲突开场，3句内抓住读者", "mood": "紧张/好奇", "words": 300},
        {"beat": "核心展示", "goal": "展示主角核心特质和金手指", "mood": "震撼/期待", "words": 500},
        {"beat": "冲突升级", "goal": "引入第一个对手或障碍，主角应对", "mood": "紧迫", "words": 600},
        {"beat": "章末钩子", "goal": "留下悬念或反转，让读者必须翻下一章", "mood": "震惊/渴望", "words": 400},
    ],
    "early": [
        {"beat": "承接上文", "goal": "延续前章钩子，推进情节", "mood": "延续前章", "words": 350},
        {"beat": "世界观展示", "goal": "通过事件展示新设定/新角色，不是说明文", "mood": "新奇/兴奋", "words": 500},
        {"beat": "爽点爆发", "goal": "主角展现能力或获得新资源，给读者爽感", "mood": "爽快/满足", "words": 600},
        {"beat": "新悬念", "goal": "引入新的疑问或更大的威胁", "mood": "期待/不安", "words": 400},
    ],
    "middle": [
        {"beat": "当前困境", "goal": "主角面临本章核心问题", "mood": "紧张/焦虑", "words": 350},
        {"beat": "尝试突破", "goal": "主角主动出击或寻找解决方案", "mood": "希望/行动", "words": 450},
        {"beat": "转折/意外", "goal": "事情不如预期，出现新变量", "mood": "惊讶/紧张", "words": 500},
        {"beat": "新的局面", "goal": "困境部分解决但引出更大问题，或进入下一阶段", "mood": "复杂/期待", "words": 400},
    ],
    "late": [
        {"beat": "最后布局", "goal": "所有线索汇聚，最终对决前的准备", "mood": "暴风前的平静", "words": 300},
        {"beat": "核心对决", "goal": "主角与最终障碍正面碰撞", "mood": "高潮/激烈", "words": 600},
        {"beat": "转折爆发", "goal": "隐藏线索兑现，主角突破极限", "mood": "燃/震撼", "words": 500},
        {"beat": "余韵/新篇", "goal": "收束本章，为最终结局或下一卷铺垫", "mood": "余韵/期待", "words": 400},
    ],
}

# 模式专属beat微调
MODE_OVERRIDES = {
    "mystery": {
        "golden_three": [
            {"beat": "诡异开场", "goal": "以反常现象/诡异细节开场", "mood": "不安/好奇", "words": 300},
            {"beat": "规则揭示", "goal": "部分展示规则，但留下关键缺失", "mood": "紧张/困惑", "words": 500},
            {"beat": "第一次违规", "goal": "有人违反规则，展示后果", "mood": "恐惧/震惊", "words": 600},
            {"beat": "新规则出现", "goal": "发现更深层规则，悬念升级", "mood": "毛骨悚然", "words": 400},
        ],
        "middle": [
            {"beat": "规则困境", "goal": "主角陷入规则矛盾，看似无解", "mood": "窒息/绝望", "words": 350},
            {"beat": "寻找漏洞", "goal": "主角分析规则，发现可能的突破口", "mood": "希望/紧张", "words": 400},
            {"beat": "规则突变", "goal": "规则突然变化，之前的分析失效", "mood": "震惊/恐惧", "words": 500},
            {"beat": "代价发现", "goal": "找到突破口但代价惨重", "mood": "纠结/沉重", "words": 450},
        ],
    },
    "xianxia": {
        "early": [
            {"beat": "承接上文", "goal": "延续前章修炼/战斗进展", "mood": "延续", "words": 350},
            {"beat": "境界突破", "goal": "展示新境界/新能力的效果", "mood": "震撼/兴奋", "words": 500},
            {"beat": "试炼/对战", "goal": "新能力第一次实战，碾压或险胜", "mood": "爽快/燃", "words": 600},
            {"beat": "更大危机", "goal": "暴露更大威胁或更强对手", "mood": "期待/不安", "words": 400},
        ],
    },
    "romance": {
        "middle": [
            {"beat": "暧昧张力", "goal": "男女主互动，拉扯感升级", "mood": "心动/甜蜜", "words": 350},
            {"beat": "误会/阻隔", "goal": "出现新障碍或误会", "mood": "揪心/焦急", "words": 450},
            {"beat": "转折揭示", "goal": "误会部分解开或新信息揭示", "mood": "感动/心疼", "words": 500},
            {"beat": "情感升级", "goal": "关系实质推进但留下新悬念", "mood": "甜蜜/期待", "words": 400},
        ],
    },
    "urban_power": {
        "golden_three": [
            {"beat": "打脸开场", "goal": "以冲突/打脸场景开场", "mood": "憋屈→爽", "words": 300},
            {"beat": "背景/实力展示", "goal": "展示主角隐藏实力或背景", "mood": "期待/爽", "words": 500},
            {"beat": "碾压/反击", "goal": "主角出手，实力碾压对手", "mood": "极度爽快", "words": 600},
            {"beat": "更大来头", "goal": "对手背后有更大势力，引出下章", "mood": "期待/兴奋", "words": 400},
        ],
    },
}

# 平台beat适配（微调字数和节奏）
PLATFORM_ADJUST = {
    "fanqie": {"words_factor": 0.85, "min_beats": 4, "max_beats": 5},  # 番茄节奏更快
    "qimao": {"words_factor": 1.0, "min_beats": 3, "max_beats": 4},    # 七猫标准节奏
    "qidian": {"words_factor": 1.15, "min_beats": 3, "max_beats": 5},  # 起点允许更慢
}


# ============================================================
# 核心函数
# ============================================================

def generate_beat_sheet(
    project_dir: str,
    chapter_num: int,
    chapter_task: str,
    mode: str = "general",
    platform: str = "qimao",
    call_ai_func: Optional[Callable] = None,
    total_chapters: int = 100,
) -> List[Dict[str, Any]]:
    """
    生成章节级 Beat Sheet。

    优先级：
    1. state.json 中已有的 beat_sheet → 直接使用
    2. AI 生成（需要 call_ai_func）
    3. 模板生成（降级方案，不依赖AI）

    生成后自动持久化到 state.json。

    Args:
        project_dir: 项目目录路径
        chapter_num: 当前章节号
        chapter_task: 章节任务描述
        mode: 写作模式 (general/xianxia/mystery/romance/...)
        platform: 平台 (qimao/fanqie/qidian)
        call_ai_func: AI调用函数（可选）
        total_chapters: 预计总章数

    Returns:
        List[Dict]: beat列表，每个beat包含 {beat, goal, mood, words}
    """
    state_path = Path(project_dir) / "state.json"
    state = _load_state(state_path)

    # 1. 检查已有
    existing = state.get("beat_sheet", {}).get(str(chapter_num))
    if existing and isinstance(existing, list) and len(existing) >= 2:
        logger.info(f"Beat Sheet: 使用已有的第{chapter_num}章节拍({len(existing)}个beat)")
        return existing

    # 2. AI生成
    if call_ai_func:
        beats = _generate_with_ai(state, chapter_num, chapter_task, mode, call_ai_func)
        if beats:
            _save_beats(state, state_path, chapter_num, beats)
            return beats

    # 3. 模板生成
    beats = _generate_from_template(state, chapter_num, chapter_task, mode, platform, total_chapters)
    _save_beats(state, state_path, chapter_num, beats)
    return beats


def inject_beat_sheet(state: Dict, chapter_num: int) -> str:
    """
    将 Beat Sheet 注入 prompt，作为写作的强制约束。

    Args:
        state: 项目 state.json 的内容
        chapter_num: 当前章节号

    Returns:
        str: 注入到 system_msg 的文本（空字符串表示无节拍）
    """
    beat_sheet = state.get("beat_sheet", {})
    chapter_beats = beat_sheet.get(str(chapter_num))
    if not chapter_beats:
        return ""

    if not isinstance(chapter_beats, list) or len(chapter_beats) == 0:
        return ""

    lines = ["本章必须严格按照以下故事节拍（Beat Sheet）生成，不得遗漏任何节拍："]
    total_words = 0
    for i, beat in enumerate(chapter_beats):
        if not isinstance(beat, dict):
            continue
        beat_name = beat.get("beat", f"节拍{i+1}")
        goal = beat.get("goal", "")
        mood = beat.get("mood", "")
        words = beat.get("words", 400)
        total_words += words
        mood_str = f", 情绪: {mood}" if mood else ""
        lines.append(f"  Beat {i+1} [{beat_name}] ({words}字): 目标 -- {goal}{mood_str}")

    lines.append(f"\n总字数约{total_words}字。每个beat必须完整达成目标后才能进入下一个beat。")
    lines.append("[FORCE] Beat Sheet是强制约束，不是建议。如果最终输出缺少任何beat的目标，视为生成失败。")

    return "\n".join(lines)


def build_and_inject_beat_sheet(
    project_dir: str,
    chapter_num: int,
    chapter_task: str,
    mode: str = "general",
    platform: str = "qimao",
    call_ai_func: Optional[Callable] = None,
) -> str:
    """
    一站式：生成 + 注入。适用于在 workflow_engine 中直接调用。

    Returns:
        str: 注入文本（空字符串表示无节拍）
    """
    try:
        beats = generate_beat_sheet(
            project_dir, chapter_num, chapter_task, mode, platform, call_ai_func
        )
        if not beats:
            return ""

        # 重新加载state（generate可能已更新）
        state = _load_state(Path(project_dir) / "state.json")
        return inject_beat_sheet(state, chapter_num)
    except Exception as e:
        logger.warning(f"Beat Sheet生成注入失败: {e}")
        return ""


def get_beat_compliance_report(content: str, beats: List[Dict]) -> Dict[str, Any]:
    """
    检查生成内容是否满足 Beat Sheet 约束。

    简化版：基于字数分布检查每个beat是否被覆盖。
    """
    if not beats or not content:
        return {"compliant": True, "coverage": 0.0, "missing_beats": [], "details": []}

    total_beats = len(beats)
    total_words_target = sum(b.get("words", 400) for b in beats if isinstance(b, dict))
    content_len = len(content)

    # 按比例切分内容，检查每个段落
    details = []
    missing_beats = []
    covered = 0

    # 粗略：按字数比例切分，检查每个段落的关键词
    cursor = 0
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            continue
        beat_words = beat.get("words", 400)
        ratio = beat_words / max(total_words_target, 1)
        seg_end = min(int(cursor + content_len * ratio), content_len)
        segment = content[cursor:seg_end]
        cursor = seg_end

        goal = beat.get("goal", "")
        beat_name = beat.get("beat", f"节拍{i+1}")

        # 简单关键词检查（从goal中提取2-4字关键词）
        keywords = _extract_keywords(goal)
        found = [kw for kw in keywords if kw in segment]

        is_covered = len(found) >= max(1, len(keywords) * 0.3)
        if is_covered:
            covered += 1
        else:
            missing_beats.append(beat_name)

        details.append({
            "beat": beat_name,
            "goal": goal[:40],
            "keywords": keywords,
            "keywords_found": found,
            "covered": is_covered,
        })

    coverage = covered / max(total_beats, 1)
    return {
        "compliant": coverage >= 0.75,
        "coverage": round(coverage, 2),
        "missing_beats": missing_beats,
        "details": details,
    }


# ============================================================
# 内部函数
# ============================================================

def _load_state(state_path: Path) -> Dict:
    """加载 state.json"""
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载state.json失败: {e}")
    return {}


def _save_beats(state: Dict, state_path: Path, chapter_num: int, beats: List[Dict]):
    """将beat保存到state.json"""
    if "beat_sheet" not in state:
        state["beat_sheet"] = {}
    state["beat_sheet"][str(chapter_num)] = beats
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logger.info(f"Beat Sheet: 第{chapter_num}章{len(beats)}个beat已持久化")
    except Exception as e:
        logger.warning(f"Beat Sheet持久化失败: {e}")


def _generate_with_ai(
    state: Dict, chapter_num: int, chapter_task: str, mode: str, call_ai_func: Callable
) -> Optional[List[Dict]]:
    """用AI生成Beat Sheet"""
    info = state.get("project_info", {})
    title = info.get("title", "")

    beat_prompt = f"""你是一位资深网文编辑，请为以下章节生成Beat Sheet（故事节拍）。

小说：《{title}》
模式：{mode}
第{chapter_num}章
章节任务：{chapter_task}

Beat Sheet格式要求：
- 将章节拆为3-5个beat（故事节拍）
- 每个beat约300-500字
- 每个beat必须有明确的目标和情绪
- beat之间必须有因果关系，不能跳跃
- 最后一个beat必须是钩子（让读者想看下一章）

请严格按以下JSON格式输出，不要输出任何其他内容：
[
  {{"beat": "节拍名称", "goal": "本段目标", "mood": "情绪基调", "words": 400}},
  ...
]"""

    try:
        result = call_ai_func(
            beat_prompt,
            system_msg="你是资深网文编辑，擅长拆解章节节奏。只输出JSON，不要其他内容。"
        )
        if result:
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                beats = json.loads(json_match.group())
                if isinstance(beats, list) and len(beats) >= 2:
                    # 验证每个beat结构
                    valid_beats = []
                    for b in beats:
                        if isinstance(b, dict) and "beat" in b and "goal" in b:
                            b.setdefault("mood", "")
                            b.setdefault("words", 400)
                            valid_beats.append(b)
                    if len(valid_beats) >= 2:
                        logger.info(f"Beat Sheet: AI生成{len(valid_beats)}个beat")
                        return valid_beats
    except Exception as e:
        logger.warning(f"AI生成Beat Sheet失败，降级到模板: {e}")

    return None


def _generate_from_template(
    state: Dict,
    chapter_num: int,
    chapter_task: str,
    mode: str,
    platform: str,
    total_chapters: int = 100,
) -> List[Dict]:
    """从模板生成Beat Sheet（降级方案）"""
    info = state.get("project_info", {})
    if total_chapters <= 0:
        total_chapters = info.get("target_chapters", 100)

    position = chapter_num / max(total_chapters, 1)

    # 选择阶段模板
    if chapter_num <= 3:
        stage_key = "golden_three"
    elif position < 0.15:
        stage_key = "early"
    elif position < 0.7:
        stage_key = "middle"
    else:
        stage_key = "late"

    # 查找模式专属模板，否则用通用模板
    mode_key = mode.split("_")[0] if "_" in mode else mode  # rule_mystery → rule
    # 也检查完整mode
    mode_overrides = MODE_OVERRIDES.get(mode) or MODE_OVERRIDES.get(mode_key)

    if mode_overrides and stage_key in mode_overrides:
        beats = [b.copy() for b in mode_overrides[stage_key]]
    else:
        beats = [b.copy() for b in TEMPLATES[stage_key]]

    # 平台适配：调整字数和beat数量
    platform_cfg = PLATFORM_ADJUST.get(platform, {})
    words_factor = platform_cfg.get("words_factor", 1.0)
    for b in beats:
        b["words"] = int(b.get("words", 400) * words_factor)

    # 用chapter_task定制第一个beat
    if chapter_task:
        beats[0]["goal"] = f"{chapter_task} -- {beats[0]['goal']}"

    # 伏笔联动：如果有未收的伏笔，在最后一个beat前插入伏笔推进
    foreshadowing = state.get("foreshadowing", [])
    if isinstance(foreshadowing, list) and len(foreshadowing) > 0:
        # 找出未收伏笔
        open_foreshadows = [
            f for f in foreshadowing
            if isinstance(f, dict) and f.get("status") in ("planted", "open", "active")
        ]
        if open_foreshadows:
            # 在倒数第一个beat之前插入一个伏笔推进beat
            last_open = open_foreshadows[-1]
            foreshadow_name = last_open.get("name", last_open.get("description", "未命名伏笔"))
            insert_idx = len(beats) - 1  # 倒数第二位
            beats.insert(insert_idx, {
                "beat": "伏笔推进",
                "goal": f"推进伏笔「{foreshadow_name}」的线索",
                "mood": "悬念/暗示",
                "words": int(300 * words_factor),
            })

    logger.info(f"Beat Sheet: 模板生成{len(beats)}个beat ({stage_key}/{mode})")
    return beats


def _extract_keywords(text: str) -> List[str]:
    """从目标文本中提取2-4字关键词"""
    # 去除标点和常见虚词
    stop_chars = set("的了在是我有和就不人都一上也很到说要去你会着没看好自己这那他她它们")
    # 简单按2-4字窗口提取
    cleaned = re.sub(r'[^\u4e00-\u9fff]', '', text)
    keywords = []

    # 2字词
    for i in range(len(cleaned) - 1):
        word = cleaned[i:i+2]
        if not any(c in stop_chars for c in word):
            keywords.append(word)

    # 3字词（覆盖面更精准）
    for i in range(len(cleaned) - 2):
        word = cleaned[i:i+3]
        if not any(c in stop_chars for c in word):
            keywords.append(word)

    # 去重、取前10
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) >= 2:
            seen.add(kw)
            unique.append(kw)
            if len(unique) >= 10:
                break

    return unique
