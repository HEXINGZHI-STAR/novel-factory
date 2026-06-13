"""Day 1 优化对比测试: 正则化 + 非线性项 + 多模型集成."""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from survival_engine_v2 import (
    Observation,
    CoxModel,
    WeibullModel,
    LogNormalAFTModel,
    LogLogisticAFTModel,
    EnsembleSurvivalAnalyzer,
    RiskAttributionEngine,
    SurvivalAnalyzer,
)


def make_fake_data(n_chapters=80, seed=42):
    random.seed(seed); np.random.seed(seed)
    observations = []
    for t in range(1, n_chapters + 1):
        hook = max(0.0, min(1.0, 0.7 + 0.2 * math.sin(t / 7.0) + random.gauss(0, 0.1)))
        exposition_pct = max(0.0, min(100.0, 30 + 15 * math.sin(t / 11.0 + 1.5) + random.gauss(0, 5)))
        action_pct = 100 - exposition_pct
        dialogue_pct = max(0.0, min(100.0, 40 + 10 * math.sin(t / 13.0) + random.gauss(0, 5)))
        narrative_pct = max(0.0, min(100.0, 30 + random.gauss(0, 5)))
        arc_quality = max(0.0, min(1.0, 0.5 + 0.3 * math.sin(t / 15.0 + 0.5) + random.gauss(0, 0.1)))
        pacing_score = max(0.0, min(1.0, 0.5 + 0.2 * math.sin(t / 17.0 - 0.5) + random.gauss(0, 0.1)))
        score = 45 + 30 * hook - 0.25 * exposition_pct + 15 * arc_quality + random.gauss(0, 10)
        threshold = 55
        event = 1 if score < threshold else 0
        observations.append(Observation(
            t=t,
            event=event,
            x=[hook, exposition_pct, action_pct, dialogue_pct, narrative_pct, arc_quality, pacing_score],
            names=["hook_health_score", "exposition_pct", "action_pct", "dialogue_pct", "narrative_pct",
                   "arc_quality_score", "pacing_score"],
            raw_score=score,
        ))
    return observations


def section(title):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


if __name__ == "__main__":
    data = make_fake_data(80, 42)
    observations = data
    threshold = 55
    print(f"数据集: {len(data)} 章, {sum(o.event for o in data)} 个风险事件")

    # ------------------------------------------------------------------
    # 1) 基准 (optimized=True: 无正则化, 无非线性项, 单 Cox 模型)
    # ------------------------------------------------------------------
    section("【对比 1】增强版 fit_forward vs 手写版 (基准)")

    # 基准: 不自动 penalizer (penalizer=0.0) + 无自动非线性项
    baseline = CoxModel.fit_forward(data, penalizer=0.0, include_nonlinear=False,
                                    include_interactions=False)
    print(f"\n基准模型 (无正则化, 无自动扩展):")
    if "error" in baseline:
        print(f"  error: {baseline['error']}")
    else:
        baseline_vars = baseline.get("selected_variables", [])
        print(f"  AIC: {baseline.get('model', {}).get('aic', None)}")
        print(f"  选中变量: {baseline_vars}")
        for name in baseline_vars:
            row = baseline.get(name, {})
            if row:
                print(f"    {name}: HR={row.get('hr', 0):.3f}, p={row.get('p_value', 0):.4f}")
        ci = CoxModel.c_index(data, baseline)
        print(f"  C-index: {ci.get('c_index', None)}")

    # 增强版: 自动 penalizer + 自动非线性项 + 交互项
    enhanced = CoxModel.fit_forward(data, penalizer=None, include_nonlinear=True,
                                    include_interactions=True)
    print(f"\n增强版模型 (自动 penalizer, 自动非线性项+交互项):")
    if "error" in enhanced:
        print(f"  error: {enhanced['error']}")
    else:
        print(f"  best_penalizer: {enhanced.get('best_penalizer', None)}")
        print(f"  AIC: {enhanced.get('model', {}).get('aic', None)}")
        evars = enhanced.get("selected_variables", [])
        print(f"  选中变量 ({len(evars)}): {evars[:6]}{'...' if len(evars) > 6 else ''}")
        nonlinear = [v for v in evars if "__sq" in v]
        interactions = [v for v in evars if "__x__" in v]
        print(f"  - 非线性项: {nonlinear}")
        print(f"  - 交互项: {interactions}")
        for name in evars[:8]:
            row = enhanced.get(name, {})
            if row:
                print(f"    {name}: HR={row.get('hr', 0):.3f}, p={row.get('p_value', 0):.4f}")
        ci2 = CoxModel.c_index(data, enhanced)
        print(f"  C-index: {ci2.get('c_index', None)}")

    # ------------------------------------------------------------------
    # 2) AFT 模型族对比
    # ------------------------------------------------------------------
    section("【对比 2】AFT 模型族 (Weibull / LogNormal / LogLogistic)")
    selected = baseline.get("selected_variables", []) if "selected_variables" in baseline else []
    print(f"共用协变量: {selected}")

    for cls_name, model_cls in [
        ("Weibull AFT", WeibullModel),
        ("LogNormal AFT", LogNormalAFTModel),
        ("LogLogistic AFT", LogLogisticAFTModel),
    ]:
        try:
            if cls_name == "Weibull AFT":
                res = model_cls.fit(data)
            else:
                res = model_cls.fit(data, selected)
            if "error" in res:
                print(f"  {cls_name}: ERROR {res['error']}")
                continue
            aic = res.get("aic")
            nll = res.get("log_likelihood")
            print(f"  {cls_name}: AIC={aic}, logLik={nll}")
            if "covariates" in res:
                for cov in res["covariates"]:
                    print(f"    {cov['var']}: HR={cov['hr']:.3f}, p={cov.get('p_value', 0):.4f}")
        except Exception as e:
            print(f"  {cls_name}: EXCEPTION {e}")

    # ------------------------------------------------------------------
    # 3) 多模型集成
    # ------------------------------------------------------------------
    section("【对比 3】EnsembleSurvivalAnalyzer.run_all (四模型投票)")
    ensemble = EnsembleSurvivalAnalyzer.run_all(data)
    print(f"n_chapters: {ensemble['n_chapters']}")
    print(f"n_events: {ensemble['n_events']}")
    for line in ensemble.get("summary_lines", []):
        print(f"  {line}")
    for model_name, info in ensemble["per_model"].items():
        err = info.get("error")
        if err:
            print(f"  [{model_name}] ERROR: {str(err)[:80]}")
            continue
        aic = info.get("aic")
        print(f"  [{model_name}] AIC={aic}")
    for name, agg in ensemble.get("agreement", {}).items():
        print(f"  {name}: {agg['direction']} (HR={agg['hrs_across_models']})")

    # ------------------------------------------------------------------
    # 4) 滚动窗口 CV 对比 (过拟合检测)
    # ------------------------------------------------------------------
    section("【对比 4】滚动窗口 CV - 有/无正则化")

    for label, model_result in [("基准 (无正则化)", baseline), ("增强版", enhanced)]:
        if "selected_variables" not in model_result:
            continue
        try:
            cv = CoxModel.rolling_window_cv(data)
            print(f"  {label}: avg_train={cv.get('avg_train_c_index'):.3f}, "
                  f"avg_test={cv.get('avg_test_c_index'):.3f}, "
                  f"gap={cv.get('train_test_gap'):.3f}")
        except Exception as e:
            print(f"  {label}: CV error {e}")

    # ------------------------------------------------------------------
    # 5) 反事实模拟: "把某变量从 A 改到 B，S(t) 怎么变？"
    # ------------------------------------------------------------------
    section("【对比 5】反事实模拟 — 改变量对 S(t) 的影响")

    # 选一个显著变量做模拟
    sel = baseline.get("selected_variables", [])
    if sel and "pacing_score" in sel:
        try:
            from survival_engine_v2 import CounterfactualSimulator
            sim = CounterfactualSimulator(data, baseline)
            report = sim.compare(
                current={"pacing_score": 0.3, "arc_quality_score": 0.3},
                targets={"pacing_score": 0.7, "arc_quality_score": 0.7},
                times=[20, 40, 60, 80],
            )
            print(f"  模拟: 把 pacing_score 从 0.3 -> 0.7, arc_quality 从 0.3 -> 0.7")
            print(f"  相对风险比: {report['relative_risk_ratio']} (< 1 表示风险降低)")
            print(f"  {'时间':>6}  {'当前 S(t)':>12}  {'目标 S(t)':>12}  {'ΔS':>8}")
            for t in report["times"]:
                sc = report["survival_current"][t]
                st = report["survival_target"][t]
                d = report["delta_by_time"][t]
                arrow = " UP" if d > 0 else (" DOWN" if d < 0 else " =")
                print(f"  {t:>6}  {sc:>12.3f}  {st:>12.3f}  {d:>+8.3f}{arrow}")
        except Exception as e:
            print(f"  反事实模拟失败: {e}")
    else:
        print("  (没有可用于模拟的变量)")

    # ------------------------------------------------------------------
    # 6) 风险归因: "这一章的风险主要来自哪里？"
    # ------------------------------------------------------------------
    section("【对比 6】风险归因 RiskAttributionEngine")
    if "selected_variables" in baseline and baseline["_model_info"]["names"]:
        # 找前 5 章做归因示例
        demo_chapters = []
        for i, o in enumerate(observations[:5]):
            cov_dict = {name: o.x[k] for k, name in enumerate(o.names)}
            attr = RiskAttributionEngine.attribute(baseline, cov_dict)
            if "error" not in attr:
                driver = attr["summary"]["top_driver"]
                top_list = attr["top_risks"][:3]
                risk_score = attr["summary"]["total_risk_score"]
                demo_chapters.append({
                    "chapter": o.t,
                    "score": round(o.raw_score, 1),
                    "risk_score": risk_score,
                    "top_driver": driver,
                })
        print(f"  前 5 章风险归因摘要:")
        for dc in demo_chapters:
            driver_name, driver_pct = dc["top_driver"] if dc["top_driver"] else ("-", 0)
            print(f"    第 {dc['chapter']:>2} 章  score={dc['score']:>5.1f}  "
                  f"风险分={dc['risk_score']:+.2f}  主要来自: {driver_name} ({driver_pct}%)")
        # 详细展示 1 章 (分数最低的那一章)
        worst_idx = min(range(len(observations[:10])), key=lambda i: observations[i].raw_score)
        worst_o = observations[worst_idx]
        cov_worst = {name: worst_o.x[k] for k, name in enumerate(worst_o.names)}
        attr_detail = RiskAttributionEngine.attribute(baseline, cov_worst)
        if "error" not in attr_detail:
            print(f"\n  第 {worst_o.t} 章详细归因 (score={worst_o.raw_score:.1f}):")
            for name, data in attr_detail["per_variable"].items():
                arrow = "↑" if data["direction"] == "增加风险" else "↓"
                print(f"    {name:<30} value={data['current_value']:>6.2f}  "
                      f"z={data['z_score']:+5.2f}  {arrow}  "
                      f"contribution={data['contribution_pct']:>5.1f}%  "
                      f"({data['direction']})")
            print(f"    total_risk_score: {attr_detail['summary']['total_risk_score']:+.3f}")
    else:
        print("  (无法做归因 — 模型未选出变量)")

    # ------------------------------------------------------------------
    # 7) 综合报告: SurvivalAnalyzer 端到端验证
    # ------------------------------------------------------------------
    section("【对比 7】SurvivalAnalyzer 综合报告 (端到端)")
    try:
        # SurvivalAnalyzer.run 要求输入格式: List[Tuple[int, Dict]]
        # 需要把 Observation 列表重新包装成诊断字典
        diagnoses = []
        for o in observations:
            cov_map = {name: o.x[k] for k, name in enumerate(o.names)}
            diag = {
                "math_score": o.raw_score,
                "math": {
                    "frequency_bands": {
                        "long_term": cov_map.get("hook_health_score", 0) / 100.0
                        if cov_map.get("hook_health_score", 0) > 1 else 0,
                        "mid_term": 0,
                        "short_term": 0,
                        "hook_health_score": cov_map.get("hook_health_score", 0),
                    },
                    "markov_chain": {
                        "state_distribution": {
                            "exposition": cov_map.get("exposition_pct", 0),
                            "dialogue": cov_map.get("dialogue_pct", 0),
                            "action": cov_map.get("action_pct", 0),
                        }
                    },
                    "integral_analysis": {
                        "arc_quality_score": cov_map.get("arc_quality_score", 0),
                    },
                    "information_metrics": {
                        "bigram_entropy": cov_map.get("bigram_entropy", 0),
                    },
                },
                "summary": {"word_count": cov_map.get("word_count_scaled", 0) * 3000.0},
            }
            diagnoses.append((o.t, diag))
        report = SurvivalAnalyzer.run(diagnoses, threshold=threshold)
        print(f"  章节总数: {report.get('total_chapters', '?')}")
        print(f"  风险事件数: {report.get('n_risk_events', '?')}")
        print(f"  Cox AIC: {report.get('cox', {}).get('model', {}).get('aic', '?')}")
        print(f"  C-index: {report.get('evaluation', {}).get('c_index', {}).get('c_index', '?')}")
        print(f"  选中变量数: {len(report.get('cox', {}).get('selected_variables', []))}")
        print(f"  选中变量: {report.get('cox', {}).get('selected_variables', [])}")
        # 摘要文本前 5 行
        summary_lines = report.get("summary", [])
        print(f"  摘要:")
        for line in summary_lines[:5]:
            print(f"    {line}")
    except Exception as e:
        print(f"  SurvivalAnalyzer 错误: {e}")
        import traceback; traceback.print_exc()

    print("\n" + "=" * 78)
    print("P0 优化验证完成 OK — RiskAttributionEngine + 综合报告")
    print("=" * 78)
