#!/usr/bin/env python3
"""
盘古人机协作写作协议 (Pangu Human-AI Collaborative Writing Protocol)

核心理念：
  - 关键章节由人（高级AI）精写，保证极致质量
  - 过渡章节由API流水线批量产出，保证效率
  - API产出后由人审校，修掉AI味和OOC
  - 记忆银行持续运作，保证长篇一致性

写作模式：
  A. 精写模式（人写）— 生命线章节、高潮章、转折章
  B. 流水线模式（API写）— 日常、铺垫、支线
  C. 协作模式（API写+人审校）— 默认推荐模式
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================
# 第一章节分类与优先级
# ============================================================

class ChapterType(Enum):
    """章节类型"""
    LIFELINE = "lifeline"       # 生命线：前3-5章，决定读者去留
    CLIMAX = "climax"           # 高潮章：卷末决战、大反转
    TURNING = "turning"         # 转折章：关键剧情转向
    REVEAL = "reveal"           # 揭秘章：伏笔回收、身份揭露
    TRANSITION = "transition"   # 过渡章：承上启下
    DAILY = "daily"             # 日常章：修炼、互动、铺垫
    SIDESTORY = "sidestory"     # 支线章：配角视角
    FILLER = "filler"           # 填充章：过渡性内容


# 章节类型 → 推荐写作模式
CHAPTER_WRITE_MODE = {
    ChapterType.LIFELINE:   "human",        # 人写，质量优先
    ChapterType.CLIMAX:     "human",         # 人写，高潮不能拉胯
    ChapterType.TURNING:    "human",         # 人写，转折必须精准
    ChapterType.REVEAL:     "human_review",  # API写+人审，揭秘需要逻辑严密
    ChapterType.TRANSITION: "api_review",    # API写+人审，过渡章质量要求中等
    ChapterType.DAILY:      "api_review",    # API写+人审，日常章可以快
    ChapterType.SIDESTORY:  "api_review",    # API写+人审，支线可以快
    ChapterType.FILLER:     "api_auto",      # API自动写，填充章不需要审
}


# ============================================================
# 第二节 七猫签约硬约束（所有模式必须遵守）
# ============================================================

@dataclass
class PlatformConstraints:
    """平台硬约束 — 不可违反的铁律"""
    # 七猫核心指标
    dialogue_rate_min: float = 0.42          # 对话率最低42%
    hook_per_words: int = 300                # 每300字一个微钩子
    first_conflict_words: int = 300          # 前300字必须出冲突
    first_hook_words: int = 500              # 前500字必须有钩子

    # 禁用词（AI味词表）
    banned_words: List[str] = field(default_factory=lambda: [
        "他感到", "缓缓地", "突然", "不是…而是", "瞳孔", "嘴角勾起",
        "不禁", "心中一惊", "倒吸一口凉气", "仿佛", "宛如",
        "如同…一般", "似乎", "隐隐约约", "不由得",
    ])

    # 描写限制
    max_description_words: int = 30          # 纯描写段落不超过30字
    max_metaphor_count: int = 1              # 每段最多1个比喻
    no_psychology_description: bool = True   # 禁止心理描写

    # 人设约束
    mc_max_speak_words: int = 10             # 主角说话不超过10字
    mc_signature_action: str = "活动右手腕"   # 主角标志性动作
    mc_personality: str = "不圣母不废话越危险越冷静"


# ============================================================
# 第三节 章节规划模板
# ============================================================

@dataclass
class ChapterPlan:
    """单章规划"""
    chapter_num: int
    chapter_type: ChapterType
    write_mode: str              # human / api_review / api_auto / human_review
    chapter_task: str            # 章节任务描述
    key_hook: str                # 章末钩子
    key_satisfaction: str        # 核心爽点
    foreshadow_plant: List[str] = field(default_factory=list)   # 本章埋的伏笔
    foreshadow_collect: List[str] = field(default_factory=list)  # 本章回收的伏笔
    characters_present: List[str] = field(default_factory=list)  # 出场人物
    word_count_target: int = 2700


def auto_classify_chapter(chapter_num: int, total_chapters: int,
                          volume_chapters: int = 50) -> ChapterType:
    """
    自动分类章节类型

    规则：
    - 第1-5章：生命线
    - 每卷最后3章：高潮
    - 每卷第1章：转折
    - 每卷第1/3和2/3处：揭秘
    - 其余：过渡/日常
    """
    if chapter_num <= 5:
        return ChapterType.LIFELINE

    pos_in_volume = chapter_num % volume_chapters
    if pos_in_volume == 0:
        pos_in_volume = volume_chapters

    # 卷末3章 = 高潮
    if pos_in_volume > volume_chapters - 3:
        return ChapterType.CLIMAX

    # 卷首 = 转折
    if pos_in_volume == 1:
        return ChapterType.TURNING

    # 卷1/3和2/3处 = 揭秘
    if pos_in_volume in (volume_chapters // 3, 2 * volume_chapters // 3):
        return ChapterType.REVEAL

    # 每5章一个日常
    if pos_in_volume % 5 == 0:
        return ChapterType.DAILY

    return ChapterType.TRANSITION


# ============================================================
# 第四节 协作写作流程
# ============================================================

class CollaborativeWritingProtocol:
    """
    人机协作写作协议

    流程：
    1. 规划阶段：自动分类章节类型 → 确定写作模式
    2. 写作阶段：按模式执行（人写/API写）
    3. 审校阶段：API产出后由人审校
    4. 记忆阶段：每章写完更新记忆银行
    """

    def __init__(self, project_dir: str, platform: str = "qimao"):
        self.project_dir = Path(project_dir)
        self.platform = platform
        self.constraints = PlatformConstraints()
        self.protocol_file = self.project_dir / "writing_protocol.json"
        self.plans: Dict[int, ChapterPlan] = {}
        self._load_protocol()

    def _load_protocol(self):
        """加载已有的写作协议"""
        if self.protocol_file.exists():
            data = json.loads(self.protocol_file.read_text(encoding='utf-8'))
            for ch_num, plan_data in data.get("chapter_plans", {}).items():
                plan_data["chapter_type"] = ChapterType(plan_data["chapter_type"])
                self.plans[int(ch_num)] = ChapterPlan(**plan_data)

    def _save_protocol(self):
        """保存写作协议"""
        data = {
            "platform": self.platform,
            "constraints": {
                "dialogue_rate_min": self.constraints.dialogue_rate_min,
                "hook_per_words": self.constraints.hook_per_words,
                "first_conflict_words": self.constraints.first_conflict_words,
                "mc_max_speak_words": self.constraints.mc_max_speak_words,
                "mc_signature_action": self.constraints.mc_signature_action,
            },
            "chapter_plans": {}
        }
        for ch_num, plan in self.plans.items():
            plan_dict = {
                "chapter_num": plan.chapter_num,
                "chapter_type": plan.chapter_type.value,
                "write_mode": plan.write_mode,
                "chapter_task": plan.chapter_task,
                "key_hook": plan.key_hook,
                "key_satisfaction": plan.key_satisfaction,
                "foreshadow_plant": plan.foreshadow_plant,
                "foreshadow_collect": plan.foreshadow_collect,
                "characters_present": plan.characters_present,
                "word_count_target": plan.word_count_target,
            }
            data["chapter_plans"][str(ch_num)] = plan_dict

        self.protocol_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def plan_chapters(self, start: int, end: int,
                      chapter_tasks: Optional[Dict[int, str]] = None,
                      total_chapters: int = 500):
        """
        规划一批章节

        Args:
            start: 起始章节号
            end: 结束章节号
            chapter_tasks: {章节号: 任务描述} 的字典
            total_chapters: 全书总章数
        """
        chapter_tasks = chapter_tasks or {}

        for ch_num in range(start, end + 1):
            ch_type = auto_classify_chapter(ch_num, total_chapters)
            write_mode = CHAPTER_WRITE_MODE[ch_type]
            task = chapter_tasks.get(ch_num, f"第{ch_num}章，继续推进剧情")

            plan = ChapterPlan(
                chapter_num=ch_num,
                chapter_type=ch_type,
                write_mode=write_mode,
                chapter_task=task,
                key_hook="（待定）",
                key_satisfaction="（待定）",
            )
            self.plans[ch_num] = plan

        self._save_protocol()
        return self.get_plan_summary(start, end)

    def get_plan_summary(self, start: int, end: int) -> str:
        """获取章节规划摘要"""
        lines = []
        lines.append(f"{'章号':>4}  {'类型':<8}  {'写作模式':<12}  {'章节任务'}")
        lines.append("-" * 70)

        mode_label = {
            "human": "人精写",
            "human_review": "人写+审校",
            "api_review": "API写+人审",
            "api_auto": "API自动",
        }
        type_label = {
            "lifeline": "生命线",
            "climax": "高潮",
            "turning": "转折",
            "reveal": "揭秘",
            "transition": "过渡",
            "daily": "日常",
            "sidestory": "支线",
            "filler": "填充",
        }

        for ch_num in range(start, end + 1):
            if ch_num in self.plans:
                plan = self.plans[ch_num]
                t = type_label.get(plan.chapter_type.value, plan.chapter_type.value)
                m = mode_label.get(plan.write_mode, plan.write_mode)
                lines.append(f"{ch_num:>4}  {t:<8}  {m:<12}  {plan.chapter_task[:30]}")

        return "\n".join(lines)

    def get_write_mode(self, chapter_num: int) -> str:
        """获取指定章节的写作模式"""
        if chapter_num in self.plans:
            return self.plans[chapter_num].write_mode
        # 没有规划时，自动分类
        ch_type = auto_classify_chapter(chapter_num, 500)
        return CHAPTER_WRITE_MODE[ch_type]

    def get_chapter_constraints_prompt(self, chapter_num: int) -> str:
        """
        生成章节写作约束prompt（注入到API调用中）

        这是协作模式的核心：无论人写还是API写，约束必须一致
        """
        plan = self.plans.get(chapter_num)
        ch_type = plan.chapter_type if plan else ChapterType.TRANSITION

        type_label = {
            ChapterType.LIFELINE: "生命线（决定读者去留）",
            ChapterType.CLIMAX: "高潮（卷末决战/大反转）",
            ChapterType.TURNING: "转折（关键剧情转向）",
            ChapterType.REVEAL: "揭秘（伏笔回收/身份揭露）",
            ChapterType.TRANSITION: "过渡（承上启下）",
            ChapterType.DAILY: "日常（修炼/互动/铺垫）",
        }

        prompt = f"""【写作约束 — 必须严格遵守】

章节类型：{type_label.get(ch_type, "过渡")}
平台：七猫（免费阅读）

硬约束：
1. 对话率≥{int(self.constraints.dialogue_rate_min * 100)}%，低于此数直接重写
2. 每{self.constraints.hook_per_words}字一个微钩子（悬念/反转/新信息）
3. 纯描写段落≤{self.constraints.max_description_words}字
4. 每段最多{self.constraints.max_metaphor_count}个比喻
5. 禁止心理描写（用动作和对话代替）
6. 主角说话≤{self.constraints.mc_max_speak_words}字
7. 主角标志性动作：{self.constraints.mc_signature_action}
8. 主角人设：{self.constraints.mc_personality}

禁用词（出现即重写）：
{', '.join(self.constraints.banned_words[:10])}

章节任务：{plan.chapter_task if plan else '继续推进剧情'}
章末钩子：{plan.key_hook if plan and plan.key_hook != '（待定）' else '必须设计一个让读者翻下一章的钩子'}
核心爽点：{plan.key_satisfaction if plan and plan.key_satisfaction != '（待定）' else '必须设计至少一个爽点'}"""

        return prompt

    def get_review_checklist(self) -> str:
        """
        审校清单（人审API产出时使用）
        """
        return """【审校清单 — 逐项检查】

□ 1. 对话率是否≥42%？（数一下对话行数/总行数）
□ 2. 主角说话是否≤10字？（检查每句林夜的台词）
□ 3. 有无禁用词？（他感到/缓缓地/突然/瞳孔/嘴角勾起）
□ 4. 有无心理描写？（"他知道""他感到""他意识到"）
□ 5. 纯描写段落是否≤30字？
□ 6. 每300字有无微钩子？
□ 7. 章末钩子是否足够强？
□ 8. 人设是否一致？（林夜不圣母不废话越危险越冷静）
□ 9. 剧情是否按大纲走？（有无AI自由发挥的剧情？）
□ 10. 伏笔是否按计划埋/收？

如有任何一项不通过，标记问题位置并修改。"""

    def update_plan(self, chapter_num: int, **kwargs):
        """更新章节规划"""
        if chapter_num in self.plans:
            plan = self.plans[chapter_num]
            for key, value in kwargs.items():
                if hasattr(plan, key):
                    setattr(plan, key, value)
            self._save_protocol()

    def mark_chapter_done(self, chapter_num: int, quality_score: float = 0.0,
                          notes: str = ""):
        """标记章节完成"""
        if chapter_num in self.plans:
            self.update_plan(
                chapter_num,
                _completed=True,
                _quality_score=quality_score,
                _notes=notes,
            )


# ============================================================
# 第五节 项目初始化模板
# ============================================================

def init_collaborative_project(project_dir: str, title: str,
                                platform: str = "qimao",
                                total_chapters: int = 500) -> CollaborativeWritingProtocol:
    """
    初始化协作写作项目

    自动规划前5章（生命线），其余章节按需规划
    """
    protocol = CollaborativeWritingProtocol(project_dir, platform)

    # 前5章固定为生命线，人精写
    lifeline_tasks = {
        1: "开篇：主角苏醒+致命威胁+人设建立",
        2: "追杀+伏击以弱胜强+基因改造升级",
        3: "发现机甲+同步率+求救信号",
        4: "救出女主+碾压战力+CP互动",
        5: "打脸三连+星门巨舰",
    }

    lifeline_hooks = {
        1: "12个机器人逼近，4分37秒",
        2: "暗金色血字'不要叫醒她'",
        3: "求救信号'救……我……'",
        4: "'林夜，你终于醒了'",
        5: "黑色巨舰从星门驶出，炮口对准空间站",
    }

    lifeline_satisfactions = {
        1: "72小时倒计时→'够了'→笑了",
        2: "布条伏击机器人+317%基因改造",
        3: "白昼机甲+97.3%同步率",
        4: "苏瑶秒杀虫怪+CP'扯平'",
        5: "铁牙团嘲讽→一炮击沉→打脸三连",
    }

    for ch_num in range(1, 6):
        plan = ChapterPlan(
            chapter_num=ch_num,
            chapter_type=ChapterType.LIFELINE,
            write_mode="human",
            chapter_task=lifeline_tasks.get(ch_num, ""),
            key_hook=lifeline_hooks.get(ch_num, "（待定）"),
            key_satisfaction=lifeline_satisfactions.get(ch_num, "（待定）"),
            characters_present=["林夜", "诺亚"] if ch_num < 4 else ["林夜", "诺亚", "苏瑶"],
            word_count_target=2700,
        )
        protocol.plans[ch_num] = plan

    protocol._save_protocol()
    return protocol


# ============================================================
# 第六节 使用示例
# ============================================================

if __name__ == "__main__":
    # 示例：初始化项目
    project_dir = "projects/末世：我有一座外星空间站"
    protocol = init_collaborative_project(project_dir, "末世：我有一座外星空间站")

    # 查看前5章规划
    print(protocol.get_plan_summary(1, 5))

    # 规划第6-15章
    print("\n")
    chapter_tasks = {
        6: "巨舰威胁+林夜应对+苏瑶恢复",
        7: "潜入巨舰+发现晨曦族线索",
        8: "巨舰内部战斗+新敌人",
        9: "逃离巨舰+能量核心升级",
        10: "铁牙团复仇+联盟信号",
        11: "日常：空间站修复+苏瑶记忆碎片",
        12: "联盟使者到来+新人类联盟",
        13: "联盟内斗+收割者潜伏者线索",
        14: "伏笔回收：暗金色血字真相",
        15: "卷末高潮：收割者先遣队降临",
    }
    print(protocol.plan_chapters(6, 15, chapter_tasks))

    # 查看第6章的写作约束
    print("\n")
    print(protocol.get_chapter_constraints_prompt(6))

    # 查看审校清单
    print("\n")
    print(protocol.get_review_checklist())
