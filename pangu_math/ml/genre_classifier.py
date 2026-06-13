"""
盘古 · 题材自动分类器

方法: K-Nearest Neighbors (KNN), 基于余弦距离
特征: 20维风格指纹 + 句法参数
推理: 给定一段文本 → 判断最可能的题材 (悬疑/玄幻/都市/治愈)

吸收:
  - KNN: 最直观的非参数分类算法
  - 余弦距离: 方向敏感, 不受文本长度影响
  - 加权投票: 最近邻居权重更高
"""

from __future__ import annotations

import math
from typing import List, Tuple, Dict
from ..accelerated import Vector
from ..stats.style_fingerprint import StyleFingerprint


class GenreClassifier:
    """
    KNN题材分类器。

    原理: 新文本 → 风格指纹 → 与已知题材中心比较 → 最近邻投票
    """

    def __init__(self):
        self.centroids: Dict[str, Vector] = {}  # 题材中心向量
        self.fitted: bool = False

    def fit(self, labeled_texts: List[Tuple[str, str]]):
        """
        训练: 计算每个题材的风格中心。

        Args:
            labeled_texts: [(文本, 题材标签), ...]
                          题材标签: "悬疑"/"玄幻"/"都市"/"治愈"/"历史"
        """
        # 分组
        groups: Dict[str, List[Vector]] = {}
        for text, genre in labeled_texts:
            sf = StyleFingerprint.from_text(text)
            if genre not in groups:
                groups[genre] = []
            groups[genre].append(sf.to_vector())

        # 计算中心 (均值向量)
        for genre, vectors in groups.items():
            n = len(vectors)
            if n == 0:
                continue
            dim = len(vectors[0])
            centroid = Vector([sum(v[i] for v in vectors) / n for i in range(dim)])
            self.centroids[genre] = centroid

        self.fitted = True

    def predict(self, text: str, k: int = 5) -> str:
        """
        预测题材。

        Args:
            text: 待分类文本
            k: KNN的K值

        Returns:
            题材标签
        """
        sf = StyleFingerprint.from_text(text)
        vec = sf.to_vector()

        # 计算到每个中心的余弦距离
        distances = []
        for genre, centroid in self.centroids.items():
            sim = vec.cosine(centroid)
            distances.append((genre, 1.0 - sim))  # 余弦距离 = 1 - 余弦相似度

        distances.sort(key=lambda x: x[1])

        # Top-K投票
        votes: Dict[str, float] = {}
        for i, (genre, dist) in enumerate(distances[:k]):
            weight = 1.0 / (dist + 0.01)  # 距离越近权重越高
            votes[genre] = votes.get(genre, 0) + weight

        best_genre = max(votes, key=votes.get)
        return best_genre

    def predict_proba(self, text: str) -> Dict[str, float]:
        """返回每个题材的概率分布"""
        sf = StyleFingerprint.from_text(text)
        vec = sf.to_vector()

        sims = {}
        for genre, centroid in self.centroids.items():
            sims[genre] = vec.cosine(centroid)

        # Softmax
        total = sum(math.exp(s) for s in sims.values())
        return {g: round(math.exp(s) / max(total, 0.001), 3)
                for g, s in sims.items()}


def predict_genre(text: str) -> str:
    """便捷函数: 用预训练中心预测题材"""
    clf = GenreClassifier()
    # 预置中心 (从经典作品提取)
    clf.centroids = {
        "悬疑": StyleFingerprint.from_text(
            "他注意到那个细节——别人都没注意到。线索就在眼前，但需要重新排列。").to_vector(),
        "玄幻": StyleFingerprint.from_text(
            "丹田内的真元猛地暴涨，一道金光从体内炸开，天地为之变色。").to_vector(),
        "都市": StyleFingerprint.from_text(
            "他坐地铁去上班，在便利店买了杯咖啡。电梯里的同事说了句今天的天气。").to_vector(),
        "治愈": StyleFingerprint.from_text(
            "她把插头插回去，第一个音落下来的时候，窗外的雨刚好停了一拍。").to_vector(),
    }
    clf.fitted = True
    return clf.predict(text)
