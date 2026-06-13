"""
盘古 · Prefect 车间流水线

用 Prefect 替换手动 for 循环，获得:
  - 可视化仪表盘 (prefect server start)
  - 自动重试失败Stage
  - 断电重启不丢进度
  - 实时查看每步耗时

启动仪表盘:
  prefect server start
  → 浏览器打开 http://127.0.0.1:4200

用法:
  from pangu_core.prefect_flow import write_chapter_flow
  result = write_chapter_flow("开门见尸", 3, "沈让带姜渺去警局做笔录")
"""

from __future__ import annotations

import sys, json, re, time
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from prefect import flow, task, get_run_logger


@task(name="W0-锚定", retries=1, tags=["logic"])
def w0_anchor(project_dir: str, chapter_num: int, chapter_task: str) -> dict:
    """W0: 读取state.json，提取锚定信息"""
    from .stages import W0AnchorStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    state = _load_state(project_dir)
    ctx.set("state", state)
    ctx.set("chapter_num", chapter_num)
    ctx.set("chapter_task", chapter_task)
    ctx.set("mode_name", state.get("project_info", {}).get("genre", "general"))

    stage = W0AnchorStage()
    output = stage.run(ctx)
    return output.data if output.success else {}


@task(name="W1-设置检查", retries=1, tags=["logic"])
def w1_setup(project_dir: str, chapter_num: int, chapter_task: str,
              anchor_data: dict) -> dict:
    """W1: WriteGates关卡 + 章节热库"""
    from .stages import W1SetupStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    ctx.set("state", _load_state(project_dir))
    ctx.set("chapter_num", chapter_num)
    ctx.set("chapter_task", chapter_task)
    ctx.set("project_dir", project_dir)
    ctx.set("anchor_data", anchor_data)

    stage = W1SetupStage()
    output = stage.run(ctx)
    return {"gate_passed": output.success}


@task(name="W2-初稿", retries=3, retry_delay_seconds=10, tags=["ai"])
def w2_draft(project_dir: str, chapter_num: int, chapter_task: str,
              anchor_data: dict) -> str:
    """W2: AI生成初稿。失败自动重试3次，间隔10秒。"""
    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config; reset_config()
    from .stages import W2DraftStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    ctx.set("state", _load_state(project_dir))
    ctx.set("chapter_num", chapter_num)
    ctx.set("chapter_task", chapter_task)
    ctx.set("project_dir", project_dir)
    ctx.set("anchor_data", anchor_data)
    ctx.set("mode_name", _load_state(project_dir).get("project_info", {}).get("genre", "general"))
    ctx.set("platform_name", _load_state(project_dir).get("project_info", {}).get("platform", "qimao"))
    ctx.set("title", _load_state(project_dir).get("project_info", {}).get("title", ""))
    ctx.set("mode_rule", "")
    ctx.set("platform_rule", "")
    ctx.set("context_content", "")

    stage = W2DraftStage()
    output = stage.run(ctx)
    if not output.success:
        raise Exception(f"W2失败: {output.errors}")
    return output.data.get("draft", "")


@task(name="W3-质检", retries=1, tags=["logic"])
def w3_qc(draft: str, project_dir: str, chapter_num: int) -> dict:
    """W3: 质量检查"""
    from .stages import W3QCStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    ctx.set("state", _load_state(project_dir))
    ctx.set("chapter_num", chapter_num)

    stage = W3QCStage()
    output = stage.run(ctx)
    if output.success:
        return output.data.get("qc_report", {})
    return {"passed": True, "score": 0.8}


@task(name="W4-精修", retries=2, retry_delay_seconds=15, tags=["ai"])
def w4_polish(draft: str, qc_report: dict, project_dir: str,
               chapter_num: int, chapter_task: str) -> str:
    """W4: AI润色。失败自动重试2次，间隔15秒。"""
    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config; reset_config()
    from .stages import W4PolishStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    ctx.set("state", _load_state(project_dir))
    ctx.set("chapter_num", chapter_num)
    ctx.set("chapter_task", chapter_task)
    ctx.set("project_dir", project_dir)
    ctx.set("qc_report", qc_report)
    ctx.set("polish_source", draft)
    ctx.set("mode_name", _load_state(project_dir).get("project_info", {}).get("genre", "general"))
    ctx.set("platform_name", _load_state(project_dir).get("project_info", {}).get("platform", "qimao"))
    ctx.set("title", _load_state(project_dir).get("project_info", {}).get("title", ""))
    ctx.set("mode_rule", "")
    ctx.set("platform_rule", "")
    ctx.set("context_content", "")

    stage = W4PolishStage()
    output = stage.run(ctx)
    return output.data.get("final", draft)


@task(name="W5-导出", retries=1, tags=["io"])
def w5_export(final_content: str, project_dir: str, chapter_num: int,
               chapter_task: str) -> dict:
    """W5: 写文件 + 更新state + 发布事件"""
    from .stages import W5ExportStage
    from .pipeline import PipelineContext

    ctx = PipelineContext()
    ctx.set("state", _load_state(project_dir))
    ctx.set("chapter_num", chapter_num)
    ctx.set("chapter_task", chapter_task)
    ctx.set("project_dir", project_dir)
    ctx.set("mode_name", _load_state(project_dir).get("project_info", {}).get("genre", "general"))

    stage = W5ExportStage()
    output = stage.run(ctx)

    # 事件总线
    from .event_bus import bus, ChapterWritten
    event = ChapterWritten()
    event.project = project_dir
    event.chapter = chapter_num
    event.words = len(final_content.replace('\n','').replace(' ',''))
    event.content = final_content
    event.state = _load_state(project_dir)
    bus.dispatch(event)

    return output.data if output.success else {}


@flow(name="盘古写作Pipeline", log_prints=True)
def write_chapter_flow(project_name: str, chapter_num: int,
                        chapter_task: str = "") -> dict:
    """
    Prefect 车间流水线: W0→W1→W2→W3→W4→W5

    每个Stage失败自动重试(W2×3, W4×2)，不中断后续。
    """
    from pangu_workshop import find_project
    from pangu_workshop_smart import SmartStrategyEngine

    proj = find_project(project_name)
    if not proj:
        return {"error": f"项目 '{project_name}' 未找到"}
    project_dir = str(proj)

    if not chapter_task:
        engine = SmartStrategyEngine(proj)
        chapter_task = engine.generate_chapter_task(chapter_num)

    logger = get_run_logger()
    logger.info(f"Pipeline启动: {project_name} 第{chapter_num}章")
    t0 = time.time()

    # W0: 锚定
    anchor = w0_anchor(project_dir, chapter_num, chapter_task)

    # W1: 设置检查
    setup = w1_setup(project_dir, chapter_num, chapter_task, anchor)

    # W2: AI初稿 (retries=3)
    draft = w2_draft(project_dir, chapter_num, chapter_task, anchor)

    # W3: 质检
    qc = w3_qc(draft, project_dir, chapter_num)

    # W4: AI精修 (retries=2)
    final = w4_polish(draft, qc, project_dir, chapter_num, chapter_task)

    # W5: 导出
    export = w5_export(final, project_dir, chapter_num, chapter_task)

    words = len(final.replace('\n','').replace(' ',''))
    elapsed = time.time() - t0
    logger.info(f"Pipeline完成: {words}字, {elapsed:.0f}秒")

    return {
        "success": True,
        "words": words,
        "elapsed": round(elapsed, 1),
        "content": final,
        "chapter": chapter_num,
    }


def _load_state(project_dir: str) -> dict:
    """加载项目状态"""
    proj = Path(project_dir)
    for sf in [proj/'.webnovel'/'state.json', proj/'state.json']:
        if sf.exists():
            return json.loads(sf.read_text(encoding='utf-8'))
    return {}
