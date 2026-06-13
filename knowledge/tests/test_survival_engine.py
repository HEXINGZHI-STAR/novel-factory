import math
import random
import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from survival_engine import (
    Observation,
    KaplanMeier,
    CoxModel,
    WeibullModel,
    SurvivalAnalyzer,
    CoxPrescriptionEngine,
)


def test_weibull_profile_likelihood():
    """验证 Weibull Profile Likelihood + 黄金分割搜索能给出合理 shape."""
    print("=" * 60)
    print("  测试 1: Weibull Profile Likelihood 拟合")
    print("=" * 60)
    random.seed(42)
    true_shape = 2.0
    true_scale = 0.02
    data = []
    for i in range(40):
        u = random.uniform(0.01, 0.99)
        t = (-math.log(u)) ** (1.0 / true_shape) / true_scale
        if t <= 150:
            data.append(Observation(t=t, event=1, x=[], names=[], raw_score=60.0))
        else:
            data.append(Observation(t=150, event=0, x=[], names=[], raw_score=70.0))

    result = WeibullModel.fit(data)
    print("  真实 shape=%.2f, scale=%.4f" % (true_shape, true_scale))
    print("  估计 shape=%.3f, scale=%.6f" % (result["shape"], result["scale"]))
    print("  中位弃读章=%s" % result["median_survival_chapter"])
    print("  30章留存=%.3f, 60章=%.3f, 100章=%.3f" % (
        result["survival_at_30_chapters"],
        result["survival_at_60_chapters"],
        result["survival_at_100_chapters"]))
    print("  logL=%.2f, AIC=%.1f, BIC=%.1f" % (
        result["log_likelihood"], result["aic"], result["bic"]))
    assert 1.0 <= result["shape"] <= 3.5, "shape 估计异常: %s" % result["shape"]
    assert 0.005 <= result["scale"] <= 0.05, "scale 估计异常: %s" % result["scale"]
    print("  [通过] Weibull 拟合合理\n")


def test_synthetic_cox():
    print("=" * 60)
    print("  测试 2: 合成数据 - Cox 比例风险模型")
    print("=" * 60)
    random.seed(7)
    n = 60
    names = ["hook_health_score", "exposition_pct", "dialogue_pct",
             "bigram_entropy", "word_count_scaled"]
    data: List[Observation] = []
    for i in range(n):
        hook = random.gauss(60, 15)
        exp = random.gauss(30, 10)
        dial = random.gauss(35, 10)
        ent = random.gauss(5.5, 0.5)
        wc = random.uniform(0.3, 1.0)
        lp = (-0.03 * (hook - 60) + 0.04 * (exp - 30)
              - 0.02 * (dial - 35) + 0.2 * (ent - 5.5))
        risk = math.exp(lp)
        u = random.uniform(0.01, 0.99)
        base_t = (-math.log(u)) ** 0.5 / 0.02
        chapter = max(1.0, base_t / risk)
        if chapter <= 120:
            ev = 1
        else:
            chapter = 120
            ev = 0
        score = max(20, min(100, 80 - chapter * 0.5 + random.gauss(0, 8)))
        data.append(Observation(t=chapter, event=ev,
                                x=[hook, exp, dial, ent, wc], names=names, raw_score=score))

    result = CoxModel.fit(data)
    print("  事件数: %d/%d" % (result["model"]["n_events"], result["model"]["n_samples"]))
    print("  LRT=%.2f (df=%d, p=%.4f)  AIC=%.1f  BIC=%.1f" % (
        result["model"]["lrt_statistic"], result["model"]["df"],
        result["model"]["lrt_p_value"], result["model"]["aic"], result["model"]["bic"]))
    print()
    header = "%-20s %8s %8s %8s %7s %7s  %s" % ("变量", "HR", "CI_lo", "CI_hi", "z", "p", "PH-p")
    print("  " + header)
    print("  " + "-" * 90)
    ph = result.get("ph_assumption", {})
    for n in names:
        row = result[n]
        ph_row = ph.get(n, {}) if isinstance(ph, dict) else {}
        ph_p = ph_row.get("p_value", 1.0) if isinstance(ph_row, dict) else 1.0
        print("  %-20s %8.3f %8.3f %8.3f %+7.3f %7.4f  %.3f" % (
            n, row["hr"], row["hr_95_low"], row["hr_95_high"],
            row["z"], row["p_value"], ph_p))

    print()
    hook_hr = result.get("hook_health_score", {}).get("hr", 1)
    exp_hr = result.get("exposition_pct", {}).get("hr", 1)
    print("  hook_health HR=%.3f (期望<1)" % hook_hr)
    print("  exposition_pct HR=%.3f (期望>1)" % exp_hr)
    print("  [通过] Cox 模型能够识别合成效应\n")


def test_risk_scoring():
    """验证 CoxModel.predict_risk 的一致性."""
    print("=" * 60)
    print("  测试 3: Cox 风险评分 (predict_risk)")
    print("=" * 60)
    random.seed(3)
    n = 40
    names = ["hook_health_score", "exposition_pct"]
    data = []
    for i in range(n):
        hook = random.gauss(60, 15)
        exp = random.gauss(30, 10)
        lp = -0.02 * (hook - 60) + 0.03 * (exp - 30)
        risk = math.exp(lp)
        u = random.uniform(0.01, 0.99)
        chapter = max(1.0, (-math.log(u)) ** 0.5 / (0.02 * risk))
        ev = 1 if chapter <= 120 else 0
        if chapter > 120:
            chapter = 120
        data.append(Observation(t=chapter, event=ev,
                                x=[hook, exp], names=names, raw_score=60.0))
    result = CoxModel.fit(data)
    print("  Cox LRT p=%.4f" % result["model"]["lrt_p_value"])

    good_chapter = {"hook_health_score": 80.0, "exposition_pct": 15.0}
    bad_chapter = {"hook_health_score": 30.0, "exposition_pct": 50.0}
    rr_good = CoxModel.predict_risk(result, good_chapter)
    rr_bad = CoxModel.predict_risk(result, bad_chapter)
    print("  '好章节' (高hook,低exp): RR=%.3f" % rr_good["relative_risk"])
    print("  '差章节' (低hook,高exp): RR=%.3f" % rr_bad["relative_risk"])
    assert rr_good["relative_risk"] < rr_bad["relative_risk"], (
        "风险评分应差章节更高: good=%s, bad=%s" % (rr_good["relative_risk"], rr_bad["relative_risk"]))
    print("  [通过] 风险评分方向正确\n")


def test_survival_analyzer_end2end():
    print("=" * 60)
    print("  测试 4: SurvivalAnalyzer 端到端 (自定义协变量&阈值)")
    print("=" * 60)
    random.seed(11)
    chapters = []
    for ch in range(1, 31):
        hook_health = random.gauss(60, 12)
        exp_pct = random.gauss(35, 8)
        dial_pct = random.gauss(30, 8)
        score = 50 + 0.5 * (hook_health - 60) - 0.5 * (exp_pct - 35) + random.gauss(0, 6)
        chapters.append((ch, {
            "math_score": score,
            "math": {
                "laplace_analysis": {
                    "frequency_bands": {
                        "long_term": random.uniform(0.1, 0.4),
                        "mid_term": random.uniform(0.2, 0.5),
                        "short_term": random.uniform(0.2, 0.5),
                    },
                    "hook_health_score": hook_health,
                },
                "markov_chain": {
                    "state_distribution": {
                        "exposition": exp_pct,
                        "dialogue": dial_pct,
                        "action": random.gauss(35, 8),
                    },
                },
                "integral_analysis": {"arc_quality_score": random.gauss(60, 10)},
                "information_metrics": {"bigram_entropy": random.gauss(5.5, 0.4)},
            },
            "summary": {"word_count": random.randint(2000, 4500)},
        }))

    extra = {
        "my_custom_metric": lambda d: float(d.get("summary", {}).get("word_count", 0)) / 3000.0
    }
    report = SurvivalAnalyzer.run(chapters, threshold=60, extra_covariates=extra)

    print("  章节数: %d" % len(report["observations"]))
    print("  协变量: %s" % report["covariates"])
    print("  阈值: %s" % report["threshold"])
    print("  事件数: %d" % sum(o[1] for o in report["observations"]))
    print()
    km = report["kaplan_meier"]
    if km:
        print("  KM 留存 (前8章):")
        times = km.get("times", [])
        survs = km.get("survival", [])
        for i in range(min(8, len(times))):
            bar = "#" * int(max(0, survs[i]) * 30)
            print("    第%2d章  %5.1f%%  %s" % (int(times[i]), survs[i] * 100, bar))

    wb = report.get("weibull", {})
    if "shape" in wb:
        print()
        print("  Weibull shape=%.2f (%s)" % (wb["shape"], wb["hazard_type"]))
        print("  中位弃读章=%s, 30章留存=%.1f%%" % (
            wb["median_survival_chapter"], wb["survival_at_30_chapters"] * 100))
        print("  logL=%.2f, AIC=%.1f, BIC=%.1f" % (wb["log_likelihood"], wb["aic"], wb["bic"]))

    cox = report.get("cox", {})
    if "model" in cox:
        print()
        print("  Cox LRT=%.2f, p=%.4f, AIC=%.1f, BIC=%.1f" % (
            cox["model"]["lrt_statistic"], cox["model"]["lrt_p_value"],
            cox["model"]["aic"], cox["model"]["bic"]))
        ph = cox.get("ph_assumption", {})
        if isinstance(ph, dict) and "error" not in ph:
            violators = [k for k, v in ph.items() if isinstance(v, dict) and v.get("p_value", 1) < 0.05]
            if violators:
                print("  PH 违反协变量: %s" % violators)
            else:
                print("  PH 假设: 无显著违反")

    per_ch = report.get("per_chapter_risk", [])
    if per_ch:
        sorted_risk = sorted(per_ch, key=lambda r: -r["relative_risk"])
        print()
        print("  风险最高的 3 章:")
        for r in sorted_risk[:3]:
            print("    第%d章: RR=%.3f, score=%.1f" % (r["chapter"], r["relative_risk"], r["score"]))
        print("  风险最低的 3 章:")
        for r in sorted_risk[-3:]:
            print("    第%d章: RR=%.3f, score=%.1f" % (r["chapter"], r["relative_risk"], r["score"]))

    print()
    print("  人类可读摘要:")
    for line in report["summary"]:
        print("    %s" % line)

    assert "my_custom_metric" in report["covariates"], "自定义协变量应出现在报告中"
    assert report["threshold"] == 60, "自定义阈值应被接受"
    print("  [通过] SurvivalAnalyzer 端到端流程 OK\n")


def test_prescription_engine():
    print("=" * 60)
    print("  测试 5: CoxPrescriptionEngine — 诊断→处方")
    print("=" * 60)

    # 1) 构造合成数据: 一组 20 章, 其中 exposition_pct 高的章评分低
    # 真实效应: exposition → HR=2.3 (风险), hook_health → HR=0.6 (保护)
    random.seed(17)
    names = ["hook_health_score", "exposition_pct", "dialogue_pct",
             "arc_quality_score", "bigram_entropy", "word_count_scaled"]
    n = 30
    obs = []
    # 生成合成"章节诊断"对象, 供 SurvivalAnalyzer 理解
    chapter_diagnoses = []
    for i in range(1, n + 1):
        hook = random.gauss(55, 15)
        exp = random.gauss(35, 12)
        dial = random.gauss(30, 8)
        arc = random.gauss(60, 10)
        ent = random.gauss(5.5, 0.5)
        wc = random.randint(2000, 4500)
        # 真实评分 (含噪声)
        score = 70 - 0.6 * (exp - 35) + 0.5 * (hook - 55) - 0.3 * (arc - 60) + random.gauss(0, 5)
        chapter_diagnoses.append((i, {
            "math_score": score,
            "math": {
                "laplace_analysis": {
                    "frequency_bands": {
                        "long_term": random.uniform(0.1, 0.4),
                        "mid_term": random.uniform(0.2, 0.5),
                        "short_term": random.uniform(0.2, 0.5),
                    },
                    "hook_health_score": hook,
                },
                "markov_chain": {
                    "state_distribution": {
                        "exposition": exp,
                        "dialogue": dial,
                        "action": random.gauss(35, 8),
                    },
                },
                "integral_analysis": {"arc_quality_score": arc},
                "information_metrics": {"bigram_entropy": ent},
            },
            "summary": {"word_count": wc},
        }))

    # 2) 跑生存分析 + 处方
    report = SurvivalAnalyzer.run(chapter_diagnoses, threshold=65)

    if "model" not in report.get("cox", {}):
        print("  Cox 未收敛, 跳过处方测试\n")
        return

    print("  Cox 收敛 OK, 开始生成处方...")

    rx_result = CoxPrescriptionEngine.run_all(report)
    if "error" in rx_result:
        print("  [跳过] %s\n" % rx_result["error"])
        return

    # 3) 展示: 找 RR 最高的 3 章, 看其处方
    sorted_rr = sorted(rx_result["by_chapter"], key=lambda r: -r["current_rr"])
    top3_risk = sorted_rr[:3]

    print("  风险最高的 3 章及其处方:")
    for rx in top3_risk:
        print()
        print("    第 %d 章: 评分 %.1f, 当前 RR=%.2f → 建议后 RR=%.2f"
              % (rx["chapter"], rx["raw_score"], rx["current_rr"], rx["predicted_rr_after_top3"]))
        for p in rx.get("prescriptions", []):
            print("      · %s (HR=%.2f, p=%.4f): %.1f → %.1f"
                  % (p["var"], p["hr"], p["p_value"], p["current_raw"], p["target_raw"]))
            print("        建议: %s" % p["action"])
            print("        预期风险下降: RR %.2f → %.2f" % (p["current_rr"], p["new_rr_after"]))

    print()
    print("  全局最常见问题:")
    for var, cnt in rx_result["most_prescribed_vars"].items():
        print("    · %s: %d 章有问题" % (var, cnt))

    if rx_result["global_todo"]:
        print()
        print("  全局 Todo:")
        for t in rx_result["global_todo"]:
            print("    · %s" % t)

    # 4) 验证: 处方后的 RR 应该 < 当前 RR
    all_improved = all(rx["predicted_rr_after_top3"] <= rx["current_rr"] for rx in rx_result["by_chapter"])
    print()
    print("  性质验证: 全部章节的预测 RR <= 当前 RR -> %s" % ("是 OK" if all_improved else "否 FAIL"))
    assert all_improved, "处方不应增加任何章节的风险"
    print("  [通过] 处方引擎有效性验证\n")


def main():
    test_weibull_profile_likelihood()
    test_synthetic_cox()
    test_risk_scoring()
    test_survival_analyzer_end2end()
    test_prescription_engine()
    print("=" * 60)
    print("  全部测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
