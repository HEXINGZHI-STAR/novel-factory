"""
盘古分析 · 内部控制框架

基于COSO内部控制框架的写作质量保证体系:

  1. 控制环境: 模式规则 + 合同链 + 硬约束
  2. 风险评估: 设定矛盾概率 + 角色OOC风险 + 伏笔过期风险
  3. 控制活动: Write Gates (prewrite/precommit/postcommit)
  4. 信息与沟通: 审查报告 + state.json同步
  5. 监控: 质量趋势 + 偏差分析 + 实时告警

用法:
    icf = InternalControlFramework(project_dir="...")
    report = icf.run_full_audit(chapter_num=1)
    print(f"控制有效: {report['effective']}")
    for finding in report['findings']:
        print(f"  [{finding['severity']}] {finding['message']}")
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path


# ================================================================
# 风险矩阵
# ================================================================

RISK_MATRIX = {
    # (影响, 可能性) → 风险等级
    ("critical", "high"):    "RED",
    ("critical", "medium"):  "RED",
    ("critical", "low"):     "ORANGE",
    ("major",    "high"):    "RED",
    ("major",    "medium"):  "ORANGE",
    ("major",    "low"):     "YELLOW",
    ("minor",    "high"):    "ORANGE",
    ("minor",    "medium"):  "YELLOW",
    ("minor",    "low"):     "GREEN",
    ("negligible","high"):   "YELLOW",
    ("negligible","medium"): "GREEN",
    ("negligible","low"):    "GREEN",
}


@dataclass
class RiskAssessment:
    """风险评估矩阵"""
    risks: List[Dict] = field(default_factory=list)

    def add_risk(self, name: str, impact: str, likelihood: str,
                  description: str, control: str):
        risk_level = RISK_MATRIX.get((impact, likelihood), "YELLOW")
        self.risks.append({
            "name": name,
            "impact": impact,
            "likelihood": likelihood,
            "risk_level": risk_level,
            "description": description,
            "existing_control": control,
        })

    def high_risks(self) -> List[Dict]:
        return [r for r in self.risks if r["risk_level"] in ("RED", "ORANGE")]

    def risk_score(self) -> float:
        """综合风险评分 (0=无风险 1=极高)"""
        weights = {"RED": 1.0, "ORANGE": 0.6, "YELLOW": 0.3, "GREEN": 0.1}
        if not self.risks:
            return 0.0
        return sum(weights.get(r["risk_level"], 0.3) for r in self.risks) / len(self.risks)

    def summary(self) -> str:
        levels = {}
        for r in self.risks:
            levels[r["risk_level"]] = levels.get(r["risk_level"], 0) + 1
        return f"风险: RED={levels.get('RED',0)} ORANGE={levels.get('ORANGE',0)} YELLOW={levels.get('YELLOW',0)} GREEN={levels.get('GREEN',0)}"


# ================================================================
# 内部控制框架
# ================================================================

@dataclass
class InternalControlFramework:
    """COSO内部控制框架 (写作适配版)"""

    project_dir: str = ""
    _state: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.project_dir:
            state_path = Path(self.project_dir) / ".webnovel" / "state.json"
            # fallback for different project structures
            if not state_path.exists():
                state_path = Path(self.project_dir) / "state.json"
            if state_path.exists():
                try:
                    self._state = json.loads(state_path.read_text(encoding="utf-8"))
                except Exception:
                    self._state = {}

    def assess_control_environment(self) -> Dict:
        """
        C1: 控制环境评估。

        检查: 模式规则是否完整、合同链是否就绪、硬约束是否明确
        """
        issues = []

        # 模式规则检查
        mode = self._state.get("project_info", {}).get("genre", "general")
        if not mode or mode == "":
            issues.append("模式未设定 → 缺少创作约束基准")

        # 硬约束检查
        setting_log = self._state.get("setting_log", {}).get("locked_rules", [])
        if len(setting_log) < 2:
            issues.append("locked_rules不足 → 控制环境薄弱")

        # 角色设定检查
        chars = self._state.get("characters", {})
        if not chars or not chars.get("protagonist", {}).get("name"):
            issues.append("主角未设定 → OOC检测基准缺失")

        return {
            "effective": len(issues) == 0,
            "issues": issues,
            "mode": mode,
            "rule_count": len(setting_log),
        }

    def assess_risk(self) -> RiskAssessment:
        """C2: 风险评估"""
        ra = RiskAssessment()

        # 设定矛盾风险
        setting_log = self._state.get("setting_log", {}).get("locked_rules", [])
        ra.add_risk(
            "设定矛盾", "critical", "medium",
            "新章节与已锁定设定产生矛盾",
            f"Write Gates precommit check ({len(setting_log)} rules)",
        )

        # 角色OOC风险
        ra.add_risk(
            "角色OOC", "major", "high",
            "角色行为偏离设定性格底线",
            "主角卡OOC警戒 + 性格一致性评分",
        )

        # 伏笔遗忘风险
        foreshadow = self._state.get("foreshadowing", {}).get("active_threads", [])
        open_count = sum(1 for t in foreshadow if t.get("status") == "open")
        ra.add_risk(
            "伏笔遗忘", "major", "high" if open_count > 3 else "medium",
            f"活跃伏笔{open_count}条，未及时推进或回收",
            "伏笔年龄检测 + 紧急度评分",
        )

        # AI味风险
        ra.add_risk(
            "AI味文本", "minor", "medium",
            "生成文本包含模板化句式",
            "De-AI规则200+词库 + 连续短句检测",
        )

        return ra

    def test_control_activities(self, chapter_num: int) -> Dict:
        """C3: 控制活动测试"""
        results = {
            "prewrite_gate": "NOT_RUN",
            "precommit_gate": "NOT_RUN",
            "postcommit_gate": "NOT_RUN",
            "review_checkpoint": "NOT_FOUND",
        }

        # 检查审查检查点
        checkpoints = self._state.get("review_checkpoints", [])
        for cp in checkpoints:
            if cp.get("chapter") == chapter_num:
                results["review_checkpoint"] = "PASS" if cp.get("passed") else "FAIL"
                break

        return results

    def run_full_audit(self, chapter_num: int = 1) -> Dict[str, Any]:
        """执行完整内部控制审计"""
        findings = []

        # C1: 控制环境
        env = self.assess_control_environment()
        if not env["effective"]:
            for issue in env["issues"]:
                findings.append({"severity": "blocker", "component": "C1",
                                  "message": issue})

        # C2: 风险评估
        risk = self.assess_risk()
        for r in risk.high_risks():
            findings.append({"severity": "warning", "component": "C2",
                              "message": f"[{r['risk_level']}] {r['name']}: {r['description']}"})

        # C3: 控制活动
        controls = self.test_control_activities(chapter_num)

        # C4: 质量监控
        checkpoints = self._state.get("review_checkpoints", [])
        scores = [cp.get("score", 0) for cp in checkpoints]
        quality_trend = "stable"
        if len(scores) >= 3:
            recent = scores[-3:]
            if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
                quality_trend = "improving"
            elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                quality_trend = "declining"
                findings.append({"severity": "warning", "component": "C4",
                                  "message": "质量连续下降趋势——需要管理干预"})

        return {
            "effective": len([f for f in findings if f["severity"] == "blocker"]) == 0,
            "findings": findings,
            "risk_level": risk.risk_score(),
            "quality_trend": quality_trend,
            "controls": controls,
            "recommendation": self._audit_opinion(findings, risk.risk_score()),
        }

    def _audit_opinion(self, findings: List[Dict], risk_score: float) -> str:
        blockers = [f for f in findings if f["severity"] == "blocker"]
        warnings = [f for f in findings if f["severity"] == "warning"]

        if blockers:
            return f"ADVERSE — {len(blockers)}个阻断项，控制无效"
        elif risk_score > 0.6:
            return f"QUALIFIED — {len(warnings)}个关注项，控制存在重大缺陷"
        elif risk_score > 0.3:
            return f"QUALIFIED — {len(warnings)}个建议项，控制有待改进"
        elif warnings:
            return "UNQUALIFIED_EMPHASIS — 控制有效，附强调事项"
        else:
            return "UNQUALIFIED — 控制有效，无缺陷"


@dataclass
class QualityAudit:
    """质量审计跟踪"""
    project_dir: str = ""
    audit_log: List[Dict] = field(default_factory=list)

    def log_audit(self, chapter_num: int, findings: List[Dict],
                   auditor: str = "PanguICF"):
        self.audit_log.append({
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "chapter": chapter_num,
            "findings_count": len(findings),
            "auditor": auditor,
        })

    def audit_trail_summary(self) -> str:
        if not self.audit_log:
            return "无审计记录"
        return f"共{len(self.audit_log)}条审计记录，最近: Ch{self.audit_log[-1]['chapter']}"
