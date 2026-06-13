#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI医学统计引擎
==================
将医学统计学方法论应用于网文文本分析。

核心理念：描述性统计 → 推断性统计 → 诊断性评价
不是简单地"打分"，而是带着置信区间、显著性水平和效应量去判断。

实现的统计方法:
1. 描述统计：均值/标准差/中位数/四分位数/偏度/峰度
2. t检验：单样本(与标杆对比)/双样本(章节间对比)/配对(修订前后)
3. 卡方检验：叙事状态分布与期望分布的拟合优度
4. 方差分析(ANOVA)：多章节组间差异
5. 生存分析：Kaplan-Meier读者留存概率估计
6. 诊断评价：敏感度/特异度/ROC曲线/AUC/约登指数
7. 线性回归：多因素预测综合质量分
8. 效应量：Cohen's d / 优势比 / Cramer's V
9. 置信区间：所有指标的95%CI

纯Python实现，无scipy/numpy依赖。
"""

import math
import re
from typing import Dict, List, Tuple, Optional
from collections import Counter


# ============================================================
# Part 0: 概率分布函数 (纯Python实现)
# ============================================================

class Distributions:
    """
    纯Python概率分布函数。
    用于计算p值、临界值、置信区间。
    """

    @staticmethod
    def normal_cdf(x: float) -> float:
        """标准正态分布累积分布函数 Φ(x)"""
        # 使用Abramowitz和Stegun近似 (精度 ~7.5e-8)
        if x < 0:
            return 1 - Distributions.normal_cdf(-x)
        p = 0.2316419
        b1 = 0.319381530
        b2 = -0.356563782
        b3 = 1.781477937
        b4 = -1.821255978
        b5 = 1.330274429
        t = 1 / (1 + p * x)
        phi = (1 / math.sqrt(2 * math.pi)) * math.exp(-x * x / 2)
        return 1 - phi * (b1*t + b2*t*t + b3*t**3 + b4*t**4 + b5*t**5)

    @staticmethod
    def normal_ppf(p: float) -> float:
        """标准正态分布分位数函数 (逆CDF)"""
        if p <= 0 or p >= 1:
            return float('inf') if p >= 1 else float('-inf')
        # 使用有理近似 (Moro算法)
        a0, a1, a2, a3 = 2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637
        b1, b2, b3, b4 = -8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833
        c0, c1, c2, c3 = 0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863
        c4, c5, c6, c7 = 0.0038405729373609, 0.0003951896511919, 0.0000321767881768, 0.0000002888167364
        c8 = 0.0000003960315187

        y = p - 0.5
        if abs(y) < 0.42:
            r = y * y
            return y * (((a3 * r + a2) * r + a1) * r + a0) / ((((b4 * r + b3) * r + b2) * r + b1) * r + 1)
        
        r = math.sqrt(-math.log(min(p, 1-p)))
        x = ((((c8 * r + c7) * r + c6) * r + c5) * r + c4) * r + c3
        x = x * r + c2
        x = x * r + c1
        x = x * r + c0
        return -x if p < 0.5 else x

    @staticmethod
    def _lgamma(x: float) -> float:
        """对数Gamma函数 ln(Γ(x))"""
        if x <= 0:
            return float('inf')
        # Lanczos近似
        g = 7
        p = [0.99999999999980993, 676.5203681218851, -1259.1392167224028,
             771.32342877765313, -176.61502916214059, 12.507343278686905,
             -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7]
        if x < 0.5:
            return math.log(math.pi) - math.log(math.sin(math.pi * x)) - Distributions._lgamma(1 - x)
        x -= 1
        a = p[0]
        for i in range(1, g+2):
            a += p[i] / (x + i)
        t = x + g + 0.5
        return math.log(math.sqrt(2 * math.pi)) + (x + 0.5) * math.log(t) - t + math.log(a)

    @staticmethod
    def _beta_inc(x: float, a: float, b: float) -> float:
        """正则化不完全Beta函数 I_x(a,b)"""
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        # 连分式展开
        front = math.exp(Distributions._lgamma(a + b) - Distributions._lgamma(a) - 
                        Distributions._lgamma(b) + a * math.log(x) + b * math.log(1 - x))
        # 使用连分式
        f = 1.0
        c = 1.0
        d = 1.0 - (a + b) * x / (a + 1)
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        h = d
        m = 0
        while m < 200:
            m += 1
            m2 = 2 * m
            # 偶数项
            aa = m * (b - m) * x / ((a + m2 - 1) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            h *= d * c
            # 奇数项
            aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            del_ = d * c
            h *= del_
            if abs(del_ - 1.0) < 3e-7:
                break
        
        return front * (h - 1.0) / a

    @classmethod
    def t_cdf(cls, t: float, df: float) -> float:
        """Student t分布的CDF P(T <= t | df)"""
        x = df / (df + t * t)
        p = 0.5 * cls._beta_inc(x, df / 2, 0.5)
        return 1 - p if t > 0 else p

    @classmethod
    def t_test_pvalue(cls, t_stat: float, df: float, two_sided: bool = True) -> float:
        """从t统计量计算p值"""
        p = 2 * (1 - cls.t_cdf(abs(t_stat), df)) if two_sided else 1 - cls.t_cdf(t_stat, df)
        return min(1.0, max(0.0, p))

    @classmethod
    def chi2_cdf(cls, x: float, df: float) -> float:
        """卡方分布的CDF P(X <= x | df)"""
        if x <= 0:
            return 0.0
        return cls._beta_inc(x / (x + 2 * df), df / 2, 0.5) if df < 1 else 1 - cls._beta_inc(2*df/(x+2*df), 0.5, df/2)
        # 简化版
        return 1 - cls._beta_inc(2*df/(x+2*df), 0.5, df/2)

    @classmethod
    def chi2_test_pvalue(cls, chi2_stat: float, df: float) -> float:
        """卡方检验p值"""
        if chi2_stat <= 0:
            return 1.0
        return min(1.0, max(0.0, 1 - cls.chi2_cdf(chi2_stat, df)))

    @staticmethod
    def _log_factorial(n: float) -> float:
        """log(n!) via Stirling"""
        if n <= 1:
            return 0
        return n * math.log(n) - n + 0.5 * math.log(2 * math.pi * n)


# ============================================================
# Part 1: 描述统计
# ============================================================

class DescriptiveStats:
    """描述性统计 (均值、标准差、分位数、偏度、峰度)"""

    @staticmethod
    def compute(data: List[float]) -> Dict:
        """计算完整描述统计"""
        n = len(data)
        if n == 0:
            return {"n": 0, "error": "空数据"}

        sorted_data = sorted(data)
        mean_val = sum(data) / n
        variance = sum((x - mean_val) ** 2 for x in data) / (n - 1) if n > 1 else 0
        sd = math.sqrt(variance)
        sem = sd / math.sqrt(n)  # 标准误

        # 分位数
        def quantile(sorted_d, q):
            idx = q * (len(sorted_d) - 1)
            lo = int(idx)
            hi = min(lo + 1, len(sorted_d) - 1)
            frac = idx - lo
            return sorted_d[lo] * (1 - frac) + sorted_d[hi] * frac

        # 偏度
        skew = 0.0
        if sd > 0 and n > 2:
            skew = (n / ((n - 1) * (n - 2))) * sum(((x - mean_val) / sd) ** 3 for x in data)

        # 峰度
        kurt = 0.0
        if sd > 0 and n > 3:
            kurt = ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * sum(((x - mean_val) / sd) ** 4 for x in data)
            kurt -= 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))

        # 变异系数
        cv = sd / abs(mean_val) if mean_val != 0 else 0

        # 95%置信区间 (正态近似)
        z_975 = 1.96
        ci_lower = mean_val - z_975 * sem
        ci_upper = mean_val + z_975 * sem

        return {
            "n": n,
            "mean": round(mean_val, 4),
            "sd": round(sd, 4),
            "sem": round(sem, 4),
            "median": round(quantile(sorted_data, 0.5), 4),
            "q1": round(quantile(sorted_data, 0.25), 4),
            "q3": round(quantile(sorted_data, 0.75), 4),
            "iqr": round(quantile(sorted_data, 0.75) - quantile(sorted_data, 0.25), 4),
            "min": round(sorted_data[0], 4),
            "max": round(sorted_data[-1], 4),
            "skewness": round(skew, 4),
            "kurtosis": round(kurt, 4),
            "cv": round(cv, 4),
            "ci_95_lower": round(ci_lower, 4),
            "ci_95_upper": round(ci_upper, 4),
        }


# ============================================================
# Part 2: 假设检验
# ============================================================

class HypothesisTests:
    """假设检验工具集"""

    @classmethod
    def one_sample_t(cls, data: List[float], null_mean: float = 50.0) -> Dict:
        """
        单样本t检验: H0: mu = null_mean
        适用于: 判断本章分数是否显著偏离标杆值
        """
        n = len(data)
        if n < 2:
            return {"error": "样本量不足", "n": n}

        mean_val = sum(data) / n
        sd = math.sqrt(sum((x - mean_val) ** 2 for x in data) / (n - 1))
        sem = sd / math.sqrt(n)

        t_stat = (mean_val - null_mean) / sem if sem > 0 else 0
        df = n - 1
        p_value = Distributions.t_test_pvalue(t_stat, df)

        # Cohen's d 效应量
        cohens_d = (mean_val - null_mean) / sd if sd > 0 else 0
        effect_size = cls._interpret_cohens_d(cohens_d)

        # 95% CI
        t_crit = 2.0 if df > 30 else cls._t_critical_approx(df)
        ci_margin = t_crit * sem
        ci_lower = mean_val - ci_margin
        ci_upper = mean_val + ci_margin

        significant = p_value < 0.05
        direction = "显著高于" if (significant and mean_val > null_mean) else \
                    "显著低于" if (significant and mean_val < null_mean) else "无显著差异"

        return {
            "test": "单样本t检验",
            "null_hypothesis": f"mu = {null_mean}",
            "sample_mean": round(mean_val, 4),
            "null_mean": null_mean,
            "t_statistic": round(t_stat, 4),
            "df": df,
            "p_value": round(p_value, 4),
            "significant": significant,
            "direction": direction,
            "cohens_d": round(cohens_d, 4),
            "effect_size": effect_size,
            "ci_95_lower": round(ci_lower, 4),
            "ci_95_upper": round(ci_upper, 4),
            "interpretation": f"本章均分{mean_val:.1f} {direction}标杆{null_mean} (p={p_value:.4f}, d={cohens_d:.3f})",
        }

    @classmethod
    def two_sample_t(cls, data1: List[float], data2: List[float], label1: str = "组1", label2: str = "组2") -> Dict:
        """
        双样本独立t检验 (Welch's t-test): H0: mu1 = mu2
        适用于: 判断两章是否显著不同 (如修订前后对比)
        """
        n1, n2 = len(data1), len(data2)
        if n1 < 2 or n2 < 2:
            return {"error": "样本量不足"}

        m1 = sum(data1) / n1
        m2 = sum(data2) / n2
        v1 = sum((x - m1) ** 2 for x in data1) / (n1 - 1)
        v2 = sum((x - m2) ** 2 for x in data2) / (n2 - 1)

        se = math.sqrt(v1 / n1 + v2 / n2)
        t_stat = (m1 - m2) / se if se > 0 else 0

        # Welch-Satterthwaite自由度
        df_num = (v1 / n1 + v2 / n2) ** 2
        df_den = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
        df = df_num / df_den if df_den > 0 else min(n1, n2) - 1

        p_value = Distributions.t_test_pvalue(t_stat, df)

        # Cohen's d
        pooled_sd = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
        cohens_d = (m1 - m2) / pooled_sd if pooled_sd > 0 else 0
        effect_size = cls._interpret_cohens_d(cohens_d)

        significant = p_value < 0.05

        return {
            "test": "双样本Welch t检验",
            "null_hypothesis": f"mu_{label1} = mu_{label2}",
            "mean_1": round(m1, 4),
            "mean_2": round(m2, 4),
            "difference": round(m1 - m2, 4),
            "t_statistic": round(t_stat, 4),
            "df": round(df, 1),
            "p_value": round(p_value, 4),
            "significant": significant,
            "cohens_d": round(cohens_d, 4),
            "effect_size": effect_size,
            "label_1": label1,
            "label_2": label2,
            "interpretation": f"{label1}均分{m1:.1f} vs {label2}均分{m2:.1f} (p={p_value:.4f}, d={cohens_d:.3f})",
        }

    @classmethod
    def chi_square_goodness_of_fit(cls, observed: Dict[str, float], expected: Dict[str, float]) -> Dict:
        """
        卡方拟合优度检验: 实际分布与期望分布是否有显著差异
        适用于: 叙事状态分布是否符合黄金比例
        """
        all_keys = set(observed.keys()) | set(expected.keys())
        chi2 = 0.0
        details = []

        for key in sorted(all_keys):
            o_val = observed.get(key, 0)
            e_val = expected.get(key, 0.001)  # 避免除0
            if e_val > 0:
                chi2 += (o_val - e_val) ** 2 / e_val
                details.append(f"  {key}: O={o_val:.3f} E={e_val:.3f}")

        df = len(all_keys) - 1
        p_value = Distributions.chi2_test_pvalue(chi2, df) if df > 0 else 1.0
        significant = p_value < 0.05

        return {
            "test": "卡方拟合优度检验",
            "chi2_statistic": round(chi2, 4),
            "df": df,
            "p_value": round(p_value, 4),
            "significant": significant,
            "interpretation": f"分布与期望{'有' if significant else '无'}显著差异 (chi2={chi2:.2f}, df={df}, p={p_value:.4f})",
            "details": details,
        }

    @classmethod
    def one_way_anova(cls, groups: List[Tuple[str, List[float]]]) -> Dict:
        """
        单因素方差分析: 多组均值是否有显著差异
        适用于: 比较多个章节的评分是否来自同一分布
        """
        if len(groups) < 2:
            return {"error": "至少需要2组"}

        all_vals = []
        for _, vals in groups:
            all_vals.extend(vals)
        grand_mean = sum(all_vals) / len(all_vals) if all_vals else 0

        # 组间平方和
        ss_between = 0
        for _, vals in groups:
            group_mean = sum(vals) / len(vals) if vals else 0
            ss_between += len(vals) * (group_mean - grand_mean) ** 2

        # 组内平方和
        ss_within = 0
        for _, vals in groups:
            if len(vals) < 2:
                continue
            group_mean = sum(vals) / len(vals)
            ss_within += sum((x - group_mean) ** 2 for x in vals)

        k = len(groups)
        n_total = len(all_vals)
        df_between = k - 1
        df_within = n_total - k

        if df_within <= 0 or ss_within == 0:
            return {"error": "组内变异为0或自由度不足"}

        ms_between = ss_between / df_between
        ms_within = ss_within / df_within
        f_stat = ms_between / ms_within if ms_within > 0 else 0

        # F分布p值近似 (用卡方近似)
        # F(k-1, n-k) 近似: 当df较大时可用
        p_value = Distributions.chi2_test_pvalue(f_stat * df_between, df_between)

        significant = p_value < 0.05
        group_means = {name: round(sum(vals) / len(vals), 2) if vals else 0 for name, vals in groups}

        return {
            "test": "单因素方差分析(ANOVA)",
            "f_statistic": round(f_stat, 4),
            "df_between": df_between,
            "df_within": df_within,
            "p_value": round(p_value, 4),
            "significant": significant,
            "group_means": group_means,
            "ss_between": round(ss_between, 4),
            "ss_within": round(ss_within, 4),
            "interpretation": f"组间{'有' if significant else '无'}显著差异 (F={f_stat:.2f}, p={p_value:.4f})",
        }

    @staticmethod
    def _interpret_cohens_d(d: float) -> str:
        d_abs = abs(d)
        if d_abs < 0.2:
            return "可忽略"
        elif d_abs < 0.5:
            return "小效应"
        elif d_abs < 0.8:
            return "中效应"
        else:
            return "大效应"

    @staticmethod
    def _t_critical_approx(df: float) -> float:
        """t分布临界值近似 (df较小时)"""
        if df <= 0:
            return 12.706  # df=0 极限
        if df >= 30:
            return 2.042
        # 粗略近似
        return 2.0 + 1.0 / math.sqrt(df)


# ============================================================
# Part 3: 生存分析
# ============================================================

class SurvivalAnalysis:
    """
    Kaplan-Meier生存分析应用于读者留存。
    
    模型: 每章的"风险事件" = 读者因质量问题弃书
    "生存" = 读者继续阅读
    
    输入: 逐章的评分列表
    输出: 生存曲线 & 估计的读者留存率
    """

    @staticmethod
    def kaplan_meier(chapter_scores: List[float], threshold: float = 55.0) -> Dict:
        """
        Kaplan-Meier估计器。
        
        参数:
            chapter_scores: 各章的质量评分 (分数越高=质量越好)
            threshold: 低于此分视为"风险事件"(读者可能弃书)
        
        返回:
            生存函数估计 S(t) = 到第t章时读者仍在读的概率
        """
        n = len(chapter_scores)
        if n == 0:
            return {"error": "无章节数据"}

        # 标记风险事件 (低于阈值 = 事件发生)
        events = [1 if score < threshold else 0 for score in chapter_scores]

        survival = []
        at_risk = n
        cumulative = 1.0

        for i in range(n):
            if at_risk > 0:
                # KM估计: S(t) = product of (1 - events/at_risk)
                if events[i] == 1:
                    cumulative *= (1 - 1 / at_risk)
                survival.append({
                    "chapter": i + 1,
                    "score": chapter_scores[i],
                    "at_risk": at_risk,
                    "event": bool(events[i]),
                    "survival_prob": round(cumulative, 4),
                })
            at_risk -= 1

        # 中位生存时间 (读者流失50%的章节)
        median_chapter = n
        for s in survival:
            if s["survival_prob"] <= 0.5:
                median_chapter = s["chapter"]
                break

        # 1年/10章/20章留存率估计
        retention_10 = survival[min(9, n-1)]["survival_prob"] if n >= 10 else survival[-1]["survival_prob"]

        # 风险评分
        if median_chapter >= n * 0.8:
            risk_level = "低风险"
        elif median_chapter >= n * 0.5:
            risk_level = "中风险"
        else:
            risk_level = "高风险"

        return {
            "test": "Kaplan-Meier生存分析",
            "n_chapters": n,
            "n_events": sum(events),
            "event_rate": round(sum(events) / n, 3) if n > 0 else 0,
            "median_survival_chapter": median_chapter,
            "retention_10_chapters": round(retention_10, 4),
            "final_survival": round(survival[-1]["survival_prob"], 4) if survival else 1.0,
            "risk_level": risk_level,
            "survival_curve": survival,
            "interpretation": f"中位留存{median_chapter}章, {risk_level}, 10章后预估留存{retention_10:.0%}",
        }

    @staticmethod
    def estimate_reader_dropoff(scores: List[float]) -> Dict:
        """估计每章的读者流失概率"""
        if len(scores) < 2:
            return {"error": "至少需要2章"}

        dropoffs = []
        for i in range(1, len(scores)):
            # 分数下降幅度映射到流失概率
            score_drop = scores[i-1] - scores[i]
            # sigmoid: 下降越大，流失概率越高
            drop_prob = 1 / (1 + math.exp(-(score_drop - 5)))  # 阈值为5分差
            drop_prob = max(0.01, min(0.5, drop_prob))  # 限制在1%-50%
            dropoffs.append({
                "from_chapter": i,
                "to_chapter": i + 1,
                "score_drop": round(score_drop, 2),
                "estimated_dropoff_rate": round(drop_prob, 4),
            })

        avg_dropoff = sum(d["estimated_dropoff_rate"] for d in dropoffs) / len(dropoffs) if dropoffs else 0

        return {
            "avg_dropoff_rate": round(avg_dropoff, 4),
            "per_chapter": dropoffs,
            "interpretation": f"平均章间流失率{avg_dropoff:.1%}",
        }


# ============================================================
# Part 4: 诊断性评价 (类似医学诊断试验)
# ============================================================

class DiagnosticEvaluation:
    """
    诊断性评价：用医学诊断试验的方法评估质量评分系统的有效性。
    
    金标准(Gold Standard): 人工判断/平台审核结果 (0=拒绝, 1=通过)
    试验(Test): 我们的自动评分系统 (高于阈值为阳性=预测通过)
    
    指标:
    - 敏感度(Sensitivity): 真阳性/(真阳性+假阴性) — 检测"好书"的能力
    - 特异度(Specificity): 真阴性/(真阴性+假阳性) — 排除"差书"的能力
    - 阳性预测值(PPV): 真阳性/预测阳性总数
    - 阴性预测值(NPV): 真阴性/预测阴性总数
    - ROC曲线下面积(AUC)
    - 约登指数(Youden's Index): 最佳截断值
    """

    @staticmethod
    def evaluate(test_scores: List[float], gold_standard: List[int],
                 thresholds: List[float] = None) -> Dict:
        """
        诊断试验评价。
        
        参数:
            test_scores: 系统评分列表 (0-100)
            gold_standard: 金标准 (0=差/拒绝, 1=好/通过)
            thresholds: 截断值列表 (默认: 40-80每隔2.5)
        
        返回:
            各截断值的敏感度/特异度 + 最优截断值
        """
        if len(test_scores) != len(gold_standard) or len(test_scores) == 0:
            return {"error": "数据长度不一致或为空"}

        if thresholds is None:
            thresholds = [round(x, 1) for x in [i * 2.5 + 40 for i in range(17)]]

        results = []
        best_youden = -1
        best_threshold = 50

        for thresh in thresholds:
            tp = tn = fp = fn = 0
            for score, gold in zip(test_scores, gold_standard):
                pred_positive = score >= thresh
                actual_positive = gold == 1

                if pred_positive and actual_positive:
                    tp += 1
                elif pred_positive and not actual_positive:
                    fp += 1
                elif not pred_positive and actual_positive:
                    fn += 1
                else:
                    tn += 1

            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
            ppv = tp / (tp + fp) if (tp + fp) > 0 else 0
            npv = tn / (tn + fn) if (tn + fn) > 0 else 0
            accuracy = (tp + tn) / (tp + tn + fp + fn)
            youden = sensitivity + specificity - 1

            results.append({
                "threshold": thresh,
                "sensitivity": round(sensitivity, 4),
                "specificity": round(specificity, 4),
                "ppv": round(ppv, 4),
                "npv": round(npv, 4),
                "accuracy": round(accuracy, 4),
                "youden_index": round(youden, 4),
            })

            if youden > best_youden:
                best_youden = youden
                best_threshold = thresh

        # 计算AUC (梯形法)
        results.sort(key=lambda x: 1 - x["sensitivity"])  # 按1-特异度排序
        auc = 0
        prev_fpr = 0
        prev_tpr = 0
        for r in results:
            fpr = 1 - r["specificity"]
            tpr = r["sensitivity"]
            auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
            prev_fpr = fpr
            prev_tpr = tpr

        # AUC质量分级
        if auc >= 0.9:
            auc_quality = "优秀"
        elif auc >= 0.8:
            auc_quality = "良好"
        elif auc >= 0.7:
            auc_quality = "一般"
        elif auc >= 0.6:
            auc_quality = "较差"
        else:
            auc_quality = "无诊断价值"

        return {
            "test": "诊断试验评价",
            "auc": round(auc, 4),
            "auc_quality": auc_quality,
            "best_threshold": best_threshold,
            "best_youden_index": round(best_youden, 4),
            "roc_points": results,
            "interpretation": f"AUC={auc:.3f}({auc_quality}), 最佳截断值={best_threshold}",
        }

    @staticmethod
    def score_diagnostic_report(test_score: float, threshold: float,
                                  sensitivity: float, specificity: float) -> Dict:
        """
        对单个评分给出诊断报告（含似然比）。
        
        阳性似然比 LR+ = 敏感度/(1-特异度)
        阴性似然比 LR- = (1-敏感度)/特异度
        验前概率 → 验后概率 = 帮助我们判断"这个分数意味着什么"
        """
        pred_positive = test_score >= threshold
        
        lr_plus = sensitivity / (1 - specificity) if specificity < 1 else float('inf')
        lr_minus = (1 - sensitivity) / specificity if specificity > 0 else float('inf')

        return {
            "score": test_score,
            "threshold": threshold,
            "prediction": "预测通过" if pred_positive else "预测拒绝",
            "sensitivity_at_threshold": sensitivity,
            "specificity_at_threshold": specificity,
            "lr_positive": round(lr_plus, 2),
            "lr_negative": round(lr_minus, 2),
            "interpretation": (
                f"评分{test_score} >= 截断值{threshold}: {pred_positive}"
                if pred_positive else
                f"评分{test_score} < 截断值{threshold}: {pred_positive}"
            ),
        }


# ============================================================
# Part 5: 线性回归
# ============================================================

class LinearRegression:
    """
    多元线性回归：预测综合质量分。
    Y = b0 + b1*X1 + b2*X2 + ... + bk*Xk
    
    适用于: 确定哪些因素(子评分)对总体质量影响最大
    以及: 给定子评分，预测综合得分
    """

    @staticmethod
    def fit(X: List[List[float]], y: List[float]) -> Dict:
        """
        最小二乘拟合。
        
        参数:
            X: 特征矩阵 [样本数][特征数]
            y: 目标向量 [样本数]
        
        返回:
            系数/截距/R2/调整R2/F检验
        """
        n = len(y)
        if n < 2 or not X or not X[0]:
            return {"error": "数据不足"}

        k = len(X[0])  # 特征数
        
        # 加截距列
        X_aug = [[1.0] + row for row in X]

        # 正规方程: beta = (X^T X)^-1 X^T y
        # 使用朴素矩阵运算 (无numpy)
        m_rows = n
        m_cols = k + 1

        # X^T X
        xtx = [[0.0] * m_cols for _ in range(m_cols)]
        for i in range(m_cols):
            for j in range(m_cols):
                s = 0.0
                for r in range(m_rows):
                    s += X_aug[r][i] * X_aug[r][j]
                xtx[i][j] = s

        # X^T y
        xty = [0.0] * m_cols
        for i in range(m_cols):
            s = 0.0
            for r in range(m_rows):
                s += X_aug[r][i] * y[r]
            xty[i] = s

        # 高斯消元求解
        beta = LinearRegression._solve_linear(xtx, xty)
        if beta is None:
            return {"error": "矩阵奇异，无法求解"}

        # 预测值
        y_pred = []
        for row in X_aug:
            pred = sum(beta[i] * row[i] for i in range(m_cols))
            y_pred.append(pred)

        # 残差
        residuals = [y[i] - y_pred[i] for i in range(n)]
        ss_res = sum(r ** 2 for r in residuals)

        # 总平方和
        y_mean = sum(y) / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)

        # R2
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k - 1) if n > k + 1 else r2

        # 系数标准误 (简化)
        mse = ss_res / (n - k - 1) if n > k + 1 else ss_res / n
        se_coef = [math.sqrt(mse * xtx[i][i] / ss_tot) if ss_tot > 0 else 0 for i in range(m_cols)]
        t_stats = [beta[i] / se_coef[i] if se_coef[i] > 0 else 0 for i in range(m_cols)]

        # 特征重要性 (标准化系数)
        beta_standardized = [0.0] * k
        for j in range(k):
            x_vals = [X[i][j] for i in range(n)]
            x_mean = sum(x_vals) / n
            x_sd = math.sqrt(sum((xi - x_mean) ** 2 for xi in x_vals) / (n - 1)) if n > 1 else 1
            y_sd = math.sqrt(sum((yi - y_mean) ** 2 for yi in y) / (n - 1)) if n > 1 else 1
            beta_standardized[j] = beta[j + 1] * x_sd / y_sd if y_sd > 0 else 0

        return {
            "intercept": round(beta[0], 4),
            "coefficients": [round(b, 4) for b in beta[1:]],
            "standardized_coefficients": [round(b, 4) for b in beta_standardized],
            "r_squared": round(r2, 4),
            "adjusted_r_squared": round(adj_r2, 4),
            "mse": round(mse, 4),
            "n": n,
            "k": k,
            "predictions": [round(p, 2) for p in y_pred],
            "interpretation": f"R2={r2:.3f}, 调整R2={adj_r2:.3f}, 解释力{'强' if r2 > 0.7 else '中等' if r2 > 0.4 else '弱'}",
        }

    @staticmethod
    def _solve_linear(A: List[List[float]], b: List[float]) -> Optional[List[float]]:
        """高斯消元求解 Ax = b"""
        n = len(A)
        aug = [A[i][:] + [b[i]] for i in range(n)]

        for col in range(n):
            # 选主元
            max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
            if abs(aug[max_row][col]) < 1e-10:
                return None
            aug[col], aug[max_row] = aug[max_row], aug[col]

            pivot = aug[col][col]
            for j in range(col, n + 1):
                aug[col][j] /= pivot

            for row in range(n):
                if row != col:
                    factor = aug[row][col]
                    for j in range(col, n + 1):
                        aug[row][j] -= factor * aug[col][j]

        return [aug[i][n] for i in range(n)]


# ============================================================
# Part 6: 综合诊断引擎
# ============================================================

class MedicalStatistics:
    """
    医学统计综合引擎。
    
    对网文文本进行类似临床诊断的完整统计分析。
    """

    @staticmethod
    def _extract_sentence_features(text: str) -> Dict:
        """从文本提取可用于统计的特征"""
        sents = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) >= 5]
        if not sents:
            return {}

        sent_lens = [len(s) for s in sents]
        
        # 情绪词计数
        pos_words = {"高兴","快乐","喜悦","幸福","美好","成功","胜利","辉煌","优秀","完美","精彩"}
        neg_words = {"悲伤","痛苦","愤怒","恐惧","绝望","失败","死亡","毁灭","黑暗","残酷"}
        
        pos_count = neg_count = 0
        for s in sents:
            for w in pos_words:
                if w in s:
                    pos_count += 1
            for w in neg_words:
                if w in s:
                    neg_count += 1

        return {
            "sentence_count": len(sents),
            "sent_lengths": sent_lens,
            "positive_triggers": pos_count,
            "negative_triggers": neg_count,
            "pos_ratio": pos_count / max(1, pos_count + neg_count),
        }

    @classmethod
    def comprehensive_diagnosis(cls, text: str, chapter_num: int = 1,
                                 chapter_history: List[str] = None,
                                 reference_scores: List[float] = None) -> Dict:
        """
        对章节执行完整的医学统计诊断。
        
        包括:
        1. 描述性统计
        2. 单样本t检验 (vs 标杆)
        3. 卡方拟合优度 (叙事分布)
        4. 与历史章节的双样本对比
        5. 诊断性评价
        """
        features = cls._extract_sentence_features(text)
        if not features:
            return {"error": "文本特征提取失败"}

        findings = []
        
        # 1. 描述统计
        desc = DescriptiveStats.compute(features["sent_lengths"])
        findings.append({"type": "描述统计", "data": desc})
        
        # 2. 句长均值与标杆对比
        target_sent_len = 80.0  # 网文黄金句长
        t_result = HypothesisTests.one_sample_t(features["sent_lengths"], target_sent_len)
        if t_result.get("significant"):
            findings.append({"type": "假设检验", "data": t_result})
        
        # 3. 与前几章对比（如有历史数据）
        chapter_history = chapter_history or []
        if chapter_history and len(chapter_history) > 0:
            prev_features = cls._extract_sentence_features(chapter_history[-1])
            if prev_features.get("sent_lengths"):
                t_prev = HypothesisTests.two_sample_t(
                    features["sent_lengths"],
                    prev_features["sent_lengths"],
                    f"第{chapter_num}章", f"第{chapter_num-1}章"
                )
                if t_prev.get("significant"):
                    findings.append({"type": "章节对比", "data": t_prev})
        
        # 4. 卡方检验：正负情绪比 vs 黄金比例
        pos = features["positive_triggers"]
        neg = features["negative_triggers"]
        total_emo = pos + neg
        if total_emo > 0:
            observed = {"positive": pos / total_emo, "negative": neg / total_emo}
            expected = {"positive": 0.67, "negative": 0.33}  # 2:1 黄金比
            chi2 = HypothesisTests.chi_square_goodness_of_fit(observed, expected)
            if chi2.get("significant"):
                findings.append({"type": "分布检验", "data": chi2})
        
        # 5. 综合诊断评分
        score = 50.0
        diagnostic_factors = []
        
        # 句长适中 (50-120)
        mean_len = desc.get("mean", 100)
        if 50 <= mean_len <= 120:
            score += 15
            diagnostic_factors.append("句长适中")
        elif 30 <= mean_len <= 180:
            diagnostic_factors.append("句长可接受")
        else:
            score -= 10
            diagnostic_factors.append(f"句长异常: {mean_len:.0f}字")
        
        # 句长变异 (CV 30%-80%健康)
        cv = desc.get("cv", 0)
        if 0.3 <= cv <= 0.8:
            score += 10
            diagnostic_factors.append("句长变异健康")
        
        # 正负情绪比
        pos_r = features.get("pos_ratio", 0.5)
        if 0.55 <= pos_r <= 0.8:
            score += 10
            diagnostic_factors.append("正负情绪比健康")
        elif pos_r < 0.3:
            score -= 10
            diagnostic_factors.append("负面情绪过重")
        
        # 章节数量
        if len(features["sent_lengths"]) >= 50:
            score += 5
        else:
            diagnostic_factors.append("句子数偏少")
        
        # 与历史的一致性
        if chapter_history and len(chapter_history) >= 2:
            score += 5
            diagnostic_factors.append("有历史数据对比")
        
        score = max(0, min(100, score))
        
        return {
            "chapter_num": chapter_num,
            "overall_diagnostic_score": round(score, 1),
            "descriptive_stats": desc,
            "significant_findings": findings,
            "diagnostic_factors": diagnostic_factors,
            "text_features": {k: v for k, v in features.items() if k != "sent_lengths"},
            "interpretation": "\n".join(diagnostic_factors),
        }


# ============================================================
# Part 7: CLI
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("用法: python medical_statistics.py <文本文件路径> [章节号]")
        print("示例: python medical_statistics.py ch1.txt 1")
        sys.exit(0)

    filepath = sys.argv[1]
    chap = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    text = Path(filepath).read_text(encoding='utf-8', errors='ignore')

    stats = MedicalStatistics()
    result = stats.comprehensive_diagnosis(text, chap)

    print(f"\n{'='*60}")
    print(f"  盘古AI医学统计引擎 — 诊断报告")
    print(f"{'='*60}")
    print(f"  章节: 第{chap}章")
    print(f"  综合诊断评分: {result['overall_diagnostic_score']}/100")

    desc = result.get("descriptive_stats", {})
    print(f"\n  [描述统计]")
    print(f"    样本量: {desc.get('n', 0)} 句")
    print(f"    均值: {desc.get('mean', 0):.1f} 字/句")
    print(f"    标准差: {desc.get('sd', 0):.1f}")
    print(f"    中位数: {desc.get('median', 0):.1f}")
    print(f"    95%CI: [{desc.get('ci_95_lower', 0):.1f}, {desc.get('ci_95_upper', 0):.1f}]")
    print(f"    偏度: {desc.get('skewness', 0):.2f} 峰度: {desc.get('kurtosis', 0):.2f}")

    print(f"\n  [诊断因素]")
    for f in result.get("diagnostic_factors", []):
        print(f"    - {f}")

    findings = result.get("significant_findings", [])
    if findings:
        print(f"\n  [显著发现]")
        for fg in findings:
            data = fg.get("data", {})
            print(f"    [{fg['type']}] {data.get('interpretation', str(data))}")
    else:
        print(f"\n  [显著发现] 无异常")
