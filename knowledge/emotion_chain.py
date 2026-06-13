#!/usr/bin/env python3
"""MECoT: 马尔可夫情绪链（Markov Emotional Chain-of-Thought）

对标论文: MECoT (ACL Findings 2025)
核心思路:
- 12维情绪环状模型（Emotion Circumplex），不是简单的喜怒哀乐
- 马尔可夫链建模情绪转移概率
- Big Five人格加权转移矩阵
- 双过程理论：直觉反应（马尔可夫链）+ 理性调节（LLM推理）
"""

import random
import math

# 12维情绪环状模型（按环形排列，相邻情绪更容易转移）
EMOTION_CIRCUMPLEX = [
    "警觉",   # 0 - 高唤醒+微正面
    "兴奋",   # 1 - 高唤醒+正面
    "愉悦",   # 2 - 中唤醒+正面
    "平静",   # 3 - 低唤醒+正面
    "放松",   # 4 - 低唤醒+微正面
    "困倦",   # 5 - 极低唤醒+中性
    "疲倦",   # 6 - 低唤醒+微负面
    "压力",   # 7 - 中唤醒+负面
    "紧张",   # 8 - 高唤醒+负面
    "焦虑",   # 9 - 高唤醒+强负面
    "恐惧",   # 10 - 极高唤醒+强负面
    "愤怒",   # 11 - 极高唤醒+强负面
]

# 情绪极性（正面/负面）
EMOTION_VALENCE = {
    "警觉": 0.2, "兴奋": 0.8, "愉悦": 0.7, "平静": 0.5,
    "放松": 0.4, "困倦": 0.0, "疲倦": -0.3, "压力": -0.5,
    "紧张": -0.6, "焦虑": -0.7, "恐惧": -0.9, "愤怒": -0.8,
}

# 情绪唤醒度（低→高）
EMOTION_AROUSAL = {
    "困倦": 0.1, "放松": 0.2, "疲倦": 0.3, "平静": 0.4,
    "愉悦": 0.5, "压力": 0.6, "警觉": 0.7, "紧张": 0.75,
    "兴奋": 0.8, "焦虑": 0.85, "愤怒": 0.9, "恐惧": 0.95,
}

# 基础转移矩阵（相邻情绪更容易转移，环形距离越远概率越低）
def _build_base_transition_matrix():
    """构建基础情绪转移矩阵（环形距离衰减）"""
    n = len(EMOTION_CIRCUMPLEX)
    matrix = {}
    for i, emotion in enumerate(EMOTION_CIRCUMPLEX):
        transitions = {}
        for j, target in enumerate(EMOTION_CIRCUMPLEX):
            # 环形距离
            distance = min(abs(i - j), n - abs(i - j))
            # 距离越近概率越高（指数衰减）
            transitions[target] = math.exp(-0.5 * distance)
        # 归一化
        total = sum(transitions.values())
        for k in transitions:
            transitions[k] /= total
        matrix[emotion] = transitions
    return matrix

BASE_TRANSITION = _build_base_transition_matrix()

# 事件类型对情绪的影响
EVENT_EMOTION_IMPACT = {
    "威胁": {"恐惧": 0.4, "紧张": 0.3, "焦虑": 0.2},
    "冲突": {"愤怒": 0.35, "紧张": 0.3, "兴奋": 0.15},
    "成功": {"愉悦": 0.4, "兴奋": 0.3, "放松": 0.15},
    "失败": {"压力": 0.3, "焦虑": 0.3, "疲倦": 0.2},
    "发现": {"警觉": 0.35, "兴奋": 0.3, "愉悦": 0.15},
    "失去": {"恐惧": 0.25, "焦虑": 0.3, "愤怒": 0.2},
    "重逢": {"愉悦": 0.4, "兴奋": 0.3, "平静": 0.15},
    "背叛": {"愤怒": 0.4, "恐惧": 0.25, "压力": 0.2},
    "牺牲": {"压力": 0.3, "平静": 0.25, "紧张": 0.2},
    "觉醒": {"兴奋": 0.4, "警觉": 0.25, "愉悦": 0.2},
    "绝望": {"恐惧": 0.35, "焦虑": 0.3, "疲倦": 0.2},
    "希望": {"愉悦": 0.3, "兴奋": 0.3, "警觉": 0.2},
}


def apply_personality_weights(base_transition, big_five):
    """用Big Five人格加权转移矩阵（对标MECoT论文核心算法）"""
    neuroticism = big_five.get("神经质", 5)
    extraversion = big_five.get("外向性", 5)
    agreeableness = big_five.get("宜人性", 5)
    openness = big_five.get("开放性", 5)

    weighted = {}
    for current_emotion, transitions in base_transition.items():
        weighted_transitions = {}
        for target_emotion, prob in transitions.items():
            weight = 1.0

            # 神经质高 → 负面情绪转移概率增加
            if EMOTION_VALENCE.get(target_emotion, 0) < 0:
                weight *= (1 + 0.1 * (neuroticism - 5))
            else:
                weight *= (1 - 0.05 * (neuroticism - 5))

            # 外向性高 → 正面情绪转移概率增加
            if EMOTION_VALENCE.get(target_emotion, 0) > 0:
                weight *= (1 + 0.08 * (extraversion - 5))
            else:
                weight *= (1 - 0.04 * (extraversion - 5))

            # 宜人性高 → 愤怒转移概率降低
            if target_emotion == "愤怒":
                weight *= (1 - 0.1 * (agreeableness - 5))
            # 宜人性高 → 压力→内疚 转移增加（用焦虑替代）
            if current_emotion == "愤怒" and target_emotion == "焦虑":
                weight *= (1 + 0.08 * (agreeableness - 5))

            # 开放性高 → 兴奋/警觉转移概率增加
            if target_emotion in ("兴奋", "警觉"):
                weight *= (1 + 0.06 * (openness - 5))

            weighted_transitions[target_emotion] = prob * weight

        # 归一化
        total = sum(weighted_transitions.values())
        for k in weighted_transitions:
            weighted_transitions[k] /= total
        weighted[current_emotion] = weighted_transitions

    return weighted


def predict_next_emotion(current_emotion, big_five, event_type=None):
    """预测角色的下一个情绪状态（双过程：直觉+理性）"""

    # 过程1：直觉反应（马尔可夫链）
    weighted_transition = apply_personality_weights(BASE_TRANSITION, big_five)
    transitions = weighted_transition.get(current_emotion, BASE_TRANSITION.get(current_emotion, {}))

    # 如果有事件，叠加事件影响
    if event_type and event_type in EVENT_EMOTION_IMPACT:
        impact = EVENT_EMOTION_IMPACT[event_type]
        for emotion, bonus in impact.items():
            if emotion in transitions:
                transitions[emotion] = transitions[emotion] + bonus
        # 归一化
        total = sum(transitions.values())
        for k in transitions:
            transitions[k] /= total

    # 按概率采样
    emotions = list(transitions.keys())
    probs = list(transitions.values())
    predicted = random.choices(emotions, weights=probs, k=1)[0]

    # 过程2：理性调节（如果人格高度尽责，负面情绪会被压制）
    conscientiousness = big_five.get("尽责性", 5)
    if conscientiousness >= 7 and EMOTION_VALENCE.get(predicted, 0) < -0.5:
        # 高尽责性的人会压制极端负面情绪
        if predicted == "恐惧" and current_emotion != "恐惧":
            predicted = "紧张"  # 降级
        elif predicted == "愤怒" and current_emotion != "愤怒":
            predicted = "压力"  # 降级

    return predicted


def generate_emotion_prompt(current_emotion, next_emotion, big_five, event_type=None):
    """生成情绪注入prompt（用于W2/W4注入）"""
    valence_shift = EMOTION_VALENCE.get(next_emotion, 0) - EMOTION_VALENCE.get(current_emotion, 0)
    arousal = EMOTION_AROUSAL.get(next_emotion, 0.5)

    prompt_parts = [f"【角色情绪状态（MECoT驱动）】"]
    prompt_parts.append(f"当前情绪: {current_emotion} → 下一情绪: {next_emotion}")

    # 情绪变化方向
    if valence_shift > 0.3:
        prompt_parts.append(f"情绪走向: 急剧好转（从{current_emotion}到{next_emotion}）")
    elif valence_shift > 0:
        prompt_parts.append(f"情绪走向: 缓和（从{current_emotion}到{next_emotion}）")
    elif valence_shift > -0.3:
        prompt_parts.append(f"情绪走向: 恶化（从{current_emotion}到{next_emotion}）")
    else:
        prompt_parts.append(f"情绪走向: 急剧恶化（从{current_emotion}到{next_emotion}）")

    # 唤醒度指导
    if arousal >= 0.8:
        prompt_parts.append(f"唤醒度: 极高——用短句、快节奏、动作密集表达{next_emotion}")
    elif arousal >= 0.6:
        prompt_parts.append(f"唤醒度: 中高——用中等句长、适度节奏表达{next_emotion}")
    elif arousal >= 0.4:
        prompt_parts.append(f"唤醒度: 中等——节奏平稳，{next_emotion}内敛表达")
    else:
        prompt_parts.append(f"唤醒度: 低——用长句、慢节奏、内心独白表达{next_emotion}")

    # 人格约束
    neuroticism = big_five.get("神经质", 5)
    if neuroticism <= 3 and EMOTION_VALENCE.get(next_emotion, 0) < -0.5:
        prompt_parts.append(f"【人格约束】神经质={neuroticism}（极稳定），{next_emotion}必须克制表达，用行动替代情绪词")
    elif neuroticism >= 7 and EMOTION_VALENCE.get(next_emotion, 0) < -0.3:
        prompt_parts.append(f"【人格约束】神经质={neuroticism}（情绪化），{next_emotion}可以外放表达，但要有具体锚点")

    # 写作禁忌
    prompt_parts.append("【情绪写作禁忌】")
    prompt_parts.append(f"- 禁止直接写'他感到{next_emotion}'，必须用动作/物件/场景表达")
    prompt_parts.append(f"- 禁止写'心中一{next_emotion}'，这是AI模板")
    prompt_parts.append(f"- {next_emotion}的表达必须符合Big Five人格画像")

    return "\n".join(prompt_parts)


def get_emotion_chain_prompt(current_emotion, mode, event_type=None):
    """获取模式对应的情绪链prompt（便捷接口）"""
    try:
        from knowledge.personality_model import MODE_PERSONALITY_TEMPLATES
        template = MODE_PERSONALITY_TEMPLATES.get(mode, MODE_PERSONALITY_TEMPLATES["general"])
        big_five = template["big_five"]
    except ImportError:
        big_five = {"开放性": 6, "尽责性": 7, "外向性": 5, "宜人性": 5, "神经质": 4}

    next_emotion = predict_next_emotion(current_emotion, big_five, event_type)
    return generate_emotion_prompt(current_emotion, next_emotion, big_five, event_type), next_emotion
