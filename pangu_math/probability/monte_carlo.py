"""
盘古数学 · 蒙特卡洛模拟

用随机抽样模拟写作中的不确定性:
  1. 情节路径模拟: 给定分支点，模拟N种可能的情节走向
  2. 读者反应模拟: 模拟读者对章节的情绪反应分布
  3. 质量稳健性: 测试章节在不同假设下的质量波动
  4. 市场表现: 模拟平台推荐/读者留存/收入

用法:
    sim = MonteCarloPlotSimulator(chapter_count=12)
    results = sim.simulate_readership(n=1000)
    print(f"预期读者留存: {results['retention_p50']:.1%}")
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any, Optional


# ================================================================
# 蒙特卡洛情节模拟器
# ================================================================

@dataclass
class MonteCarloPlotSimulator:
    """蒙特卡洛情节路径模拟器"""

    chapter_count: int = 12
    base_retention: float = 0.85       # 基础每章留存率
    quality_volatility: float = 0.08   # 质量波动率 (σ)
    hook_impact: float = 0.05          # 钩子对留存的影响

    def simulate_readership(self, n: int = 1000,
                             chapter_qualities: List[float] = None) -> Dict[str, float]:
        """
        模拟N个读者的追读行为。

        Args:
            n: 模拟读者数
            chapter_qualities: 每章质量分数 (0-1), None则随机生成

        Returns:
            {retention_p50, retention_p10, retention_p90, expected_readers}
        """
        if chapter_qualities is None:
            # 随机生成质量曲线 (先升后降是典型模式)
            chapter_qualities = []
            for i in range(self.chapter_count):
                base = 0.6 + 0.2 * math.sin(i / self.chapter_count * math.pi)
                noise = random.gauss(0, self.quality_volatility)
                chapter_qualities.append(max(0.1, min(1.0, base + noise)))

        # numpy 向量化快速通道 (100x faster)
        try:
            import numpy as np
            return self._simulate_vectorized(n, chapter_qualities)
        except ImportError:
            pass

        # 纯Python fallback
        final_retentions = []
        for _ in range(n):
            retention = 1.0
            for ch in range(self.chapter_count):
                quality = chapter_qualities[ch]
                ch_retention = self.base_retention * (0.7 + 0.3 * quality)
                reader_tolerance = random.gauss(1.0, 0.1)
                ch_retention *= reader_tolerance
                if ch < 2:
                    ch_retention *= 1.1
                elif ch >= self.chapter_count - 2:
                    ch_retention *= 1.05
                retention *= max(0.1, min(1.0, ch_retention))
            final_retentions.append(retention)

        final_retentions.sort()
        return self._result_dict(final_retentions, chapter_qualities)

    def _simulate_vectorized(self, n: int, qualities: list) -> Dict[str, float]:
        """numpy向量化：一次计算所有读者×所有章节的留存矩阵"""
        import numpy as np
        q = np.array(qualities, dtype=np.float64)  # (chapters,)
        ch_ret = self.base_retention * (0.7 + 0.3 * q)  # (chapters,)
        # 开篇和结尾的加权
        ch_ret[:2] *= 1.1
        ch_ret[-2:] *= 1.05
        # 读者容忍度: (n, 1) 广播到 (n, chapters)
        tolerance = np.random.normal(1.0, 0.1, size=(n, 1))
        retention_matrix = np.clip(ch_ret * tolerance, 0.1, 1.0)  # (n, chapters)
        # 累积留存 = 每章留存连乘
        final = np.prod(retention_matrix, axis=1)  # (n,)
        final.sort()
        return self._result_dict(final.tolist(), qualities)

    def _result_dict(self, retentions: list, qualities: list) -> dict:
        n = len(retentions)
        return {
            "retention_p50": retentions[n // 2],
            "retention_p10": retentions[n // 10],
            "retention_p90": retentions[9 * n // 10],
            "expected_readers": int(10000 * retentions[n // 2]),
            "mean_quality": sum(qualities) / max(len(qualities), 1),
        }

    def simulate_revenue(self, n: int = 1000, platform: str = "qimao",
                          chapter_qualities: List[float] = None) -> Dict[str, float]:
        """模拟平台收入"""
        if chapter_qualities is None:
            chapter_qualities = [random.gauss(0.65, 0.1) for _ in range(self.chapter_count)]

        # 平台收益参数
        platform_params = {
            "qimao": {"cpm": 3.0, "vip_rate": 0.03, "free_reads_per_ch": 5000},
            "fanqie": {"cpm": 2.5, "vip_rate": 0.02, "free_reads_per_ch": 8000},
            "qidian": {"cpm": 5.0, "vip_rate": 0.05, "free_reads_per_ch": 3000},
        }
        params = platform_params.get(platform, platform_params["qimao"])

        total_revenues = []
        for _ in range(n):
            # 初始读者
            readers = int(random.gauss(10000, 2000))
            readers = max(100, readers)

            total_rev = 0.0
            for ch in range(self.chapter_count):
                quality = chapter_qualities[ch]
                # 免费读者
                free_reads = readers * params["free_reads_per_ch"] * (0.8 + 0.2 * quality)
                ad_rev = free_reads / 1000 * params["cpm"] * random.gauss(1.0, 0.15)

                # VIP读者
                vip_readers = int(readers * params["vip_rate"] * quality)
                vip_rev = vip_readers * 0.3  # 每章约0.3元

                total_rev += ad_rev + vip_rev

                # 读者流失
                retention = self.base_retention * (0.7 + 0.3 * quality)
                readers = int(readers * retention)

            total_revenues.append(total_rev)

        total_revenues.sort()
        return {
            "revenue_p50": total_revenues[n // 2],
            "revenue_p10": total_revenues[n // 10],
            "revenue_p90": total_revenues[9 * n // 10],
            "platform": platform,
        }

    def simulate_plot_branch(self, branches: List[Dict],
                               n: int = 100) -> Dict[str, Any]:
        """
        模拟情节分支选择。

        Args:
            branches: [{"name": "分支A", "quality": 0.7, "risk": 0.3, "readers": 5000}, ...]
            n: 模拟次数

        Returns: 每个分支的胜出概率和期望读者数
        """
        results = {}
        for branch in branches:
            outcomes = []
            for _ in range(n):
                # 质量 + 随机波动
                realized_quality = max(0.0, min(1.0,
                    random.gauss(branch["quality"], 0.1)))
                # 风险: 一定概率质量大幅下降
                if random.random() < branch.get("risk", 0.2):
                    realized_quality *= random.uniform(0.3, 0.7)
                # 读者数
                readers = branch.get("readers", 5000) * (0.5 + realized_quality)
                outcomes.append(readers)

            outcomes.sort()
            branch_name = branch["name"]
            results[branch_name] = {
                "expected_readers": sum(outcomes) / n,
                "p50_readers": outcomes[n // 2],
                "p90_readers": outcomes[9 * n // 10],
                "win_probability": sum(1 for o in outcomes
                                        if o == max(outcomes)) / n,
            }
        return results


def monte_carlo_quality(chapter_text: str, n: int = 500) -> Dict[str, float]:
    """
    蒙特卡洛质量稳健性测试。

    对章节文本做N次随机扰动，检测质量是否稳定。
    使用自举法(bootstrap)重采样句子。
    """
    import re
    sentences = [s.strip() for s in re.split(r'[。！？!?\n]', chapter_text)
                 if len(s.strip()) >= 2]

    if len(sentences) < 10:
        return {"robustness": 1.0, "n": 0}

    # 基础统计
    orig_lens = [len(s) for s in sentences]
    orig_mean = sum(orig_lens) / len(orig_lens)

    quality_scores = []
    for _ in range(n):
        # Bootstrap: 重采样
        sample = random.choices(sentences, k=len(sentences))
        sample_lens = [len(s) for s in sample]
        sample_mean = sum(sample_lens) / len(sample_lens)
        sample_std = math.sqrt(sum((l - sample_mean) ** 2 for l in sample_lens)
                                / len(sample_lens))
        cv = sample_std / sample_mean if sample_mean > 0 else 0.0

        # 质量分 = 接近原始均值 + CV合理
        mean_score = 1.0 - min(1.0, abs(sample_mean - orig_mean) / orig_mean)
        cv_score = 1.0 if 0.25 <= cv <= 0.8 else 0.6
        quality_scores.append((mean_score + cv_score) / 2)

    scores_sorted = sorted(quality_scores)
    return {
        "robustness": scores_sorted[n // 2],
        "robustness_p10": scores_sorted[n // 10],
        "robustness_p90": scores_sorted[9 * n // 10],
        "stable": scores_sorted[n // 10] > 0.6,
    }
