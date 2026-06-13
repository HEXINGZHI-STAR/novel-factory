"""
盘古分析层 (PanguAnalytics)

经济学 + 管理会计 + 财务会计 + 内部控制的写作应用:
  - economics:     供需分析、边际效用、机会成本、市场均衡
  - accounting:    成本归集、预算差异、盈亏平衡、资产估值
  - control:       COSO内控框架、风险矩阵、审计轨迹、合规检查
"""

from .economics import MarketAnalyzer, WritingEconomics
from .accounting import CostAccounting, BudgetVariance
from .control import InternalControlFramework, QualityAudit

__all__ = [
    "MarketAnalyzer", "WritingEconomics",
    "CostAccounting", "BudgetVariance",
    "InternalControlFramework", "QualityAudit",
]
