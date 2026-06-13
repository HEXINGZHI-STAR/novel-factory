"""
盘古数学 · 词汇多样性分析

四个核心指标:
  - TTR (Type-Token Ratio): 唯一词数/总词数 — 简单但受文本长度影响大
  - MTLD (Measure of Textual Lexical Diversity): 文本长度不敏感的TTR
  - HD-D (Hypergeometric Distribution D): 基于超几何分布的概率模型
  - Simpson指数: 1 - Σ(p_i²), 生态学多样性指标

中文适配: 使用字符级(单字)+词级(简单分词)双层分析

用法:
    ld = LexicalDiversity.from_text(chapter_text)
    print(f"TTR: {ld.ttr:.3f}, MTLD: {ld.mtld:.1f}")
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Dict, Set
from dataclasses import dataclass


# ================================================================
# 简单中文分词 (不依赖jieba的fallback)
# ================================================================

def _simple_tokenize(text: str) -> List[str]:
    """简单中文分词: 2-gram字符级，适用于无jieba环境"""
    # 清理标点
    cleaned = re.sub(r'[^一-鿿]', '', text)
    tokens = []
    i = 0
    while i < len(cleaned):
        # 尝试2字词
        if i + 1 < len(cleaned):
            tokens.append(cleaned[i:i+2])
        i += 1
    return tokens

def _char_tokenize(text: str) -> List[str]:
    """字符级分词"""
    return re.findall(r'[一-鿿]', text)


# ================================================================
# 词汇多样性
# ================================================================

@dataclass
class LexicalDiversity:
    """词汇多样性指标"""

    # 字符级
    char_ttr: float = 0.0            # 字种/总字数
    char_count: int = 0
    unique_char_count: int = 0

    # 词级
    word_ttr: float = 0.0            # 词种/总词数
    mtld: float = 0.0               # MTLD (Textual Lexical Diversity)
    hd_d: float = 0.0               # HD-D (Hypergeometric Distribution D)
    simpson: float = 0.0            # Simpson多样性指数

    # 额外指标
    hapax_ratio: float = 0.0        # 仅出现一次的词占比
    entropy: float = 0.0            # 词频香农熵

    @classmethod
    def from_text(cls, text: str):
        return cls.from_tokens(_char_tokenize(text), _simple_tokenize(text))

    @classmethod
    def from_tokens(cls, char_tokens: List[str], word_tokens: List[str]):
        ld = cls()

        # === 字符级 ===
        char_counter = Counter(char_tokens)
        ld.char_count = len(char_tokens)
        ld.unique_char_count = len(char_counter)
        ld.char_ttr = ld.unique_char_count / max(ld.char_count, 1)

        # === 词级 ===
        word_counter = Counter(word_tokens)
        word_total = len(word_tokens)
        word_unique = len(word_counter)
        ld.word_ttr = word_unique / max(word_total, 1)

        # MTLD
        ld.mtld = _compute_mtld(word_tokens)

        # HD-D
        ld.hd_d = _compute_hdd(word_tokens, word_counter)

        # Simpson
        if word_total > 0:
            ld.simpson = 1.0 - sum((c / word_total) ** 2
                                    for c in word_counter.values())

        # Hapax
        hapax_count = sum(1 for c in word_counter.values() if c == 1)
        ld.hapax_ratio = hapax_count / max(word_unique, 1)

        # 香农熵
        ld.entropy = _shannon_entropy(word_counter, word_total)

        return ld

    def summary(self) -> str:
        return (
            f"字TTR={self.char_ttr:.3f} 词TTR={self.word_ttr:.3f} "
            f"MTLD={self.mtld:.1f} Simpson={self.simpson:.3f} "
            f"Hapax={self.hapax_ratio:.2f}"
        )


# ================================================================
# MTLD 实现
# ================================================================

def _compute_mtld(tokens: List[str], ttr_threshold: float = 0.72) -> float:
    """
    计算MTLD (Measure of Textual Lexical Diversity)。

    MTLD是TTR达到阈值时需要的平均词数。
    双向计算取平均以减少端点偏差。
    """
    if len(tokens) < 50:
        return 0.0

    def _mtld_one_direction(toks):
        factors = 0
        factor_size = 0
        seen: Set[str] = set()
        for token in toks:
            factor_size += 1
            seen.add(token)
            ttr = len(seen) / factor_size
            if ttr < ttr_threshold:
                factors += 1
                factor_size = 0
                seen.clear()
        # 残余部分的偏因子
        if factor_size > 0:
            residual_ttr = (1.0 - len(seen) / factor_size) / (1.0 - ttr_threshold)
            factors += residual_ttr
        return len(toks) / factors if factors > 0 else len(toks)

    forward = _mtld_one_direction(tokens)
    backward = _mtld_one_direction(list(reversed(tokens)))
    return (forward + backward) / 2.0


# ================================================================
# HD-D 实现
# ================================================================

def _compute_hdd(tokens: List[str], counter: Counter,
                  sample_size: int = 42) -> float:
    """
    基于超几何分布的HD-D值。

    对每个词类型，计算在随机sample_size个token中至少出现1次的概率。
    所有类型的概率求和即为HD-D。
    """
    N = len(tokens)
    if N < sample_size:
        return 0.0

    hd_d = 0.0
    for freq in counter.values():
        # P(X≥1) = 1 - P(X=0) = 1 - C(N-freq, sample) / C(N, sample)
        # 用近似: 1 - ((N - freq) / N) ^ sample
        prob = 1.0 - ((N - freq) / N) ** sample_size
        hd_d += prob
    return hd_d


# ================================================================
# 香农熵
# ================================================================

def _shannon_entropy(counter: Counter, total: int) -> float:
    """计算词频香农熵"""
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total)
                for c in counter.values() if c > 0)


# ================================================================
# 便捷函数
# ================================================================

def compute_all_diversity(text: str) -> LexicalDiversity:
    """一次性计算全部词汇多样性指标"""
    return LexicalDiversity.from_text(text)
