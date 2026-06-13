"""
盘古 · Burrows' Delta 风格距离

学术标准 (30年): z-score标准化top-N高频词的曼哈顿距离。
比余弦相似度更准确的风格差异度量。

公式:
  ΔB = (1/n) * Σᵢ |zᵢ(A) − zᵢ(B)|
  其中 zᵢ = (freqᵢ − μ) / σ, 在参考语料库上计算

论文: Mikros et al., "Burrows' Delta as a Convergent Validator", JQL 2026

盘古用法:
  - 检测风格漂移: 每章与前章的Delta距离
  - AI/人类判断: 生成章节与经典参考的Delta距离
  - 多作者风格聚类: pairwise Delta矩阵
"""

from __future__ import annotations

import re
import math
from typing import List, Dict, Tuple
from collections import Counter


def _word_frequencies(text: str, n: int = 500) -> Dict[str, float]:
    """提取前N个最高频词的归一化频率"""
    # 中文: 使用字符2-gram作为"词"
    chars = re.sub(r'[^一-鿿]', '', text)
    words = [chars[i:i+2] for i in range(len(chars) - 1)]
    counter = Counter(words)
    total = sum(counter.values())
    top_n = dict(counter.most_common(n))
    return {k: v / max(total, 1) for k, v in top_n.items()}


def _z_score(freqs: Dict[str, float],
              corpus_stats: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
    """将词频转换为z-score"""
    z = {}
    for word, freq in freqs.items():
        mu, sigma = corpus_stats.get(word, (0.0, 0.01))
        z[word] = (freq - mu) / sigma if sigma > 0 else 0.0
    return z


def burrows_delta(text1: str, text2: str,
                   corpus_texts: List[str] = None,
                   n_words: int = 300) -> float:
    """
    计算两段文本之间的Burrows' Delta风格距离。

    Args:
        text1, text2: 比较的两段文本
        corpus_texts: 参考语料库文本 (用于计算z-score的μ和σ)
        n_words: 使用前N个最高频词

    Returns:
        Delta距离 (越小越相似, 典型阈值: <1.0=同作者, >1.5=不同作者)
    """
    freq1 = _word_frequencies(text1, n_words)
    freq2 = _word_frequencies(text2, n_words)

    # 计算语料库统计量
    if corpus_texts:
        all_freqs = [_word_frequencies(t, n_words) for t in corpus_texts]
        corpus_stats = {}
        all_words = set()
        for f in all_freqs:
            all_words.update(f.keys())

        for word in all_words:
            vals = [f.get(word, 0.0) for f in all_freqs]
            mu = sum(vals) / len(vals)
            sigma = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
            corpus_stats[word] = (mu, sigma)
    else:
        # 无参考语料库: 使用简单z-score (基于两段文本的合并)
        all_words = set(freq1.keys()) | set(freq2.keys())
        corpus_stats = {}
        for word in all_words:
            f1 = freq1.get(word, 0.0)
            f2 = freq2.get(word, 0.0)
            mu = (f1 + f2) / 2
            sigma = math.sqrt(((f1 - mu) ** 2 + (f2 - mu) ** 2) / 2) or 0.01
            corpus_stats[word] = (mu, sigma)

    z1 = _z_score(freq1, corpus_stats)
    z2 = _z_score(freq2, corpus_stats)

    # ΔB = mean(|z_i1 - z_i2|)
    common_words = set(z1.keys()) & set(z2.keys())
    if not common_words:
        return 999.0

    delta = sum(abs(z1[w] - z2[w]) for w in common_words) / len(common_words)
    return round(delta, 4)


def delta_distance(text1: str, text2: str) -> float:
    """便捷函数"""
    return burrows_delta(text1, text2)
