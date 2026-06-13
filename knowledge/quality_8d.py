#!/usr/bin/env python3
"""8维质量评分系统（对标WebNovelBench - EACL 2026）

8个评估维度：
1. 角色塑造 - 角色是否有独特性、行为是否符合人设
2. 情节推进 - 是否有剧情进展、不是原地踏步
3. 对话质量 - 对话是否自然、有信息量、声线差异化
4. 叙事风格 - 文笔是否有质感、不是AI模板
5. 情感深度 - 是否能引起读者情感共鸣
6. 世界构建 - 设定是否自洽、有细节
7. 节奏控制 - 爽点/钩子分布是否合理
8. 创新性 - 是否有反套路元素、不是千篇一律
"""

import re
from collections import Counter


def score_character(text: str, mode: str = "general") -> dict:
    """评分：角色塑造"""
    score = 5.0
    issues = []

    # 检测对话声线差异化
    dialogues = re.findall(r'[""「]([^""」]{5,})[""」]', text)
    if len(dialogues) >= 4:
        lengths = [len(d) for d in dialogues]
        avg = sum(lengths) / len(lengths)
        similar = sum(1 for l in lengths if abs(l - avg) < 5)
        if similar / len(lengths) > 0.8:
            score -= 1.5
            issues.append("对话声线单一，所有角色说话方式一样")
        else:
            score += 1.0

    # 检测角色行为一致性（简单版：检查是否有矛盾词对）
    contradiction_pairs = [("冷静", "暴怒"), ("果断", "犹豫"), ("沉默", "滔滔不绝")]
    for w1, w2 in contradiction_pairs:
        if w1 in text and w2 in text:
            score -= 0.5
            issues.append(f"可能存在角色行为矛盾：'{w1}'vs'{w2}'")

    # 检测角色是否有独特动作
    unique_actions = re.findall(r'(活动右手腕|摩挲|攥紧|咬唇|挑眉|眯眼)', text)
    if unique_actions:
        score += 1.0

    return {"score": max(1, min(10, score)), "issues": issues}


def score_plot(text: str, mode: str = "general") -> dict:
    """评分：情节推进"""
    score = 5.0
    issues = []

    # 检测是否有新事件发生
    event_markers = re.findall(r'(发现|遇到|出现|突然|得知|意识到|决定)', text)
    if len(event_markers) >= 3:
        score += 1.5
    elif len(event_markers) == 0:
        score -= 2.0
        issues.append("本章无剧情推进，纯描写/对话")

    # 检测是否有冲突
    conflict_words = re.findall(r'(对抗|冲突|威胁|危险|矛盾|对峙|拒绝)', text)
    if conflict_words:
        score += 1.0
    else:
        score -= 0.5
        issues.append("缺少冲突/张力")

    return {"score": max(1, min(10, score)), "issues": issues}


def score_dialogue(text: str, mode: str = "general") -> dict:
    """评分：对话质量"""
    score = 5.0
    issues = []

    # 对话率
    dialogues = re.findall(r'[""「]([^""」]+)[""」]', text)
    total_chars = len(text)
    if total_chars > 0:
        dialogue_chars = sum(len(d) for d in dialogues)
        dialogue_ratio = dialogue_chars / total_chars

        if dialogue_ratio >= 0.40:
            score += 2.0
        elif dialogue_ratio >= 0.30:
            score += 1.0
        elif dialogue_ratio < 0.20:
            score -= 1.5
            issues.append(f"对话率过低({dialogue_ratio:.0%})，七猫要求≥40%")

    # 对话信息密度（对话中是否包含新信息）
    info_words = re.findall(r'[""「][^""」]*(发现|知道|告诉|秘密|真相|计划)[^""」]*[""」]', text)
    if info_words:
        score += 1.0

    return {"score": max(1, min(10, score)), "issues": issues}


def score_style(text: str, mode: str = "general") -> dict:
    """评分：叙事风格"""
    score = 5.0
    issues = []

    # AI味词检测
    ai_words = ["缓缓地", "嘴角勾起", "瞳孔骤然", "不禁", "竟然", "瞬间", "微微一笑"]
    ai_count = sum(1 for w in ai_words if w in text)
    if ai_count == 0:
        score += 2.0
    elif ai_count <= 2:
        score += 0.5
    else:
        score -= 1.5
        issues.append(f"AI味词过多({ai_count}个)")

    # 句长变异
    sentences = re.split(r'[。！？]', text)
    sentences = [s for s in sentences if len(s) > 2]
    if len(sentences) >= 5:
        lengths = [len(s) for s in sentences]
        avg = sum(lengths) / len(lengths)
        variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        cv = (variance ** 0.5) / avg if avg > 0 else 0
        if cv >= 0.4:
            score += 1.0
        elif cv < 0.2:
            score -= 1.0
            issues.append("句长过于均匀，AI特征明显")

    return {"score": max(1, min(10, score)), "issues": issues}


def score_emotion(text: str, mode: str = "general") -> dict:
    """评分：情感深度"""
    score = 5.0
    issues = []

    # 检测是否有具体情感锚点（而非标签式情感）
    # 好的情感描写：用动作/物件/场景表达情感
    emotion_anchors = re.findall(r'(手指.*摩挲|攥紧.*拳头|咬紧.*牙|眼眶.*红|声音.*发抖|沉默.*很久)', text)
    if emotion_anchors:
        score += 2.0
    else:
        issues.append("缺少具体情感锚点（动作/物件/场景），只有标签式情感")

    # 检测标签式情感（差）
    label_emotions = re.findall(r'(感到悲伤|非常愤怒|心中一惊|十分害怕|无比兴奋)', text)
    if label_emotions:
        score -= 1.5
        issues.append(f"标签式情感({len(label_emotions)}处)，应用动作/物件替代")

    # 检测Callback（引用前文具体细节）
    callback_patterns = re.findall(r'(还记得|想起.*那|像.*那次|和.*一样)', text)
    if callback_patterns:
        score += 1.0

    return {"score": max(1, min(10, score)), "issues": issues}


def score_worldbuilding(text: str, mode: str = "general") -> dict:
    """评分：世界构建"""
    score = 5.0
    issues = []

    # 检测设定细节
    detail_words = re.findall(r'(符文|阵法|丹药|灵石|星门|空间站|异能|规则|禁忌)', text)
    if detail_words:
        score += 1.5

    # 检测感官描写
    sensory = re.findall(r'(闻到|听到|摸到|尝到|看到|感觉到.*温度|冰冷|灼热|潮湿)', text)
    if len(sensory) >= 2:
        score += 1.0
    elif len(sensory) == 0:
        score -= 0.5
        issues.append("缺少感官描写，世界不够立体")

    return {"score": max(1, min(10, score)), "issues": issues}


def score_pacing(text: str, mode: str = "general") -> dict:
    """评分：节奏控制"""
    score = 5.0
    issues = []

    # 检测章末钩子
    last_200 = text[-200:] if len(text) > 200 else text
    hook_patterns = re.findall(r'(但是|然而|就在这时|突然|不可能|难道|原来|竟然)', last_200)
    if hook_patterns:
        score += 1.5
    else:
        score -= 1.0
        issues.append("章末缺少钩子，读者不会翻下一章")

    # 检测节奏变化（短句加速+长句减速）
    sentences = re.split(r'[。！？]', text)
    sentences = [s for s in sentences if len(s) > 2]
    if len(sentences) >= 10:
        short = sum(1 for s in sentences if len(s) <= 10)
        long = sum(1 for s in sentences if len(s) >= 35)
        if short > 0 and long > 0:
            score += 1.0  # 有节奏变化
        elif short == 0:
            score -= 0.5
            issues.append("缺少短句加速，节奏偏慢")

    return {"score": max(1, min(10, score)), "issues": issues}


def score_novelty(text: str, mode: str = "general") -> dict:
    """评分：创新性"""
    score = 5.0
    issues = []

    # 检测套路桥段
    cliches = [
        ("退婚", "退婚流"),
        ("拍卖会捡漏", "拍卖会捡漏"),
        ("路边捡到神器", "路边捡神器"),
        ("所有女人都爱主角", "后宫套路"),
        ("主角无代价变强", "无代价升级"),
    ]
    cliche_found = []
    for pattern, name in cliches:
        if pattern in text:
            cliche_found.append(name)

    if cliche_found:
        score -= 1.5
        issues.append(f"检测到套路桥段: {'、'.join(cliche_found)}")
    else:
        score += 1.0

    # 检测反转元素
    reversal_patterns = re.findall(r'(但.*不是|反而|却.*原来|出乎意料|反转)', text)
    if reversal_patterns:
        score += 1.0

    return {"score": max(1, min(10, score)), "issues": issues}


def full_8d_score(text: str, mode: str = "general") -> dict:
    """8维全面评分"""
    scorers = [
        ("角色塑造", score_character),
        ("情节推进", score_plot),
        ("对话质量", score_dialogue),
        ("叙事风格", score_style),
        ("情感深度", score_emotion),
        ("世界构建", score_worldbuilding),
        ("节奏控制", score_pacing),
        ("创新性", score_novelty),
    ]

    results = {}
    all_issues = []
    total_score = 0

    for name, scorer in scorers:
        result = scorer(text, mode)
        results[name] = result["score"]
        total_score += result["score"]
        all_issues.extend([f"[{name}] {i}" for i in result["issues"]])

    avg_score = total_score / len(scorers)

    return {
        "scores": results,
        "avg_score": round(avg_score, 1),
        "total_score": total_score,
        "max_score": len(scorers) * 10,
        "issues": all_issues,
        "weakest": min(results, key=results.get),
        "strongest": max(results, key=results.get),
    }


def generate_wildcard_reversal(mode: str = "general") -> str:
    """生成Wildcard反转元素（打破AI的'最可能路径'）"""
    import random

    wildcards = {
        "crazy_lit": [
            "在高潮处插入一个完全无关的日常细节（如：他注意到墙上的钟停了）",
            "让配角说一句完全出人意料的话，改变所有人的计划",
            "在发疯场景中突然插入一段童年回忆",
        ],
        "urban_power": [
            "主角使用异能时产生一个意想不到的副作用",
            "最信任的人给出一个含糊的警告",
            "异能失效的瞬间，主角用最原始的方式解决问题",
        ],
        "female_solo": [
            "女主做出一个看似错误但实际是更高层次的决策",
            "竞争对手主动提供帮助，但原因不明",
            "女主的某个决定让盟友也感到意外",
        ],
        "reality_revenge": [
            "复仇过程中发现对手也在被更大的势力利用",
            "主角付出代价后，发现结果和预期完全不同",
            "一个看似无关的小人物改变了整个局面",
        ],
        "folk_horror": [
            "恐怖场景中出现一个不合时宜的温馨细节",
            "主角发现禁忌仪式的真正目的和传说完全不同",
            "最安全的做法反而引向了最大的危险",
        ],
        "rule_mystery": [
            "新发现的规则和已有规则产生矛盾",
            "看似安全的区域突然出现新规则",
            "主角发现规则本身在变化，但变化的规律可以被利用",
        ],
        "healing_life": [
            "治愈过程中出现反复，但反复本身带来了新的理解",
            "一个陌生人的无意之举改变了主角的心结",
            "主角帮助别人时，意外解开了自己的问题",
        ],
        "healing_life_v2": [
            "治愈过程中出现反复，但反复本身带来了新的理解",
            "一个陌生人的无意之举改变了主角的心结",
            "主角帮助别人时，意外解开了自己的问题",
        ],
        "romance": [
            "误会不是通过解释消除，而是通过一个意外事件",
            "感情升温时出现一个让双方都尴尬的共同秘密",
            "第三方不是破坏者，而是意外推动者",
        ],
        "history_scholar": [
            "历史知识帮了主角，但也带来了一个现代人不该知道的危险",
            "古人的智慧比主角预想的更深，或更不同",
            "一个历史细节和当前困境产生惊人的相似",
        ],
        "retro_life": [
            "年代细节引发一个意想不到的连锁反应",
            "老一辈的做法看似过时，实际暗含智慧",
            "一个被遗忘的老物件突然变得至关重要",
        ],
        "general": [
            "主角做出一个看似错误但直觉驱动的选择",
            "最不起眼的细节成为关键转折点",
            "帮助主角的人有自己不可告人的目的",
        ],
    }

    mode_wildcards = wildcards.get(mode, wildcards["general"])
    return random.choice(mode_wildcards)
