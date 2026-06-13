#!/usr/bin/env python3
"""EvolvTrip: 时序心理状态图谱（Temporal Theory-of-Mind Graph）

对标论文: EvolvTrip (arxiv 2025, University of Manchester + King's College London)
核心思路:
- 4维ToM（Theory of Mind）: 信念(belief)/欲望(desire)/意图(intention)/情绪(emotion)
- 心理状态三元组: (角色, 心理谓词, 对象)
- 时序追踪: 随章节推进自动更新图谱
- 小模型+EvolvTrip ≈ 大模型的ToM推理能力
"""

from datetime import datetime


# 4维ToM定义
TOM_DIMENSIONS = {
    "belief": "信念——角色认为什么是真的（可能错误）",
    "desire": "欲望——角色想要什么（核心驱动力）",
    "intention": "意图——角色打算做什么（行动计划）",
    "emotion": "情绪——角色当前感受（MECoT驱动）",
}

# 心理谓词（用于三元组）
PSYCHOLOGICAL_PREDICATES = {
    "belief": ["认为", "相信", "怀疑", "误以为", "确信", "不知道"],
    "desire": ["想要", "渴望", "需要", "追求", "逃避", "保护"],
    "intention": ["计划", "打算", "准备", "决定", "考虑", "放弃"],
    "emotion": ["感到", "体验", "压抑", "释放", "掩饰", "爆发"],
}


class PsychologicalTriplet:
    """心理状态三元组: (角色, 心理谓词, 对象)"""

    def __init__(self, character, predicate, obj, dimension, chapter, confidence=1.0):
        self.character = character
        self.predicate = predicate
        self.obj = obj
        self.dimension = dimension  # belief/desire/intention/emotion
        self.chapter = chapter
        self.confidence = confidence
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    def to_dict(self):
        return {
            "character": self.character,
            "predicate": self.predicate,
            "obj": self.obj,
            "dimension": self.dimension,
            "chapter": self.chapter,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d):
        t = cls(d["character"], d["predicate"], d["obj"],
                d["dimension"], d["chapter"], d.get("confidence", 1.0))
        t.timestamp = d.get("timestamp", "")
        return t

    def __repr__(self):
        return f"({self.character}, {self.predicate}, {self.obj}) [{self.dimension}@Ch{self.chapter}]"


class EvolvTripGraph:
    """时序心理状态图谱"""

    def __init__(self):
        self.triplets = []  # 所有心理三元组
        self.chapter_snapshots = {}  # 每章的心理状态快照

    def add_triplet(self, triplet):
        """添加心理三元组"""
        self.triplets.append(triplet)

    def get_character_state(self, character, chapter=None):
        """获取角色在指定章节的心理状态"""
        relevant = []
        for t in self.triplets:
            if t.character != character:
                continue
            if chapter is not None and t.chapter > chapter:
                continue
            relevant.append(t)

        # 按维度分组，取每个维度最新的
        state = {}
        for dim in TOM_DIMENSIONS:
            dim_triplets = [t for t in relevant if t.dimension == dim]
            if dim_triplets:
                latest = max(dim_triplets, key=lambda t: t.chapter)
                state[dim] = latest
        return state

    def get_belief_desire_conflicts(self, character):
        """检测信念-欲望冲突（角色相信的 vs 角色想要的）"""
        state = self.get_character_state(character)
        conflicts = []

        belief = state.get("belief")
        desire = state.get("desire")

        if belief and desire:
            # 简单冲突检测：信念和欲望的对象是否矛盾
            if belief.obj and desire.obj and belief.obj in desire.obj:
                conflicts.append({
                    "type": "信念-欲望冲突",
                    "description": f"{character}{belief.predicate}{belief.obj}，但{desire.predicate}{desire.obj}",
                    "narrative_potential": "高——这是内在张力的来源",
                })

        return conflicts

    def get_intention_emotion_gap(self, character):
        """检测意图-情绪差距（角色打算做的 vs 角色感受的）"""
        state = self.get_character_state(character)
        gaps = []

        intention = state.get("intention")
        emotion = state.get("emotion")

        if intention and emotion:
            # 意图是理性的，情绪是感性的，差距=戏剧张力
            gaps.append({
                "type": "意图-情绪差距",
                "description": f"{character}{intention.predicate}{intention.obj}，但内心{emotion.predicate}{emotion.obj}",
                "narrative_potential": "极高——这是角色深度的来源",
            })

        return gaps

    def generate_psychological_prompt(self, character, chapter=None):
        """生成心理状态注入prompt（用于W1/W2注入）"""
        state = self.get_character_state(character, chapter)
        if not state:
            return ""

        prompt_parts = [f"【{character}心理状态图谱（EvolvTrip驱动）】"]

        for dim, triplet in state.items():
            dim_name = TOM_DIMENSIONS.get(dim, dim)
            prompt_parts.append(f"{dim_name}: {triplet.predicate}{triplet.obj}")

        # 检测冲突和差距
        conflicts = self.get_belief_desire_conflicts(character)
        gaps = self.get_intention_emotion_gap(character)

        if conflicts:
            prompt_parts.append("\n【内在冲突——写作时必须体现】")
            for c in conflicts:
                prompt_parts.append(f"- {c['description']}（{c['narrative_potential']}）")

        if gaps:
            prompt_parts.append("\n【理性vs感性差距——这是角色深度的来源】")
            for g in gaps:
                prompt_parts.append(f"- {g['description']}（{g['narrative_potential']}）")

        # 写作约束
        prompt_parts.append("\n【心理状态写作约束】")
        belief = state.get("belief")
        if belief:
            prompt_parts.append(f"- {character}当前认为: {belief.obj}，所有行为必须基于这个信念（即使信念是错误的）")
            prompt_parts.append(f"- 如果信念是错误的，{character}不能表现出'知道真相'的样子")

        intention = state.get("intention")
        if intention:
            prompt_parts.append(f"- {character}当前打算: {intention.obj}，对话和行动必须服务于此意图")

        return "\n".join(prompt_parts)

    def to_dict(self):
        return {
            "triplets": [t.to_dict() for t in self.triplets],
            "chapter_snapshots": self.chapter_snapshots,
        }

    @classmethod
    def from_dict(cls, d):
        graph = cls()
        graph.triplets = [PsychologicalTriplet.from_dict(t) for t in d.get("triplets", [])]
        graph.chapter_snapshots = d.get("chapter_snapshots", {})
        return graph


def extract_psychological_states_from_text(text, chapter_num, character_names=None):
    """从文本中提取心理状态三元组（规则版，不依赖AI）"""
    triplets = []

    # 信念提取
    belief_patterns = [
        (r"(\w+)(认为|相信|确信)(.+?)[。，]", "belief"),
        (r"(\w+)(怀疑|不确定)(.+?)[。，]", "belief"),
        (r"(\w+)(不知道|没意识到)(.+?)[。，]", "belief"),
    ]

    # 欲望提取
    desire_patterns = [
        (r"(\w+)(想要|渴望|需要|必须)(.+?)[。，]", "desire"),
        (r"(\w+)(追求|寻找|保护)(.+?)[。，]", "desire"),
    ]

    # 意图提取
    intention_patterns = [
        (r"(\w+)(计划|打算|准备|决定)(.+?)[。，]", "intention"),
        (r"(\w+)(考虑|思考)(.+?)[。，]", "intention"),
    ]

    import re
    all_patterns = belief_patterns + desire_patterns + intention_patterns

    for pattern, dim in all_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            char_name = match[0]
            if character_names and char_name not in character_names:
                continue
            predicate = match[1]
            obj = match[2][:30]  # 截断
            triplets.append(PsychologicalTriplet(
                char_name, predicate, obj, dim, chapter_num
            ))

    return triplets


def generate_tom_prompt_for_chapter(character_profiles, chapter_num, previous_states=None):
    """为章节生成ToM注入prompt"""
    graph = EvolvTripGraph()

    # 从前文状态重建图谱
    if previous_states:
        for state_dict in previous_states:
            try:
                t = PsychologicalTriplet.from_dict(state_dict)
                graph.add_triplet(t)
            except Exception:
                pass

    # 为每个角色生成心理prompt
    prompts = []
    for name in character_profiles:
        prompt = graph.generate_psychological_prompt(name, chapter_num)
        if prompt:
            prompts.append(prompt)

    return "\n\n".join(prompts)
