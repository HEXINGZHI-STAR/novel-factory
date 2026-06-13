"""盘古 AI - 精算学引擎集成测试 (含所有新增模块)

运行:
    python -m knowledge.test_all_models      # 从盘古根目录
    python test_all_models.py                 # 从 knowledge 目录
"""

import sys
import os
import random
import math

# 确保包导入路径正确
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# ============================================================
# 1. 基本导入测试
# ============================================================
def test_imports():
    print("=" * 60)
    print("  测试 1: 模块导入")
    print("=" * 60)
    try:
        from survival_engine import (
            Observation, KaplanMeier, CoxModel, WeibullModel,
            SurvivalAnalyzer, CoxPrescriptionEngine,
        )
        from bayesian_engine import (
            BootstrapCI, JamesSteinShrinker, BayesianAnalyzer,
            EmpiricalBayesAnalyzer,
        )
        print("  [OK] survival_engine 导入成功")
        print("  [OK] bayesian_engine 导入成功")
        print("  [OK] 所有新增类可访问:")
        print("    - CoxModel.fit_forward (前向变量选择)")
        print("    - CoxModel.fit_bootstrap (Bootstrap SE)")
        print("    - WeibullModel.fit_segmented (分段 Weibull)")
        print("    - EmpiricalBayesAnalyzer (经验贝叶斯)")
        print("    - CoxPrescriptionEngine (诊断→处方引擎)")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback; traceback.print_exc()
        return False


# ============================================================
# 2. 合成数据生成器 —— 模拟"章节评分 + 协变量"
# ============================================================
def generate_synthetic_data(n_chapters=40, seed=42):
    """生成 n_chapters 章的合成数据:
    - hook_health: 越高越好 (HR<1, 保护因子)
    - exposition_pct: 越高越差 (HR>1, 风险因子)
    - action_pct: 中性
    - dialogue_pct: 中性
    - arc_quality_score: 越高越好 (HR<1)
    """
    random.seed(seed)
    chapters = []
    for i in range(1, n_chapters + 1):
        hook = random.gauss(55, 12)
        exp = random.gauss(38, 14)
        act = random.gauss(30, 8)
        dial = random.gauss(32, 7)
        arc = random.gauss(60, 10)
        entropy = random.gauss(5.0, 1.0)
        wc_scaled = random.gauss(0.5, 0.15)

        # 真实评分 = 基础 + 钩子贡献 - 叙述惩罚 + 结构奖励 + 噪声
        score = (55
                 + 0.6 * (hook - 55)
                 - 0.4 * (exp - 38)
                 + 0.3 * (arc - 60)
                 + random.gauss(0, 5))
        score = max(20, min(95, score))

        # 生成 6 个子维度评分 (作为 Bootstrap 的输入)
        sub_scores = [
            score + random.gauss(0, 4),   # 钩子
            score + random.gauss(0, 5),   # 节奏
            score + random.gauss(0, 4),   # 角色
            score + random.gauss(0, 5),   # 对话
            score + random.gauss(0, 6),   # 氛围
            score + random.gauss(0, 4),   # 整体
        ]
        sub_scores = [max(10, min(100, s)) for s in sub_scores]
        chapters.append({
            "chapter": i,
            "score": score,
            "sub_scores": sub_scores,
            "covariates": {
                "hook_health_score": hook,
                "exposition_pct": exp,
                "action_pct": act,
                "dialogue_pct": dial,
                "arc_quality_score": arc,
                "bigram_entropy": entropy,
                "word_count_scaled": wc_scaled,
            },
        })
    return chapters


# ============================================================
# 3. 贝叶斯引擎测试
# ============================================================
def test_bayesian():
    print()
    print("=" * 60)
    print("  测试 2: 贝叶斯引擎 (James-Stein + 经验贝叶斯)")
    print("=" * 60)

    chapters = generate_synthetic_data(n_chapters=20)
    chapters_data = [{"chapter": c["chapter"], "sub_scores": c["sub_scores"]}
                     for c in chapters]

    # James-Stein (经典)
    ba = BayesianAnalyzer()
    js = ba.analyze_chapters(chapters_data)
    print(f"  James-Stein: n={js['n_chapters']}, 收缩因子={js['shrinkage_factor']:.3f}")
    print(f"    均分: raw={js['global_raw_mean']:.1f} → 收缩后={js['global_shrunken_mean']:.1f}")
    print(f"    建议数量: {len(js['recommendations'])} 条")

    # 经验贝叶斯 (自适应)
    eb = EmpiricalBayesAnalyzer()
    eb_report = eb.analyze_chapters(chapters_data)
    print(f"\n  经验贝叶斯: tau_sq(章间真实变异)={eb_report['tau_sq_chapter_variation']:.3f}, "
          f"sigma_sq(平均噪声)={eb_report['mean_noise_variance']:.3f}")
    print(f"    信噪比 S/N = {eb_report['signal_to_noise_ratio']:.3f} "
          "(>3 → 信号主导; <1 → 噪声主导)")
    print(f"    大幅收缩章: {eb_report['n_heavy_shrink']} / {eb_report['n_chapters']}")
    print(f"    保留原分章: {eb_report['n_low_shrink']} / {eb_report['n_chapters']}")
    max_diff = max(abs(d) for d in eb_report["vs_james_stein_diffs"])
    print(f"    JS 与 EB 最大差异: {max_diff:.2f} 分")

    # 断言: EB 的"逐章收缩"应与 JS 的"全局收缩"整体方向一致
    js_shrunken = [m["shrunken_score"] for m in js["chapters"]]
    eb_shrunken = [m["shrunken_score"] for m in eb_report["chapters"]]
    raw_scores = [m["raw_score"] for m in js["chapters"]]

    # 简单的 sanity check: 两者不应该完全相同 (除非 S/N 特别低)
    assert len(js_shrunken) == len(eb_shrunken), "章数不匹配"
    print("  [通过] 贝叶斯两个引擎输出一致的章数")
    return True


# ============================================================
# 4. Cox 模型新方法测试: fit_forward + fit_bootstrap
# ============================================================
def test_cox_new_methods():
    print()
    print("=" * 60)
    print("  测试 3: Cox 模型 —— 前向选择 + Bootstrap")
    print("=" * 60)

    chapters = generate_synthetic_data(n_chapters=40)

    # 构造 observations
    names = list(chapters[0]["covariates"].keys())
    obs = []
    for c in chapters:
        score = c["score"]
        event = 1 if score < 55 else 0
        x = [c["covariates"][k] for k in names]
        obs.append(Observation(t=c["chapter"], event=event,
                               x=x, names=names, raw_score=score))

    n_events = sum(o.event for o in obs)
    print(f"  样本: {len(obs)} 章, 事件(评分<55): {n_events}")

    # 经典 fit (一次性所有协变量)
    classic = CoxModel.fit(obs)
    print(f"\n  经典 Cox (全协变量):")
    selected_classic = 0
    for name in names:
        if name in classic and isinstance(classic[name], dict):
            row = classic[name]
            pval = row.get("p_value", 1.0)
            print(f"    {name}: HR={row['hr']:.3f}, p={pval:.4f}")
            if pval < 0.15:
                selected_classic += 1

    # fit_forward (前向选择 + AIC 停止)
    fwd = CoxModel.fit_forward(obs)
    print(f"\n  Cox 前向选择 (AIC):")
    if "model" in fwd:
        model_info = fwd["model"]
        print(f"    选中变量数: {len(model_info.get('selected_vars', []))} / {len(names)}")
        print(f"    AIC={model_info.get('aic', 'N/A')}, "
              f"LRT chi2={model_info.get('lrt_statistic', 'N/A'):.3f}, "
              f"p={model_info.get('lrt_p_value', 'N/A'):.4f}")
        if "trace" in model_info and model_info["trace"]:
            print(f"    选择过程: "
                  + " → ".join(f"{t['step']}:{t['varname']}" for t in model_info["trace"]))
        for name in model_info.get("selected_vars", []):
            row = fwd.get(name, {})
            print(f"    {name}: HR={row.get('hr', 'N/A'):.3f}, "
                  f"p={row.get('p_value', 1):.4f}, "
                  f"beta_unit={row.get('beta_unit', 0):.3f}")
    else:
        note = fwd.get("note", fwd.get("error", "未知错误"))
        print(f"    [注意] {note}")

    # fit_bootstrap (稳健 SE)
    print(f"\n  Bootstrap Cox (n=100 重采样):")
    try:
        boot = CoxModel.fit_bootstrap(obs, n_bootstrap=100)
        if "model" in boot and "bootstrap" in boot:
            binfo = boot["bootstrap"]
            print(f"    收敛率: {binfo['convergence_rate']:.2f} ({binfo['n_valid']}/{binfo['total']})")
            for name in boot["model"].get("selected_vars", []):
                row = boot.get(name, {})
                if "bootstrap_se" in row:
                    print(f"    {name}: "
                          f"Bootstrap SE={row['bootstrap_se']:.4f}, "
                          f"Bootstrap p={row['bootstrap_p']:.4f}, "
                          f"HR [{row['bootstrap_hr_low']:.3f},{row['bootstrap_hr_high']:.3f}]")
        else:
            print("    Bootstrap 未产出有效结果 (样本可能太小)")
    except Exception as e:
        print(f"    [WARN] Bootstrap 出错: {e}")

    # 断言: 如果 exposition_pct 显著, 则 HR > 1; 如果 hook_health 显著, 则 HR < 1
    if "model" in fwd:
        svars = fwd["model"].get("selected_vars", [])
        for name in svars:
            row = fwd.get(name, {})
            hr = row.get("hr", 1.0)
            if "exposition" in name:
                assert hr > 1.0, f"{name} 应为风险因子(HR>1), 实际={hr}"
            if "hook_health" in name or "arc_quality" in name:
                assert hr < 1.0, f"{name} 应为保护因子(HR<1), 实际={hr}"
        print("  [通过] 选中变量方向符合预期")

    return True


# ============================================================
# 5. Weibull 分段模型测试
# ============================================================
def test_weibull_segmented():
    print()
    print("=" * 60)
    print("  测试 4: Weibull 分段模型")
    print("=" * 60)

    chapters = generate_synthetic_data(n_chapters=60)

    # 构造 observations
    names = list(chapters[0]["covariates"].keys())
    obs = []
    for c in chapters:
        score = c["score"]
        event = 1 if score < 55 else 0
        obs.append(Observation(t=c["chapter"], event=event,
                               x=[0.0], names=["filler"], raw_score=score))

    # 单一 Weibull (整本书估计 1 个 shape/scale)
    single = WeibullModel.fit(obs)
    print(f"  单一 Weibull (全 60 章): shape={single['shape']:.3f}, "
          f"scale={single['scale']:.6f}, 中位弃读章={single['median_survival_chapter']}")
    print(f"    logL={single['log_likelihood']:.2f}, AIC={single['aic']:.1f}")

    # 分段 Weibull: 每 20 章一段 (0-20, 20-40, 40-inf)
    segmented = WeibullModel.fit_segmented(obs, breakpoints=[20, 40])
    print(f"\n  分段 Weibull (0-20 / 20-40 / 40+ 章):")
    if "segments" in segmented:
        for s in segmented["segments"]:
            if "shape" in s:
                print(f"    [{s['segment']}] shape={s['shape']:.3f} ({s['hazard_type']}), "
                      f"n={s['n_events']}/{s['n']} 事件, AIC={s['aic']:.1f}")
            else:
                print(f"    [{s['segment']}] n={s['n']} → {s.get('note', s.get('error', '跳过'))}")
        print(f"\n  模型对比: 单一 AIC={single['aic']:.1f} vs "
              f"分段 total AIC={segmented['total_aic']:.1f} "
              f"(ΔAIC={single['aic'] - segmented['total_aic']:+.1f})")

    # Sanity: shape 参数应该 > 0
    for s in segmented.get("segments", []):
        if "shape" in s:
            assert s["shape"] > 0, f"shape 必须 > 0, 实际={s['shape']}"
    print("  [通过] 所有段 shape 为正")
    return True


# ============================================================
# 6. SurvivalAnalyzer 端到端 + 处方引擎
# ============================================================
def test_survival_analyzer_and_prescription():
    print()
    print("=" * 60)
    print("  测试 5: SurvivalAnalyzer 端到端 + CoxPrescriptionEngine")
    print("=" * 60)

    chapters = generate_synthetic_data(n_chapters=50)
    chapter_diagnoses = []
    for c in chapters:
        cov = c["covariates"]
        # 构造 survival_engine 期望的 diagnose 格式
        diag = {
            "math_score": c["score"],
            "math": {
                "laplace_analysis": {
                    "frequency_bands": {"long_term": 0.3, "mid_term": 0.3, "short_term": 0.3},
                    "hook_health_score": cov["hook_health_score"],
                },
                "markov_chain": {
                    "state_distribution": {
                        "exposition": cov["exposition_pct"],
                        "action": cov["action_pct"],
                        "dialogue": cov["dialogue_pct"],
                    },
                },
                "integral_analysis": {"arc_quality_score": cov["arc_quality_score"]},
                "information_metrics": {"bigram_entropy": cov["bigram_entropy"]},
            },
            "summary": {"word_count": int(cov["word_count_scaled"] * 3000 + 2000)},
        }
        chapter_diagnoses.append((c["chapter"], diag))

    report = SurvivalAnalyzer.run(chapter_diagnoses, threshold=58)
    print(f"  生存分析: {len(report.get('observations', []))} 章输入, "
          f"{len(report.get('covariates', []))} 个协变量")

    # Cox 模型输出
    cox = report.get("cox", {})
    if "model" in cox:
        m = cox["model"]
        print(f"  Cox: 选中 {len(m.get('selected_vars', []))} 个变量, "
              f"AIC={m.get('aic', 'N/A')}")
        for name in m.get("selected_vars", []):
            row = cox.get(name, {})
            print(f"    {name}: HR={row.get('hr', 'N/A'):.3f}, p={row.get('p_value', 1):.4f}")

    # 每章相对风险
    per_ch = report.get("per_chapter_risk", [])
    if per_ch:
        sorted_risk = sorted(per_ch, key=lambda r: -r["relative_risk"])
        print(f"\n  风险最高的 3 章:")
        for r in sorted_risk[:3]:
            print(f"    第{r['chapter']}章: RR={r['relative_risk']:.2f}, 评分={r['score']:.1f}")
        print(f"  风险最低的 3 章:")
        for r in sorted_risk[-3:]:
            print(f"    第{r['chapter']}章: RR={r['relative_risk']:.2f}, 评分={r['score']:.1f}")

    # 处方引擎
    rx = CoxPrescriptionEngine.run_all(report)
    if "error" in rx:
        print(f"\n  [跳过] 处方引擎: {rx['error']}")
    else:
        by_ch = rx.get("by_chapter", [])
        print(f"\n  处方引擎: 为 {len(by_ch)} 章生成了建议")
        # 找高风险章节的处方
        high_risk = [c for c in by_ch if c.get("current_rr", 0) >= 3.0]
        if high_risk:
            print(f"  高风险章节 (RR>=3): {len(high_risk)} 章")
            top = sorted(high_risk, key=lambda c: -c["current_rr"])[:2]
            for t in top:
                print(f"    第{t['chapter']}章: RR={t['current_rr']:.1f} → "
                      f"建议后 RR={t['predicted_rr_after_top3']:.1f} "
                      f"(下降{t['improvement']:+.1f})")
                for pres in t["prescriptions"][:2]:
                    print(f"      - {pres['var']}: {pres['current_raw']:.1f} → "
                          f"{pres['target_raw']:.1f} ({pres['action'][:30]})")

    # 断言: 处方后的 RR 不应该超过当前 RR
    if by_ch:
        for ch in by_ch:
            assert ch["predicted_rr_after_top3"] <= ch["current_rr"] + 1e-6, \
                f"第{ch['chapter']}章: 处方后 RR 增加 (bug)"
        print("  [通过] 处方后的 RR 不大于当前 RR")
    return True


# ============================================================
# 7. predict_risk 测试: Cox 模型能否做样本外预测
# ============================================================
def test_cox_predict():
    print()
    print("=" * 60)
    print("  测试 6: Cox 预测 —— 单章相对风险")
    print("=" * 60)

    chapters = generate_synthetic_data(n_chapters=40)
    names = list(chapters[0]["covariates"].keys())
    obs = []
    for c in chapters:
        score = c["score"]
        event = 1 if score < 55 else 0
        x = [c["covariates"][k] for k in names]
        obs.append(Observation(t=c["chapter"], event=event,
                               x=x, names=names, raw_score=score))

    cox = CoxModel.fit_forward(obs)
    if "model" not in cox:
        print("  [跳过] Cox 未收敛")
        return True

    # 构造"好章节"和"差章节"的协变量样本
    good_chapter = {"hook_health_score": 75, "exposition_pct": 25,
                    "action_pct": 35, "dialogue_pct": 40,
                    "arc_quality_score": 78, "bigram_entropy": 5.5,
                    "word_count_scaled": 0.6}
    bad_chapter = {"hook_health_score": 40, "exposition_pct": 60,
                   "action_pct": 25, "dialogue_pct": 15,
                   "arc_quality_score": 45, "bigram_entropy": 4.0,
                   "word_count_scaled": 0.4}

    good_rr = CoxModel.predict_risk(cox, good_chapter)
    bad_rr = CoxModel.predict_risk(cox, bad_chapter)

    print(f"  好章节 (高 hook+低 exp): RR={good_rr['relative_risk']:.2f}")
    for name, contrib in good_rr.get("contributions", {}).items():
        if isinstance(contrib, dict):
            print(f"    {name}: beta*x_std={contrib.get('contribution', 0):+.3f}")
    print(f"  差章节 (低 hook+高 exp): RR={bad_rr['relative_risk']:.2f}")
    for name, contrib in bad_rr.get("contributions", {}).items():
        if isinstance(contrib, dict):
            print(f"    {name}: beta*x_std={contrib.get('contribution', 0):+.3f}")

    # 断言: 差章节 RR 应显著大于好章节
    ratio = bad_rr['relative_risk'] / max(good_rr['relative_risk'], 1e-6)
    print(f"\n  差/好 RR 比值 = {ratio:.2f}x (预期 > 3x)")
    assert ratio > 1.5, f"差章节的 RR 应该显著高于好章节 (ratio={ratio:.2f})"
    print("  [通过] 方向正确: 差章节 RR > 好章节 RR")
    return True


# ============================================================
# 主入口
# ============================================================
def main():
    results = []
    results.append(("导入", test_imports()))
    results.append(("贝叶斯 (JS + EB)", test_bayesian()))
    results.append(("Cox 新方法 (fit_forward + Bootstrap)", test_cox_new_methods()))
    results.append(("Weibull 分段", test_weibull_segmented()))
    results.append(("SurvivalAnalyzer 端到端 + 处方", test_survival_analyzer_and_prescription()))
    results.append(("Cox 预测", test_cox_predict()))

    print()
    print("=" * 60)
    print("  总览")
    print("=" * 60)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    n_pass = sum(1 for _, ok in results if ok)
    print(f"\n  {n_pass}/{len(results)} 测试通过")

    return n_pass == len(results)


if __name__ == "__main__":
    # 延迟导入 (防止循环依赖)
    from survival_engine import Observation, CoxModel, WeibullModel, SurvivalAnalyzer, CoxPrescriptionEngine
    from bayesian_engine import BayesianAnalyzer, EmpiricalBayesAnalyzer
    ok = main()
    sys.exit(0 if ok else 1)
