"""
盘古数学 · 贝叶斯推断

写作中的贝叶斯思维:
  - 先验概率 P(H): 基于题材/模式/平台的初始假设
  - 似然 P(E|H): 新证据出现时、该假设下看到这个证据的概率
  - 后验概率 P(H|E): 看到证据后更新信念

应用场景:
  1. 质量推断: 每读完一段，更新"本章质量合格"的后验概率
  2. 设定矛盾检测: 新事实与已锁定规则的冲突概率
  3. 伏笔回收预期: 基于已埋设伏笔的年龄，预测回收概率
  4. 读者留存: 基于每章质量信号，更新"读者会追读"的概率

用法:
    bq = BayesianQualityModel(prior=0.7)  # 70%先验信心
    bq.update(evidence_strength=0.6)      # 看到一个中等强度的正面证据
    bq.update(evidence_strength=0.3)      # 看到一个弱证据
    print(f"后验质量: {bq.posterior:.1%}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ================================================================
# 贝叶斯更新器 (通用)
# ================================================================

@dataclass
class BayesianUpdater:
    """
    通用贝叶斯更新器。

    P(H|E) = P(E|H) * P(H) / P(E)
    使用对数几率(log-odds)避免浮点下溢。
    """
    prior: float = 0.5              # P(H): 先验概率
    posterior: float = 0.5          # 当前后验概率
    log_odds: float = 0.0           # 对数几率 log(P/(1-P))
    evidence_history: List[Tuple[float, float]] = field(default_factory=list)
    # (likelihood_ratio, timestamp)

    def __post_init__(self):
        self.posterior = self.prior
        self.log_odds = self._prob_to_log_odds(self.prior)

    @staticmethod
    def _prob_to_log_odds(p: float) -> float:
        """概率 → 对数几率"""
        p = max(0.001, min(0.999, p))
        return math.log(p / (1 - p))

    @staticmethod
    def _log_odds_to_prob(lo: float) -> float:
        """对数几率 → 概率"""
        return 1.0 / (1.0 + math.exp(-lo))

    def update(self, likelihood_ratio: float, weight: float = 1.0):
        """
        用新证据更新信念。

        Args:
            likelihood_ratio: P(E|H)/P(E|¬H)，>1表示证据支持H，<1表示反对H
            weight: 证据权重 (0-1)，弱证据权重低
        """
        # 加权对数似然比
        weighted_lr = 1.0 + (likelihood_ratio - 1.0) * weight
        if weighted_lr <= 0:
            weighted_lr = 0.01

        self.log_odds += math.log(weighted_lr)
        self.posterior = self._log_odds_to_prob(self.log_odds)
        self.evidence_history.append((likelihood_ratio, weight))

    def update_direct(self, true_positive: int, false_positive: int,
                       total_positive: int, total_negative: int):
        """
        基于频率直接更新。

        Args:
            true_positive: 真阳性 (H为真时观察到证据的次数)
            false_positive: 假阳性 (H为假时观察到证据的次数)
            total_positive: H为真的总次数
            total_negative: H为假的总次数
        """
        tp_rate = true_positive / max(total_positive, 1)
        fp_rate = false_positive / max(total_negative, 1)
        if fp_rate < 1e-9:
            fp_rate = 1e-9
        lr = tp_rate / fp_rate
        self.update(lr, weight=min(1.0, (total_positive + total_negative) / 100))

    def confidence_interval(self, z: float = 1.96) -> Tuple[float, float]:
        """
        后验概率的95%置信区间 (基于Beta分布近似)。

        当 evidence_history 为空时返回宽区间。
        """
        n = len(self.evidence_history)
        if n == 0:
            return (max(0.0, self.posterior - 0.2), min(1.0, self.posterior + 0.2))

        # Beta(α, β) 近似: α = 成功次数+1, β = 失败次数+1
        successes = sum(1 for lr, _ in self.evidence_history if lr > 1.0)
        failures = n - successes
        alpha = successes + 1
        beta_val = failures + 1,  # intentional

        # 实际上是 alpha = successes + 1, beta = failures + 1
        # 均值 = alpha / (alpha + beta)
        # 方差 = alpha*beta / ((alpha+beta)^2 * (alpha+beta+1))
        a = successes + 1.0
        b = failures + 1.0
        mean = a / (a + b)
        std = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
        lo = max(0.0, mean - z * std)
        hi = min(1.0, mean + z * std)
        return (lo, hi)

    def is_confident(self, threshold: float = 0.9, min_evidence: int = 5) -> bool:
        """是否已达到高置信度 (>threshold 且有足够证据)"""
        return (self.posterior > threshold or self.posterior < (1 - threshold)) \
               and len(self.evidence_history) >= min_evidence

    def reset(self):
        """重置为初始状态"""
        self.posterior = self.prior
        self.log_odds = self._prob_to_log_odds(self.prior)
        self.evidence_history.clear()


# ================================================================
# 贝叶斯质量模型 (写作专用)
# ================================================================

@dataclass
class BayesianQualityModel:
    """
    贝叶斯章节质量推断模型。

    先验: 基于题材/模式/作者历史，预设质量概率
    证据: 每一段/每句提供微小的质量信号
    后验: 实时更新的质量置信度
    """
    prior_quality: float = 0.6      # P(Quality=OK): 先验质量概率
    posterior_quality: float = 0.6
    _updater: BayesianUpdater = field(init=False)

    # 子维度
    sub_models: dict = field(default_factory=dict)

    def __post_init__(self):
        self._updater = BayesianUpdater(prior=self.prior_quality)
        self.posterior_quality = self.prior_quality
        self.sub_models = {
            "setting_consistency": BayesianUpdater(prior=0.85),   # 设定通常一致
            "character_consistency": BayesianUpdater(prior=0.80), # 角色通常稳定
            "pacing_quality": BayesianUpdater(prior=0.65),        # 节奏中等先验
            "emotional_depth": BayesianUpdater(prior=0.55),       # 情绪偏保守
        }

    def feed_paragraph(self, para: str):
        """喂入一段文本，更新所有子模型和后验"""
        signals = self._extract_signals(para)

        # 更新子模型
        self.sub_models["setting_consistency"].update(
            signals.get("setting_lr", 1.0), weight=0.3)
        self.sub_models["character_consistency"].update(
            signals.get("character_lr", 1.0), weight=0.3)
        self.sub_models["pacing_quality"].update(
            signals.get("pacing_lr", 1.0), weight=0.4)
        self.sub_models["emotional_depth"].update(
            signals.get("emotion_lr", 1.0), weight=0.4)

        # 综合后验: 子模型的加权平均对数几率
        weights = {"setting_consistency": 0.30, "character_consistency": 0.30,
                    "pacing_quality": 0.20, "emotional_depth": 0.20}
        avg_log_odds = sum(
            w * m.log_odds for name, m in self.sub_models.items()
            for w in [weights[name]]
        )
        self._updater.log_odds = avg_log_odds
        self._updater.posterior = self._updater._log_odds_to_prob(avg_log_odds)
        self.posterior_quality = self._updater.posterior

    def _extract_signals(self, para: str) -> dict:
        """从段落提取质量信号 (简化版)"""
        signals = {}
        para_len = len(para)

        # 设定一致性信号: 没有矛盾词对 → 正面
        contradictions = [("冷静","暴怒"), ("果断","犹豫"), ("沉默","滔滔不绝")]
        has_contra = any(w1 in para and w2 in para for w1, w2 in contradictions)
        signals["setting_lr"] = 0.3 if has_contra else 1.2

        # 角色一致性信号: 行为+情绪合理
        signals["character_lr"] = 1.1  # 默认轻微正面

        # 节奏信号: 段落长度适中 (80-300字)
        if 80 <= para_len <= 300:
            signals["pacing_lr"] = 1.3
        elif para_len < 30 or para_len > 500:
            signals["pacing_lr"] = 0.6
        else:
            signals["pacing_lr"] = 1.0

        # 情绪信号: 有具体感官描写 → 正面
        sensory = ("温度","冰凉","温暖","粗糙","光滑","柔软","硬",
                    "光","暗","声音","气味","味道","风吹","湿")
        has_sensory = any(w in para for w in sensory)
        signals["emotion_lr"] = 1.4 if has_sensory else 0.9

        return signals

    def diagnose(self) -> str:
        """诊断当前状态"""
        issues = []
        for name, model in self.sub_models.items():
            if model.posterior < 0.4:
                issues.append(f"{name}: LOW ({model.posterior:.1%})")
        if not issues:
            return f"Quality: {self.posterior_quality:.1%} — all dimensions OK"
        return f"Quality: {self.posterior_quality:.1%} — concerns: {'; '.join(issues)}"

    def recommend_action(self) -> str:
        """基于当前后验推荐下一步行动"""
        if self.posterior_quality > 0.75:
            return "CONTINUE — 质量稳定，继续当前节奏"
        elif self.posterior_quality > 0.50:
            worst = min(self.sub_models.items(), key=lambda x: x[1].posterior)
            return f"WATCH — 总体可接受，关注 {worst[0]} ({worst[1].posterior:.1%})"
        elif self.posterior_quality > 0.30:
            worst = min(self.sub_models.items(), key=lambda x: x[1].posterior)
            return f"REVISE — 质量下降，重点修改 {worst[0]} 相关段落"
        else:
            return "STOP — 质量严重低于预期，建议重写本章"
