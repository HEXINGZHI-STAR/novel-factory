"""
盘古AI - 统一提示词与知识注入

之前: 句式参数在 pangu_optimized.py 和 workflow_engine.py 各定义一份
      _MODE_TO_GENRE 在 pangu_optimized.py 中被定义了两次且值冲突
      平台规则散落在3个地方
现在: 一处定义，全局共享
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

from .config import get_config

BASE_DIR = get_config().base_dir


# ============================================================
# 句式参数（唯一真值来源 - Single Source of Truth）
# 来自素材库16部真实网络文学的统计分析
# ============================================================

@dataclass(frozen=True)
class SentenceParams:
    """题材的句式参数向量（不可变，借鉴Rust的struct）"""
    mu_L: int           # 平均句长目标
    p_long: float       # 长句率(≥31字)目标
    p_describe: float   # 描写句占比
    p_narrate: float    # 叙述推进句占比
    p_action: float     # 动作句占比
    r_q: float          # 问号率
    r_e: float          # 叹号率
    core_pattern: str   # 核心写作模式描述


# 唯一真值：题材 -> 句式参数
GENRE_PARAMS: Dict[str, SentenceParams] = {
    "玄幻/仙侠":    SentenceParams(30, 0.40, 0.22, 0.25, 0.16, 0.10, 0.15, "说明->描写->动作->对话循环"),
    "历史/权谋":    SentenceParams(35, 0.53, 0.30, 0.28, 0.05, 0.15, 0.05, "长句+描写+极少量对话"),
    "悬疑/无限流":  SentenceParams(50, 0.57, 0.41, 0.10, 0.05, 0.26, 0.16, "长描写铺垫->极短句揭示->问号结尾"),
    "军事":         SentenceParams(48, 0.61, 0.36, 0.28, 0.08, 0.18, 0.49, "几乎无对话，全靠叙述推进"),
    "体育/爽文":    SentenceParams(22, 0.28, 0.15, 0.15, 0.23, 0.08, 0.12, "短句动作流，但句子也要15-25字"),
    "西方奇幻":     SentenceParams(32, 0.43, 0.37, 0.17, 0.08, 0.11, 0.08, "描写占比最高(37%)，对话推动"),
    "科幻/都市科技": SentenceParams(28, 0.42, 0.20, 0.34, 0.10, 0.15, 0.08, "说明/背景句占比最高(30%-34%)"),
    "都市":         SentenceParams(28, 0.40, 0.22, 0.28, 0.15, 0.12, 0.10, "通用都市节奏"),
    "治愈":         SentenceParams(28, 0.38, 0.28, 0.22, 0.10, 0.14, 0.12, "温暖描写+日常对话循环"),
    "通用":         SentenceParams(30, 0.40, 0.25, 0.25, 0.15, 0.10, 0.12, "通用平衡模式"),
}

# 唯一真值：模式名 -> 题材名
MODE_TO_GENRE: Dict[str, str] = {
    "urban_power": "都市",
    "general": "通用",
    "female_solo": "都市",
    "romance": "都市",
    "mystery": "悬疑/无限流",
    "rule_mystery": "悬疑/无限流",
    "规则怪谈": "悬疑/无限流",
    "historical": "历史/权谋",
    "military": "军事",
    "xianxia": "玄幻/仙侠",
    "xuanhuan": "玄幻/仙侠",
    "scifi": "科幻/都市科技",
    "fantasy": "西方奇幻",
    "sports": "体育/爽文",
    "crazy_lit": "都市",
    "folk_horror": "悬疑/无限流",
    "healing_life": "治愈",
    "healing_life_v2": "治愈",
    "reality_revenge": "都市",
    "retro_life": "都市",
    "history_scholar": "历史/权谋",
}


def get_genre_for_mode(mode: str) -> str:
    """根据模式名获取题材名"""
    return MODE_TO_GENRE.get(mode, MODE_TO_GENRE.get(mode.split('_')[0], "通用"))


def get_params_for_mode(mode: str) -> SentenceParams:
    """根据模式名获取句式参数"""
    genre = get_genre_for_mode(mode)
    return GENRE_PARAMS.get(genre, GENRE_PARAMS["通用"])


# ============================================================
# 知识注入器
# ============================================================

class KnowledgeInjector:
    """
    根据阶段ID决定注入哪些知识。
    不同阶段需要不同的知识密度：
    - W0(主旨锚定): 轻量 - 只需要钩子设计原则
    - W1(设定预处理): 中量 - 需要题材设定规则
    - W2(正文初稿): 重量 - 完整句式参数+AI禁令+平台约束
    - W3(逻辑质检): 中量 - 逻辑检查清单+句式检查
    - W4(文笔精修): 重量 - 完整句式参数+AI禁令+镜头语言+平台约束

    # DEPRECATED: Use PromptBuilder instead
    # 此类保留以保持向后兼容，新代码请使用 pangu_core.prompt_builder.PromptBuilder
    # PromptBuilder 提供更完整的17层注入链，合并了 build_smart_prompt() 和本类的逻辑
    """

    @staticmethod
    def inject(stage_id: int, mode: str, platform: str, workshop_prompt: str = "") -> str:
        """根据阶段ID构建system_msg（规则蒸馏版：每阶段只注入最关键3-5条硬约束）

        # DEPRECATED: Use PromptBuilder instead
        # 此方法保留以保持向后兼容，新代码请使用 pangu_core.prompt_builder.PromptBuilder
        """
        parts = []
        genre = get_genre_for_mode(mode)
        params = get_params_for_mode(mode)

        # ---- W0 主旨锚定 ----
        if stage_id == 0:
            parts.append(f"【角色】盘古V7.0【主旨锚定车间】W0。根据一句话故事，产出本章的核心钩子和冲突。")
            parts.append("""【钩子设计原则】
  - 每章结尾必须有钩子让读者想看下一章
  - 钩子类型（悬念/危机/反转/期待/情感）需要轮换，连续两章不得同类型
  - 输出JSON: {"hook": "章末钩子", "conflict": "本章核心冲突", "expected_payoff": "读者期待的回报"}""")

        # ---- W1 设定预处理 ----
        elif stage_id == 1:
            parts.append(f"【角色】盘古V7.0【设定预处理车间】W1。提取本章需要的场景、人物状态、关键设定，形成'本章热库'。")

        # ---- W2 正文初稿 ----
        elif stage_id == 2:
            parts.append(f"【角色】盘古V7.0【正文初稿车间】W2。根据热库产出2000字初稿，重点是故事推进。")
            parts.append(f"【句式硬约束·{genre}】μ_L≥{params.mu_L} p_long≥{params.p_long} CV_L≥0.30 最长/最短≥5 H_punct≥1.0 描写≈{params.p_describe} 叙述≈{params.p_narrate} 动作≈{params.p_action} 模式:{params.core_pattern}")
            parts.append("【禁令】❌连续3句≤12字 ❌\"他感到/心中/暗道\"+情绪词 ❌\"缓缓/淡淡/微微\"≤2/千字 ❌\"忽然/突然/猛然\"≤3/千字 ❌\"不是…而是…\" ❌对话单独换行")
            parts.append("短句→扩展动作+细节；情绪词→具体动作；纯对话→叙述+动作+对话混合")

        # ---- W3 逻辑质检 ----
        elif stage_id == 3:
            parts.append(f"【角色】盘古V7.0【逻辑质检车间】W3。检查正文初稿的逻辑一致性、剧情推进合理性，输出修正后的骨架。")
            parts.append(f"""【句式检查项】（质检时重点检查）
  - 平均句长是否达到25字以上？
  - 是否有连续3句以上的短句(≤12字)？
  - 是否出现了"他感到/缓缓地/突然"等AI味词汇？
  - 长句(≥31字)占比是否达到{params.p_long}以上？""")

        # ---- W4 文笔精修 ----
        elif stage_id == 4:
            parts.append(f"【角色】盘古V7.0【文笔精修车间】W4。为骨架添加质感、情绪、镜头、氛围。核心：只化妆不动刀——不改剧情/人物逻辑/不添新事件。")
            parts.append(f"【句式约束】同W2 + 极短揭示句(1-10字)占比≈0.10")
            parts.append("【精修5技】1.环境锚定细节 2.心理→动作(\"他感到悲伤\"→\"手指摩挲杯沿\") 3.氛围≤20% 4.明确机位(全景/中景/特写/主观) 5.对话用动作替代\"他说\"")
            parts.append("【禁令】同W2")

        else:
            parts.append(f"【角色】盘古V7.0【写作车间】W{stage_id}。完成写作任务。")

        # 平台约束（W2/W4注入）
        if stage_id in [2, 4]:
            platform_rules = _PLATFORM_RULES.get(platform, "")
            if platform_rules:
                parts.append(platform_rules)

        # workshop原始prompt的补充说明
        if workshop_prompt:
            extracted = _extract_guide_sections(workshop_prompt)
            if extracted:
                parts.append("【车间补充说明】\n" + extracted)

        return "\n\n".join(p.strip() for p in parts if p.strip())


# ============================================================
# 平台规则（唯一真值来源）
# ============================================================

_PLATFORM_RULES = {
    "qimao": "【七猫】爽感>悬念>情感 段落≤3行 章末强钩子",
    "fanqie": "【番茄】300字出冲突 800字一爽点 段落1-2句 拒绝慢热",
    "qidian": "【起点】设定严谨逻辑自洽 允许长段落 必须有长线钩子",
    "zhihu": "【知乎盐选】克制·留白·心理恐怖 短段适配手机 结尾落在画面/天气/物件上 不给答案只给余韵",
    "jinjiang": "【晋江】细腻五感丰富 对话有潜台词话不说满 情绪渗透型不直给 主角人设鲜明情感细腻",
}

# ============================================================
# 爽点分类体系 (10型) — 来源: 盘古V1.0 + 网文市场验证
# ============================================================

COOL_POINT_TYPES = {
    "打脸":  {"desc": "被看不起→证明自己→对方被打脸", "intensity": 8, "cooldown_chapters": 1},
    "捡漏":  {"desc": "别人不识货→主角低价获得→价值曝光", "intensity": 6, "cooldown_chapters": 2},
    "暧昧":  {"desc": "男女主互动→肢体/言语擦边→关系推进", "intensity": 7, "cooldown_chapters": 1},
    "突破":  {"desc": "修炼/能力升级→突破瓶颈→实力跃迁", "intensity": 8, "cooldown_chapters": 3},
    "反转":  {"desc": "读者预期被推翻→真相揭露→恍然大悟", "intensity": 9, "cooldown_chapters": 3},
    "碾压":  {"desc": "主角实力碾压对手→众人震惊→建立威慑", "intensity": 9, "cooldown_chapters": 2},
    "夺宝":  {"desc": "发现/争夺宝物→到手→宝物展示价值", "intensity": 7, "cooldown_chapters": 2},
    "收服":  {"desc": "收服强力角色/宠物/势力→忠诚展示", "intensity": 8, "cooldown_chapters": 4},
    "揭秘":  {"desc": "隐藏的秘密被揭示→世界观扩大→新目标", "intensity": 8, "cooldown_chapters": 5},
    "共鸣":  {"desc": "读者感情被触发→'原来不止我一个人'→情绪释放", "intensity": 6, "cooldown_chapters": 2},
}

# ============================================================
# 钩子类型详细分类 (8型) — 来源: 盘古V1.0 + 七猫/番茄平台
# ============================================================

HOOK_TYPES = {
    "悬念":     {"desc": "让读者想知道'接下来发生了什么'", "formula": "信息缺口 + 倒计时/威胁", "platform": "all"},
    "反转":     {"desc": "读者以为A→结果是B→新的问题出现", "formula": "预期推翻 + 新信息", "platform": "all"},
    "期待":     {"desc": "让读者想看'这个爽点怎么兑现'", "formula": "预告爽点 + 延迟满足", "platform": "qimao,fanqie"},
    "情感":     {"desc": "让读者停留在情绪余韵中", "formula": "情绪高点 + 画面定格", "platform": "zhihu,jinjiang"},
    "危机":     {"desc": "角色处于危险中→读者焦虑→必须翻页", "formula": "危险逼近 + 时间锁", "platform": "all"},
    "余韵":     {"desc": "画面/天气/物件收尾→让读者'再待一会儿'", "formula": "空镜/物件状态变化", "platform": "zhihu"},
    "话语未尽": {"desc": "对话说到一半→关键信息悬停", "formula": "对话中断 + 新信息暗示", "platform": "all"},
    "倒计时":   {"desc": "时间限制→必须在X内完成Y", "formula": "deadline + 高代价失败", "platform": "fanqie,qimao"},
}

# ============================================================
# 情绪释放方式 (6型) — 来源: healing_life_v2 模式
# ============================================================

RELEASE_TYPES = {
    "善意崩溃":  {"desc": "被最小的一件好事击溃——越小的善意越动人", "trigger": "陌生人的微小善意/回忆触发"},
    "诉说":      {"desc": "在黑暗中说出来——对一个人说出从没说出口的话", "trigger": "安全的环境+信任的人"},
    "无声胜利":  {"desc": "删掉号码/放下东西/停止重复——不是战胜了，是不再需要战了", "trigger": "积累到临界点后的释然"},
    "雨水眼泪":  {"desc": "天气作为情绪的容器——雨/雪/风包裹着释放", "trigger": "天气变化+独处"},
    "食物触发":  {"desc": "一口食物触发记忆→哭/笑/沉默", "trigger": "吃到某个味道/做某道菜"},
    "沉默":      {"desc": "没有释放就是最大的释放——'她张了张嘴，什么也没说'", "trigger": "想说什么但放弃了"},
}


# ============================================================
# 便捷函数
# ============================================================

def build_system_prompt(stage_id: int, mode: str, platform: str = "qimao",
                        workshop_prompt: str = "") -> str:
    """构建完整的system_msg（全局便捷函数）"""
    return KnowledgeInjector.inject(stage_id, mode, platform, workshop_prompt)


def _extract_guide_sections(prompt: str) -> str:
    """从原始workshop prompt中提取有用的指导性段落"""
    keywords = ["核心原则", "核心模式", "输出格式", "技术标准", "模式特殊", "写作要点", "精修技术", "质检清单"]
    lines = prompt.split("\n")
    extracted = []
    capturing = False

    for line in lines:
        stripped = line.strip()
        if any(kw in stripped for kw in keywords):
            capturing = True
            extracted.append(stripped)
            continue
        if capturing and stripped.startswith("## ") and not any(kw in stripped for kw in keywords):
            capturing = False
            continue
        if capturing:
            extracted.append(stripped)

    result = "\n".join(extracted).strip()
    return result if len(result) > 100 else ""
