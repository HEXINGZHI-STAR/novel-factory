#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI — 贝叶斯统计引擎 (Bayesian Engine)
=============================================
方向1: 贝叶斯收缩 (James-Stein)  — 把单章评分向全局均值收缩，压制噪声
方向2: Bootstrap 置信区间         — 给每个评分加 [低, 高] 区间，替代"一个标量分"

纯 Python 实现，零依赖。
用法:
    from bayesian_engine import BayesianAnalyzer
    analyzer = BayesianAnalyzer()

    # --- 单章: 给评分加置信区间 ---
    sub_scores = [65.0, 72.0, 58.0, 61.0, 68.0]  # 5个子评分（顺序随意）
    weights    = [0.20, 0.20, 0.20, 0.20, 0.20]
    ci = analyzer.bootstrap_chapter(sub_scores, weights)
    # -> {"raw_score": 64.8, "ci_low": 60.2, "ci_high": 69.1, "std_err": 2.3,
    #     "shrunken_score": 64.8, "confidence": "中"}

    # --- 多章: James-Stein 收缩 + 逐章 CI ---
    # chapters = [{"sub_scores": [...], "weights": [...]}, ...]
    report = analyzer.analyze_chapters(chapters)
    # -> {"global_mean": 61.2, "before": [64.8, ...], "after": [62.3, ...],
    #     "shrinkage_factor": 0.18, "chapter_cis": [...], "recommendations": [...]}
"""

import math
import random
from typing import List, Dict, Optional, Tuple


# ============================================================
# 1. Bootstrap 置信区间
# ============================================================
class BootstrapCI:
    """
    非参数 Bootstrap：对一组"子评分 + 权重"做有放回重采样，
    得到"综合评分"的经验分布，从而输出 95% 置信区间。

    直觉:  你一章有5个维度的分。如果5个分都在 60-65 之间，说明评分稳定；
          如果某维度 30 分、另一维度 90 分，说明"评分有争议"，CI 会更宽。
    """

    DEFAULT_N_RESAMPLES = 1000
    DEFAULT_CONFIDENCE = 0.95  # 95%

    @classmethod
    def ci(cls, sub_scores: List[float], weights: Optional[List[float]] = None,
           n_resamples: int = DEFAULT_N_RESAMPLES,
           confidence: float = DEFAULT_CONFIDENCE) -> Dict:
        """
        对一组子评分做 Bootstrap。

        参数:
            sub_scores: 子评分列表（例如 5 个维度的分）
            weights:    可选，子评分的权重；不给则用均匀权重
            n_resamples: 重采样次数（默认 1000，够稳了）
            confidence: 置信水平（默认 0.95）

        返回:
            {"raw_score": 原始加权均值,
             "ci_low":    区间下限,
             "ci_high":   区间上限,
             "std_err":   标准误,
             "median":    Bootstrap 分布中位数,
             "width":     区间宽度 (ci_high - ci_low),
             "confidence_label": "低/中/高",
             "distribution": [分1, 分2, ...]  # (可选, 用于画图)}
        """
        n = len(sub_scores)
        if n == 0:
            return {"raw_score": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                    "std_err": 0.0, "median": 0.0, "width": 0.0, "confidence_label": "未知"}

        # 权重归一化
        if weights is None:
            weights = [1.0 / n] * n
        wsum = sum(weights)
        weights = [w / wsum for w in weights]

        # 原始加权均值
        raw = sum(s * w for s, w in zip(sub_scores, weights))

        if n == 1:
            # 只有一个子分 → 无法重采样，返回退化区间 (+/- 0)
            return {"raw_score": round(raw, 1),
                    "ci_low": round(raw, 1), "ci_high": round(raw, 1),
                    "std_err": 0.0, "median": round(raw, 1), "width": 0.0,
                    "confidence_label": "高"}

        # Bootstrap 主循环: 有放回地抽取 n 个子评分，算加权均值
        rng = random.Random(42)  # 固定种子，结果可复现
        means = []
        for _ in range(n_resamples):
            indices = [rng.randint(0, n - 1) for _ in range(n)]
            resampled_scores = [sub_scores[i] for i in indices]
            resampled_weights = [weights[i] for i in indices]
            ws = sum(resampled_weights)
            m = sum(s * w for s, w in zip(resampled_scores, resampled_weights)) / ws
            means.append(m)

        means.sort()

        # 计算置信区间
        alpha = 1 - confidence
        lo_idx = int(len(means) * alpha / 2)
        hi_idx = int(len(means) * (1 - alpha / 2)) - 1
        lo_idx = max(0, min(lo_idx, len(means) - 1))
        hi_idx = max(0, min(hi_idx, len(means) - 1))

        ci_low = means[lo_idx]
        ci_high = means[hi_idx]
        median = means[len(means) // 2]

        # 标准误 = Bootstrap 分布的标准差
        m_mean = sum(means) / len(means)
        std_err = math.sqrt(sum((m - m_mean) ** 2 for m in means) / len(means))
        width = ci_high - ci_low

        # "置信度"标签: 区间越窄越自信
        if width <= 5:
            label = "高"
        elif width <= 12:
            label = "中"
        else:
            label = "低"

        return {
            "raw_score": round(raw, 1),
            "ci_low": round(ci_low, 1),
            "ci_high": round(ci_high, 1),
            "std_err": round(std_err, 2),
            "median": round(median, 1),
            "width": round(width, 1),
            "confidence_label": label,
        }


# ============================================================
# 2. James-Stein 收缩估计器
# ============================================================
class JamesSteinShrinker:
    """
    James-Stein 收缩估计器。

    直觉:
        给定 K 个"有噪声的观测值" Y_1, Y_2, ..., Y_K （例如 K 章评分）
        经典统计告诉你 Y_i 是对 θ_i 的最好估计，但其实——
        z_i = Ȳ + (1 - c) * (Y_i - Ȳ)
        在平方误差损失下，*一致地* 比原始 Y_i 更好（当 K >= 4 时）。

        c = (K-3) * sigma_sq / sum((Y_j - global_mean)**2 for Y_j in scores)
        c 越大 → 收缩越狠；当 c > 1 时截断为 1（完全收缩到均值）

    关键性质:
        - 不改变全局均值 (sum(z_i) = sum(Y_i))
        - 对"离群值"收缩最大，对"接近均值"的值几乎不变
        - 当 K 很小时 (K < 4)，退化为原始值（避免过度收缩）
    """

    @classmethod
    def shrink(cls, scores: List[float],
               sigma2: Optional[float] = None,
               min_chapters: int = 4) -> Dict:
        """
        对一组评分做 James-Stein 收缩。

        参数:
            scores:       各章的评分 (最好已经是各自章节的"相对稳定"的均值)
            sigma2:       评分的"内在噪声方差"；不传则用样本方差的保守估计
            min_chapters: 至少多少章才启用收缩；少于这个数返回原始值

        返回:
            {"before": [原始评分],
             "after":  [收缩后评分],
             "shrinkage_factor": c,  # ∈ [0, 1]，0=不收缩，1=完全收缩到均值
             "global_mean": 全局均值,
             "max_shrinkage_pts": 单章最大收缩幅度,
             "note": 解释性文字}
        """
        K = len(scores)
        global_mean = sum(scores) / K if K > 0 else 0.0

        if K < min_chapters:
            return {
                "before": scores[:],
                "after": scores[:],
                "shrinkage_factor": 0.0,
                "global_mean": round(global_mean, 1),
                "max_shrinkage_pts": 0.0,
                "note": f"章节数({K})过少，未启用收缩（需≥{min_chapters}章）",
            }

        # 偏差平方和
        sst = sum((y - global_mean) ** 2 for y in scores)

        if sst < 1e-8:
            # 所有分相同，无需收缩
            return {
                "before": scores[:],
                "after": scores[:],
                "shrinkage_factor": 0.0,
                "global_mean": round(global_mean, 1),
                "max_shrinkage_pts": 0.0,
                "note": "各章评分完全一致，无可收缩空间",
            }

        # 估计 sigma_sq: 不传的话，用"残差方差的上界"
        if sigma2 is None:
            # 用样本方差作为 sigma_sq 的保守估计（略微偏大 → 收缩略狠，更安全）
            sigma2 = sst / (K - 1)

        # 核心公式
        raw_c = (K - 3) * sigma2 / sst
        c = max(0.0, min(1.0, raw_c))  # 截断到 [0, 1]

        after = [global_mean + (1 - c) * (y - global_mean) for y in scores]

        max_shrink = max(abs(a - b) for a, b in zip(after, scores))

        note = (
            f"收缩系数 c={c:.2f}。"
            + ("几乎无收缩，说明各章评分差异真实。" if c < 0.1 else
               "中等收缩，压制了约 " + str(int(c * 100)) + "% 的噪声波动。" if c < 0.5 else
               "强收缩，原始评分中有较多噪声被滤掉。")
        )

        return {
            "before": [round(s, 1) for s in scores],
            "after": [round(s, 1) for s in after],
            "shrinkage_factor": round(c, 3),
            "global_mean": round(global_mean, 1),
            "max_shrinkage_pts": round(max_shrink, 1),
            "note": note,
        }


# ============================================================
# 3. 组合门面: BayesianAnalyzer
# ============================================================
class BayesianAnalyzer:
    """
    对外统一接口。输入章节的子评分，输出：
      - 每章的 "收缩后评分" + "95% CI"
      - 全局的收缩报告
      - 一组人类可读的建议（哪些章的"低分/高分"值得相信，哪些是噪声）
    """

    def __init__(self):
        self.ci = BootstrapCI()
        self.shrinker = JamesSteinShrinker()

    # ---------------------------------------------------------
    # 单章: Bootstrap CI
    # ---------------------------------------------------------
    def bootstrap_chapter(self, sub_scores: List[float],
                          weights: Optional[List[float]] = None) -> Dict:
        """给单章评分加 95% 置信区间。"""
        return self.ci.ci(sub_scores, weights)

    # ---------------------------------------------------------
    # 多章: James-Stein + 逐章 CI
    # ---------------------------------------------------------
    def analyze_chapters(self, chapters: List[Dict]) -> Dict:
        """
        参数:
            chapters: 列表，每项 = {"sub_scores": [..], "weights": [..], "chapter": i,
                                    "raw_score_override": float (可选)}

        返回: 一个大 dict，直接可以 dump 或打印
        """
        n = len(chapters)

        # --- 先做逐章 Bootstrap，拿到 CI ---
        chapter_cis = []
        for ch in chapters:
            sub = ch.get("sub_scores", [])
            w = ch.get("weights", None)
            r = self.ci.ci(sub, w)
            # 支持 raw_score_override
            override = ch.get("raw_score_override")
            if override is not None and isinstance(override, (int, float)):
                old_med = r["median"]
                old_low = r["ci_low"]
                old_high = r["ci_high"]
                r["raw_score"] = round(float(override), 1)
                r["median"] = round(float(override), 1)
                r["ci_low"] = round(float(override) + (old_low - old_med), 1)
                r["ci_high"] = round(float(override) + (old_high - old_med), 1)
            r["chapter"] = ch.get("chapter", len(chapter_cis) + 1)
            chapter_cis.append(r)

        raw_scores = [c["raw_score"] for c in chapter_cis]
        medians = [c["median"] for c in chapter_cis]

        # --- 用 Bootstrap 中位数做 James-Stein 收缩 ---
        # 用中位数比用原始均值更稳（抗极端子分）
        shrink_report = self.shrinker.shrink(medians)

        # --- 组合输出: 给每章组装 "收缩后评分 ± CI" ---
        merged = []
        for i, (ci, shrunken) in enumerate(zip(chapter_cis, shrink_report["after"])):
            # 收缩是对"中位数"的收缩，CI 的宽度不变（只平移区间中心）
            offset = shrunken - ci["median"]
            merged.append({
                "chapter": ci["chapter"],
                "raw_score": ci["raw_score"],
                "shrunken_score": round(shrunken, 1),
                "ci_low": round(ci["ci_low"] + offset, 1),
                "ci_high": round(ci["ci_high"] + offset, 1),
                "ci_width": ci["width"],
                "std_err": ci["std_err"],
                "confidence_label": ci["confidence_label"],
                "delta_from_raw": round(shrunken - ci["raw_score"], 1),
            })

        # --- 生成人类可读的建议 ---
        recs = self._recommend(merged, shrink_report)

        # --- 整体摘要 ---
        raw_mean = round(sum(raw_scores) / n, 1) if n else 0.0
        shrunken_mean = round(sum(m["shrunken_score"] for m in merged) / n, 1) if n else 0.0
        avg_ci_width = round(sum(m["ci_width"] for m in merged) / n, 1) if n else 0.0

        return {
            "n_chapters": n,
            "global_raw_mean": raw_mean,
            "global_shrunken_mean": shrunken_mean,
            "avg_ci_width": avg_ci_width,
            "shrinkage_factor": shrink_report["shrinkage_factor"],
            "max_shrinkage_pts": shrink_report["max_shrinkage_pts"],
            "note": shrink_report["note"],
            "chapters": merged,
            "recommendations": recs,
        }

    # ---------------------------------------------------------
    # 辅助: 建议生成
    # ---------------------------------------------------------
    @staticmethod
    def _recommend(chapters: List[Dict], shrink_report: Dict) -> List[str]:
        recs = []
        n = len(chapters)
        if n == 0:
            return recs

        mean = shrink_report["global_mean"]

        # 最值得关注的"低分章"（收缩后分 < 均值 - 5 且 CI 确认可靠）
        low_confident = [c for c in chapters
                         if c["shrunken_score"] < mean - 5 and c["ci_width"] <= 12]
        high_noisy = [c for c in chapters if c["ci_width"] > 12]

        if low_confident:
            chs = ", ".join(f"第{c['chapter']}章({c['shrunken_score']})" for c in low_confident)
            recs.append(f"⚠ 确认低分章: {chs} — 评分显著低于均值且CI窄，是真正的薄弱环节，优先改写")
        if high_noisy:
            chs = ", ".join(f"第{c['chapter']}章(CI宽{c['ci_width']})" for c in high_noisy)
            recs.append(f"· 高噪声章: {chs} — 子维度评分分歧大（有的很好有的很差），建议拆开维度单独评估")

        if shrink_report["shrinkage_factor"] > 0.3 and shrink_report["max_shrinkage_pts"] > 2:
            recs.append(f"· 本次收缩幅度最大 {shrink_report['max_shrinkage_pts']} 分 — "
                        f"说明原始报告中某些极端分数有较大概率是噪声，收缩后更可信")

        if shrink_report["shrinkage_factor"] < 0.1:
            recs.append("· 收缩系数极小 — 各章差异基本是真实的，不用怀疑评分")

        if not recs:
            recs.append("· 各章评分稳定，结构良好，无特殊调整建议")

        return recs


# ============================================================
# 3b. 经验贝叶斯自适应收缩 —— "每章按自身噪声水平独立收缩"
# ============================================================
class EmpiricalBayesAnalyzer:
    """
    James-Stein 的升级版: 全局收缩是对"所有章"用同一系数，而经验贝叶斯
    对"每章"分别估计其收缩强度 = f(该章自身的 Bootstrap 标准差, 各章之间的真实变异).

    形式:
        后验均值(章i) = global_mean + B_i * (median_i - global_mean)
        B_i           = tau_sq / (tau_sq + sigma_i_sq)
        tau_sq = 各章之间的"真实变异" (由数据反解, Robust)
        sigma_i_sq = 章 i 的 Bootstrap 方差 = (SE_i)^2

    直觉:
        - 噪声章 (sigma_i 大): B_i 小 → 更多被拉回均值
        - 信号章 (sigma_i 小): B_i 大 → 几乎保持原分
    这比固定的 James-Stein 更"智能"，也解决了"某章评分极度分裂导致收缩过度"的问题。
    """

    def __init__(self):
        self.ci = BootstrapCI()

    def analyze_chapters(self, chapters: List[Dict]) -> Dict:
        n = len(chapters)
        if n == 0:
            return {"n_chapters": 0, "chapters": [], "recommendations": []}

        # 1. 逐章 Bootstrap → 拿到 (median, sigma_i)
        chapter_data = []
        for ch in chapters:
            sub = ch.get("sub_scores", [])
            w = ch.get("weights", None)
            r = self.ci.ci(sub, w)
            # 支持 raw_score_override: 用外部提供的综合评分覆盖 bootstrap 均值，
            # 但保留 bootstrap 的 CI 宽度和 std_err 用于测量噪声
            override = ch.get("raw_score_override")
            if override is not None and isinstance(override, (int, float)):
                old_median = r["median"]
                old_raw = r["raw_score"]
                old_low = r["ci_low"]
                old_high = r["ci_high"]
                # 以 override 为新中心，保持原 CI 宽度不变
                r["raw_score"] = round(float(override), 1)
                r["median"] = round(float(override), 1)
                r["ci_low"] = round(float(override) + (old_low - old_median), 1)
                r["ci_high"] = round(float(override) + (old_high - old_median), 1)
                r["score_source"] = "override"
            else:
                r["score_source"] = "bootstrap"
            r["chapter"] = ch.get("chapter", len(chapter_data) + 1)
            chapter_data.append(r)

        medians = [c["median"] for c in chapter_data]
        std_errs = [c["std_err"] for c in chapter_data]
        raw_scores = [c["raw_score"] for c in chapter_data]

        # 2. 估计 tau_sq —— 各章之间的"真实变异"
        # tau_sq = max(0, var(medians) - mean(sigma_i_sq))  (Moment estimator)
        var_obs = sum((m - sum(medians) / n) ** 2 for m in medians) / max(n - 1, 1)
        mean_noise = sum(se ** 2 for se in std_errs) / n
        tau_sq = max(0.0, var_obs - mean_noise)

        # 3. 对每章计算 B_i = tau_sq / (tau_sq + sigma_i_sq), 得到 EB 收缩分
        global_mean = sum(medians) / n
        shrunken_scores = []
        merged = []
        for i, cd in enumerate(chapter_data):
            sigma_sq = std_errs[i] ** 2
            denom = tau_sq + sigma_sq
            if denom > 0:
                b_i = tau_sq / denom  # 保留原始信号的比例
            else:
                b_i = 1.0
            shrunken = global_mean + b_i * (medians[i] - global_mean)
            offset = shrunken - medians[i]
            shrunken_scores.append(shrunken)
            merged.append({
                "chapter": cd["chapter"],
                "raw_score": cd["raw_score"],
                "bootstrap_median": round(medians[i], 2),
                "bootstrap_std_err": round(std_errs[i], 3),
                "shrinkage_factor": round(1 - b_i, 4),  # 1 - B_i = 被拉回均值的比例
                "shrunken_score": round(shrunken, 1),
                "ci_low": round(cd["ci_low"] + offset, 1),
                "ci_high": round(cd["ci_high"] + offset, 1),
                "ci_width": cd["width"],
                "confidence_label": cd["confidence_label"],
                "delta_from_raw": round(shrunken - cd["raw_score"], 1),
            })

        # 4. 诊断: 哪些章被大幅收缩了?
        heavy_shrink = [m for m in merged if m["shrinkage_factor"] > 0.5]
        low_shrink = [m for m in merged if m["shrinkage_factor"] < 0.2]

        # 5. 生成建议
        recs = []
        if heavy_shrink:
            chs = ", ".join(
                f"第{m['chapter']}章(被收缩{m['delta_from_raw']:+})"
                for m in heavy_shrink
            )
            recs.append(
                f"[EB 大幅收缩] {chs} — 这些章的子维度评分方差较大 (sigma_sq 远大于章间真实变异 tau_sq), "
                f"经验贝叶斯把它们更多拉回均值, 其原始极端分有较大概率是噪声"
            )

        if low_shrink:
            chs = ", ".join(
                f"第{m['chapter']}章({m['shrunken_score']})" for m in low_shrink
            )
            recs.append(
                f"[EB 保留] {chs} — 这些章内部方差小且偏离均值显著, 收缩因子<0.2, "
                f"评分基本是真实信号, 可信"
            )

        # 与 James-Stein 的对比: 简单 JS 收缩报告
        js_report = JamesSteinShrinker.shrink(medians)
        js_scores = js_report["after"]
        diff_from_js = [round(merged[i]["shrunken_score"] - js_scores[i], 2)
                        for i in range(n)]

        raw_mean = round(sum(raw_scores) / n, 1)
        eb_mean = round(sum(m["shrunken_score"] for m in merged) / n, 1)
        avg_ci_width = round(sum(m["ci_width"] for m in merged) / n, 1)

        return {
            "n_chapters": n,
            "method": "empirical_bayes_adaptive",
            "tau_sq_chapter_variation": round(tau_sq, 3),
            "mean_noise_variance": round(mean_noise, 3),
            "signal_to_noise_ratio": round(tau_sq / max(mean_noise, 1e-6), 3),
            "global_mean": round(global_mean, 2),
            "global_raw_mean": raw_mean,
            "global_eb_mean": eb_mean,
            "avg_ci_width": avg_ci_width,
            "n_heavy_shrink": len(heavy_shrink),
            "n_low_shrink": len(low_shrink),
            "chapters": merged,
            "recommendations": recs,
            "vs_james_stein_diffs": diff_from_js,
        }


# ============================================================
# 4. 简易: 直接从 pangu_math_core 的 full_analysis 结果提取子评分
# ============================================================
def extract_sub_scores_from_analysis(result: Dict) -> Dict:
    """
    从 pangu_math_core.MathEngine.full_analysis() 的输出中，
    抽取 5 个维度的子评分 + 默认权重。

    返回: {"sub_scores": [..], "weights": [..]}
    """
    sub = []
    labels = []

    # 1. 傅里叶节律分
    fr = result.get("fourier_analysis", {})
    if isinstance(fr, dict):
        spec = fr.get("emotion_spectrum", {}) if isinstance(fr, dict) else {}
        if isinstance(spec, dict):
            rs = spec.get("rhythm_score")
            if isinstance(rs, (int, float)):
                sub.append(float(rs))
                labels.append("傅里叶节律")

    # 2. 钩子健康分
    lp = result.get("laplace_analysis", {})
    if isinstance(lp, dict):
        hs = lp.get("hook_health_score")
        if isinstance(hs, (int, float)):
            sub.append(float(hs))
            labels.append("钩子")

    # 3. 情绪弧质量分
    it = result.get("integral_analysis", {})
    if isinstance(it, dict):
        aq = it.get("arc_quality_score")
        if isinstance(aq, (int, float)):
            sub.append(float(aq))
            labels.append("情绪弧")

    # 4. 马尔可夫健康分
    mc = result.get("markov_chain", {})
    if isinstance(mc, dict):
        mh = mc.get("health_score")
        if isinstance(mh, (int, float)):
            sub.append(float(mh))
            labels.append("叙事链")

    # 5. 信息论词汇丰富度
    inf = result.get("information_metrics", {})
    if isinstance(inf, dict):
        vr = inf.get("vocab_richness")
        if isinstance(vr, (int, float)):
            sub.append(float(vr) * 100.0 if vr <= 1.0 else float(vr))
            labels.append("词汇")

    # 没拿到足够的子分？退化：返回总分作为单子分
    if len(sub) < 2:
        overall = result.get("overall_math_score", 50)
        return {"sub_scores": [float(overall)], "weights": [1.0], "labels": ["综合"]}

    # 目前 5 个维度权重相等
    weights = [1.0 / len(sub)] * len(sub)
    return {"sub_scores": sub, "weights": weights, "labels": labels}


if __name__ == "__main__":
    # 自测: 模拟 8 章的子评分
    print("=" * 60)
    print("  Bayesian 引擎自测")
    print("=" * 60)
    analyzer = BayesianAnalyzer()

    # 模拟: 5 个子分 per chapter
    chapters = []
    mock_data = [
        ([65, 72, 58, 61, 68], "第1章"),
        ([62, 60, 70, 65, 63], "第2章"),
        ([45, 55, 50, 60, 48], "第3章"),   # 真·低分
        ([66, 68, 64, 70, 67], "第4章"),
        ([92, 40, 55, 50, 90], "第5章"),   # 高分 + 极度分歧（噪声）
        ([64, 66, 62, 68, 65], "第6章"),
        ([70, 72, 68, 74, 71], "第7章"),
        ([60, 58, 62, 55, 59], "第8章"),
    ]
    for i, (sub, name) in enumerate(mock_data, 1):
        chapters.append({"sub_scores": sub, "weights": [0.2]*5, "chapter": i})

    report = analyzer.analyze_chapters(chapters)

    print(f"\n  章节数: {report['n_chapters']}")
    print(f"  原始均分: {report['global_raw_mean']}  →  收缩均分: {report['global_shrunken_mean']}")
    print(f"  平均 CI 宽度: {report['avg_ci_width']} 分")
    print(f"  收缩系数: {report['shrinkage_factor']}  (最大单章收缩 {report['max_shrinkage_pts']} 分)")
    print(f"  {report['note']}")

    print(f"\n  {'章':>4}  {'原始':>6}  {'收缩':>7}  {'Δ':>5}  {'95% CI':>13}  {'宽度':>5}  {'置信':>4}")
    print("  " + "-" * 60)
    for c in report["chapters"]:
        print(f"  第{c['chapter']:>2}章  {c['raw_score']:>6.1f}  "
              f"{c['shrunken_score']:>7.1f}  {c['delta_from_raw']:+5.1f}  "
              f"[{c['ci_low']:>5.1f}, {c['ci_high']:>5.1f}]  {c['ci_width']:>5.1f}  {c['confidence_label']:>4}")

    print(f"\n  建议:")
    for r in report["recommendations"]:
        print(f"  {r}")
