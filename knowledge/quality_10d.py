#!/usr/bin/env python3
"""10维质量评分系统 + StoryScope 5项AI叙事缺陷检测

8维基础（已有）: 角色塑造/情节推进/对话质量/叙事风格/情感深度/世界构建/节奏控制/创新性
2维新增（对标"Novel" Benchmark ACL 2025）: 主题深度/叙事技巧
5项AI叙事缺陷（对标StoryScope arxiv 2026, 马里兰大学+Google DeepMind）
"""

import re
import random
from collections import Counter


# ========== 8维基础评分（从quality_8d.py导入，降级时自建） ==========
try:
    from knowledge.quality_8d import (
        score_character, score_plot, score_dialogue, score_style,
        score_emotion, score_worldbuilding, score_pacing, score_novelty,
        full_8d_score,
    )
    HAS_8D = True
except ImportError:
    HAS_8D = False


# ========== 2维新增评分 ==========

def score_theme_depth(text, mode="general"):
    """评分：主题深度（对标Novel Benchmark的thematic depth指标）"""
    score = 5.0
    issues = []

    # 检测是否有主题表达（不是直接说教）
    # 好的主题：通过事件/对话/象征间接表达
    # 差的主题：直接写"这个故事告诉我们"

    # 说教检测
    preaching_patterns = re.findall(r'(这个故事告诉我们|他明白了|她终于理解了|他懂得了|他领悟了|这让他意识到)', text)
    if preaching_patterns:
        score -= 2.0
        issues.append(f"直接说教({len(preaching_patterns)}处)，应通过事件间接表达主题")

    # 象征/隐喻检测（好的主题表达方式）
    metaphor_patterns = re.findall(r'(像.*一样|仿佛|如同|宛如|犹如)', text)
    if metaphor_patterns:
        score += 1.0

    # 主题冲突检测（好的小说有主题张力）
    theme_conflicts = re.findall(r'(但.*却|然而.*又|虽然.*但是|一方面.*另一方面)', text)
    if len(theme_conflicts) >= 2:
        score += 1.0

    # 价值观碰撞检测
    value_words = re.findall(r'(对错|善恶|生死|自由|责任|正义|牺牲|选择)', text)
    if value_words:
        score += 0.5

    return {"score": max(1, min(10, score)), "issues": issues}


def score_narrative_technique(text, mode="general"):
    """评分：叙事技巧（对标Novel Benchmark的narrative technique指标）"""
    score = 5.0
    issues = []

    # 检测时间线跳跃（非线性叙事=高级技巧）
    time_jumps = re.findall(r'(之前|那时|回忆|想起|多年前|曾经|后来|很久以后|在那之前)', text)
    if time_jumps:
        score += 1.5
    else:
        score -= 1.0
        issues.append("纯线性叙事，缺少闪回/倒叙/预叙等时间线技巧")

    # 检测视角切换
    pov_markers = re.findall(r'(在他看来|从她的角度|他不知道的是|她没看到|而在另一边)', text)
    if pov_markers:
        score += 1.0

    # 检测留白/悬念（不把所有事说透）
    ambiguity = re.findall(r'(没有说|沉默|没有回答|欲言又止|没有解释|不知道为什么)', text)
    if ambiguity:
        score += 1.0
    else:
        issues.append("缺少留白，AI倾向把所有事说透")

    # 检测环境叙事（用环境暗示情绪/主题）
    env_narrative = re.findall(r'(雨|风|光|影|暗|冷|热|雾|雷|雪)', text)
    if len(env_narrative) >= 3:
        score += 0.5

    return {"score": max(1, min(10, score)), "issues": issues}


# ========== StoryScope 5项AI叙事缺陷检测 ==========

def check_storyscope_defects(text):
    """检测AI叙事5大底层缺陷（对标StoryScope, 马里兰大学+Google DeepMind 2026）

    5大缺陷（仅用叙事特征就能93.2%准确率区分AI和人类）:
    1. AI太爱说教 - 77%的AI故事直接点明主题 vs 人类52%
    2. AI不会跳时间线 - 79%的AI故事无支线 vs 人类57%
    3. AI必须给交代 - 47%的AI故事主角顿悟/接受 vs 人类27%
    4. AI对话是辩论 - AI对话59%是哲学讨论 vs 人类34%
    5. AI引用模糊 - AI引用72%是模糊暗指 vs 人类50%明确提及
    """
    defects = []

    # 缺陷1: 说教（在文本后半段检测）
    second_half = text[len(text)//2:] if len(text) > 500 else text
    preaching = re.findall(r'(明白了|理解了|懂得了|领悟了|这个故事|他终于|她终于|让他意识到|使她明白)', second_half)
    if preaching:
        defects.append({
            "defect": "说教倾向",
            "severity": len(preaching),
            "description": f"文本后半段出现{len(preaching)}处直接说教",
            "fix": "删除说教句，让读者自己得出结论。用事件/对话替代'他明白了'",
            "evidence": preaching,
        })

    # 缺陷2: 纯线性叙事
    time_markers = re.findall(r'(之前|那时|回忆起|想起.*那|多年前|曾经|后来|很久以后|在那之前|回溯)', text)
    if len(time_markers) == 0:
        defects.append({
            "defect": "纯线性叙事",
            "severity": 1,
            "description": "全文按时间顺序推进，无闪回/倒叙/预叙",
            "fix": "在关键场景插入1处闪回（'他想起了...'）或1处预叙（'他不知道的是...'）",
            "evidence": [],
        })

    # 缺陷3: 交代式结尾
    last_300 = text[-300:] if len(text) > 300 else text
    closure_patterns = re.findall(r'(接受了|释然了|放下了|和解了|成长了|释怀了|终于.*了)', last_300)
    if closure_patterns:
        defects.append({
            "defect": "交代式结尾",
            "severity": len(closure_patterns),
            "description": f"结尾出现{len(closure_patterns)}处交代式收束",
            "fix": "改为悬念结尾或留白结尾，不要给角色一个'结论'",
            "evidence": closure_patterns,
        })

    # 缺陷4: 辩论式对话
    dialogues = re.findall(r'[""「]([^""」]{15,})[""」]', text)
    if dialogues:
        debate_count = 0
        debate_keywords = ['认为', '应该', '必须', '本质', '意义', '道理', '原则', '价值', '其实', '事实上']
        for d in dialogues:
            if any(kw in d for kw in debate_keywords):
                debate_count += 1
        if len(dialogues) > 0 and debate_count / len(dialogues) > 0.3:
            defects.append({
                "defect": "辩论式对话",
                "severity": round(debate_count / len(dialogues), 2),
                "description": f"{debate_count}/{len(dialogues)}句对话是哲学讨论/辩论",
                "fix": "把辩论改为日常对话（吃饭/走路/做事时随口说），或用行动替代对话",
                "evidence": [d[:30] for d in dialogues if any(kw in d for kw in debate_keywords)][:3],
            })

    # 缺陷5: 模糊引用
    vague_refs = re.findall(r'(某种古老|某种神秘|某种力量|某种感觉|某种气息|某种存在|某种规则|一种说不清)', text)
    if vague_refs:
        defects.append({
            "defect": "模糊引用",
            "severity": len(vague_refs),
            "description": f"出现{len(vague_refs)}处'某种XX'式模糊描述",
            "fix": "用具体描述替代：'某种古老的力量'→'像深海鲸鱼低鸣般的震动'",
            "evidence": vague_refs,
        })

    return defects


# ========== 10维全面评分 ==========

def full_10d_score(text, mode="general"):
    """10维全面评分（8维基础+2维新增+StoryScope缺陷检测）"""

    # 8维基础评分
    if HAS_8D:
        base_result = full_8d_score(text, mode)
        scores = dict(base_result["scores"])
        all_issues = list(base_result["issues"])
    else:
        # 降级：简化评分
        scores = {
            "角色塑造": 5, "情节推进": 5, "对话质量": 5, "叙事风格": 5,
            "情感深度": 5, "世界构建": 5, "节奏控制": 5, "创新性": 5,
        }
        all_issues = []

    # 2维新增评分
    theme_result = score_theme_depth(text, mode)
    scores["主题深度"] = theme_result["score"]
    all_issues.extend([f"[主题深度] {i}" for i in theme_result["issues"]])

    technique_result = score_narrative_technique(text, mode)
    scores["叙事技巧"] = technique_result["score"]
    all_issues.extend([f"[叙事技巧] {i}" for i in technique_result["issues"]])

    # StoryScope缺陷检测
    defects = check_storyscope_defects(text)
    for d in defects:
        all_issues.append(f"[StoryScope] {d['defect']}: {d['description']}")

    total_score = sum(scores.values())
    avg_score = total_score / len(scores)

    # StoryScope缺陷扣分
    defect_penalty = sum(d["severity"] * 0.5 for d in defects)
    adjusted_avg = max(1, avg_score - defect_penalty * 0.3)

    return {
        "scores": scores,
        "avg_score": round(adjusted_avg, 1),
        "raw_avg_score": round(avg_score, 1),
        "total_score": total_score,
        "max_score": len(scores) * 10,
        "issues": all_issues,
        "weakest": min(scores, key=scores.get),
        "strongest": max(scores, key=scores.get),
        "storyscope_defects": defects,
        "defect_count": len(defects),
        "defect_penalty": round(defect_penalty, 1),
    }


# ========== Wildcard反转（保留并增强） ==========

WILDCARDS = {
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


def generate_wildcard_reversal(mode="general"):
    """生成Wildcard反转元素（打破AI的'最可能路径'）"""
    mode_wildcards = WILDCARDS.get(mode, WILDCARDS["general"])
    return random.choice(mode_wildcards)
