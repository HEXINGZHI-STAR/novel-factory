#!/usr/bin/env python3
"""Big Five + VIA 人格模型（对标CMN'25论文 Empowering Players as Story Creators）

核心思路：
- Big Five（大五人格）：开放性/尽责性/外向性/宜人性/神经质，每项1-10分
- VIA（价值观优势）：24项性格优势中选3-5项核心优势
- 从Big Five+VIA推导：压力反应/情感触发器/决策风格/冲突模式/社交模式
"""

# Big Five维度定义
BIG_FIVE_DIMENSIONS = {
    "开放性": "想象力/好奇心/创造力 vs 务实/保守/传统",
    "尽责性": "自律/计划性/可靠 vs 随性/冲动/自由",
    "外向性": "社交/活跃/热情 vs 独处/安静/内敛",
    "宜人性": "信任/合作/善良 vs 竞争/怀疑/强硬",
    "神经质": "焦虑/情绪化/脆弱 vs 稳定/冷静/坚韧",
}

# VIA 24项性格优势
VIA_STRENGTHS = [
    "创造力", "好奇心", "判断力", "好学", "洞察力",  # 智慧
    "勇气", "毅力", "诚实", "热情",  # 勇气
    "仁爱", "善良", "社交智慧",  # 仁爱
    "公平", "领导力", "团队合作",  # 正义
    "宽恕", "谦逊", "谨慎", "自律",  # 节制
    "欣赏美", "感恩", "希望", "幽默", "信仰",  # 超越
]

# 12种模式的默认Big Five+VIA模板
MODE_PERSONALITY_TEMPLATES = {
    "crazy_lit": {
        "big_five": {"开放性": 8, "尽责性": 3, "外向性": 7, "宜人性": 2, "神经质": 8},
        "via": ["勇气", "诚实", "创造力"],
        "stress_response": "压力越大越极端，从压抑切换为爆发",
    },
    "urban_power": {
        "big_five": {"开放性": 6, "尽责性": 7, "外向性": 5, "宜人性": 4, "神经质": 3},
        "via": ["毅力", "判断力", "勇气"],
        "stress_response": "冷静分析局势，找到对手弱点一击制胜",
    },
    "female_solo": {
        "big_five": {"开放性": 7, "尽责性": 8, "外向性": 4, "宜人性": 5, "神经质": 4},
        "via": ["毅力", "洞察力", "自律"],
        "stress_response": "不情绪化，用行动证明自己",
    },
    "reality_revenge": {
        "big_five": {"开放性": 5, "尽责性": 8, "外向性": 3, "宜人性": 2, "神经质": 6},
        "via": ["毅力", "谨慎", "判断力"],
        "stress_response": "隐忍蓄力，等待最佳时机反击",
    },
    "folk_horror": {
        "big_five": {"开放性": 9, "尽责性": 5, "外向性": 2, "宜人性": 6, "神经质": 7},
        "via": ["好奇心", "洞察力", "谨慎"],
        "stress_response": "恐惧中保持观察，从异常细节中找到线索",
    },
    "rule_mystery": {
        "big_five": {"开放性": 8, "尽责性": 9, "外向性": 2, "宜人性": 3, "神经质": 5},
        "via": ["判断力", "好学", "谨慎"],
        "stress_response": "规则越严越冷静，用逻辑找到漏洞",
    },
    "healing_life": {
        "big_five": {"开放性": 7, "尽责性": 6, "外向性": 5, "宜人性": 9, "神经质": 3},
        "via": ["善良", "感恩", "欣赏美"],
        "stress_response": "用温暖化解困境，但内心有韧性",
    },
    "healing_life_v2": {
        "big_five": {"开放性": 7, "尽责性": 6, "外向性": 5, "宜人性": 9, "神经质": 3},
        "via": ["善良", "感恩", "欣赏美"],
        "stress_response": "用温暖化解困境，但内心有韧性",
    },
    "romance": {
        "big_five": {"开放性": 8, "尽责性": 5, "外向性": 6, "宜人性": 7, "神经质": 6},
        "via": ["仁爱", "社交智慧", "热情"],
        "stress_response": "情感波动大，但最终选择信任",
    },
    "history_scholar": {
        "big_five": {"开放性": 9, "尽责性": 9, "外向性": 2, "宜人性": 5, "神经质": 2},
        "via": ["好学", "判断力", "洞察力"],
        "stress_response": "以史为鉴，从历史中找到破局之法",
    },
    "retro_life": {
        "big_five": {"开放性": 5, "尽责性": 7, "外向性": 6, "宜人性": 8, "神经质": 4},
        "via": ["坚韧", "善良", "团队合作"],
        "stress_response": "靠人情和韧性熬过难关",
    },
    "general": {
        "big_five": {"开放性": 6, "尽责性": 7, "外向性": 5, "宜人性": 5, "神经质": 4},
        "via": ["勇气", "毅力", "判断力"],
        "stress_response": "压力下保持冷静，逐步解决问题",
    },
}


def derive_from_big_five(big_five: dict) -> dict:
    """从Big Five分数推导角色行为模式"""
    openness = big_five.get("开放性", 5)
    conscientiousness = big_five.get("尽责性", 5)
    extraversion = big_five.get("外向性", 5)
    agreeableness = big_five.get("宜人性", 5)
    neuroticism = big_five.get("神经质", 5)

    # 推导决策风格
    if conscientiousness >= 7 and openness >= 7:
        decision_style = "计划型创新者——先分析再行动，但方案有创意"
    elif conscientiousness >= 7:
        decision_style = "严谨执行者——按计划行事，不冒险"
    elif openness >= 7:
        decision_style = "直觉型冒险者——凭感觉行动，常有意外之举"
    else:
        decision_style = "随性应对者——见招拆招，没有固定模式"

    # 推导冲突模式
    if agreeableness <= 3:
        conflict_style = "强硬对抗——不退让，正面硬刚"
    elif agreeableness >= 7 and neuroticism >= 7:
        conflict_style = "内心挣扎——想退让但又不甘心"
    elif agreeableness >= 7:
        conflict_style = "寻求共赢——尽量让各方满意"
    else:
        conflict_style = "有理有据地争取——不主动冲突但也不退缩"

    # 推导社交模式
    if extraversion >= 7 and agreeableness >= 7:
        social_style = "社交核心——自然成为群体中心"
    elif extraversion >= 7:
        social_style = "主动出击——敢开口但未必讨喜"
    elif extraversion <= 3 and agreeableness >= 7:
        social_style = "安静温暖——不主动但被需要"
    elif extraversion <= 3:
        social_style = "独行侠——不依赖他人"
    else:
        social_style = "选择性社交——需要时才开口"

    # 推导压力反应
    if neuroticism <= 3 and conscientiousness >= 7:
        stress_response = "越危险越冷静，判断力反而提升"
    elif neuroticism <= 3:
        stress_response = "情绪稳定但可能反应迟钝"
    elif neuroticism >= 7 and openness >= 7:
        stress_response = "焦虑中爆发创造力——压力越大想法越极端"
    elif neuroticism >= 7:
        stress_response = "情绪波动大，容易崩溃或冲动"
    else:
        stress_response = "适度紧张，正常应对"

    # 推导情感触发器
    triggers = []
    if agreeableness >= 7:
        triggers.append("看到他人受苦")
    if agreeableness <= 3:
        triggers.append("被轻视或侮辱")
    if neuroticism >= 7:
        triggers.append("失去控制感")
    if conscientiousness >= 7:
        triggers.append("规则被打破")
    if openness >= 7:
        triggers.append("发现未知事物")
    if extraversion <= 3:
        triggers.append("被强迫社交")

    return {
        "decision_style": decision_style,
        "conflict_style": conflict_style,
        "social_style": social_style,
        "stress_response": stress_response,
        "emotional_triggers": triggers,
    }


def generate_personality_prompt(big_five: dict, via: list, character_name: str = "主角") -> str:
    """生成人格注入prompt（用于W1/W2注入）"""
    derived = derive_from_big_five(big_five)

    prompt_parts = [f"【{character_name}人格画像（Big Five+VIA驱动）】"]

    # Big Five
    prompt_parts.append(f"人格维度：")
    for dim, score in big_five.items():
        level = "极高" if score >= 8 else "偏高" if score >= 6 else "中等" if score >= 4 else "偏低" if score >= 2 else "极低"
        prompt_parts.append(f"  {dim}({level}{score}/10)")

    # VIA
    prompt_parts.append(f"核心优势：{'、'.join(via)}")

    # 推导结果
    prompt_parts.append(f"决策风格：{derived['decision_style']}")
    prompt_parts.append(f"冲突模式：{derived['conflict_style']}")
    prompt_parts.append(f"社交模式：{derived['social_style']}")
    prompt_parts.append(f"压力反应：{derived['stress_response']}")
    prompt_parts.append(f"情感触发器：{'、'.join(derived['emotional_triggers'][:3])}")

    # 写作约束
    prompt_parts.append(f"【写作约束——必须遵循人格画像】")
    prompt_parts.append(f"- {character_name}在压力下：{derived['stress_response']}，禁止写出相反反应")
    prompt_parts.append(f"- {character_name}面对冲突：{derived['conflict_style']}，禁止写出相反行为")
    prompt_parts.append(f"- {character_name}的情感触发：{'、'.join(derived['emotional_triggers'][:2])}，遇到这些场景必须有情绪波动")

    return "\n".join(prompt_parts)


def get_mode_personality_prompt(mode: str, character_name: str = "主角") -> str:
    """获取模式对应的默认人格prompt"""
    template = MODE_PERSONALITY_TEMPLATES.get(mode, MODE_PERSONALITY_TEMPLATES["general"])
    return generate_personality_prompt(template["big_five"], template["via"], character_name)
