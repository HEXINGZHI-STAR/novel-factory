"""
盘古 · 数学语言学指标

吸收学术成果:
  - 标点Zipf律 + Weibull分布: arXiv:2503.04449, 2025
  - 认知风格计量/陌生化: Kurzynski, Computational Humanities Research, 2025
  - 词邻接网络拓扑: Dec et al., Physical Review E, 2025
  - 跨语言最小作者识别量: Ryabko et al., Entropy, 2025

盘古应用:
  - 标点规律检测: AI文本标点太均匀 → AI味指标
  - 陌生化评分: 文本偏离预期的程度 → 文采/创造力指标
  - 词网络复杂性: 词汇使用模式的丰富度
"""

from __future__ import annotations

import re
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter
from dataclasses import dataclass, field


# ================================================================
# 标点规律分析 (arXiv:2503.04449)
# ================================================================

@dataclass
class PunctuationMetrics:
    """
    标点统计指标。

    论文发现:
      - 中文标点服从Zipf律 (包括标点后)
      - 标点间隔服从离散Weibull分布
      - 句末标点 (。！？) 比句内标点 (，、；) 更能体现个人风格
      - AI文本的标点使用比真人更"规律"——Weibull形状参数更小
    """
    comma_ratio: float = 0.0        # 逗号占比
    period_ratio: float = 0.0       # 句号占比
    question_ratio: float = 0.0     # 问号占比
    exclaim_ratio: float = 0.0      # 叹号占比
    punct_entropy: float = 0.0      # 标点熵 (越高=标点使用越多样)
    avg_interval: float = 0.0       # 平均标点间隔 (字)
    interval_std: float = 0.0       # 标点间隔标准差
    weibull_shape: float = 0.0      # Weibull形状参数 (越小=越规律=越像AI)
    zipf_adherence: float = 0.0     # Zipf律符合度 (0-1)

    @property
    def ai_likelihood(self) -> float:
        """
        标点规律判定AI味。
        Weibull形状<1.5 + 标点熵<1.0 → 高度疑似AI。
        """
        score = 0.0
        if self.weibull_shape < 1.5:
            score += 0.4
        if self.punct_entropy < 1.0:
            score += 0.3
        if abs(self.zipf_adherence - 1.0) < 0.1:
            score += 0.2  # 太完美地符合Zipf=AI
        if self.interval_std / max(self.avg_interval, 1) < 0.5:
            score += 0.1  # 标点间隔太均匀
        return min(1.0, score)


def analyze_punctuation(text: str) -> PunctuationMetrics:
    """
    标点规律分析。

    基于 arXiv:2503.04449 的方法:
      1. 计算标点频率分布 → 熵
      2. 计算标点间隔 → Weibull分布拟合
      3. 验证Zipf律 → 符合度
    """
    m = PunctuationMetrics()

    # 统计标点
    punct_chars = {"，": 0, "。": 0, "？": 0, "！": 0, "、": 0, "；": 0, "：": 0}
    total_punct = 0
    positions = []  # 标点位置

    for i, ch in enumerate(text):
        if ch in punct_chars:
            punct_chars[ch] += 1
            total_punct += 1
            positions.append(i)

    if total_punct == 0:
        return m

    # 1. 标点频率
    m.comma_ratio = punct_chars["，"] / total_punct
    m.period_ratio = punct_chars["。"] / total_punct
    m.question_ratio = punct_chars["？"] / total_punct
    m.exclaim_ratio = punct_chars["！"] / total_punct

    # 2. 标点熵
    m.punct_entropy = -sum(
        (c / total_punct) * math.log2(c / total_punct)
        for c in punct_chars.values() if c > 0
    )
    # 归一化: 除以最大可能熵 log2(7)
    m.punct_entropy /= math.log2(7)

    # 3. 标点间隔 (字)
    if len(positions) > 1:
        intervals = [positions[i] - positions[i-1]
                     for i in range(1, len(positions))]
        m.avg_interval = sum(intervals) / len(intervals)
        m.interval_std = math.sqrt(
            sum((x - m.avg_interval) ** 2 for x in intervals) / len(intervals))

        # Weibull形状参数 (简化估计: cv的倒数)
        # shape < 1 = 递减失效率 (规律性高=AI)
        # shape > 1 = 递增失效率 (不规律=人类)
        cv = m.interval_std / max(m.avg_interval, 0.1)
        m.weibull_shape = max(0.3, 1.0 / cv)

    # 4. Zipf律符合度
    # 标点频率应服从幂律分布: f(r) ∝ 1/r^α
    ranked = sorted(punct_chars.values(), reverse=True)
    ranked = [r for r in ranked if r > 0]
    if len(ranked) >= 3:
        # 计算α: log(f) = -α*log(r) + C
        log_r = [math.log(i + 1) for i in range(len(ranked))]
        log_f = [math.log(r) for r in ranked]
        n = len(log_r)
        # 简单线性回归斜率
        a_r = sum(log_r) / n
        a_f = sum(log_f) / n
        num = sum((log_r[i] - a_r) * (log_f[i] - a_f) for i in range(n))
        den = sum((log_r[i] - a_r) ** 2 for i in range(n))
        alpha = -num / den if den > 0 else 0
        # Zipf律: α应≈1.0
        m.zipf_adherence = 1.0 - min(1.0, abs(alpha - 1.0))

    return m


# ================================================================
# 陌生化/创造力评分 (Cognitive Stylometry, Cambridge 2025)
# ================================================================

@dataclass
class DefamiliarizationMetrics:
    """
    陌生化指标 (基于 Kurzynski 2025 的迷惑度地形图)。

    原理:
      - 用GPT预测文本中每个词的概率
      - 低概率词 = 出乎意料 = 陌生化 = 创造力
      - 高概率词 = 可预测 = 平淡 = AI味

    简化版 (无GPT): 用n-gram稀有度近似
    """
    rare_bigram_ratio: float = 0.0     # 稀有2-gram占比
    hapax_legomena_ratio: float = 0.0  # 仅出现一次的词占比
    creativity_score: float = 0.0       # 综合创造力 (0=平淡, 1=高度陌生化)

    @property
    def verdict(self) -> str:
        if self.creativity_score > 0.7:
            return "高度陌生化——文采斐然，读者感到新鲜"
        elif self.creativity_score > 0.4:
            return "适度陌生化——有文采但不晦涩"
        elif self.creativity_score > 0.2:
            return "可预测性高——内容平淡，缺乏惊喜"
        else:
            return "高度可预测——AI味严重，千篇一律"


def analyze_defamiliarization(text: str) -> DefamiliarizationMetrics:
    """
    陌生化分析。

    基于 Kurzynski (2025) 的方法，简化为n-gram稀有度。
    """
    m = DefamiliarizationMetrics()
    chars = re.sub(r'[^一-鿿]', '', text)

    if len(chars) < 10:
        return m

    # 2-gram统计
    bigrams = [chars[i:i+2] for i in range(len(chars) - 1)]
    bigram_counter = Counter(bigrams)

    # 稀有bigram: 仅出现1-2次
    rare = sum(1 for c in bigram_counter.values() if c <= 2)
    m.rare_bigram_ratio = rare / max(len(bigram_counter), 1)

    # Hapax legomena: 仅出现一次
    unigrams = Counter(chars)
    hapax = sum(1 for c in unigrams.values() if c == 1)
    m.hapax_legomena_ratio = hapax / max(len(unigrams), 1)

    # 创造力 = 稀有组合 + 单次出现词
    m.creativity_score = min(1.0,
        m.rare_bigram_ratio * 0.6 + m.hapax_legomena_ratio * 0.4)

    return m


# ================================================================
# 词网络复杂性 (Physical Review E, 2025)
# ================================================================

@dataclass
class WordNetworkMetrics:
    """
    词汇网络拓扑指标。

    基于 Dec et al. (2025):
      - 将文本构建为词邻接网络 (每个词是一个节点，相邻共现=边)
      - 计算平均最短路径长度、聚类系数
      - 中文加入标点后，与英文网络拓扑趋同
    """
    avg_path_length: float = 0.0     # 平均最短路径
    clustering_coeff: float = 0.0    # 聚类系数
    network_density: float = 0.0     # 网络密度
    small_worldness: float = 0.0     # 小世界性 (>1=小世界网络)


def analyze_word_network(text: str, window: int = 5) -> WordNetworkMetrics:
    """
    词汇网络分析。

    构建共现网络: 窗口内任意两个词之间连边。
    """
    m = WordNetworkMetrics()
    chars = re.sub(r'[^一-鿿]', '', text)
    words = [chars[i:i+2] for i in range(len(chars) - 1)]

    if len(words) < 20:
        return m

    # 选top-200高频词构建网络 (完整网络太大)
    counter = Counter(words)
    top_words = set(w for w, _ in counter.most_common(200))

    # 共现窗口内构建邻接表
    edges = set()
    for i in range(len(words) - window):
        window_words = [w for w in words[i:i+window] if w in top_words]
        for j in range(len(window_words)):
            for k in range(j + 1, len(window_words)):
                a, b = window_words[j], window_words[k]
                if a != b:
                    edges.add((min(a, b), max(a, b)))

    # 计算指标
    nodes = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    n = len(nodes)
    e = len(edges)

    if n < 2:
        return m

    # 网络密度
    max_edges = n * (n - 1) / 2
    m.network_density = e / max_edges if max_edges > 0 else 0.0

    # 平均度
    avg_degree = 2 * e / n

    # 平均最短路径 (近似: 密度越高路径越短)
    if m.network_density > 0.5:
        m.avg_path_length = 1.5
    elif m.network_density > 0.2:
        m.avg_path_length = 2.5
    else:
        m.avg_path_length = 4.0

    # 聚类系数 (近似)
    m.clustering_coeff = min(1.0, avg_degree / max(n, 1))

    # 小世界性 = (C/C_random) / (L/L_random)
    # 简化: C高 + L短 = 小世界
    c_random = avg_degree / max(n, 1)
    l_random = math.log(n) / math.log(max(avg_degree, 1))
    if c_random > 0 and l_random > 0:
        gamma = m.clustering_coeff / c_random if c_random > 0 else 0
        lam = m.avg_path_length / l_random if l_random > 0 else 0
        m.small_worldness = gamma / lam if lam > 0 else 0

    return m
