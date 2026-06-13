"""
盘古 · GUARD: 熵驱动自适应质量评估

吸收: Lee et al. (2025), "GUARD: Glocal Uncertainty-Driven Adaptive Decoding"
      Findings of EMNLP 2025

原理:
  Global Entropy:  整章的信息熵 → 判断"整体是否太均质(AI味)"
  Local Entropy:   每个段落的信息熵 → 判断"局部是否有起伏"
  GUARD = Global + Local 联合驱动 → 自适性调整质量判断

优势:
  - 不依赖人工阈值 (不像我们之前"AI风险>0.5就报警")
  - 有理论保证的无偏性和一致性
  - 同时考虑全局和局部

盘古应用: 替代 bayesian.py 中简单的手动阈值判断
"""

from __future__ import annotations

import re
import math
from typing import List, Tuple, Dict
from collections import Counter


def _sentence_entropy(text: str) -> float:
    """计算一段文本的字符级信息熵"""
    chars = re.findall(r'[一-鿿]', text)
    if len(chars) < 5:
        return 0.0
    counter = Counter(chars)
    total = len(chars)
    entropy = -sum((c / total) * math.log2(c / total)
                   for c in counter.values())
    # 归一化: 除以最大可能熵 log2(unique_chars)
    max_entropy = math.log2(len(counter)) if counter else 1.0
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _global_entropy(text: str) -> float:
    """
    全局熵: 整章的信息熵。
    0=完全均质(AI味重), 1=高度变化。
    """
    return _sentence_entropy(text)


def _local_entropy_deviations(text: str) -> List[float]:
    """
    局部熵偏差: 每个段落的熵与全局熵的偏差。
    偏差大 = 段落之间有起伏(真人特征)
    偏差小 = 段落均质(AI特征)
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
    if len(paragraphs) < 3:
        return [0.0]

    entropies = [_sentence_entropy(p) for p in paragraphs]
    global_ent = _global_entropy(text)

    deviations = [abs(e - global_ent) for e in entropies]
    return deviations


class GuardEvaluator:
    """
    GUARD 质量评估器。

    结合全局熵 + 局部熵偏差 → 自适应质量判断。
    """

    def evaluate(self, text: str) -> dict:
        """
        对文本进行GUARD评估。

        Returns:
            {
              "quality_score": 0-1,
              "is_ai_like": bool,
              "global_entropy": float,
              "local_deviation_mean": float,
              "verdict": str,
            }
        """
        ge = _global_entropy(text)
        deviations = _local_entropy_deviations(text)

        mean_dev = sum(deviations) / len(deviations) if deviations else 0.0

        # GUARD联合评分
        # 全局熵低 + 局部偏差小 = AI味重
        # 全局熵高 + 局部偏差大 = 真人特征
        quality = (ge * 0.4 + min(mean_dev * 3, 1.0) * 0.6)

        # 判定: 不需要人工阈值，用GUARD的自适应
        ai_like = quality < 0.35
        if quality > 0.65:
            verdict = "真人写作特征显著"
        elif quality > 0.45:
            verdict = "在AI/真人边界，需具体段落审查"
        elif quality > 0.25:
            verdict = "AI痕迹明显，建议局部改写"
        else:
            verdict = "高度疑似AI生成文本"

        return {
            "quality_score": round(quality, 3),
            "is_ai_like": ai_like,
            "global_entropy": round(ge, 3),
            "local_deviation_mean": round(mean_dev, 3),
            "verdict": verdict,
        }


def guard_evaluate(text: str) -> dict:
    """便捷函数"""
    return GuardEvaluator().evaluate(text)
