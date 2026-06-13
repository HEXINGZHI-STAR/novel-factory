"""
盘古数学 · 情绪频谱分析

将章节文本的情绪信号做傅里叶变换，提取叙事情绪的频谱特征:
  - 主导频率: 叙事情绪波动的快慢 (高频=密集情绪切换，低频=长情绪段落)
  - 频谱能量分布: 各频段的能量占比
  - 情绪复杂度: 频谱熵 (高频多=情绪丰富)
  - 情绪周期: 主导频率对应的叙事节奏周期

用法:
    spec = EmotionSpectrum.from_text(chapter_text)
    print(f"主导频率: {spec.dominant_freq:.3f}")
    print(f"情绪复杂度: {spec.complexity:.2f}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple
from collections import Counter


# ================================================================
# 情绪词 (按唤醒度+极性分组)
# ================================================================

_POS_HIGH_AROUSAL = {"狂喜","兴奋","激动","热血","震撼","惊艳","暴起","炸裂"}
_POS_LOW_AROUSAL = {"平静","放松","温暖","温柔","治愈","舒缓","安静","舒适"}
_NEG_HIGH_AROUSAL = {"愤怒","恐惧","绝望","崩溃","暴怒","惊恐","怒吼","撕裂"}
_NEG_LOW_AROUSAL = {"悲伤","忧郁","疲惫","倦怠","消沉","黯淡","冷淡","空洞"}

_ALL_EMOTION = list(_POS_HIGH_AROUSAL | _POS_LOW_AROUSAL |
                     _NEG_HIGH_AROUSAL | _NEG_LOW_AROUSAL)


# ================================================================
# 情绪频谱
# ================================================================

@dataclass
class EmotionSpectrum:
    """情绪频谱分析结果"""
    signal: List[float] = field(default_factory=list)    # 情绪信号 (每个句子的情绪值)
    spectrum: List[float] = field(default_factory=list)   # 频谱幅值
    dominant_freq: float = 0.0      # 主导频率 (句^-1)
    dominant_period: float = 0.0    # 主导周期 (句)
    complexity: float = 0.0         # 频谱熵 (高=情绪丰富)
    energy_bands: dict = field(default_factory=dict)  # {低频/中频/高频: 能量比}
    mean_valence: float = 0.0       # 平均极性 (-1负 ~ +1正)
    mean_arousal: float = 0.0       # 平均唤醒度 (0低 ~ 1高)

    @classmethod
    def from_text(cls, text: str):
        spec = cls()

        # 1. 提取情绪信号: 逐句
        sentences = [s.strip() for s in re.split(r'[。！？!?\n]', text)
                     if len(s.strip()) >= 2]
        if not sentences:
            return spec

        for sent in sentences:
            valence = 0.0
            arousal = 0.0

            for word in _POS_HIGH_AROUSAL:
                if word in sent:
                    valence += 0.8
                    arousal += 0.9
            for word in _POS_LOW_AROUSAL:
                if word in sent:
                    valence += 0.6
                    arousal += 0.3
            for word in _NEG_HIGH_AROUSAL:
                if word in sent:
                    valence -= 0.8
                    arousal += 0.9
            for word in _NEG_LOW_AROUSAL:
                if word in sent:
                    valence -= 0.5
                    arousal += 0.2

            # 组合信号: valence * arousal (有情绪且强烈的句子得分高)
            signal_val = valence * (arousal + 0.5)
            spec.signal.append(signal_val)
            spec.mean_valence += valence
            spec.mean_arousal += arousal

        n = len(spec.signal)
        spec.mean_valence /= n
        spec.mean_arousal /= n

        # 2. 傅里叶变换 (DFT)
        spec.spectrum = _dft(spec.signal)
        spec.spectrum = spec.spectrum[:len(spec.spectrum) // 2]  # 只保留正频率

        # 3. 主导频率
        if len(spec.spectrum) > 1:
            max_idx = max(range(1, len(spec.spectrum)),
                          key=lambda i: spec.spectrum[i])
            spec.dominant_freq = max_idx / n
            spec.dominant_period = n / max_idx if max_idx > 0 else 0.0

        # 4. 频段能量
        half = len(spec.spectrum)
        low_cut = half // 6          # 低频: 前1/6
        mid_cut = half // 3          # 中频: 1/6 ~ 1/3
        total_energy = sum(v ** 2 for v in spec.spectrum)
        if total_energy > 0:
            low_energy = sum(v ** 2 for v in spec.spectrum[:low_cut]) / total_energy
            mid_energy = sum(v ** 2 for v in spec.spectrum[low_cut:mid_cut]) / total_energy
            high_energy = sum(v ** 2 for v in spec.spectrum[mid_cut:]) / total_energy
            spec.energy_bands = {"低频": low_energy, "中频": mid_energy, "高频": high_energy}

        # 5. 频谱熵 (复杂度)
        if total_energy > 0:
            probs = [v ** 2 / total_energy for v in spec.spectrum if v > 1e-6]
            spec.complexity = -sum(p * math.log2(p) for p in probs) / max(math.log2(len(probs)), 1)
            spec.complexity = min(1.0, spec.complexity)

        return spec

    def is_emotionally_flat(self, threshold: float = 0.3) -> bool:
        """检测情绪是否过于平坦 (低频能量过高)"""
        return self.energy_bands.get("低频", 0) > 0.7 and self.complexity < threshold

    def summary(self) -> str:
        return (
            f"主导周期={self.dominant_period:.0f}句 "
            f"极性={self.mean_valence:.2f} "
            f"复杂度={self.complexity:.2f} "
            f"低频={self.energy_bands.get('低频', 0):.1%}"
        )


# ================================================================
# 离散傅里叶变换 (纯Python)
# ================================================================

def _dft(signal: List[float]) -> List[float]:
    """离散傅里叶变换。numpy可用时O(n log n)，否则O(n²)纯Python降级。"""
    n = len(signal)
    if n == 0:
        return []
    try:
        import numpy as np
        fft = np.fft.fft(np.array(signal, dtype=np.float64))
        return (np.abs(fft) / n).tolist()
    except ImportError:
        pass
    # 纯Python O(n²) fallback
    result = []
    for k in range(n):
        real = sum(signal[t] * math.cos(2 * math.pi * k * t / n)
                    for t in range(n))
        imag = sum(signal[t] * math.sin(2 * math.pi * k * t / n)
                    for t in range(n))
        result.append(math.sqrt(real ** 2 + imag ** 2) / n)
    return result


def compute_emotion_spectrum(text: str) -> EmotionSpectrum:
    """便捷函数"""
    return EmotionSpectrum.from_text(text)
