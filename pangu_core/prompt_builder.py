#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 统一Prompt注入链

将 pangu_optimized.py 的 build_smart_prompt() 和
workflow_engine.py 的 KnowledgeInjector.inject() 合并为
统一的 PromptBuilder 类。

17层Prompt注入链:
- L01: 系统角色 (system role)
- L02: 模式规则 (mode rules, from MODE_TO_GENRE + mode JSON)
- L03: 平台规则 (platform rules)
- L04: 风格指引 (style guidance + style vault + engine/math/genre/emotion)
- L05: 句式参数 (sentence params, from SentenceParams)
- L06: 参考材料 (reference material)
- L07: 前文摘要 (previous summary/context)
- L08: 角色状态 (character states + Lorebook) [T02: DbPipeline]
- L09: 伏笔线索 (foreshadowing threads) [T02: DbPipeline]
- L10: 故事合约 (story contracts) [T02: StoryContracts]
- L11: 记忆层 (memory layers) [T02: MemoryOrchestrator]
- L12: RAG检索 (RAG retrieval) [T02: PanguHybridRAG]
- L13: 节拍表 (beat sheet)
- L14: 章节任务 (chapter task + opening_boost + taboo_line)
- L15: 数据库上下文 (DB context summary) [T02: DbPipeline]
- L16: 格式规则 (format rules: De-AI + IQ firewall + 视角 + 感官)
- L17: 最终包装 (final wrap: format instruction)
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .config import BASE_DIR
from .prompts import (
    GENRE_PARAMS,
    MODE_TO_GENRE,
    SentenceParams,
    get_genre_for_mode,
    get_params_for_mode,
)


# ============ 缓存 ============

_UNIVERSAL_PROMPT_CACHE: Optional[str] = None
_PLATFORM_RULES_CACHE: Optional[str] = None
_SENTENCE_REF_V3_CACHE: Optional[str] = None
_DE_AI_RULES_CACHE: Optional[str] = None


# ============ PromptBuilder ============

class PromptBuilder:
    """统一Prompt注入链构建器。

    将 build_smart_prompt() 的17层注入逻辑和 KnowledgeInjector 的
    阶段感知知识注入合并为统一的PromptBuilder。

    用法:
        builder = PromptBuilder()
        # 构建完整prompt（单字符串，17层拼接）
        full_prompt = builder.build_full_prompt(context)
        # 构建分离的system/user消息（推荐，AI调用时使用）
        system_msg, user_msg = builder.build_system_and_user(context, stage_id="W2")
        # 构建单层prompt（用于W0锚定等场景）
        layer_prompt = builder.build_layer("L01", context)
    """

    def __init__(self, config: Any = None):
        self.config = config

    def build_full_prompt(self, context: Any) -> str:
        """构建完整17层prompt，返回拼接后的单字符串。

        Args:
            context: PipelineContext实例

        Returns:
            17层prompt拼接后的完整字符串
        """
        parts = []
        parts.append(self._L01_system_role(context))
        parts.append(self._L02_mode_rules(context))
        parts.append(self._L03_platform_rules(context))
        parts.append(self._L04_style_guidance(context))
        parts.append(self._L05_sentence_params(context))
        parts.append(self._L06_reference_material(context))
        parts.append(self._L07_previous_summary(context))
        parts.append(self._L08_character_states(context))
        parts.append(self._L09_foreshadowing(context))
        parts.append(self._L10_story_contracts(context))
        parts.append(self._L11_memory_layers(context))
        parts.append(self._L12_rag_retrieval(context))
        parts.append(self._L13_beat_sheet(context))
        parts.append(self._L14_chapter_task(context))
        parts.append(self._L15_db_context(context))
        parts.append(self._L16_format_rules(context))
        parts.append(self._L17_final_wrap(context))
        return "\n\n".join(p for p in parts if p)

    def build_system_and_user(
        self, context: Any, stage_id: str = "W2"
    ) -> Tuple[str, str]:
        """构建分离的system_msg和user_msg。

        这是AI调用时推荐使用的方法，因为AI API通常需要
        分离的system和user消息。

        System消息包含: L01-L13, L15-L16 (规则、约束、上下文)
        User消息包含: L14, L17 (任务指令、格式要求)

        Args:
            context: PipelineContext实例
            stage_id: 当前Stage ID，用于阶段感知的知识注入

        Returns:
            (system_msg, user_msg) 元组
        """
        # 设置当前stage_id到context（供各层方法读取）
        context.set("current_stage_id", stage_id)

        # System消息：规则、约束、上下文
        system_parts = []
        system_parts.append(self._L01_system_role(context))
        system_parts.append(self._L02_mode_rules(context))
        system_parts.append(self._L03_platform_rules(context))
        system_parts.append(self._L04_style_guidance(context))
        system_parts.append(self._L05_sentence_params(context))
        system_parts.append(self._L06_reference_material(context))
        system_parts.append(self._L07_previous_summary(context))
        system_parts.append(self._L08_character_states(context))
        system_parts.append(self._L09_foreshadowing(context))
        system_parts.append(self._L10_story_contracts(context))
        system_parts.append(self._L11_memory_layers(context))
        system_parts.append(self._L12_rag_retrieval(context))
        system_parts.append(self._L13_beat_sheet(context))
        system_parts.append(self._L15_db_context(context))
        system_parts.append(self._L16_format_rules(context))
        system_msg = "\n\n".join(p for p in system_parts if p)

        # User消息：任务指令、格式要求
        user_parts = []
        user_parts.append(self._L14_chapter_task(context))
        user_parts.append(self._L17_final_wrap(context))
        user_msg = "\n\n".join(p for p in user_parts if p)

        return system_msg, user_msg

    def build_layer(self, layer_id: str, context: Any) -> str:
        """构建单层prompt，用于W0锚定等场景。

        Args:
            layer_id: 层ID，如"L01"/"L05"等
            context: PipelineContext实例

        Returns:
            单层prompt字符串
        """
        layer_map = {
            "L01": self._L01_system_role,
            "L02": self._L02_mode_rules,
            "L03": self._L03_platform_rules,
            "L04": self._L04_style_guidance,
            "L05": self._L05_sentence_params,
            "L06": self._L06_reference_material,
            "L07": self._L07_previous_summary,
            "L08": self._L08_character_states,
            "L09": self._L09_foreshadowing,
            "L10": self._L10_story_contracts,
            "L11": self._L11_memory_layers,
            "L12": self._L12_rag_retrieval,
            "L13": self._L13_beat_sheet,
            "L14": self._L14_chapter_task,
            "L15": self._L15_db_context,
            "L16": self._L16_format_rules,
            "L17": self._L17_final_wrap,
        }
        method = layer_map.get(layer_id)
        if method is None:
            return ""
        return method(context)

    # ================================================================
    # L01: 系统角色
    # 迁移自: _load_universal_prompt() + KnowledgeInjector的角色定义
    # ================================================================

    def _L01_system_role(self, ctx: Any) -> str:
        """构建系统角色提示。

        合并了 pangu_optimized.py 的 _load_universal_prompt() 和
        workflow_engine.py KnowledgeInjector 的角色定义。
        """
        stage_id = ctx.get("current_stage_id", "W2")
        parts = []

        # 加载通用写作规则文件
        universal = _load_universal_prompt()
        if universal:
            parts.append(universal)

        # 阶段感知的角色定义（迁移自KnowledgeInjector.inject_for_stage）
        role_text = self._get_stage_role(stage_id, ctx)
        if role_text:
            parts.append(role_text)

        return "\n\n".join(p for p in parts if p)

    def _get_stage_role(self, stage_id: str, ctx: Any) -> str:
        """根据Stage ID生成角色定义文本。

        迁移自 workflow_engine.py 的 KnowledgeInjector.inject_for_stage()
        中的角色定义部分。
        """
        mode_name = ctx.get("mode_name", "general")
        genre = get_genre_for_mode(mode_name)
        params = get_params_for_mode(mode_name)

        if stage_id == "W0":
            return (
                "【角色】你是盘古V7.0小说工厂的【主旨锚定车间】，代号W0。\n"
                "【任务】根据一句话故事，产出本章的核心钩子和冲突。\n"
                "【设计原则】每章结尾必须有钩子让读者想看下一章；"
                "钩子类型（悬念/危机/反转/期待/情感）需要轮换。\n"
                '【输出】纯JSON: {"hook": "章末钩子", "conflict": "本章核心冲突", '
                '"expected_payoff": "读者期待的回报"}'
            )
        elif stage_id == "W1":
            return (
                "【角色】你是盘古V7.0小说工厂的【设定预处理车间】，代号W1。\n"
                "【任务】提取本章需要的场景、人物状态、关键设定，形成'本章热库'。\n"
                "【设计原则】本章热库只保留本章必须用到的信息（约500字）。\n"
                f"【题材模式】当前题材: {genre}\n"
                "【输出】纯文本: 场景列表+人物状态+关键设定+本章任务解析。"
            )
        elif stage_id == "W2":
            platform = ctx.get("platform_name", "qimao")
            dia_pct = "35%" if platform in ("qimao", "fanqie") else "30%"
            return (
                "你是起点中文网顶级签约作家。写玄幻小说章节。\n\n"
                f"【核心要求】本章必须有大量对话，对话占比≥{dia_pct}。用\"X说：\"格式。"
                "人物之间要有多轮对话，每段对话3-5句。对话推进剧情、展示人物性格、制造冲突。\n"
                "对话后跟一句动作描写。如：\n"
                '  "状元公，接旨吧。"太监尖声道。\n'
                '  沈夜拱手："敢问公公，将我调往何处？"\n'
                '  "镇妖司。"太监将密旨塞进他手里，转身便走。\n'
                '  沈夜追问："为何是我？"\n'
                '  太监头也不回："去了便知。"\n\n'
                "对话为主，叙述为辅。不要大段环境描写。句均25-30字，2500-3000字。"
            )
        elif stage_id == "W3":
            return (
                "【角色】你是盘古V2.0小说工厂的【逻辑质检车间】，代号W3。\n"
                "【任务】检查W2骨架的逻辑一致性，输出两部分：(1)JSON质检报告 (2)修正后的骨架。\n"
                "【质检清单】\n"
                "  1. 时间线：事件先后顺序是否合理？\n"
                "  2. 人物一致性：行为是否符合性格设定？\n"
                "  3. 因果链：每个行动有动机和后果吗？\n"
                "  4. 设定矛盾：是否违反已建立的规则？\n"
                "  5. 信息完整：是否有缺失的关键动作或冗余重复？\n"
                "  6. 钩子有效性：章末是否留了有效钩子？\n"
                "  7. 禁用词检查：是否出现了W2禁止的内容（环境/心理/氛围/比喻/情绪词）？\n\n"
                "【输出格式】\n"
                "```json\n"
                '{"passed": true/false, "score": 0-10, "issues": [...], "fixed_skeleton": "修正后的完整骨架"}\n'
                "```\n"
                "必须提供 fixed_skeleton 字段——这是W4精修车间的输入。"
            )
        elif stage_id == "W4":
            mode_name = ctx.get("mode_name", "general")
            mode_rules = _get_w4_mode_rules(mode_name)
            return (
                f"【角色】你是盘古V2.0小说工厂的【文笔精修车间】，代号W4。\n"
                f"【任务】接收W3修正后的骨架，添加质感、情绪、镜头、氛围，输出最终成品。\n"
                f"【核心原则】只化妆，不动刀——不改剧情/不改人物行为/不添加新事件。\n\n"
                f"{mode_rules}"
            )
        else:
            return f"【角色】盘古V7.0小说工厂【写作车间】{stage_id}。完成写作任务。"

    # ================================================================
    # L02: 模式规则
    # 迁移自: _load_mode_deep_injection() + load_mode_rules() + DB mode_vibe
    # ================================================================

    def _L02_mode_rules(self, ctx: Any) -> str:
        """构建模式规则提示。

        合并了 pangu_optimized.py 的 _load_mode_deep_injection() 和
        load_mode_rules() 的逻辑，以及 workflow_engine.py 中
        从DB获取的 mode_vibe。
        """
        mode_name = ctx.get("mode_name", "general")
        mode_rule = ctx.get("mode_rule", "")

        parts = []

        # 1. 从 modes/ JSON 加载深度规则
        deep_injection = _load_mode_deep_injection(mode_name)
        if deep_injection:
            parts.append(f"## 模式深度规则（{mode_name}）\n{deep_injection}")

        # 2. PipelineConfig预加载的mode_rule
        if mode_rule:
            parts.append(f"## 模式基础规则\n{mode_rule}")

        # 3. 从数据库获取模式微调（如有unified_db）
        db_vibe = self._load_mode_vibe_from_db(mode_name)
        if db_vibe:
            parts.append(f"## 模式微调\n{db_vibe}")

        return "\n\n".join(p for p in parts if p)

    def _load_mode_vibe_from_db(self, mode_name: str) -> str:
        """从统一数据库获取模式核心原则和钩子类型。"""
        try:
            from .db import get_db
            db = get_db()
            if db is None:
                return ""
            mode = db.get_mode(mode_name)
            if not mode:
                return ""
            parts = []
            core = mode.get("core_principle", "")
            if core:
                parts.append(f"模式内核：{core}")
            w2 = mode.get("workshop_configs", {}).get("w2_special", {})
            hook_types = w2.get("hook_types", [])
            if hook_types:
                parts.append(f"推荐钩子类型：{', '.join(hook_types)}")
            return " ".join(parts) if parts else ""
        except Exception:
            return ""

    # ================================================================
    # L03: 平台规则
    # 迁移自: _extract_platform_section() + _PLATFORM_RULES
    # ================================================================

    def _L03_platform_rules(self, ctx: Any) -> str:
        """构建平台规则提示。

        合并了 pangu_optimized.py 的 _extract_platform_section() 和
        KnowledgeInjector._get_platform_rules() 的逻辑。
        """
        platform_name = ctx.get("platform_name", "qimao")
        stage_id = ctx.get("current_stage_id", "W2")

        # 只在W2/W4阶段注入详细平台规则
        if stage_id not in ("W2", "W4"):
            return ""

        parts = []

        # 1. 从 platform_rules.txt 提取指定平台的约束
        platform_section = _extract_platform_section(platform_name)
        if platform_section:
            parts.append(f"## 平台专属约束（当前目标平台）\n{platform_section}")

        # 2. PipelineConfig预加载的platform_rule
        platform_rule = ctx.get("platform_rule", "")
        if platform_rule:
            parts.append(f"## 平台基础规则\n{platform_rule}")

        # 3. 简要平台约束（迁移自KnowledgeInjector._get_platform_rules）
        brief = self._get_brief_platform_rules(platform_name)
        if brief:
            parts.append(brief)

        return "\n\n".join(p for p in parts if p)

    def _get_brief_platform_rules(self, platform: str) -> str:
        """获取简要平台约束（迁移自KnowledgeInjector._get_platform_rules）。"""
        platform_rules_map = {
            "qimao": (
                "【平台约束·七猫】\n"
                "  - 目标读者：25-40岁女性为主\n"
                "  - 情绪优先级：爽感 > 悬念 > 情感 > 设定\n"
                "  - 段落长度：手机端每段≤3行\n"
                "  - 章末钩子必须强（'让读者想立刻点下一章'是唯一标准）"
            ),
            "fanqie": (
                "【平台约束·番茄】\n"
                "  - 目标读者：全年龄段，算法驱动分发\n"
                "  - 开头300字必须抓眼球——黄金前三章规则\n"
                "  - 每800-1200字一个爽点或反转\n"
                "  - 段落极短（1-2句一段为主）\n"
                "  - 信息密度高，拒绝慢热"
            ),
            "qidian": (
                "【平台约束·起点】\n"
                "  - 目标读者：18-35岁男性为主\n"
                "  - 强调设定严谨、逻辑自洽\n"
                "  - 允许较长段落和复杂句式\n"
                "  - 世界观铺陈可慢热但必须有长线钩子"
            ),
        }
        return platform_rules_map.get(platform, "")

    # ================================================================
    # L04: 风格指引
    # 迁移自: _load_style_guidance + _load_style_vault +
    #          _load_engine_guidance + _load_math_guidance +
    #          _load_genre_template_hints + _extract_emotion_anchors
    # ================================================================

    def _L04_style_guidance(self, ctx: Any) -> str:
        """构建风格指引提示。

        合并了6个风格相关的加载函数:
        - _load_style_guidance(): 风格指纹数据库
        - _load_style_vault(): V1.0风格映射
        - _load_engine_guidance(): 创作引擎战略推荐
        - _load_math_guidance(): 数学引擎优化指引
        - _load_genre_template_hints(): 题材CSV模板
        - _extract_emotion_anchors(): 情绪锚点
        """
        mode_name = ctx.get("mode_name", "general")
        platform_name = ctx.get("platform_name", "qimao")
        chapter_num = ctx.get("chapter_num", 1)
        chapter_task = ctx.get("chapter_task", "")

        parts = []

        # 1. 风格指纹指引
        style_guidance = _load_style_guidance(mode_name, platform_name)
        if style_guidance:
            parts.append(f"## 同类型成功作品的量化风格参考\n{style_guidance}")

        # 2. 风格库自动匹配
        style_vault = _load_style_vault(mode_name, chapter_task)
        if style_vault:
            parts.append(f"## 风格库匹配指引\n{style_vault}")

        # 3. 创作引擎战略推荐
        engine_guidance = _load_engine_guidance(mode_name, platform_name, chapter_num)
        if engine_guidance:
            parts.append(
                f"## 创作引擎战略推荐（基于{chapter_num}章位置分析）\n{engine_guidance}"
            )

        # 4. 数学引擎优化指引
        math_guidance = _load_math_guidance(chapter_task, chapter_num, platform_name)
        if math_guidance:
            parts.append(f"## 数学引擎优化指引（梯度分析）\n{math_guidance}")

        # 5. 题材模板自动注入
        genre_template_hints = _load_genre_template_hints(mode_name, chapter_task)
        if genre_template_hints:
            parts.append(f"## 题材模板指引\n{genre_template_hints}")

        # 6. 情绪锚点注入
        state = ctx.get("state", {})
        emotion_anchor_hints = _extract_emotion_anchors(state, chapter_num)
        if emotion_anchor_hints:
            parts.append(f"## 情绪锚点（本章应重点营造的情绪）\n{emotion_anchor_hints}")

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L05: 句式参数
    # 迁移自: _build_sentence_constraints() + KnowledgeInjector W2/W4句式注入
    # ================================================================

    def _L05_sentence_params(self, ctx: Any) -> str:
        """构建句式参数硬约束提示。

        合并了 pangu_optimized.py 的 _build_sentence_constraints() 和
        workflow_engine.py KnowledgeInjector 的 W2/W4 句式参数注入。
        """
        mode_name = ctx.get("mode_name", "general")
        stage_id = ctx.get("current_stage_id", "W2")
        genre = get_genre_for_mode(mode_name)
        params = get_params_for_mode(mode_name)

        parts = []

        # 核心句式硬约束（迁移自_build_sentence_constraints + KnowledgeInjector W2）
        parts.append(f"""【句式硬约束 · 题材:{genre}】
你写的每一段文字必须满足以下参数（来自真人网文统计）：

变量定义: n=句数, L_i=第i句字数, μ_L=平均句长=(1/n)ΣL_i, p_long=长句率, CV_L=句长变异系数

必须达到:
  平均句长 μ_L ≥ {params.mu_L}字        （AI通常只写8-15字，必须加长）
  长句率 p_long ≥ {params.p_long}           （31字以上的句子占比，写复合句）
  句长变异 CV_L = σ_L/μ_L ≥ 0.30      （不许写一样长的句子）
  最长句/最短句 ≥ 5                     （制造节奏冲击）
  标点熵 H_punct ≥ 1.0                  （不许全是句号，要有问号/叹号/破折号）
  描写句占比 ≈ {params.p_describe}
  叙述推进句占比 ≈ {params.p_narrate}
  动作句占比 ≈ {params.p_action}
  核心写作模式: {params.core_pattern}

绝对禁止（AI常犯，真人几乎不写）:
  ❌ 连续3句都是 ≤12字的短句
  ❌ "他感到/他心中/他暗道/他心里" + 情绪词（写具体动作替代）
  ❌ "缓缓地/淡淡地/微微地/静静地/轻轻地"每1000字 ≤ 2个
  ❌ "忽然/突然/猛然/骤然"每1000字 ≤ 3个
  ❌ "不是……而是……"判断结构
  ❌ 每句对话都单独换行（对话嵌入叙述中）

改写操作: 短句→扩展动作+细节；抽象情绪→具体动作；纯对话→叙述+动作+对话混合""")

        # W4额外的精修技术标准（迁移自KnowledgeInjector W4）
        if stage_id == "W4":
            parts.append("""【精修技术标准】
  1. 环境描写：每个场景至少有一个"锚定细节"——让读者记住这个场景的具象元素
  2. 心理描写：不直接写"他感到悲伤"，写"他的手指无意识地摩挲着杯沿"
  3. 氛围渲染：用天气/光线/声音/气味营造情绪基调，但不超过全文20%
  4. 镜头语言：明确每段的"机位"——全景？中景？特写？主观镜头？
  5. 对话润色：去掉冗余的"他说""她说"，用动作代替说话人标识
  极短揭示句(1-10字)占比 ≈ 0.10（制造节奏冲击点）""")

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L06: 参考材料
    # 迁移自: state.json 的 references 字段 + _load_sentence_reference_v3
    # ================================================================

    def _L06_reference_material(self, ctx: Any) -> str:
        """构建参考材料提示。

        从 state.json 的 references 字段加载参考材料，
        以及加载句式结构参考v3。
        """
        state = ctx.get("state", {})
        parts = []

        # 1. state.json中的references
        references = state.get("references", [])
        if references and isinstance(references, list):
            ref_texts = []
            for ref in references[:5]:
                if isinstance(ref, str):
                    ref_texts.append(ref)
                elif isinstance(ref, dict):
                    title = ref.get("title", "")
                    content = ref.get("content", "")
                    if title and content:
                        ref_texts.append(f"【{title}】\n{content[:500]}")
            if ref_texts:
                parts.append("## 参考材料\n" + "\n\n".join(ref_texts))

        # 2. 句式结构参考v3（如有）
        sentence_ref = _load_sentence_reference_v3()
        if sentence_ref:
            # 只截取前800字，避免prompt过长
            parts.append("## 句式结构参考\n" + sentence_ref[:800])

        # 3. 优先级参考书检索 (按 priority_score 排序)
        priority_refs = _load_priority_references(ctx)
        if priority_refs:
            parts.append("## 高优先级参考书（按参考价值排序）\n" + priority_refs)

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L07: 前文摘要
    # 迁移自: context_content (previous chapters)
    # ================================================================

    def _L07_previous_summary(self, ctx: Any) -> str:
        """构建前文摘要提示。

        从 PipelineContext 的 context_content 字段读取前文内容。
        """
        context_content = ctx.get("context_content", "")
        if not context_content:
            return ""
        return context_content

    # ================================================================
    # L08: 角色状态 (含Lorebook注入)
    # 迁移自: _inject_lorebook() + state characters
    # T02: 将由DbPipeline提供数据
    # ================================================================

    def _L08_character_states(self, ctx: Any) -> str:
        """构建角色状态提示（含Lorebook强制注入）。

        合并了 pangu_optimized.py 的 _inject_lorebook() 和
        state 中的角色状态数据。

        T02阶段将由DbPipeline提供更完整的角色状态数据。
        """
        state = ctx.get("state", {})
        chapter_task = ctx.get("chapter_task", "")
        context_content = ctx.get("context_content", "")

        parts = []

        # 1. Lorebook强制注入（迁移自_inject_lorebook）
        lorebook_injection = _inject_lorebook(state, chapter_task, context_content)
        if lorebook_injection:
            parts.append(f"## 世界观设定（Lorebook强制约束）\n{lorebook_injection}")

        # 2. 角色状态（从state.json）
        characters = state.get("characters", {})
        if isinstance(characters, dict):
            protagonist = characters.get("protagonist", {})
            key_chars = characters.get("key_characters", [])

            char_parts = []
            if protagonist.get("name"):
                state_str = protagonist.get("current_state", "状态未知")
                char_parts.append(f"主角: {protagonist['name']}，{state_str}")
                if protagonist.get("location"):
                    char_parts.append(f"  位置: {protagonist['location']}")

            for char in key_chars[:5]:
                name = char.get("name", "")
                char_state = char.get("current_state", "")
                if name:
                    if char_state:
                        char_parts.append(f"  {name}: {char_state}")
                    else:
                        char_parts.append(f"  {name}")

            if char_parts:
                parts.append("## 角色状态\n" + "\n".join(char_parts))

        # T02: 从DbContext补充角色状态
        db_context = ctx.get("db_context")
        if db_context:
            try:
                char_states = db_context.character_states
                if char_states:
                    db_char_parts = []
                    for cs in char_states[:8]:
                        name = cs.get("name", "")
                        state_str = cs.get("current_state", "")
                        location = cs.get("location", "")
                        if name:
                            line = f"  {name}: {state_str}"
                            if location:
                                line += f" (位置: {location})"
                            db_char_parts.append(line)
                    if db_char_parts:
                        parts.append("## 角色状态(DB补充)\n" + "\n".join(db_char_parts))
            except Exception:
                pass  # DbContext读取失败，不影响已有数据

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L09: 伏笔线索
    # 迁移自: _build_foreshadow_reminder() + state foreshadowing
    # T02: 将由DbPipeline提供数据
    # ================================================================

    def _L09_foreshadowing(self, ctx: Any) -> str:
        """构建伏笔追踪提示。

        迁移自 pangu_optimized.py 的 _build_foreshadow_reminder()。

        T02阶段将由DbPipeline提供更完整的伏笔数据。
        """
        state = ctx.get("state", {})
        chapter_num = ctx.get("chapter_num", 1)

        parts = []

        # 1. 伏笔追踪提醒（迁移自_build_foreshadow_reminder）
        foreshadow = state.get("foreshadowing", {})
        if isinstance(foreshadow, list):
            active_threads = foreshadow
        else:
            active_threads = foreshadow.get("active_threads", [])

        if active_threads:
            reminders = []
            for t in active_threads:
                if t.get("status") != "open":
                    continue
                planted = t.get("planted_ch", 0)
                age = chapter_num - planted
                desc = t.get("description", "未知线索")
                if age >= 2:
                    urgency = "⚠ 需要推进" if age >= 5 else "可继续延续"
                    reminders.append(f"- 第{planted}章埋设: {desc} ({urgency})")

            if reminders:
                parts.append(
                    "【伏笔提醒】以下是前文埋下的活跃伏笔，注意在本章中延续或兑现：\n"
                    + "\n".join(reminders[:5])
                )

        # 2. 超龄伏笔紧迫提醒
        open_threads = [t for t in active_threads if t.get("status") == "open"]
        urgent = [t for t in open_threads if chapter_num - t.get("planted_ch", 0) >= 3]
        if urgent:
            parts.append(
                f"⚠ 有{len(urgent)}条伏笔已超过3章未兑现，本章需要推进或收束其中至少1条"
            )

        # T02: 从DbContext补充伏笔线索
        db_context = ctx.get("db_context")
        if db_context:
            try:
                fs_threads = db_context.foreshadowing_threads
                if fs_threads:
                    fs_parts = []
                    for ft in fs_threads[:8]:
                        desc = ft.get("description", "")
                        status = ft.get("status", "")
                        planted = ft.get("planted_ch", 0)
                        if desc and status in ("open", "active"):
                            fs_parts.append(f"- [DB] 第{planted}章埋设: {desc}")
                    if fs_parts:
                        parts.append("## 伏笔线索(DB补充)\n" + "\n".join(fs_parts))
            except Exception:
                pass

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L10: 故事合约
    # T02: 将由StoryContracts提供
    # ================================================================

    def _L10_story_contracts(self, ctx: Any) -> str:
        """构建故事合约提示。

        T02阶段将由StoryContracts.build_for_stage()提供。
        """
        project_dir = ctx.get("project_dir", "")
        chapter_num = ctx.get("chapter_num", 1)
        chapter_task = ctx.get("chapter_task", "")
        mode_name = ctx.get("mode_name", "general")
        platform_name = ctx.get("platform_name", "qimao")

        try:
            from .story_contracts import build_and_inject_chapter_contract
            contract = build_and_inject_chapter_contract(
                project_dir, chapter_num,
                chapter_task=chapter_task,
                mode=mode_name,
                platform=platform_name,
            )
            if contract:
                return contract
        except ImportError:
            pass
        except Exception:
            pass
        return ""

    # ================================================================
    # L11: 记忆层
    # T02: 将由MemoryOrchestrator提供
    # ================================================================

    def _L11_memory_layers(self, ctx: Any) -> str:
        """构建记忆层提示。

        T02阶段将由MemoryOrchestrator.build_for_pipeline()提供。
        """
        project_dir = ctx.get("project_dir", "")
        chapter_num = ctx.get("chapter_num", 1)

        try:
            from .memory_layers import build_and_inject_memory
            memory_text = build_and_inject_memory(project_dir, chapter_num, task_type="write")
            if memory_text:
                return memory_text
        except ImportError:
            pass
        except Exception:
            pass
        return ""

    # ================================================================
    # L12: RAG检索
    # T02: 将由PanguHybridRAG提供
    # ================================================================

    def _L12_rag_retrieval(self, ctx: Any) -> str:
        """构建RAG检索提示。

        优先使用 rag_engine (FAISS/NumPy), 降级到 rag_hybrid。
        无可用后端时返回空，不阻塞Pipeline。
        """
        chapter_task = ctx.get("chapter_task", "")
        project_dir = ctx.get("project_dir", "")

        # 1. 新引擎 (FAISS优先)
        try:
            from .rag_engine import search_for_chapter
            results = search_for_chapter(chapter_task, project_dir, k=3)
            if results:
                parts = [f"- [RAG] {r.content[:200]}" for r in results]
                return "## RAG检索结果\n" + "\n".join(parts)
        except ImportError:
            pass

        # 2. 旧引擎 (降级)
        try:
            from .rag_hybrid import PanguHybridRAG
            from .config import BASE_DIR
            from pathlib import Path
            import asyncio

            rag = ctx.get("rag_instance")
            if rag is None:
                knowledge_dir = Path(project_dir) if project_dir else BASE_DIR / "knowledge"
                rag = PanguHybridRAG(knowledge_dir, use_rerank=False)
                try:
                    rag.initialize([])
                except Exception:
                    pass
                ctx.set("rag_instance", rag)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    results = []
                else:
                    results = loop.run_until_complete(
                        rag.hybrid_search(chapter_task, top_k=3))
            except RuntimeError:
                results = asyncio.run(rag.hybrid_search(chapter_task, top_k=3))

            if results:
                parts = [f"- [RAG] {r.content[:200]}" for r in results[:3]]
                if parts:
                    return "## RAG检索结果\n" + "\n".join(parts)
        except Exception:
            pass

        return ""

    # ================================================================
    # L13: 节拍表
    # 迁移自: _inject_beat_sheet() + _generate_beat_sheet()
    # ================================================================

    def _L13_beat_sheet(self, ctx: Any) -> str:
        """构建Beat Sheet故事节拍约束提示。

        迁移自 pangu_optimized.py 的 _inject_beat_sheet()。
        """
        state = ctx.get("state", {})
        chapter_num = ctx.get("chapter_num", 1)

        beat_sheet = state.get("beat_sheet", {})
        chapter_beats = beat_sheet.get(str(chapter_num))

        if not chapter_beats or not isinstance(chapter_beats, list):
            return ""
        if len(chapter_beats) == 0:
            return ""

        lines = ["本章必须严格按照以下故事节拍（Beat Sheet）生成，不得遗漏任何节拍："]
        total_words = 0
        for i, beat in enumerate(chapter_beats):
            if not isinstance(beat, dict):
                continue
            beat_name = beat.get("beat", f"节拍{i+1}")
            goal = beat.get("goal", "")
            mood = beat.get("mood", "")
            words = beat.get("words", 400)
            total_words += words
            mood_str = f"，情绪：{mood}" if mood else ""
            lines.append(
                f"  Beat {i+1}「{beat_name}」({words}字)：目标——{goal}{mood_str}"
            )

        lines.append(f"\n总字数约{total_words}字。每个beat必须完整达成目标后才能进入下一个beat。")
        lines.append(
            "⚠ Beat Sheet是强制约束，不是建议。如果最终输出缺少任何beat的目标，视为生成失败。"
        )

        return "## 故事节拍（Beat Sheet强制约束）\n" + "\n".join(lines)

    # ================================================================
    # L14: 章节任务
    # 迁移自: build_smart_prompt() user_msg 的任务部分
    # ================================================================

    def _L14_chapter_task(self, ctx: Any) -> str:
        """构建章节任务提示。

        合并了 build_smart_prompt() 中 user_msg 的任务部分：
        - 书名和章节号
        - 开篇加强（黄金三章）
        - AI高风险词提醒
        - 章节任务正文
        """
        title = ctx.get("title", "")
        chapter_num = ctx.get("chapter_num", 1)
        chapter_task = ctx.get("chapter_task", "")
        platform_name = ctx.get("platform_name", "qimao")
        mode_name = ctx.get("mode_name", "general")

        parts = []

        # 1. 开篇加强（黄金三章）
        is_opening = chapter_num <= 3
        opening_boost = ""
        if is_opening:
            opening_boost = (
                f"\n⚠️ 这是黄金三章的第{chapter_num}章。"
                "必须严格遵守开篇规则：第一句话发生事情，主角主动行动，"
                f"金手指必须在{'500' if platform_name == 'fanqie' else '800'}字内展示或暗示，章末留强钩子。"
            )

        # 2. AI高风险词提醒
        taboo_line = ""
        taboo_words = self._get_taboo_words(platform_name)
        if taboo_words:
            taboo_line = f"\n本章特别注意避开以下AI高风险词：{', '.join(taboo_words[:10])}"

        # 3. 模式内核
        mode_vibe = ""
        try:
            from .db import get_db
            db = get_db()
            if db:
                mode = db.get_mode(mode_name)
                if mode:
                    core = mode.get("core_principle", "")
                    w2 = mode.get("workshop_configs", {}).get("w2_special", {})
                    hook_types = w2.get("hook_types", [])
                    if core:
                        mode_vibe = f"模式内核：{core}"
                    if hook_types:
                        mode_vibe += f" 推荐钩子类型：{', '.join(hook_types)}。"
        except Exception:
            pass

        # 4. QC反馈（W4阶段专用）
        qc_feedback = ctx.get("qc_feedback", "")

        # 组装任务文本
        task_text = f"请为小说《{title}》写第{chapter_num}章正文。{opening_boost}\n\n本章任务：{chapter_task}{taboo_line}\n\n{mode_vibe}"
        parts.append(task_text)

        if qc_feedback:
            parts.append(qc_feedback)

        return "\n\n".join(p for p in parts if p)

    def _get_taboo_words(self, platform_name: str) -> List[str]:
        """从数据库获取平台AI高风险词。"""
        try:
            from .db import get_db
            db = get_db()
            if db:
                plat = db.get_platform(platform_name)
                if plat:
                    return plat.get("ai_trace_high_risk", [])
        except Exception:
            pass
        return []

    # ================================================================
    # L15: 数据库上下文
    # T02: 将由DbPipeline提供
    # ================================================================

    def _L15_db_context(self, ctx: Any) -> str:
        """构建数据库上下文提示。

        T02阶段将由DbPipeline.read_before_write()的DbContext.to_prompt_text()提供。
        """
        db_context = ctx.get("db_context")
        if db_context:
            try:
                prompt_text = db_context.to_prompt_text()
                if prompt_text:
                    return f"## 数据库上下文\n{prompt_text}"
            except Exception:
                pass
        return ""

    # ================================================================
    # L16: 格式规则
    # 迁移自: _load_de_ai_rules() + _load_iq_firewall() + 视角铁律 + 感官铁律
    # ================================================================

    def _L16_format_rules(self, ctx: Any) -> str:
        """构建格式规则提示。

        合并了:
        - _load_de_ai_rules(): 去AI味写作铁律
        - _load_iq_firewall(): 智商防火墙
        - 视角铁律
        - 感官描写铁律
        """
        parts = []

        # 1. 去AI味写作铁律
        de_ai_rules = _load_de_ai_rules()
        if de_ai_rules:
            parts.append(f"## 去AI味写作铁律\n{de_ai_rules}")

        # 2. 智商防火墙
        iq_firewall = _load_iq_firewall()
        if iq_firewall:
            parts.append(f"## 智商防火墙\n{iq_firewall}")

        # 3. 视角铁律
        parts.append("""### 视角铁律
- 视角锁死主角（70%篇幅）
- 可切对手视角（15%篇幅）
- 可切第三方视角（10%篇幅）
- 上帝视角（5%篇幅，仅用于大高潮定格）
- 切换视角时必须有明确锚点
- 不跳别人心理，不写"他在想什么""")

        # 4. 感官描写铁律
        parts.append("""### 感官描写铁律（每章必须）
- 视觉细节：至少1处（具体物件的颜色/形状/状态）
- 听觉细节：至少1处（对话内容/环境音/动作声）
- 触觉/嗅觉/味觉：至少1处（三选一）
- 细节分散植入，不集中写大段描写""")

        return "\n\n".join(p for p in parts if p)

    # ================================================================
    # L17: 最终包装
    # 迁移自: build_smart_prompt() user_msg 的格式要求部分
    # ================================================================

    def _L17_final_wrap(self, ctx: Any) -> str:
        """构建最终包装提示。

        迁移自 build_smart_prompt() user_msg 中的格式要求。
        """
        chapter_num = ctx.get("chapter_num", 1)

        return (
            "要求：约2000字。直接输出正文，不要前言后记、不要章节标题。\n\n"
            f"第{chapter_num}章正文："
        )


# ================================================================
# 辅助函数（迁移自 pangu_optimized.py）
# ================================================================

def _load_universal_prompt() -> str:
    """加载通用高质量写作规则。"""
    global _UNIVERSAL_PROMPT_CACHE
    if _UNIVERSAL_PROMPT_CACHE is None:
        path = BASE_DIR / "system_prompts" / "universal_writer.txt"
        if path.exists():
            _UNIVERSAL_PROMPT_CACHE = path.read_text(encoding="utf-8")
        else:
            _UNIVERSAL_PROMPT_CACHE = ""
    return _UNIVERSAL_PROMPT_CACHE


def _extract_platform_section(platform_name: str) -> str:
    """从platform_rules.txt提取指定平台的约束。"""
    rules = _load_platform_rules_file()
    if not rules:
        return ""

    platform_map = {
        "fanqie": "番茄小说（fanqie）",
        "qimao": "七猫小说（qimao）",
        "qidian": "起点中文网（qidian）",
    }

    section_name = platform_map.get(platform_name, platform_map.get("qimao"))

    # 找到对应平台段落
    pattern = rf'## ============ {section_name}.*?(?=\n## ============|\Z)'
    match = re.search(pattern, rules, re.DOTALL)
    if match:
        return match.group(0)

    # 回退：用关键词找
    for name in [section_name] + list(platform_map.values()):
        pattern = rf'## ============ {name}.*?(?=\n## ============|\Z)'
        match = re.search(pattern, rules, re.DOTALL)
        if match:
            return match.group(0)

    return ""


def _load_platform_rules_file() -> str:
    """加载三平台约束模块文件。"""
    global _PLATFORM_RULES_CACHE
    if _PLATFORM_RULES_CACHE is None:
        path = BASE_DIR / "system_prompts" / "platform_rules.txt"
        if path.exists():
            _PLATFORM_RULES_CACHE = path.read_text(encoding="utf-8")
        else:
            _PLATFORM_RULES_CACHE = ""
    return _PLATFORM_RULES_CACHE


def _load_sentence_reference_v3() -> str:
    """加载句式结构参考v3。"""
    global _SENTENCE_REF_V3_CACHE
    if _SENTENCE_REF_V3_CACHE is None:
        path = BASE_DIR / "knowledge" / "references" / "writing" / "sentence-structure-reference-v3.md"
        if path.exists():
            _SENTENCE_REF_V3_CACHE = path.read_text(encoding="utf-8")
        else:
            _SENTENCE_REF_V3_CACHE = ""
    return _SENTENCE_REF_V3_CACHE


def _load_style_guidance(mode_name: str, platform_name: str) -> str:
    """从风格指纹数据库加载同类型作品的量化风格指引。"""
    try:
        from knowledge.style_fingerprint import StyleDatabase
    except ImportError:
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR))
            from knowledge.style_fingerprint import StyleDatabase
        except ImportError:
            return ""

    genre = get_genre_for_mode(mode_name)
    try:
        style_db = StyleDatabase()
        guidance = style_db.get_writing_guidance(genre, platform_name)
        return guidance if guidance else ""
    except Exception:
        return ""


def _load_style_vault(mode_name: str, chapter_task: str) -> str:
    """加载风格库：从V1.0抽取的风格映射+港片风格库+叙事基因库。"""
    csv_path = BASE_DIR / "knowledge" / "references" / "webnovel_csv" / "风格映射.csv"
    genre_dir = BASE_DIR / "knowledge" / "references" / "webnovel_genres"

    # 1. 读取风格映射CSV
    style_map = []
    if csv_path.exists():
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    style_map.append(row)
        except Exception:
            return ""

    if not style_map:
        return ""

    # 2. 从chapter_task中匹配关键词
    matched_row = None
    max_matches = 0
    task_lower = chapter_task.lower() if chapter_task else ""

    for row in style_map:
        keywords = row.get("关键词", "")
        if not keywords:
            continue
        kw_list = [kw.strip() for kw in keywords.split("/") if kw.strip()]
        match_count = sum(1 for kw in kw_list if kw in task_lower)
        if match_count > max_matches:
            max_matches = match_count
            matched_row = row

    # 模糊匹配
    if matched_row is None and mode_name:
        mode_lower = mode_name.lower()
        for row in style_map:
            keywords = row.get("关键词", "")
            kw_list = [kw.strip() for kw in keywords.split("/") if kw.strip()]
            if any(kw in mode_lower for kw in kw_list):
                matched_row = row
                break

    if matched_row is None:
        return ""

    # 3. 读取对应风格的详细描述
    main_style = matched_row.get("主风格", "")
    aux_style = matched_row.get("辅风格", "")
    accent_style = matched_row.get("点缀风格", "")
    female_type = matched_row.get("女角色类型", "")
    platform = matched_row.get("平台", "")

    all_details = _load_genre_style_details(genre_dir)

    # 4. 组装返回文本
    result_parts = []
    result_parts.append(
        f"风格匹配结果：主风格【{main_style}】(60%) + 辅风格【{aux_style}】(30%) + "
        f"点缀风格【{accent_style}】(10%)"
    )
    if female_type:
        result_parts.append(f"女角色类型：{female_type}")
    if platform:
        result_parts.append(f"推荐平台：{platform}")

    for style_name in [main_style, aux_style, accent_style]:
        detail = all_details.get(style_name, "")
        if detail:
            result_parts.append(f"\n【风格·{style_name}】\n{detail.strip()}")

    return "\n".join(result_parts)


def _load_genre_style_details(genre_dir: Path) -> Dict[str, str]:
    """从多个风格库MD文件中加载风格详细描述。"""
    all_details: Dict[str, str] = {}

    md_files = [
        genre_dir / "港片风格库.md",
        genre_dir / "国漫叙事基因.md",
        genre_dir / "电视剧叙事基因.md",
        genre_dir / "短剧打脸基因.md",
    ]

    for md_path in md_files:
        if not md_path.exists():
            continue
        try:
            content = md_path.read_text(encoding="utf-8")
            current_style = None
            current_lines: List[str] = []
            for line in content.split("\n"):
                if line.startswith("## "):
                    skip_keywords = ["港片", "国漫", "电视剧", "短剧"]
                    section_name = line[3:].strip()
                    if current_style:
                        all_details[current_style] = "\n".join(current_lines)
                    if any(kw in section_name for kw in skip_keywords):
                        current_style = None
                        current_lines = []
                        continue
                    current_style = section_name
                    current_lines = []
                elif current_style:
                    current_lines.append(line)
            if current_style:
                all_details[current_style] = "\n".join(current_lines)
        except Exception:
            pass

    return all_details


def _load_engine_guidance(mode_name: str, platform_name: str, chapter_num: int) -> str:
    """从创作引擎获取位置感知的写作策略推荐。"""
    genre = get_genre_for_mode(mode_name)
    try:
        from knowledge.creative_engine import CreativeEngine
        engine = CreativeEngine()
        strategy_prompt = engine.get_strategy_prompt(genre, chapter_num, platform_name)
        return strategy_prompt if strategy_prompt else ""
    except Exception:
        return ""


def _load_math_guidance(chapter_task: str, chapter_num: int, platform_name: str) -> str:
    """使用数学引擎对当前章节草稿进行质量评估和梯度优化。"""
    try:
        from knowledge.pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        if len(chapter_task) > 500:
            result = engine.full_analysis(chapter_task, chapter_num)
            guidance = engine.get_guidance_prompt(result, platform_name)
            return guidance
        return f"[数学引擎] 平台{platform_name}第{chapter_num}章目标质量分≥70"
    except Exception:
        return ""


def _load_mode_deep_injection(mode_name: str) -> str:
    """从modes/目录加载模式JSON的深度规则注入。"""
    mode_file = BASE_DIR / "modes" / f"{mode_name}.json"
    if not mode_file.exists():
        return ""

    try:
        mode_config = json.loads(mode_file.read_text(encoding="utf-8"))
    except Exception:
        return ""

    parts = []

    # 1. W2特殊规则
    w2 = mode_config.get("w2_special", {})
    if w2:
        w2_parts = []
        if w2.get("dialogue_priority"):
            w2_parts.append(f"  对话优先级: {w2['dialogue_priority']}")
        if w2.get("action_style"):
            w2_parts.append(f"  动作风格: {w2['action_style']}")
        if w2.get("hook_types"):
            w2_parts.append(f"  钩子类型: {' | '.join(w2['hook_types'][:5])}")
        if w2_parts:
            parts.append("【W2正文规则】\n" + "\n".join(w2_parts))

    # 2. W4特殊规则
    w4 = mode_config.get("w4_special", {})
    if w4:
        w4_parts = []
        if w4.get("emotion_parameter"):
            w4_parts.append(f"  情绪参数: {w4['emotion_parameter']}")
        if w4.get("sensory_priority"):
            w4_parts.append(f"  感官优先级: {' > '.join(w4['sensory_priority'][:3])}")
        if w4.get("shot_types"):
            w4_parts.append(f"  推荐镜头: {' | '.join(w4['shot_types'][:4])}")
        if w4.get("dialogue_style"):
            w4_parts.append(f"  对话风格: {w4['dialogue_style']}")
        if w4.get("taboo"):
            w4_parts.append(f"  ⚠ 禁忌: {w4['taboo']}")
        if w4.get("atmosphere_techniques"):
            w4_parts.append(f"  氛围技法: {' | '.join(w4['atmosphere_techniques'][:4])}")
        if w4_parts:
            parts.append("【W4精修规则】\n" + "\n".join(w4_parts))

    # 3. 章节结构模板
    chapter_structure = mode_config.get("chapter_structure", {})
    if chapter_structure:
        cs_parts = []
        for key, val in chapter_structure.items():
            cs_parts.append(f"  {key}: {val}")
        parts.append("【章节结构模板】\n" + "\n".join(cs_parts))

    # 4. 示例钩子
    example_hooks = mode_config.get("example_chapter_hooks", [])
    if example_hooks:
        hook_sample = example_hooks[0]
        parts.append(f"【示例钩子】{hook_sample[:120]}...")

    # 5. 成功指标
    success = mode_config.get("success_metrics", {})
    if success:
        s_parts = []
        for k, v in success.items():
            s_parts.append(f"  {k}: {str(v)[:80]}")
        parts.append("【成功指标】\n" + "\n".join(s_parts[:4]))

    return "\n\n".join(parts) if parts else ""


def _load_genre_template_hints(mode_name: str, chapter_task: str) -> str:
    """从题材CSV中加载匹配的题材模板规则。"""
    genre_name = get_genre_for_mode(mode_name)
    csv_path = BASE_DIR / "knowledge" / "references" / "csv" / "题材与调性推理.csv"
    if not csv_path.exists():
        return ""

    try:
        matched_rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = row.get("canonical_genre", "")
                keywords = row.get("关键词", "")
                if genre_name in canonical or any(
                    kw in chapter_task for kw in keywords.split("|") if kw
                ):
                    matched_rows.append(row)

        if not matched_rows:
            return ""

        parts = []
        for row in matched_rows[:3]:
            name = row.get("题材/流派", row.get("编号", ""))
            core_summary = row.get("核心摘要", "")
            poison = row.get("毒点", "")
            rhythm = row.get("节奏策略", "")
            if core_summary:
                parts.append(f"【{name}】{core_summary}")
            if poison:
                parts.append(f"  ⚠ 毒点: {poison}")
            if rhythm:
                parts.append(f"  🎯 节奏: {rhythm}")

        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def _extract_emotion_anchors(state: Dict[str, Any], chapter_num: int) -> str:
    """从state中提取当前章节应匹配的情绪锚点。"""
    parts = []

    # 从角色状态推断情绪
    chars = state.get("characters", {})
    if isinstance(chars, list):
        chars = {}
    protagonist = chars.get("protagonist", {})
    if protagonist.get("current_state"):
        parts.append(f"主角当前状态: {protagonist['current_state']}")

    # 从伏笔推断紧迫情绪
    foreshadow = state.get("foreshadowing", {})
    if isinstance(foreshadow, list):
        active_threads = foreshadow
    else:
        active_threads = foreshadow.get("active_threads", [])
    open_threads = [t for t in active_threads if t.get("status") == "open"]
    if open_threads:
        urgent = [t for t in open_threads if chapter_num - t.get("planted_ch", 0) >= 3]
        if urgent:
            parts.append(f"⚠ 有{len(urgent)}条伏笔已超过3章未兑现，本章需要推进或收束其中至少1条")

    # 从设定日志推断氛围
    setting_log = state.get("setting_log", {})
    if isinstance(setting_log, list):
        locked = setting_log
    else:
        locked = setting_log.get("locked_rules", [])
    if locked and len(locked) > 5:
        parts.append("设定已较为丰富，注意用已有设定制造冲突而非引入新设定")

    return "\n".join(parts) if parts else ""


def _inject_lorebook(
    state: Dict[str, Any], chapter_task: str, context_content: str
) -> str:
    """Lorebook强制注入：事前约束世界观词条。"""
    lorebook = state.get("lorebook", {})
    if not lorebook or not isinstance(lorebook, dict):
        return ""

    match_text = f"{chapter_task} {context_content}"

    matched_entries = []
    for entry_name, entry_data in lorebook.items():
        if not isinstance(entry_data, dict):
            continue
        triggers = entry_data.get("triggers", [entry_name])
        description = entry_data.get("description", "")
        priority = entry_data.get("priority", 5)

        if not description:
            continue

        for trigger in triggers:
            if trigger and trigger in match_text:
                matched_entries.append((priority, entry_name, description))
                break

    if not matched_entries:
        return ""

    matched_entries.sort(key=lambda x: x[0])

    lines = []
    for priority, name, desc in matched_entries[:8]:
        lines.append(f"【{name}】{desc}")

    result = "以下设定必须在写作中严格遵守，不得矛盾：\n" + "\n".join(lines)
    result += "\n\n⚠ 以上为强制约束，相关角色的言行举止、相关设定的细节描写必须与此一致。"
    return result


# ================================================================
# W4 模式差异化规则 (P0-2: 盘古核心竞争力)
# ================================================================

_W4_MODE_RULES = {
    "healing_life": """
【治愈系模式·W4精修规则】
五感优先级: 触觉 > 听觉 > 视觉 > 味觉 > 嗅觉
  - 触觉: 温度/质地/湿度——指尖碰到杯壁的温/毛衣袖口的软
  - 听觉: 沉默/呼吸/远处的声音——安静中的声音比大声更有力
镜头语言: 特写(手/物件/表情) + 空镜(人物走后的空间) + 固定长镜头(一个动作的完整过程)
对话风格: 话不说满，言外之意>字面意思。每句≤20字。用动作替代"他说/她说"
禁忌: 禁用"突然/猛然/竟然/却"。禁用内心OS("她想：...")。禁用直白情绪词
结尾: 落在画面/天气/物件上，不让读者"想点下一页"而是"想在这一刻停留"
金句: 每章1-2句可截图传播的话，从叙事中自然长出，不提前设计
""",
    "mystery": """
【悬疑模式·W4精修规则】
五感优先级: 视觉 > 听觉 > 触觉 > 嗅觉 > 味觉
  - 视觉: 光线/影子/细节——门缝下的光/墙上的影子/镜子里的人
  - 听觉: 突然的声响/持续的沉默/远处的声音——冰箱压缩机的嗡声/楼道里的脚步声
镜头语言: 固定机位(站定不动的观察) + 跳切(时间省略制造不安) + 主观镜头(主角看见的)
对话风格: 对话即调查——每句对话推进信息或制造怀疑。对话占比≥25%。'他说苏西是谁'——信息缺口即钩子。用\"X说：...\"的格式，对话之间用动作填充
禁忌: 不解释恐怖(让读者自己拼)，不给确定答案，不在章末总结
氛围: 日常中的不对劲——阳光下的灰尘比黑暗中的怪物更恐怖
结尾: 落在不确定上——门缝下的光/屏幕亮了一下又灭了/有人在黑暗里查看了一条消息
""",
    "rule_mystery": """
【规则怪谈模式·W4精修规则】
五感优先级: 听觉 > 视觉 > 触觉 > 嗅觉 > 味觉
  - 听觉: 规则的宣告声/违反规则后的声音/沉默中的呼吸
  - 视觉: 规则生效的视觉标记——文字自燃/空间扭曲/镜中异常
镜头语言: 固定机位(规则区的压迫感) + 跳切(规则触发的瞬间) + 空镜(规则区外的正常世界)
对话风格: 规则陈述式——角色在试探规则的边界，对话中包含逻辑推演
禁忌: 绝对禁用"突然/猛然/竟然"。规则区的描述必须精确(触发条件/违反惩罚/漏洞)
氛围: 规则的不可违抗性——不是鬼故事，是逻辑陷阱。压迫感来自"你知道违反会死但仍然可能违反"
结尾: 落在对规则的重新理解上——破解了一个规则，但发现了更大的规则
""",
    "urban_power": """
【都市异能模式·W4精修规则】
五感优先级: 视觉 > 触觉 > 听觉 > 嗅觉 > 味觉
  - 视觉: 能力的视觉呈现——光芒/特效/物理变化
  - 触觉: 能力使用的体感——发热/刺痛/力竭
镜头语言: 动作片式快速剪辑——能力展示+结果，不拖沓
对话风格: 口语化，对话占比≥40%。能力讨论穿插在日常对话中
禁忌: 不解释能力原理(留白)。不滥写内心OS。能力有明确限制和代价
氛围: 现实锚点——具体数字/金额/温度。超能力在普通日常中展开
""",
    "general": """
【通用模式·W4精修规则】
五感优先级: 视觉 > 触觉 > 听觉
镜头语言: 全景→中景→特写的递进。场景切换有锚点
对话风格: 对话占比30-50%，每句对话有用途(推剧情/亮人设)
禁忌: 禁用AI味词汇(200+禁词库)。不禁内心OS但每章≤2处
氛围: 平衡——300字小波动/800字中波动
""",

    "xianxia": """
【玄幻仙侠模式·W4精修规则】 (吸收: 玄幻小说指令)
五感优先级: 视觉 > 触觉 > 听觉
升级体系: 每级有明确名称/突破条件/代价/战力提升幅度。不写模糊的"实力大涨"
金手指: 必须有来源+限制+代价。每章最多用1次，不能解决所有问题
世界观: 力量体系自洽——来源/途径/境界命名有规则可循。不突然引入新设定
禁忌: 战力崩坏(前后矛盾)。越级挑战需铺垫。同阶对战先分析再动手
节奏: 每一卷至少1次大境界突破+1次生死战。每章至少1个爽点(升级/碾压/夺宝)
""",

    "scifi": """
【科幻模式·W4精修规则】 (吸收: 科幻小说指令)
五感优先级: 视觉 > 触觉 > 听觉
科技设定: 必须有理论基础或合理的技术推演。不凭空出现万能科技
金手指: 技术来源可追溯。有工艺门槛和资源限制
世界观: 科技与社会共演——新技术改变了什么？带来了什么新问题？
禁忌: 技术矛盾(前面做不到后面突然可以)。无视物理规律无铺垫
节奏: 科技发现→验证→应用→副作用→修正，每阶段1-2章
""",

    "tomato": """
【番茄平台·过稿规则】 (吸收: 番茄过稿指令)
开篇铁律: 前300字必须出冲突/悬念/异常。黄金三章定生死。
爽点密度: 每800-1200字至少1个爽点(打脸/捡漏/逆袭/碾压/突破/反转)
段落: 手机端≤3行。1-2句一段为主。拒绝长段落和大段描写。
对话: 对话占比≥40%。用对话推进剧情，减少旁白叙述。
金手指: 可量化(数字面板/等级提升)。有CD时间。不能用金手指解决全部问题。
签约难度: 都市>玄幻>悬疑>小众。都市是最容易签约也是最难写出新意的赛道。
""",

    "zhihu_short": """
【知乎盐选模式·W4精修规则】 (吸收: 某乎短篇指令)
结局铁律: 结局必须违背真实生活——需要生活中不常见的反转/意外/重击。
字数: 1-3万字最佳。每段2000-3000字。
情感驱动: 情感>情节。让读者"鼻子一酸"比"想知后续"更重要。
视角: 第一人称或第三人称限知。不跳POV。
对话: 插入对话揭示人物个性与冲突。对话占比15-25%。
细节: 用具体细节(物件/颜色/温度/气味)让故事可感。不空写情绪。
结尾: 落在画面/天气/物件上。不让读者"想知道接下来发生了什么"——让读者"想再读一遍"。
""",
}


def _get_w4_mode_rules(mode_name: str) -> str:
    """获取W4模式差异化规则"""
    # 精确匹配
    if mode_name in _W4_MODE_RULES:
        return _W4_MODE_RULES[mode_name]
    # 模糊匹配
    for key, rules in _W4_MODE_RULES.items():
        if key in mode_name or mode_name in key:
            return rules
    return _W4_MODE_RULES["general"]


# ================================================================
# 优先级参考书检索 (L06 新增)
# ================================================================

def _load_priority_references(ctx: Any) -> str:
    """从数据库按 priority_score 检索高优先级参考书。

    匹配规则:
      1. 福尔摩斯级别经典 (priority≥80) → 必选前3
      2. 同题材高优先级 (priority≥60, 题材匹配) → 选前5
      3. 同平台高优先级 → 补前3
    返回格式化的参考书摘要，供Prompt注入。
    """
    chapter_task = ctx.get("chapter_task", "")
    mode_name = ctx.get("mode_name", "general")
    platform_name = ctx.get("platform_name", "qimao")

    try:
        import sqlite3
        from .prompts import get_genre_for_mode
        genre = get_genre_for_mode(mode_name)

        db_path = BASE_DIR / "knowledge" / "novel_reference.db"
        if not db_path.exists():
            return ""

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        results = []

        # 1. 顶级经典 (P0, 不限题材)
        classics = conn.execute('''
            SELECT title, author, genre, rating, priority_score, notes
            FROM books WHERE priority_score >= 80 AND is_reference = 1
            ORDER BY priority_score DESC LIMIT 3
        ''').fetchall()
        for b in classics:
            results.append(f"- [P0经典·{b['priority_score']:.0f}分]《{b['title']}》{b['author'] or ''} — {b['genre'] or ''}")

        # 2. 同题材高优先级
        genre_books = conn.execute('''
            SELECT title, author, genre, rating, priority_score
            FROM books WHERE priority_score >= 55 AND is_reference = 1
            AND (genre LIKE ? OR mode LIKE ?)
            ORDER BY priority_score DESC LIMIT 5
        ''', (f'%{genre}%', f'%{mode_name}%')).fetchall()
        for b in genre_books:
            results.append(f"- [同题材·{b['priority_score']:.0f}分]《{b['title']}》{b['genre'] or ''}")

        # 3. 同平台高优先级
        platform_books = conn.execute('''
            SELECT title, author, genre, rating, priority_score
            FROM books WHERE priority_score >= 50
            AND platform LIKE ?
            ORDER BY priority_score DESC LIMIT 3
        ''', (f'%{platform_name}%',)).fetchall()
        for b in platform_books:
            results.append(f"- [同平台·{b['priority_score']:.0f}分]《{b['title']}》{b['genre'] or ''}")

        # 4. 经典技法注入 (从writing_techniques表)
        for b in classics[:1]:  # 只取最高优先级的那本
            title_prefix = b['title'][:10]
            techniques = conn.execute('''
                SELECT technique_type, name, description FROM writing_techniques
                WHERE book_id = (SELECT id FROM books WHERE title LIKE ?
                ORDER BY priority_score DESC LIMIT 1)
            ''', (f'%{title_prefix}%',)).fetchall()
            if techniques:
                results.append(f"\n【{b['title']}技法分析】")
                for t in techniques[:5]:
                    results.append(f"  - {t['name']}: {t['description']}")

        conn.close()

        if results:
            return "以下为系统推荐的高价值参考书（优先级评分越高，参考价值越大）：\n" + "\n".join(results[:12])

    except Exception:
        pass
    return ""


def _load_de_ai_rules() -> str:
    """加载De-AI化写作铁律。"""
    global _DE_AI_RULES_CACHE
    if _DE_AI_RULES_CACHE is not None:
        return _DE_AI_RULES_CACHE

    _DE_AI_RULES_CACHE = """以下规则必须在生成正文时严格遵守，违反即为AI味暴露：

### 句式铁律
1. 禁止连续3句以上使用相同的句式结构（主谓宾、条件句、因果句）
2. 禁止"不是A而是B"的二分对照壳——这是AI最典型的讲义腔，正文中最多出现1处
3. 条件句（一旦…就/只有…才/无论…都）全文不超过2处
4. 禁止"通过…来…"的因果封装句式
5. 句子长度必须长短交替：禁止连续5句以上都是20-30字的中等句

### 段落铁律
6. 禁止连续3段结构相同（观点→展开→总结的"三明治"段）
7. 段落厚度必须交替：允许短段（1-2句）、中段（3-5句）、厚段（6句+）混合
8. 段尾不要补抽象结论——能停在动作、对话、场景、具体后果上，就不要再概括

### 词汇铁律
9. 路标词（更关键/换句话说/事实上/与此同时/总之）全文合计不超过2次
10. 高频分析词（拆解/梳理/剖析/聚焦/洞察/赋能/驱动/构建）严禁堆叠，每次最多1个
11. 禁止"作为/本质上/归根结底/简单来说"的讲义动作词
12. 禁止"遮羞布/面具/外衣/揭开真面目"的戏剧化揭露修辞

### 叙事铁律
13. 对话必须是活的——禁止3段以上连续对话都用"X道"的同一格式
14. 情绪铺陈禁止线性递进（紧张→更紧张→最紧张），必须打断和迂回
15. 转折不可预测——禁止"就在这时"/"然而"/"殊不知"的AI式标准转折
16. 禁止章末用"一切才刚刚开始"/"更大的风暴即将来临"等模板悬念结尾

### V1.0扩展禁用词铁律（200+禁用词强制过滤）
17. 以下词汇在任何情况下不得出现在正文中：顿时、连忙、显然、似乎、或许、可能、一定、十分、几乎、嘴角勾起一抹、眼中闪过一丝、行云流水、心下了然、仿佛、如同、一抹、一股、一丝、他知道、她知道、觉得、意识到、感觉到、紧锁、立刻、大致、确实、注定、缓缓地、竟然、居然、不禁、暗自、微微、不由得、赫然、陡然、蓦然、猛然、猝然、骤然、已然、恍然、默然、悚然、渐渐、更是、沉重、看不出、淡淡、郑重、此刻、恐怕、清淡、不知道、心中一凛、话锋一转、眼神深邃、显著、至关重要、微微挑眉、波涛汹涌、绝对、不可估量、无法想象、无法用言语形容、脸上带着笑意、平静地、显得有些兴奋、心中了然、激动地、眼神热切、目光里毫不遮掩、淡淡地、不卑不亢、显得异常清晰、暂时、不断、瞬间、这一刻、再次、一时之间、这一次、看似、沉吟、隐隐有了猜测、淡淡地应了一句、目光扫过、心中一片平静、显得更加、一丝、坚定、的眼神、深吸一口气、缓缓地说、锐利的眼睛、他的嘴角微微上扬、他的表情变暗、他的心一跳、他的脸变了、不容置疑、不易察觉、的目光、心中、想、认为、略微、有点、带着、猛地、口吻、纯粹、冰冷、电弧、闪烁、裹挟、清冷、沸腾、扭曲、撕裂、漆黑、窒息、剧痛、心中一动、不动声色、小心翼翼、沉吟片刻、心里隐隐有了猜测、果然、脸上堆满了笑"""
    return _DE_AI_RULES_CACHE


def _load_iq_firewall() -> str:
    """加载智商防火墙规则。"""
    return """### 智商防火墙
**智商分标准**：
- 10分：绝世天才，算无遗策，每一步都有退路
- 9分：高智商，能设计多层试探，极少犯错
- 8分：聪明人，能识破常见套路
- 7分：普通人偏上，遇事会慌但能反应过来
- 6分：普通人，容易被带节奏
- 5分：偏低，容易上当
- 4分及以下：愚钝，经常被利用

**防火墙规则**：如果角色智商分 < 行为风险分，则该行为被禁止。

**绝对禁止行为**（任何智商≥5的角色）：
- 直接暴露核心秘密
- 在公共场合说现代词汇（穿越/重生设定中）
- 相信陌生人的秘密
- 不设防地交底"""
