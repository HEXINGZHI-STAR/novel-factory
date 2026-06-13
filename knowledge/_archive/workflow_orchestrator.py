#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI呼吸系统 — 工作流编排引擎
=================================
模拟组织行为学中的跨部门协作流程：
方案构建 → 策划 → 审核 → 评估 → 决策 → 实施 → 反馈循环

每个阶段是一个"部门"，有明确的输入/输出契约。
部门之间通过编排器(Orchestrator)进行信息沟通和监督。
失败的阶段触发反馈循环回到上游。

设计原则:
- 每个阶段必须显式声明决策: PASS / REVISE / REJECT
- REVISE触发回滚到指定上游阶段
- 全流程产生审计轨迹(audit_trail)
- 最终决策基于所有阶段的加权投票
"""

import math
import json
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ============================================================
# 决策枚举
# ============================================================

class Verdict(str, Enum):
    PASS   = "PASS"     # 通过，进入下一阶段
    REVISE = "REVISE"   # 需要修改，回滚到指定阶段
    REJECT = "REJECT"   # 彻底否决，终止流程
    SKIP   = "SKIP"     # 跳过（条件不满足）


class StageID(str, Enum):
    """工作流阶段标识"""
    INTAKE       = "intake"        # 接收输入
    PLANNING     = "planning"      # 方案构建
    STRATEGY     = "strategy"      # 策划（创作引擎）
    QUALITY      = "quality"       # 审核（静态质量检查）
    DYNAMIC      = "dynamic"       # 评估（动态评分）
    MATH         = "math"          # 评估（数学引擎）
    STATISTICS   = "statistics"    # 评估（医学统计）
    STYLE        = "style"         # 审核（风格指纹）
    DECISION     = "decision"      # 决策
    EXECUTION    = "execution"     # 实施（生成指引）
    COMPLETE     = "complete"      # 完成


# ============================================================
# 数据结构
# ============================================================

@dataclass
class StageReport:
    """单个阶段的执行报告"""
    stage: StageID
    verdict: Verdict
    score: float = 0.0           # 0-100
    confidence: float = 0.0      # 0-1
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    rollback_to: Optional[StageID] = None  # REVISE时回滚目标
    duration_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def summary(self) -> str:
        icon = {"PASS": "[OK]", "REVISE": "[RW]", "REJECT": "[XX]", "SKIP": "[--]"}.get(self.verdict.value, "[?]")
        return f"{icon} {self.stage.value:12s} | score={self.score:5.1f} | {self.verdict.value}"


@dataclass
class WorkflowContext:
    """在整个工作流中流动的上下文信息"""
    # 输入
    text: str = ""
    chapter_num: int = 1
    platform: str = "qimao"
    genre: str = "unknown"
    mode: str = "general"
    project_name: str = ""

    # 中间产物（各阶段填充）
    chapter_history: List[str] = field(default_factory=list)  # 前几章文本
    planning_result: Dict = field(default_factory=dict)
    strategy_result: Dict = field(default_factory=dict)
    quality_result: Dict = field(default_factory=dict)
    dynamic_result: Dict = field(default_factory=dict)
    math_result: Dict = field(default_factory=dict)
    statistics_result: Dict = field(default_factory=dict)
    style_result: Dict = field(default_factory=dict)
    decision_result: Dict = field(default_factory=dict)
    execution_result: Dict = field(default_factory=dict)

    # 元信息
    revision_round: int = 0
    max_revisions: int = 3


@dataclass 
class WorkflowResult:
    """整个工作流的最终结果"""
    passed: bool = False
    final_score: float = 0.0
    audit_trail: List[StageReport] = field(default_factory=list)
    guidance: str = ""
    revision_count: int = 0
    total_duration_ms: float = 0.0
    bottleneck_stage: str = ""

    def summary(self) -> str:
        lines = [f"\n{'='*60}"]
        lines.append(f"  盘古AI呼吸系统 — 工作流报告")
        lines.append(f"{'='*60}")
        for report in self.audit_trail:
            lines.append(f"  {report.summary()}")
        lines.append(f"{'='*60}")
        lines.append(f"  最终决策: {'通过' if self.passed else '未通过'}  |  综合评分: {self.final_score:.1f}/100")
        lines.append(f"  修订次数: {self.revision_count}  |  耗时: {self.total_duration_ms:.0f}ms")
        if self.bottleneck_stage:
            lines.append(f"  瓶颈阶段: {self.bottleneck_stage}")
        return "\n".join(lines)


# ============================================================
# 工作流编排器 — 呼吸系统核心
# ============================================================

class BreathingOrchestrator:
    """
    呼吸系统核心编排器。
    
    模拟组织行为:
    - 每个阶段是一个"部门"，独立决策但通过编排器沟通
    - 阶段之间的信息流是双向的（下游可以反馈给上游）
    - 决策不是单点判断，而是多阶段加权投票
    - 失败不终止，而是回滚重试（像呼吸一样有吸有呼）
    
    呼吸节奏:
    - 吸气(INHALE): 收集信息 → planning + strategy
    - 评估(HOLD):  分析质量 → quality + dynamic + math + statistics + style  
    - 呼气(EXHALE): 输出决策 → decision + execution
    - 反馈(FEEDBACK): 如果失败，回滚后重新吸气
    """

    def __init__(self):
        # 确保所有同级模块可导入
        import os, sys
        _knowledge_dir = os.path.dirname(os.path.abspath(__file__))
        if _knowledge_dir not in sys.path:
            sys.path.insert(0, _knowledge_dir)
        
        # 阶段权重（不同平台侧重点不同）
        self.stage_weights = {
            StageID.QUALITY:    0.15,
            StageID.DYNAMIC:    0.20,
            StageID.MATH:       0.25,
            StageID.STATISTICS: 0.20,
            StageID.STYLE:      0.10,
            StageID.STRATEGY:   0.10,
        }
        
        # 平台特定的权重调整
        self.platform_weights = {
            "qimao":   {StageID.DYNAMIC: 0.25, StageID.MATH: 0.20, StageID.QUALITY: 0.15},  # 七猫重情绪节奏
            "fanqie":  {StageID.DYNAMIC: 0.30, StageID.QUALITY: 0.20, StageID.MATH: 0.15},   # 番茄重开篇冲击
            "qidian":  {StageID.MATH: 0.30, StageID.STYLE: 0.15, StageID.STATISTICS: 0.20},  # 起点重深度
        }

        # 通过阈值
        self.pass_thresholds = {
            StageID.QUALITY: 60,
            StageID.DYNAMIC: 55,
            StageID.MATH: 50,
            StageID.STATISTICS: 50,
            StageID.STYLE: 50,
            StageID.STRATEGY: 60,
        }

    def breathe(self, ctx: WorkflowContext) -> WorkflowResult:
        """
        启动一个完整的"呼吸"周期。
        
        所有阶段依次执行，每个阶段都能看到前面阶段的结果（信息沟通）。
        REVISE不阻塞下游，只在审计轨迹中标记。
        最终由DECISION阶段汇总各部门意见做判决。
        """
        start_time = time.time()
        audit: List[StageReport] = []

        # 定义管道（全部执行）
        pipeline = [
            self._stage_intake,
            self._stage_planning,
            self._stage_strategy,
            self._stage_quality,
            self._stage_dynamic,
            self._stage_math,
            self._stage_statistics,
            self._stage_style,
            self._stage_decision,
            self._stage_execution,
        ]

        # 执行所有阶段
        for stage_fn in pipeline:
            report = stage_fn(ctx, audit)
            audit.append(report)

        # 如果有REJECT，终止
        rejected = any(r.verdict == Verdict.REJECT for r in audit)
        if rejected:
            rejected_stage = next(r.stage.value for r in audit if r.verdict == Verdict.REJECT)
            audit.append(StageReport(
                stage=StageID.COMPLETE, verdict=Verdict.REJECT,
                details={"message": f"阶段{rejected_stage}否决，流程终止"},
            ))
            return self._build_result(audit, False, start_time)

        # 判断最终是否通过
        passed = self._calculate_final_verdict(audit, ctx.platform)
        return self._build_result(audit, passed, start_time)

    # ============ 各阶段实现 ============

    def _stage_intake(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段0: 接收输入 — 检查输入是否有效"""
        t0 = time.time()
        
        warnings = []
        if len(ctx.text) < 200:
            return StageReport(
                stage=StageID.INTAKE, verdict=Verdict.REJECT, score=0,
                warnings=["文本过短，不足200字"],
                duration_ms=(time.time() - t0) * 1000
            )
        
        if len(ctx.text) < 1000:
            warnings.append("文本较短(不足1000字)，部分分析精度可能受影响")
        
        return StageReport(
            stage=StageID.INTAKE, verdict=Verdict.PASS, score=100,
            confidence=1.0,
            details={"text_length": len(ctx.text), "chapter_num": ctx.chapter_num},
            warnings=warnings,
            duration_ms=(time.time() - t0) * 1000
        )

    def _stage_planning(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段1: 方案构建 — 根据类型/平台/章节位置确定写作目标"""
        t0 = time.time()
        
        position = "opening"
        if ctx.chapter_num <= 3:
            position = "opening"
        elif ctx.chapter_num <= 20:
            position = "early"
        elif ctx.chapter_num <= 100:
            position = "mid"
        else:
            position = "late"

        platform_targets = {
            "qimao": {"hook_density": 0.3, "pos_neg_ratio": 2.0, "dialogue_ratio": 0.3},
            "fanqie": {"hook_density": 0.4, "pos_neg_ratio": 2.5, "dialogue_ratio": 0.4},
            "qidian": {"hook_density": 0.25, "pos_neg_ratio": 1.8, "dialogue_ratio": 0.35},
        }
        targets = platform_targets.get(ctx.platform, platform_targets["qimao"])

        return StageReport(
            stage=StageID.PLANNING, verdict=Verdict.PASS, score=100, confidence=1.0,
            details={
                "position": position,
                "platform": ctx.platform,
                "genre": ctx.genre,
                "targets": targets,
            },
            duration_ms=(time.time() - t0) * 1000
        )

    def _stage_strategy(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段2: 策划 — 创作引擎策略推荐"""
        t0 = time.time()
        try:
            from creative_engine import CreativeEngine
            engine = CreativeEngine()
            result = engine.recommend_strategy(ctx.genre, ctx.chapter_num, ctx.platform)
            ctx.strategy_result = result

            confidence = result.get("confidence", 0.5)
            score = confidence * 100
            sample_count = result.get("sample_count", 0)

            # 样本量太少或未知类型 → 跳过，不阻塞
            if sample_count < 3 or ctx.genre == "unknown":
                return StageReport(stage=StageID.STRATEGY, verdict=Verdict.SKIP, score=score,
                                 confidence=0, details=result,
                                 warnings=[f"类型'{ctx.genre}'样本不足({sample_count}条)，跳过策略推荐"],
                                 duration_ms=(time.time() - t0) * 1000)

            threshold = self.pass_thresholds[StageID.STRATEGY]
            return StageReport(
                stage=StageID.STRATEGY, 
                verdict=Verdict.PASS if score >= threshold else Verdict.REVISE,
                score=score, confidence=confidence,
                details=result,
                recommendations=result.get("actionable_tips", []),
                duration_ms=(time.time() - t0) * 1000
            )
        except ImportError:
            return StageReport(stage=StageID.STRATEGY, verdict=Verdict.SKIP, score=50,
                             confidence=0, duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.STRATEGY, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[str(e)], duration_ms=(time.time() - t0) * 1000)

    def _stage_quality(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段3: 审核 — 静态质量检查"""
        t0 = time.time()
        try:
            from quality_checker import check_chapter
            report = check_chapter(ctx.text, ctx.platform, ctx.chapter_num, ctx.mode)
            
            # 统计问题
            fatals = len(report.fatals) if hasattr(report, 'fatals') else 0
            issues = len(report.issues) if hasattr(report, 'issues') else 0
            warnings_count = len(report.warnings) if hasattr(report, 'warnings') else 0
            
            # 致命问题直接否决
            if fatals > 0:
                return StageReport(
                    stage=StageID.QUALITY, verdict=Verdict.REJECT, score=0,
                    details={"fatals": fatals, "issues": issues},
                    warnings=[f"致命问题: {fatals}个"],
                    duration_ms=(time.time() - t0) * 1000
                )
            
            # 计算分数
            score = max(0, 100 - issues * 10 - warnings_count * 3)
            ctx.quality_result = {"passed": report.passed if hasattr(report, 'passed') else (fatals == 0),
                                  "issues": issues, "warnings": warnings_count, "score": score}
            
            threshold = self.pass_thresholds[StageID.QUALITY]
            if score >= threshold:
                return StageReport(stage=StageID.QUALITY, verdict=Verdict.PASS, score=score,
                                 confidence=0.9, details=ctx.quality_result,
                                 duration_ms=(time.time() - t0) * 1000)
            else:
                return StageReport(stage=StageID.QUALITY, verdict=Verdict.REVISE, score=score,
                                 confidence=0.9, details=ctx.quality_result,
                                 rollback_to=StageID.PLANNING,
                                 recommendations=["请根据策划阶段的目标重新修改文本"],
                                 duration_ms=(time.time() - t0) * 1000)
        except ImportError:
            return StageReport(stage=StageID.QUALITY, verdict=Verdict.SKIP, score=50,
                             confidence=0, duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.QUALITY, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[str(e)], duration_ms=(time.time() - t0) * 1000)

    def _stage_dynamic(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段4: 评估 — 动态情绪评分"""
        t0 = time.time()
        try:
            from dynamic_scorer import DynamicScorer
            scorer = DynamicScorer()
            result = scorer.comprehensive_score(ctx.text, ctx.platform)
            ctx.dynamic_result = result
            
            score = result.get("total_score", 50)
            threshold = self.pass_thresholds[StageID.DYNAMIC]
            
            if score >= threshold:
                return StageReport(stage=StageID.DYNAMIC, verdict=Verdict.PASS, score=score,
                                 confidence=0.85, details=result,
                                 duration_ms=(time.time() - t0) * 1000)
            else:
                return StageReport(stage=StageID.DYNAMIC, verdict=Verdict.REVISE, score=score,
                                 confidence=0.85, details=result,
                                 rollback_to=StageID.STRATEGY,
                                 recommendations=["动态评分不达标，建议参考策略调整"],
                                 duration_ms=(time.time() - t0) * 1000)
        except ImportError:
            return StageReport(stage=StageID.DYNAMIC, verdict=Verdict.SKIP, score=50,
                             confidence=0, duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.DYNAMIC, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[str(e)], duration_ms=(time.time() - t0) * 1000)

    def _stage_math(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段5: 评估 — 数学引擎全分析"""
        t0 = time.time()
        try:
            from pangu_math_core import PanguMathEngine
            engine = PanguMathEngine()
            result = engine.full_analysis(ctx.text, ctx.chapter_num)
            ctx.math_result = result
            
            score = result.get("overall_math_score", 50)
            threshold = self.pass_thresholds[StageID.MATH]
            
            if score >= threshold:
                return StageReport(stage=StageID.MATH, verdict=Verdict.PASS, score=score,
                                 confidence=0.8, details=result,
                                 duration_ms=(time.time() - t0) * 1000)
            else:
                return StageReport(stage=StageID.MATH, verdict=Verdict.REVISE, score=score,
                                 confidence=0.8, details=result,
                                 rollback_to=StageID.QUALITY,
                                 recommendations=["数学模型评分不达标，建议根据数学诊断优化"],
                                 duration_ms=(time.time() - t0) * 1000)
        except ImportError:
            return StageReport(stage=StageID.MATH, verdict=Verdict.SKIP, score=50,
                             confidence=0, duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.MATH, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[str(e)], duration_ms=(time.time() - t0) * 1000)

    def _stage_statistics(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段6: 评估 — 医学统计分析"""
        t0 = time.time()
        try:
            from medical_statistics import MedicalStatistics
            stats = MedicalStatistics()
            
            # 收集前几轮的分析数据做统计推断
            previous_scores = []
            for report in trail:
                if report.score > 0:
                    previous_scores.append(report.score)
            
            result = stats.comprehensive_diagnosis(ctx.text, ctx.chapter_num, 
                                                     ctx.chapter_history, previous_scores)
            ctx.statistics_result = result
            
            score = result.get("overall_diagnostic_score", 50)
            threshold = self.pass_thresholds[StageID.STATISTICS]
            
            warnings_list = []
            for test in result.get("significant_findings", []):
                if test.get("p_value", 0) < 0.05:
                    warnings_list.append(f"{test['test']}: p={test['p_value']:.4f} (<0.05, 显著)")
            
            if score >= threshold:
                return StageReport(stage=StageID.STATISTICS, verdict=Verdict.PASS, score=score,
                                 confidence=0.9, details=result, warnings=warnings_list,
                                 duration_ms=(time.time() - t0) * 1000)
            else:
                return StageReport(stage=StageID.STATISTICS, verdict=Verdict.REVISE, score=score,
                                 confidence=0.9, details=result, warnings=warnings_list,
                                 rollback_to=StageID.MATH,
                                 recommendations=["统计推断未通过显著性检验"],
                                 duration_ms=(time.time() - t0) * 1000)
        except ImportError as e:
            return StageReport(stage=StageID.STATISTICS, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[f"依赖缺失: {e}"],
                             duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.STATISTICS, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[f"统计异常{type(e).__name__}: {e}"],
                             duration_ms=(time.time() - t0) * 1000)

    def _stage_style(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段7: 审核 — 风格指纹分析"""
        t0 = time.time()
        try:
            from style_fingerprint import StyleFingerprint
            fp = StyleFingerprint(ctx.text, platform=ctx.platform)
            result = fp.to_dict()
            ctx.style_result = result
            
            # 基于deep_math评分
            deep = result.get("deep_math", {})
            deep_score = deep.get("overall_complexity", 50) if isinstance(deep, dict) else 50
            ai_flag = deep.get("ai_template_detected", False) if isinstance(deep, dict) else False
            
            warnings_list = []
            if ai_flag:
                warnings_list.append("检测到AI模板化特征，建议人工润色")
            
            threshold = self.pass_thresholds[StageID.STYLE]
            if deep_score >= threshold:
                return StageReport(stage=StageID.STYLE, verdict=Verdict.PASS, score=deep_score,
                                 confidence=0.75, details=result, warnings=warnings_list,
                                 duration_ms=(time.time() - t0) * 1000)
            else:
                return StageReport(stage=StageID.STYLE, verdict=Verdict.REVISE, score=deep_score,
                                 confidence=0.75, details=result, warnings=warnings_list,
                                 rollback_to=StageID.STRATEGY,
                                 recommendations=["风格评分不达标，建议丰富词汇和句式"],
                                 duration_ms=(time.time() - t0) * 1000)
        except ImportError:
            return StageReport(stage=StageID.STYLE, verdict=Verdict.SKIP, score=50,
                             confidence=0, duration_ms=(time.time() - t0) * 1000)
        except Exception as e:
            return StageReport(stage=StageID.STYLE, verdict=Verdict.SKIP, score=50,
                             confidence=0, warnings=[str(e)], duration_ms=(time.time() - t0) * 1000)

    def _stage_decision(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段8: 决策 — 综合各部门意见做最终判决"""
        t0 = time.time()
        
        # 收集所有非SKIP阶段的评分
        valid_reports = [r for r in trail if r.verdict != Verdict.SKIP and r.stage != StageID.DECISION]
        
        if not valid_reports:
            return StageReport(stage=StageID.DECISION, verdict=Verdict.REJECT, score=0,
                             confidence=1.0, details={"message": "无有效评估数据"},
                             duration_ms=(time.time() - t0) * 1000)

        # 加权投票
        platform_w = self.platform_weights.get(ctx.platform, {})
        total_weight = 0
        weighted_score = 0
        
        detail_lines = []
        for report in valid_reports:
            w = platform_w.get(report.stage, self.stage_weights.get(report.stage, 0.1))
            weighted_score += report.score * w * report.confidence
            total_weight += w * report.confidence
            detail_lines.append(f"  {report.stage.value}: {report.score:.1f} x {w:.2f} x {report.confidence:.2f}")
        
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 50

        # 决策逻辑
        if final_score >= 70:
            verdict = Verdict.PASS
            message = "综合评估通过，可以开始写作/发布"
        elif final_score >= 55:
            verdict = Verdict.REVISE
            message = "综合评估偏低，建议修订后重新评估"
        else:
            verdict = Verdict.REVISE
            message = "综合评估不合格，需要大幅度修改"

        ctx.decision_result = {
            "final_score": final_score,
            "verdict": verdict.value,
            "weighted_breakdown": detail_lines,
            "message": message,
        }

        return StageReport(
            stage=StageID.DECISION, verdict=verdict, score=final_score,
            confidence=0.95, details=ctx.decision_result,
            recommendations=[message],
            duration_ms=(time.time() - t0) * 1000
        )

    def _stage_execution(self, ctx: WorkflowContext, trail: List[StageReport]) -> StageReport:
        """阶段9: 实施 — 生成写作指引"""
        t0 = time.time()
        
        guidance_parts = []
        
        # 从数学引擎获取指引
        if ctx.math_result and "error" not in ctx.math_result:
            try:
                from pangu_math_core import PanguMathEngine
                engine = PanguMathEngine()
                guidance = engine.get_guidance_prompt(ctx.math_result, ctx.platform)
                guidance_parts.append(guidance)
            except Exception:
                pass

        # 从策略引擎获取建议
        if ctx.strategy_result:
            tips = ctx.strategy_result.get("actionable_tips", [])
            if tips:
                guidance_parts.append("\n[策略引擎建议]")
                for tip in tips[:5]:
                    guidance_parts.append(f"  - {tip}")

        # 从动态评分获取建议
        if ctx.dynamic_result:
            breakdown = ctx.dynamic_result.get("breakdown", {})
            weak_points = []
            for name, data in breakdown.items():
                if data.get("score", 100) < 60:
                    weak_points.append(f"  - {name}: {data.get('detail', '需要改进')}")
            if weak_points:
                guidance_parts.append("\n[动态评分弱项]")
                guidance_parts.extend(weak_points)

        full_guidance = "\n".join(guidance_parts) if guidance_parts else "无特别指引"
        ctx.execution_result = {"guidance": full_guidance}

        return StageReport(
            stage=StageID.EXECUTION, verdict=Verdict.PASS, score=100,
            confidence=1.0,
            details={"guidance_length": len(full_guidance)},
            duration_ms=(time.time() - t0) * 1000
        )

    # ============ 辅助方法 ============

    def _find_rollback_target(self, current_fn, pipeline) -> Optional[StageID]:
        """根据当前失败的阶段，找到应该回滚到的上游阶段"""
        # 映射：哪个阶段失败，回滚到哪个阶段
        rollback_map = {
            "_stage_quality":    StageID.PLANNING,
            "_stage_dynamic":    StageID.STRATEGY,
            "_stage_math":       StageID.QUALITY,
            "_stage_statistics": StageID.MATH,
            "_stage_style":      StageID.STRATEGY,
            "_stage_strategy":   StageID.PLANNING,
        }
        fn_name = current_fn.__name__
        return rollback_map.get(fn_name)

    def _calculate_final_verdict(self, audit: List[StageReport], platform: str) -> bool:
        """根据审计轨迹判断最终是否通过"""
        decision_reports = [r for r in audit if r.stage == StageID.DECISION]
        if not decision_reports:
            return False
        
        last_decision = decision_reports[-1]
        if last_decision.verdict == Verdict.PASS:
            return True
        
        # 如果最后一个决策分数>65且有多个PASS阶段，也算通过
        pass_count = sum(1 for r in audit if r.verdict == Verdict.PASS)
        if last_decision.score >= 65 and pass_count >= 4:
            return True
        
        return False

    def _build_result(self, audit: List[StageReport], passed: bool, start_time: float) -> WorkflowResult:
        """构建工作流结果"""
        total_duration = (time.time() - start_time) * 1000
        revision_count = sum(1 for r in audit if r.stage == StageID.DECISION) - 1
        
        # 找到瓶颈（耗时最长的阶段）
        valid = [r for r in audit if r.duration_ms > 0]
        bottleneck = max(valid, key=lambda r: r.duration_ms) if valid else None

        # 综合评分
        decision_reports = [r for r in audit if r.stage == StageID.DECISION]
        final_score = decision_reports[-1].score if decision_reports else 0

        # 最终指引
        exec_reports = [r for r in audit if r.stage == StageID.EXECUTION]
        guidance = ""
        if exec_reports:
            guidance_details = exec_reports[-1].details
            guidance = guidance_details.get("guidance", "")

        return WorkflowResult(
            passed=passed,
            final_score=final_score,
            audit_trail=audit,
            guidance=guidance,
            revision_count=max(0, revision_count),
            total_duration_ms=total_duration,
            bottleneck_stage=bottleneck.stage.value if bottleneck else ""
        )


# ============================================================
# CLI和便捷函数
# ============================================================

def breathe(text: str, chapter_num: int = 1, platform: str = "qimao",
            genre: str = "unknown", project_name: str = "",
            chapter_history: List[str] = None) -> WorkflowResult:
    """
    便捷函数：对文本执行一次完整的"呼吸"周期。
    
    示例:
        result = breathe(text, chapter_num=1, platform="qimao")
        print(result.summary())
        print(result.guidance)
    """
    ctx = WorkflowContext(
        text=text,
        chapter_num=chapter_num,
        platform=platform,
        genre=genre,
        project_name=project_name,
        chapter_history=chapter_history or [],
    )
    orchestrator = BreathingOrchestrator()
    return orchestrator.breathe(ctx)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python workflow_orchestrator.py <文本文件路径> [章节号] [平台]")
        print("示例: python workflow_orchestrator.py ch1.txt 1 qimao")
        sys.exit(0)

    filepath = sys.argv[1]
    chapter_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    platform = sys.argv[3] if len(sys.argv) > 3 else "qimao"

    text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
    result = breathe(text, chapter_num=chapter_num, platform=platform)
    
    print(result.summary())
    if result.guidance:
        print(f"\n{'='*60}")
        print("  实施指引 (EXECUTION)")
        print(f"{'='*60}")
        print(result.guidance)
