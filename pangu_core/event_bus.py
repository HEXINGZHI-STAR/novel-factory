"""
盘古 · 事件总线 (基于Whistle)

发布-订阅模式替代手动调用链。
Pipeline写完一章后发布事件，所有订阅者自动触发。

用法:
  from pangu_core.event_bus import bus, ChapterWritten
  bus.dispatch(ChapterWritten(project="开门见尸", chapter=5, words=2500))
"""

from __future__ import annotations

from whistle import EventDispatcher, Event


# 全局事件总线
bus = EventDispatcher()


# ================================================================
# 事件定义
# ================================================================

class ChapterWritten(Event):
    """章节写完事件"""
    name = "chapter_written"


class PipelineError(Event):
    """Pipeline异常事件"""
    name = "pipeline_error"


# ================================================================
# 订阅者注册
# ================================================================

@bus.listen(ChapterWritten)
def on_chapter_written(event: ChapterWritten):
    """章节写完 → 触发全部后处理"""
    data = event.__dict__
    project = data.get("project", "")
    chapter = data.get("chapter", 0)
    content = data.get("content", "")
    state = data.get("state", {})

    # 1. DB写入
    try:
        from .state_sync import StateSync
        from .db import get_db
        db = get_db()
        state_sync = StateSync(project, db)
        state_sync.sync_to_db(state)
        print("  [DB] OK")
    except Exception as e:
        print(f"  [DB] FAIL: {e}")

    # 2. 投影
    try:
        from .projection import run_projections
        info = state.get("project_info", {})
        mode = info.get("genre", "general")
        run_projections(project, chapter, content, "", mode)
        print("  [投影] OK")
    except Exception:
        pass

    # 3. 记忆提交
    try:
        from .memory_layers import PanguMemoryOrchestrator
        from pathlib import Path
        orchestrator = PanguMemoryOrchestrator(Path(project))
        orchestrator.commit_memory(chapter, content)
        print("  [记忆] OK")
    except Exception:
        pass

    # 4. 情报分析
    try:
        from pangu_intelligence import analyze_chapter
        ci = analyze_chapter(project, chapter, content, state)
        if ci:
            print(f"  [情报] {ci.summary()[:60]}")
    except Exception:
        pass

    # 5. KPI
    try:
        from pangu_project.kpi import KPIDashboard
        words = data.get("words", 0)
        dash = KPIDashboard(project)
        dash.record(chapter, score=80, words=words, cost=0.003, time_h=0.5)
        print(f"  [KPI] {dash.overall_score():.0f}/100")
    except Exception:
        pass


@bus.listen(PipelineError)
def on_pipeline_error(event: PipelineError):
    """Pipeline异常 → 记录"""
    data = event.__dict__
    print(f"  [!] Pipeline错误: {data.get('project','')} "
          f"Ch{data.get('chapter',0)}: {data.get('error','')[:100]}")
