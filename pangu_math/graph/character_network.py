"""
盘古数学 · 角色交互网络

从章节文本中提取角色共现网络，分析:
  - 节点中心度: 谁是本章/全局的核心角色
  - 交互强度: 两个角色之间的交互频率
  - 聚类系数: 角色群组 (三角关系/阵营)
  - 网络密度: 故事的角色复杂度
  - 结构洞: 本应有交互但没有的角色对 (可能是剧情遗漏)
  - 单章支配度: 某个角色是否过度支配了叙事

用法:
    cn = CharacterNetwork.from_text(chapter_text, characters=["林屿","陈柏","江予安","苏西"])
    print(f"中心角色: {cn.most_central()}")
    print(f"网络密度: {cn.density:.3f}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional


# ================================================================
# 中文人名提取 (简单规则)
# ================================================================

_CN_NAME_PATTERN = re.compile(r'[一-鿿]{2,3}(?=说道|问道|喊道|笑道|说道|想着|觉得|走到|看见|听见|发现|决定|突然|忽然|走了|来了|去了|站起来|坐下去)')

# 常见2字姓氏
_COMMON_SURNAMES = set("林陈江张王李赵刘周吴郑杨黄朱马何高罗郭梁宋谢韩唐于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文")


def extract_character_mentions(text: str, known_characters: List[str]) -> Dict[str, List[int]]:
    """
    从文本中提取已知角色的出现位置。

    Returns: {角色名: [出现位置列表]}
    """
    mentions: Dict[str, List[int]] = {name: [] for name in known_characters}

    for name in known_characters:
        pos = 0
        while True:
            idx = text.find(name, pos)
            if idx == -1:
                break
            mentions[name].append(idx)
            pos = idx + len(name)

    return mentions


# ================================================================
# 角色交互网络
# ================================================================

@dataclass
class CharacterNetwork:
    """角色交互网络"""
    characters: List[str] = field(default_factory=list)
    adjacency: Dict[Tuple[str, str], int] = field(default_factory=dict)  # (A,B)→共现次数
    mentions: Dict[str, int] = field(default_factory=dict)               # 出现次数
    total_paragraphs: int = 0

    # 网络指标
    density: float = 0.0
    centralities: Dict[str, float] = field(default_factory=dict)  # 角色中心度
    clustering_coeff: float = 0.0
    dominance: Dict[str, float] = field(default_factory=dict)     # 支配度

    @classmethod
    def from_text(cls, text: str, characters: List[str]):
        cn = cls(characters=characters)

        # 1. 切段落
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        cn.total_paragraphs = len(paragraphs)

        # 2. 每段检查角色共现
        for para in paragraphs:
            present: Set[str] = set()
            for name in characters:
                if name in para:
                    cn.mentions[name] = cn.mentions.get(name, 0) + para.count(name)
                    present.add(name)

            # 记录共现边
            names_list = sorted(present)
            for i in range(len(names_list)):
                for j in range(i + 1, len(names_list)):
                    key = (names_list[i], names_list[j])
                    cn.adjacency[key] = cn.adjacency.get(key, 0) + 1

        # 3. 计算网络指标
        n = len(characters)
        if n >= 2:
            # 密度: 实际边数 / 最大可能边数
            max_edges = n * (n - 1) / 2
            cn.density = len(cn.adjacency) / max_edges if max_edges > 0 else 0.0

            # 度中心性: 与多少个其他角色有交互
            for name in characters:
                degree = sum(1 for (a, b) in cn.adjacency
                              if (a == name or b == name))
                cn.centralities[name] = degree / max(n - 1, 1)

            # 支配度: 该角色的出现段落数 / 总段落数
            for name in characters:
                paras_with_char = sum(1 for p in paragraphs if name in p)
                cn.dominance[name] = paras_with_char / max(cn.total_paragraphs, 1)

            # 聚类系数 (简化: 有多少三角关系)
            triangles = 0
            possible_triangles = 0
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        a, b, c = characters[i], characters[j], characters[k]
                        has_ab = (a, b) in cn.adjacency or (b, a) in cn.adjacency
                        has_bc = (b, c) in cn.adjacency or (c, b) in cn.adjacency
                        has_ca = (c, a) in cn.adjacency or (a, c) in cn.adjacency
                        if has_ab and has_bc and has_ca:
                            triangles += 1
                        possible_triangles += 1
            cn.clustering_coeff = triangles / max(possible_triangles, 1)

        return cn

    def most_central(self) -> str:
        """返回中心度最高的角色"""
        if not self.centralities:
            return ""
        return max(self.centralities, key=self.centralities.get)

    def strongest_interaction(self) -> Optional[Tuple[str, str, int]]:
        """返回交互最强的角色对"""
        if not self.adjacency:
            return None
        (a, b), count = max(self.adjacency.items(), key=lambda x: x[1])
        return a, b, count

    def isolated_characters(self) -> List[str]:
        """返回被隔离的角色 (中心度为0)"""
        return [name for name in self.characters
                if self.centralities.get(name, 0.0) == 0.0]

    def excessive_dominance(self, threshold: float = 0.7) -> Optional[str]:
        """检测单角色过度支配 (可能的问题)"""
        for name, dom in self.dominance.items():
            if dom > threshold:
                return name
        return None

    def missing_interactions(self) -> List[Tuple[str, str]]:
        """检测应该有交互但没有的角色对"""
        missing = []
        n = len(self.characters)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = self.characters[i], self.characters[j]
                if (a, b) not in self.adjacency and (b, a) not in self.adjacency:
                    # 两者都有大量出现但没有共现 → 可能遗漏
                    mentions_a = self.mentions.get(a, 0)
                    mentions_b = self.mentions.get(b, 0)
                    if mentions_a > 0 and mentions_b > 0 and mentions_a + mentions_b > 5:
                        missing.append((a, b))
        return missing

    def summary(self) -> str:
        return (
            f"角色数={len(self.characters)} "
            f"中心={self.most_central()} "
            f"密度={self.density:.2f} "
            f"支配={max(self.dominance.values()):.0%}" if self.dominance else "..."
        )


def build_character_network(text: str, characters: List[str]) -> CharacterNetwork:
    """便捷函数"""
    return CharacterNetwork.from_text(text, characters)
