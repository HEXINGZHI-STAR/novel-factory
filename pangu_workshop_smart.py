"""
盘古智能工作室 (Smart Workshop)

在 pangu_workshop.py 基础上叠加数学决策层:
  写前: 自动分析项目状态 → 推荐最优策略
  写中: 批量写章时动态调参 → 质量反馈闭环
  写后: 情报驱动下一章建议

用法:
    # 智能写章 (自动选模式/调参)
    python pangu_workshop_smart.py write -p "逻辑之下" -c 7

    # 智能批量 (每章写完后自动调参)
    python pangu_workshop_smart.py batch -p "逻辑之下" --from 7 --to 10

    # 项目诊断 (全维度分析 + 策略建议)
    python pangu_workshop_smart.py diagnose -p "逻辑之下"
"""

from __future__ import annotations

import sys
import json
import time
import math
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


# ================================================================
# 写作策略
# ================================================================

@dataclass
class WritingStrategy:
    """最优写作策略"""
    mode: str = "quick"              # quick / workshop
    target_words: int = 2300
    temperature: float = 0.7
    hook_type: str = "悬念"          # 推荐钩子类型
    release_type: Optional[str] = None  # 情绪释放方式
    opening_boost: bool = False      # 是否开篇加强
    use_claude_w4: bool = False      # W4是否用Claude精修
    priority_dimensions: List[str] = field(default_factory=list)  # 重点关注的维度


# ================================================================
# 智能策略引擎
# ================================================================

class SmartStrategyEngine:
    """
    写作前分析引擎: 基于项目状态 + 数学模型 → 最优策略。
    """

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.state = self._load_state()
        self.chapter_histories: Dict[int, dict] = {}  # 前章情报缓存

    def _load_state(self) -> dict:
        for sf in [
            self.project_dir / ".webnovel" / "state.json",
            self.project_dir / "state.json",
        ]:
            if sf.exists():
                return json.loads(sf.read_text(encoding="utf-8"))
        return {}

    def _load_previous_intelligence(self, chapter_num: int) -> Optional[dict]:
        """加载前章情报"""
        if chapter_num in self.chapter_histories:
            return self.chapter_histories[chapter_num]

        intel_file = (
            self.project_dir / ".webnovel" / "intelligence" /
            f"chapter_{chapter_num:04d}.json"
        )
        if intel_file.exists():
            data = json.loads(intel_file.read_text(encoding="utf-8"))
            self.chapter_histories[chapter_num] = data
            return data
        return None

    def recommend_strategy(self, chapter_num: int) -> WritingStrategy:
        """
        为指定章节推荐最优写作策略。

        决策依据:
        - 章节位置 (开篇/过渡/高潮/终章)
        - 前章质量分数和趋势
        - 伏笔紧迫度
        - AI风险是否偏高
        - 平台特性
        """
    def check_write_gate(self, chapter_num: int) -> dict:
        """
        Openwrite风格上下文门禁——写前检查，防止长篇小说内容漂移。
        返回 {"passed": bool, "issues": [], "warnings": []}
        """
        issues = []
        warnings = []
        info = self.state.get("project_info", {})
        total_ch = info.get("target_chapters", 100)
        current_ch = self.state.get("progress", {}).get("current_chapter", 0)

        # 1. 大纲覆盖检查 (支持 src/ 和 大纲/ 两种路径)
        outline = (self.project_dir / "src" / "总纲.md"
                   if (self.project_dir / "src" / "总纲.md").exists()
                   else self.project_dir / "大纲" / "总纲.md")
        if outline.exists():
            content = outline.read_text(encoding="utf-8")
            if f"第{chapter_num}章" not in content and f"Ch{chapter_num}" not in content:
                warnings.append(f"总纲中未找到第{chapter_num}章规划，可能内容漂移")
        else:
            issues.append("总纲.md 缺失——创建 src/总纲.md 或 大纲/总纲.md")

        # 2. 前章钩子衔接检查 (≥5章时)
        if chapter_num > 5:
            prev_intel = self._load_previous_intelligence(chapter_num - 1)
            if prev_intel and prev_intel.get("quality_posterior", 0.8) < 0.5:
                warnings.append(f"前章质量偏低({prev_intel['quality_posterior']:.0%})，建议先修订再继续")

        # 3. 伏笔过期检查
        foreshadow = self.state.get("foreshadowing", {}).get("active_threads", [])
        expired = [t for t in foreshadow if isinstance(t, dict)
                   and t.get("status") == "open"
                   and chapter_num - t.get("planted_ch", 0) > 5]
        if expired:
            warnings.append(f"有{len(expired)}条伏笔超过5章未推进，建议本章回收")

        # 4. 设定充分性检查
        locked_rules = self.state.get("setting_log", {}).get("locked_rules", [])
        if chapter_num > 20 and len(locked_rules) < 10:
            warnings.append("长篇连载设定不足，建议补充世界观规则")

        # 5. 角色完整性
        chars = self.state.get("characters", {})
        protag = chars.get("protagonist", {}) if isinstance(chars, dict) else {}
        if not protag.get("name"):
            warnings.append("主角未设定，OOC风险")

        passed = len(issues) == 0
        return {"passed": passed, "issues": issues, "warnings": warnings,
                "chapter": chapter_num, "total_chapters": total_ch}

    def pre_write_platform_check(self, chapter_num: int) -> dict:
        """
        写前平台优势分析——联动 TrendRadar + StrategyEngine。
        在Pipeline执行前调用，输出平台最优参数。
        """
        info = self.state.get("project_info", {})
        platform = info.get("platform", "qimao")
        genre = info.get("genre", "general")

        # 1. 趋势分析
        from pangu_analytics.trend_radar import TrendRadar
        radar = TrendRadar()
        radar.add_from_platform_observation(platform, [
            (genre, 60, 80),  # 当前题材供需
        ])
        trend = radar.recommend_genre(platform)

        # 2. 策略推荐
        strategy = self.recommend_strategy(chapter_num)

        # 3. 平台特定参数
        platform_params = {
            "qimao": {"dia_pct": 0.30, "words_min": 2000, "hook_type": "强钩子","段落":"≤3行"},
            "qidian": {"dia_pct": 0.25, "words_min": 2500, "hook_type": "长线钩子","段落":"允许长段"},
            "fanqie": {"dia_pct": 0.35, "words_min": 1800, "hook_type": "爽点密集","段落":"1-2句"},
            "zhihu": {"dia_pct": 0.15, "words_min": 2000, "hook_type": "留白收尾","段落":"短段"},
        }
        pp = platform_params.get(platform, platform_params["qimao"])

        # 4. W4模式匹配
        from pangu_core.prompt_builder import _get_w4_mode_rules
        w4_rules = _get_w4_mode_rules(genre)

        return {
            "platform": platform, "genre": genre,
            "trend_opportunity": trend.get("opportunity_score", 50),
            "recommended_genre": trend.get("recommended_genre", genre),
            "strategy": {
                "mode": strategy.mode,
                "words": strategy.target_words,
                "temperature": strategy.temperature,
                "hook": strategy.hook_type,
                "release": strategy.release_type,
                "use_claude": strategy.use_claude_w4,
            },
            "platform_requires": pp,
            "w4_mode": genre,
            "w4_rules_preview": str(w4_rules)[:200],
            "advice": (
                f"{platform}平台{genre}题材: "
                f"机会评分{trend.get('opportunity_score',50)}/100, "
                f"对话率目标≥{pp['dia_pct']:.0%}, "
                f"章节≥{pp['words_min']}字, "
                f"钩子类型={pp['hook_type']}"
            ),
        }

    def recommend_strategy(self, chapter_num: int) -> WritingStrategy:
        s = WritingStrategy()
        info = self.state.get("project_info", {})
        platform = info.get("platform", "qimao")
        total_ch = info.get("target_chapters", 12)

        # === 1. 模式选择 ===
        prev_intel = self._load_previous_intelligence(chapter_num - 1)
        if prev_intel:
            quality = prev_intel.get("quality_posterior", 0.7)
            ai_risk = prev_intel.get("ai_risk_score", 0.0)
            # 质量低或AI风险高 → workshop模式加强质检
            if quality < 0.5 or ai_risk > 0.6:
                s.mode = "workshop"
            else:
                s.mode = "quick"
        elif chapter_num <= 3:
            s.mode = "workshop"  # 前三章: 工坊模式保证质量
        else:
            s.mode = "quick"

        # === 2. 字数目标 ===
        s.target_words = self._optimal_words(chapter_num, total_ch, platform)

        # === 3. 温度 ===
        s.temperature = self._optimal_temperature(chapter_num, prev_intel)

        # === 4. 钩子类型 ===
        s.hook_type = self._recommend_hook(chapter_num)

        # === 5. 情绪释放 ===
        s.release_type = self._recommend_release(chapter_num)

        # === 6. 开篇加强 ===
        s.opening_boost = chapter_num <= 3

        # === 7. Claude精修 ===
        s.use_claude_w4 = self._should_use_claude(chapter_num, prev_intel)

        # === 8. 优先级 ===
        s.priority_dimensions = self._priority_dims(chapter_num, prev_intel)

        return s

    def _optimal_words(self, ch: int, total: int, platform: str) -> int:
        """基于章节位置 + 平台的最优字数"""
        if platform == "知乎盐选":
            base = 2200
        elif platform == "番茄":
            base = 1800
        elif platform == "七猫":
            base = 2000
        else:
            base = 2500

        if ch == 1 or ch == total:
            return int(base * 1.2)
        elif ch <= 3 or ch >= total - 2:
            return int(base * 1.1)
        elif ch % 4 == 0:
            return int(base * 1.15)
        elif ch % 4 == 1:
            return int(base * 0.9)
        return base

    def _optimal_temperature(self, ch: int, prev_intel: dict) -> float:
        """自适应温度"""
        base = 0.7
        if prev_intel:
            quality = prev_intel.get("quality_posterior", 0.7)
            if quality < 0.5:
                base -= 0.1  # 质量低 → 降低温度 (更确定)
            elif quality > 0.8:
                base += 0.05  # 质量高 → 稍高温度 (更创意)
        if ch <= 3:
            base -= 0.05  # 开篇要稳
        return round(min(0.9, max(0.5, base)), 2)

    def _recommend_hook(self, ch: int) -> str:
        """推荐钩子类型 (避免与最近2章重复)"""
        hooks = ["悬念", "反转", "期待", "情感", "危机", "余韵"]
        recent = []
        for c in range(max(1, ch - 2), ch):
            intel = self._load_previous_intelligence(c)
            if intel:
                ht = intel.get("chapter_meta", {}).get(str(c), {}).get("hook_type", "")
                if ht:
                    recent.append(ht)

        available = [h for h in hooks if h not in recent[-2:]]
        return available[0] if available else hooks[ch % len(hooks)]

    def _recommend_release(self, ch: int) -> Optional[str]:
        """推荐情绪释放方式 (每3-4章1次大释放)"""
        releases = ["善意崩溃", "诉说", "无声胜利", "雨水/眼泪", "食物触发", "沉默"]
        if ch % 3 == 0 or ch % 4 == 0:
            recent = []
            for c in range(max(1, ch - 3), ch):
                intel = self._load_previous_intelligence(c)
                if intel:
                    rt = intel.get("chapter_meta", {}).get(str(c), {}).get("release_type", "")
                    if rt:
                        recent.append(rt)
            available = [r for r in releases if r not in recent]
            return available[0] if available else releases[ch % len(releases)]
        return None

    def _should_use_claude(self, ch: int, prev_intel: dict) -> bool:
        """判断是否值得用Claude精修W4"""
        if ch == 1 or ch == self.state.get("project_info", {}).get("target_chapters", 12):
            return True  # 首尾章: 值得
        if prev_intel and prev_intel.get("ai_risk_score", 0) > 0.5:
            return True  # AI味偏高: Claude去味
        return False

    def _priority_dims(self, ch: int, prev_intel: dict) -> List[str]:
        """识别需要重点关注的维度"""
        priority = []
        if prev_intel:
            if prev_intel.get("ai_risk_score", 0) > 0.5:
                priority.append("sentence_variety")
            if prev_intel.get("tension_envelope", {}).get("pacing_quality", 1) < 0.5:
                priority.append("pacing")
            if prev_intel.get("character_network", {}).get("excessive_dominance"):
                priority.append("character_balance")
        return priority

    def generate_chapter_task(self, chapter_num: int) -> str:
        """
        从总纲+前章情报自动合成最优章任务。

        Returns: 一段包含具体写作指令的任务描述
        """
        # 从总纲提取
        tasks = {}
        outline = self.project_dir / "大纲" / "总纲.md"
        if outline.exists():
            import re
            for line in outline.read_text(encoding="utf-8").split('\n'):
                m = re.match(r'.*第(\d+)章[：:]\s*(.+)', line)
                if m:
                    tasks[int(m.group(1))] = m.group(2)

        base_task = tasks.get(chapter_num, f"第{chapter_num}章正文")

        # 风格一致性: 注入前章风格指纹
        if chapter_num > 1:
            try:
                from pangu_math.stats.style_fingerprint import StyleFingerprint
                prev_content = None
                content_dir = self.project_dir / "正文"
                prev_files = list(content_dir.glob(f"*第{chapter_num-1}章*"))
                if prev_files:
                    prev_content = prev_files[0].read_text(encoding="utf-8")
                if prev_content:
                    sf = StyleFingerprint.from_text(prev_content)
                    top3 = sf.top_dimensions(3)
                    base_task += f"【风格一致】前章风格: {top3[0][0]}主导。保持与前章一致的叙事节奏和句法风格。"
            except Exception:
                pass

        # 叠加策略
        strategy = self.recommend_strategy(chapter_num)
        prev_intel = self._load_previous_intelligence(chapter_num - 1)

        enhancements = []
        if strategy.opening_boost:
            enhancements.append("开篇300字内必须建立日常中的异常感")
        if strategy.hook_type:
            enhancements.append(f"章末钩子类型: {strategy.hook_type}")
        if strategy.release_type:
            enhancements.append(f"本章情绪释放方式: {strategy.release_type}")

        # 前章问题修正
        if prev_intel:
            ai_risk = prev_intel.get("ai_risk_score", 0)
            if ai_risk > 0.5:
                enhancements.append("注意增加句长变化，避免连续短句")
            advice = prev_intel.get("next_chapter_advice", "")
            if advice:
                enhancements.append(advice)

        # 伏笔提醒
        foreshadow = self.state.get("foreshadowing", {}).get("active_threads", [])
        urgent = [
            t for t in foreshadow
            if t.get("status") == "open"
            and chapter_num - t.get("planted_ch", 0) >= 3
        ]
        if urgent:
            enhancements.append(
                f"⚠ 必须推进或回收伏笔: {urgent[0].get('description', '?')[:40]}"
            )

        # 对话模板（强制注入，解决DeepSeek不写对话的根因）
        platform = self.state.get("project_info", {}).get("platform", "qimao")
        dia_pct = "35%" if platform in ("qidian",) else "25%"
        dialogue_template = (
            f"\n【强制对话要求】本章对话占比≥{dia_pct}。人物之间必须有多轮对话。格式示例：\n"
            '"X说：..." 后跟一句动作。如：\n'
            '  沈夜拱手："敢问公公，将我调往何处？"\n'
            '  太监将密旨塞进他手里："镇妖司。即刻上任。"\n'
            '  沈夜追问："为何是我？"\n'
            '  太监转身便走，影子在墙上拉长："去了便知。"\n'
            '对话推动剧情，每段对话3-5句。对话之间用简短动作填充。'
        )

        task_parts = [base_task + dialogue_template]
        if enhancements:
            task_parts.append("【本章约束】" + "；".join(enhancements))

        return "\n".join(task_parts)


# ================================================================
# 自适应批处理
# ================================================================

class AdaptiveBatchRunner:
    """
    自适应批量写作: 每章写完后分析结果 → 动态调整下一章策略。
    """

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.engine = SmartStrategyEngine(project_dir)
        self.results: List[dict] = []

    def run(self, from_ch: int, to_ch: int, base_mode: str = "quick",
             delay: float = 3.0) -> dict:
        """
        自适应批量写章。

        每章写完 → 读取情报 → 如果质量下降 → 自动切换workshop模式
        """
        current_mode = base_mode
        stats = {"success": 0, "failed": 0, "adaptations": 0, "chapters": []}

        for ch in range(from_ch, to_ch + 1):
            # 生成策略
            strategy = self.engine.recommend_strategy(ch)
            task = self.engine.generate_chapter_task(ch)

            # 门禁检查
            gate = self.engine.check_write_gate(ch)
            if not gate["passed"]:
                print(f"  ⛔ 门禁未通过: {gate['issues']}")
                stats["chapters"].append({"chapter": ch, "success": False, "gate_failed": True})
                stats["failed"] += 1
                continue
            if gate["warnings"]:
                print(f"  ⚠ 门禁提醒: {'; '.join(gate['warnings'][:2])}")

            print(f"\n{'='*60}")
            print(f"  智能策略 Ch{ch}: {strategy.mode} | "
                  f"{strategy.target_words}字 | T={strategy.temperature} | "
                  f"钩子={strategy.hook_type}")
            if strategy.use_claude_w4:
                print(f"  ⚡ W4 Claude精修 | 重点: {strategy.priority_dimensions}")
            if strategy.release_type:
                print(f"  💧 情绪释放: {strategy.release_type}")
            print(f"{'='*60}")

            # 写章
            ok = self._write_one(ch, task, strategy)
            stats["chapters"].append({"chapter": ch, "success": ok, "strategy": strategy})

            if ok:
                stats["success"] += 1

                # 分析本章结果 → 决定是否调整
                time.sleep(1)  # 等文件写入
                intel = self.engine._load_previous_intelligence(ch)
                prev_intel = self.engine._load_previous_intelligence(ch - 1)

                if intel and prev_intel:
                    quality_now = intel.get("quality_posterior", 0.7)
                    quality_prev = prev_intel.get("quality_posterior", 0.7)

                    # 质量下降 → 切换workshop
                    if quality_now < quality_prev - 0.1 and current_mode == "quick":
                        current_mode = "workshop"
                        stats["adaptations"] += 1
                        print(f"  ⚠ 质量下降 ({quality_prev:.0%}→{quality_now:.0%}) → 切换workshop模式")
                    # 质量恢复 → 切回quick
                    elif quality_now > 0.7 and current_mode == "workshop":
                        current_mode = "quick"
                        stats["adaptations"] += 1
                        print(f"  ✅ 质量恢复 ({quality_now:.0%}) → 切回quick模式")
            else:
                stats["failed"] += 1

            if ch < to_ch:
                print(f"  ⏳ {delay}s...")
                time.sleep(delay)

        return stats

    def _write_one(self, ch: int, task: str, strategy: WritingStrategy) -> bool:
        """执行单章写作"""
        from pangu_workshop import write_chapter
        return write_chapter(
            self.project_dir, ch,
            mode=strategy.mode,
            chapter_task=task,
        )


# ================================================================
# 项目诊断
# ================================================================

def diagnose_project(project_dir: Path):
    """全维度项目诊断 + 策略建议"""
    from pangu_workshop import load_state, project_status
    from pangu_intelligence import analyze_chapter

    project_status(project_dir)
    state = load_state(project_dir)
    current_ch = state.get("progress", {}).get("current_chapter", 0)
    info = state.get("project_info", {})

    print(f"\n{'='*60}")
    print(f"  智能诊断")
    print(f"{'='*60}")

    # 1. 审查最新章
    if current_ch > 0:
        ci = analyze_chapter(str(project_dir), current_ch, state=state)
        print(f"\n  最新章 Ch{current_ch}:")
        print(f"    质量后验: {ci.quality_posterior:.1%}")
        print(f"    AI风险:   {ci.ai_risk_score:.2f}")
        print(f"    节奏质量: {ci.tension_envelope.get('pacing_quality', '?'):.2f}")
        print(f"    审计意见: {ci.audit_opinion}")

        # 问题诊断
        if ci.ai_risk_score > 0.5:
            print(f"    ⚠ AI味偏高 — 建议下章用workshop模式 + Claude精修")
        if ci.quality_posterior < 0.5:
            print(f"    ⚠ 质量偏低 — 检查前3章是否连续下降")
        if ci.rhythm_analysis.get("is_mechanistic"):
            print(f"    ⚠ 节奏机械 — 插入长描写或纯对话打破模式")

    # 2. 伏笔健康
    from pangu_math.graph.foreshadow_graph import ForeshadowGraph
    fg = ForeshadowGraph.from_state(state)
    print(f"\n  伏笔网络: {fg.summary()}")
    if fg.expired_threads:
        print(f"    ⚠ 过期伏笔: {len(fg.expired_threads)}条 — 下章优先处理")
    if fg.bottleneck_chapters:
        print(f"    ⚠ 回收瓶颈章: Ch{fg.bottleneck_chapters}")

    # 3. 进度预测
    from pangu_project.gantt import WritingGantt
    gantt = WritingGantt(
        info.get("title", ""),
        info.get("target_chapters", 12),
    )
    target = info.get("target_chapters", 12)
    remaining = target - current_ch
    if remaining > 0:
        days_per_ch = 2.0
        est_days = remaining * days_per_ch
        import datetime
        eta = datetime.datetime.now() + datetime.timedelta(days=est_days)
        print(f"\n  进度: {current_ch}/{target} | 预计完成: {eta.strftime('%Y-%m-%d')}")

    # 4. 经济学
    from pangu_analytics.economics import WritingEconomics
    econ = WritingEconomics(
        info.get("platform", "qimao"),
        info.get("genre", "general"),
    )
    print(f"\n  经济学:")
    print(f"    最优定价: {econ.optimal_price():.1f}元")
    print(f"    读者LTV:  {econ.reader_lifecycle_value():.0f}元")

    # 5. 策略推荐
    engine = SmartStrategyEngine(project_dir)
    next_ch = current_ch + 1
    strategy = engine.recommend_strategy(next_ch)
    task = engine.generate_chapter_task(next_ch)

    print(f"\n  下章策略 Ch{next_ch}:")
    print(f"    模式: {strategy.mode}")
    print(f"    目标字数: {strategy.target_words}")
    print(f"    温度: {strategy.temperature}")
    print(f"    钩子: {strategy.hook_type}")
    if strategy.release_type:
        print(f"    释放: {strategy.release_type}")
    if strategy.use_claude_w4:
        print(f"    💎 建议W4用Claude精修")
    if strategy.priority_dimensions:
        print(f"    重点维度: {', '.join(strategy.priority_dimensions)}")
    print(f"\n  推荐任务:")
    print(f"    {task}")


# ================================================================
# CLI
# ================================================================

def main():
    from pangu_workshop import find_project, list_projects

    parser = argparse.ArgumentParser(description="盘古智能工作室")
    sub = parser.add_subparsers(dest="command")

    p_write = sub.add_parser("write", help="智能写一章")
    p_write.add_argument("--project", "-p", required=True)
    p_write.add_argument("--chapter", "-c", type=int, required=True)

    p_batch = sub.add_parser("batch", help="自适应批量写章")
    p_batch.add_argument("--project", "-p", required=True)
    p_batch.add_argument("--from", dest="from_ch", type=int, required=True)
    p_batch.add_argument("--to", dest="to_ch", type=int, required=True)
    p_batch.add_argument("--delay", type=float, default=3.0)

    p_diag = sub.add_parser("diagnose", help="全维度项目诊断")
    p_diag.add_argument("--project", "-p", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    proj = find_project(args.project)
    if not proj:
        print(f"[ERROR] 项目未找到: {args.project}")
        sys.exit(1)

    if args.command == "write":
        engine = SmartStrategyEngine(proj)
        strategy = engine.recommend_strategy(args.chapter)
        task = engine.generate_chapter_task(args.chapter)
        from pangu_workshop import write_chapter
        write_chapter(proj, args.chapter, mode=strategy.mode, chapter_task=task)

    elif args.command == "batch":
        runner = AdaptiveBatchRunner(proj)
        stats = runner.run(args.from_ch, args.to_ch, delay=args.delay)
        print(f"\n  自适应完成: {stats['success']}/{stats['failed'] + stats['success']}")
        print(f"  策略调整: {stats['adaptations']}次")

    elif args.command == "diagnose":
        diagnose_project(proj)


if __name__ == "__main__":
    main()
