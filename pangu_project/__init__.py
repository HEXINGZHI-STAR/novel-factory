"""
盘古项目管理 (PanguProject)

管理学在写作项目管理中的应用:
  - gantt:        写作甘特图 — 卷/章的时间线与里程碑
  - kpi:          写作KPI仪表盘 — 质量/速度/成本/读者四维指标
  - resource:     资源分配 — 时间/API预算/修改次数的优化配置
"""

from .gantt import WritingGantt, ProjectMilestone
from .kpi import WritingKPI, KPIDashboard

__all__ = [
    "WritingGantt", "ProjectMilestone",
    "WritingKPI", "KPIDashboard",
]
