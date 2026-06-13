"""
盘古数学 · 图论层

模块:
  - character_network:  角色交互网络分析
  - foreshadow_graph:   伏笔网络分析
  - plot_dag:           情节因果DAG
"""

from .character_network import CharacterNetwork, build_character_network
from .foreshadow_graph import ForeshadowGraph, build_foreshadow_graph

__all__ = [
    "CharacterNetwork", "build_character_network",
    "ForeshadowGraph", "build_foreshadow_graph",
]
