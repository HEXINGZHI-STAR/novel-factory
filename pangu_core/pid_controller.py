"""
盘古 · PID 控制器 — Pipeline 自我调节

控制论在写作中的应用:
  - P(比例):  当前偏差有多大 → 立刻修正
  - I(积分):  偏差持续了多久 → 累积修正
  - D(微分):  偏差在加速还是减速 → 预判修正

应用场景:
  1. 对话率PID: 目标30%，当前8% → 自动提高W2温度
  2. 句均PID:   目标25字，当前15字 → 自动加长句法约束
  3. AI风险PID: 目标<0.3，当前0.5 → 自动触发加严润色

盘古适配:
  不需要人工选择工坊/快速模式、不需要手动调温度
  → Pipeline 写完一章 → PID 检测 → 自动调整下一章参数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class PIDController:
    """
    PID控制器。

    Kp: 比例系数 — 偏差多大时立刻反应
    Ki: 积分系数 — 偏差持续多久才反应 (防抖)
    Kd: 微分系数 — 偏差变化速率 (提前预判)
    """

    setpoint: float       # 目标值
    Kp: float = 1.0       # 比例增益
    Ki: float = 0.1       # 积分增益
    Kd: float = 0.05      # 微分增益

    # 内部状态
    _prev_error: float = 0.0
    _integral: float = 0.0
    _history: List[float] = field(default_factory=list)

    def update(self, measured_value: float) -> float:
        """
        输入当前测量值，返回修正量。

        Args:
            measured_value: 当前测量值 (如对话率0.08)

        Returns:
            correction: PID修正量 (如 +0.15 → 需要加温15%)
        """
        error = self.setpoint - measured_value

        # P: 比例项 — 越大越激进
        p_term = self.Kp * error

        # I: 积分项 — 累积偏差 (带限幅防积分饱和)
        self._integral += error
        self._integral = max(-3.0, min(3.0, self._integral))
        i_term = self.Ki * self._integral

        # D: 微分项 — 误差变化率
        d_term = self.Kd * (error - self._prev_error)

        # PID输出
        correction = p_term + i_term + d_term
        self._prev_error = error
        self._history.append(correction)

        return correction

    def reset(self):
        self._prev_error = 0.0
        self._integral = 0.0
        self._history.clear()


@dataclass
class PipelineSelfTuner:
    """
    Pipeline 自调节器 — 三个PID控制器联动。

    每章写完后自动调节下一章的参数。
    """

    # 三个PID
    dialogue_pid: PIDController = field(default_factory=lambda:
        PIDController(setpoint=0.25, Kp=1.5, Ki=0.1, Kd=0.05))

    sentence_pid: PIDController = field(default_factory=lambda:
        PIDController(setpoint=25.0, Kp=0.02, Ki=0.01, Kd=0.005))

    ai_risk_pid: PIDController = field(default_factory=lambda:
        PIDController(setpoint=0.25, Kp=2.0, Ki=0.15, Kd=0.08))

    # 当前参数
    current_temperature: float = 0.70
    current_mode: str = "workshop"
    consecutive_warnings: int = 0

    def tune(self, chapter_metrics: dict) -> dict:
        """
        根据章节指标自动调整下一章参数。

        Args:
            chapter_metrics: {"dialogue_ratio": 0.08, "mean_len": 15, "ai_risk": 0.5}

        Returns:
            调整后的参数和建议
        """
        adjustments = {}

        # 1. 对话率PID
        dia = chapter_metrics.get("dialogue_ratio", 0.0)
        dia_correction = self.dialogue_pid.update(dia)
        if abs(dia_correction) > 0.05:
            # 对话率低 → 加温
            new_temp = self.current_temperature + dia_correction * 0.3
            new_temp = max(0.5, min(0.9, new_temp))
            adjustments["temperature"] = round(new_temp, 2)
            adjustments["dia_correction"] = round(dia_correction, 3)

        # 2. 句均PID
        sl = chapter_metrics.get("mean_len", 20)
        sl_correction = self.sentence_pid.update(sl)
        if abs(sl_correction) > 2:
            adjustments["sentence_adjustment"] = (
                "加长句法约束" if sl_correction > 0 else "放松句法约束")

        # 3. AI风险PID
        ai = chapter_metrics.get("ai_risk", 0.3)
        ai_correction = self.ai_risk_pid.update(ai)
        if ai_correction > 0.1:
            self.consecutive_warnings += 1
        else:
            self.consecutive_warnings = max(0, self.consecutive_warnings - 1)

        # 4. 模式自适应
        if self.consecutive_warnings >= 2 and self.current_mode == "quick":
            self.current_mode = "workshop"
            adjustments["mode_change"] = "quick → workshop (连续质量警告)"
        elif self.consecutive_warnings == 0 and self.current_mode == "workshop":
            self.current_mode = "quick"
            adjustments["mode_change"] = "workshop → quick (质量恢复)"

        return adjustments

    def recommend_action(self) -> str:
        """基于PID状态推荐下一步行动"""
        if self.consecutive_warnings >= 3:
            return f"STOP — 连续{self.consecutive_warnings}章质量偏离，建议人工介入审查Pipeline参数"
        elif self.consecutive_warnings >= 1:
            return f"WATCH — 质量在偏离中，PID正在自动修正"
        else:
            return "CONTINUE — 质量稳定，PID控制器无干预"

    def summary(self) -> str:
        return (
            f"PID状态: 对话PID累积={self.dialogue_pid._integral:.2f}, "
            f"句法PID累积={self.sentence_pid._integral:.2f}, "
            f"AI风险PID累积={self.ai_risk_pid._integral:.2f}, "
            f"连续警告={self.consecutive_warnings}"
        )
