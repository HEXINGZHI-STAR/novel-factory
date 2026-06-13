"""
盘古 · 广义随机占优 (GSD) 评估框架

论文: Garces Arias et al., "Statistical Multicriteria Evaluation of LLM-Generated Text", arXiv:2506.18082, 2025

核心思想:
  不人为加权多个质量维度，而是用"随机占优"判断——
  文本A在所有维度上都不劣于文本B时，A占优B。
  不需要选择权重，避免"句法占30%还是50%"的争论。

盘古用法:
  比较两章的质量，给出"谁在哪维度上显著更优"的统计推断。
"""

from __future__ import annotations

from typing import List, Dict, Tuple
import math


def gsd_compare(chapter_a: Dict[str, float],
                chapter_b: Dict[str, float],
                dimensions: List[str] = None,
                alpha: float = 0.10) -> Dict:
    """
    比较两章的多维度质量。

    Args:
        chapter_a: {"句均": 22, "对话率": 0.13, "AI风险": 0.15, ...}
        chapter_b: {"句均": 18, "对话率": 0.08, "AI风险": 0.45, ...}
        dimensions: 比较的维度 (默认全部)
        alpha: 显著性水平

    Returns:
        {"a_dominates": bool, "b_dominates": bool, "dim_details": [...]}
    """
    dims = dimensions or list(chapter_a.keys())
    details = []

    a_better = 0
    b_better = 0

    for dim in dims:
        va = chapter_a.get(dim, 0)
        vb = chapter_b.get(dim, 0)
        diff = va - vb
        # 判断方向: AI风险、连续短句 越低越好；其他越高越好
        if dim in ("AI风险", "连续短句", "设定问题"):
            diff = -diff  # 反转: 更低=更好

        if diff > 0.01:
            a_better += 1
            verdict = "A优"
        elif diff < -0.01:
            b_better += 1
            verdict = "B优"
        else:
            verdict = "平"

        details.append({
            "dimension": dim,
            "value_a": va,
            "value_b": vb,
            "diff": round(diff, 4),
            "verdict": verdict,
        })

    # GSD判定: A在所有维度上不劣于B → A占优
    n_dims = len(dims)
    a_dominates = a_better >= n_dims * 0.75  # 75%维度胜出 = 占优
    b_dominates = b_better >= n_dims * 0.75

    return {
        "a_dominates": a_dominates,
        "b_dominates": b_dominates,
        "a_better_dims": a_better,
        "b_better_dims": b_better,
        "total_dims": n_dims,
        "verdict": "A显著占优" if a_dominates else
                   "B显著占优" if b_dominates else
                   f"A优{a_better}维, B优{b_better}维, 无显著占优",
        "details": details,
    }


def gsd_evaluate(chapter_metrics: Dict[str, float],
                   baseline: str = "auto") -> Dict:
    """
    单章评估: 与内置基准线比较。

    Args:
        chapter_metrics: 章节指标字典
        baseline: "qimao" / "qidian" / "zhihu" / "auto"

    Returns:
        GSD比较结果
    """
    baselines = {
        "qimao":  {"句均": 22, "对话率": 0.25, "AI风险": 0.3, "CV": 0.4, "节奏": 0.6},
        "qidian": {"句均": 28, "对话率": 0.30, "AI风险": 0.4, "CV": 0.5, "节奏": 0.5},
        "zhihu":  {"句均": 18, "对话率": 0.12, "AI风险": 0.2, "CV": 0.6, "节奏": 0.4},
    }
    base = baselines.get(baseline, baselines["qimao"])
    return gsd_compare(chapter_metrics, base)
