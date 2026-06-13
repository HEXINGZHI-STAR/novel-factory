#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
                         DEPRECATED - 已废弃
===========================================================================
  本文件已废弃，请使用 pangu_core/pipeline.py 替代。
  
  迁移指引:
  1. 导入方式: from pangu_core.pipeline import WritingPipeline, PipelineConfig
  2. 使用方式: 
     config = PipelineConfig.from_workshop_mode()  # 或 from_quick_mode()
     pipeline = WritingPipeline(config)
     result = pipeline.run(context)
  
  废弃原因:
  - 本文件实现的7层Prompt注入已升级为17层注入链
  - 新增三层记忆系统、五路投影、三层关卡质控等功能
  - 统一使用 pangu_core/ 下的模块化实现
  
  最后维护日期: 2026-06-11
===========================================================================

盘古AI工作流引擎 v1.0 (旧版)
借鉴短剧制作工作流思想：分阶段、契约化、可质检、可重试、可独立运行

核心架构:
    WorkflowEngine (调度器)
        |
        +-- Stage (阶段基类)
        |       |-- input_schema  (输入契约: 需要哪些字段)
        |       |-- output_schema (输出契约: 产出哪些字段)
        |       |-- system_prompt (阶段专属提示词)
        |       |-- knowledge_policy (该阶段需要注入哪些知识)
        |       |-- validate()    (质检门: 检查输出是否符合契约)
        |       |-- run()         (执行: 注入知识 -> 调用AI -> 通过质检)
        |
        +-- KnowledgeInjector (知识分层注入器)
        |       |-- inject(Stage) -> 返回该阶段需要的system_msg
        |
        +-- QualityGate (质检门)
                |-- check_schema()  检查字段契约
                |-- check_content() 检查内容质量
                |-- suggest_retry()  不通过时给出重跑建议

使用方式:
    engine = WorkflowEngine(config)
    engine.add_stage(W0AnchorStage())
    engine.add_stage(W1SetupStage())
    engine.add_stage(W2DraftStage())
    engine.add_stage(W3QCStage())
    engine.add_stage(W4PolishStage())
    result = engine.run({"title": "...", "chapter_task": "...", "mode": "general", "platform": "qimao"})
"""

import json
import time
import re
import sys
from collections import Counter
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

# 添加knowledge目录以导入reference_engine
sys.path.insert(0, str(Path(__file__).parent / "knowledge"))

try:
    from reference_engine import WritingReference, WritingTechniqueLibrary
    HAS_REFERENCE_ENGINE = True
except:
    HAS_REFERENCE_ENGINE = False
    print("[WARN] reference_engine 不可用，将降级运行")

try:
    from mode_data_injector import ModeDataInjector
    HAS_MODE_INJECTOR = True
except ImportError:
    HAS_MODE_INJECTOR = False
    print("[WARN] mode_data_injector 不可用，模式数据注入将降级")

try:
    from memory_bank import MemoryBank
    HAS_MEMORY_BANK = True
except ImportError:
    HAS_MEMORY_BANK = False
    print("[WARN] memory_bank 不可用，记忆银行将降级")

# Write Gates（从 webnovel-writer 移植，三层关卡）
try:
    from pangu_core.write_gates import run_write_gate
    HAS_WRITE_GATES = True
except ImportError:
    HAS_WRITE_GATES = False
    print("[WARN] write_gates 不可用，Write Gates 将降级")

# Beat Sheet（章节级故事节拍约束）
try:
    from pangu_core.beat_sheet import build_and_inject_beat_sheet, get_beat_compliance_report
    HAS_BEAT_SHEET = True
except ImportError:
    HAS_BEAT_SHEET = False
    print("[WARN] beat_sheet 不可用，Beat Sheet 将降级")

# 统一从 pangu_core.prompts 导入句式参数和模式映射（唯一真值来源）
try:
    from pangu_core.prompts import GENRE_PARAMS as _CORE_GENRE_PARAMS, MODE_TO_GENRE as MODE_TO_GENRE
    # 将 SentenceParams dataclass 转为 dict 格式（兼容 KnowledgeInjector 内部使用）
    SENTENCE_PARAMS = {k: {key: val for key, val in v.__dict__.items() if not key.startswith('_')}
                       for k, v in _CORE_GENRE_PARAMS.items()}
except ImportError:
    print("[WARN] pangu_core.prompts 不可用，使用内嵌句式参数副本")
    SENTENCE_PARAMS = {
        "玄幻/仙侠":    {"mu_L": 30, "p_long": 0.40, "p_describe": 0.22, "p_narrate": 0.25, "p_action": 0.16, "r_q": 0.10, "r_e": 0.15},
        "历史/权谋":    {"mu_L": 35, "p_long": 0.53, "p_describe": 0.30, "p_narrate": 0.28, "p_action": 0.05, "r_q": 0.15, "r_e": 0.05},
        "悬疑/无限流":  {"mu_L": 50, "p_long": 0.57, "p_describe": 0.41, "p_narrate": 0.10, "p_action": 0.05, "r_q": 0.26, "r_e": 0.16},
        "军事":         {"mu_L": 48, "p_long": 0.61, "p_describe": 0.36, "p_narrate": 0.28, "p_action": 0.08, "r_q": 0.18, "r_e": 0.49},
        "体育/爽文":    {"mu_L": 22, "p_long": 0.28, "p_describe": 0.15, "p_narrate": 0.15, "p_action": 0.23, "r_q": 0.08, "r_e": 0.12},
        "西方奇幻":     {"mu_L": 32, "p_long": 0.43, "p_describe": 0.37, "p_narrate": 0.17, "p_action": 0.08, "r_q": 0.11, "r_e": 0.08},
        "科幻/都市科技": {"mu_L": 28, "p_long": 0.42, "p_describe": 0.20, "p_narrate": 0.34, "p_action": 0.10, "r_q": 0.15, "r_e": 0.08},
        "都市":         {"mu_L": 28, "p_long": 0.40, "p_describe": 0.22, "p_narrate": 0.28, "p_action": 0.15, "r_q": 0.12, "r_e": 0.10},
        "治愈":         {"mu_L": 28, "p_long": 0.38, "p_describe": 0.28, "p_narrate": 0.22, "p_action": 0.10, "r_q": 0.14, "r_e": 0.12},
        "通用":         {"mu_L": 30, "p_long": 0.40, "p_describe": 0.25, "p_narrate": 0.25, "p_action": 0.15, "r_q": 0.10, "r_e": 0.12},
    }
    MODE_TO_GENRE = {
        "urban_power": "都市", "general": "通用", "female_solo": "都市",
        "romance": "都市", "mystery": "悬疑/无限流", "rule_mystery": "悬疑/无限流",
        "规则怪谈": "悬疑/无限流", "historical": "历史/权谋", "history_scholar": "历史/权谋",
        "military": "军事", "xianxia": "玄幻/仙侠", "xuanhuan": "玄幻/仙侠",
        "scifi": "科幻/都市科技", "fantasy": "西方奇幻", "sports": "体育/爽文",
        "crazy_lit": "都市", "folk_horror": "悬疑/无限流",
        "healing_life": "治愈", "healing_life_v2": "治愈",
        "reality_revenge": "都市", "retro_life": "都市",
    }


# ============================================================
# 数据契约定义（Data Contracts）
# ============================================================

@dataclass
class StageInput:
    """阶段输入契约：定义每个阶段必须接收的字段"""
    # 全局信息
    title: str = ""
    chapter_task: str = ""
    mode: str = "general"          # 写作模式: general/urban_power/rule_mystery/romance/military...
    platform: str = "qimao"        # 平台: qimao/fanqie/qidian
    current_chapter: int = 1

    # 上下文(可选)
    context: str = ""              # 前几章的摘要/上下文

    # 项目目录(用于记忆银行等持久化)
    project_dir: str = ""

    # 上一阶段的输出(由工作流引擎自动填充)
    previous_outputs: Dict[int, str] = field(default_factory=dict)

    # 扩展字段
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageOutput:
    """阶段输出契约：定义每个阶段必须产出的字段"""
    stage_id: int
    stage_name: str
    content: str                    # 主要输出内容
    summary: str = ""               # 精简摘要(给下一阶段看的)
    success: bool = False
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    elapsed_time: float = 0.0

    def to_dict(self):
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "content": self.content,
            "summary": self.summary,
            "success": self.success,
            "message": self.message,
            "metadata": self.metadata,
            "elapsed_time": round(self.elapsed_time, 2),
        }


# ============================================================
# 知识分层注入器（Knowledge Injector）
# ============================================================

class KnowledgeInjector:
    """
    不同阶段注入不同的知识。
    - W0(主旨锚定): 不需要句式知识，需要钩子设计
    - W1(设定预处理): 需要题材-设定规则
    - W2(正文初稿): **需要完整知识** - 句式铁律+参数+AI禁令
    - W3(逻辑质检): 需要逻辑一致性检查清单
    - W4(文笔精修): **需要完整知识** + 镜头语言+氛围渲染

    句式参数统一从 pangu_core.prompts.GENRE_PARAMS 导入（唯一真值来源）
    """

    @classmethod
    def get_genre_params(cls, mode: str) -> Dict:
        """根据模式获取句式参数"""
        genre = MODE_TO_GENRE.get(mode, MODE_TO_GENRE.get(mode.split('_')[0], "通用"))
        return SENTENCE_PARAMS.get(genre, SENTENCE_PARAMS["通用"])

    @classmethod
    def inject_for_stage(cls, stage_id: int, mode: str, platform: str, workshop_prompt: str = "") -> str:
        """
        根据阶段ID决定注入哪些知识。
        返回一个完整的 system_msg。
        """
        parts = []
        genre = MODE_TO_GENRE.get(mode, MODE_TO_GENRE.get(mode.split('_')[0], "通用"))
        params = cls.get_genre_params(mode)

        # ============= 阶段0: 主旨锚定 - 只需要钩子设计原则 =============
        if stage_id == 0:
            parts.append("【角色】你是盘古V7.0小说工厂的【主旨锚定车间】，代号W0。")
            parts.append("【任务】根据一句话故事，产出本章的核心钩子和冲突。")
            parts.append("【设计原则】每章结尾必须有钩子让读者想看下一章；钩子类型（悬念/危机/反转/期待/情感）需要轮换。")
            parts.append("【输出】纯JSON，字段: {\"hook\": \"章末钩子\", \"conflict\": \"本章核心冲突\", \"expected_payoff\": \"读者期待的回报\"}")

        # ============= 阶段1: 设定预处理 - 需要题材设定规则 =============
        elif stage_id == 1:
            parts.append("【角色】你是盘古V7.0小说工厂的【设定预处理车间】，代号W1。")
            parts.append("【任务】提取本章需要的场景、人物状态、关键设定，形成\"本章热库\"。")
            parts.append("【设计原则】本章热库只保留本章必须用到的信息（约500字）。")
            parts.append("【题材模式】当前题材: " + genre)
            parts.append("【输出】纯文本，包含: 场景列表+人物状态+关键设定+本章任务解析。")

        # ============= 阶段2: 正文初稿 - 需要完整知识（句式铁律 + 参数 + AI禁令） =============
        elif stage_id == 2:
            parts.append("【角色】你是盘古V7.0小说工厂的【正文初稿车间】，代号W2。")
            parts.append("【任务】根据热库产出2000字左右的正文初稿。重点是故事推进，不是润色。")

            # 核心: 句式铁律（数学参数化）
            parts.append(f"""
【句式硬约束 · 题材:{genre}】（来自16部真人网文统计，必须严格遵守）
  平均句长 μ_L ≥ {params['mu_L']}字          （AI通常只写8-15字，必须加长）
  长句率 p_long ≥ {params['p_long']}            （31字以上句子占比，写复合句）
  句长变异 CV_L = σ_L/μ_L ≥ 0.30         （不许写一样长的句子）
  最长句/最短句 ≥ 5                       （制造节奏冲击）
  标点熵 H_punct ≥ 1.0                    （不许全是句号，问号/叹号/破折号交替）
  描写句占比 ≈ {params['p_describe']}
  叙述推进句占比 ≈ {params['p_narrate']}
  动作句占比 ≈ {params['p_action']}

【AI禁令·绝对不许】
  ❌ 连续3句都是≤12字的短句
  ❌ "他感到/他心中/他暗道/他心里" + 情绪形容词（写具体动作代替）
  ❌ "缓缓地/淡淡地/微微地/静静地/轻轻地"每1000字≤2个
  ❌ "忽然/突然/猛然/骤然"每1000字≤3个
  ❌ "不是……而是……"判断结构
  ❌ 每句对话都单独换行（对话嵌入叙述中）

【改写操作】短句→扩展动作+细节；抽象情绪→具体动作描写；纯对话→叙述+动作+对话混合
""")

        # ============= 阶段3: 逻辑质检 - 需要逻辑检查清单 =============
        elif stage_id == 3:
            parts.append("【角色】你是盘古V7.0小说工厂的【逻辑质检车间】，代号W3。")
            parts.append("【任务】检查正文初稿的逻辑一致性、剧情推进合理性，输出修正后的骨架。")
            parts.append("""
【质检清单】
  1. 时间线检查：事件先后顺序是否合理？
  2. 人物一致性：人物的行为是否符合其性格和设定？
  3. 因果检查：每个行动是否有合理的动机和后果？
  4. 设定一致性：是否违反了前文建立的规则？
  5. 信息密度：是否有冗余或缺失的关键信息？
  6. 钩子有效性：章末钩子是否成立？
  7. 句式检查（重点）：
     - 平均句长是否达到25字以上？
     - 是否有连续短句？
     - 是否出现了"他感到/缓缓地/突然"等AI味词汇？

【输出】先写"质检报告"列出问题，再写"修正后的骨架"（可以直接使用初稿的合格部分）
如果全文合格，写"无需修正"并原样输出初稿骨架。
""")

        # ============= 阶段4: 文笔精修 - 需要完整知识 + 镜头语言 + 氛围渲染 =============
        elif stage_id == 4:
            parts.append("【角色】你是盘古V7.0小说工厂的【文笔氛围精修车间】，代号W4。")
            parts.append("【任务】接收W3质检通过的剧情骨架，添加质感、情绪、镜头、氛围，输出最终成品章节。")
            parts.append("【核心原则】只化妆，不动刀——不许改剧情走向，不许改人物行为逻辑，不许添加新事件。")

            # 核心: 句式铁律（同W2）
            parts.append(f"""
【句式硬约束 · 题材:{genre}】（必须严格遵守）
  平均句长 μ_L ≥ {params['mu_L']}字
  长句率 p_long ≥ {params['p_long']}
  句长变异 CV_L ≥ 0.30
  最长句/最短句 ≥ 5
  标点熵 H_punct ≥ 1.0
  极短揭示句(1-10字)占比 ≈ 0.10（制造节奏冲击点）

【精修技术标准】
  1. 环境描写：每个场景至少有一个"锚定细节"——让读者记住这个场景的具象元素
  2. 心理描写：不直接写"他感到悲伤"，写"他的手指无意识地摩挲着杯沿"
  3. 氛围渲染：用天气/光线/声音/气味营造情绪基调，但不超过全文20%
  4. 镜头语言：明确每段的"机位"——全景？中景？特写？主观镜头？
  5. 对话润色：去掉冗余的"他说""她说"，用动作代替说话人标识

【AI禁令·绝对不许】同W2（禁止"他感到/缓缓地/突然/不是...而是"等AI味表达）
""")

        # 添加平台约束（对W2/W4特别重要）
        if stage_id in [2, 4]:
            platform_rules = cls._get_platform_rules(platform)
            if platform_rules:
                parts.append(platform_rules)

        # 最后添加workshop的专有prompt（如果有）
        if workshop_prompt:
            # 从workshop的prompt中提取"核心原则"和"输出格式"部分（跳过角色定义，我们已经重新定义了角色）
            extracted = cls._extract_guide_sections(workshop_prompt)
            if extracted:
                parts.append("【车间补充说明】\n" + extracted)

        return "\n\n".join(p.strip() for p in parts if p.strip())

    @classmethod
    def _get_platform_rules(cls, platform: str) -> str:
        """获取平台特定约束"""
        platform_rules_map = {
            "qimao": """
【平台约束·七猫】
  - 目标读者：25-40岁女性为主
  - 情绪优先级：爽感 > 悬念 > 情感 > 设定
  - 段落长度：手机端每段≤3行
  - 章末钩子必须强（"让读者想立刻点下一章"是唯一标准）
""",
            "fanqie": """
【平台约束·番茄】
  - 目标读者：全年龄段，算法驱动分发
  - 开头300字必须抓眼球——黄金前三章规则
  - 每800-1200字一个爽点或反转
  - 段落极短（1-2句一段为主）
  - 信息密度高，拒绝慢热
""",
            "qidian": """
【平台约束·起点】
  - 目标读者：18-35岁男性为主
  - 强调设定严谨、逻辑自洽
  - 允许较长段落和复杂句式
  - 世界观铺陈可慢热但必须有长线钩子
""",
        }
        return platform_rules_map.get(platform, "")  # 默认无平台约束

    @classmethod
    def _extract_guide_sections(cls, prompt: str) -> str:
        """从原始workshop prompt中提取有用的指导性段落（去掉角色定义）"""
        # 提取"核心原则"、"输出格式"、"模式特殊规则"、"技术标准"等关键词后的内容
        keywords = ["核心原则", "核心模式", "输出格式", "技术标准", "模式特殊", "写作要点", "精修技术", "质检清单"]
        lines = prompt.split("\n")
        extracted = []
        capturing = False

        for line in lines:
            stripped = line.strip()
            # 如果行包含关键词，开始捕获
            if any(kw in stripped for kw in keywords):
                capturing = True
                extracted.append(stripped)
                continue
            # 如果是另一个大标题，停止捕获
            if capturing and stripped.startswith("## ") and not any(kw in stripped for kw in keywords):
                capturing = False
                continue
            if capturing:
                extracted.append(stripped)

        result = "\n".join(extracted).strip()
        # 如果太短就放弃（可能原始prompt结构不清晰）
        return result if len(result) > 100 else ""


# ============================================================
# 质检门（Quality Gate）
# ============================================================

class QualityGate:
    """检查阶段输出是否合格，不合格则给出重跑建议"""

    @classmethod
    def check(cls, stage_id: int, content: str, min_length: int = 50,
              platform: str = "qimao", chapter_num: int = 1, mode: str = "general") -> Dict[str, Any]:
        """
        增强版质检：优先使用后端37+项质检，降级到原有7项检测
        返回: {"pass": bool, "score": float, "issues": [str], "retry_hint": str}
        """
        # W0/W1是短文本（大纲/设定），跳过后端37+项质检（弧光等对短文本不适用）
        if stage_id in [0, 1]:
            return cls._basic_check(stage_id, content, min_length, platform, chapter_num, mode)

        # 优先使用后端37+项质检
        backend_result = cls._backend_full_check(content)
        if backend_result:
            # 补充 retry_hint
            if not backend_result.get("pass", True):
                issues = backend_result.get("issues", [])
                specific_hints = issues[:5]
                backend_result["retry_hint"] = (
                    "【质检反馈·必须修正（后端37+项）】\n"
                    + "\n".join(f"  - {h}" for h in specific_hints)
                    + "\n请针对以上问题逐条修正后重写。"
                )
            else:
                backend_result["retry_hint"] = ""
            return backend_result

        # 降级到原有7项检测
        return cls._basic_check(stage_id, content, min_length, platform, chapter_num, mode)

    @classmethod
    def _backend_full_check(cls, content):
        """使用后端observability.py的AutoRewriteEngine做37+项质检"""
        try:
            from pathlib import Path as _Path
            backend_dir = str(_Path(__file__).parent / "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            from observability import AutoRewriteEngine
            engine = AutoRewriteEngine()
            inspection = engine.full_inspection(content)
            if not inspection:
                return None

            defects = inspection.get("defects", {})
            # defects 可能是 dict {"items": [...], "scores": [...], "total_defects": N}
            if isinstance(defects, dict):
                defect_items = defects.get("items", [])
            elif isinstance(defects, list):
                defect_items = defects
            else:
                defect_items = []
            issues = []
            score = 1.0

            for d in defect_items[:15]:
                if isinstance(d, dict):
                    severity = d.get("severity", "warning")
                    desc = d.get("description", str(d))[:80]
                else:
                    severity = "warning"
                    desc = str(d)[:80]
                issues.append(f"[{severity}] {desc}")
                if severity == "critical":
                    score -= 0.1
                elif severity == "warning":
                    score -= 0.05

            return {
                "pass": len(defect_items) == 0,
                "score": round(max(score, 0.0), 2),
                "issues": issues,
                "retry_hint": "",
                "source": "backend_37+",
                "defect_count": len(defect_items),
            }
        except ImportError:
            return None
        except Exception as e:
            print(f"[QualityGate] 后端质检失败: {e}")
            return None

    @classmethod
    def _basic_check(cls, stage_id: int, content: str, min_length: int = 50,
                     platform: str = "qimao", chapter_num: int = 1, mode: str = "general") -> Dict[str, Any]:
        """原有7项检测（降级方案）"""
        issues = []
        score = 1.0

        # 基础检查
        if not content or len(content.strip()) < min_length:
            issues.append(f"内容过短（{len(content)}字，预期≥{min_length}字）")
            score -= 0.5

        # W2/W4: 使用 quality_checker 的规则引擎质检
        if stage_id in [2, 4]:
            try:
                from quality_checker import check_chapter, ChapterQualityReport
                report = check_chapter(content, platform=platform, chapter_num=chapter_num, mode=mode)

                # 将 fatal 级问题转为 issues
                for fatal in report.fatals:
                    detail = fatal['detail']
                    if fatal.get('line'):
                        detail = f"第{fatal['line']}行: {detail}"
                    issues.append(detail)
                    score -= 0.15

                # 将 warning 级问题也记录，但扣分较少
                for warning in report.warnings:
                    issues.append(warning['detail'])
                    score -= 0.05

            except ImportError:
                # 降级到原有的简单检查
                ai_patterns = {
                    "他感到": 0.05, "他心中": 0.05, "他暗道": 0.05, "他心里": 0.05,
                    "缓缓地": 0.03, "淡淡地": 0.03, "微微地": 0.03,
                    "忽然": 0.03, "突然": 0.03, "猛然": 0.03,
                    "不是……而是": 0.10, "不是...而是": 0.10,
                }
                for pattern, penalty in ai_patterns.items():
                    count = content.count(pattern)
                    if count > 0:
                        per_1000 = count / max(len(content) / 1000, 1)
                        if per_1000 > 1.0:
                            issues.append(f"'{pattern}'出现{count}次（{per_1000:.1f}/千字，超阈值）")
                            score -= penalty * min(per_1000, 3)

                # 句长检查（粗略: 统计句号分隔的句子）
                sentences = [s.strip() for s in re.split(r'[。！？\n]', content) if s.strip()]
                if sentences:
                    short_sentences = sum(1 for s in sentences if len(s) <= 10)
                    avg_len = sum(len(s) for s in sentences) / len(sentences)
                    short_ratio = short_sentences / len(sentences)

                    if avg_len < 15:
                        issues.append(f"平均句长仅{avg_len:.0f}字（预期≥25字，AI写法特征）")
                        score -= 0.15
                    if short_ratio > 0.4:
                        issues.append(f"短句率{short_ratio:.0%}过高（预期≤40%）")
                        score -= 0.10

                    # 连续短句检查
                    consecutive_short = 0
                    max_consecutive_short = 0
                    for s in sentences:
                        if len(s) <= 10:
                            consecutive_short += 1
                            max_consecutive_short = max(max_consecutive_short, consecutive_short)
                        else:
                            consecutive_short = 0
                    if max_consecutive_short >= 5:
                        issues.append(f"出现{max_consecutive_short}句连续短句（典型AI写法）")
                        score -= 0.10

            # 统计检测（无论 quality_checker 是否可用都执行）
            stat_issues = QualityGate._statistical_check(content)
            issues.extend(stat_issues)
            score -= 0.05 * len(stat_issues)

            # === 新增检测：词汇疲劳 ===
            word_fatigue_issues = cls._check_word_fatigue(content)
            if word_fatigue_issues:
                issues.extend(word_fatigue_issues)

            # === 新增检测：角色行为合理性 ===
            character_issues = cls._check_character_behavior(content, mode)
            if character_issues:
                issues.extend(character_issues)

            # === 新增检测：8维质量评分 ===
            score_8d_issues = cls._check_8d_score(content, mode)
            if score_8d_issues:
                issues.extend(score_8d_issues)

        score = max(0.0, score)
        passed = score >= 0.7 and len([i for i in issues if '致命' in i or 'fatal' in i.lower()]) <= 1

        retry_hint = ""
        if not passed:
            # 构建更具体的重试反馈
            specific_hints = []
            for issue in issues[:5]:
                if '第' in issue and '行' in issue:
                    specific_hints.append(issue)  # 已包含行号的问题
                elif '建议' in issue or '替换' in issue:
                    specific_hints.append(issue)
                else:
                    specific_hints.append(issue)

            retry_hint = "【质检反馈·必须修正】\n" + "\n".join(f"  - {h}" for h in specific_hints)
            retry_hint += "\n请针对以上问题逐条修正后重写。"

        return {
            "pass": passed,
            "score": round(score, 2),
            "issues": issues,
            "retry_hint": retry_hint,
        }

    @staticmethod
    def _statistical_check(content: str) -> list:
        """统计检测：用数学指标检测AI痕迹"""
        issues = []

        # 1. 句长变异系数 CV_L
        sentences = [s.strip() for s in re.split(r'[。！？\n]', content) if s.strip()]
        if len(sentences) >= 5:
            lengths = [len(s) for s in sentences]
            mean_len = sum(lengths) / len(lengths)
            if mean_len > 0:
                std_len = (sum((l - mean_len)**2 for l in lengths) / len(lengths)) ** 0.5
                cv = std_len / mean_len
                if cv < 0.25:
                    issues.append(f"句长变异系数CV_L={cv:.2f}过低（<0.25为AI特征，目标≥0.30）")

            # 2. 连续等长句检测
            same_len_count = 0
            for i in range(1, len(lengths)):
                if abs(lengths[i] - lengths[i-1]) <= 3:
                    same_len_count += 1
            if same_len_count / max(len(lengths)-1, 1) > 0.5:
                issues.append(f"连续等长句比例{same_len_count/(len(lengths)-1):.0%}过高（AI特征：句子长度过于均匀）")

        # 3. 标点熵检测
        punct_count = {}
        total_punct = 0
        for ch in content:
            if ch in '。！？，、；：……——':
                punct_count[ch] = punct_count.get(ch, 0) + 1
                total_punct += 1
        if total_punct > 10:
            import math
            entropy = -sum((c/total_punct) * math.log2(c/total_punct) for c in punct_count.values() if c > 0)
            if entropy < 1.0:
                issues.append(f"标点熵H={entropy:.2f}过低（<1.0说明标点单一，AI特征）")

        return issues

    @staticmethod
    def _check_word_fatigue(text):
        """词汇疲劳检测（对标InkOS）"""
        # 用jieba分词（优先），降级用正则
        words = []
        try:
            import jieba
            words = [w for w in jieba.cut(text) if len(w) >= 2 and re.match(r'^[\u4e00-\u9fff]+$', w)]
        except ImportError:
            # 降级：只匹配标点分隔的2-4字词
            words = re.findall(r'(?<=[，。！？；：、\s""''「」])[\u4e00-\u9fff]{2,4}(?=[，。！？；：、\s""''「」])', text)
            if not words:
                words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)

        if not words:
            return []

        counter = Counter(words)
        total_chars = len(text)
        if total_chars == 0:
            return []

        # 功能词白名单（不算疲劳）
        whitelist = {"一个", "已经", "可以", "没有", "不是", "什么", "这个", "那个",
                     "自己", "他们", "我们", "就是", "但是", "因为", "所以", "如果",
                     "虽然", "只是", "还是", "而且", "或者", "然后", "于是", "可能",
                     "什么", "怎么", "这样", "那样", "这些", "那些", "时候", "地方",
                     "起来", "出来", "下来", "上去", "过去", "回来", "过来", "出来",
                     "突然", "缓缓", "渐渐", "默默", "静静", "淡淡", "微微"}

        fatigued = []
        for word, count in counter.most_common(20):
            if word in whitelist:
                continue
            freq = count / total_chars * 1000  # 每千字出现次数
            if freq > 5:  # 每千字5次以上算疲劳
                fatigued.append(f"词汇疲劳: '{word}' 出现{count}次({freq:.1f}次/千字)")

        return fatigued

    @staticmethod
    def _check_8d_score(text, mode="general"):
        """10维质量评分+StoryScope缺陷检测"""
        try:
            from knowledge.quality_10d import full_10d_score
            result = full_10d_score(text, mode)
            issues = []
            # 低于5分的维度标记为问题
            for dim, score in result["scores"].items():
                if score < 5:
                    issues.append(f"10维评分[{dim}]={score}/10，需改进")
            # 最弱维度特别提示
            if result["avg_score"] < 6:
                issues.append(f"10维均分={result['avg_score']}，最弱维度: {result['weakest']}")
            # StoryScope缺陷
            for d in result.get("storyscope_defects", []):
                issues.append(f"StoryScope缺陷[{d['defect']}]: {d['fix']}")
            return issues
        except ImportError:
            # 降级到8维
            try:
                from knowledge.quality_8d import full_8d_score
                result = full_8d_score(text, mode)
                issues = []
                for dim, score in result["scores"].items():
                    if score < 5:
                        issues.append(f"8维评分[{dim}]={score}/10，需改进")
                if result["avg_score"] < 6:
                    issues.append(f"8维均分={result['avg_score']}，最弱维度: {result['weakest']}")
                return issues
            except ImportError:
                return []

    @staticmethod
    def _check_character_behavior(text, mode="general"):
        """角色行为合理性检查（Would They Really? 测试）"""
        issues = []

        # 通用检查：主角说"求求你"但人设不是软弱型
        mc_patterns = [
            (r'求求你', "主角出现'求求你'，与强势人设不符"),
            (r'我不行了', "主角出现'我不行了'，与坚韧人设不符"),
            (r'放过我吧', "主角出现'放过我吧'，与不屈人设不符"),
        ]

        for pattern, warning in mc_patterns:
            if re.search(pattern, text):
                issues.append(warning)

        # 检测"所有角色说话方式一样"
        dialogues = re.findall(r'[""「]([^""」]{5,})[""」]', text)
        if len(dialogues) >= 4:
            # 检查对话长度是否都差不多
            lengths = [len(d) for d in dialogues]
            avg = sum(lengths) / len(lengths)
            similar = sum(1 for l in lengths if abs(l - avg) < 5)
            if similar / len(lengths) > 0.8:
                issues.append(f"对话声线单一: {similar}/{len(lengths)}句对话长度相似(均{avg:.0f}字)")

        return issues


# ============================================================
# 阶段基类（Stage Base）
# ============================================================

class Stage:
    """
    工作流阶段基类。每个具体阶段只需实现:
    - STAGE_ID / STAGE_NAME
    - build_user_input()      把StageInput转换成给AI的user消息
    - parse_output()          把AI返回的字符串解析成StageOutput
    """

    STAGE_ID = -1
    STAGE_NAME = "未命名"
    MIN_OUTPUT_LENGTH = 50
    MAX_RETRIES = 2  # 初次调用 + 2次重试 = 最多3次

    def __init__(self):
        self.wdb = None  # 车间数据库(可选)
        self.call_ai_func = None  # AI调用函数(必须设置)
        self.use_ai = True

    def set_dependencies(self, call_ai_func: Callable, wdb=None, use_ai: bool = True):
        """设置依赖"""
        self.call_ai_func = call_ai_func
        self.wdb = wdb
        self.use_ai = use_ai

    def get_workshop_prompt_path(self) -> Path:
        """获取车间原始prompt文件路径（可选，子类覆盖）"""
        return None

    def build_user_input(self, input_data: StageInput) -> str:
        """构建给AI的user消息（子类必须覆盖）"""
        raise NotImplementedError

    def parse_output(self, raw_output: str, input_data: StageInput, elapsed: float) -> StageOutput:
        """解析AI输出（子类覆盖以做结构化解析）"""
        return StageOutput(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            content=raw_output or "",
            summary=raw_output[:300] if raw_output else "",
            success=bool(raw_output and len(raw_output) > self.MIN_OUTPUT_LENGTH),
            message="OK" if raw_output else "AI返回空内容",
            elapsed_time=elapsed,
        )

    def run(self, input_data: StageInput) -> StageOutput:
        """
        执行一个阶段：
        1. 用KnowledgeInjector构建system_msg
        2. 构建user_input
        3. 调用AI
        4. 质检
        5. 不通过则带着质检意见重试
        """
        assert self.call_ai_func is not None, "必须先调用set_dependencies设置AI调用函数"

        print(f"\n  [W{self.STAGE_ID}] {self.STAGE_NAME}...")
        t0 = time.time()

        # 1. 构建system_msg（知识注入）
        workshop_prompt = ""
        prompt_path = self.get_workshop_prompt_path()
        if prompt_path and prompt_path.exists():
            workshop_prompt = prompt_path.read_text(encoding='utf-8')

        system_msg = KnowledgeInjector.inject_for_stage(
            stage_id=self.STAGE_ID,
            mode=input_data.mode,
            platform=input_data.platform,
            workshop_prompt=workshop_prompt,
        )

        # 模式数据注入：加载模式专属配置 + CSV数据 + 风格指纹 + 平台配置
        if HAS_MODE_INJECTOR:
            mode_injection = ModeDataInjector.get_injection(
                stage_id=self.STAGE_ID,
                mode=input_data.mode,
                platform=input_data.platform,
                chapter_task=input_data.chapter_task,
                chapter_num=input_data.current_chapter,
                project_dir=input_data.project_dir,
            )
            if mode_injection:
                system_msg += "\n\n" + mode_injection

        # ★ L10: Story System 合同注入（从 webnovel-writer 移植）
        if input_data.project_dir and self.STAGE_ID >= 1:
            try:
                from pangu_core.story_contracts import build_and_inject_chapter_contract
                contract_text = build_and_inject_chapter_contract(
                    input_data.project_dir,
                    chapter=input_data.current_chapter,
                    chapter_task=input_data.chapter_task,
                    mode=input_data.mode,
                    platform=input_data.platform,
                )
                if contract_text:
                    system_msg += "\n\n" + contract_text
            except ImportError:
                pass  # story_contracts 不可用，降级
            except Exception as e:
                print(f"    [WARN] Story合同注入失败: {e}")

        # ★ L11: 长期记忆注入（从 webnovel-writer memory/ 移植）
        if input_data.project_dir and self.STAGE_ID in (2, 4):
            try:
                from pangu_core.memory_layers import PanguMemoryOrchestrator
                from pangu_core.memory_layers import build_memory_injection
                orchestrator = PanguMemoryOrchestrator(Path(input_data.project_dir))
                memory_pack = orchestrator.build_memory_pack(
                    chapter=input_data.current_chapter,
                    task_type="write",
                )
                if memory_pack:
                    injection = build_memory_injection(memory_pack)
                    if injection:
                        system_msg += "\n\n" + injection
            except ImportError:
                pass  # memory_layers 不可用，降级
            except Exception as e:
                print(f"    [WARN] 记忆注入失败: {e}")

        # ★ L12: Beat Sheet 故事节拍约束（受Sudowrite Story Engine启发）
        # 将章节拆为3-5个beat，每个beat有明确目标，AI必须按节拍写作
        if HAS_BEAT_SHEET and input_data.project_dir and self.STAGE_ID == 2:
            try:
                beat_injection = build_and_inject_beat_sheet(
                    input_data.project_dir,
                    chapter_num=input_data.current_chapter,
                    chapter_task=input_data.chapter_task,
                    mode=input_data.mode,
                    platform=input_data.platform,
                    call_ai_func=self.call_ai_func if self.use_ai else None,
                )
                if beat_injection:
                    system_msg += "\n\n" + beat_injection
                    print(f"    [BeatSheet] 节拍约束已注入")
            except Exception as e:
                print(f"    [WARN] BeatSheet注入失败: {e}")

        # 2. 构建user消息
        user_input = self.build_user_input(input_data)

        # 3+4. 调用AI + 质检 + 重试
        retry_count = 0
        last_content = ""
        last_issues = []
        step_id = None

        # 如果有workshop数据库，记录步骤
        if self.wdb:
            try:
                step_id = self.wdb.create_workshop_step(
                    input_data.extra.get("task_id", 0),
                    self.STAGE_ID,
                    user_input[:1000],
                )
                if step_id:
                    self.wdb.start_workshop_step(step_id)
            except Exception as e:
                print(f"    [WARN] 记录步骤失败: {e}")

        while retry_count <= self.MAX_RETRIES:
            # 如果是重试，带上上次的问题
            current_user_input = user_input
            if retry_count > 0 and last_issues:
                feedback = "\n\n【上一版的问题，请修正】\n" + "\n".join(f"  - {i}" for i in last_issues[:5])
                current_user_input = user_input + feedback

            # 调用AI
            if self.use_ai:
                raw_output = self.call_ai_func(current_user_input, system_msg=system_msg)
            else:
                raw_output = f"[W{self.STAGE_ID} 模拟输出] {self.STAGE_NAME}占位内容"

            elapsed = time.time() - t0

            # 解析输出
            output = self.parse_output(raw_output, input_data, elapsed)
            last_content = output.content

            # 质检
            qc_result = QualityGate.check(
                self.STAGE_ID, output.content, self.MIN_OUTPUT_LENGTH,
                platform=input_data.platform,
                chapter_num=input_data.current_chapter,
                mode=input_data.mode,
            )

            if qc_result["pass"]:
                # 通过质检
                output.success = True
                output.message = f"通过质检(score={qc_result['score']})"
                output.metadata["qc_score"] = qc_result["score"]
                output.metadata["qc_issues"] = qc_result["issues"]
                break
            else:
                # 未通过，记录问题准备重试
                last_issues = qc_result["issues"]
                retry_count += 1
                if retry_count <= self.MAX_RETRIES:
                    print(f"    质检未通过(score={qc_result['score']}), 第{retry_count}次重试...")
                    print(f"    问题: {'; '.join(last_issues[:2])}")
                else:
                    # 最后一次也不通过，但仍返回结果
                    output.success = True  # 即使不完美也继续（带警告）
                    output.message = f"质检低分通过(score={qc_result['score']}, 问题{len(last_issues)}个)"
                    output.metadata["qc_score"] = qc_result["score"]
                    output.metadata["qc_issues"] = qc_result["issues"]

        # 记录到数据库
        if step_id and self.wdb:
            try:
                from . import CONFIG  # 尝试获取全局配置
                model = getattr(CONFIG, 'get', lambda k, default=None: default)('model', 'unknown')
                temperature = 0.7
            except:
                model = "unknown"
                temperature = 0.7
            try:
                self.wdb.complete_workshop_step(
                    step_id, last_content, model, model, temperature, len(last_content)
                )
            except Exception as e:
                pass

        elapsed_total = time.time() - t0
        print(f"    完成 ({elapsed_total:.1f}s, {len(last_content)}字)")
        return output


# ============================================================
# 工作流引擎（Workflow Engine）
# ============================================================

class WorkflowEngine:
    """
    工作流调度器：按顺序执行所有Stage，管理状态流转，支持断点续传。
    """

    def __init__(self, call_ai_func: Callable, wdb=None, use_ai: bool = True):
        self.stages: List[Stage] = []
        self.call_ai_func = call_ai_func
        self.wdb = wdb
        self.use_ai = use_ai
        self.results: Dict[int, StageOutput] = {}

    def add_stage(self, stage: Stage):
        """添加一个阶段"""
        stage.set_dependencies(self.call_ai_func, self.wdb, self.use_ai)
        self.stages.append(stage)

    def run(self, initial_input: Dict[str, Any], resume_from: int = -1) -> Dict[str, Any]:
        """
        运行整个工作流。
        initial_input: 初始输入字典 {title, chapter_task, mode, platform, current_chapter, ...}
        resume_from: 从哪个阶段恢复(-1=从头开始, 2=跳过W0/W1直接从W2开始)
        """
        # 构建StageInput
        input_data = StageInput(
            title=initial_input.get("title", ""),
            chapter_task=initial_input.get("chapter_task", ""),
            mode=initial_input.get("mode", "general"),
            platform=initial_input.get("platform", "qimao"),
            current_chapter=initial_input.get("current_chapter", 1),
            context=initial_input.get("context", ""),
            project_dir=initial_input.get("project_dir", ""),
            previous_outputs={},
            extra=initial_input.get("extra", {}),
        )

        print("=" * 60)
        print(f"  盘古V7小说工厂工作流")
        print(f"  作品: {input_data.title} | 第{input_data.current_chapter}章")
        print(f"  模式: {input_data.mode} | 平台: {input_data.platform}")
        print("=" * 60)

        # ============ Write Gate: prewrite（写前关卡）============
        if HAS_WRITE_GATES and input_data.project_dir:
            try:
                prewrite_report = run_write_gate(
                    input_data.project_dir,
                    chapter=input_data.current_chapter,
                    stage="prewrite",
                )
                if not prewrite_report.get("ok", True):
                    blocker_errors = [e for e in prewrite_report.get("errors", [])
                                      if e.get("severity") == "blocker"]
                    if blocker_errors:
                        print(f"  [GATE:prewrite] ⛔ 写前关卡阻断({len(blocker_errors)}个blocker)")
                        for err in blocker_errors[:3]:
                            print(f"    - {err.get('code')}: {err.get('message')}")
                        print(f"    → {blocker_errors[0].get('repair', '请修复后重试')}")
                        # 阻断模式：返回空结果（可配置为继续）
                        return {
                            "final_content": "",
                            "final_summary": f"prewrite gate blocked: {blocker_errors[0].get('code')}",
                            "all_outputs": {},
                            "success": False,
                            "gate_reports": {"prewrite": prewrite_report},
                        }
                    # 非blocker的warning只打日志，不阻断
                    warnings = prewrite_report.get("warnings", [])
                    if warnings:
                        print(f"  [GATE:prewrite] ⚠ {len(warnings)}个警告")
                        for w in warnings[:2]:
                            print(f"    - {w.get('code')}: {w.get('message')}")
                else:
                    print(f"  [GATE:prewrite] ✅ 写前关卡通过")
            except Exception as e:
                print(f"  [GATE:prewrite] ⚠ 关卡异常: {e}，继续执行")

        # 执行各阶段
        for stage in self.stages:
            # 跳过已完成的阶段（断点续传）
            if stage.STAGE_ID <= resume_from:
                # 如果有之前的结果，加载进来
                if stage.STAGE_ID in self.results:
                    input_data.previous_outputs[stage.STAGE_ID] = self.results[stage.STAGE_ID].content
                    print(f"\n  [W{stage.STAGE_ID}] 跳过(已有结果)")
                continue

            # 执行阶段
            result = stage.run(input_data)
            self.results[stage.STAGE_ID] = result

            # 把结果塞到input里，下一阶段可以读取
            input_data.previous_outputs[stage.STAGE_ID] = result.content

            # 如果失败，终止流程
            if not result.success and stage.STAGE_ID >= 2:
                print(f"\n  [W{stage.STAGE_ID}] 失败，终止工作流: {result.message}")
                break

        # 返回最终结果
        final_stage_id = max(self.results.keys()) if self.results else -1
        final_result = self.results.get(final_stage_id)

        print("\n" + "=" * 60)
        print("  工作流执行完毕")
        print("=" * 60)
        for sid in sorted(self.results.keys()):
            r = self.results[sid]
            status = "OK" if r.success else "FAIL"
            print(f"  W{sid} {r.stage_name}: {status} ({r.elapsed_time:.1f}s, {len(r.content)}字)")

        # ============ Write Gate: precommit（写后提交前关卡）============
        if HAS_WRITE_GATES and input_data.project_dir and final_result:
            try:
                precommit_report = run_write_gate(
                    input_data.project_dir,
                    chapter=input_data.current_chapter,
                    stage="precommit",
                    content=final_result.content,
                )
                if not precommit_report.get("ok", True):
                    blocker_errors = [e for e in precommit_report.get("errors", [])
                                      if e.get("severity") == "blocker"]
                    if blocker_errors:
                        print(f"  [GATE:precommit] ⛔ 提交前关卡阻断({len(blocker_errors)}个blocker)")
                        for err in blocker_errors[:3]:
                            print(f"    - {err.get('code')}: {err.get('message')}")
                        # precommit阻断：不更新state，但仍然返回内容（降级模式）
                        print(f"    → 继续执行但跳过状态更新")
                    else:
                        warnings = precommit_report.get("warnings", [])
                        if warnings:
                            print(f"  [GATE:precommit] ⚠ {len(warnings)}个警告")
                else:
                    print(f"  [GATE:precommit] ✅ 提交前关卡通过")
            except Exception as e:
                print(f"  [GATE:precommit] ⚠ 关卡异常: {e}，继续执行")

        # ★ Beat Sheet 合规检查：验证最终输出是否满足节拍约束
        if HAS_BEAT_SHEET and input_data.project_dir and final_result:
            try:
                from pangu_core.beat_sheet import get_beat_compliance_report
                state_path = Path(input_data.project_dir) / "state.json"
                if state_path.exists():
                    with open(state_path, "r", encoding="utf-8") as sf:
                        chk_state = json.load(sf)
                    chapter_beats = chk_state.get("beat_sheet", {}).get(str(input_data.current_chapter))
                    if chapter_beats and isinstance(chapter_beats, list):
                        compliance = get_beat_compliance_report(final_result.content, chapter_beats)
                        if compliance["compliant"]:
                            print(f"  [BeatSheet] ✅ 节拍合规 (覆盖率{compliance['coverage']:.0%})")
                        else:
                            print(f"  [BeatSheet] ⚠ 节拍未完全覆盖 (覆盖率{compliance['coverage']:.0%}, 缺失: {', '.join(compliance['missing_beats'][:3])})")
            except Exception as e:
                print(f"  [BeatSheet] ⚠ 合规检查失败: {e}")

        # 记忆银行：W4完成后自动提取记忆
        if HAS_MEMORY_BANK and 4 in self.results and input_data.project_dir:
            try:
                final_content = self.results[4].content
                mb = MemoryBank(input_data.project_dir)
                mb.extract_from_chapter(
                    chapter_num=input_data.current_chapter,
                    chapter_content=final_content,
                    call_ai_func=None,
                )
                print(f"  [记忆] 第{input_data.current_chapter}章记忆已提取")
            except Exception as e:
                print(f"  [WARN] 记忆提取失败: {e}")

        # ============ Write Gate: postcommit（提交后关卡）============
        if HAS_WRITE_GATES and input_data.project_dir:
            try:
                postcommit_report = run_write_gate(
                    input_data.project_dir,
                    chapter=input_data.current_chapter,
                    stage="postcommit",
                )
                if not postcommit_report.get("ok", True):
                    errors = postcommit_report.get("errors", [])
                    warnings = postcommit_report.get("warnings", [])
                    if errors:
                        print(f"  [GATE:postcommit] ⛔ 提交后关卡发现{len(errors)}个错误")
                        for err in errors[:3]:
                            print(f"    - {err.get('code')}: {err.get('message')}")
                    if warnings:
                        print(f"  [GATE:postcommit] ⚠ {len(warnings)}个警告")
                        for w in warnings[:2]:
                            print(f"    - {w.get('code')}: {w.get('message')}")
                else:
                    print(f"  [GATE:postcommit] ✅ 提交后关卡通过")
            except Exception as e:
                print(f"  [GATE:postcommit] ⚠ 关卡异常: {e}")

        return {
            "final_content": final_result.content if final_result else "",
            "final_summary": final_result.summary if final_result else "",
            "all_outputs": {sid: r.to_dict() for sid, r in self.results.items()},
            "success": all(r.success for r in self.results.values()),
        }


# ============================================================
# 具体阶段实现（Concrete Stages）
# ============================================================

class W0AnchorStage(Stage):
    """W0: 主旨锚定"""
    STAGE_ID = 0
    STAGE_NAME = "主旨锚定"
    MIN_OUTPUT_LENGTH = 20

    def get_workshop_prompt_path(self) -> Path:
        return Path(__file__).parent / "workshops" / "workshop_0_anchor" / "system_prompt.txt"

    def build_user_input(self, input_data: StageInput) -> str:
        return (
            f"一句话故事：{input_data.title}——{input_data.chapter_task}\n"
            f"平台：{input_data.platform}\n"
            f"请输出JSON格式的主旨锚定。"
        )


class W1SetupStage(Stage):
    """W1: 设定预处理"""
    STAGE_ID = 1
    STAGE_NAME = "设定预处理"
    MIN_OUTPUT_LENGTH = 100

    def get_workshop_prompt_path(self) -> Path:
        return Path(__file__).parent / "workshops" / "workshop_1_setup" / "system_prompt.txt"

    def build_user_input(self, input_data: StageInput) -> str:
        w0_out = input_data.previous_outputs.get(0, "")[:300]

        # RAG注入：检索与章节任务相关的写作提示
        rag_hints = ""
        try:
            from knowledge.rag_injector import get_writing_hints
            rag_hints = get_writing_hints(
                mode=input_data.mode,
                chapter_task=input_data.chapter_task,
                platform=input_data.platform,
                chapter_num=input_data.current_chapter,
            )
        except ImportError:
            pass

        # 记忆银行：获取前文追踪信息
        memory_context = ""
        if HAS_MEMORY_BANK and input_data.project_dir:
            try:
                mb = MemoryBank(input_data.project_dir)
                memory_context = mb.get_context_for_chapter(input_data.current_chapter)
                if memory_context:
                    memory_context = f"\n【前文记忆追踪】\n{memory_context[:500]}\n"
            except Exception:
                pass

        base = (
            f"全书冷库摘要：{input_data.title}，{input_data.mode}模式\n"
            f"本章任务：{input_data.chapter_task}\n"
            f"近3章：{input_data.context[:500] if input_data.context else '（首章）'}\n"
            f"W0主旨：{w0_out}\n"
        )
        if memory_context:
            base += memory_context
        if rag_hints:
            base += f"\n{rag_hints}\n"

        base += "请输出【本章热库】（500字以内）："
        return base


class W2DraftStage(Stage):
    """W2: 正文初稿"""
    STAGE_ID = 2
    STAGE_NAME = "正文初稿"
    MIN_OUTPUT_LENGTH = 500

    def get_workshop_prompt_path(self) -> Path:
        return Path(__file__).parent / "workshops" / "workshop_2_draft" / "system_prompt.txt"

    def build_user_input(self, input_data: StageInput) -> str:
        w1_out = input_data.previous_outputs.get(1, "")[:500]

        # RAG注入：风格锚点
        style_anchor = ""
        try:
            from knowledge.rag_injector import get_style_anchor
            style_anchor = get_style_anchor(input_data.mode, input_data.platform)
        except ImportError:
            pass

        # 数学引擎guidance：基于前文分析给出写作建议
        math_guidance = ""
        try:
            from knowledge.pangu_math_core import PanguMathEngine
            math_engine = PanguMathEngine()
            # 如果有前文，分析前文给出建议
            prev_text = input_data.context[:2000] if input_data.context else ""
            if prev_text and len(prev_text) > 200:
                analysis = math_engine.full_analysis(prev_text)
                guidance = math_engine.get_guidance_prompt(analysis, mode=input_data.mode)
                if guidance:
                    math_guidance = f"\n【数学引擎·写作建议】\n{guidance[:300]}\n"
        except Exception:
            pass

        # 创作引擎策略
        strategy_hint = ""
        try:
            from knowledge.creative_engine import CreativeEngine
            ce = CreativeEngine()
            strategy = ce.recommend_strategy(input_data.current_chapter, mode=input_data.mode)
            if strategy:
                prompt = ce.get_strategy_prompt(strategy, mode=input_data.mode)
                if prompt:
                    strategy_hint = f"\n【创作策略·{strategy}】\n{prompt[:200]}\n"
        except Exception:
            pass

        base = (
            f"本章热库：{w1_out}\n"
            f"本章任务：{input_data.chapter_task}\n"
            f"字数：2000字\n"
        )
        if style_anchor:
            base += f"\n{style_anchor}\n"
        if math_guidance:
            base += math_guidance
        if strategy_hint:
            base += strategy_hint

        base += "请输出【正文初稿】："
        return base


class W3QCStage(Stage):
    """W3: 逻辑质检"""
    STAGE_ID = 3
    STAGE_NAME = "逻辑质检"
    MIN_OUTPUT_LENGTH = 100

    def get_workshop_prompt_path(self) -> Path:
        return Path(__file__).parent / "workshops" / "workshop_3_qc" / "system_prompt.txt"

    def build_user_input(self, input_data: StageInput) -> str:
        w1_out = input_data.previous_outputs.get(1, "")[:300]
        w2_out = input_data.previous_outputs.get(2, "")[:2000]
        return (
            f"本章热库：{w1_out}\n"
            f"正文初稿：{w2_out}\n"
            f"请输出【质检报告】+【修正后的骨架】："
        )


class W4PolishStage(Stage):
    """W4: 文笔精修 + 质量闭环改写"""
    STAGE_ID = 4
    STAGE_NAME = "文笔精修"
    MIN_OUTPUT_LENGTH = 800
    QUALITY_THRESHOLD = 65.0  # 质量阈值

    def get_workshop_prompt_path(self) -> Path:
        return Path(__file__).parent / "workshops" / "workshop_4_polish" / "system_prompt.txt"

    def build_user_input(self, input_data: StageInput) -> str:
        w3_out = input_data.previous_outputs.get(3, "")[:2000]
        # 如果W3不可用，用W2
        if not w3_out or len(w3_out.strip()) < 100:
            w3_out = input_data.previous_outputs.get(2, "")[:2000]

        # 风格指纹指引：基于真人网文数据给出精修方向
        style_guidance = ""
        try:
            from knowledge.style_fingerprint import StyleDatabase
            sdb = StyleDatabase()
            guidance = sdb.get_writing_guidance(input_data.mode)
            if guidance:
                style_guidance = f"\n【风格指纹·精修指引】\n{guidance[:300]}\n"
        except Exception:
            pass

        # 战斗场景检测
        genre = MODE_TO_GENRE.get(input_data.mode, "通用")
        combat_keywords = ["战斗", "打", "杀", "对决", "交锋", "反击", "逆袭", "爆发", "燃"]
        is_combat = any(kw in input_data.chapter_task for kw in combat_keywords)

        base = (
            f"修正后的骨架：{w3_out}\n"
            f"模式：{input_data.mode}\n"
            f"字数：2000字\n"
        )
        if style_guidance:
            base += style_guidance
        if is_combat:
            base += "\n【注意】本章包含战斗/高燃场景，请使用战斗模式精修：加速用短句(8-12字)，力量用长句(35+字)，揭示用极短句(3-5字)\n"

        base += "请输出【成品章节】："
        return base

    def run(self, input_data: StageInput) -> StageOutput:
        """W4执行：精修 + 可选的迭代改写"""
        # 先执行标准的Stage.run()获取精修结果
        result = super().run(input_data)

        if not result.success:
            return result

        # 质量闭环：如果精修后评分仍低于阈值，执行分维度改写
        qc_score = result.metadata.get("qc_score", 1.0)
        if qc_score < 0.75 and self.call_ai_func and self.use_ai:
            try:
                from knowledge.rewrite_pass import run_rewrite_passes
                print(f"    W4评分{qc_score:.2f}较低，启动分维度改写...")
                rewrite_result = run_rewrite_passes(
                    content=result.content,
                    call_ai_func=self.call_ai_func,
                    platform=input_data.platform,
                    chapter_num=input_data.current_chapter,
                    quality_threshold=self.QUALITY_THRESHOLD,
                    max_passes=2,  # 最多2轮改写，控制成本
                )
                if rewrite_result["improved"]:
                    result.content = rewrite_result["final_content"]
                    result.metadata["rewrite_passes"] = rewrite_result["passes_done"]
                    result.metadata["rewrite_initial_score"] = rewrite_result["initial_score"]
                    result.metadata["rewrite_final_score"] = rewrite_result["final_score"]
                    print(f"    改写完成: {rewrite_result['initial_score']:.1f}→{rewrite_result['final_score']:.1f} ({rewrite_result['passes_done']}轮)")
            except ImportError:
                pass  # rewrite_pass不可用，跳过

        return result


# ============================================================
# 便捷函数（Convenience Functions）
# ============================================================

def build_default_workflow(call_ai_func: Callable, wdb=None, use_ai: bool = True) -> WorkflowEngine:
    """构建默认的W0-W4工作流"""
    engine = WorkflowEngine(call_ai_func, wdb, use_ai)
    engine.add_stage(W0AnchorStage())
    engine.add_stage(W1SetupStage())
    engine.add_stage(W2DraftStage())
    engine.add_stage(W3QCStage())
    engine.add_stage(W4PolishStage())
    return engine


def run_workflow_pipeline(call_ai_func: Callable, initial_input: Dict[str, Any],
                         wdb=None, use_ai: bool = True,
                         collaborative_mode: str = None) -> Dict[str, Any]:
    """
    一行代码运行完整工作流。
    这是给外部调用者的主要接口。

    collaborative_mode:
        None / "api_auto"  — 纯API流水线（默认）
        "api_review"       — API写+人审校（推荐）
        "human_review"     — 人写+API辅助审校
        "human"            — 人精写（不调用API，由外部提供内容）

    initial_input示例:
        {
            "title": "我的小说",
            "chapter_task": "主角初入宗门，发现异常",
            "mode": "xianxia",
            "platform": "qimao",
            "current_chapter": 1,
            "context": "",  # 前几章的摘要
        }
    """
    # 协作模式：人精写，不走流水线
    if collaborative_mode == "human":
        return {
            "final_content": "",
            "final_summary": "",
            "all_outputs": {},
            "success": True,
            "collaborative_mode": "human",
            "message": "人精写模式：请手动编写本章内容，完成后使用审校清单检查",
        }

    # API流水线模式
    engine = build_default_workflow(call_ai_func, wdb, use_ai)

    # 协作模式：注入平台硬约束到每个车间
    if collaborative_mode in ("api_review", "human_review"):
        try:
            from writing_protocol import CollaborativeWritingProtocol
            project_dir = initial_input.get("project_dir", "")
            if project_dir:
                protocol = CollaborativeWritingProtocol(project_dir)
                chapter_num = initial_input.get("current_chapter", 1)
                constraints_prompt = protocol.get_chapter_constraints_prompt(chapter_num)
                # 将约束注入到initial_input的extra中
                if "extra" not in initial_input:
                    initial_input["extra"] = {}
                initial_input["extra"]["collaborative_constraints"] = constraints_prompt
        except ImportError:
            pass

    result = engine.run(initial_input)

    # 协作模式：API写完后标记需要审校
    if collaborative_mode in ("api_review", "human_review"):
        result["collaborative_mode"] = collaborative_mode
        result["needs_review"] = True
        result["review_checklist"] = _get_review_checklist()

    return result


def _get_review_checklist() -> str:
    """获取审校清单"""
    return """【审校清单 — 逐项检查】

□ 1. 对话率是否≥42%？
□ 2. 主角说话是否≤10字？
□ 3. 有无禁用词？（他感到/缓缓地/突然/瞳孔/嘴角勾起）
□ 4. 有无心理描写？（"他知道""他感到""他意识到"）
□ 5. 纯描写段落是否≤30字？
□ 6. 每300字有无微钩子？
□ 7. 章末钩子是否足够强？
□ 8. 人设是否一致？
□ 9. 剧情是否按大纲走？
□ 10. 伏笔是否按计划埋/收？"""


if __name__ == "__main__":
    # 简单自测
    print("Workflow Engine v1.0 - 自测模式")
    print("-" * 40)

    # 模拟一个call_ai函数
    def mock_ai(prompt, system_msg=None, model=None):
        # 模拟返回一些简单文本，用于测试流程
        if "主旨锚定" in (system_msg or ""):
            return '{"hook": "他发现了一个不该存在的东西...", "conflict": "宗门规则与真相的冲突", "expected_payoff": "揭露真相的爽感"}'
        elif "设定预处理" in (system_msg or ""):
            return "【场景】青云宗后山，深夜\n【人物】主角: 刚入门弟子，状态: 警惕\n【关键设定】宗门有'不可夜入后山'的铁规\n【本章任务】主角因好奇违反规则，发现了隐藏的秘密"
        elif "正文初稿" in (system_msg or ""):
            # 故意写一些"AI味"的文本来测试质检门
            return ("他缓缓地睁开眼睛，感到一阵剧烈的头痛。四周一片漆黑，他感到心中充满了不安。\n"
                   "他站起身来，慢慢地向前走去。忽然，他听到了什么声音。\n"
                   "他停下脚步，淡淡地说道：'谁？' 没有人回答。他感到心跳加速，微微地颤抖了一下。\n"
                   "他继续向前走，发现了一道亮光从门缝中透出。他感到事情有些不对劲。\n"
                   "他推开门，看到了一个巨大的房间。房间里摆满了各种奇怪的东西。他感到十分震惊。\n"
                   "在房间的中央，有一个祭坛。祭坛上放着一本古老的书。他感到这本书一定很重要。\n"
                   "他走过去，拿起那本书。书页翻开，上面写着四个字：'不要打开'。\n"
                   "他感到犹豫了一下，但最终还是决定打开它。他慢慢地翻开了第一页。\n"
                   "书页上的文字开始发光。他感到一股强大的力量从书中涌出。他猛然向后退去。\n"
                   "书合上了。房间恢复了寂静。他站在那里，心跳还在加速。\n"
                   "他知道，从这一刻起，一切都改变了。他的命运，已经和这本书绑在了一起。\n\n"
                   "（为了达到2000字的要求，我需要在这里添加更多的内容。他环顾四周，发现房间的墙壁上刻满了奇怪的符号。\n"
                   "这些符号在黑暗中发出微弱的光芒，似乎在讲述一个古老的故事。他走近墙壁，仔细地观察着这些符号。\n"
                   "符号讲述的是一个关于禁忌的传说，一个关于力量与代价的故事。他感到自己的呼吸变得急促起来。\n"
                   "他知道，他刚刚打开的不仅仅是一本书。那是一个封印，一个被前人小心守护的秘密。\n"
                   "而现在，那个封印，已经被他打破了。\n")
        elif "逻辑质检" in (system_msg or ""):
            return "【质检报告】\n1. 逻辑基本通顺，但有AI味词汇（缓缓地/淡淡地/感到）\n2. 钩子有效\n3. 人物动机合理\n\n【修正后的骨架】\n(保留了W2的核心剧情，润色了对话和叙述)"
        else:
            return "这是精修后的成品章节文本。包含环境描写、心理描写、镜头语言等，字数约2000字。"

    # 测试知识注入
    print("\n[测试1] 知识注入测试 - W2的system_msg长度:")
    sys_msg = KnowledgeInjector.inject_for_stage(2, "xianxia", "qimao", "")
    print(f"  W2 system_msg: {len(sys_msg)}字")
    print(f"  包含'句式硬约束': {'句式硬约束' in sys_msg}")
    print(f"  包含'AI禁令': {'AI禁令' in sys_msg}")
    print(f"  包含'μ_L': {'μ_L' in sys_msg}")

    print("\n[测试2] 工作流完整执行（模拟AI）")
    result = run_workflow_pipeline(
        call_ai_func=mock_ai,
        initial_input={
            "title": "青云宗秘闻",
            "chapter_task": "主角夜入后山，发现宗门禁忌",
            "mode": "xianxia",
            "platform": "qimao",
            "current_chapter": 1,
            "context": "",
        },
        use_ai=True,
    )

    print(f"\n  最终结果: success={result['success']}")
    print(f"  最终内容字数: {len(result['final_content'])}字")
    for sid, data in sorted(result['all_outputs'].items()):
        print(f"  W{sid}: {len(data['content'])}字, qc_score={data.get('metadata', {}).get('qc_score', 'N/A')}")

    print("\n[测试3] 质检门测试")
    test_content = "他感到很伤心。他缓缓地转过身。突然，他听到了什么。他淡淡地笑了。"
    qc = QualityGate.check(2, test_content)
    print(f"  测试文本: '{test_content[:50]}...'")
    print(f"  质检结果: pass={qc['pass']}, score={qc['score']}, issues={len(qc['issues'])}个")
    for issue in qc['issues']:
        print(f"    - {issue}")

    print("\n所有测试完成！")
