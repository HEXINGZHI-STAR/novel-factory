"""
盘古数学 · 文本分布分析

对章节文本的句长、段长、对话长度进行统计分布建模。
核心指标:
  - 正态性检验 (偏度/峰度/K-S距离)
  - Gamma分布拟合 (句长分布通常右偏)
  - 变异系数 CV = σ/μ (盘古核心指标)
  - 最大/最小比 (节奏冲击)
  - 连续短句检测 (AI味指标)
  - 长短交替率 (真人写作特征)

用法:
    stats = SentenceStats.from_text(chapter_text)
    print(f"句均: {stats.mean:.1f}, CV: {stats.cv:.3f}")
    print(f"连续短句最长: {stats.max_consecutive_short}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from collections import Counter


# ================================================================
# 分句/分段工具
# ================================================================

def split_sentences(text: str) -> List[str]:
    """按中文标点分句，保留有意义长度的句子"""
    raw = re.split(r'[。！？!?\n]', text)
    return [s.strip() for s in raw if len(s.strip()) >= 2]

def split_paragraphs(text: str) -> List[str]:
    """按空行分段落"""
    return [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

def extract_dialogues(text: str) -> List[str]:
    """提取引号内的对话"""
    return re.findall(r'[""「]([^""」 ]{2,})[""」]', text)


# ================================================================
# 分布统计
# ================================================================

@dataclass
class DistributionStats:
    """单变量分布统计"""
    values: List[float] = field(repr=False)
    n: int = 0
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    cv: float = 0.0             # 变异系数 = std/mean
    skewness: float = 0.0       # 偏度 (正=右偏)
    kurtosis: float = 0.0       # 超额峰度 (正=尖峰)
    min_val: float = 0.0
    max_val: float = 0.0
    max_min_ratio: float = 0.0  # 最长/最短比 (盘古节奏指标)
    percentile_25: float = 0.0
    percentile_75: float = 0.0
    percentile_90: float = 0.0
    histogram: List[Tuple[float, float, int]] = field(default_factory=list)  # (bin_start, bin_end, count)

    @classmethod
    def from_values(cls, values: List[float]):
        if not values:
            return cls(values=[])
        n = len(values)
        sorted_vals = sorted(values)
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        cv = std / mean if mean > 0 else 0.0

        # 偏度 (skewness)
        if std > 0:
            skewness = sum(((v - mean) / std) ** 3 for v in values) / n
            kurtosis = sum(((v - mean) / std) ** 4 for v in values) / n - 3.0
        else:
            skewness, kurtosis = 0.0, 0.0

        # 分位数
        def percentile(p):
            idx = int(n * p / 100.0)
            return sorted_vals[min(idx, n - 1)]

        # 直方图 (10 bins)
        hist_bins = 10
        bin_width = (sorted_vals[-1] - sorted_vals[0]) / hist_bins if sorted_vals[-1] > sorted_vals[0] else 1.0
        hist = []
        for b in range(hist_bins):
            lo = sorted_vals[0] + b * bin_width
            hi = lo + bin_width
            cnt = sum(1 for v in values if lo <= v < hi)
            hist.append((round(lo, 1), round(hi, 1), cnt))

        return cls(
            values=values, n=n,
            mean=round(mean, 2), median=percentile(50),
            std=round(std, 2), cv=round(cv, 4),
            skewness=round(skewness, 4), kurtosis=round(kurtosis, 4),
            min_val=sorted_vals[0], max_val=sorted_vals[-1],
            max_min_ratio=round(sorted_vals[-1] / sorted_vals[0], 1) if sorted_vals[0] > 0 else 0,
            percentile_25=percentile(25), percentile_75=percentile(75),
            percentile_90=percentile(90),
            histogram=hist,
        )

    def summary(self) -> str:
        """人类可读的分布摘要"""
        return (
            f"n={self.n} μ={self.mean} σ={self.std} CV={self.cv:.3f} "
            f"偏度={self.skewness:.2f} 峰度={self.kurtosis:.2f} "
            f"max/min={self.max_min_ratio:.1f}"
        )


# ================================================================
# 句子级统计
# ================================================================

@dataclass
class SentenceStats:
    """句子级别统计分析"""
    char_counts: List[int] = field(default_factory=list)
    dist: Optional[DistributionStats] = None

    # 盘古核心指标
    mean_sentence_length: float = 0.0       # μ_L (目标 ≥ 25-30，但治愈系 12-18)
    cv_sentence_length: float = 0.0         # CV_L (目标 ≥ 0.30)
    long_sentence_ratio: float = 0.0        # p_long: ≥31字的句子占比
    short_sentence_ratio: float = 0.0       # ≤12字的句子占比

    # 连续短句检测 (AI味核心指标)
    max_consecutive_short: int = 0          # 最长连续短句(≤12字)串
    consecutive_short_runs: int = 0         # 连续短句串的数量

    # 长短交替
    alternation_rate: float = 0.0           # 长→短→长的切换频率

    @classmethod
    def from_text(cls, text: str):
        sentences = split_sentences(text)
        char_counts = [len(s) for s in sentences]
        return cls.from_counts(char_counts)

    @classmethod
    def from_counts(cls, char_counts: List[int]):
        if not char_counts:
            return cls()
        stats = cls()
        stats.char_counts = char_counts
        stats.dist = DistributionStats.from_values([float(c) for c in char_counts])

        n = len(char_counts)
        stats.mean_sentence_length = sum(char_counts) / n
        stats.cv_sentence_length = (stats.dist.std / stats.mean_sentence_length
                                     if stats.mean_sentence_length > 0 else 0.0)
        stats.long_sentence_ratio = sum(1 for c in char_counts if c >= 31) / n
        stats.short_sentence_ratio = sum(1 for c in char_counts if c <= 12) / n

        # 连续短句检测
        consecutive = 0
        max_consec = 0
        run_count = 0
        for c in char_counts:
            if c <= 12:
                consecutive += 1
            else:
                if consecutive >= 3:
                    run_count += 1
                max_consec = max(max_consec, consecutive)
                consecutive = 0
        if consecutive >= 3:
            run_count += 1
        max_consec = max(max_consec, consecutive)
        stats.max_consecutive_short = max_consec
        stats.consecutive_short_runs = run_count

        # 长短交替率
        switches = 0
        for i in range(1, n):
            prev_long = char_counts[i-1] > 25
            curr_long = char_counts[i] > 25
            if prev_long != curr_long:
                switches += 1
        stats.alternation_rate = switches / max(n - 1, 1)

        return stats

    def ai_risk_score(self) -> float:
        """AI写作风险评分 (0-1, 越高越像AI)"""
        score = 0.0
        # 句均太短
        if self.mean_sentence_length < 15:
            score += 0.3
        elif self.mean_sentence_length < 20:
            score += 0.15
        # 连续短句
        if self.max_consecutive_short >= 5:
            score += 0.3
        elif self.max_consecutive_short >= 3:
            score += 0.15
        # CV过低 (句子一样长)
        if self.cv_sentence_length < 0.25:
            score += 0.2
        # 长短不交替
        if self.alternation_rate < 0.2:
            score += 0.2
        return min(1.0, score)

    def summary(self) -> str:
        return (
            f"句均={self.mean_sentence_length:.1f}字 "
            f"CV={self.cv_sentence_length:.3f} "
            f"长句比={self.long_sentence_ratio:.1%} "
            f"AI风险={self.ai_risk_score():.2f}"
        )


# ================================================================
# 章节级统计
# ================================================================

@dataclass
class ChapterStats:
    """章节级综合统计分析"""
    sentence: SentenceStats
    paragraph_lengths: DistributionStats
    dialogue_ratio: float           # 对话率
    dialogue_count: int             # 对话段数
    avg_dialogue_length: float      # 平均对话长度
    description_ratio: float        # 描写占比 (粗略)
    narration_ratio: float          # 叙述占比
    action_ratio: float             # 动作占比
    paragraph_alternation: float    # 段长交替率

    @classmethod
    def from_text(cls, text: str):
        sent = SentenceStats.from_text(text)
        paragraphs = split_paragraphs(text)
        para_lens = [len(p) for p in paragraphs]
        para_dist = DistributionStats.from_values([float(l) for l in para_lens])

        # 对话分析
        dialogues = extract_dialogues(text)
        dialogue_chars = sum(len(d) for d in dialogues)
        total_chars = len(text.replace('\n', '').replace(' ', ''))
        dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0.0
        avg_dial_len = dialogue_chars / len(dialogues) if dialogues else 0.0

        # 粗略体裁分类
        desc_ratio, narr_ratio, action_ratio = cls._classify_content(text, total_chars)

        # 段长交替
        if len(para_lens) > 1:
            para_switches = sum(1 for i in range(1, len(para_lens))
                                if (para_lens[i] > 200) != (para_lens[i-1] > 200))
            para_alt = para_switches / (len(para_lens) - 1)
        else:
            para_alt = 0.0

        return cls(
            sentence=sent,
            paragraph_lengths=para_dist,
            dialogue_ratio=round(dialogue_ratio, 3),
            dialogue_count=len(dialogues),
            avg_dialogue_length=round(avg_dial_len, 1),
            description_ratio=round(desc_ratio, 3),
            narration_ratio=round(narr_ratio, 3),
            action_ratio=round(action_ratio, 3),
            paragraph_alternation=round(para_alt, 3),
        )

    @staticmethod
    def _classify_content(text: str, total_chars: int) -> Tuple[float, float, float]:
        """基于关键词粗略估算描写/叙述/动作占比"""
        action_words = {"冲","杀","砍","刺","挥","射","跑","跳","躲","闪",
                        "挡","击","踢","打","抓","握","扔","推","拉","抱",
                        "追","逃","退","进","攻","守"}
        desc_words = {"美丽","明亮","黑暗","温暖","寒冷","安静","嘈杂",
                      "光","颜色","颜色","形状","纹理","质地",
                      "阳光","灯","影子","天气","雨","风","雪"}

        action_count = sum(text.count(w) for w in action_words)
        desc_count = sum(text.count(w) for w in desc_words)

        total = max(total_chars, 1)
        return (
            desc_count * 20 / total,       # 描写估算
            (total_chars - action_count * 15 - desc_count * 20) / total,  # 叙述
            action_count * 15 / total,     # 动作估算
        )

    def quality_pass(self, mode: str = "general") -> Tuple[bool, List[str]]:
        """检查是否通过盘古质量门槛"""
        issues = []
        sent = self.sentence

        if sent.max_consecutive_short >= 5:
            issues.append(f"连续短句过长({sent.max_consecutive_short}句)")
        if sent.ai_risk_score() > 0.6:
            issues.append(f"AI味风险过高({sent.ai_risk_score():.2f})")
        if self.dialogue_ratio > 0.6:
            issues.append(f"对话率过高({self.dialogue_ratio:.0%})")
        if sent.cv_sentence_length < 0.20:
            issues.append(f"句长变化不足(CV={sent.cv_sentence_length:.3f})")

        return len(issues) == 0, issues

    def summary(self) -> str:
        return (
            f"句子: {self.sentence.summary()}\n"
            f"段落: {self.paragraph_lengths.summary()}\n"
            f"对话率: {self.dialogue_ratio:.1%} "
            f"段交替: {self.paragraph_alternation:.3f}"
        )
