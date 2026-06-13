"""
盘古数学 · 风格指纹量化

将章节文本映射为固定维度的风格向量，支持:
  - 风格指纹提取: 文本 → 20维风格向量
  - 风格距离: 两章/两作者之间的风格差异
  - 风格聚类: 识别相似风格的作品群
  - AI/真人判别: 基于风格指纹的AI写作检测
  - 题材匹配: 当前文本离哪个题材标准最近

20维风格空间 (借鉴Stylometry):
  1-3:   句法维 (句均/句CV/长短比)
  4-5:   词汇维 (TTR/Hapax)
  6-9:   标点维 (,。！？占比)
  10-13: 词性维 (动作/形容/名词/虚词占比)
  14-16: 段落维 (段均/段CV/短段比)
  17-18: 对话维 (对话率/平均对话长度)
  19-20: 情绪维 (正面词密度/负面词密度)

用法:
    sf = StyleFingerprint.from_text(chapter_text)
    vector = sf.to_vector()        # 20维向量
    distance = sf.distance(other_sf)  # 风格距离
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import Counter

from ..accelerated import Vector


# ================================================================
# 词库
# ================================================================

_ACTION_WORDS = {"冲","杀","砍","刺","挥","射","跑","跳","躲","闪","挡",
                 "击","踢","打","抓","握","扔","推","拉","抱","追","逃",
                 "站","走","坐","躺","倒","翻","转"}

_ADJ_WORDS = {"美","丑","大","小","高","低","长","短","快","慢","厚","薄",
              "亮","暗","冷","热","新","旧","好","坏","强","弱","轻","重",
              "深","浅","多","少","远","近","白","黑","红","绿","蓝"}

_NOUN_WORDS = {"人","手","眼","头","脸","心","声","门","窗","桌","椅",
               "灯","墙","地","天","水","火","风","雨","云","月","日",
               "花","树","路","车","房","屋","街","城","山","海"}

_FUNCTION_WORDS = {"的","了","在","是","有","和","就","不","也","都",
                   "要","会","可","能","还","很","把","被","从","对"}

_POS_WORDS = {"好","美","强","爽","喜","乐","笑","爱","暖","光","胜利",
              "成功","突破","觉醒","强大","完美","幸福","快乐","满意",
              "获得","拥有","创造","新生"}

_NEG_WORDS = {"死","灭","毁","暗","冷","痛","恨","怒","怕","惨","绝望",
              "崩溃","恐惧","危险","痛苦","折磨","悲伤","伤心","愤怒",
              "失败","背叛","陷阱","阴谋","黑暗","深渊"}


# ================================================================
# 风格指纹
# ================================================================

@dataclass
class StyleFingerprint:
    """20维风格指纹"""
    label: str = ""  # 可选的标签 (如 "Ch1" / "林屿视角")

    # 原始特征值 (归一化前)
    features: List[float] = field(default_factory=lambda: [0.0] * 20)

    @classmethod
    def from_text(cls, text: str, label: str = ""):
        sf = cls(label=label)
        chars = re.findall(r'[一-鿿]', text)
        total_chars = max(len(chars), 1)

        # === 句法维 (1-3) ===
        sentences = [s.strip() for s in re.split(r'[。！？!?\n]', text) if len(s.strip()) >= 2]
        if sentences:
            sent_lens = [len(s) for s in sentences]
            mean_sl = sum(sent_lens) / len(sent_lens)
            std_sl = math.sqrt(sum((l - mean_sl)**2 for l in sent_lens) / len(sent_lens))
            cv_sl = std_sl / mean_sl if mean_sl > 0 else 0.0
            long_ratio = sum(1 for l in sent_lens if l >= 31) / len(sent_lens)
            sf.features[0] = _norm(mean_sl, 5, 50)       # 句均
            sf.features[1] = min(cv_sl, 1.5)             # 句CV
            sf.features[2] = long_ratio                  # 长句比

        # === 词汇维 (4-5) ===
        unique_chars = len(set(chars))
        ttr = unique_chars / total_chars
        char_cnt = Counter(chars)
        hapax = sum(1 for c in char_cnt.values() if c == 1) / max(unique_chars, 1)
        sf.features[3] = ttr
        sf.features[4] = hapax

        # === 标点维 (6-9) ===
        comma = text.count('，') / total_chars
        period = text.count('。') / total_chars
        question = text.count('？') / total_chars
        exclaim = text.count('！') / total_chars
        sf.features[5] = min(comma * 30, 1.0)
        sf.features[6] = min(period * 30, 1.0)
        sf.features[7] = min(question * 50, 1.0)
        sf.features[8] = min(exclaim * 50, 1.0)

        # === 词性维 (10-13) ===
        action_count = sum(text.count(w) for w in _ACTION_WORDS)
        adj_count = sum(text.count(w) for w in _ADJ_WORDS)
        noun_count = sum(text.count(w) for w in _NOUN_WORDS)
        func_count = sum(text.count(w) for w in _FUNCTION_WORDS)
        sf.features[9] = min(action_count / total_chars * 10, 1.0)
        sf.features[10] = min(adj_count / total_chars * 10, 1.0)
        sf.features[11] = min(noun_count / total_chars * 8, 1.0)
        sf.features[12] = min(func_count / total_chars * 5, 1.0)

        # === 段落维 (14-16) ===
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        if len(paragraphs) > 1:
            para_lens = [len(p) for p in paragraphs]
            mean_pl = sum(para_lens) / len(para_lens)
            std_pl = math.sqrt(sum((l - mean_pl)**2 for l in para_lens) / len(para_lens))
            cv_pl = std_pl / mean_pl if mean_pl > 0 else 0.0
            short_para_ratio = sum(1 for l in para_lens if l <= 80) / len(para_lens)
            sf.features[13] = _norm(mean_pl, 50, 500)
            sf.features[14] = min(cv_pl, 1.5)
            sf.features[15] = short_para_ratio

        # === 对话维 (17-18) ===
        dialogues = re.findall(r'[""「]([^""」]{2,})[""」]', text)
        if dialogues:
            dia_chars = sum(len(d) for d in dialogues)
            dia_ratio = dia_chars / total_chars
            avg_dia_len = dia_chars / len(dialogues)
            sf.features[16] = dia_ratio
            sf.features[17] = _norm(avg_dia_len, 5, 50)

        # === 情绪维 (19-20) ===
        pos_count = sum(text.count(w) for w in _POS_WORDS)
        neg_count = sum(text.count(w) for w in _NEG_WORDS)
        sf.features[18] = min(pos_count / total_chars * 20, 1.0)
        sf.features[19] = min(neg_count / total_chars * 20, 1.0)

        return sf

    def to_vector(self) -> Vector:
        """导出为20维Vector"""
        return Vector(self.features[:])

    def distance(self, other: StyleFingerprint) -> float:
        """风格距离 (欧氏距离)"""
        return self.to_vector().distance(other.to_vector())

    def cosine_similarity(self, other: StyleFingerprint) -> float:
        """风格余弦相似度"""
        return self.to_vector().cosine(other.to_vector())

    def dimension_names(self) -> List[str]:
        """返回每个维度的名称"""
        return [
            "句均", "句CV", "长句比",
            "TTR", "Hapax",
            "逗号", "句号", "问号", "叹号",
            "动作词", "形容词", "名词", "虚词",
            "段均", "段CV", "短段比",
            "对话率", "对话均长",
            "正面情绪", "负面情绪",
        ]

    def top_dimensions(self, n: int = 5) -> List[Tuple[str, float]]:
        """返回值最大的n个维度"""
        names = self.dimension_names()
        pairs = list(zip(names, self.features))
        pairs.sort(key=lambda x: -x[1])
        return pairs[:n]


def _norm(val: float, lo: float, hi: float) -> float:
    """将值映射到 [0, 1] 区间"""
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))


# ================================================================
# 风格分析
# ================================================================

def compute_style_vector(text: str, label: str = "") -> Vector:
    """便捷函数: 一次调用获取风格向量"""
    sf = StyleFingerprint.from_text(text, label)
    return sf.to_vector()


def style_distance(text1: str, text2: str) -> float:
    """两段文本的风格距离"""
    sf1 = StyleFingerprint.from_text(text1, "A")
    sf2 = StyleFingerprint.from_text(text2, "B")
    return sf1.distance(sf2)


def detect_style_drift(chapter_vectors: List[Vector],
                        threshold: float = 0.3) -> List[int]:
    """
    检测风格漂移: 找出风格突变(与前章距离>阈值)的章节。

    Returns: 风格突变的章节索引列表
    """
    drift_chapters = []
    for i in range(1, len(chapter_vectors)):
        d = chapter_vectors[i].distance(chapter_vectors[i-1])
        if d > threshold:
            drift_chapters.append(i)
    return drift_chapters


def classify_genre(fingerprint: StyleFingerprint,
                   genre_centroids: Dict[str, Vector]) -> str:
    """
    将风格指纹匹配到最近的题材中心。

    Args:
        fingerprint: 待分类的风格指纹
        genre_centroids: {题材名: 标准风格向量}

    Returns: 最近题材名
    """
    best_genre = "general"
    best_sim = -1.0
    vec = fingerprint.to_vector()

    for genre, centroid in genre_centroids.items():
        sim = vec.cosine(centroid)
        if sim > best_sim:
            best_sim = sim
            best_genre = genre

    return best_genre
