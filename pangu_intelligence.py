"""
盘古情报中心 (Pangu Intelligence)

Pipeline 集成钩子: W5 导出完成后自动运行全部分析引擎，
生成统一章节情报报告 (intelligence.json)。

调用链:
  Pipeline W5 → pangu_intelligence.analyze(project_dir, chapter_num)
    ├── stats:    distribution + diversity + readability + style_fingerprint
    ├── signal:   emotion_spectrum + tension_envelope + rhythm
    ├── graph:    character_network + foreshadow_graph
    ├── bayesian: quality_updater (逐段更新)
    ├── monte_carlo: retention_simulation
    ├── economics: market_analysis
    ├── accounting: cost_tracking
    ├── control: audit_check
    └── kpi: dashboard_update
    → 写入 {project}/.webnovel/intelligence/chapter_{N}.json

用法:
    from pangu_intelligence import analyze_chapter
    report = analyze_chapter(project_dir, chapter_num=1)
    print(report.summary())
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ================================================================
# 统一情报报告
# ================================================================

@dataclass
class ChapterIntelligence:
    """章节统一情报报告"""
    chapter: int
    project: str = ""
    analyzed_at: str = ""

    # 基础
    word_count: int = 0
    paragraph_count: int = 0

    # Stats
    sentence_stats: Dict = field(default_factory=dict)
    diversity_stats: Dict = field(default_factory=dict)
    readability_score: Dict = field(default_factory=dict)
    style_vector: List[float] = field(default_factory=list)

    # Signal
    emotion_spectrum: Dict = field(default_factory=dict)
    tension_envelope: Dict = field(default_factory=dict)
    rhythm_analysis: Dict = field(default_factory=dict)

    # Graph
    character_network: Dict = field(default_factory=dict)
    foreshadow_health: Dict = field(default_factory=dict)

    # Intelligence
    quality_posterior: float = 0.0
    quality_trend: str = "stable"
    ai_risk_score: float = 0.0
    reader_retention_est: float = 0.0

    # Controls
    risk_flags: List[Dict] = field(default_factory=list)
    audit_opinion: str = "PENDING"

    # Action
    recommendation: str = ""
    next_chapter_advice: str = ""

    def summary(self) -> str:
        flags = len(self.risk_flags)
        return (
            f"Ch{self.chapter} | {self.word_count}字 | "
            f"质量后验={self.quality_posterior:.0%} | "
            f"AI风险={self.ai_risk_score:.2f} | "
            f"风险标记={flags} | "
            f"{self.audit_opinion}"
        )

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter, "project": self.project,
            "analyzed_at": self.analyzed_at,
            "word_count": self.word_count, "paragraph_count": self.paragraph_count,
            "sentence_stats": self.sentence_stats,
            "diversity_stats": self.diversity_stats,
            "readability_score": self.readability_score,
            "style_vector": [round(v, 4) for v in self.style_vector],
            "emotion_spectrum": self.emotion_spectrum,
            "tension_envelope": self.tension_envelope,
            "rhythm_analysis": self.rhythm_analysis,
            "character_network": self.character_network,
            "foreshadow_health": self.foreshadow_health,
            "quality_posterior": self.quality_posterior,
            "quality_trend": self.quality_trend,
            "ai_risk_score": self.ai_risk_score,
            "reader_retention_est": self.reader_retention_est,
            "risk_flags": self.risk_flags,
            "audit_opinion": self.audit_opinion,
            "recommendation": self.recommendation,
            "next_chapter_advice": self.next_chapter_advice,
        }


# ================================================================
# 主分析函数
# ================================================================

def analyze_chapter(project_dir: str, chapter_num: int,
                     chapter_content: str = None,
                     state: dict = None) -> ChapterIntelligence:
    """
    对一章执行全部分析，返回统一情报报告。

    这是 Pipeline W5 之后的标准后处理钩子。

    Args:
        project_dir: 项目根目录
        chapter_num: 章节号
        chapter_content: 章节正文（None则自动读取）
        state: state.json 内容（None则自动读取）

    Returns:
        ChapterIntelligence 完整情报报告
    """
    proj_path = Path(project_dir)
    ci = ChapterIntelligence(
        chapter=chapter_num,
        project=proj_path.name,
        analyzed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    # === 读取正文 ===
    if chapter_content is None:
        content_dir = proj_path / "正文"
        candidates = list(content_dir.glob(f"*{chapter_num:04d}*"))
        if not candidates:
            candidates = list(content_dir.glob(f"*第{chapter_num}章*"))
        if candidates:
            chapter_content = candidates[0].read_text(encoding="utf-8")
        else:
            ci.risk_flags.append({"level": "RED", "msg": f"第{chapter_num}章文件不存在"})
            return ci

    ci.word_count = len(chapter_content.replace('\n', '').replace(' ', ''))
    ci.paragraph_count = len([p for p in chapter_content.split('\n\n') if p.strip()])

    # === Stats ===
    try:
        from pangu_math.stats.distribution import SentenceStats, ChapterStats
        sent = SentenceStats.from_text(chapter_content)
        ci.sentence_stats = {
            "mean_len": round(sent.mean_sentence_length, 1),
            "cv": round(sent.cv_sentence_length, 3),
            "long_ratio": round(sent.long_sentence_ratio, 3),
            "max_consecutive_short": sent.max_consecutive_short,
        }
        ci.ai_risk_score = sent.ai_risk_score()

        chap = ChapterStats.from_text(chapter_content)
        ci.sentence_stats["dialogue_ratio"] = chap.dialogue_ratio
    except Exception as e:
        ci.risk_flags.append({"level": "YELLOW", "msg": f"Stats分析失败: {e}"})

    try:
        from pangu_math.stats.diversity import LexicalDiversity
        ld = LexicalDiversity.from_text(chapter_content)
        ci.diversity_stats = {
            "char_ttr": round(ld.char_ttr, 3), "mtld": round(ld.mtld, 1),
            "simpson": round(ld.simpson, 3), "entropy": round(ld.entropy, 2),
        }
    except Exception as e:
        pass

    try:
        from pangu_math.stats.readability import chinese_readability
        score = chinese_readability(chapter_content)
        ci.readability_score = {
            "total": round(score.total_score, 0), "grade": score.grade,
            "avg_strokes": round(score.avg_strokes, 1),
        }
    except Exception as e:
        pass

    try:
        from pangu_math.stats.style_fingerprint import StyleFingerprint
        sf = StyleFingerprint.from_text(chapter_content, f"Ch{chapter_num}")
        ci.style_vector = sf.features[:]
    except Exception as e:
        pass

    # === Signal ===
    try:
        from pangu_math.signal.emotion_spectrum import EmotionSpectrum
        es = EmotionSpectrum.from_text(chapter_content)
        ci.emotion_spectrum = {
            "dominant_period": round(es.dominant_period, 0),
            "complexity": round(es.complexity, 2),
            "mean_valence": round(es.mean_valence, 2),
            "energy_bands": es.energy_bands,
        }
    except Exception as e:
        pass

    try:
        from pangu_math.signal.tension_envelope import TensionEnvelope
        te = TensionEnvelope.from_text(chapter_content)
        ci.tension_envelope = {
            "peak_value": round(te.peak_value, 1),
            "peak_position": round(te.peak_position, 2),
            "mean_tension": round(te.mean_tension, 1),
            "pacing_quality": round(te.pacing_quality(), 2),
        }
    except Exception as e:
        pass

    try:
        from pangu_math.signal.rhythm_analyzer import RhythmAnalyzer
        ra = RhythmAnalyzer.from_text(chapter_content)
        ci.rhythm_analysis = {
            "primary_period": round(ra.primary_period, 0),
            "consistency": round(ra.consistency, 3),
            "is_mechanistic": ra.is_mechanistic(),
            "is_chaotic": ra.is_chaotic(),
        }
    except Exception as e:
        pass

    # === Graph ===
    if state:
        try:
            chars = state.get("characters", {})
            known = [chars.get("protagonist", {}).get("name", "")]
            known += [c.get("name", "") for c in chars.get("key_characters", [])]
            known = [n for n in known if n]

            if known:
                from pangu_math.graph.character_network import CharacterNetwork
                cn = CharacterNetwork.from_text(chapter_content, known)
                ci.character_network = {
                    "most_central": cn.most_central(),
                    "density": round(cn.density, 3),
                    "excessive_dominance": cn.excessive_dominance(),
                    "isolated": cn.isolated_characters(),
                }
        except Exception as e:
            pass

        try:
            from pangu_math.graph.foreshadow_graph import ForeshadowGraph
            fg = ForeshadowGraph.from_state(state)
            ci.foreshadow_health = {
                "open": fg.total_open, "resolved": fg.total_resolved,
                "orphans": len(fg.orphin_threads),
                "expired": len(fg.expired_threads),
                "health_score": round(fg.health_score(), 2),
            }
        except Exception as e:
            pass

    # === Bayesian Quality ===
    try:
        from pangu_math.probability.bayesian import BayesianQualityModel
        bq = BayesianQualityModel(prior_quality=0.65)
        paragraphs = [p.strip() for p in chapter_content.split('\n\n') if p.strip()]
        for para in paragraphs:
            bq.feed_paragraph(para)
        ci.quality_posterior = bq.posterior_quality

        # 质量趋势: 前半vs后半
        if len(paragraphs) >= 4:
            mid = len(paragraphs) // 2
            bq1 = BayesianQualityModel(prior_quality=0.65)
            for p in paragraphs[:mid]: bq1.feed_paragraph(p)
            bq2 = BayesianQualityModel(prior_quality=0.65)
            for p in paragraphs[mid:]: bq2.feed_paragraph(p)
            if bq2.posterior_quality > bq1.posterior_quality + 0.1:
                ci.quality_trend = "improving"
            elif bq2.posterior_quality < bq1.posterior_quality - 0.1:
                ci.quality_trend = "declining"
            else:
                ci.quality_trend = "stable"
    except Exception as e:
        pass

    # === Monte Carlo ===
    try:
        from pangu_math.probability.monte_carlo import MonteCarloPlotSimulator
        sim = MonteCarloPlotSimulator(chapter_count=min(12, state.get("project_info", {}).get("target_chapters", 12) if state else 12))
        result = sim.simulate_readership(n=100)
        ci.reader_retention_est = result["retention_p50"]
    except Exception as e:
        pass

    # === Risk Assessment ===
    if ci.ai_risk_score > 0.5:
        ci.risk_flags.append({
            "level": "ORANGE",
            "msg": f"AI风险偏高 ({ci.ai_risk_score:.2f})",
            "detail": f"连续短句={ci.sentence_stats.get('max_consecutive_short', 0)}",
        })
    if ci.quality_posterior < 0.4:
        ci.risk_flags.append({
            "level": "RED",
            "msg": f"质量后验过低 ({ci.quality_posterior:.0%})",
        })
    if ci.rhythm_analysis.get("is_mechanistic"):
        ci.risk_flags.append({
            "level": "YELLOW",
            "msg": "节奏过于机械化",
        })

    # === Audit Opinion ===
    reds = sum(1 for f in ci.risk_flags if f["level"] == "RED")
    oranges = sum(1 for f in ci.risk_flags if f["level"] == "ORANGE")
    if reds > 0:
        ci.audit_opinion = "ADVERSE — 存在阻断级风险"
    elif oranges > 0:
        ci.audit_opinion = f"QUALIFIED — {oranges}个关注项"
    else:
        ci.audit_opinion = "CLEAN — 无显著风险"

    # === Recommendation ===
    ci.recommendation = _generate_recommendation(ci)
    ci.next_chapter_advice = _next_chapter_advice(ci, state)

    # === Save ===
    _save_intelligence(proj_path, chapter_num, ci)

    return ci


def _generate_recommendation(ci: ChapterIntelligence) -> str:
    """基于所有分析维度生成建议"""
    recs = []

    if ci.ai_risk_score > 0.5:
        recs.append("增加句长变化，减少连续短句")

    if ci.rhythm_analysis.get("is_mechanistic"):
        recs.append("打破固定节奏——插入一段长描写或纯对话")

    if ci.quality_trend == "declining":
        recs.append("质量在后半章下降——检查后半是否赶工")

    if ci.tension_envelope.get("pacing_quality", 1) < 0.5:
        recs.append("节奏需要张弛调整——峰值附近插入'呼吸'段")

    if not recs:
        recs.append("质量稳定，保持当前节奏")

    return "; ".join(recs)


def _next_chapter_advice(ci: ChapterIntelligence, state: dict) -> str:
    """基于当前章情报，建议下一章的策略"""
    advice = []

    # 伏笔推进建议
    if state:
        fg_data = ci.foreshadow_health
        expired = fg_data.get("expired", 0)
        if expired > 0:
            advice.append(f"⚠ 有{expired}条过期伏笔——下章必须推进或回收")

    # 情绪曲线建议
    es = ci.emotion_spectrum
    if es.get("mean_valence", 0) < -0.3:
        advice.append("本章情绪偏负面——下章考虑一个小释放")
    elif es.get("mean_valence", 0) > 0.3:
        advice.append("本章情绪积极——下章可以上强度了")

    # 节奏建议
    tension = ci.tension_envelope
    if tension.get("peak_position", 0.5) < 0.4:
        advice.append("峰值偏前——下章注意把高潮放在65-85%位置")

    if not advice:
        advice.append("按总纲章纲正常推进")

    return "; ".join(advice)


def _save_intelligence(proj_path: Path, chapter_num: int, ci: ChapterIntelligence):
    """保存情报报告到文件"""
    intel_dir = proj_path / ".webnovel" / "intelligence"
    intel_dir.mkdir(parents=True, exist_ok=True)

    report_path = intel_dir / f"chapter_{chapter_num:04d}.json"
    report_path.write_text(
        json.dumps(ci.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8")


# ================================================================
# Pipeline 钩子 (供 W5 调用)
# ================================================================

def pipeline_post_commit_hook(project_dir: str, chapter_num: int,
                               chapter_content: str, state: dict) -> ChapterIntelligence:
    """
    Pipeline W5 后自动调用的钩子函数。

    在 pangu_core/pipeline.py 的 _run_quick_mode_post_hooks 中
    或 pangu_core/stages.py 的 W5ExportStage.run 末尾调用。
    """
    print(f"\n  [Intelligence] 分析第{chapter_num}章...")
    ci = analyze_chapter(project_dir, chapter_num, chapter_content, state)
    print(f"  [Intelligence] {ci.summary()}")
    return ci
