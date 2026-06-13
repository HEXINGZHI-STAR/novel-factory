"""
盘古数学 · 博弈论冲突建模

角色冲突的博弈模型:
  - 囚徒困境: 两个角色的信任博弈 → 合作/背叛收益矩阵
  - 智猪博弈: 强角色/弱角色的"搭便车"行为
  - 鹰鸽博弈: 对峙中的强硬vs妥协
  - 混合策略纳什均衡: 计算角色间的最优行为概率

用法:
    game = ConflictGame.from_prisoners_dilemma()
    nash = game.nash_equilibrium()
    print(f"角色A最优策略: 合作={nash['A_cooperate']:.1%}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ================================================================
# 收益矩阵
# ================================================================

@dataclass
class PayoffMatrix:
    """2×2博弈的收益矩阵"""
    name: str = ""  # 博弈名称

    # 收益: payoff[row_strategy][col_strategy] = (row_payoff, col_payoff)
    # 行玩家策略: [0]=合作/妥协, [1]=背叛/强硬
    # 列玩家策略: [0]=合作/妥协, [1]=背叛/强硬
    payoffs: List[List[Tuple[float, float]]] = field(default_factory=list)
    row_labels: List[str] = field(default_factory=lambda: ["合作", "背叛"])
    col_labels: List[str] = field(default_factory=lambda: ["合作", "背叛"])

    @classmethod
    def prisoners_dilemma(cls):
        """囚徒困境: 个体理性导致集体非理性"""
        return cls(
            name="囚徒困境",
            payoffs=[
                [(-1, -1), (-5,  0)],   # 都合作: 各判1年; A合作B背叛: A判5年B自由
                [( 0, -5), (-3, -3)],   # A背叛B合作: A自由B判5年; 都背叛: 各判3年
            ],
            row_labels=["保持沉默", "供出对方"],
            col_labels=["保持沉默", "供出对方"],
        )

    @classmethod
    def hawk_dove(cls, v: float = 0.6, c: float = 0.8):
        """
        鹰鸽博弈: 争资源时的强硬vs妥协。

        v = 资源价值, c = 冲突成本
        如果 c > v，则纯鹰策略不是均衡
        """
        return cls(
            name="鹰鸽博弈",
            payoffs=[
                [(v/2, v/2), (0,   v)],  # 都鸽: 平分; A鸽B鹰: A退出B全得
                [(v,   0), ((v-c)/2, (v-c)/2)],  # A鹰B鸽: A全得; 都鹰: 各得(v-c)/2
            ],
            row_labels=["鸽(妥协)", "鹰(强硬)"],
            col_labels=["鸽(妥协)", "鹰(强硬)"],
        )

    @classmethod
    def battle_of_sexes(cls):
        """性别战: 双方偏好不同协调博弈"""
        return cls(
            name="性别战",
            payoffs=[
                [(3, 2), (0, 0)],   # 都去A偏好的活动: A得3B得2
                [(0, 0), (2, 3)],   # 都去B偏好的活动: A得2B得3
            ],
            row_labels=["去对方喜欢的", "坚持自己"],
            col_labels=["去对方喜欢的", "坚持自己"],
        )

    @classmethod
    def chicken_game(cls):
        """胆小鬼博弈: 对峙中先让的人输"""
        return cls(
            name="胆小鬼博弈",
            payoffs=[
                [( 0,  0), (-1,  1)],   # 都让: 平局; A让B不让: A丢脸B赢
                [( 1, -1), (-5, -5)],   # A不让B让: A赢B丢脸; 都不让: 双输
            ],
            row_labels=["转向", "直冲"],
            col_labels=["转向", "直冲"],
        )


# ================================================================
# 冲突博弈分析器
# ================================================================

@dataclass
class ConflictGame:
    """角色冲突博弈分析器"""
    payoff: PayoffMatrix
    p_row: float = 0.5  # 行玩家的混合策略: P(选择策略0)
    p_col: float = 0.5  # 列玩家的混合策略: P(选择策略0)

    @classmethod
    def from_prisoners_dilemma(cls):
        return cls(payoff=PayoffMatrix.prisoners_dilemma())

    @classmethod
    def from_hawk_dove(cls, resource_value: float = 0.6, fight_cost: float = 0.8):
        return cls(payoff=PayoffMatrix.hawk_dove(resource_value, fight_cost))

    @classmethod
    def from_conflict_type(cls, conflict_type: str):
        """根据叙事冲突类型选择博弈"""
        types = {
            "信任": PayoffMatrix.prisoners_dilemma(),
            "对峙": PayoffMatrix.hawk_dove(),
            "协调": PayoffMatrix.battle_of_sexes(),
            "较量": PayoffMatrix.chicken_game(),
        }
        return cls(payoff=types.get(conflict_type, PayoffMatrix.prisoners_dilemma()))

    def nash_equilibrium(self) -> Dict:
        """
        计算混合策略纳什均衡。

        无差异条件:
        E_row(策略0) = E_row(策略1) → 解得 p_col
        E_col(策略0) = E_col(策略1) → 解得 p_row
        """
        P = self.payoff.payoffs

        # 行玩家无差异: p*P[0][0] + (1-p)*P[0][1] = p*P[1][0] + (1-p)*P[1][1]
        # 其中 p = P(列选策略0)
        a = P[0][0][0]  # row payoff when (0,0)
        b = P[0][1][0]  # row payoff when (0,1)
        c = P[1][0][0]  # row payoff when (1,0)
        d = P[1][1][0]  # row payoff when (1,1)

        denom = a - b - c + d
        if abs(denom) < 1e-9:
            p_col_eq = 0.5  # 退化情况
        else:
            p_col_eq = (d - b) / denom
            p_col_eq = max(0.0, min(1.0, p_col_eq))

        # 列玩家无差异: q*P[0][0] + (1-q)*P[1][0] = q*P[0][1] + (1-q)*P[1][1]
        # 其中 q = P(行选策略0)
        e = P[0][0][1]  # col payoff when (0,0)
        f = P[1][0][1]  # col payoff when (1,0)
        g = P[0][1][1]  # col payoff when (0,1)
        h = P[1][1][1]  # col payoff when (1,1)

        denom2 = e - f - g + h
        if abs(denom2) < 1e-9:
            p_row_eq = 0.5
        else:
            p_row_eq = (h - f) / denom2
            p_row_eq = max(0.0, min(1.0, p_row_eq))

        return {
            "row_cooperate_prob": round(p_row_eq, 3),
            "col_cooperate_prob": round(p_col_eq, 3),
            "row_betray_prob": round(1 - p_row_eq, 3),
            "col_betray_prob": round(1 - p_col_eq, 3),
            "expected_row_payoff": round(
                p_row_eq * (p_col_eq * a + (1 - p_col_eq) * b) +
                (1 - p_row_eq) * (p_col_eq * c + (1 - p_col_eq) * d), 3),
            "expected_col_payoff": round(
                p_col_eq * (p_row_eq * e + (1 - p_row_eq) * f) +
                (1 - p_col_eq) * (p_row_eq * g + (1 - p_row_eq) * h), 3),
        }

    def pure_nash(self) -> List[Tuple[int, int]]:
        """找出纯策略纳什均衡"""
        P = self.payoff.payoffs
        equilibria = []

        for i in range(2):  # row strategy
            for j in range(2):  # col strategy
                # 行玩家: 给定列策略j, 行选i是否最优?
                row_best = P[i][j][0] >= P[1 - i][j][0]
                # 列玩家: 给定行策略i, 列选j是否最优?
                col_best = P[i][j][1] >= P[i][1 - j][1]
                if row_best and col_best:
                    equilibria.append((i, j))

        return equilibria

    def drama_quality(self) -> float:
        """
        戏剧性评分 (0-1)。

        好的戏剧冲突应有:
        - 混合策略 (不是单调的"都合作"或"都背叛")
        - 适中的期望收益差 (不是一边倒)
        """
        nash = self.nash_equilibrium()
        # 混合策略越接近0.5越有戏剧性
        p_row = nash["row_cooperate_prob"]
        p_col = nash["col_cooperate_prob"]
        mix_score = 1.0 - 2 * abs(p_row - 0.5) * abs(p_col - 0.5)

        # 期望收益差
        payoff_diff = abs(
            nash["expected_row_payoff"] - nash["expected_col_payoff"])
        balance_score = max(0.0, 1.0 - payoff_diff / 3.0)

        pure_nash = self.pure_nash()
        # 混合策略均衡比纯策略更有戏剧性
        has_mixed = not any(i == j == 0 or i == j == 1
                             for i, j in pure_nash)

        drama = mix_score * 0.4 + balance_score * 0.3 + (0.3 if has_mixed else 0.0)
        return min(1.0, drama)

    def narrative_insight(self) -> str:
        """
        给出叙事建议: 基于博弈均衡推导角色行为逻辑。

        例如囚徒困境 → "角色A最优策略是背叛(70%)。这解释了为什么
        两个本该合作的人会互相出卖——不是因为他们坏，是因为博弈结构。"
        """
        nash = self.nash_equilibrium()
        p_row = nash["row_cooperate_prob"]
        p_col = nash["col_cooperate_prob"]

        if self.payoff.name == "囚徒困境":
            if p_row < 0.3 and p_col < 0.3:
                return ("双方都倾向于背叛。这并非道德缺陷——"
                       "在信息隔绝下，背叛是占优策略。"
                       "若要促成合作，需要引入'重复博弈'或'第三方惩罚'。")
            else:
                return ("存在一定合作可能。这个冲突的戏剧张力在于: "
                       "双方都知道合作更好，但都怕对方背叛。")
        elif self.payoff.name == "鹰鸽博弈":
            if nash["row_cooperate_prob"] > 0.5:
                return ("对峙偏向妥协。角色更倾向于'先让一步'——"
                       "这可能是因为冲突成本太高，双方都输不起。")
            else:
                return ("对峙中'鹰派'占优。但要注意: 如果双方都鹰，"
                       "结果对所有人都更糟。这是悲剧冲突的基础。")
        else:
            return f"混合策略均衡: A合作概率={p_row:.0%}, B合作概率={p_col:.0%}"


def plot_conflict_matrix(char_a: str, char_b: str,
                          conflict_type: str = "信任") -> ConflictGame:
    """便捷函数: 创建两个角色的冲突博弈"""
    return ConflictGame.from_conflict_type(conflict_type)
