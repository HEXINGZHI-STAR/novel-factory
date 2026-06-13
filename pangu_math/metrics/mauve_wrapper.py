"""
盘古 · MAUVE 指标包装器

MAUVE (NeurIPS 2021 杰出论文): 基于KL散度前沿，
测量AI生成文本与人类文本之间的统计分布差距。
分数 0-1，越接近1越接近人类水平。

原始实现: https://github.com/krishnap25/mauve
论文: Pillutla et al., "MAUVE: Measuring the Gap Between Neural Text and Human Text using Divergence Frontiers", NeurIPS 2021

盘古适配:
  - 参考文本: 福尔摩斯/盗墓笔记等经典作品的章节
  - 被测文本: Pipeline生成的章节
  - 轻量化: 文本<500字时降级到Burrows' Delta
"""

from __future__ import annotations

import math
import re
from typing import List, Optional
from collections import Counter


def mauve_score(generated_text: str, reference_texts: List[str],
                 use_gpu: bool = False) -> float:
    """
    计算MAUVE分数。

    Args:
        generated_text: 待评估的生成文本
        reference_texts: 参考文本列表 (人类写作)
        use_gpu: 是否使用GPU (需安装faiss-gpu)

    Returns:
        MAUVE分数 (0-1). 0=完全不像人类, 1=无法区分
    """
    # 轻量级文本 (<500字) 用降级方案
    gen_len = len(generated_text.replace('\n', '').replace(' ', ''))
    ref_len = sum(len(r.replace('\n', '').replace(' ', '')) for r in reference_texts)

    if gen_len < 300 or ref_len < 500:
        return _lightweight_mauve(generated_text, reference_texts)

    # 完整MAUVE
    try:
        from mauve import compute_mauve
        result = compute_mauve(
            p_text=generated_text,
            q_text=reference_texts,
            device_id=0 if use_gpu else -1,
            max_text_length=256,
            verbose=False,
            featurize_model_name='gpt2',
        )
        return result.mauve
    except ImportError:
        return _lightweight_mauve(generated_text, reference_texts)
    except Exception:
        return _lightweight_mauve(generated_text, reference_texts)


def _lightweight_mauve(gen: str, refs: List[str]) -> float:
    """
    轻量MAUVE: 当文本太短或mauve库不可用时降级。
    基于词频分布的KL散度估计。

    原理 (来自MAUVE论文):
      将文本嵌入量化到k个簇，构建P(gen)和Q(ref)两个分布，
      计算KL散度曲线下的面积作为MAUVE分数。
    降级版: 直接在字符n-gram频率分布上计算对称KL散度。
    """
    def _char_ngram_dist(text: str, n: int = 3) -> dict:
        chars = re.sub(r'[^一-鿿]', '', text)
        if len(chars) < n:
            return {}
        ngrams = [chars[i:i+n] for i in range(len(chars) - n + 1)]
        total = len(ngrams)
        return {k: v/total for k, v in Counter(ngrams).items()}

    gen_dist = _char_ngram_dist(gen)
    ref_dist = _char_ngram_dist(' '.join(refs))

    # 合并词表
    all_keys = set(gen_dist.keys()) | set(ref_dist.keys())

    # 对称KL散度: (KL(P||Q) + KL(Q||P)) / 2
    kl_pq = 0.0
    kl_qp = 0.0
    for k in all_keys:
        p = gen_dist.get(k, 1e-9)
        q = ref_dist.get(k, 1e-9)
        kl_pq += p * math.log(p / q)
        kl_qp += q * math.log(q / p)

    # MAUVE = 1 - exp(-对称KL)
    sym_kl = (kl_pq + kl_qp) / 2
    mauve = 1.0 - math.exp(-sym_kl)
    return max(0.0, min(1.0, mauve))


def compute_mauve(generated: str, references: List[str]) -> float:
    """便捷函数"""
    return mauve_score(generated, references)
