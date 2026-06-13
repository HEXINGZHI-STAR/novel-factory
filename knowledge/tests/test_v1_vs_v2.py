# -*- coding: utf-8 -*-
"""对比测试: 手写 v1 vs lifelines v2 — 纯 ASCII 输出"""
import sys, os, random, time
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from survival_engine import (
    Observation as ObsV1, KaplanMeier as KMV1, CoxModel as CoxV1,
    WeibullModel as WeibullV1, SurvivalAnalyzer as SAV1,
)
from survival_engine_v2 import (
    Observation as ObsV2, KaplanMeier as KMV2, CoxModel as CoxV2,
    WeibullModel as WeibullV2, SurvivalAnalyzer as SAV2,
)

def make_data(n=80, seed=42):
    random.seed(seed)
    v1_obs, v2_obs = [], []
    for ch in range(1, n + 1):
        hook = random.gauss(55, 10)
        expo = random.gauss(40, 12)
        action = random.gauss(30, 8)
        score = 60 + 0.7 * (hook - 55) - 0.4 * (expo - 40) + random.gauss(0, 6)
        event = 1 if score < 55 else 0
        covs = [hook, expo, action]
        names = ["hook_health_score", "exposition_pct", "action_pct"]
        v1_obs.append(ObsV1(t=ch, event=event, x=covs, names=names, raw_score=score))
        v2_obs.append(ObsV2(t=ch, event=event, x=covs, names=names, raw_score=score))
    return v1_obs, v2_obs


def sec(t):
    print(); print("=" * 65); print(f"  {t}"); print("=" * 65); print()


def main():
    errors = []
    passes = 0
    v1_obs, v2_obs = make_data(80, seed=42)

    # [1] KM
    sec("1. Kaplan-Meier")
    t0 = time.time()
    km1 = KMV1.fit(v1_obs)
    t_v1 = time.time() - t0
    t0 = time.time()
    km2 = KMV2.fit(v2_obs)
    t_v2 = time.time() - t0
    n_ev1 = len(km1.get("survival", [])) if isinstance(km1.get("survival"), list) else 0
    n_ev2 = km2.get("n_events", 0)
    n_ev1_actual = sum(o.event for o in v1_obs)
    print(f"  v1: {len(km1.get('times', []))} 点 (事件数实际={n_ev1_actual}) [{t_v1:.3f}s]")
    print(f"  v2: {len(km2.get('km_times', []))} 点, n_events={n_ev2} [{t_v2:.3f}s]")
    if n_ev1_actual == n_ev2:
        print("  [OK] 事件数一致")
        passes += 1
    else:
        errors.append(f"KM 事件数: {n_ev1_actual} vs {n_ev2}")

    # [2] Cox 前向选择
    sec("2. Cox 前向选择")
    t0 = time.time()
    cox1 = CoxV1.fit_forward(v1_obs)
    t_v1 = time.time() - t0
    t0 = time.time()
    cox2 = CoxV2.fit_forward(v2_obs)
    t_v2 = time.time() - t0
    m1 = cox1.get("model", {})
    m2 = cox2.get("model", {})
    v1_sel = cox1.get("selected_variables", [])
    v2_sel = cox2.get("selected_variables", [])
    print(f"  v1 选中: {v1_sel}")
    print(f"     LRT={m1.get('lrt_statistic', 'N/A')}, AIC={m1.get('aic', 'N/A')} [{t_v1:.3f}s]")
    print(f"  v2 选中: {v2_sel}")
    print(f"     LRT={m2.get('lrt_statistic', 'N/A'):.2f}, AIC={m2.get('aic', 'N/A'):.2f} [{t_v2:.3f}s]")
    # 看 HR 并排对比
    if v2_sel:
        print(f"     v2 HR: " + ", ".join(f"{n}={cox2[n]['hr']:.3f}" for n in v2_sel))
    common = set(v1_sel) & set(v2_sel)
    if common or (not v1_sel and not v2_sel):
        print(f"  [OK] 变量选择交集: {sorted(common)}")
        passes += 1
    else:
        errors.append(f"变量选择: v1={v1_sel}, v2={v2_sel}")

    # [3] C-index
    sec("3. C-index")
    ci1 = CoxV1.c_index(v1_obs, cox1)
    ci2 = CoxV2.c_index(v2_obs, cox2)
    c1 = ci1.get("c_index"); c2 = ci2.get("c_index")
    print(f"  v1: C={c1}")
    print(f"  v2: C={c2}")
    if c1 is not None and c2 is not None:
        diff = abs(c1 - c2)
        print(f"  |Δ|={diff:.4f}")
        if diff < 0.15:
            print("  [OK] C-index 量级一致 (|Δ| < 0.15)")
            passes += 1
        else:
            errors.append(f"C-index |Δ|={diff}")
    else:
        print("  (跳过: 某一侧无协变量)")

    # [4] Brier / IBS
    sec("4. Brier / IBS")
    br1 = CoxV1.brier_score(v1_obs, cox1)
    br2 = CoxV2.brier_score(v2_obs, cox2)
    ibs1 = br1.get("integrated_brier_score")
    ibs2 = br2.get("integrated_brier_score")
    print(f"  v1 IBS: {ibs1}")
    print(f"  v2 IBS: {ibs2}")
    if ibs1 is not None and ibs2 is not None:
        print("  [OK] 两边都可计算概率校准")
        passes += 1
    else:
        errors.append(f"IBS: v1={ibs1}, v2={ibs2}")

    # [5] Rolling CV
    sec("5. Rolling Window CV")
    try:
        cv2 = CoxV2.rolling_window_cv(v2_obs, train_size=20, test_size=10)
        if "n_folds" in cv2:
            print(f"  v2: folds={cv2['n_folds']}, train C={cv2['avg_train_c_index']:.3f}, "
                  f"test C={cv2['avg_test_c_index']:.3f}, gap={cv2['train_test_gap']:.3f}")
            print("  [OK] v2 CV 可运行")
            passes += 1
        else:
            print(f"  v2 note: {cv2.get('note', cv2.get('error', ''))}")
    except Exception as e:
        errors.append(f"CV v2: {e}")

    # [6] Schoenfeld
    sec("6. Schoenfeld PH 检验")
    try:
        sch2 = CoxV2.schoenfeld_test(v2_obs, cox2)
        if "per_variable" in sch2:
            nv = sch2["global_test"]["n_tested"]
            nviol = sch2["global_test"]["n_violations"]
            print(f"  v2: {nv} 个变量, {nviol} 个违反 PH")
            for name, info in sch2["per_variable"].items():
                print(f"    - {name}: p={info['p_value']:.4f} {'OK' if info['ph_ok'] else 'VIOLATION'}")
            print("  [OK] v2 Schoenfeld 可运行")
            passes += 1
        else:
            print(f"  v2: {sch2.get('note', sch2.get('error', ''))}")
    except Exception as e:
        errors.append(f"Schoenfeld v2: {e}")

    # [7] 时间依存
    sec("7. 时间依存协变量 (var x log t)")
    try:
        td2 = CoxV2.fit_with_time_dependence(v2_obs)
        if isinstance(td2.get("time_dependence"), list):
            td_items = td2["time_dependence"]
            print(f"  v2: 分析 {len(td_items)} 个变量")
            for item in td_items[:3]:
                interp = item.get("interpretation", "")
                viol_flag = "(显著违反)" if "显著违反" in interp else "(稳定)"
                print(f"    - {item['var']}: HR(5)={item['hr_at_t5']:.3f} → HR(50)={item['hr_at_t50']:.3f}, "
                      f"gamma_p={item['gamma_p_value']:.4f} {viol_flag}")
            mc = td2.get("model_comparison", {})
            print(f"  模型对比: LRT={mc.get('lr_statistic', 'N/A'):.2f}, "
                  f"AIC_base={mc.get('aic_base', 'N/A'):.2f}, "
                  f"AIC_ext={mc.get('aic_extended', 'N/A'):.2f}")
            print("  [OK] v2 时间依存可运行")
            passes += 1
        else:
            print(f"  v2: {td2.get('error', td2.get('note', ''))}")
    except Exception as e:
        errors.append(f"TimeDep v2: {e}")

    # [8] 共享脆弱
    sec("8. 共享脆弱 (组内相关)")
    try:
        groups = [f"block_{i // 15}" for i in range(len(v2_obs))]
        sf2 = CoxV2.fit_shared_frailty(v2_obs, groups)
        if "frailty" in sf2:
            fr = sf2["frailty"]
            print(f"  v2: n_groups={fr.get('n_groups')}, CV(组间)={fr.get('group_variance_1_over_theta'):.4f}")
            low = fr.get("lowest_risk_groups", [])
            high = fr.get("highest_risk_groups", [])
            if low: print(f"     最低风险组: {[g[0] for g in low]}")
            if high: print(f"     最高风险组: {[g[0] for g in high]}")
            adj = fr.get("adjusted_coefficients", {})
            for name, val in list(adj.items())[:3]:
                print(f"     {name}: HR_frailty={val['hr_frailty']:.3f}, HR_cox={val['hr_cox_original']:.3f} (Δ{val['change_pct']:+.1f}%)")
            print("  [OK] v2 共享脆弱可运行")
            passes += 1
        else:
            print(f"  v2: {sf2.get('error', sf2.get('note', ''))}")
    except Exception as e:
        errors.append(f"SharedFrailty v2: {e}")

    # [9] Weibull
    sec("9. Weibull AFT")
    try:
        w2 = WeibullV2.fit(v2_obs)
        if "shape" in w2:
            print(f"  v2: shape={w2['shape']:.3f}, scale={w2['scale']:.1f}, "
                  f"median={w2['median']:.1f}章, AIC={w2['aic']:.1f}")
            print(f"     {w2.get('interpretation', '')}")
            print("  [OK] v2 Weibull 可运行")
            passes += 1
        else:
            print(f"  v2: {w2.get('error', '')}")
    except Exception as e:
        errors.append(f"Weibull v2: {e}")

    # [10] SurvivalAnalyzer 端到端
    sec("10. SurvivalAnalyzer 端到端")
    chapter_diag = []
    for obs in v2_obs[:60]:
        diag = {
            "math_score": obs.raw_score,
            "math": {
                "frequency_bands": {
                    "long_term": obs.x[0] / 100.0, "mid_term": 0.3, "short_term": 0.3,
                    "hook_health_score": obs.x[0],
                },
                "markov_chain": {"state_distribution": {
                    "exposition": obs.x[1], "action": obs.x[2],
                    "dialogue": 100 - obs.x[1] - obs.x[2]
                }},
                "integral_analysis": {"arc_quality_score": 55.0},
                "information_metrics": {"bigram_entropy": 5.0},
            },
            "summary": {"word_count": 3000},
        }
        chapter_diag.append((obs.t, diag))
    try:
        report2 = SAV2.run(chapter_diag, threshold=55)
        print(f"  v2: {len(report2.get('per_chapter_risk', []))} 章风险")
        print(f"  evaluation 模块: {list(report2.get('evaluation', {}).keys())}")
        print(f"  summary: {len(report2.get('summary', []))} 行")
        for line in report2["summary"][-8:]:
            print(f"    - {line}")
        print("  [OK] v2 端到端可运行")
        passes += 1
    except Exception as e:
        errors.append(f"SA v2: {e}")
        import traceback; traceback.print_exc()

    # 总结
    sec("总结")
    print(f"  通过: {passes} / 10")
    print(f"  问题: {len(errors)}")
    for e in errors:
        print(f"    - {e}")
    print(f"  v1 大小: {os.path.getsize(os.path.join(script_dir, 'survival_engine.py'))/1024:.1f} KB")
    print(f"  v2 大小: {os.path.getsize(os.path.join(script_dir, 'survival_engine_v2.py'))/1024:.1f} KB")
    print(f"  缩减比: {os.path.getsize(os.path.join(script_dir, 'survival_engine.py')) / max(os.path.getsize(os.path.join(script_dir, 'survival_engine_v2.py')), 1):.1f}x")

    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
