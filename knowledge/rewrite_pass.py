#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 精简版分维度改写（3轮）
从5轮精简为3轮，减少API调用次数，集成到主流程：
  Pass 1: 钩子+对话 (合并原P1+P2)
  Pass 2: 情绪+动作 (合并原P3+P4)
  Pass 3: 润色+去AI味 (原P5)
"""

import re
import math
from typing import Dict, Any, Optional, Callable


def run_rewrite_passes(
    content: str,
    call_ai_func: Callable,
    platform: str = "qimao",
    chapter_num: int = 1,
    quality_threshold: float = 70.0,
    max_passes: int = 3,
) -> Dict[str, Any]:
    """
    执行分维度迭代改写，直到质量达标或达到最大轮次。

    参数:
        content: 待改写的章节文本
        call_ai_func: AI调用函数 (prompt, system_msg=None) -> str
        platform: 目标平台
        chapter_num: 章节编号
        quality_threshold: 质量阈值（数学评分），低于此值继续改写
        max_passes: 最大改写轮次

    返回:
        {
            "final_content": str,       # 最终文本
            "initial_score": float,     # 初始评分
            "final_score": float,       # 最终评分
            "passes_done": int,         # 实际执行轮次
            "improved": bool,           # 是否有提升
            "trail": [...],             # 每轮记录
        }
    """
    trail = []
    current_text = content

    # 初始评分
    initial_score = _quick_score(current_text)
    current_score = initial_score

    for pass_num in range(1, max_passes + 1):
        # 如果已经达标，提前停止
        if current_score >= quality_threshold:
            break

        # 选择本轮改写策略
        if pass_num == 1:
            system_msg, focus = _pass1_system(platform), "钩子+对话"
        elif pass_num == 2:
            system_msg, focus = _pass2_system(platform), "情绪+动作"
        else:
            system_msg, focus = _pass3_system(platform), "润色+去AI味"

        # 调用AI改写
        user_msg = f"请改写以下章节，重点优化{focus}。保留原有情节100%不变，直接输出改写后正文。\n\n--- 原文 ---\n{current_text.strip()}"

        rewritten = call_ai_func(user_msg, system_msg=system_msg)

        if not rewritten or len(rewritten.strip()) < 200:
            # 改写失败，跳过本轮
            trail.append({"pass": pass_num, "focus": focus, "score_before": current_score, "score_after": current_score, "status": "failed"})
            continue

        # 评分
        new_score = _quick_score(rewritten)

        trail.append({
            "pass": pass_num,
            "focus": focus,
            "score_before": current_score,
            "score_after": new_score,
            "status": "improved" if new_score > current_score else "no_improvement",
        })

        # 只有提升时才采用新版本
        if new_score > current_score:
            current_text = rewritten
            current_score = new_score

    return {
        "final_content": current_text,
        "initial_score": round(initial_score, 1),
        "final_score": round(current_score, 1),
        "passes_done": len(trail),
        "improved": current_score > initial_score,
        "trail": trail,
    }


def _quick_score(text: str) -> float:
    """
    快速质量评分（0-100），不依赖pangu_math_core。
    基于统计指标：句长、句长变异、对话率、AI味词密度。
    """
    if not text or len(text) < 100:
        return 30.0

    score = 50.0  # 基线

    # 1. 句长分析 (权重30%)
    sentences = [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]
    if len(sentences) >= 3:
        lengths = [len(s) for s in sentences]
        mean_len = sum(lengths) / len(lengths)

        # 平均句长加分 (目标25-35字)
        if mean_len >= 25:
            score += 10
        elif mean_len >= 20:
            score += 5

        # 句长变异加分 (CV >= 0.3)
        if mean_len > 0:
            std_len = (sum((l - mean_len)**2 for l in lengths) / len(lengths)) ** 0.5
            cv = std_len / mean_len
            if cv >= 0.30:
                score += 10
            elif cv >= 0.20:
                score += 5

    # 2. 对话率 (权重20%)
    total_chars = len(text.replace('\n', '').replace(' ', ''))
    dialogue_chars = sum(len(m.group()) for m in re.finditer(r'["""][^""""]+?["\u201d"]', text))
    dialogue_ratio = dialogue_chars / max(total_chars, 1)
    if dialogue_ratio >= 0.30:
        score += 10
    elif dialogue_ratio >= 0.20:
        score += 5

    # 3. AI味词扣分 (权重30%)
    ai_words = ["他感到", "他心中", "他暗道", "缓缓地", "淡淡地", "微微地", "静静地", "轻轻地",
                "忽然", "突然", "猛然", "骤然", "不是……而是", "不是...而是",
                "瞳孔骤然", "嘴角勾起", "倒吸一口", "心中一惊", "心中一沉"]
    ai_count = sum(text.count(w) for w in ai_words)
    per_1000 = ai_count / max(len(text) / 1000, 1)
    if per_1000 <= 1:
        score += 10
    elif per_1000 <= 3:
        score += 0
    else:
        score -= min(per_1000 * 2, 15)

    # 4. 段落多样性 (权重20%)
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if len(paragraphs) >= 3:
        para_lengths = [len(p) for p in paragraphs]
        max_min_ratio = max(para_lengths) / max(min(para_lengths), 1)
        if max_min_ratio >= 5:
            score += 10
        elif max_min_ratio >= 3:
            score += 5

    return max(0, min(100, score))


# ============ 3轮改写的system prompt ============

def _pass1_system(platform: str) -> str:
    """Pass 1: 钩子+对话"""
    return f"""你是{platform}网文改写专家。本轮只做两件事：
1. 增加钩子：每300-500字插入1个句级钩子（悬疑问句/紧急转换/威胁预告），每3-5段1个段级钩子
2. 提升对话：将超过3句的纯叙述段落改为角色对话，对话率目标≥30%

规则：保留原有情节100%不变，不改叙事视角，不添新剧情线。直接输出改写后正文。"""


def _pass2_system(platform: str) -> str:
    """Pass 2: 情绪+动作"""
    return f"""你是{platform}网文改写专家。本轮只做两件事：
1. 情绪平衡：确保正负情绪比>1:3，建立情绪弧线（压→扬→压→大扬），用具体动作代替"他感到XX"
2. 增加动作：将纯说明/背景介绍段落改为角色行动发现，exposition<40%，action/climax>15%

规则：保留原有情节100%不变，不改叙事视角，不添新剧情线。直接输出改写后正文。"""


def _pass3_system(platform: str) -> str:
    """Pass 3: 润色+去AI味"""
    return f"""你是{platform}网文改写专家。本轮只做两件事：
1. 去AI味：删除所有"他感到/缓缓地/突然/不是…而是/瞳孔/嘴角勾起"等模板表达，替换为个性化描写
2. 感官补全：确保至少激活3种感官（视觉/听觉/触觉/嗅觉），每场景至少1个锚定细节

规则：保留原有情节100%不变，不改叙事视角，不添新剧情线。直接输出改写后正文。"""
