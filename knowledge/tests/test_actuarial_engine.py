# -*- coding: utf-8 -*-
"""盘古 AI 精算学引擎综合测试 —— 验证所有新增模块

验证内容:
  1. CoxModel.c_index               (排序精度)
  2. CoxModel.brier_score           (概率校准)
  3. CoxModel.rolling_window_cv     (滚动窗口交叉验证)
  4. CoxModel.schoenfeld_test       (PH 假设检验)
  5. CoxModel.fit_with_time_dependence (时间依存协变量)
  6. CoxModel.fit_shared_frailty    (共享脆弱, 组内相关)
  7. SurvivalAnalyzer 端到端        (全流程 + evaluation)
"""

import sys, os, math, random
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
parent = os.path.dirname(script_dir)
if parent not in sys.path:
    sys.path.insert(0, parent)

from survival_engine import (
    Observation, KaplanMeier, CoxModel, WeibullModel, SurvivalAnalyzer
)


# ============================================================
# 工具函数: 生成带协变量效应的合成章节数据
# ============================================================
def generate_synthetic(n_chapters=60, seed=42):
    """合成数据: 协变量有真实效应 + 噪声."""
    random.seed(seed)
    obs = []
    for ch in range(1, n_chapters + 1):
        hook = random.gauss(55, 10)
        expo = random.gauss(40, 12)
        action = random.gauss(30, 8)
        # 真实评分 = 基础 + hook保护 - expo危险 + 噪声
        score = 60 + 0.7 * (hook - 55) - 0.4 * (expo - 40) + random.gauss(0, 6)
        score = max(20, min(95, score))
        event = 1 if score < 55 else 0
        obs.append(Observation(t=ch, event=event,
                               x=[hook, expo, action],
                               names=["hook_health_score", "exposition_pct", "action_pct"],
                               raw_score=score))
    return obs


# ============================================================
# 测试 1: C-index (Harrell's concordance)
# ============================================================
def test_c_index():
    print("[1] C-index 测试")
    obs = generate_synthetic(60)
    cox = CoxModel.fit_forward(obs)
    assert "model" in cox, "Cox 必须收敛"
    ci = CoxModel.c_index(obs, cox)
    print(f"    C-index = {ci['c_index']:.4f}")
    print(f"    可比较对: {ci['n_comparable']}, 一致对: {ci['n_concordant']}, 平级: {ci.get('n_tied',0)}")
    assert ci['c_index'] is not None, "C-index 必须有数值"
    assert 0.3 <= ci['c_index'] <= 1.0, f"C-index 不合理: {ci['c_index']}"
    # 解释: 合成数据中 hook/expo 有真实效应 -> C-index 应 > 0.55
    print(f"    {ci.get('interpretation','')}")
    if ci['c_index'] > 0.55:
        print("    -> 模型有正排序能力 (C-index > 0.55  OK)")
    else:
        print("    -> C-index 偏低, 可能协变量选择不足")
    print()


# ============================================================
# 测试 2: Brier Score + IBS
# ============================================================
def test_brier():
    print("[2] Brier Score + IBS 测试")
    obs = generate_synthetic(60)
    cox = CoxModel.fit_forward(obs)
    bs = CoxModel.brier_score(obs, cox)
    assert "integrated_brier_score" in bs
    ibs = bs["integrated_brier_score"]
    print(f"    IBS = {ibs:.4f}")
    print(f"    相对零模型 = {bs.get('relative_ibs','N/A')}")
    print(f"    解释: {bs.get('interpretation','')}")
    # IBS 应 < 0.25 (随机水平)
    if ibs < 0.25:
        print(f"    -> IBS < 0.25 (低于随机), 校准 OK")
    else:
        print(f"    -> 警告: IBS > 0.25, 概率校准不足")
    n_events = len(bs.get("brier_by_time", []))
    print(f"    计算了 {n_events} 个时间点的 Brier 得分")
    print()


# ============================================================
# 测试 3: 滚动窗口 CV
# ============================================================
def test_rolling_cv():
    print("[3] 滚动窗口交叉验证")
    obs = generate_synthetic(80, seed=123)  # 更多数据
    cox = CoxModel.fit_forward(obs)
    n = len(obs)
    if n >= 30:
        cv = CoxModel.rolling_window_cv(obs, train_size=min(20, n // 2),
                                        test_size=min(10, n // 4))
        if "n_folds" in cv:
            print(f"    Folds = {cv['n_folds']}")
            print(f"    训练 C = {cv['avg_train_c_index']:.4f}")
            print(f"    测试 C = {cv['avg_test_c_index']:.4f}")
            print(f"    训练-测试差距 = {cv['train_test_gap']:.4f}")
            print(f"    {cv.get('interpretation','')}")
            # 基本校验: 训练 C 应不低于测试 C
            if cv['avg_train_c_index'] < cv['avg_test_c_index'] - 0.05:
                print("    警告: 训练 C 显著低于测试 C, 检查代码")
            else:
                print("    -> 训练/测试排序合理 (训练>=测试 OK)")
        else:
            print(f"    (CV 返回 error: {cv.get('error','')})")
    else:
        print("    跳过: 数据太少")
    print()


# ============================================================
# 测试 4: Schoenfeld 残差 PH 检验
# ============================================================
def test_schoenfeld():
    print("[4] Schoenfeld 残差 PH 假设检验")
    obs = generate_synthetic(50)
    cox = CoxModel.fit_forward(obs)
    test = CoxModel.schoenfeld_test(obs, cox)
    if "per_variable" in test:
        print(f"    被检验变量: {list(test['per_variable'].keys())}")
        for name, info in test["per_variable"].items():
            r = info.get("correlation_r", 0)
            p = info.get("p_value", 1)
            status = "违反" if not info.get("ph_ok", True) else "OK"
            print(f"      {name}: r={r:+.3f}, p={p:.4f} [{status}]")
        print(f"    全局: {test.get('global_test',{}).get('n_violations',0)} 个变量违反")
    else:
        print(f"    (无事件或无法计算)")
    print()


# ============================================================
# 测试 5: 时间依存协变量
# ============================================================
def test_time_dependence():
    print("[5] 时间依存 Cox (var * log(t))")
    obs = generate_synthetic(80, seed=7)
    tdc = CoxModel.fit_with_time_dependence(obs)
    td = tdc.get("time_dependence", [])
    base_lr = tdc.get("model_comparison", {})
    if td:
        print(f"    分析了 {len(td)} 个变量")
        for a in td[:5]:
            print(f"      {a['var']}: 原始 HR={a['hr_at_t5']:.3f}(t=5), "
                  f"{a['hr_at_t20']:.3f}(t=20), {a['hr_at_t50']:.3f}(t=50)")
            print(f"        {a.get('interpretation','')}")
    # 似然比检验: 时间依存模型 AIC 应 <= 基础模型 (或接近)
    if "lr_statistic" in base_lr:
        print(f"    模型对比: LRT={base_lr['lr_statistic']:.2f}, "
              f"p={base_lr.get('lr_p_value',1):.4f}")
        print(f"    AIC 基础={base_lr.get('aic_base','N/A')}, "
              f"AIC 扩展={base_lr.get('aic_extended','N/A')}")
    print()


# ============================================================
# 测试 6: 共享脆弱模型 (组内相关)
# ============================================================
def test_shared_frailty():
    print("[6] 共享脆弱模型 Shared Frailty")
    obs = generate_synthetic(60, seed=456)
    # 构造人工"组"效应: 每 15 章一组, 前两组有轻微额外风险
    blocks = []
    for i in range(len(obs)):
        blocks.append(f"block_{i // 15}")
    sf = CoxModel.fit_shared_frailty(obs, blocks)
    if "frailty" in sf:
        fr = sf["frailty"]
        theta = fr.get("theta")
        n_groups = fr.get("n_groups")
        print(f"    theta={theta:.3f}, 组间变异=1/theta={1/theta:.4f}")
        print(f"    n_groups={n_groups}")
        print(f"    {fr.get('interpretation','')}")
        # 每章 alpha 排序
        low = fr.get("lowest_risk_groups", [])
        high = fr.get("highest_risk_groups", [])
        if low:
            print(f"    最低风险组: {low[:2]}")
        if high:
            print(f"    最高风险组: {high[:2]}")
        # 调整后的 HR 对比标准 Cox
        adj = fr.get("adjusted_coefficients", {})
        if adj:
            print(f"    共享脆弱 vs 标准 Cox 的 HR 调整:")
            for name, val in list(adj.items())[:3]:
                print(f"      {name}: HR_frailty={val['hr_frailty']:.3f}, "
                      f"HR_cox={val['hr_cox_original']:.3f}, 变化={val['change_pct']:+.2f}%")
    else:
        print(f"    (未收敛: {sf.get('error','')})")
    print()


# ============================================================
# 测试 7: SurvivalAnalyzer 端到端 (含 evaluation)
# ============================================================
def test_survival_analyzer_full():
    print("[7] SurvivalAnalyzer 端到端测试")
    obs = generate_synthetic(60, seed=789)
    chapter_diag = []
    for o in obs:
        # 构造类似生存分析需要的格式
        d = {
            "math_score": o.raw_score,
            "math": {
                "laplace_analysis": {"frequency_bands": {"long_term": 0.3, "mid_term": 0.3, "short_term": 0.3},
                                     "hook_health_score": o.x[0]},
                "markov_chain": {"state_distribution": {"exposition": o.x[1], "action": o.x[2],
                                                         "dialogue": 100 - o.x[1] - o.x[2]}},
                "integral_analysis": {"arc_quality_score": 55.0},
                "information_metrics": {"bigram_entropy": 5.0},
            },
            "summary": {"word_count": 3000},
        }
        chapter_diag.append((o.t, d))
    report = SurvivalAnalyzer.run(chapter_diag, threshold=55)
    print(f"    Cox 模型: {len(report.get('per_chapter_risk',[]))} 章")
    print(f"    Weibull shape: {report.get('weibull',{}).get('shape','N/A')}")
    # 检查 evaluation 是否完整填充
    eval_keys = list(report.get("evaluation", {}).keys())
    print(f"    evaluation 模块: {eval_keys}")
    for k in ["c_index", "brier", "rolling_cv", "schoenfeld", "time_dependence", "shared_frailty"]:
        if k in report["evaluation"]:
            val = report["evaluation"][k]
            status = "OK" if isinstance(val, dict) and "error" not in val else (
                "SKIP" if val.get("note") else "ERR")
            print(f"      - {k}: {status}")
    # summary 列表
    summary = report.get("summary", [])
    print(f"    summary 行数: {len(summary)}")
    for line in summary[-8:]:
        print(f"      {line.strip() if isinstance(line,str) else line}")
    print()


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("  精算学引擎综合测试")
    print("=" * 60)
    results = []
    tests = [
        ("C-index", test_c_index),
        ("Brier/IBS", test_brier),
        ("Rolling CV", test_rolling_cv),
        ("Schoenfeld", test_schoenfeld),
        ("Time Dependence", test_time_dependence),
        ("Shared Frailty", test_shared_frailty),
        ("SurvivalAnalyzer 端到端", test_survival_analyzer_full),
    ]
    for name, fn in tests:
        try:
            fn()
            results.append((name, True, ""))
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append((name, False, str(e)))
            print(f"    ERROR: {e}")
        print()

    print("=" * 60)
    print("  总结")
    print("=" * 60)
    passed = 0
    for name, ok, err in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if err:
            print(f"        {err}")
        passed += 1 if ok else 0
    print(f"\n  {passed}/{len(results)} 测试通过")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
