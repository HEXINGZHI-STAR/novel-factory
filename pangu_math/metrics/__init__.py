"""
盘古数学 · 高级指标层

吸收学术界最新成果:
  - mauve_score:    MAUVE (NeurIPS 2021) — KL散度测AI/人类文本分布差距
  - burrows_delta:  Burrows' Delta (30年学术标准) — z-score词频曼哈顿距离
  - gsd_evaluate:   GSD框架 (2025) — 广义随机占优多维度评估
"""
from .mauve_wrapper import mauve_score, compute_mauve
from .burrows_delta import burrows_delta, delta_distance
from .gsd_framework import gsd_evaluate, gsd_compare

__all__ = [
    "mauve_score", "compute_mauve",
    "burrows_delta", "delta_distance",
    "gsd_evaluate", "gsd_compare",
]
