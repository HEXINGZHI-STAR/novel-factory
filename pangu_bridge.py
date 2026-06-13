"""
盘古 Python Bridge — FastAPI 常驻服务

替代 backend-java/PythonBridge.java 的 ProcessBuilder 方式。
Java 通过 HTTP 调用，Python 进程常驻 → 性能 10x+。

启动:
  python pangu_bridge.py --port 5100
  uvicorn pangu_bridge:app --host 127.0.0.1 --port 5100

Java 端使用 (替代 ProcessBuilder):
  RestTemplate rest = new RestTemplate();
  String result = rest.postForObject(
      "http://127.0.0.1:5100/analyze",
      Map.of("text", chapterContent, "chapter_num", 5),
      String.class);
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# === FastAPI ===
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import uvicorn
    HAS_API = True
except ImportError:
    HAS_API = False

app = FastAPI(
    title="Pangu Python Bridge",
    version="2.0",
    description="盘古数学引擎常驻服务 — Java↔Python HTTP桥接",
)


# === 请求模型 ===
class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="章节正文")
    chapter_num: int = Field(1, ge=1, description="章节号")

class CompareRequest(BaseModel):
    text1: str = Field(..., description="文本1")
    text2: str = Field(..., description="文本2")

class SequenceRequest(BaseModel):
    chapters: list[str] = Field(..., min_length=1, max_length=50)

class GuidanceRequest(BaseModel):
    analysis_result: dict = Field(..., description="分析结果JSON")
    platform: str = Field("qimao", description="平台名")


# === 路由 ===

@app.get("/health")
async def health():
    """健康检查"""
    try:
        from knowledge.pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        return {"status": "healthy", "engine": "PanguMathEngine"}
    except Exception as e:
        raise HTTPException(503, f"Engine unavailable: {e}")


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """分析章节 — 替代 PythonBridge.analyzeChapter()"""
    from knowledge.pangu_math_core import PanguMathEngine
    engine = PanguMathEngine()
    result = engine.full_analysis(req.text, req.chapter_num)
    return result


@app.post("/compare")
async def compare(req: CompareRequest):
    """对比两段文本 — 替代 PythonBridge.compareChapters()"""
    from knowledge.pangu_math_core import PanguMathEngine
    engine = PanguMathEngine()
    result = engine.compare_texts(req.text1, req.text2)
    return result


@app.post("/sequence")
async def sequence(req: SequenceRequest):
    """序列分析 (多章) — 替代 PythonBridge.analyzeSequence()"""
    from knowledge.pangu_math_core import PanguMathEngine
    engine = PanguMathEngine()
    result = engine.sequence_analysis(req.chapters)
    return result


@app.post("/guidance")
async def guidance(req: GuidanceRequest):
    """获取写作指引 — 替代 PythonBridge.getGuidancePrompt()"""
    from knowledge.pangu_math_core import PanguMathEngine
    engine = PanguMathEngine()
    prompt = engine.get_guidance_prompt(req.analysis_result, req.platform)
    return {"guidance": prompt}


@app.post("/analyze_batch")
async def analyze_batch(requests: list[AnalyzeRequest]):
    """批量分析 (一次HTTP调用处理多章)"""
    from knowledge.pangu_math_core import PanguMathEngine
    engine = PanguMathEngine()
    results = []
    for req in requests:
        results.append(engine.full_analysis(req.text, req.chapter_num))
    return {"results": results}


# === 扩展路由 (Java骨架调用) ===

class WriteRequest(BaseModel):
    project: str = Field(..., description="项目名")
    chapter: int = Field(1, ge=1)
    task: str = Field("")
    mode: str = Field("workshop")
    platform: str = Field("qimao")

class ReviewRequest(BaseModel):
    project: str
    chapter: int

class StrategyRequest(BaseModel):
    project: str
    chapter: int

class TrendRequest(BaseModel):
    platform: str = Field("qimao")

class CreateProjectRequest(BaseModel):
    title: str
    platform: str = Field("qimao")
    genre: str = Field("悬疑")
    chapters: int = Field(100)

class AnalyzeStatsRequest(BaseModel):
    text: str

class AnalyzeTextRequest(BaseModel):
    text: str
    known_characters: list = []
    foreshadowing_count: int = 0

class AnalyzeArcRequest(BaseModel):
    valences: list[float]
    expected_arc: str = ""

@app.post("/write")
async def write(req: WriteRequest):
    """写章 Pipeline W0-W5"""
    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config; reset_config()
    from pangu_core.pipeline import WritingPipeline, PipelineConfig
    from pangu_workshop import find_project

    proj = find_project(req.project)
    if not proj: return {"error": f"项目 '{req.project}' 未找到"}

    config = (PipelineConfig.from_workshop_mode if req.mode == "workshop"
              else PipelineConfig.from_quick_mode)(
        project_dir=str(proj), chapter=req.chapter, task=req.task,
        mode="mystery", platform=req.platform)
    result = WritingPipeline(config).run()
    wc = len(result.chapter_content.replace('\n','').replace(' ',''))
    return {"success": result.success, "words": wc,
            "content": result.chapter_content[:5000], "errors": result.errors}

@app.post("/review")
async def review(req: ReviewRequest):
    """审查章节"""
    from pangu_intelligence import analyze_chapter
    from pangu_workshop import find_project
    import json
    proj = find_project(req.project)
    if not proj: return {"error": "项目未找到"}
    state = json.loads((proj/'.webnovel'/'state.json').read_text(encoding='utf-8')) if (proj/'.webnovel'/'state.json').exists() else {}
    ci = analyze_chapter(str(proj), req.chapter, state=state)
    return {"quality": ci.quality_posterior, "ai_risk": ci.ai_risk_score,
            "audit": ci.audit_opinion, "recommendation": ci.recommendation}

@app.post("/analyze/stats")
async def analyze_stats(req: AnalyzeStatsRequest):
    """文本统计"""
    from pangu_math.stats.distribution import SentenceStats, ChapterStats
    sent = SentenceStats.from_text(req.text)
    chap = ChapterStats.from_text(req.text)
    return {"mean_len": sent.mean_sentence_length, "cv": sent.cv_sentence_length,
            "ai_risk": sent.ai_risk_score(), "dialogue": chap.dialogue_ratio}

@app.post("/analyze/arc")
async def analyze_arc(req: AnalyzeArcRequest):
    """情感弧线分析"""
    from pangu_analytics.emotional_arc import EmotionalArcAnalyzer
    ea = EmotionalArcAnalyzer()
    result = ea.analyze(req.valences, req.expected_arc or None)
    return {"best_arc": result.best_arc, "match": result.match_score,
            "next": result.next_direction, "slope": result.current_slope}

@app.post("/analyze/persuasion")
async def analyze_persuasion(req: AnalyzeStatsRequest):
    """说服力分析"""
    from pangu_analytics.persuasion_engine import PersuasionAnalyzer
    return PersuasionAnalyzer().full_report(req.text)

@app.post("/analyze/neural")
async def analyze_neural(req: AnalyzeStatsRequest):
    """神经共鸣分析"""
    from pangu_analytics.neural_resonance import neural_resonance
    r = neural_resonance(req.text)
    return {"mirror": r.mirror_score, "oxytocin": r.oxytocin_score,
            "sensory": r.sensory_score, "resonance": r.resonance_index,
            "verdict": r.emotional_arc, "suggestions": r.suggestions}

@app.post("/analyze/cognitive")
async def analyze_cognitive(req: AnalyzeTextRequest):
    """认知负荷分析"""
    from pangu_analytics.cognitive_load import CognitiveLoadAnalyzer
    r = CognitiveLoadAnalyzer().analyze(
        req.text, req.known_characters, req.foreshadowing_count)
    return {"overload": r.overload_risk, "dropout": r.dropout_risk,
            "verdict": r.verdict, "suggestions": r.suggestions}

@app.post("/strategy")
async def strategy(req: StrategyRequest):
    """写作策略推荐"""
    from pangu_workshop_smart import SmartStrategyEngine
    from pangu_workshop import find_project
    proj = find_project(req.project)
    if not proj: return {"error": "项目未找到"}
    engine = SmartStrategyEngine(proj)
    s = engine.recommend_strategy(req.chapter)
    task = engine.generate_chapter_task(req.chapter)
    return {"mode": s.mode, "words": s.target_words, "temperature": s.temperature,
            "hook": s.hook_type, "release": s.release_type, "task": task}

@app.post("/trend/radar")
async def trend_radar(req: TrendRequest):
    """趋势雷达"""
    from pangu_analytics.trend_radar import TrendRadar
    radar = TrendRadar()
    rec = radar.recommend_genre(req.platform)
    return rec

@app.get("/projects")
async def list_projects():
    """列出所有项目"""
    from pangu_workshop import PROJECT_ROOTS, load_state
    result = []
    for root in PROJECT_ROOTS:
        if not root.exists(): continue
        for child in root.iterdir():
            if not child.is_dir(): continue
            state = load_state(child)
            if not state: continue
            info = state.get('project_info',{})
            prog = state.get('progress',{})
            result.append({"title": info.get('title',child.name),
                "platform": info.get('platform','?'),
                "genre": info.get('genre','?'),
                "progress": f"{prog.get('current_chapter',0)}/{info.get('target_chapters','?')}",
                "words": prog.get('total_words',0)})
    return result

@app.post("/projects/create")
async def create_project(req: CreateProjectRequest):
    """创建项目"""
    from pangu_optimized import create_project_quick
    proj_dir = create_project_quick(req.title, req.genre, req.platform, req.chapters)
    return {"success": True, "project_dir": proj_dir}

# === 启动 ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not HAS_API:
        print("[FATAL] pip install fastapi uvicorn pydantic")
        sys.exit(1)

    print(f"盘古 Python Bridge 启动: http://{args.host}:{args.port}")
    print(f"  /health  /analyze  /compare  /sequence  /guidance  /analyze_batch")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
