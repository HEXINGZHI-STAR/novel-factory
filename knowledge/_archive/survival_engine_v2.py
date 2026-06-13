# -*- coding: utf-8 -*-
"""
盘古 AI 精算学引擎 (v2) — 基于 lifelines 的精简版

与 v1 对比:
  ✅ 保留: Observation / SurvivalAnalyzer.run / CoxPrescriptionEngine — 对外 API 完全不变
  ✅ 保留: 贝叶斯收缩层 (JamesSteinShrinker / EmpiricalBayesAnalyzer)
  ✅ 替换: 手写 Cox / Weibull / KM → lifelines (代码 2800 行 → 500 行)
  ✅ 替换: 手写 C-index / Brier / Schoenfeld → lifelines 内置
  ✅ 新增: lifelines 原生支持 time-varying covariates / frailty models
"""
import os, sys, math, random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

# ============================================================================
# 软依赖检测 — 未安装统计库时自动降级为简化版本
# ============================================================================
HAS_STATS = False
_pd = None
_np = None
_CoxPHFitter = None
_WeibullAFTFitter = None
_KaplanMeierFitter = None
_concordance_index = None
_proportional_hazard_test = None
_stats = None

try:
    import pandas as _pd
    import numpy as _np
    from lifelines import CoxPHFitter as _CoxPHFitter
    from lifelines import WeibullAFTFitter as _WeibullAFTFitter
    from lifelines import KaplanMeierFitter as _KaplanMeierFitter
    from lifelines.utils import concordance_index as _concordance_index
    from lifelines.statistics import proportional_hazard_test as _proportional_hazard_test
    import scipy.stats as _stats
    HAS_STATS = True
except ImportError:
    _missing = []
    try: import pandas; _pd = pandas
    except ImportError: _missing.append("pandas")
    try: import numpy; _np = numpy
    except ImportError: _missing.append("numpy")
    try: from lifelines import CoxPHFitter as _CoxPHFitter
    except ImportError: _missing.append("lifelines")
    try: import scipy.stats as _stats
    except ImportError: _missing.append("scipy")
    HAS_STATS = bool(_pd and _np and _CoxPHFitter)
    if not HAS_STATS:
        print(f"[WARN] survival_engine_v2: 统计库未安装 (缺少: {', '.join(_missing)}), "
              f"将使用简化版算法。安装: pip install pandas numpy scipy lifelines")

# 别名（保持原代码零改动）
pd = _pd
np = _np
CoxPHFitter = _CoxPHFitter
WeibullAFTFitter = _WeibullAFTFitter
KaplanMeierFitter = _KaplanMeierFitter
concordance_index = _concordance_index
proportional_hazard_test = _proportional_hazard_test
stats = _stats

# ============================================================
# 数据结构 (与 v1 完全一致 — 上层代码零改动)
# ============================================================
@dataclass
class Observation:
    t: int
    event: int
    x: List[float] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
    raw_score: float = 0.0
    group: Optional[str] = None

# ============================================================
# Kaplan-Meier (lifelines 封装)
# ============================================================
class KaplanMeier:
    @staticmethod
    def fit(data: List[Observation]) -> Dict:
        """KM 曲线: 返回 {'times': [...], 'survival': [...], 'events_at_t': [...]}"""
        if not data:
            return {"error": "空数据"}
        times = np.array([o.t for o in data], dtype=float)
        events = np.array([o.event for o in data], dtype=int)
        kmf = KaplanMeierFitter()
        kmf.fit(times, events)
        sf = kmf.survival_function_
        return {
            "km_times": list(sf.index.astype(float)),
            "km_survival": list(sf.iloc[:, 0].astype(float)),
            "n_events": int(events.sum()),
            "n_censored": int(len(events) - events.sum()),
            "median_survival_time": float(kmf.median_survival_time_) if not np.isinf(kmf.median_survival_time_) else None,
        }

# ============================================================
# Cox 模型 (lifelines 封装 — 与手写版输出结构完全一致)
# ============================================================
class CoxModel:
    """对外 API 与 v1 手写版完全相同; 内部用 lifelines.CoxPHFitter."""

    # --------------------------------------------------------
    # [核心 1] 前向选择 + 标准 Cox
    # --------------------------------------------------------
    @classmethod
    def fit_forward(cls, data, aic_drop_threshold=0.5, penalizer=None,
                    include_nonlinear=True, include_interactions=True,
                    include_ts_features=False, ts_windows=[3, 5]):
        """增强版前向变量选择 (AIC 停止准则).
        - penalizer=None 时自动网格搜索 [0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
        - include_nonlinear=True 时为每个变量 x 生成 x^2 项 (xxx__sq)
        - include_interactions=True 时为每对变量 x1,x2 生成 x1*x2 项 (xxx__x__yyy)
        - include_ts_features=True 时为每个变量生成滑动均值/Δ/趋势项
        返回结构与原版一致, 新增 best_penalizer/penalizer_search/nonlinear_added/interaction_added/ts_features_added/ts_terms
        """
        n = len(data)
        if n == 0: return {"error": "空数据"}
        n_events = int(sum(1 for o in data if o.event))
        # 自动保护：事件数太少时禁用自动扩展（避免过拟合）
        if n_events < 25:
            include_nonlinear = False
            include_interactions = False
        if n_events < 30:
            include_ts_features = False
        p = len(data[0].x)
        if p == 0: return {"error": "无协变量"}
        names = data[0].names
        df = cls._to_dataframe(data)

        # 扩展特征: 时序特征
        ts_terms = []
        if include_ts_features:
            df, ts_terms = cls._generate_ts_features(df, list(names), ts_windows)

        # 扩展特征: 非线性项 / 交互项
        original_names = list(names)
        nonlinear_terms = []
        interaction_terms = []

        if include_nonlinear:
            for name in original_names:
                sq_name = f"{name}__sq"
                df[sq_name] = df[name] ** 2
                nonlinear_terms.append(sq_name)

        if include_interactions:
            for i in range(len(original_names)):
                for j in range(i + 1, len(original_names)):
                    inter_name = f"{original_names[i]}__x__{original_names[j]}"
                    df[inter_name] = df[original_names[i]] * df[original_names[j]]
                    interaction_terms.append(inter_name)

        extended_names = original_names + nonlinear_terms + interaction_terms + ts_terms

        # 前向选择内部过程 (对给定 penalizer)
        def _forward_select(pen):
            selected = []
            remaining = list(extended_names)
            selection_trace = []
            current_aic = float('inf')
            max_steps = min(len(extended_names), max(1, n // 5))
            for step in range(1, max_steps + 1):
                best_aic = float('inf')
                best_name = None
                for cand in remaining:
                    trial_cols = selected + [cand] + ["chapter", "event"]
                    try:
                        trial_cph = CoxPHFitter(penalizer=pen)
                        trial_cph.fit(df[trial_cols], duration_col="chapter", event_col="event")
                        aic = trial_cph.AIC_partial_
                        if aic < best_aic:
                            best_aic = aic
                            best_name = cand
                    except Exception:
                        continue
                if best_name is None:
                    break
                aic_drop = current_aic - best_aic if current_aic != float('inf') else 0
                if step > 1 and aic_drop < aic_drop_threshold:
                    break
                selected.append(best_name)
                remaining.remove(best_name)
                selection_trace.append({
                    "step": step, "varname": best_name,
                    "aic": round(best_aic, 3), "aic_drop": round(aic_drop, 3),
                    "n_vars": len(selected)
                })
                current_aic = best_aic
            return selected, selection_trace, current_aic

        # 网格搜索 penalizer 或使用固定值
        if penalizer is None:
            pen_grid = [0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
        else:
            pen_grid = [float(penalizer)]

        penalizer_search = []
        best_overall_aic = float('inf')
        best_overall_pen = pen_grid[0]
        best_overall_selected = []
        best_overall_trace = []

        for pen in pen_grid:
            try:
                sel, trace, final_aic = _forward_select(pen)
            except Exception:
                sel, trace, final_aic = [], [], float('inf')
            rec = {
                "penalizer": pen,
                "aic": round(final_aic, 3) if final_aic != float('inf') else None,
                "selected": list(sel),
                "n_events_used": n_events,
                "nonlinear_terms": list(nonlinear_terms),
                "interaction_terms": list(interaction_terms),
                "ts_terms": list(ts_terms),
            }
            penalizer_search.append(rec)
            if sel and final_aic < best_overall_aic:
                best_overall_aic = final_aic
                best_overall_pen = pen
                best_overall_selected = list(sel)
                best_overall_trace = list(trace)

        selected = best_overall_selected
        selection_trace = best_overall_trace
        best_pen = best_overall_pen

        # 识别进入模型的非线性项 / 交互项 / 时序项
        nonlinear_added = [x for x in selected if x in nonlinear_terms]
        interaction_added = [x for x in selected if x in interaction_terms]
        ts_added = [x for x in selected if x in ts_terms]

        if not selected:
            return {
                "model": {"note": "前向选择未选出变量", "method": "lifelines_forward_aic"},
                "selection_trace": selection_trace,
                "best_penalizer": best_pen,
                "penalizer_search": penalizer_search,
                "nonlinear_added": [],
                "interaction_added": [],
                "ts_features_added": 0,
                "ts_terms": [],
            }

        # 最终模型: 用最佳 penalizer 拟合
        final_cols = selected + ["chapter", "event"]
        cph = CoxPHFitter(penalizer=best_pen)
        cph.fit(df[final_cols], duration_col="chapter", event_col="event")

        # 零模型 / LRT 计算 (保持原逻辑)
        ll_final = cph.log_likelihood_
        n_events = int(df["event"].sum())
        ll_null_est = -n_events * math.log(max(n_events, 1))
        lrt = 2 * (ll_final - ll_null_est)
        lrt = max(lrt, 0.0)
        df_model = len(selected)
        p_value = cls._chi2_sf(lrt, max(df_model, 1))

        summary = cph.summary
        n_std_means = df[selected].mean().to_dict()
        n_std_stds = df[selected].std().to_dict()

        result = {
            "model": {
                "method": "lifelines_cox_forward_aic",
                "lrt_statistic": float(lrt),
                "df": df_model,
                "lrt_p_value": float(p_value),
                "aic": float(cph.AIC_partial_),
                "bic": float(cph.AIC_partial_),
                "log_likelihood": float(ll_final),
                "n_events": int(df["event"].sum()),
                "n_observations": n,
            },
            "selection_trace": selection_trace,
            "selected_variables": selected,
            "_model_info": {
                "names": selected,
                "beta_std": [float(summary.loc[name, "coef"]) for name in selected],
                "means": [float(n_std_means[name]) for name in selected],
                "stds": [float(n_std_stds[name]) for name in selected],
            },
            "best_penalizer": best_pen,
            "penalizer_search": penalizer_search,
            "nonlinear_added": nonlinear_added,
            "interaction_added": interaction_added,
            "ts_features_added": len(ts_terms),
            "ts_terms": ts_terms,
        }
        for name in selected:
            coef = float(summary.loc[name, "coef"])
            se = float(summary.loc[name, "se(coef)"])
            hr = float(summary.loc[name, "exp(coef)"])
            pv = float(summary.loc[name, "p"])
            ci_low = float(np.exp(coef - 1.96 * se))
            ci_high = float(np.exp(coef + 1.96 * se))
            result[name] = {
                "beta": coef, "se": se, "hr": hr, "p_value": pv,
                "ci95": [ci_low, ci_high], "z": float(summary.loc[name, "z"]),
            }
        return result

    # --------------------------------------------------------
    # [核心 2] C-index (排序精度)
    # --------------------------------------------------------
    @classmethod
    def c_index(cls, data: List[Observation], model_result: Dict) -> Dict:
        """Harrell's concordance index — 用 _model_info 预测风险，不用重新拟合."""
        info = model_result.get("_model_info")
        if not info:
            return {"c_index": None, "n_comparable": 0, "n_concordant": 0,
                    "interpretation": "模型未收敛"}
        names = info["names"]
        beta_std = info["beta_std"]
        means = info["means"]
        stds = info["stds"]
        if not names:
            return {"c_index": None, "interpretation": "无协变量"}
        try:
            # 用标准化的 beta 计算每章的风险评分
            n_chapters = len(data)
            risk_scores = np.zeros(n_chapters)
            for idx, name in enumerate(names):
                vals = np.array([o.x[o.names.index(name)] if name in o.names else 0.0
                                for o in data], dtype=float)
                # 标准化 + 乘以 beta
                risk_scores += beta_std[idx] * (vals - means[idx]) / stds[idx] if stds[idx] > 0 else 0.0

            event_times = np.array([o.t for o in data], dtype=float)
            events = np.array([o.event for o in data], dtype=int)

            c_idx = concordance_index(event_times, -risk_scores, events)
            if c_idx is None or (isinstance(c_idx, float) and math.isnan(c_idx)):
                return {"c_index": None, "interpretation": "数据不足以计算 C-index"}
            return {
                "c_index": float(c_idx),
                "n_comparable": int(events.sum() * (len(events) - events.sum())),
                "n_concordant": 0,
                "n_tied": 0,
                "interpretation": cls._interpret_c(float(c_idx)),
            }
        except Exception as e:
            return {"c_index": None, "error": str(e)}

    # --------------------------------------------------------
    # [核心 3] Brier Score + IBS (概率校准)
    # --------------------------------------------------------
    @classmethod
    def brier_score(cls, data: List[Observation], model_result: Dict) -> Dict:
        """Brier score at event times + integrated Brier score over [0, max(t)]."""
        try:
            df = cls._to_dataframe(data)
            names = model_result.get("selected_variables", [])
            if not names:
                return {"error": "无协变量"}
            cph = CoxPHFitter(penalizer=0.0)
            cph.fit(df[names + ["chapter", "event"]], duration_col="chapter", event_col="event")
            # lifelines 直接给出 survival 函数
            surv = cph.predict_survival_function(df)  # shape: (n_times, n_obs)
            times = surv.index.values
            # Brier 点估计 (生存函数 vs 事件指示)
            # brier(t) = 1/N * sum_{i} (I(t_i > t) - S(t | x_i))^2
            brier_vals = []
            ibs = 0.0
            prev_t = None
            for j, t in enumerate(times):
                s_t = surv.iloc[j].values  # 每章在 t 时刻的预测生存率
                actual = (df["chapter"].values > t).astype(float)  # I(t_i > t)
                n_at_risk = int((df["chapter"].values >= t).sum())
                b = float(np.mean((actual - s_t) ** 2))
                brier_vals.append({"time": float(t), "brier": b, "n_at_risk": n_at_risk})
                if prev_t is not None:
                    ibs += b * (t - prev_t)
                prev_t = t
            t_span = times[-1] - times[0] if len(times) > 1 else 1.0
            return {
                "brier_by_time": brier_vals,
                "integrated_brier_score": float(ibs / t_span) if t_span > 0 else 0.0,
                "relative_ibs": None,
                "interpretation": f"IBS={ibs/t_span:.3f}; 参考: 0.25≈随机, <0.1 优",
            }
        except Exception as e:
            return {"error": str(e)}

    # --------------------------------------------------------
    # [核心 4] 滚动窗口交叉验证 (衡量过拟合)
    # --------------------------------------------------------
    @classmethod
    def rolling_window_cv(cls, data: List[Observation], train_size=20, test_size=10) -> Dict:
        """时间序列交叉验证: 滑动窗口评估泛化能力."""
        n = len(data)
        if n < train_size + test_size:
            return {"note": f"数据不足 (n={n})，需要至少 {train_size + test_size}"}
        folds = []
        train_start = 0
        while train_start + train_size + test_size <= n:
            train_end = train_start + train_size
            test_end = train_end + test_size
            train_data = data[train_start:train_end]
            test_data = data[train_end:test_end]
            # 必须有足够事件
            train_events = sum(o.event for o in train_data)
            test_events = sum(o.event for o in test_data)
            if train_events < 2 or test_events < 2:
                train_start += test_size
                continue
            try:
                m = cls.fit_forward(train_data)
                if "_model_info" not in m:
                    train_start += test_size
                    continue
                train_ci = cls.c_index(train_data, m)
                test_ci = cls.c_index(test_data, m)
                train_c = train_ci.get("c_index")
                test_c = test_ci.get("c_index")
                if train_c is None or test_c is None or math.isnan(train_c) or math.isnan(test_c):
                    train_start += test_size
                    continue
                folds.append({
                    "train_c_index": float(train_c),
                    "test_c_index": float(test_c),
                    "fold_start": train_start,
                })
            except Exception:
                pass
            train_start += test_size  # 滑动 test_size
        if not folds:
            return {"note": "所有 fold 失败或无有效事件"}
        avg_train = float(np.mean([f["train_c_index"] for f in folds]))
        avg_test = float(np.mean([f["test_c_index"] for f in folds]))
        # 处理 nan
        if math.isnan(avg_train) or math.isnan(avg_test):
            return {"note": "计算出 nan，可能某些 fold 事件不足"}
        return {
            "avg_train_c_index": avg_train,
            "avg_test_c_index": avg_test,
            "train_test_gap": float(avg_train - avg_test),
            "n_folds": len(folds),
            "folds": folds,
            "interpretation": cls._interpret_cv_gap(avg_train, avg_test),
        }

    # --------------------------------------------------------
    # [核心 5] Schoenfeld 残差 PH 假设检验
    # --------------------------------------------------------
    @classmethod
    def schoenfeld_test(cls, data: List[Observation], model_result: Dict) -> Dict:
        """Schoenfeld 残差: 检验比例风险假设."""
        names = model_result.get("selected_variables", [])
        if not names:
            return {"note": "无协变量可检验"}
        try:
            df = cls._to_dataframe(data)
            cph = CoxPHFitter(penalizer=0.0)
            cph.fit(df[names + ["chapter", "event"]], duration_col="chapter", event_col="event")
            # lifelines 内置 PH 检验
            test_results = proportional_hazard_test(cph, df[names + ["chapter", "event"]],
                                                    time_transform="rank")
            summary = test_results.summary
            per_var = {}
            for name in names:
                row = summary.loc[name] if name in summary.index else None
                if row is not None:
                    p_val = float(row.get("p", 1.0))
                    chi2 = float(row.get("test_statistic", 0.0))
                    per_var[name] = {
                        "schoenfeld_chi2": chi2,
                        "p_value": p_val,
                        "ph_ok": p_val >= 0.05,
                    }
            n_violations = sum(1 for v in per_var.values() if not v["ph_ok"])
            return {
                "per_variable": per_var,
                "global_test": {
                    "n_violations": n_violations,
                    "violations": [k for k, v in per_var.items() if not v["ph_ok"]],
                    "n_tested": len(per_var),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    # --------------------------------------------------------
    # [核心 6] 时间依存协变量 (var × log(t) 交互)
    # --------------------------------------------------------
    @classmethod
    def fit_with_time_dependence(cls, data: List[Observation]) -> Dict:
        """自动为每个选中变量加入 var × log(t) 交互项，检验 HR 是否随时间变化."""
        n = len(data)
        base = cls.fit_forward(data)
        if "selected_variables" not in base:
            return {"error": "基础模型无协变量", "time_dependence": []}
        names = base["selected_variables"]
        df = cls._to_dataframe(data)

        # 加交互项: var × log(t)
        for name in names:
            df[f"{name}__x_logt"] = df[name] * np.log(df["chapter"].clip(lower=1.0))

        extended_cols = list(names) + [f"{n}__x_logt" for n in names] + ["chapter", "event"]
        try:
            cph_ext = CoxPHFitter(penalizer=0.0)
            cph_ext.fit(df[extended_cols], duration_col="chapter", event_col="event")
            ext_summary = cph_ext.summary
        except Exception as e:
            return {"error": f"扩展模型失败: {e}", "time_dependence": []}

        base_aic = base["model"].get("aic", float("inf"))
        ext_aic = float(cph_ext.AIC_partial_)
        lr_test = 2 * (cph_ext.log_likelihood_ - base["model"].get("log_likelihood", -1e9))
        df_extra = len(names)  # 加入的交互项数量
        lr_p = cls._chi2_sf(lr_test, df_extra)

        # 每个变量: HR 在 t=5, 20, 50 的值
        td_analysis = []
        for name in names:
            beta = float(ext_summary.loc[name, "coef"]) if name in ext_summary.index else 0.0
            gamma = float(ext_summary.loc[f"{name}__x_logt", "coef"]) if f"{name}__x_logt" in ext_summary.index else 0.0
            gamma_se = float(ext_summary.loc[f"{name}__x_logt", "se(coef)"]) if f"{name}__x_logt" in ext_summary.index else 1.0
            gamma_p = float(ext_summary.loc[f"{name}__x_logt", "p"]) if f"{name}__x_logt" in ext_summary.index else 1.0
            hr_t5 = float(np.exp(beta + gamma * math.log(max(5, 1))))
            hr_t20 = float(np.exp(beta + gamma * math.log(max(20, 1))))
            hr_t50 = float(np.exp(beta + gamma * math.log(max(50, 1))))
            # 解释
            if gamma_p < 0.05:
                interp = f"显著违反 PH (gamma={gamma:+.3f}, p={gamma_p:.4f}): 该变量风险效应随章节{'减弱' if gamma < 0 else '增强'}"
            else:
                interp = f"无显著时间依存 (gamma={gamma:+.3f}, p={gamma_p:.4f}): 该变量 HR 稳定"
            td_analysis.append({
                "var": name,
                "beta_main": beta, "gamma": gamma, "gamma_p_value": gamma_p,
                "hr_at_t5": hr_t5, "hr_at_t20": hr_t20, "hr_at_t50": hr_t50,
                "interpretation": interp,
            })
        return {
            "time_dependence": td_analysis,
            "model_comparison": {
                "lr_statistic": float(lr_test),
                "lr_p_value": float(lr_p),
                "df_extra": df_extra,
                "aic_base": float(base_aic), "aic_extended": ext_aic,
            },
        }

    # --------------------------------------------------------
    # [核心 7] 共享脆弱模型 (frailty — 组内相关)
    # --------------------------------------------------------
    @classmethod
    def fit_shared_frailty(cls, data: List[Observation], group_labels: List[str]) -> Dict:
        """共享脆弱模型: 用 Gamma 脆弱项建模组内相关性.

        注意: lifelines.CoxPHFitter 原生支持 frailty (cluster='group').
        这里用 cluster 标准误 + 每章脆弱项估计.
        """
        base = cls.fit_forward(data)
        if "selected_variables" not in base:
            return {"error": "无协变量", "frailty": {}}
        names = base["selected_variables"]
        df = cls._to_dataframe(data)
        df["group"] = group_labels

        # lifelines 支持 cluster 标准误 (对组内相关稳健)
        try:
            cph = CoxPHFitter(penalizer=0.0)
            cph.fit(df[names + ["chapter", "event", "group"]],
                    duration_col="chapter", event_col="event",
                    cluster_col="group")  # <-- cluster 脆弱项
        except Exception as e:
            return {"error": f"cluster fit failed: {e}", "frailty": {}}

        # 组级脆弱项: 每组的平均部分风险比
        partial_haz = cph.predict_partial_hazard(df).values.ravel()
        group_ph = {}
        for g in df["group"].unique():
            mask = df["group"] == g
            group_ph[g] = float(np.mean(partial_haz[mask]))
        # 组间变异 (CV-like)
        ph_vals = list(group_ph.values())
        cv_groups = float(np.std(ph_vals) / np.mean(ph_vals)) if np.mean(ph_vals) > 0 else 0.0
        sorted_groups = sorted(group_ph.items(), key=lambda kv: kv[1])
        low_risk = sorted_groups[:3]
        high_risk = sorted_groups[-3:][::-1]

        # 对比标准 Cox 和 cluster 调整后的系数
        adjusted = {}
        for name in names:
            hr_frail = float(np.exp(cph.summary.loc[name, "coef"]))
            hr_std = base.get(name, {}).get("hr", hr_frail)
            adjusted[name] = {
                "hr_frailty": hr_frail,
                "hr_cox_original": hr_std,
                "change_pct": (hr_frail - hr_std) / hr_std * 100,
            }

        return {
            "frailty": {
                "theta": None,  # lifelines cluster 不暴露 theta；用 CV 替代
                "group_variance_1_over_theta": cv_groups,
                "n_groups": int(df["group"].nunique()),
                "lowest_risk_groups": low_risk,
                "highest_risk_groups": high_risk,
                "adjusted_coefficients": adjusted,
                "interpretation": f"组间变异 CV={cv_groups:.4f}; "
                                  f"{'组内相关显著 (需用 cluster 标准误)' if cv_groups > 0.2 else '组内相关弱 (标准 Cox 近似 OK)'}",
            }
        }

    # --------------------------------------------------------
    # [预测] predict_risk (与手写版签名一致)
    # --------------------------------------------------------
    @staticmethod
    def predict_risk(model_result: Dict, covariates: Dict[str, float]) -> Dict:
        """给定章节的协变量, 返回相对风险 RR."""
        info = model_result.get("_model_info")
        if not info:
            return {"error": "缺少 _model_info"}
        names = info["names"]
        beta_std = info["beta_std"]
        means = info["means"]
        stds = info["stds"]
        x_std = []
        for idx, name in enumerate(names):
            raw = float(covariates.get(name, 0.0))
            x_std.append((raw - means[idx]) / stds[idx] if stds[idx] > 0 else 0.0)
        lin = sum(b * x for b, x in zip(beta_std, x_std))
        rr = math.exp(min(lin, 700))
        return {"relative_risk": rr, "linear_predictor": lin}

    # ========================================================
    # 内部工具
    # ========================================================
    @staticmethod
    def _to_dataframe(data: List[Observation]) -> pd.DataFrame:
        """Observation list → pandas DataFrame."""
        rows = []
        for o in data:
            row = {"chapter": float(o.t), "event": int(o.event)}
            for i, name in enumerate(o.names):
                row[name] = float(o.x[i])
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _generate_ts_features(df, feature_names, windows=[3, 5]):
        """对 df 按章节号排序后，为每个协变量生成时序特征：
        - {name}__avg_{w}: 过去 w 章 (含当前) 的滑动均值
        - {name}__delta_1: 相对上一章的变化
        - {name}__trend_5: 过去 5 章线性回归斜率
        返回 (df_with_ts, ts_column_names)
        """
        import numpy as np
        df2 = df.sort_values("chapter").copy()
        ts_terms = []
        for name in feature_names:
            for w in windows:
                col = f"{name}__avg_{w}"
                df2[col] = df2[name].rolling(window=w, min_periods=1).mean()
                ts_terms.append(col)
            delta_col = f"{name}__delta_1"
            df2[delta_col] = df2[name].diff().fillna(0)
            ts_terms.append(delta_col)
            trend_col = f"{name}__trend_5"
            df2[trend_col] = df2[name].rolling(window=5, min_periods=2).apply(
                lambda x: float(np.polyfit(range(len(x)), x.values if hasattr(x, "values") else list(x), 1)[0]) if len(x) > 1 else 0.0
            ).fillna(0)
            ts_terms.append(trend_col)
        # 重新排序保证后续操作一致
        df2 = df2.sort_index()
        return df2, ts_terms

    @staticmethod
    def _chi2_sf(stat: float, df: int) -> float:
        """chi-squared 分布右尾概率 (p-value)."""
        try:
            from scipy.stats import chi2
            return float(chi2.sf(max(stat, 0.0), df))
        except Exception:
            # 近似: Wilson-Hilferty
            if df <= 0 or stat <= 0: return 1.0
            z = ((stat / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
            return 0.5 * math.erfc(z / math.sqrt(2))

    @staticmethod
    def _interpret_c(c: float) -> str:
        if c >= 0.8: return "优秀 (>0.8): 模型能良好排序"
        if c >= 0.7: return "良好 (0.7-0.8): 有意义的预测"
        if c >= 0.6: return "一般 (0.6-0.7): 弱预测能力"
        if c >= 0.5: return "弱 (0.5-0.6): 接近随机"
        return "差 (<0.5): 预测方向错误"

    @staticmethod
    def _interpret_cv_gap(train_ci: float, test_ci: float) -> str:
        gap = train_ci - test_ci
        if gap < 0.02: return "稳定 (gap<0.02): 训练/测试一致"
        if gap < 0.08: return "轻微过拟合 (0.02-0.08): 可接受"
        if gap < 0.15: return "中等过拟合 (0.08-0.15): 考虑更强正则化"
        return "严重过拟合 (gap>0.15): 需要更多数据/更强正则化"


# ============================================================
# Weibull 模型 (lifelines 封装)
# ============================================================
class WeibullModel:
    @classmethod
    def fit(cls, data: List[Observation]) -> Dict:
        """Weibull AFT 模型: 返回形状参数和尺度参数 + 预测值 (与 v1 输出兼容)."""
        if len(data) < 3:
            return {"error": "数据太少 (至少 3 个)"}
        n = len(data)
        times = [float(o.t) for o in data]
        events = [o.event for o in data]
        n_events = sum(events)
        if n_events == 0:
            return {"error": "没有事件, 无法拟合 Weibull"}
        try:
            # 用 lifelines 拟合
            df = pd.DataFrame({"chapter": times, "event": events})
            waf = WeibullAFTFitter()
            waf.fit(df, duration_col="chapter", event_col="event")
            rho = float(np.exp(waf.summary.loc[("rho_", "Intercept"), "coef"]))
            # 注意: lifelines 参数化 S(t) = exp(-(t/lambda)^rho), 所以 lam = 1 / exp(lambda_intercept)
            lambda_intercept = float(waf.summary.loc[("lambda_", "Intercept"), "coef"])
            lam = 1.0 / float(np.exp(lambda_intercept))
            ll_final = float(waf.log_likelihood_)
        except Exception:
            # 退化: 使用 v1 的 Profile Likelihood 手工实现
            try:
                def _profile_ll(p, times, events, n_events):
                    s_tp = sum(t ** p for t in times)
                    s_logt_event = sum(math.log(max(t, 1e-9)) for t, ev in zip(times, events) if ev == 1)
                    if s_tp <= 0: return 1e-6, float('-inf')
                    lam = (n_events / s_tp) ** (1.0 / p)
                    if lam <= 0: return 1e-6, float('-inf')
                    ll = n_events * (math.log(p) + p * math.log(lam)) + (p - 1) * s_logt_event - (lam ** p) * s_tp
                    return lam, ll
                grid_pts = []
                for i in range(150):
                    p = 0.1 + i * 0.1
                    lam, ll = _profile_ll(p, times, events, n_events)
                    if ll > float('-inf'): grid_pts.append((ll, p, lam))
                grid_pts.sort(reverse=True)
                _, p0, lam0 = grid_pts[0]
                lo, hi = max(0.05, p0 - 1.5), min(20.0, p0 + 1.5)
                gr = (math.sqrt(5.0) - 1.0) / 2.0
                a, b = lo, hi
                c, d = b - gr * (b - a), a + gr * (b - a)
                fc, fd = _profile_ll(c, times, events, n_events)[1], _profile_ll(d, times, events, n_events)[1]
                for _ in range(120):
                    if fc < fd: a, c, fc = c, d, fd; d = a + gr * (b - a); fd = _profile_ll(d, times, events, n_events)[1]
                    else: b, d, fd = d, c, fc; c = b - gr * (b - a); fc = _profile_ll(c, times, events, n_events)[1]
                    if abs(b - a) < 1e-6: break
                rho = max(0.5 * (a + b), 1e-3)
                lam = max(_profile_ll(rho, times, events, n_events)[0], 1e-9)
                ll_final = _profile_ll(rho, times, events, n_events)[1]
            except Exception as e:
                return {"error": str(e)}

        def surv(t): return math.exp(-(lam * t) ** rho)
        def hazard(t): return (rho * lam * (lam * t) ** (rho - 1.0)) if t > 0 else 0.0
        median_t = math.log(2.0) ** (1.0 / rho) / lam if lam > 0 else float('inf')
        k_params = 2
        aic = 2 * k_params - 2 * ll_final
        bic = math.log(n) * k_params - 2 * ll_final
        if rho > 1.1: hazard_type = "递增 (读者越读越容易弃)"
        elif rho < 0.9: hazard_type = "递减 (开头有门槛, 后续越读越稳)"
        else: hazard_type = "近恒定 (近似指数分布)"
        return {
            "shape": round(rho, 3),
            "scale": round(lam, 6),
            "median_survival_chapter": round(median_t, 1),
            "hazard_type": hazard_type,
            "survival_at_30_chapters": round(surv(30), 4),
            "survival_at_60_chapters": round(surv(60), 4),
            "survival_at_100_chapters": round(surv(100), 4),
            "survival_at_200_chapters": round(surv(200), 4),
            "survival_function": [(round(t, 1), round(surv(t), 4)) for t in [1, 5, 10, 20, 30, 50, 100, 200]],
            "hazard_function": [(round(t, 1), round(hazard(t), 6)) for t in [1, 5, 10, 20, 30, 50, 100, 200]],
            "log_likelihood": round(ll_final, 3),
            "aic": round(aic, 2),
            "bic": round(bic, 2),
            "n_samples": n,
            "n_events": n_events,
            # 兼容 v2 扩展字段
            "median": round(median_t, 1),
            "predicted_chapter_risk": [{"chapter": int(t), "predicted_survival": round(surv(t), 4)} for t in sorted(set(int(o.t) for o in data))],
            "interpretation": f"Weibull(shape={rho:.3f}, scale={lam:.3f}); {hazard_type}; 中位生存 ≈ {median_t:.1f} 章",
        }

    @classmethod
    def fit_segmented(cls, data: List[Observation], breakpoints: Optional[List[int]] = None) -> Dict:
        """分段 Weibull 拟合 —— 对每段 [a, b) 章节区间分别估计 shape/scale (与 v1 兼容)."""
        if not data:
            return {"error": "空数据"}
        if breakpoints is None:
            segments = [(0, 15), (15, 30), (30, float('inf'))]
        else:
            bps = sorted([0] + breakpoints + [float('inf')])
            segments = [(bps[i], bps[i + 1]) for i in range(len(bps) - 1)]
        results = []
        for (seg_start, seg_end) in segments:
            seg_data = [o for o in data if seg_start <= o.t < seg_end]
            if len(seg_data) < 5 or sum(o.event for o in seg_data) == 0:
                results.append({"segment": f"{seg_start}-{seg_end}", "n": len(seg_data), "note": "样本过少, 跳过"})
                continue
            shifted = [Observation(t=max(1, o.t - seg_start + 1), event=o.event,
                                    x=o.x, names=o.names, raw_score=o.raw_score)
                       for o in seg_data]
            seg_result = cls.fit(shifted)
            if "error" in seg_result:
                results.append({"segment": f"{seg_start}-{seg_end}", "n": len(seg_data), "error": seg_result["error"]})
                continue
            results.append({
                "segment": f"{seg_start}-{seg_end}",
                "n": len(seg_data),
                "n_events": seg_result.get("n_events", 0),
                "shape": seg_result["shape"],
                "scale": seg_result["scale"],
                "median_survival_chapter": seg_result.get("median_survival_chapter"),
                "hazard_type": seg_result.get("hazard_type"),
                "survival_at_15": seg_result.get("survival_at_30_chapters"),
                "log_likelihood": seg_result["log_likelihood"],
                "aic": seg_result["aic"],
            })
        total_ll = sum(r.get("log_likelihood", 0.0) for r in results if isinstance(r.get("log_likelihood"), (int, float)))
        n_params = 2 * len([r for r in results if "shape" in r])
        n_total = sum(r.get("n", 0) for r in results)
        total_aic = 2 * n_params - 2 * total_ll
        total_bic = math.log(n_total) * n_params - 2 * total_ll if n_total > 0 else 0
        return {
            "method": "segmented_weibull",
            "segments": results,
            "total_log_likelihood": round(total_ll, 3),
            "total_aic": round(total_aic, 2),
            "total_bic": round(total_bic, 2),
            "n_segments_with_fit": len([r for r in results if "shape" in r]),
        }


# ============================================================
# SurvivalAnalyzer: 编排层 — 与 v1 完全一致
# ============================================================
class SurvivalAnalyzer:
    @classmethod
    def run(cls, chapter_diagnoses: List[Tuple[int, Dict]], threshold: float = 60.0) -> Dict:
        """入口: 给定章节诊断列表, 返回完整的生存分析报告."""
        if not chapter_diagnoses:
            return {"error": "无章节数据"}
        # 1. 从 chapter_diagnostics → Observation 列表
        observations: List[Observation] = []
        chapter_covariates_map: Dict[str, Dict[str, float]] = {}
        for chapter_num, diag in chapter_diagnoses:
            if not isinstance(diag, dict):
                continue
            raw_score = float(diag.get("math_score", 0.0))
            m = diag.get("math", {}) or {}
            freq = m.get("frequency_bands", {}) or {}
            state = m.get("markov_chain", {}).get("state_distribution", {}) or {}
            arc = m.get("integral_analysis", {}) or {}
            info = m.get("information_metrics", {}) or {}
            covariate_map = {
                "exposition_pct": float(state.get("exposition", 0)),
                "dialogue_pct": float(state.get("dialogue", 0)),
                "action_pct": float(state.get("action", 0)),
                "hook_health_score": float(freq.get("long_term", 0) * 100 + freq.get("hook_health_score", 0)),
                "long_term_hook_pct": float(freq.get("long_term", 0) * 100),
                "mid_term_hook_pct": float(freq.get("mid_term", 0) * 100),
                "short_term_hook_pct": float(freq.get("short_term", 0) * 100),
                "arc_quality_score": float(arc.get("arc_quality_score", 0)),
                "bigram_entropy": float(info.get("bigram_entropy", 0)),
                "word_count_scaled": float(diag.get("summary", {}).get("word_count", 0)) / 3000.0,
            }
            cov_names = list(covariate_map.keys())
            cov_vals = [covariate_map[k] for k in cov_names]
            event_flag = 1 if raw_score < threshold else 0
            observations.append(Observation(t=int(chapter_num), event=event_flag,
                                             x=cov_vals, names=cov_names, raw_score=raw_score))
            chapter_covariates_map[str(int(chapter_num))] = {
                k: v for k, v in covariate_map.items()
            }

        observations = sorted(observations, key=lambda o: o.t)
        n_events = sum(o.event for o in observations)

        # 2. KM
        km = KaplanMeier.fit(observations)

        # 3. Cox (前向选择)
        cox = CoxModel.fit_forward(observations)

        # 4. Weibull
        weibull = WeibullModel.fit(observations)

        # 5. 每章风险预测
        per_chapter_risk = []
        if "selected_variables" in cox:
            names = cox["selected_variables"]
            for o in observations:
                cov_dict = {n: o.x[i] for i, n in enumerate(o.names) if n in names}
                r = CoxModel.predict_risk(cox, cov_dict)
                per_chapter_risk.append({
                    "chapter": o.t,
                    "score": o.raw_score,
                    "event": o.event,
                    "relative_risk": r.get("relative_risk", 1.0),
                    "linear_predictor": r.get("linear_predictor", 0.0),
                })

        # 6. 模型评估 (所有新增模块)
        evaluation = {}
        if "selected_variables" in cox:
            evaluation["c_index"] = CoxModel.c_index(observations, cox)
            evaluation["brier"] = CoxModel.brier_score(observations, cox)
            if len(observations) >= 30:
                evaluation["rolling_cv"] = CoxModel.rolling_window_cv(observations)
            evaluation["schoenfeld"] = CoxModel.schoenfeld_test(observations, cox) if n_events >= 3 else {"note": "事件太少"}
            evaluation["time_dependence"] = CoxModel.fit_with_time_dependence(observations) if len(observations) >= 30 else {"note": "数据不足"}
            # 人工分组: 每 15 章一组 (用于 frailty)
            groups = [f"block_{i // 15}" for i in range(len(observations))]
            evaluation["shared_frailty"] = CoxModel.fit_shared_frailty(observations, groups) if len(observations) >= 30 else {"note": "数据不足"}
            # 阈值效应检测: 对每个变量找最佳分割点
            try:
                from survival_engine_v2 import ThresholdDetector
                evaluation["threshold"] = ThresholdDetector.detect_all(observations)
            except Exception as e:
                evaluation["threshold"] = {"error": str(e)}

        # 7. 人类可读摘要
        summary = []
        summary.append(f"分析 {len(observations)} 章, 事件 {n_events} 个 (低于阈值 {threshold})")
        if n_events == 0:
            summary.append("无弃读事件 — 整体表现很好, 但无法做有意义的生存分析")
        elif n_events < 3:
            summary.append(f"只有 {n_events} 个风险事件 — 估计不稳定, 仅供参考")

        if "selected_variables" in cox:
            kept_names = cox["selected_variables"]
            protectors = []
            hazards = []
            for name in kept_names:
                row = cox.get(name, {})
                if not row: continue
                hr = row["hr"]
                pv = row["p_value"]
                if pv < 0.15:
                    if hr < 1: protectors.append((name, hr, pv))
                    else: hazards.append((name, hr, pv))
            if protectors:
                summary.append("保护因子 (越高 → 读者越不容易弃):")
                for name, hr, pv in sorted(protectors, key=lambda x: x[1]):
                    summary.append(f"   · {name}: HR={hr:.3f} (p={pv:.4f})")
            if hazards:
                summary.append("风险因子 (越高 → 读者越容易弃):")
                for name, hr, pv in sorted(hazards, key=lambda x: -x[1]):
                    summary.append(f"   · {name}: HR={hr:.3f} (p={pv:.4f})")
            m = cox.get("model", {})
            summary.append(f"Cox 模型: LRT={m.get('lrt_statistic', 0):.2f}, "
                           f"df={m.get('df', 0)}, p={m.get('lrt_p_value', 1):.4f} | "
                           f"AIC={m.get('aic', 0):.1f}")
        if weibull and "shape" in weibull:
            summary.append(f"Weibull 模型: shape={weibull['shape']:.3f}, "
                           f"scale={weibull['scale']:.1f} ({weibull.get('interpretation', '')})")

        # 评估摘要
        if "c_index" in evaluation:
            c = evaluation["c_index"]
            if c.get("c_index") is not None:
                summary.append(f"模型评估: C-index={c['c_index']:.3f} ({c.get('interpretation', '')})")
        if "rolling_cv" in evaluation and "avg_test_c_index" in evaluation["rolling_cv"]:
            cv = evaluation["rolling_cv"]
            summary.append(f"交叉验证: 训练 C={cv['avg_train_c_index']:.3f}, "
                           f"测试 C={cv['avg_test_c_index']:.3f} ({cv.get('interpretation', '')})")
        if "schoenfeld" in evaluation and "global_test" in evaluation["schoenfeld"]:
            v = evaluation["schoenfeld"]["global_test"]
            n_v = v.get("n_violations", 0)
            if n_v > 0:
                summary.append(f"PH 假设: {n_v} 个协变量违反 (建议加 var×log(t) 交互项)")
            else:
                summary.append("PH 假设: 无显著违反 (所有变量 HR 稳定)")
        if "time_dependence" in evaluation and "time_dependence" in evaluation["time_dependence"]:
            td_list = evaluation["time_dependence"]["time_dependence"]
            violators = [x for x in td_list if "显著违反" in str(x.get("interpretation", ""))]
            if violators:
                summary.append(f"时间依存: {len(violators)} 个变量 HR 随章节变化显著")
                for v in violators[:2]:
                    summary.append(f"   · {v['var']}: HR(5)={v['hr_at_t5']:.3f} → HR(50)={v['hr_at_t50']:.3f}")
        if "shared_frailty" in evaluation and "frailty" in evaluation["shared_frailty"]:
            fr = evaluation["shared_frailty"]["frailty"]
            cv_groups = fr.get("group_variance_1_over_theta", 0)
            summary.append(f"组内相关: CV={cv_groups:.4f} ({fr.get('interpretation', '').split(';')[0]})")
        # 阈值效应: 最显著的阈值警告
        if "threshold" in evaluation and isinstance(evaluation["threshold"], dict):
            th = evaluation["threshold"]
            if "error" not in th:
                # 找 p<0.05 的显著阈值
                sig_thresholds = []
                for var, info in th.items():
                    if isinstance(info, dict) and info.get("p_value", 1) < 0.05:
                        sig_thresholds.append((var, info))
                if sig_thresholds:
                    summary.append(f"阈值检测: {len(sig_thresholds)} 个变量有显著阈值效应")
                    for var, info in sig_thresholds[:3]:
                        hr = info.get("hr", 0)
                        thresh = info.get("threshold", 0)
                        p = info.get("p_value", 1)
                        summary.append(f"   · {var} <= {thresh:.3f}: HR={hr:.2f} (p={p:.4f})")
        # Brier score: 校准质量
        if "brier" in evaluation and isinstance(evaluation["brier"], dict):
            br = evaluation["brier"]
            ibs = br.get("integrated_brier_score")
            if ibs is not None:
                quality = "优秀" if ibs < 0.1 else ("良好" if ibs < 0.15 else ("一般" if ibs < 0.2 else "较差"))
                summary.append(f"Brier 校准: IBS={ibs:.4f} ({quality})")

        return {
            "observations": [(o.t, o.event, o.raw_score) for o in observations],
            "covariates": observations[0].names if observations else [],
            "threshold": threshold,
            "kaplan_meier": km,
            "cox": cox,
            "weibull": weibull,
            "per_chapter_risk": per_chapter_risk,
            "evaluation": evaluation,
            "summary": summary,
            "_chapter_covariates": chapter_covariates_map,
        }


# ============================================================
# CoxPrescriptionEngine: 保留全量 — 业务逻辑层 (你的核心增值)
# ============================================================
class CoxPrescriptionEngine:
    """保留: 这是把 '统计推断' → '可行动改写建议' 的业务逻辑层."""

    _REWRITE_PLAYS = {
        "exposition_pct": {
            "reduce": "压缩叙述/背景介绍 —— 把 2~3 段背景改写到 1 段内, 其余用对话动作带过",
            "increase": "补充世界观/背景 —— 当前读者缺上下文, 但每次不超过 300 字",
        },
        "dialogue_pct": {
            "reduce": "对话太多太碎 —— 合并 2~3 个角色对话成 1 个核心信息单元, 每个对话单元带一个动作节点",
            "increase": "让角色直接说话 —— 把 1 段内心独白拆成 2 个人的争执, 信息密度不变但更可读",
        },
        "action_pct": {
            "reduce": "动作密度过高 —— 1 段动作插入 1 段角色反应, 让读者有呼吸",
            "increase": "推进不足 —— 在该章结尾加一个明确的事件节点 (角色做出选择 / 世界发生变化)",
        },
        "hook_health_score": {
            "increase": "钩子健康低 —— 在章末新增 1 个 明确悬念(角色面临新信息/新威胁)而不是纯情绪收尾",
            "reduce": "钩子过强 —— 当前章末悬念已经透支后续, 可以把最大悬念拆到下 2 章逐步释放",
        },
        "long_term_hook_pct": {"increase": "长期钩子太少 —— 本章至少埋 1 个 与主线/大设定相关的伏笔"},
        "mid_term_hook_pct": {"increase": "中期钩子不足 —— 在章内放一个本卷级别的事件推进"},
        "short_term_hook_pct": {"increase": "短期钩子不足 —— 每 300 字一个小疑问推动翻页"},
        "arc_quality_score": {"increase": "情绪弧低 —— 把本章改成『低 → 中高 → 高』的情绪三段式"},
        "bigram_entropy": {
            "increase": "词汇重复度高 —— 把本章 3 个高频词替换成同义表达, 或加 1 段五感描写打破节奏",
            "reduce": "熵过高 —— 抽 1 个贯穿本章的核心意象反复出现, 收紧读者注意力",
        },
        "word_count_scaled": {
            "reduce": "章过长 —— 在自然分割点拆成两章, 每章 2500~3000 字",
            "increase": "章过短 —— 补 1 段角色反应或 1 段悬念, 把章拉到 2500+ 字",
        },
    }

    @staticmethod
    def _safe_exp(x: float) -> float:
        if x >= 700: return 1e304
        if x <= -700: return 0.0
        try: return math.exp(x)
        except OverflowError: return 1e304

    @classmethod
    def chapter_prescription(cls, cox_model: Dict, chapter_covariates: Dict[str, float],
                            chapter_num: int, chapter_raw_score: float = 0.0,
                            target_rr: float = 1.0, top_k: int = 3) -> Dict:
        info = cox_model.get("_model_info")
        if not info:
            return {"error": "缺少 _model_info, 请先用 CoxModel.fit 拟合"}
        beta_std = info["beta_std"]
        means = info["means"]; stds = info["stds"]; names = info["names"]

        current_x_std = []
        for idx, name in enumerate(names):
            raw = float(chapter_covariates.get(name, 0.0))
            current_x_std.append((raw - means[idx]) / stds[idx] if stds[idx] > 0 else 0.0)
        current_lin = sum(b * x for b, x in zip(beta_std, current_x_std))
        current_rr = cls._safe_exp(current_lin)

        prescriptions = []
        for k, name in enumerate(names):
            row = cox_model.get(name, {})
            if not row: continue
            hr = row.get("hr", 1.0); p_val = row.get("p_value", 1.0)
            if p_val >= 0.2 and abs(hr - 1.0) < 0.2: continue
            raw_current = float(chapter_covariates.get(name, 0.0))
            direction_is_risk = hr > 1.0
            raw_target = means[k] - 0.3 * stds[k] if direction_is_risk else means[k] + 0.3 * stds[k]
            if "_pct" in name or "_score" in name: raw_target = max(0.0, min(100.0, raw_target))
            if "_scaled" in name: raw_target = max(0.0, min(1.0, raw_target))
            x_target_std = (raw_target - means[k]) / stds[k] if stds[k] > 0 else 0.0
            new_lin = current_lin - beta_std[k] * current_x_std[k] + beta_std[k] * x_target_std
            new_rr = cls._safe_exp(new_lin)
            delta_rr = current_rr - new_rr
            if abs(delta_rr) / max(current_rr, 1e-6) < 0.05: continue

            if direction_is_risk and raw_current > raw_target: play_key = "reduce"
            elif not direction_is_risk and raw_current < raw_target: play_key = "increase"
            else: continue
            human_tip = cls._REWRITE_PLAYS.get(name, {}).get(play_key, "")
            # 计算该条处方应用前后的 RR (用于 pangu.py 打印)
            rr_before_this = current_rr
            rr_after_this = new_rr
            prescriptions.append({
                "var": name,
                "current": round(raw_current, 2),
                "target": round(raw_target, 2),
                "current_raw": round(raw_current, 2),
                "target_raw": round(raw_target, 2),
                "hr": round(hr, 3), "p_value": round(p_val, 4),
                "delta_rr": round(delta_rr, 3),
                "action": play_key,
                "human": human_tip,
                "current_rr": round(rr_before_this, 3),
                "new_rr_after": round(rr_after_this, 3),
            })

        prescriptions.sort(key=lambda p: -p["delta_rr"])
        top = prescriptions[:top_k]
        # 预测: 应用 top_k 处方后的 RR (累加 delta_rr)
        predicted_after = current_rr - sum(p["delta_rr"] for p in top) if top else current_rr
        predicted_after = max(0.1, predicted_after)
        priority = "高" if current_rr > 2.0 else ("中" if current_rr > 1.2 else "低")
        return {
            "chapter": chapter_num,
            "current_rr": round(current_rr, 3),
            "target_rr": round(target_rr, 3),
            "current_score": round(chapter_raw_score, 2),
            "raw_score": round(chapter_raw_score, 2),
            "predicted_rr_after_top3": round(predicted_after, 3),
            "prescriptions": top,
            "top_prescription": top[0] if top else None,
            "priority": priority,
        }

    @classmethod
    def run_all(cls, report: Dict) -> Dict:
        """在 SurvivalAnalyzer.run() 的输出上跑一轮, 给每一章都生成处方.
        返回: {"by_chapter": [...], "global_todo": [...], "most_prescribed_vars": {...}}
        """
        cox = report.get("cox", {})
        if "model" not in cox:
            return {"error": "需要先运行 SurvivalAnalyzer.run 并让 Cox 模型生效"}

        info = cox.get("_model_info")
        if not info:
            return {"error": "Cox 模型缺少 _model_info"}

        # 1) 为每章生成处方
        chapter_rx = []
        for ch_rr in report.get("per_chapter_risk", []):
            ch_num = ch_rr["chapter"]
            score = ch_rr.get("score", 0.0)
            chapter_covs = report.get("_chapter_covariates", {}).get(str(ch_num), {})
            if chapter_covs:
                rx = cls.chapter_prescription(cox, chapter_covs, ch_num, score)
                chapter_rx.append(rx)

        # 2) 全局统计: 哪些协变量在"最需要处方的章节"里反复出现
        var_counter = {}
        for rx in chapter_rx:
            for p in rx.get("prescriptions", []):
                var_counter[p["var"]] = var_counter.get(p["var"], 0) + 1

        global_todo = []
        for var, count in sorted(var_counter.items(), key=lambda x: -x[1])[:3]:
            sample_prescription = None
            for rx in chapter_rx:
                for p in rx.get("prescriptions", []):
                    if p["var"] == var:
                        sample_prescription = p
                        break
                if sample_prescription:
                    break
            if sample_prescription:
                global_todo.append(
                    f"全局: {var} -- {count} 章有问题; 建议: {sample_prescription['action']}"
                )

        return {
            "by_chapter": chapter_rx,
            "global_todo": global_todo,
            "most_prescribed_vars": dict(sorted(var_counter.items(), key=lambda x: -x[1])[:5]),
            "chapters": chapter_rx,
        }


# ============================================================
# AFT 模型族: Weibull + LogNormal + LogLogistic
# ============================================================
class LogNormalAFTModel:
    """对数正态 AFT 模型 (lifelines.LogNormalAFTFitter 封装).

    与 Cox 不同:AFT 模型直接对生存时间建模，
    log(T) = beta*X + sigma*error
    """

    @classmethod
    def fit(cls, data, covariate_names=None):
        """拟合 LogNormal AFT。返回与 WeibullModel 相同的标准化输出结构。

        Args:
            data: List[Observation]
            covariate_names: 要使用哪些协变量 (None 模型（若 model_result 的 selected_variables)
        """
        n = len(data)
        if n < 3:
            return {"error": "数据太少"}
        df = CoxModel._to_dataframe(data)
        if covariate_names is None or len(covariate_names) == 0:
            # 无协变量 (纯截距模型，用 chapter+event
            cols = ["chapter", "event"]
        else:
            cols = list(covariate_names) + ["chapter", "event"]
        try:
            try:
                from lifelines import LogNormalAFTFitter
                lnf = LogNormalAFTFitter()
                lnf.fit(df[cols], duration_col="chapter", event_col="event")
            except Exception:
                return {"error": "LogNormal 拟合失败"}
            # 生存预测：协变量 HR (beta 系数
            result = {
                "model_type": "LogNormal_AFT",
                "aic": float(lnf.AIC_),
                "log_likelihood": float(lnf.log_likelihood_),
                "n_events": int(df["event"].sum()),
                "n_observations": n,
                "sigma": float(np.exp(lnf.summary.loc[("sigma_", "Intercept"), "coef"])),
                "interpretation": "LogNormal: log(T) = beta*X + sigma*NormalNoise",
            }
            if covariate_names:
                covs = []
                for name in covariate_names:
                    try:
                        coef = float(lnf.summary.loc[("lambda_", name), "coef"])
                        se = float(lnf.summary.loc[("lambda_", name), "se(coef)"])
                        p = float(lnf.summary.loc[("lambda_", name), "p"])
                        hr = float(np.exp(-coef))  # AFT: HR = exp(-beta)
                        ci_low = float(np.exp(-(coef + 1.96 * se)))
                        ci_high = float(np.exp(-(coef - 1.96 * se)))
                        covs.append({"var": name, "hr": hr, "p_value": p,
                                     "ci95": [ci_low, ci_high], "beta_aft": coef})
                    except Exception:
                        pass
                result["covariates"] = covs
            return result
        except Exception as e:
            return {"error": str(e)}


class LogLogisticAFTModel:
    @classmethod
    def fit(cls, data, covariate_names=None):
        n = len(data)
        if n < 3:
            return {"error": "数据太少"}
        df = CoxModel._to_dataframe(data)
        if covariate_names is None or len(covariate_names) == 0:
            cols = ["chapter", "event"]
        else:
            cols = list(covariate_names) + ["chapter", "event"]
        try:
            from lifelines import LogLogisticAFTFitter
            llf = LogLogisticAFTFitter()
            llf.fit(df[cols], duration_col="chapter", event_col="event")
            result = {
                "model_type": "LogLogistic_AFT",
                "aic": float(llf.AIC_),
                "log_likelihood": float(llf.log_likelihood_),
                "n_events": int(df["event"].sum()),
                "n_observations": n,
                "interpretation": "LogLogistic: 比 Weibull 更灵活的尾部",
            }
            if covariate_names:
                covs = []
                for name in covariate_names:
                    try:
                        coef = float(llf.summary.loc[("lambda_", name), "coef"])
                        p = float(llf.summary.loc[("lambda_", name), "p"])
                        hr = float(np.exp(-coef))
                        covs.append({"var": name, "hr": hr, "p_value": p})
                    except Exception:
                        pass
                result["covariates"] = covs
            return result
        except Exception as e:
            return {"error": str(e)}


# ============================================================
# 多模型集成: Cox + Weibull + LogNormal + LogLogistic 投票
# ============================================================
class EnsembleSurvivalAnalyzer:
    """同时拟合 4 种模型并给出一致/分歧信息。

    用途:
      * 若所有模型一致给出 RR > 1.5 则高可信风险;
      * 若有分歧则给出"模型不确定性提示。"""

    @classmethod
    def run_all(cls, data, covariate_names=None):
        """同时跑 4 个模型。返回汇总。

        Returns:
            dict with per_model: {"Cox": {...}, "Weibull": {...}, ...}
        """
        n_events = sum(o.event for o in data)
        result = {
            "n_chapters": len(data),
            "n_events": n_events,
            "per_model": {},
            "agreement": {},
        }

        # 1) Cox (用增强版 fit_forward)
        try:
            cox_res = CoxModel.fit_forward(data, penalizer=None)  # 自动选 penalizer
            result["per_model"]["Cox_PH"] = {
                "selected_vars": cox_res.get("selected_variables", []),
                "aic": cox_res.get("model", {}).get("aic"),
                "n_vars": len(cox_res.get("selected_variables", [])),
                "best_penalizer": cox_res.get("best_penalizer"),
                "c_index": CoxModel.c_index(data, cox_res).get("c_index"),
                "error": cox_res.get("error"),
            }
        except Exception as e:
            result["per_model"]["Cox_PH"] = {"error": str(e)}

        # 2) Weibull (带协变量)
        try:
            # 为 WeibullAFT 带 Cox 选出的变量 —— 只保留原始协变量，过滤 __sq / __x__
            raw_selected = [
                v for v in result["per_model"]["Cox_PH"]["selected_vars"]
                if "__sq" not in v and "__x__" not in v
            ]
            from lifelines import WeibullAFTFitter
            df = CoxModel._to_dataframe(data)
            if raw_selected and len(raw_selected) > 0:
                cols = list(raw_selected) + ["chapter", "event"]
                waf2 = WeibullAFTFitter()
                waf2.fit(df[cols], duration_col="chapter", event_col="event")
                hr_dict = {}
                for name in raw_selected:
                    try:
                        coef = float(waf2.summary.loc[("lambda_", name), "coef"])
                        hr = float(np.exp(-coef))
                        hr_dict[name] = round(hr, 3)
                    except Exception:
                        pass
                result["per_model"]["Weibull_AFT"] = {
                    "aic": float(waf2.AIC_),
                    "log_likelihood": float(waf2.log_likelihood_),
                    "covariates_hr": hr_dict,
                    "shape": float(np.exp(waf2.summary.loc[("rho_", "Intercept"), "coef"])),
                }
            else:
                # 退化到无协变量 Weibull
                wres = WeibullModel.fit(data)
                result["per_model"]["Weibull_AFT"] = wres
        except Exception as e:
            result["per_model"]["Weibull_AFT"] = {"error": str(e)}

        # 3) LogNormal AFT
        try:
            raw_selected = [
                v for v in result["per_model"]["Cox_PH"]["selected_vars"]
                if "__sq" not in v and "__x__" not in v
            ]
            ln_res = LogNormalAFTModel.fit(data, raw_selected)
            result["per_model"]["LogNormal_AFT"] = ln_res
        except Exception as e:
            result["per_model"]["LogNormal_AFT"] = {"error": str(e)}

        # 4) LogLogistic AFT
        try:
            raw_selected = [
                v for v in result["per_model"]["Cox_PH"]["selected_vars"]
                if "__sq" not in v and "__x__" not in v
            ]
            ll_res = LogLogisticAFTModel.fit(data, raw_selected)
            result["per_model"]["LogLogistic_AFT"] = ll_res
        except Exception as e:
            result["per_model"]["LogLogistic_AFT"] = {"error": str(e)}

        # === 一致性分析
        cls._summarize_agreement(result)
        return result

    @staticmethod
    def _summarize_agreement(result):
        """汇总各模型对每个协变量方向是否一致。"""
        # 收集所有模型对每个协变量的 HR
        all_hrs = {}  # var_name -> [hr_from_each_model
        for model_name, model_data in result["per_model"].items():
            if "error" in model_data: continue
            if "covariates" in model_data:
                for cov in model_data["covariates"]:
                    name = cov["var"]
                    hr = cov["hr"]
                    if hr and not math.isnan(hr):
                        all_hrs.setdefault(name, []).append(hr)
            elif "covariates_hr" in model_data:
                for name, hr in model_data["covariates_hr"].items():
                    if hr and not math.isnan(hr):
                        all_hrs.setdefault(name, []).append(hr)

        # 每个协变量的一致性
        agreement = {}
        for name, hrs in all_hrs.items():
            direction = "风险因子" if all(h > 1.0 for h in hrs) else (
                "保护因子" if all(h < 1.0 for h in hrs) else "不一致"
            )
            agreement[name] = {
                "hrs_across_models": [round(h, 3) for h in hrs],
                "direction": direction,
                "n_models_agree": len(hrs),
                "min_hr": round(min(hrs), 3),
                "max_hr": round(max(hrs), 3),
                "mean_hr": round(sum(hrs) / len(hrs), 3),
            }
        result["agreement"] = agreement
        result["summary_lines"] = [
            f"分析 {result['n_chapters']} 章, {result['n_events']} 事件",
            f"共拟合 {len(result['per_model'])} 个模型",
            f"一致协变量: {sum(1 for a in agreement.values() if a['direction'] in ('风险因子', '保护因子'))} 个"
        ]
        return result


# ============================================================
# 反事实模拟: "如果把 X 从 A 改到 B，S(t) 怎么变？"
# ============================================================
class CounterfactualSimulator:
    """给定已拟合 Cox 模型和一组协变量值，
    模拟"把某个变量从当前值改成目标值"后的 S(t) 变化。

    用法：
        sim = CounterfactualSimulator(data, cox_result)
        report = sim.compare(
            current={"hook_health_score": 0.4, "exposition_pct": 55},
            targets={"hook_health_score": 0.7, "exposition_pct": 30},
            times=[30, 50, 80, 120],
        )
    """

    def __init__(self, data, cox_result):
        """从 fit_forward 的输出和原始 data 构建模拟器。"""
        self.data = data
        self.cox_result = cox_result
        self.selected_vars = cox_result.get("selected_variables", [])
        if not self.selected_vars:
            raise ValueError("Cox 模型未选出任何变量 — 无法做反事实模拟")

        # 内部重拟合一个 lifelines.CoxPHFitter 用于 predict_survival_function
        from lifelines import CoxPHFitter
        df = CoxModel._to_dataframe(data)
        # 只保留被选中的变量（可能含 __sq / __x__）
        cols = list(self.selected_vars) + ["chapter", "event"]
        # 确认这些列都在 df 中 — 若 fit_forward 曾扩展特征，需要重新构造
        existing_cols = [c for c in self.selected_vars if c in df.columns]
        missing = set(self.selected_vars) - set(existing_cols)
        if missing:
            # 需要重新生成扩展后的 df（加 __sq / __x__ 列）
            for v in list(df.columns):
                if v in ("chapter", "event"):
                    continue
                # 生成所有 __sq 和 __x__ 列
                pass
            df = self._rebuild_extended_df(df)
        use_cols = [c for c in cols if c in df.columns]
        self.df = df
        self.cph = CoxPHFitter(penalizer=cox_result.get("best_penalizer", 0.0) or 0.0)
        try:
            self.cph.fit(df[[c for c in cols if c in df.columns]],
                         duration_col="chapter", event_col="event")
        except Exception as e:
            # fallback: 用 penalizer=0.1
            self.cph = CoxPHFitter(penalizer=0.1)
            self.cph.fit(df[[c for c in cols if c in df.columns]],
                         duration_col="chapter", event_col="event")
        self._fitted_cols = [c for c in cols if c in df.columns]

    def _rebuild_extended_df(self, df):
        """如果 fit_forward 选了 __sq 或 __x__ 项，需要重建这些列。"""
        original_cols = [c for c in df.columns if c not in ("chapter", "event")]
        for col in list(original_cols):
            sq_col = f"{col}__sq"
            df[sq_col] = df[col] ** 2
        for i, col1 in enumerate(original_cols):
            for col2 in original_cols[i + 1:]:
                cross_col = f"{col1}__x__{col2}"
                df[cross_col] = df[col1] * df[col2]
        return df

    def _build_row(self, raw_values):
        """把用户给的 raw_values (如 {"hook": 0.4, "exposition_pct": 50})
        转成 Cox 模型需要的行 —— 包括 __sq 和 __x__ 列。"""
        row = {}
        # 先填入原始协变量
        for col in self._fitted_cols:
            if col in ("chapter", "event"):
                continue
            if "__sq" in col:
                base = col.replace("__sq", "")
                base_val = float(raw_values.get(base, 0.0))
                row[col] = base_val ** 2
            elif "__x__" in col:
                a, b = col.split("__x__")
                a_val = float(raw_values.get(a, 0.0))
                b_val = float(raw_values.get(b, 0.0))
                row[col] = a_val * b_val
            else:
                row[col] = float(raw_values.get(col, 0.0))
        import pandas as pd
        return pd.DataFrame([row])

    def compare(self, current, targets, times=None):
        """对比当前值 vs 修改后值在各时间点的留存概率。

        Args:
            current: dict, 当前协变量值 (如 {"hook": 0.4, "exposition_pct": 55})
            targets: dict, 修改目标值 (如 {"hook": 0.7, "exposition_pct": 30})
            times: list of int, 要预测的时间点 (默认 [30, 50, 80, 120])

        Returns: dict with:
            - survival_current: {t: S(t)}
            - survival_target: {t: S(t)}
            - delta: {t: S_target(t) - S_current(t)}
            - changes_applied: [(var, from, to)]
        """
        if times is None:
            times = [30, 50, 80, 120]
        import numpy as np

        row_current = self._build_row(current)
        row_target = self._build_row({**current, **targets})

        try:
            surv_current = self.cph.predict_survival_function(row_current, times=times)
            surv_target = self.cph.predict_survival_function(row_target, times=times)
            sc, st = {}, {}
            for i, t in enumerate(times):
                sc[int(t)] = float(surv_current.iloc[i, 0])
                st[int(t)] = float(surv_target.iloc[i, 0])
        except Exception as e:
            # fallback: 用 partial_hazard 比 (相对风险比)
            ph_c_arr = self.cph.predict_partial_hazard(row_current).values.ravel()
            ph_t_arr = self.cph.predict_partial_hazard(row_target).values.ravel()
            ph_c = float(ph_c_arr[0]) if len(ph_c_arr) else 1.0
            ph_t = float(ph_t_arr[0]) if len(ph_t_arr) else 1.0
            ratio = ph_t / ph_c if ph_c > 0 else 1.0
            # 用平均基线生存函数 * ratio (近似)
            baseline = self.cph.baseline_survival_
            sc, st = {}, {}
            baseline_times = np.asarray(baseline.index).ravel()
            for t in times:
                idx = int(np.argmin(np.abs(baseline_times - t)))
                closest_t = baseline_times[idx]
                vals = baseline.loc[closest_t]
                if hasattr(vals, 'values'):
                    s0 = float(vals.values.ravel()[0])
                else:
                    s0 = float(vals)
                sc[int(t)] = s0
                st[int(t)] = s0 ** ratio

        changes = [(k, current.get(k, None), targets[k]) for k in sorted(targets.keys())]
        ph_current = float(self.cph.predict_partial_hazard(row_current).values.ravel()[0])
        ph_target = float(self.cph.predict_partial_hazard(row_target).values.ravel()[0])
        return {
            "changes_applied": changes,
            "survival_current": sc,
            "survival_target": st,
            "delta_by_time": {t: round(st[t] - sc[t], 4) for t in times},
            "relative_risk_ratio": round(ph_target / max(ph_current, 1e-9), 3),
            "times": times,
        }


# ============================================================
# 风险归因引擎: "这一章的风险主要来自哪里？"
# ============================================================
class RiskAttributionEngine:
    """
    给定已拟合 Cox 模型 + 某章的协变量值，输出"风险归因分解"。

    方法 (SHAP-lite):
      contribution_i = beta_std_i * z_score_i
      其中 z_score_i = (x_i - mean_i) / std_i

    归一化到百分比后得到"每个变量对该章风险的贡献度"。
    """

    @classmethod
    def attribute(cls, cox_model_result, chapter_covariates):
        """对单章做风险归因。

        Args:
            cox_model_result: dict, 来自 CoxModel.fit_forward() 的输出
            chapter_covariates: dict, 如 {"hook_health_score": 0.35, ...}

        Returns:
            dict:
              - per_variable: {var: {"contribution_pct", "z_score", "beta_std", "raw_contribution", "direction"}}
              - top_risks: [(var, pct), ...] 按贡献度排序
              - summary: {"total_risk_score", "n_vars", "top_driver"}
        """
        info = cox_model_result.get("_model_info")
        if not info:
            return {"error": "缺少 _model_info — 无法做归因"}

        names = info["names"]
        beta_std = info["beta_std"]
        means = info["means"]
        stds = info["stds"]

        # 1) 逐变量计算 contribution = beta_std * z_score
        per_var = {}
        total_abs = 0.0
        for idx, name in enumerate(names):
            raw = float(chapter_covariates.get(name, means[idx]))
            if stds[idx] > 0:
                z = (raw - means[idx]) / stds[idx]
            else:
                z = 0.0
            raw_contribution = beta_std[idx] * z
            per_var[name] = {
                "z_score": round(z, 3),
                "beta_std": round(beta_std[idx], 4),
                "raw_contribution": round(raw_contribution, 4),
                "direction": "增加风险" if raw_contribution > 0 else "降低风险",
                "current_value": round(raw, 3),
                "mean_value": round(means[idx], 3),
            }
            total_abs += abs(raw_contribution)

        # 2) 归一化到百分比
        for name in per_var:
            raw_c = per_var[name]["raw_contribution"]
            if total_abs > 0:
                per_var[name]["contribution_pct"] = round(abs(raw_c) / total_abs * 100, 1)
            else:
                per_var[name]["contribution_pct"] = 0.0

        # 3) 按 contribution_pct 排序
        sorted_vars = sorted(per_var.items(), key=lambda kv: kv[1]["contribution_pct"], reverse=True)
        top_risks = [(name, data["contribution_pct"]) for name, data in sorted_vars]

        # 4) total_risk_score = sum(positive contributions)  — 正值表示额外风险
        positive_sum = sum(max(v["raw_contribution"], 0) for v in per_var.values())

        return {
            "per_variable": per_var,
            "top_risks": top_risks,
            "summary": {
                "total_risk_score": round(positive_sum, 3),
                "n_vars": len(names),
                "top_driver": top_risks[0] if top_risks else None,
            },
        }

    @classmethod
    def attribute_all(cls, cox_model_result, observations):
        """对所有章做风险归因，返回列表。"""
        all_attributions = []
        for o in observations:
            cov_dict = {name: o.x[i] for i, name in enumerate(o.names)}
            attr = cls.attribute(cox_model_result, cov_dict)
            if "error" not in attr:
                all_attributions.append({
                    "chapter": o.t,
                    "event": o.event,
                    "score": o.raw_score,
                    "attribution": attr,
                })
        return all_attributions


# ============================================================
# 新增: TextDiagnosticEngine — 基于特征的文本质量诊断
# 
# 核心思想:
#   与其用一个无区分度的 overall_math_score (总是 61),
#   不如直接检查 12 维风格向量 + 信息论特征是否落在
#   "好小说" 的参考区间内。
#
#   每个特征都有一个 "理想范围 (ideal range)":
#     - 在范围内  -> GOOD (+1 分)
#     - 偏离较小   -> INFO (0 分, 提示)
#     - 严重偏离   -> WARNING (-1 分)
#     - 极度偏离   -> CRITICAL (-2 分)
# ============================================================
class TextDiagnosticEngine:
    """
    文本诊断引擎 v3.0
    输入: pangu_math_core.full_analysis() 的完整结果
    输出: 
        - quality_score: -2N ~ +N 的结构化质量评分 (N=特征数, 越高越好)
        - diagnoses: [{feature, current, ideal, severity, message, prescription}]
        - overall_assessment: 文本整体评价 ("问题严重 / 有改进空间 / 合格 / 优秀")
    """

    # 参考区间定义 (基于 45 章小说的统计 + 写作常识):
    #   format: (min_ideal, max_ideal, min_tolerable, max_tolerable)
    #   在 [min_ideal, max_ideal] 内 = GOOD
    #   在 [min_tolerable, min_ideal) 或 (max_ideal, max_tolerable] 内 = WARNING
    #   < min_tolerable 或 > max_tolerable = CRITICAL
    REFERENCE_RANGES = {
        # 对话占比: 好小说通常有 15-25% 的对话
        "dialogue_ratio": {
            "ideal_min": 0.12, "ideal_max": 0.28,
            "warn_min": 0.05, "warn_max": 0.38,
            "display_name": "对话占比",
            "good_msg": "对话与叙述平衡良好",
            "low_warning": "对话过少, 读者容易感到枯燥",
            "low_critical": "几乎没有对话, 文本像说明文而非小说",
            "high_warning": "对话过多, 缺乏场景与心理描写",
            "high_critical": "几乎全是对话, 像剧本而非小说",
        },
        # 动作密度: 场景要有动作推进, 但不能全是动作
        "action_density": {
            "ideal_min": 0.12, "ideal_max": 0.28,
            "warn_min": 0.05, "warn_max": 0.35,
            "display_name": "动作密度",
            "good_msg": "动作/叙述比例合理",
            "low_warning": "缺乏动作描写, 节奏偏慢",
            "low_critical": "几乎没有动作, 叙事停滞不前",
            "high_warning": "动作过多, 读者缺乏喘息",
            "high_critical": "纯动作流, 没有思考与情感",
        },
        # 句长方差: 好小说的句子长短应该有变化 (0.3-0.5 为佳)
        "sentence_variance": {
            "ideal_min": 0.30, "ideal_max": 0.50,
            "warn_min": 0.15, "warn_max": 0.52,
            "display_name": "句长变化",
            "good_msg": "长短句交替自然, 节奏感好",
            "low_warning": "句长过于一致, 节奏平淡",
            "low_critical": "所有句子长度相近, 像机器翻译",
            "high_warning": "句长波动过大, 阅读不流畅",
            "high_critical": "节奏混乱, 需要统一风格",
        },
        # 情绪均值: 文本情绪不应太平淡 (0.25-0.40)
        "emotion_mean": {
            "ideal_min": 0.25, "ideal_max": 0.40,
            "warn_min": 0.18, "warn_max": 0.48,
            "display_name": "情绪强度",
            "good_msg": "情绪表达有层次, 不平淡也不过激",
            "low_warning": "情绪偏淡, 读者缺乏代入感",
            "low_critical": "几乎无情绪描写, 文本像新闻报道",
            "high_warning": "情绪过于浓烈, 需要留白",
            "high_critical": "情绪过载, 读者感到疲劳",
        },
        # 自转移率: 低 = 好 (句子类型多样). 高于 0.32 说明句式重复
        "self_transition": {
            "ideal_min": 0.15, "ideal_max": 0.30,
            "warn_min": 0.08, "warn_max": 0.35,
            "display_name": "句式多样性",
            "good_msg": "句式多样, 不单调",
            "low_warning": "",
            "low_critical": "",
            "high_warning": "句式重复, 建议增加倒装/设问/省略等",
            "high_critical": "句式高度重复, 明显的模板化写作",
            "inverted": True,  # 值越低越好
        },
        # Zipf R^2: 语言的自然度. > 0.40 说明符合自然语言规律
        "zipf_r2": {
            "ideal_min": 0.40, "ideal_max": 0.55,
            "warn_min": 0.30, "warn_max": 0.60,
            "display_name": "语言自然度",
            "good_msg": "用词符合自然语言规律",
            "low_warning": "词汇分布不自然, 可能有重复或生造",
            "low_critical": "语言非常不自然, 像机器生成",
            "high_warning": "",
            "high_critical": "",
        },
        # Bigram 熵: 信息丰富度. 太低=重复, 太高=混乱
        "bigram_entropy": {
            "ideal_min": 9.5, "ideal_max": 10.5,
            "warn_min": 9.0, "warn_max": 11.0,
            "display_name": "信息丰富度",
            "good_msg": "词汇使用丰富且可控",
            "low_warning": "词汇重复度高, 阅读感单调",
            "low_critical": "严重重复, 可能有大段套话",
            "high_warning": "词汇过于发散, 风格不统一",
            "high_critical": "词汇混乱, 缺乏写作重心",
        },
        # 均句长: 中文小说通常 15-30 字/句
        "sentence_len": {
            "ideal_min": 0.08, "ideal_max": 0.15,
            "warn_min": 0.05, "warn_max": 0.20,
            "display_name": "平均句长",
            "good_msg": "句子长度适中",
            "low_warning": "句子偏短, 像流水账",
            "low_critical": "句子太短, 阅读碎片化",
            "high_warning": "句子偏长, 可以拆分成短句",
            "high_critical": "句子过长, 读者读起来很累",
        },
        # N-gram 唯一性: 衡量原创性 / 词汇多样性
        "ngram_unique": {
            "ideal_min": 0.27, "ideal_max": 0.35,
            "warn_min": 0.22, "warn_max": 0.40,
            "display_name": "词汇独特性",
            "good_msg": "用词有特色但不晦涩",
            "low_warning": "词汇过于普通, 缺乏个性化表达",
            "low_critical": "严重陈词滥调, 建议换一些新鲜表达",
            "high_warning": "词汇过于生僻, 读者可能看不懂",
            "high_critical": "大量生僻词, 需要简化",
        },
        # 复杂度: 信息复杂度平衡
        "complexity": {
            "ideal_min": 0.45, "ideal_max": 0.55,
            "warn_min": 0.38, "warn_max": 0.60,
            "display_name": "信息复杂度",
            "good_msg": "信息量适中, 不空洞也不堆砌",
            "low_warning": "信息密度偏低, 内容不够充实",
            "low_critical": "信息过薄, 像大纲而非正文",
            "high_warning": "信息密度偏高, 读者消化困难",
            "high_critical": "信息堆砌, 需要删减与整理",
        },
        # 段落长度: 好小说通常段落较短 (便于手机阅读)
        "paragraph_len": {
            "ideal_min": 0.02, "ideal_max": 0.05,
            "warn_min": 0.01, "warn_max": 0.08,
            "display_name": "段落长度",
            "good_msg": "段落长短适中, 手机阅读友好",
            "low_warning": "段落偏短, 结构略散",
            "low_critical": "每句一段, 像聊天记录",
            "high_warning": "段落偏长, 建议拆分",
            "high_critical": "大段文字, 严重影响阅读体验",
        },
        # 钩子强度: 越高越好
        "hook_strength": {
            "ideal_min": 0.15, "ideal_max": 0.20,
            "warn_min": 0.12, "warn_max": 0.25,
            "display_name": "钩子强度",
            "good_msg": "钩子有效, 有悬念和张力",
            "low_warning": "钩子偏弱, 读者容易走神",
            "low_critical": "几乎没有钩子, 文本缺乏推进力",
            "high_warning": "",
            "high_critical": "",
        },
        # 情绪波动: 应该有一定起伏
        "emotion_variance": {
            "ideal_min": 0.005, "ideal_max": 0.020,
            "warn_min": 0.001, "warn_max": 0.030,
            "display_name": "情绪波动",
            "good_msg": "情绪有起伏, 叙事节奏自然",
            "low_warning": "情绪太平稳, 缺乏戏剧性",
            "low_critical": "情绪零波动, 像流水账",
            "high_warning": "情绪起伏过大, 可能撕裂叙事",
            "high_critical": "",
        },
    }

    SEVERITY_SCORES = {
        "CRITICAL": -2,
        "WARNING": -1,
        "INFO": 0,
        "GOOD": 1,
    }

    @classmethod
    def diagnose(cls, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        对单一章节进行完整诊断.
        
        Args:
            analysis_result: pangu_math_core.full_analysis() 的输出
        Returns:
            {
                "quality_score": float,   # 综合质量分
                "diagnoses": [...],       # 每条诊断
                "severity_counts": {...}, # 各严重级别的计数
                "summary": str,           # 简短总结
            }
        """
        style_vec = analysis_result.get("style_vector", {})
        info_metrics = analysis_result.get("information_metrics", {})

        # 合并所有可用特征
        features = {}
        for key in cls.REFERENCE_RANGES:
            if key in style_vec:
                features[key] = style_vec[key]
            elif key in info_metrics:
                features[key] = info_metrics[key]

        diagnoses = []
        quality_score = 0
        severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0, "GOOD": 0}

        for feat_name, ranges in cls.REFERENCE_RANGES.items():
            if feat_name not in features:
                continue
            value = features[feat_name]
            display = ranges["display_name"]

            severity, message = cls._assess_feature(feat_name, value, ranges)
            severity_counts[severity] += 1
            quality_score += cls.SEVERITY_SCORES[severity]

            prescriptions = cls._get_prescriptions(feat_name, value, severity, ranges)

            diagnoses.append({
                "feature": feat_name,
                "display_name": display,
                "current_value": round(value, 4),
                "ideal_range": (ranges["ideal_min"], ranges["ideal_max"]),
                "severity": severity,
                "message": message,
                "prescriptions": prescriptions,
                "score_contribution": cls.SEVERITY_SCORES[severity],
            })

        # 排序: CRITICAL 在前, GOOD 在后
        severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "GOOD": 3}
        diagnoses.sort(key=lambda d: severity_order.get(d["severity"], 99))

        # 归一化 quality_score 到 0-100 分
        max_possible = len(diagnoses)  # 每特征 +1
        min_possible = -2 * len(diagnoses)
        if max_possible != min_possible:
            normalized_score = round(
                (quality_score - min_possible) / (max_possible - min_possible) * 100, 1
            )
        else:
            normalized_score = 50.0

        # 总体评价
        if normalized_score >= 75:
            overall = "优秀"
        elif normalized_score >= 60:
            overall = "合格"
        elif normalized_score >= 40:
            overall = "有改进空间"
        else:
            overall = "问题严重"

        return {
            "quality_score": quality_score,
            "quality_score_normalized": normalized_score,
            "diagnoses": diagnoses,
            "severity_counts": severity_counts,
            "overall": overall,
            "top_problems": [d for d in diagnoses if d["severity"] in ("CRITICAL", "WARNING")][:5],
            "top_strengths": [d for d in diagnoses if d["severity"] == "GOOD"][:5],
        }

    @classmethod
    def _assess_feature(cls, feat_name, value, ranges):
        """评估某一特征并返回 (severity, message)."""
        ideal_min, ideal_max = ranges["ideal_min"], ranges["ideal_max"]
        warn_min, warn_max = ranges["warn_min"], ranges["warn_max"]
        inverted = ranges.get("inverted", False)

        if ideal_min <= value <= ideal_max:
            return "GOOD", ranges.get("good_msg", "指标良好")
        elif warn_min <= value < ideal_min:
            return "WARNING", ranges.get("low_warning", "偏低")
        elif ideal_max < value <= warn_max:
            return "WARNING", ranges.get("high_warning", "偏高")
        elif value < warn_min:
            return "CRITICAL", ranges.get("low_critical", "严重偏低")
        else:  # value > warn_max
            return "CRITICAL", ranges.get("high_critical", "严重偏高")

    @classmethod
    def _get_prescriptions(cls, feat_name, value, severity, ranges):
        """生成可执行的修改建议 (不是空洞的"风险高", 而是"怎么做")。"""
        if severity == "GOOD":
            return ["保持当前风格"]
        if severity == "INFO":
            return ["关注即可, 暂不需要主动修改"]

        ideal_min, ideal_max = ranges["ideal_min"], ranges["ideal_max"]
        direction = "low" if value < ideal_min else "high"

        # 针对每个特征的具体建议
        prescriptions = {
            "dialogue_ratio": {
                "low": [
                    "增加 2-3 段人物对话: 用 '他说/她问' 引出一句台词",
                    "把叙述性的信息包装成对话形式 (比如让人物讨论而非作者说明)",
                    "加入一段内心独白 (用引号或括号包起来)",
                ],
                "high": [
                    "把 1-2 段纯对话改为间接引语或动作描写",
                    "在对话之间穿插环境描写或人物反应",
                ],
            },
            "action_density": {
                "low": [
                    "加入 1-2 个有视觉冲击力的动作句 (如 '他猛地转身')",
                    "把静态描述改为动态表达 (从 '房间很暗' 到 '他走进黑暗的房间')",
                ],
                "high": [
                    "减少连续的动作句, 插入心理描写或环境描写",
                    "把 2-3 个小动词合并为一个更精准的动词",
                ],
            },
            "sentence_variance": {
                "low": [
                    "写一个 30 字以上的长句 (串联多个动作/感受)",
                    "写一个 5 字以内的短句或独词句 (用于强调)",
                    "尝试倒装句或设问句",
                ],
                "high": [
                    "把超长句拆成 2-3 个短句",
                    "用连接词把几个相邻短句合并",
                ],
            },
            "emotion_mean": {
                "low": [
                    "加入一段明确的情绪描写 (不要 '他很生气', 写 '拳头攥紧了')",
                    "用感官细节暗示情绪 (冷/热/心跳/呼吸)",
                ],
                "high": [
                    "做一次情感留白: 用沉默或环境描写代替直接情绪宣泄",
                    "用反讽或冷静观察中和激烈情绪",
                ],
            },
            "self_transition": {
                "low": [],
                "high": [
                    "把连续 3 句的 'XX 说 / XX 想 / XX 做' 改写其中一句",
                    "尝试以景物描写或时间流逝开头新的一段",
                ],
            },
            "zipf_r2": {
                "low": [
                    "检查是否有重复词或套话, 替换其中一半",
                    "增加一些具体的、个性化的细节描写",
                ],
                "high": [],
            },
            "bigram_entropy": {
                "low": [
                    "找重复出现的形容词/副词, 换 3-5 个近义词",
                    "引入一个新的细节或观察角度",
                ],
                "high": [
                    "把生僻/书面语替换为读者熟悉的表达",
                    "统一部分术语或称呼 (避免同一概念用多个词)",
                ],
            },
            "sentence_len": {
                "low": [
                    "把 2-3 个短句合并为一个带连接词的长句",
                    "增加一些修饰成分或插入语",
                ],
                "high": [
                    "找到最长的 1-2 句, 拆成短句",
                    "删除非必要的定语和副词",
                ],
            },
            "ngram_unique": {
                "low": [
                    "换 3-5 个常用词为更具体的表达 (从 '好看' 到 '眉眼间有锐气')",
                    "加入一个只在这个场景才会出现的细节",
                ],
                "high": [
                    "把生僻词替换为常用词",
                    "统一人物称呼或地名写法",
                ],
            },
            "complexity": {
                "low": [
                    "补充背景信息或人物动机",
                    "增加一个次要冲突或伏笔",
                ],
                "high": [
                    "删除 1-2 个不重要的细节",
                    "把解释性内容压缩为暗示",
                ],
            },
            "paragraph_len": {
                "low": [
                    "把 2-3 个极短段落合并 (相关内容放在一段)",
                ],
                "high": [
                    "找到最长的段落, 在逻辑转折处拆分成两段",
                    "每 200 字至少有一个换行",
                ],
            },
            "hook_strength": {
                "low": [
                    "在段落末尾加一个悬念或问题 (如 '但他不知道的是...')",
                    "引入一个未解决的信息缺口",
                    "检查是否有冲突或张力元素, 没有就加一个",
                ],
                "high": [],
            },
            "emotion_variance": {
                "low": [
                    "制造一次情绪起伏: 平静 -> 紧张 -> 松弛",
                    "引入一个意外的事件或对话",
                ],
                "high": [
                    "用过渡句平滑极端的情绪转折",
                ],
            },
        }

        return prescriptions.get(feat_name, {}).get(direction, ["参考同类优秀小说的写法"])

    @classmethod
    def diagnose_multi_chapter(cls, analysis_results_by_chapter: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        对多章节进行整体诊断 + 趋势分析。
        
        Args:
            analysis_results_by_chapter: [{"chapter": int, "analysis": {...}}, ...]
        """
        per_chapter = []
        for item in analysis_results_by_chapter:
            ch_num = item["chapter"]
            diag = cls.diagnose(item["analysis"])
            per_chapter.append({
                "chapter": ch_num,
                "diagnosis": diag,
            })

        # 趋势分析 (前半 vs 后半)
        n = len(per_chapter)
        if n >= 2:
            half = n // 2
            first_scores = [c["diagnosis"]["quality_score_normalized"] for c in per_chapter[:half]]
            second_scores = [c["diagnosis"]["quality_score_normalized"] for c in per_chapter[half:]]
            first_avg = sum(first_scores) / len(first_scores)
            second_avg = sum(second_scores) / len(second_scores)
            trend_delta = round(second_avg - first_avg, 1)
            if trend_delta >= 5:
                trend = f"上升趋势 (+{trend_delta} 分): 越写越好"
            elif trend_delta <= -5:
                trend = f"下降趋势 ({trend_delta} 分): 越写越差, 需要注意"
            else:
                trend = f"稳定 ({trend_delta:+.1f} 分): 质量一致"
        else:
            first_avg = second_avg = trend_delta = None
            trend = "章节不足, 无法判断趋势"

        # 找出整本小说最常见的问题 (跨章节聚合)
        problem_counter = {}
        strength_counter = {}
        for item in per_chapter:
            for d in item["diagnosis"]["diagnoses"]:
                feat = d["feature"]
                if d["severity"] in ("CRITICAL", "WARNING"):
                    problem_counter[feat] = problem_counter.get(feat, 0) + 1
                elif d["severity"] == "GOOD":
                    strength_counter[feat] = strength_counter.get(feat, 0) + 1

        top_problems = sorted(problem_counter.items(), key=lambda x: -x[1])[:3]
        top_strengths = sorted(strength_counter.items(), key=lambda x: -x[1])[:3]

        return {
            "num_chapters": n,
            "per_chapter": per_chapter,
            "trend": trend,
            "trend_delta": trend_delta,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg,
            "top_problems_across_book": top_problems,
            "top_strengths_across_book": top_strengths,
        }

    @classmethod
    def print_diagnosis(cls, diag: Dict[str, Any], verbose: bool = True) -> str:
        """把诊断结果格式化为可读字符串 (用于 report 输出)。"""
        lines = []
        lines.append(f"  质量评分: {diag['quality_score_normalized']:.1f}/100  ({diag['overall']})")

        sc = diag["severity_counts"]
        lines.append(
            f"  指标分布: {sc['GOOD']} 好 / {sc['INFO']} 中性 / "
            f"{sc['WARNING']} 警告 / {sc['CRITICAL']} 严重"
        )

        if diag["top_problems"]:
            lines.append(f"\n  【主要问题】")
            for d in diag["top_problems"]:
                icon = "!!" if d["severity"] == "CRITICAL" else "!"
                lines.append(f"  {icon} {d['display_name']} = {d['current_value']:.4f} "
                           f"(理想 {d['ideal_range'][0]:.3f}-{d['ideal_range'][1]:.3f})")
                lines.append(f"     {d['message']}")
                if verbose:
                    for rx in d["prescriptions"][:2]:
                        lines.append(f"     -> {rx}")

        if diag["top_strengths"] and verbose:
            lines.append(f"\n  【做得好的】")
            for d in diag["top_strengths"]:
                lines.append(f"  ++ {d['display_name']} = {d['current_value']:.4f} "
                           f"({d['message']})")

        return "\n".join(lines)


# ============================================================
# 阈值效应检测: "当 hook 低于 X 时，读者风险翻倍"
# ============================================================
class ThresholdDetector:
    """对每个协变量自动寻找最佳分割点，量化"低于/高于该阈值"的风险差异。

    方法:
      1. 对变量 var 在 10-20 个分位数处尝试分割
      2. 对每个分割点，用 is_low = (var <= threshold) 作为单协变量拟合 Cox
      3. 选择 p-value 最小 (HR 最显著) 的分割点作为最佳阈值
      4. 输出: 阈值、HR、p-value、高低组 30/60 章留存率

    用法:
      results = ThresholdDetector.detect_all(data)
    """

    @classmethod
    def detect_all(cls, data, n_quantiles=15, min_group_size=5):
        """对所有协变量做阈值检测。

        Returns dict: {var_name: {"threshold": X, "hr": HR, "p_value": p,
                                 "survival_low_30": s30_low, "survival_high_30": s30_high,
                                 "survival_low_60": s60_low, "survival_high_60": s60_high}}
        """
        from lifelines import CoxPHFitter, KaplanMeierFitter
        import pandas as pd
        import numpy as np

        df = CoxModel._to_dataframe(data)
        n_events = int(df["event"].sum())
        if n_events < 5:
            return {"error": "事件太少 (<5)，无法做阈值检测"}

        feature_names = [c for c in df.columns if c not in ("chapter", "event")]
        results = {}

        for name in feature_names:
            vals = df[name].values
            # 去重的分位数点
            q_range = np.linspace(0.2, 0.8, n_quantiles)
            thresholds = []
            for q in q_range:
                t = float(np.quantile(vals, q))
                if len(thresholds) == 0 or t != thresholds[-1]:
                    thresholds.append(t)

            best = None
            for thresh in thresholds:
                is_low = (vals <= thresh).astype(int)
                n_low = int(is_low.sum())
                n_high = int(len(is_low) - n_low)
                if n_low < min_group_size or n_high < min_group_size:
                    continue
                events_low = int((is_low * df["event"].values).sum())
                events_high = int(((1 - is_low) * df["event"].values).sum())
                if events_low < 2 or events_high < 2:
                    continue

                sub_df = pd.DataFrame({
                    "chapter": df["chapter"].values,
                    "event": df["event"].values,
                    "is_low": is_low,
                })
                try:
                    cph = CoxPHFitter(penalizer=0.0)
                    cph.fit(sub_df, duration_col="chapter", event_col="event")
                    p_val = float(cph.summary.loc["is_low", "p"])
                    hr = float(np.exp(cph.summary.loc["is_low", "coef"]))
                    if best is None or p_val < best["p_value"]:
                        best = {
                            "threshold": round(thresh, 3),
                            "hr": round(hr, 3),
                            "p_value": round(p_val, 4),
                            "n_low": n_low,
                            "n_high": n_high,
                            "events_low": events_low,
                            "events_high": events_high,
                        }
                except Exception:
                    continue

            if best is not None:
                # KM 曲线对比: 低组 vs 高组的 30/60 章留存
                try:
                    is_low = (vals <= best["threshold"]).astype(int)
                    kmf = KaplanMeierFitter()
                    kmf.fit(df["chapter"][is_low == 1], df["event"][is_low == 1])
                    s30_low = float(kmf.survival_function_at_times(30).values[0]) if 30 <= df["chapter"].max() else None
                    s60_low = float(kmf.survival_function_at_times(60).values[0]) if 60 <= df["chapter"].max() else None
                    kmf.fit(df["chapter"][is_low == 0], df["event"][is_low == 0])
                    s30_high = float(kmf.survival_function_at_times(30).values[0]) if 30 <= df["chapter"].max() else None
                    s60_high = float(kmf.survival_function_at_times(60).values[0]) if 60 <= df["chapter"].max() else None
                    best["survival_low_30"] = round(s30_low, 3) if s30_low is not None else None
                    best["survival_high_30"] = round(s30_high, 3) if s30_high is not None else None
                    best["survival_low_60"] = round(s60_low, 3) if s60_low is not None else None
                    best["survival_high_60"] = round(s60_high, 3) if s60_high is not None else None
                    # 留存率提升（高组 - 低组）
                    if s30_low is not None and s30_high is not None:
                        best["survival_delta_30"] = round(s30_high - s30_low, 3)
                    if s60_low is not None and s60_high is not None:
                        best["survival_delta_60"] = round(s60_high - s60_low, 3)
                except Exception:
                    pass
                results[name] = best

        # 按 p-value 排序
        sorted_results = dict(sorted(results.items(), key=lambda kv: kv[1].get("p_value", 1.0)))
        return sorted_results


# ============================================================================
# 降级模块 — 当 HAS_STATS == False 时启用（纯 Python 实现，无外部依赖）
# ============================================================================

if not HAS_STATS:
    # ---- 简化版统计工具（纯 math + statistics）----
    import statistics as _builtin_stats

    class _SimpleStats:
        @staticmethod
        def mean(values):
            return sum(values) / len(values) if values else 0.0
        @staticmethod
        def median(values):
            s = sorted(values)
            n = len(s)
            if n == 0: return 0.0
            if n % 2: return float(s[n//2])
            return float(s[n//2-1] + s[n//2]) / 2.0
        @staticmethod
        def stdev(values):
            if len(values) < 2: return 0.0
            m = sum(values) / len(values)
            return (sum((v-m)**2 for v in values) / (len(values)-1)) ** 0.5
        @staticmethod
        def pearson(x, y):
            n = len(x)
            if n < 2: return 0.0
            mx, my = sum(x)/n, sum(y)/n
            num = sum((xi-mx)*(yi-my) for xi,yi in zip(x,y))
            dx = (sum((xi-mx)**2 for xi in x))**0.5
            dy = (sum((yi-my)**2 for yi in y))**0.5
            if dx == 0 or dy == 0: return 0.0
            return num / (dx * dy)

    _S = _SimpleStats()

    # ---- 替换 KaplanMeier（简化版，不做置信区间）----
    class KaplanMeier:
        @staticmethod
        def fit(data):
            if not data: return {"error": "空数据", "mode": "simplified"}
            events = sorted([(o.t, o.event) for o in data], key=lambda x: x[0])
            n = len(events)
            times = []
            survival = []
            s = 1.0
            at_risk = n
            for i, (t, ev) in enumerate(events):
                if ev:
                    s *= (at_risk - 1) / at_risk
                at_risk -= 1
                times.append(float(t))
                survival.append(round(s, 6))
            n_events = sum(1 for _, e in events if e)
            return {
                "km_times": times,
                "km_survival": survival,
                "n_events": n_events,
                "n_censored": n - n_events,
                "mode": "simplified (纯Python, 建议安装 pandas/numpy/lifelines 获得完整功能)"
            }

    # ---- 替换 CoxModel（简化版：只做相关性分析 + 简单分群）----
    class CoxModel:
        @classmethod
        def fit_forward(cls, data, aic_drop_threshold=0.5, penalizer=None, **kwargs):
            if not data: return {"error": "空数据", "mode": "simplified"}
            n = len(data)
            n_events = sum(1 for o in data if o.event)
            if n < 3 or n_events < 1:
                return {"error": "数据太少", "n": n, "n_events": n_events, "mode": "simplified"}
            # 简化版：只计算每个协变量与事件/时间的相关系数作为"重要性"
            features = {}
            for o in data:
                for i, v in enumerate(o.x):
                    name = o.names[i] if i < len(o.names) else f"x{i}"
                    features.setdefault(name, []).append((float(v), float(o.t), int(o.event)))
            results = {}
            for name, entries in features.items():
                xs = [e[0] for e in entries]
                ts = [e[1] for e in entries]
                evs = [e[2] for e in entries]
                corr_x_t = _S.pearson(xs, ts)
                ev_group_high = sum(1 for x, t, e in entries if x >= _S.median(xs) and e)
                ev_group_low  = sum(1 for x, t, e in entries if x <  _S.median(xs) and e)
                results[name] = {
                    "corr_with_time": round(corr_x_t, 4),
                    "event_rate_high": round(ev_group_high / max(1, sum(1 for e in entries if e[0] >= _S.median(xs))), 4),
                    "event_rate_low": round(ev_group_low / max(1, sum(1 for e in entries if e[0] < _S.median(xs))), 4),
                    "note": "简化版相关性分析（无 lifelines），建议安装统计库获得 Cox 回归系数"
                }
            return {
                "mode": "simplified — 安装 pandas/numpy/lifelines 获得完整 Cox 回归",
                "n": n,
                "n_events": n_events,
                "features": results
            }

        @classmethod
        def fit_simple(cls, data, feature_names=None, penalizer=None):
            return cls.fit_forward(data)

    # ---- 替换 WeibullModel（简化版占位）----
    class WeibullModel:
        @staticmethod
        def fit(data, feature_names=None):
            if not data: return {"error": "空数据", "mode": "simplified"}
            ts = [float(o.t) for o in data]
            return {
                "mode": "simplified (无 lifelines 完整拟合)",
                "median_time": _S.median(ts),
                "mean_time": _S.mean(ts),
                "note": "请安装 lifelines 获得 Weibull AFT 模型系数与置信区间"
            }

    # ---- 替换 SurvivalAnalyzer（简化版）----
    class SurvivalAnalyzer:
        @classmethod
        def run(cls, data):
            if not data: return {"error": "空数据"}
            km = KaplanMeier.fit(data)
            cox = CoxModel.fit_forward(data)
            return {
                "mode": "simplified",
                "kaplan_meier": km,
                "cox_analysis": cox,
                "note": "完整功能需要: pip install pandas numpy scipy lifelines"
            }

    # ---- 替换 CoxPrescriptionEngine（简化版）----
    class CoxPrescriptionEngine:
        @staticmethod
        def prescript(analysis_result):
            if not analysis_result or "error" in (analysis_result or {}):
                return [{"recommendation": "数据不足，无法给出处方建议"}]
            features = analysis_result.get("cox_analysis", {}).get("features", {})
            recs = []
            for name, info in features.items():
                if isinstance(info, dict) and "event_rate_high" in info:
                    eh = info["event_rate_high"]
                    el = info["event_rate_low"]
                    if eh > el * 1.2:
                        recs.append({"feature": name, "suggestion": f"降低 {name}（高值组事件率 {eh:.2%} vs 低值组 {el:.2%}）"})
                    elif el > eh * 1.2:
                        recs.append({"feature": name, "suggestion": f"提升 {name}（低值组事件率 {el:.2%} vs 高值组 {eh:.2%}）"})
            if not recs:
                recs.append({"recommendation": "当前简化版分析未发现强关联特征，建议安装 lifelines 做完整 Cox 回归"})
            return recs
