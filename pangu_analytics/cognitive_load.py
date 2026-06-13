"""
盘古 · 读者认知负荷模型

认知科学在写作中的应用:
  - 工作记忆: 读者能同时追踪的角色/伏笔/线索数量上限
  - 注意力分配: 开放循环(悬念)占用工作记忆，超负荷→弃书
  - 预期违反: 真人写作打破预测模式，AI永远满足预测→"AI味"的本质

关键数字 (来自认知心理学):
  - 工作记忆上限: 7±2个信息块 (Miller, 1956)
  - 开放悬念上限: 3个 (超出读者会忘记或焦虑弃书)
  - 注意力半衰期: ~15分钟无刺激→注意力漂移
  - 叙事可预测性: AI文本的预测性>85%，真人写作60-75%

盘古应用:
  - 检测章节是否"认知过载": 引入角色太多/伏笔太密→读者会迷失
  - 预测弃书点: 工作记忆超载的章节
  - 钩子轮换建议: 当前有3个开放悬念时→不要再加第四个
"""

from __future__ import annotations

import re
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class CognitiveLoadReport:
    """认知负荷分析报告"""
    total_characters: int = 0       # 本章出现的角色数
    new_characters: int = 0         # 新引入角色数
    open_loops: int = 0             # 开放悬念数
    information_density: float = 0.0  # 信息密度 (0-1)
    overload_risk: float = 0.0      # 超载风险 (0-1)
    dropout_risk: float = 0.0       # 弃书风险 (0-1)
    verdict: str = ""
    suggestions: List[str] = field(default_factory=list)


class CognitiveLoadAnalyzer:
    """
    读者认知负荷分析器。

    原理:
      - 工作记忆上限 ~7个信息块 → 超过则超载
      - 每个"新角色/新设定/新伏笔"占1个信息块
      - 开放悬念占2个信息块(因为读者持续在想它)
    """

    def analyze(self, text: str, known_characters: List[str],
                known_foreshadowing: int = 0) -> CognitiveLoadReport:
        """
        分析一章的认知负荷。

        Args:
            text: 章节正文
            known_characters: 已有角色列表 (前文已出现的)
            known_foreshadowing: 已有开放伏笔数

        Returns:
            CognitiveLoadReport
        """
        report = CognitiveLoadReport()

        # 1. 角色负荷
        present_chars = self._detect_characters(text, known_characters)
        report.total_characters = len(present_chars)
        report.new_characters = len([c for c in present_chars
                                      if c not in known_characters])

        # 2. 悬念/伏笔负荷
        # 检测本章开放的新悬念 (问号结尾/突发事件/未解之谜)
        new_loops = self._detect_open_loops(text)
        report.open_loops = known_foreshadowing + new_loops

        # 3. 信息密度 (每百字引入的新信息块数)
        total_chars = len(re.sub(r'[^一-鿿]', '', text))
        info_blocks = (report.new_characters * 2 + new_loops * 3 +
                       self._detect_new_rules(text))
        report.information_density = min(1.0,
            info_blocks / max(total_chars / 100, 1))

        # 4. 超载风险
        # 工作记忆负荷 = 角色数 + 新设定 + 开放悬念*2
        cognitive_load = (len(present_chars) * 0.5 +
                          report.new_characters * 1.5 +
                          report.open_loops * 2.0 +
                          self._detect_new_rules(text) * 1.0)
        report.overload_risk = min(1.0, cognitive_load / 12.0)

        # 5. 弃书风险 (超载 + 密度)
        report.dropout_risk = (report.overload_risk * 0.6 +
                                report.information_density * 0.4)

        # 6. 判定
        suggestions = []
        if report.overload_risk > 0.8:
            report.verdict = f"认知严重超载 (负荷{cognitive_load:.1f}/12)"
            suggestions.append("建议减少新角色或新设定的引入")
        elif report.overload_risk > 0.5:
            report.verdict = f"认知偏高 (负荷{cognitive_load:.1f}/12)，可接受"
        else:
            report.verdict = f"认知舒适 (负荷{cognitive_load:.1f}/12)"

        if report.open_loops > 4:
            suggestions.append(f"开放悬念{report.open_loops}个(上限3-4个)，建议本章回收至少1条")
        if report.new_characters > 3:
            suggestions.append(f"本章引入{report.new_characters}个新角色，建议分批引入")
        if report.information_density > 0.7:
            suggestions.append("信息密度过高，建议插入'呼吸段'(日常/对话)缓冲")

        report.suggestions = suggestions
        return report

    def _detect_characters(self, text: str, known: List[str]) -> List[str]:
        """检测文本中出现的角色 (基于已知角色名匹配)"""
        present = []
        for name in known:
            if name in text:
                present.append(name)
        # 简单检测新角色: 连续2-3个中文字符后跟"说/道/问/喊"
        new_names = set(re.findall(r'([一-鿿]{2,3})(?:说|道|问|喊|叫|笑|怒)', text))
        for name in new_names:
            if name not in known and name not in present:
                present.append(name)
        return present

    def _detect_open_loops(self, text: str) -> int:
        """检测本章新开放多少悬念/伏笔"""
        loops = 0
        # 问号结尾 = 悬念
        question_ends = len(re.findall(r'[？?]\s*$', text[-500:])) if len(text) > 500 else 0
        loops += question_ends

        # 突发事件 = 新展开
        sudden_events = len(re.findall(r'(?:突然|忽然|竟然|居然|不料|谁知)', text[:1000]))
        loops += min(sudden_events, 3)

        # 未解之谜 = 新伏笔
        mystery_markers = len(re.findall(r'(?:不知道|不确定|未必|难道|莫非)', text[:1000]))
        loops += min(mystery_markers, 3)

        return min(loops, 10)

    def _detect_new_rules(self, text: str) -> int:
        """检测本章引入多少新设定/规则"""
        rules = 0
        # 检测设定引入型句式
        rules += len(re.findall(r'(?:原来|其实|之所以|是因为|规则|定律)', text[:2000]))
        return min(rules, 5)
