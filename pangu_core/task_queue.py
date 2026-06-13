"""
盘古 · 任务队列 (基于Huey)

替代批量写章的 for+time.sleep 模式:
  - 任务入队后立即返回，不阻塞
  - 失败自动重试 (最多3次)
  - 支持定时调度 (延迟N秒执行)
  - SQLite零配置，无需Redis

用法:
    # 启动 worker (新终端):
    python -m huey.bin.huey_consumer pangu_core.task_queue.huey

    # 入队任务:
    from pangu_core.task_queue import queue_chapter
    queue_chapter("开门见尸", 5)
    queue_chapter("开门见尸", 6)
    # → worker 自动依次执行
"""

from __future__ import annotations

from pathlib import Path
from huey import SqliteHuey, crontab

BASE = Path(__file__).resolve().parent.parent
huey = SqliteHuey('pangu', filename=str(BASE / 'knowledge' / 'task_queue.db'))


@huey.task(retries=3, retry_delay=10)
def write_chapter_task(project_name: str, chapter_num: int,
                        mode: str = "workshop", task: str = ""):
    """
    写章任务。失败自动重试3次，间隔10秒。

    Worker 会自动执行，不阻塞调用方。
    """
    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config; reset_config()
    from pangu_core.pipeline import WritingPipeline, PipelineConfig
    from pangu_workshop import find_project
    from pangu_workshop_smart import SmartStrategyEngine

    proj = find_project(project_name)
    if not proj:
        return {"error": f"项目 '{project_name}' 未找到", "chapter": chapter_num}

    if not task:
        engine = SmartStrategyEngine(proj)
        task = engine.generate_chapter_task(chapter_num)

    state = {}
    for sf in [proj/'.webnovel'/'state.json', proj/'state.json']:
        if sf.exists():
            import json
            state = json.loads(sf.read_text(encoding='utf-8'))

    use_workshop = mode == "workshop"
    config = (PipelineConfig.from_workshop_mode if use_workshop
              else PipelineConfig.from_quick_mode)(
        project_dir=str(proj), chapter=chapter_num, task=task,
        mode=state.get('project_info', {}).get('genre', 'general'),
        platform=state.get('project_info', {}).get('platform', 'qimao'),
    )

    result = WritingPipeline(config).run()
    wc = len(result.chapter_content.replace('\n', '').replace(' ', ''))

    if result.success and wc > 500:
        (proj/'正文'/f'第{chapter_num}章.txt').write_text(
            result.chapter_content, encoding='utf-8')

    return {
        "project": project_name, "chapter": chapter_num,
        "success": result.success, "words": wc,
        "errors": len(result.errors),
    }


@huey.periodic_task(crontab(minute='0', hour='*/4'))
def health_check():
    """每4小时自检: 确保任务队列正常"""
    return {"status": "ok", "queue_size": len(huey)}


def queue_chapter(project: str, chapter: int,
                   mode: str = "workshop", delay: int = 0):
    """
    入队一章。

    Args:
        delay: 延迟秒数 (用于分散API请求)
    """
    if delay > 0:
        return write_chapter_task.schedule(
            args=(project, chapter, mode, ''),
            delay=delay)
    return write_chapter_task(project, chapter, mode, '')


def queue_batch(project: str, from_ch: int, to_ch: int,
                 mode: str = "workshop", delay: int = 5):
    """
    批量入队。每章间隔 delay 秒，避免API限流。

    Returns:
        任务列表
    """
    tasks = []
    for ch in range(from_ch, to_ch + 1):
        t = write_chapter_task.schedule(
            args=(project, ch, mode, ''),
            delay=(ch - from_ch) * delay)
        tasks.append({"chapter": ch, "task_id": str(t)})
    return tasks
