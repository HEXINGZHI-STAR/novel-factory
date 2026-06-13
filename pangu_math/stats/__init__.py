"""
盘古数学 · 统计建模层

模块:
  - distribution:    句长/段长/对话长度分布分析
  - diversity:       词汇多样性 (TTR/MTLD/HD-D/Simpson)
  - readability:     中文可读性评估
  - style_fingerprint: 风格指纹量化 (N-gram + PCA)
"""

from .distribution import SentenceStats, ChapterStats
from .diversity import LexicalDiversity, compute_all_diversity
from .readability import ReadabilityScore, chinese_readability
from .style_fingerprint import StyleFingerprint, compute_style_vector

__all__ = [
    "SentenceStats", "ChapterStats",
    "LexicalDiversity", "compute_all_diversity",
    "ReadabilityScore", "chinese_readability",
    "StyleFingerprint", "compute_style_vector",
]
