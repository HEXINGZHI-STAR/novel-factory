#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质量分析模块 - 从 pangu.py 提取
提供完整的13维文本质量分析功能
"""

import re
import math
from collections import Counter
from typing import Dict, Any


# ============================================================
# 关键词词典
# ============================================================
ACTION_WORDS = [
    "冲", "杀", "砍", "刺", "斩", "挥", "劈", "射", "飞", "跑",
    "跳", "躲", "闪", "挡", "击", "踢", "打", "抓", "握", "拿",
    "提", "扔", "抛", "掷", "推", "拉", "扯", "拽", "拖", "抱",
    "追", "逃", "退", "进", "攻", "守", "战", "斗", "搏", "拼",
    "怒", "喝", "吼", "叫", "喊", "笑", "哭", "怒视", "冷笑", "狞笑",
]

EMOTION_WORDS = [
    "喜", "怒", "哀", "乐", "悲", "愁", "烦", "恼", "恨", "爱",
    "怕", "惊", "疑", "慌", "羞", "愧", "悔", "怨", "怒", "急",
    "痛", "苦", "闷", "愁", "烦", "躁", "怒不可遏", "怒火中烧", "悲愤",
    "喜出望外", "惊喜", "震惊", "惊恐", "恐惧", "畏惧", "害怕",
    "悲伤", "悲痛", "哀伤", "伤心", "难过", "忧郁", "沮丧",
    "愤怒", "恼怒", "气愤", "暴怒", "愤慨", "怨恨", "憎恶",
    "开心", "高兴", "快乐", "愉快", "喜悦", "兴奋", "激动",
    "失望", "绝望", "失落", "无助", "迷茫", "困惑", "疑惑",
]

DESCRIPTION_WORDS = [
    "美丽", "漂亮", "丑陋", "英俊", "潇洒", "丑陋", "肮脏", "干净",
    "高大", "矮小", "肥胖", "瘦弱", "强壮", "虚弱", "年轻", "年老",
    "明亮", "黑暗", "温暖", "寒冷", "炎热", "凉爽", "潮湿", "干燥",
    "安静", "喧闹", "嘈杂", "寂静", "热闹", "冷清", "繁华", "荒凉",
    "神秘", "诡异", "恐怖", "可怕", "危险", "安全", "舒适", "痛苦",
]

TRANSITION_WORDS = [
    "但是", "可是", "然而", "不过", "虽然", "尽管", "即使", "假如",
    "如果", "要是", "万一", "一旦", "只要", "只有", "除非", "否则",
    "因此", "所以", "于是", "从而", "结果", "导致", "致使", "使得",
    "首先", "其次", "接着", "然后", "最后", "终于", "后来", "不久",
    "突然", "忽然", "猛然", "骤然", "渐渐", "慢慢", "缓缓", "悄悄",
]

PASSIVE_WORDS = [
    "被", "遭", "受", "挨", "给", "让", "叫", "为...所", "予以",
]

HOOK_PATTERNS = [
    r"却见", r"只见", r"原来", r"竟然", r"居然",
    r"秘密", r"真相", r"真相大白", r"惊人", r"恐怖", r"诡异", r"可怕",
    r"未完", r"待续", r"欲知", r"下回",
]

AI_TEMPLATE_WORDS = [
    "首先", "其次", "最后", "综上所述", "一言以蔽之", "总而言之",
    "可以看出", "不难发现", "值得一提", "需要说明", "众所周知",
    "一般来说", "从某种意义上说", "在一定程度上", "不可否认",
    "不难理解", "显而易见", "毋庸讳言", "毫无疑问", "归根结底",
]


# ============================================================
# 核心分析函数
# ============================================================

def analyze_text(text: str) -> Dict[str, Any]:
    """
    对一段正文做完整分析，返回 style_vector 和 information_metrics
    
    Args:
        text: 要分析的文本
        
    Returns:
        包含以下字段的字典:
        - style_vector: 13维风格向量
        - information_metrics: 信息论度量
        - hook_strength: 钩子强度 (0-1)
        - has_hook: 是否包含钩子
        - total_chars: 总字符数
        - total_words: 总词数
        - n_sentences: 句子数
        - n_paragraphs: 段落数
    """
    if not text or not text.strip():
        empty = {k: 0.0 for k in ["dialogue_ratio", "action_density", "sentence_variance",
                                   "emotion_mean", "self_transition", "narrative_ratio",
                                   "description_ratio"]}
        info = {k: 0.0 for k in ["avg_sentence_length", "type_token_ratio",
                                  "vocabulary_richness", "paragraph_density",
                                  "transition_word_ratio", "passive_voice_ratio"]}
        return {"style_vector": empty, "information_metrics": info,
                "hook_strength": 0, "has_hook": False,
                "total_chars": 0, "total_words": 0,
                "n_sentences": 0, "n_paragraphs": 0}

    # 分段
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\r\n\s*\r\n', text) if p.strip()]
    n_paragraphs = max(len(paragraphs), 1)

    # 分句 (按 。！？!?. 以及换行)
    sentences = [s.strip() for s in re.split(r'[。！？!?~]+|\n', text) if s.strip()]
    n_sentences = max(len(sentences), 1)

    total_chars = len(text)
    # 中文词数 = 中文字符数，英文词数 = 空格分隔的词数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    total_words = chinese_chars + english_words

    # 对话检测: 「」""'' 引号内的内容
    dialogue_parts = re.findall(r'[「"“\'‘]([^」"”\'’]{0,200})[」"”\'’]', text)
    dialogue_chars = sum(len(d) for d in dialogue_parts)

    # 风格特征计算
    sentence_lengths = [len(s) for s in sentences]
    avg_sentence_len = sum(sentence_lengths) / n_sentences if n_sentences else 20.0
    sentence_variance = 0.0
    if n_sentences > 1:
        mean_len = avg_sentence_len
        std_len = math.sqrt(sum((l - mean_len) ** 2 for l in sentence_lengths) / n_sentences)
        sentence_variance = std_len / max(mean_len, 20.0)
        sentence_variance = min(sentence_variance, 1.0)

    # 动作/情感/叙述/描写 关键词计数
    action_count = sum(text.count(w) for w in ACTION_WORDS)
    emotion_count = sum(text.count(w) for w in EMOTION_WORDS)
    desc_count = sum(text.count(w) for w in DESCRIPTION_WORDS)
    transition_count = sum(text.count(w) for w in TRANSITION_WORDS)
    passive_count = sum(1 for w in PASSIVE_WORDS if w in text)

    # 归一化
    char_scale = max(total_chars, 100)
    dialogue_ratio = min(dialogue_chars / char_scale, 1.0)
    density_scale = 20.0
    action_density = min(action_count / char_scale * density_scale, 1.0)
    emotion_mean = min(emotion_count / char_scale * density_scale, 1.0)
    description_ratio = min(desc_count / char_scale * density_scale, 1.0)

    # 叙述比例 = 剩余部分
    narr = max(1.0 - dialogue_ratio - action_density - description_ratio, 0.0)

    # 自相关性: 相邻句子长度变化
    self_trans = 0.0
    if n_sentences > 3:
        similar_count = 0
        total_pairs = 0
        for i in range(n_sentences - 1):
            if sentence_lengths[i] > 0 and sentence_lengths[i + 1] > 0:
                ratio = min(sentence_lengths[i], sentence_lengths[i + 1]) / max(sentence_lengths[i], sentence_lengths[i + 1])
                if ratio > 0.7:
                    similar_count += 1
                total_pairs += 1
        self_trans = similar_count / max(total_pairs, 1)
        self_trans = min(self_trans, 1.0)

    # 情感方差
    emo_per_sent = [sum(s.count(w) for w in EMOTION_WORDS) for s in sentences]
    emotion_variance = 0.0
    if n_sentences > 1:
        mean_emo = sum(emo_per_sent) / n_sentences
        if mean_emo > 0:
            emo_std = math.sqrt(sum((e - mean_emo) ** 2 for e in emo_per_sent) / n_sentences)
            emotion_variance = emo_std / max(total_chars / 100, 10)
            emotion_variance = min(emotion_variance, 0.05)

    # 信息论度量
    chinese_list = re.findall(r'[\u4e00-\u9fff]', text)
    if chinese_list:
        unique_chars = len(set(chinese_list))
        type_token_ratio = unique_chars / len(chinese_list)
    else:
        type_token_ratio = 0.0

    # 词汇丰富度 (bi-gram 多样性)
    bigrams = []
    for i in range(len(chinese_list) - 1):
        bigrams.append(chinese_list[i] + chinese_list[i+1])
    unique_bigrams = len(set(bigrams)) if bigrams else 0
    bigram_entropy = 0.0
    if bigrams:
        freq = Counter(bigrams)
        total_b = len(bigrams)
        for count in freq.values():
            p = count / total_b
            bigram_entropy -= p * math.log2(p)

    vocab_richness = unique_bigrams / max(len(bigrams), 1) if bigrams else type_token_ratio

    # ngram_unique: unique bigram ratio
    length_factor = min(1.0, len(chinese_list) / 5000.0)
    ngram_unique = min(vocab_richness * length_factor, 1.0)

    # 段落密度
    paragraph_density = n_paragraphs / max(total_chars / 500, 1)
    paragraph_density = min(paragraph_density, 1.0)

    # 过渡词比例
    transition_word_ratio = min(transition_count / max(n_sentences / 10, 1), 1.0)

    # 被动语态比例
    passive_voice_ratio = min(passive_count / max(n_sentences / 5, 1), 1.0)

    # sentence_len norm
    sentence_len_norm = avg_sentence_len / 200.0
    sentence_len_norm = max(0.0, min(sentence_len_norm, 0.5))

    # paragraph_len norm
    paragraph_len_norm = n_paragraphs / max(total_chars, 100)
    paragraph_len_norm = max(0.0, min(paragraph_len_norm, 0.2))

    # zipf_r2
    zipf_r2 = max(0.0, min(1.0, 0.5 + (type_token_ratio - 0.25) * 1.5))

    # complexity
    emo_var_comp = min(emotion_variance * 20, 1.0)
    complexity = (sentence_variance + ngram_unique + (1.0 - self_trans) + emo_var_comp) / 4.0
    complexity = max(0.0, min(complexity, 1.0))

    # 钩子强度 (章末 300 字检测)
    last_300 = text[-300:] if len(text) > 300 else text
    hook_score = 0.0
    for pattern in HOOK_PATTERNS:
        if re.search(pattern, last_300):
            hook_score += 0.2
    hook_strength = min(hook_score, 1.0)
    has_hook = hook_strength >= 0.4

    return {
        "style_vector": {
            "dialogue_ratio": round(dialogue_ratio, 4),
            "action_density": round(action_density, 4),
            "sentence_variance": round(sentence_variance, 4),
            "emotion_mean": round(emotion_mean, 4),
            "self_transition": round(self_trans, 4),
            "zipf_r2": round(zipf_r2, 4),
            "bigram_entropy": round(bigram_entropy, 4),
            "sentence_len": round(sentence_len_norm, 4),
            "ngram_unique": round(ngram_unique, 4),
            "complexity": round(complexity, 4),
            "paragraph_len": round(paragraph_len_norm, 4),
            "hook_strength": round(hook_strength, 4),
            "emotion_variance": round(emotion_variance, 4),
            "narrative_ratio": round(narr, 4),
            "description_ratio": round(description_ratio, 4),
        },
        "information_metrics": {
            "avg_sentence_length": round(avg_sentence_len, 1),
            "type_token_ratio": round(type_token_ratio, 4),
            "vocabulary_richness": round(vocab_richness, 4),
            "paragraph_density": round(paragraph_density, 4),
            "transition_word_ratio": round(transition_word_ratio, 4),
            "passive_voice_ratio": round(passive_voice_ratio, 4),
        },
        "hook_strength": round(hook_strength, 4),
        "has_hook": has_hook,
        "total_chars": total_chars,
        "total_words": total_words,
        "n_sentences": n_sentences,
        "n_paragraphs": n_paragraphs,
    }


def detect_ai_template_words(text: str) -> Dict[str, Any]:
    """
    检测AI模板词汇
    
    Args:
        text: 要检测的文本
        
    Returns:
        包含检测结果的字典
    """
    hits = []
    for word in AI_TEMPLATE_WORDS:
        if word in text:
            count = text.count(word)
            hits.append({"word": word, "count": count})
    
    return {
        "ai_word_count": len(hits),
        "hits": hits,
        "has_ai_pattern": len(hits) >= 5,
    }


def analyze_chapter_quality(text: str) -> Dict[str, Any]:
    """
    综合分析章节质量，返回结构化报告
    
    Args:
        text: 章节文本
        
    Returns:
        质量分析报告
    """
    analysis = analyze_text(text)
    ai_detection = detect_ai_template_words(text)
    
    issues = []
    
    # AI味检测
    if ai_detection["ai_word_count"] >= 5:
        issues.append({
            "severity": "WARNING",
            "category": "AI模板词",
            "detail": f"发现{ai_detection['ai_word_count']}个AI模板词",
            "suggestion": "建议替换为更具个人风格的描写",
            "hits": ai_detection["hits"][:10],
        })
    
    # 字数检测
    char_count = analysis.get("total_chars", 0)
    if char_count < 500:
        issues.append({
            "severity": "FATAL",
            "category": "篇幅不足",
            "detail": f"章节仅 {char_count} 字，过短",
            "suggestion": "建议扩充到 1500 字以上",
        })
    elif char_count > 8000:
        issues.append({
            "severity": "WARNING",
            "category": "篇幅过长",
            "detail": f"章节 {char_count} 字，偏长",
            "suggestion": "考虑拆分为两章",
        })
    
    # 钩子检测
    if not analysis.get("has_hook", False):
        issues.append({
            "severity": "INFO",
            "category": "章末钩子",
            "detail": "章末未检测到钩子",
            "suggestion": "建议在章节末尾设置悬念或伏笔",
        })
    
    # 对话率检测
    dialogue_ratio = analysis["style_vector"].get("dialogue_ratio", 0)
    if dialogue_ratio < 0.15:
        issues.append({
            "severity": "INFO",
            "category": "对话率",
            "detail": f"对话率 {dialogue_ratio:.2f}，偏低",
            "suggestion": "适当增加对话，让故事更生动",
        })
    elif dialogue_ratio > 0.55:
        issues.append({
            "severity": "INFO",
            "category": "对话率",
            "detail": f"对话率 {dialogue_ratio:.2f}，偏高",
            "suggestion": "适当增加叙述和描写",
        })
    
    # 句长检测
    avg_sentence_len = analysis["information_metrics"].get("avg_sentence_length", 0)
    if avg_sentence_len > 30:
        issues.append({
            "severity": "WARNING",
            "category": "平均句长",
            "detail": f"平均句长 {avg_sentence_len:.1f} 字，偏长",
            "suggestion": "适当拆分长句，提高可读性",
        })
    
    return {
        "analysis": analysis,
        "ai_detection": ai_detection,
        "issues": issues,
        "overall_score": _calculate_overall_score(analysis, ai_detection),
    }


def _calculate_overall_score(analysis: Dict, ai_detection: Dict) -> float:
    """
    计算综合质量分数
    
    Args:
        analysis: 文本分析结果
        ai_detection: AI模板词检测结果
        
    Returns:
        综合分数 (0-100)
    """
    score = 60.0
    
    # 字数分 (20分)
    char_count = analysis.get("total_chars", 0)
    if 1500 <= char_count <= 5000:
        score += 20
    elif 1000 <= char_count < 1500:
        score += 10
    elif 500 <= char_count < 1000:
        score += 5
    
    # 钩子分 (10分)
    if analysis.get("has_hook", False):
        score += 10
    elif analysis.get("hook_strength", 0) >= 0.2:
        score += 5
    
    # AI味扣分 (-20分)
    ai_count = ai_detection.get("ai_word_count", 0)
    if ai_count >= 10:
        score -= 20
    elif ai_count >= 5:
        score -= 10
    
    # 对话率分 (10分)
    dialogue_ratio = analysis["style_vector"].get("dialogue_ratio", 0)
    if 0.15 <= dialogue_ratio <= 0.55:
        score += 10
    
    return min(100.0, max(0.0, score))