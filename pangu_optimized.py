#!/usr/bin/env python3
"""
盘古AI · 入口 (DEPRECATED — 已瘦身至 ≤90行)

原 ~3000 行功能已全部迁移至:
  - pangu_core/pipeline.py        WritingPipeline + W0-W5 Stages
  - pangu_core/prompt_builder.py   17层Prompt注入链
  - pangu_core/config.py           双Provider配置
  - pangu_core/ai_client.py        多Provider AI调用
  - pangu_workshop.py              统一工作室入口 (推荐)
  - pangu_workshop_smart.py        智能工作室
  - pangu_intelligence.py          情报中心

推荐使用:
  python pangu_workshop.py write --project "项目名" --chapter N
  python pangu_workshop_smart.py diagnose --project "项目名"
"""

from __future__ import annotations

import sys, json, warnings
from pathlib import Path
from datetime import datetime

warnings.warn(
    "pangu_optimized.py is DEPRECATED. Use pangu_workshop.py instead.",
    DeprecationWarning, stacklevel=2,
)

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 向后兼容: 重导出核心API
from pangu_core.config import get_config, Config
from pangu_core.ai_client import call_ai, AIClient
from pangu_core.pipeline import WritingPipeline, PipelineConfig, PipelineResult


def create_project_quick(title: str, genre: str = "general",
                          platform: str = "qimao", target_chapters: int = 12,
                          core_selling_points: str = ""):
    """创建项目 (向后兼容)"""
    projects_dir = BASE_DIR / "projects"
    proj_dir = projects_dir / title
    proj_dir.mkdir(parents=True, exist_ok=True)
    webnovel = proj_dir / ".webnovel"
    webnovel.mkdir(exist_ok=True)
    for d in ["大纲", "设定集", "正文", "审查报告"]:
        (proj_dir / d).mkdir(exist_ok=True)
    state = {
        "project_info": {
            "title": title, "genre": genre, "platform": platform,
            "target_chapters": target_chapters, "target_words": target_chapters * 2500,
            "core_selling_points": core_selling_points,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        },
        "progress": {"current_chapter": 0, "total_words": 0},
        "characters": {}, "foreshadowing": {"active_threads": []},
        "setting_log": {"locked_rules": []}, "review_checkpoints": [], "chapter_meta": {},
    }
    (webnovel / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    (proj_dir / "大纲" / "总纲.md").write_text(
        f"# {title}\n\n## 故事一句话\n\n## 核心主线\n", encoding="utf-8")
    (proj_dir / "设定集" / "主角卡.md").write_text(
        "# 主角卡\n\n- 姓名：\n- 身份：\n", encoding="utf-8")
    print(f"[OK] 项目已创建: {proj_dir}")
    return str(proj_dir)


if __name__ == "__main__":
    print("盘古AI v2.0 — pangu_workshop.py 是唯一入口")
    print("  python pangu_workshop.py write --project <项目> --chapter <N>")
