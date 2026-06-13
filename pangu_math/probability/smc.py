"""
盘古 · Sequential Monte Carlo (SMC) 替代随机采样

吸收: Lew et al. (2023), "Sequential Monte Carlo for Controlled LM Generation"
      arXiv: 2504.13139, 2025

原理:
  传统MC: random.sample() — 随机抽取，低效
  SMC:   每个样本有权重，根据观测结果重新分配权重 → 重采样
         → 高质量样本获得更多"后代"，低质量样本被淘汰

优势: 小模型用SMC可击败8倍大的模型
盘古应用: 替代 monte_carlo.py 中的 random.choices()

用法:
  smc = SMC(n_particles=200)
  results = smc.simulate(generate_fn, observe_fn, steps=12)
"""

from __future__ import annotations

import math
import random
from typing import List, Callable, Dict, Any


class SMCSimulator:
    """
    Sequential Monte Carlo 模拟器。

    每个"粒子"= 一个读者的追读路径。
    SMC在每一步做: 预测→观测→重加权→重采样。
    """

    def __init__(self, n_particles: int = 200,
                  resample_threshold: float = 0.5):
        self.n_particles = n_particles
        self.resample_threshold = resample_threshold
        self.particles: List[Dict] = []  # 当前粒子集

    def simulate(self,
                  transition_fn: Callable[[float], float],
                  observe_fn: Callable[[float], float],
                  steps: int = 12,
                  initial_value: float = 1.0) -> Dict[str, Any]:
        """
        SMC模拟。

        Args:
            transition_fn: 状态转移函数 f(current_value) → next_value
            observe_fn: 观测似然函数 f(value) → likelihood (0-1)
            steps: 模拟步数
            initial_value: 初始值

        Returns:
            模拟结果统计
        """
        # 初始化粒子
        self.particles = [
            {"value": initial_value, "weight": 1.0 / self.n_particles}
            for _ in range(self.n_particles)
        ]

        history = []

        for step in range(steps):
            # Step 1: 预测 (每个粒子根据转移函数推进)
            for p in self.particles:
                noise = random.gauss(0, 0.05)
                p["value"] = transition_fn(p["value"])
                p["value"] += noise
                p["value"] = max(0.01, min(1.0, p["value"]))

            # Step 2: 观测 (根据观测函数计算权重)
            total_weight = 0.0
            for p in self.particles:
                likelihood = observe_fn(p["value"])
                p["weight"] = max(0.001, likelihood)  # 避免零权重
                total_weight += p["weight"]

            # Step 3: 归一化权重
            for p in self.particles:
                p["weight"] /= total_weight

            # Step 4: 检查是否需要重采样
            ess = self._effective_sample_size()
            if ess < self.n_particles * self.resample_threshold:
                self._resample()

            # 记录当前步的统计
            values = [p["value"] for p in self.particles]
            values.sort()
            history.append({
                "step": step + 1,
                "p50": values[self.n_particles // 2],
                "p10": values[self.n_particles // 10],
                "p90": values[9 * self.n_particles // 10],
                "mean": sum(values) / len(values),
                "ess": round(ess),
            })

        final_values = sorted([p["value"] for p in self.particles])
        return {
            "p50": final_values[self.n_particles // 2],
            "p10": final_values[self.n_particles // 10],
            "p90": final_values[9 * self.n_particles // 10],
            "mean": sum(final_values) / len(final_values),
            "history": history,
        }

    def _effective_sample_size(self) -> float:
        """计算有效样本量 (ESS)。ESS < threshold → 需要重采样。"""
        w = [p["weight"] for p in self.particles]
        sum_w2 = sum(wi ** 2 for wi in w)
        if sum_w2 == 0:
            return 0.0
        return 1.0 / sum_w2

    def _resample(self):
        """系统重采样: 高权重粒子获得更多后代。"""
        weights = [p["weight"] for p in self.particles]
        n = self.n_particles

        # 累积权重
        cumsum = []
        s = 0.0
        for w in weights:
            s += w
            cumsum.append(s)

        # 系统采样
        new_particles = []
        u0 = random.random() / n
        j = 0
        for i in range(n):
            u = u0 + i / n
            while u > cumsum[j] and j < n - 1:
                j += 1
            # 复制粒子
            new_particles.append({
                "value": self.particles[j]["value"],
                "weight": 1.0 / n,
            })

        self.particles = new_particles


def smc_readership_sim(total_chapters: int = 12,
                        base_retention: float = 0.90,
                        n_particles: int = 200) -> Dict[str, Any]:
    """
    SMC读者留存模拟 (替代 monte_carlo.py 的 simulate_readership)。

    每个粒子 = 一个读者的留存率路径。
    """
    def transition(retention):
        return retention * base_retention * random.gauss(1.0, 0.08)

    def observe(retention):
        # 观测似然: 留存率越高越"真实"
        return max(0.01, retention)

    smc = SMCSimulator(n_particles=n_particles)
    return smc.simulate(transition, observe, steps=total_chapters)
