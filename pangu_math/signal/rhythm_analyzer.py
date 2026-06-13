"""
盘古数学 · 叙事节奏自相关分析

检测文本中句长/情绪/事件密度的周期模式:
  - 自相关函数 (ACF): 发现叙事中的周期性结构
  - 节奏周期: 多少句一个"叙事单元"完成
  - 节奏一致性: 如果周期性太强→机械化(AI味)；太弱→混乱
  - 半周期检测: 找到叙事从"铺陈→揭示"的转折点

用法:
    ra = RhythmAnalyzer.from_text(chapter_text)
    print(f"节奏周期: {ra.primary_period:.0f}句")
    print(f"一致性: {ra.consistency:.2f}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List


@dataclass
class RhythmAnalyzer:
    """叙事节奏自相关分析"""
    sentence_lengths: List[int] = field(default_factory=list)
    acf: List[float] = field(default_factory=list)           # 自相关函数
    primary_period: float = 0.0   # 主要周期 (句)
    secondary_period: float = 0.0 # 次要周期
    consistency: float = 0.0      # 节奏一致性 (0=乱, 1=机械)
    half_period: float = 0.0      # 半周期 (铺陈→揭示转折)
    stationarity: float = 0.0     # 平稳性: 前/后半节奏一致性

    @classmethod
    def from_text(cls, text: str):
        ra = cls()

        sentences = [s.strip() for s in re.split(r'[。！？!?\n]', text)
                     if len(s.strip()) >= 2]
        if len(sentences) < 10:
            return ra

        # 1. 句长序列
        ra.sentence_lengths = [len(s) for s in sentences]

        # 2. 自相关函数 (ACF)
        ra.acf = _autocorrelation(ra.sentence_lengths)

        # 3. 找主要周期 (第一个显著的ACF峰值，跳过lag=0)
        ra.primary_period = _find_first_peak(ra.acf)
        if ra.primary_period > 0:
            # 找次要周期 (第二显著峰值)
            skip_range = int(ra.primary_period * 0.8)
            ra.secondary_period = _find_first_peak(ra.acf, skip=int(ra.primary_period + skip_range))
            ra.half_period = ra.primary_period / 2.0

        # 4. 一致性: 主要周期处的ACF值
        if ra.primary_period > 0:
            idx = int(ra.primary_period)
            if idx < len(ra.acf):
                ra.consistency = ra.acf[idx]

        # 5. 平稳性: 前后半的ACF差异
        n = len(ra.sentence_lengths)
        if n > 20:
            mid = n // 2
            acf_first = _autocorrelation(ra.sentence_lengths[:mid])
            acf_second = _autocorrelation(ra.sentence_lengths[mid:])
            if len(acf_first) > 0 and len(acf_second) > 0:
                # 比较前几个lag的ACF差异
                diffs = [abs(acf_first[i] - acf_second[i])
                          for i in range(min(5, len(acf_first), len(acf_second)))]
                ra.stationarity = max(0.0, 1.0 - sum(diffs) / len(diffs))

        return ra

    def is_mechanistic(self, threshold: float = 0.7) -> bool:
        """检测节奏是否过于机械化 (AI味指标)"""
        return self.consistency > threshold

    def is_chaotic(self, threshold: float = 0.15) -> bool:
        """检测节奏是否过于混乱"""
        return self.consistency < threshold and len(self.sentence_lengths) > 20

    def summary(self) -> str:
        return (
            f"周期={self.primary_period:.0f}句 "
            f"一致性={self.consistency:.3f} "
            f"{'[机械]' if self.is_mechanistic() else ''}"
            f"{'[混乱]' if self.is_chaotic() else ''}"
        )


# ================================================================
# 自相关函数
# ================================================================

def _autocorrelation(signal: List[int], max_lag: int = None) -> List[float]:
    """计算信号的自相关函数 (ACF)"""
    n = len(signal)
    if n < 2:
        return []
    max_lag = max_lag or min(n // 3, 30)  # 最多30个lag
    mean = sum(signal) / n
    # 方差
    var = sum((s - mean) ** 2 for s in signal)
    if var == 0:
        return [1.0] * max_lag

    acf = []
    for lag in range(max_lag + 1):
        numerator = sum((signal[i] - mean) * (signal[i + lag] - mean)
                         for i in range(n - lag))
        acf.append(numerator / var)
    return acf


def _find_first_peak(acf: List[float], skip: int = 1) -> float:
    """找到ACF中第一个显著峰值 (跳过前skip个)"""
    for lag in range(skip + 1, len(acf) - 1):
        if acf[lag] > acf[lag - 1] and acf[lag] > acf[lag + 1]:
            if acf[lag] > 0.15:  # 显著阈值
                return float(lag)
    return 0.0


def compute_rhythm_autocorr(text: str) -> RhythmAnalyzer:
    """便捷函数"""
    return RhythmAnalyzer.from_text(text)
