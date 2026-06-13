"""
盘古数学 · 随机过程

叙事中的随机过程模型:
  - 情绪马尔可夫链: 基于当前情绪状态预测下一状态的概率分布
  - 泊松事件过程: 建模"每N字出现一个关键事件"的随机到达
  - 维纳过程: 建模累积张力 (带漂移的随机游走)

用法:
    emc = EmotionMarkovChain.from_mode("healing_life_v2")
    next_state = emc.next("压抑")  # 采样下一个情绪状态
    path = emc.simulate_path(steps=20)  # 模拟20步情绪路径
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# ================================================================
# 情绪马尔可夫链
# ================================================================

# 情绪状态空间 (12维环状)
EMOTION_STATES = [
    "警觉", "兴奋", "愉悦", "平静", "放松",
    "困倦", "疲倦", "压力", "紧张", "焦虑", "恐惧", "愤怒",
]

# 治愈系情绪转移矩阵 (更倾向正面和低唤醒)
_HEALING_TRANSITION = {
    "平静": {"放松": 0.35, "愉悦": 0.25, "警觉": 0.15, "困倦": 0.10, "疲倦": 0.08, "压力": 0.05, "紧张": 0.02},
    "放松": {"平静": 0.30, "愉悦": 0.25, "困倦": 0.20, "警觉": 0.10, "疲倦": 0.10, "其他": 0.05},
    "愉悦": {"平静": 0.30, "放松": 0.25, "兴奋": 0.20, "警觉": 0.15, "其他": 0.10},
    "警觉": {"平静": 0.25, "紧张": 0.20, "压力": 0.15, "焦虑": 0.15, "愉悦": 0.10, "其他": 0.15},
    "困倦": {"放松": 0.30, "平静": 0.25, "疲倦": 0.20, "其他": 0.25},
    "疲倦": {"困倦": 0.25, "平静": 0.20, "压力": 0.20, "放松": 0.15, "其他": 0.20},
    "压力": {"紧张": 0.30, "疲倦": 0.20, "焦虑": 0.20, "警觉": 0.15, "其他": 0.15},
    "紧张": {"焦虑": 0.30, "压力": 0.25, "恐惧": 0.20, "警觉": 0.15, "其他": 0.10},
    "焦虑": {"紧张": 0.25, "恐惧": 0.25, "压力": 0.20, "疲倦": 0.15, "其他": 0.15},
    "恐惧": {"焦虑": 0.30, "紧张": 0.25, "愤怒": 0.20, "警觉": 0.15, "其他": 0.10},
    "愤怒": {"紧张": 0.25, "恐惧": 0.20, "压力": 0.20, "焦虑": 0.15, "疲倦": 0.10, "其他": 0.10},
    "兴奋": {"愉悦": 0.35, "警觉": 0.25, "平静": 0.20, "放松": 0.10, "其他": 0.10},
}

# 悬疑/紧张情绪转移（更倾向负面和高唤醒）
_SUSPENSE_TRANSITION = {
    "平静": {"警觉": 0.30, "紧张": 0.20, "压力": 0.15, "放松": 0.15, "焦虑": 0.10, "其他": 0.10},
    "警觉": {"紧张": 0.30, "焦虑": 0.25, "恐惧": 0.15, "压力": 0.15, "其他": 0.15},
    "紧张": {"焦虑": 0.30, "恐惧": 0.30, "警觉": 0.20, "压力": 0.10, "其他": 0.10},
    "焦虑": {"恐惧": 0.35, "紧张": 0.25, "压力": 0.20, "警觉": 0.10, "其他": 0.10},
    "恐惧": {"焦虑": 0.30, "愤怒": 0.25, "紧张": 0.20, "警觉": 0.15, "其他": 0.10},
    "愤怒": {"紧张": 0.30, "恐惧": 0.25, "焦虑": 0.20, "压力": 0.15, "其他": 0.10},
    "压力": {"紧张": 0.30, "焦虑": 0.25, "疲倦": 0.20, "警觉": 0.15, "其他": 0.10},
    "放松": {"平静": 0.30, "警觉": 0.25, "愉悦": 0.15, "困倦": 0.15, "其他": 0.15},
}


@dataclass
class EmotionMarkovChain:
    """情绪马尔可夫链"""
    transition_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    current_state: str = "平静"

    @classmethod
    def from_mode(cls, mode: str = "healing_life_v2"):
        """根据模式加载情绪转移矩阵"""
        if mode in ("healing_life_v2", "healing_life", "general"):
            return cls(transition_matrix=_HEALING_TRANSITION, current_state="平静")
        elif mode in ("rule_mystery", "folk_horror", "mystery"):
            return cls(transition_matrix=_SUSPENSE_TRANSITION, current_state="警觉")
        else:
            # 混合: 合并两个矩阵
            mixed = {}
            for state in EMOTION_STATES:
                h = _HEALING_TRANSITION.get(state, {})
                s = _SUSPENSE_TRANSITION.get(state, {})
                combined = {}
                for k in set(list(h.keys()) + list(s.keys())):
                    combined[k] = (h.get(k, 0) + s.get(k, 0)) / 2
                # 归一化
                total = sum(combined.values())
                if total > 0:
                    for k in combined:
                        combined[k] /= total
                mixed[state] = combined
            return cls(transition_matrix=mixed, current_state="平静")

    def next(self, current: str = None) -> str:
        """采样下一个情绪状态"""
        state = current or self.current_state
        transitions = self.transition_matrix.get(state, {})
        if not transitions:
            # fallback: 均匀分布到邻接状态
            idx = EMOTION_STATES.index(state) if state in EMOTION_STATES else 0
            n = len(EMOTION_STATES)
            neighbors = [EMOTION_STATES[(idx + i) % n] for i in (-2, -1, 1, 2)]
            return random.choice(neighbors)

        # 加权采样
        states = list(transitions.keys())
        probs = list(transitions.values())

        # "其他" → 均匀分布到剩余状态
        if "其他" in states:
            other_idx = states.index("其他")
            other_prob = probs[other_idx]
            states.pop(other_idx)
            probs.pop(other_idx)
            remaining = [s for s in EMOTION_STATES if s not in states]
            if remaining:
                states.extend(remaining)
                probs.extend([other_prob / len(remaining)] * len(remaining))

        total = sum(probs)
        r = random.random() * total
        cumsum = 0
        for s, p in zip(states, probs):
            cumsum += p
            if r <= cumsum:
                self.current_state = s
                return s
        self.current_state = states[-1]
        return states[-1]

    def simulate_path(self, steps: int = 20, start: str = None) -> List[str]:
        """模拟一条情绪路径"""
        if start:
            self.current_state = start
        path = [self.current_state]
        for _ in range(steps):
            path.append(self.next())
        return path

    def stationary_distribution(self) -> Dict[str, float]:
        """
        计算稳态分布 (幂迭代)。

        返回: {情绪状态: 长期概率}
        """
        # 初始化均匀分布
        dist = {s: 1.0 / len(EMOTION_STATES) for s in EMOTION_STATES}

        # 迭代
        for _ in range(100):
            new_dist = {s: 0.0 for s in EMOTION_STATES}
            for state, prob in dist.items():
                transitions = self.transition_matrix.get(state, {})
                if not transitions:
                    new_dist[state] += prob
                    continue
                for next_state, trans_prob in transitions.items():
                    if next_state != "其他":
                        new_dist[next_state] += prob * trans_prob
                    else:
                        # "其他"均匀分配
                        remaining = [s for s in EMOTION_STATES
                                      if s not in transitions or s == "其他"]
                        for rs in remaining:
                            new_dist[rs] += prob * trans_prob / len(remaining)
            # 收敛检测
            max_diff = max(abs(new_dist[s] - dist[s]) for s in EMOTION_STATES)
            dist = new_dist
            if max_diff < 1e-6:
                break
        return dist


# ================================================================
# 泊松事件过程
# ================================================================

@dataclass
class PoissonEventProcess:
    """
    泊松事件过程: 建模"关键事件"在文本中的随机到达。

    λ = 每N字的期望事件数。
    用于检测事件密度是否合理。
    """
    lambda_per_1000chars: float = 2.0  # 每千字2个关键事件

    def expected_events(self, word_count: int) -> float:
        return word_count / 1000.0 * self.lambda_per_1000chars

    def probability_at_least(self, word_count: int, k: int) -> float:
        """给定字数，至少发生k个事件的概率"""
        lam = self.expected_events(word_count)
        prob = 1.0
        for i in range(k):
            prob -= math.exp(-lam) * (lam ** i) / math.factorial(i)
        return prob

    def is_event_sparse(self, word_count: int, actual_events: int) -> bool:
        """检测事件是否过于稀疏 (< 期望的一半 → True)"""
        return actual_events < self.expected_events(word_count) * 0.5

    def is_event_dense(self, word_count: int, actual_events: int) -> bool:
        """检测事件密度是否过高 (> 期望的2倍 → True)"""
        return actual_events > self.expected_events(word_count) * 2.0


# ================================================================
# 维纳过程 (带漂移的随机游走 — 累积张力模型)
# ================================================================

@dataclass
class StochasticTensionModel:
    """
    累积张力 = 维纳过程 (带漂移的随机游走)

    dT = μ*dt + σ*dW
    μ = 漂移率 (正=自然堆积张力)
    σ = 波动率 (事件冲击)
    """
    drift: float = 0.05       # 每段自然堆积5%张力
    volatility: float = 0.15  # 事件冲击波动率
    tension: float = 0.0      # 当前张力 (0-1)

    def step(self, has_event: bool = False, event_intensity: float = 0.0):
        """
        推进一个时间步。

        Args:
            has_event: 是否有"事件"发生
            event_intensity: 事件强度 (0-1)
        """
        # 确定性漂移
        self.tension += self.drift

        # 随机冲击
        shock = random.gauss(0, self.volatility)

        # 事件冲击
        if has_event:
            shock += event_intensity * random.gauss(0.3, 0.1)

        self.tension += shock
        self.tension = max(0.0, min(1.0, self.tension))

    def simulate(self, steps: int = 20,
                  events: List[int] = None,
                  event_intensities: List[float] = None) -> List[float]:
        """模拟steps步的张力曲线"""
        events = events or []
        intensities = event_intensities or []
        path = [self.tension]
        for i in range(steps):
            has_event = i in events
            intensity = intensities[events.index(i)] if i in events and intensities else 0.5
            self.step(has_event, intensity)
            path.append(self.tension)
        return path

    def release_threshold(self) -> float:
        """返回当前是否需要释放 (张力>0.8 → 需要释放点)"""
        return self.tension
