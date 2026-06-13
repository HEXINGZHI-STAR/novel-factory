"""
盘古数学 · 信号处理层

模块:
  - emotion_spectrum:  叙事情绪频谱分析
  - tension_envelope:  张力包络线提取
  - rhythm_analyzer:   叙事节奏自相关分析
"""

from .emotion_spectrum import EmotionSpectrum, compute_emotion_spectrum
from .tension_envelope import TensionEnvelope, compute_tension_envelope
from .rhythm_analyzer import RhythmAnalyzer, compute_rhythm_autocorr

__all__ = [
    "EmotionSpectrum", "compute_emotion_spectrum",
    "TensionEnvelope", "compute_tension_envelope",
    "RhythmAnalyzer", "compute_rhythm_autocorr",
]
