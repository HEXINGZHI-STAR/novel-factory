"""
盘古数学 · 概率论层

应用概率论到写作系统:
  - bayesian:     贝叶斯推断 — 在证据积累中更新"质量/设定矛盾/伏笔回收"的概率
  - monte_carlo:  蒙特卡洛模拟 — 模拟故事走向、读者反应、市场表现
  - stochastic:   随机过程 — 情绪马尔可夫链、叙事状态转移
"""

from .bayesian import BayesianUpdater, BayesianQualityModel
from .monte_carlo import MonteCarloPlotSimulator, monte_carlo_quality
from .stochastic import StochasticTensionModel, EmotionMarkovChain

__all__ = [
    "BayesianUpdater", "BayesianQualityModel",
    "MonteCarloPlotSimulator", "monte_carlo_quality",
    "StochasticTensionModel", "EmotionMarkovChain",
]
