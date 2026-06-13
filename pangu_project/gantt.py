"""
盘古项目 · 写作甘特图

将整个写作项目可视化为甘特图:
  - 3卷 × 4章 = 12个任务条
  - 里程碑: 每卷完成、审查节点、发布节点
  - 依赖关系: 第N章→第N+1章 (串行依赖)
  - 关键路径: 核心创作链路的瓶颈识别

用法:
    gantt = WritingGantt(project_name="消失的第四个人", chapters=12, volumes=3)
    gantt.schedule(start_date="2026-06-12")
    print(gantt.to_ascii())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta


# ================================================================
# 里程碑
# ================================================================

@dataclass
class ProjectMilestone:
    """项目里程碑"""
    name: str
    chapter: int
    type: str = "chapter"  # chapter / review / release / volume_end
    planned_date: str = ""
    actual_date: str = ""
    status: str = "pending"  # pending / completed / delayed

    def is_late(self) -> bool:
        return self.status == "delayed" or (
            self.actual_date and self.planned_date and
            self.actual_date > self.planned_date
        )


# ================================================================
# 写作甘特图
# ================================================================

@dataclass
class WritingGantt:
    """写作项目甘特图"""

    project_name: str = ""
    total_chapters: int = 12
    volumes: int = 3
    chapters_per_volume: int = 4

    # 时间参数
    days_per_chapter: float = 2.0     # 每章计划天数
    days_per_review: float = 0.5      # 每章审查天数
    buffer_days: float = 3.0          # 卷间缓冲

    milestones: List[ProjectMilestone] = field(default_factory=list)
    start_date: str = ""

    def schedule(self, start_date: str = "2026-06-12"):
        """自动生成写作计划"""
        self.start_date = start_date
        current = datetime.strptime(start_date, "%Y-%m-%d")

        for ch in range(1, self.total_chapters + 1):
            # 写章
            self.milestones.append(ProjectMilestone(
                name=f"第{ch}章-起草",
                chapter=ch,
                type="chapter",
                planned_date=current.strftime("%Y-%m-%d"),
            ))
            current += timedelta(days=self.days_per_chapter)

            # 审查
            self.milestones.append(ProjectMilestone(
                name=f"第{ch}章-审查",
                chapter=ch,
                type="review",
                planned_date=current.strftime("%Y-%m-%d"),
            ))
            current += timedelta(days=self.days_per_review)

            # 卷末里程碑
            if ch % self.chapters_per_volume == 0 and ch < self.total_chapters:
                vol = ch // self.chapters_per_volume
                self.milestones.append(ProjectMilestone(
                    name=f"第{vol}卷完成",
                    chapter=ch,
                    type="volume_end",
                    planned_date=current.strftime("%Y-%m-%d"),
                ))
                current += timedelta(days=self.buffer_days)

        # 最终发布
        self.milestones.append(ProjectMilestone(
            name="全本完成",
            chapter=self.total_chapters,
            type="release",
            planned_date=current.strftime("%Y-%m-%d"),
        ))

    def complete_chapter(self, chapter_num: int, actual_date: str = None):
        """标记一章完成"""
        actual = actual_date or datetime.now().strftime("%Y-%m-%d")
        for ms in self.milestones:
            if ms.chapter == chapter_num:
                ms.status = "completed"
                ms.actual_date = actual

    def progress(self) -> float:
        """完成进度 (0-1)"""
        completed = sum(1 for ms in self.milestones
                         if ms.status == "completed" and ms.type == "chapter")
        return completed / self.total_chapters

    def critical_path(self) -> List[str]:
        """识别关键路径上的延迟任务"""
        delayed = []
        for ms in self.milestones:
            if ms.is_late():
                delayed.append(ms.name)
        return delayed

    def estimated_completion(self) -> str:
        """预计完成日期"""
        if not self.start_date:
            return "未计划"
        # 剩余章数 × 每章天数 + 缓冲
        remaining = self.total_chapters - int(self.progress() * self.total_chapters)
        remaining_days = remaining * (self.days_per_chapter + self.days_per_review)
        remaining_days += (self.volumes - self.progress() * self.volumes) * self.buffer_days
        end = datetime.now() + timedelta(days=remaining_days)
        return end.strftime("%Y-%m-%d")

    def to_ascii(self, width: int = 60) -> str:
        """ASCII甘特图"""
        if not self.milestones:
            return "无计划"

        lines = [f"{self.project_name} 写作甘特图", "=" * width]
        start = datetime.strptime(self.start_date, "%Y-%m-%d") if self.start_date else datetime.now()
        total_days = (datetime.strptime(self.milestones[-1].planned_date, "%Y-%m-%d") - start).days
        scale = width / max(total_days, 1)

        for ms in self.milestones[:20]:  # 显示前20条
            offset = (datetime.strptime(ms.planned_date, "%Y-%m-%d") - start).days
            bar = "█" if ms.status == "completed" else "▓" if ms.status == "delayed" else "░"
            bar_len = max(1, int(3 * scale))
            prefix = " " * max(0, int(offset * scale))
            status_mark = "✓" if ms.status == "completed" else "·"
            lines.append(f"{prefix}{bar * bar_len} {status_mark} {ms.name} ({ms.planned_date})")

        return "\n".join(lines)
