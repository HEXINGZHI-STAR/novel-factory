"""
盘古 · 章节质量分类器

方法: 逻辑回归 (纯Python + numpy)
特征: 20维风格指纹 + 句法指标 + 对话率 + 张力节奏
训练: 有监督 (需要人工标注"优质/需改"标签)
预测: 0-1概率, >0.7=优质, <0.3=需重写

吸收:
  - 逻辑回归: 经典ML算法, 可解释性强 (每个特征有权重)
  - L2正则化: 防止过拟合
  - Sigmoid输出: 概率化
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional
from ..accelerated import Vector, Matrix


class QualityClassifier:
    """
    逻辑回归质量分类器。

    特征向量 (10维):
      0: 句均长度 (归一化)
      1: 句长CV
      2: 长句比
      3: 对话率
      4: AI风险 (反转: 1-AI风险)
      5: 词汇多样性 TTR
      6: 张力节奏质量
      7: 连续短句数 (反转)
      8: 段交替率
      9: 可读性分数 (归一化)
    """

    def __init__(self):
        self.weights: Optional[Vector] = None  # 10维权重
        self.bias: float = 0.0
        self.fitted: bool = False

    def _sigmoid(self, z: float) -> float:
        return 1.0 / (1.0 + math.exp(-z))

    def _extract_features(self, sentence_stats: dict, diversity_stats: dict,
                           tension_stats: dict, readability_score: float) -> Vector:
        """从盘古分析模块提取特征向量"""
        features = [
            min(sentence_stats.get("mean_len", 0) / 40, 1.0),  # 句均/40
            min(sentence_stats.get("cv", 0), 1.5),
            sentence_stats.get("long_ratio", 0),
            min(sentence_stats.get("dialogue_ratio", 0), 0.6),
            1.0 - sentence_stats.get("ai_risk", 0.5),  # 反转
            diversity_stats.get("char_ttr", 0.3),
            tension_stats.get("pacing_quality", 0.5),
            1.0 - min(sentence_stats.get("max_consecutive_short", 0) / 15, 1.0),
            sentence_stats.get("alternation_rate", 0.3),
            min(readability_score / 100, 1.0),
        ]
        return Vector(features)

    def fit(self, X: List[Vector], y: List[int],
             learning_rate: float = 0.01, epochs: int = 100) -> QualityClassifier:
        """
        训练逻辑回归模型。

        Args:
            X: 特征向量列表 (每个10维)
            y: 标签列表 (1=优质, 0=需改)
            learning_rate: 学习率
            epochs: 训练轮数
        """
        n_features = len(X[0])
        self.weights = Vector([0.0] * n_features)
        self.bias = 0.0
        n = len(X)

        for epoch in range(epochs):
            total_loss = 0.0
            for i in range(n):
                # 预测
                z = self.weights.dot(X[i]) + self.bias
                pred = self._sigmoid(z)

                # 梯度
                error = pred - y[i]
                grad_w = X[i] * (error / n)
                grad_b = error / n

                # L2正则化
                reg = 0.01
                grad_w = grad_w + self.weights * (reg / n)

                # 更新
                self.weights = self.weights - grad_w * learning_rate
                self.bias -= grad_b * learning_rate

                # 损失 (交叉熵)
                eps = 1e-9
                total_loss += -(y[i] * math.log(pred + eps) +
                                 (1 - y[i]) * math.log(1 - pred + eps))

            if epoch % 20 == 0:
                pass  # loss tracking

        self.fitted = True
        return self

    def predict_proba(self, features: Vector) -> float:
        """预测优质概率 (0-1)"""
        if not self.fitted:
            return 0.5
        z = self.weights.dot(features) + self.bias
        return self._sigmoid(z)

    def predict(self, features: Vector, threshold: float = 0.5) -> str:
        """预测分类标签"""
        proba = self.predict_proba(features)
        if proba > 0.75:
            return "优质"
        elif proba > 0.45:
            return "合格"
        else:
            return "需改"


def train_quality_model(training_data: List[Tuple[dict, int]]) -> QualityClassifier:
    """
    便捷函数: 从训练数据构建分类器。

    训练数据格式: [(指标dict, 标签), ...]
    标签: 1=优质, 0=需改
    """
    clf = QualityClassifier()
    X = []
    y = []
    for metrics, label in training_data:
        features = clf._extract_features(
            metrics.get("sentence", {}),
            metrics.get("diversity", {}),
            metrics.get("tension", {}),
            metrics.get("readability", 50),
        )
        X.append(features)
        y.append(label)

    if len(X) > 2:
        clf.fit(X, y)
    return clf
