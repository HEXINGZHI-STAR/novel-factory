#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 全部Stage定义（W0Anchor ~ W5Export）

Stage是Pipeline的原子执行单元。每个Stage：
- 拥有唯一的stage_id（"W0"-"W5"）
- 实现run(context) -> StageOutput方法
- 可选实现validate_input/validate_output进行校验
- 通过PipelineContext与前后Stage传递数据

Stage与原workflow_engine.py Stage类的关系：
- 保留核心设计思想（Stage模式、知识分层、质检门）
- 接口从 StageInput/StageOutput(dict) 简化为 PipelineContext/StageOutput
- AI调用统一走 pangu_core.ai_client.call_ai()
- Prompt构建统一走 pangu_core.prompt_builder.PromptBuilder
"""

from __future__ import annotations

import re
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from .pipeline import StageOutput
from .prompt_builder import PromptBuilder
from .prompts import get_genre_for_mode, get_params_for_mode

if TYPE_CHECKING:
    from .pipeline import PipelineContext


# ============ Stage基类 ============

class BaseStage(ABC):
    """Stage基类，定义Stage的公共接口和行为。

    子类必须实现:
    - run(context): 执行Stage核心逻辑

    子类可选实现:
    - validate_input(context): 输入校验
    - validate_output(output): 输出校验

    Attributes:
        stage_id: Stage唯一标识，如"W0"/"W2"
        name: Stage中文名称
        knowledge_policy: 该Stage需要哪些知识注入
    """
    stage_id: str = ""
    name: str = "未命名Stage"
    knowledge_policy: Dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def run(self, context: PipelineContext) -> StageOutput:
        """执行Stage核心逻辑。

        Args:
            context: Pipeline运行上下文，包含state、配置、前序Stage输出

        Returns:
            StageOutput: 执行结果，包含success/data/warnings/errors
        """
        ...

    def validate_input(self, context: PipelineContext) -> bool:
        """校验输入是否满足Stage执行条件。

        默认实现检查必要字段是否存在。子类可覆盖以添加更多校验。
        """
        required_keys = ["state", "chapter_num", "chapter_task"]
        return all(context.get(k) is not None for k in required_keys)

    def validate_output(self, output: StageOutput) -> bool:
        """校验Stage输出是否满足基本质量要求。

        默认实现只检查success标志。子类可覆盖以添加更多校验。
        """
        return output.success


# ============ W0: 锚定上下文 ============

class W0AnchorStage(BaseStage):
    """W0: 主旨锚定 — 加载state.json，锚定上下文，提取钩子和冲突。

    核心职责:
    - 从state.json加载项目状态
    - 提取角色状态、伏笔线索、设定规则
    - 生成章节锚定信息（钩子+冲突+预期回报）
    - 将锚定数据写入PipelineContext供后续Stage使用
    """

    stage_id = "W0"
    name = "主旨锚定"
    knowledge_policy = {
        "layers": ["L01", "L02", "L07"],
        "inject_mode": "light",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W0锚定：解析state，提取章节锚定信息。"""
        state = context.get("state", {})
        chapter_num = context.get("chapter_num", 1)
        chapter_task = context.get("chapter_task", "")

        from .data_contracts import AnchorData
        anchor = AnchorData.from_state(state, chapter_num, chapter_task)
        anchor_data = anchor.to_dict()
        context.set("anchor_data", anchor_data)

        return StageOutput(
            stage_id=self.stage_id,
            success=True,
            data=anchor_data,
            warnings=[],
        )

    def _build_anchor_summary(
        self,
        anchor_data: Dict[str, Any],
        chapter_num: int,
        chapter_task: str,
    ) -> str:
        """构建锚定摘要文本。"""
        parts = []
        parts.append(f"第{chapter_num}章 | 任务: {chapter_task}")

        protagonist = anchor_data.get("protagonist", {})
        if protagonist.get("name"):
            parts.append(f"主角: {protagonist['name']}")
            if protagonist.get("current_state"):
                parts.append(f"  状态: {protagonist['current_state']}")

        active_threads = anchor_data.get("active_threads", [])
        open_threads = [t for t in active_threads if t.get("status") == "open"]
        if open_threads:
            parts.append(f"活跃伏笔: {len(open_threads)}条")

        key_chars = anchor_data.get("key_characters", [])
        if key_chars:
            names = [c.get("name", "?") for c in key_chars[:5]]
            parts.append(f"关键角色: {', '.join(names)}")

        return "\n".join(parts)

    def validate_input(self, context: PipelineContext) -> bool:
        """W0需要state和chapter_num"""
        return context.get("state") is not None and context.get("chapter_num") is not None


# ============ W1: 设置检查 ============

class W1SetupStage(BaseStage):
    """W1: 设置检查 — WriteGates(prewrite) + 构建章节热库。

    核心职责:
    - 执行prewrite关卡（WriteGates）
    - 构建本章热库（场景+人物状态+关键设定）
    - 解析章节任务，提取写作约束
    """

    stage_id = "W1"
    name = "设置检查"
    knowledge_policy = {
        "layers": ["L01", "L02", "L03", "L07", "L08", "L09"],
        "inject_mode": "medium",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W1：prewrite关卡 + 章节热库构建。"""
        state = context.get("state", {})
        chapter_num = context.get("chapter_num", 1)
        chapter_task = context.get("chapter_task", "")
        project_dir = context.get("project_dir", "")

        warnings = []
        setup_data = {}

        # 1. 执行prewrite关卡
        gate_passed = True
        # T02: prewrite关卡
        try:
            from .write_gates import run_write_gate
            gate_report = run_write_gate(project_dir, chapter=chapter_num, stage="prewrite")
            if gate_report and not gate_report.get("ok", True):
                blocker_errors = [e for e in gate_report.get("errors", [])
                                 if e.get("severity") == "blocker"]
                if blocker_errors:
                    gate_passed = False
                    warnings.append(f"prewrite关卡阻断: {blocker_errors[0].get('message', '')}")
            context.set("gate_report_prewrite", gate_report)
        except ImportError:
            warnings.append("write_gates不可用，跳过prewrite关卡")
        setup_data["gate_passed"] = gate_passed

        # 2. 构建章节热库
        anchor_data = context.get("anchor_data", {})
        hotlib = self._build_hotlib(state, chapter_num, chapter_task, anchor_data)
        setup_data["hotlib"] = hotlib

        # 3. 解析章节任务
        task_analysis = self._analyze_chapter_task(chapter_task, chapter_num, state)
        setup_data["task_analysis"] = task_analysis

        # 4. 将热库写入context
        context.set("hotlib", hotlib)
        context.set("task_analysis", task_analysis)

        return StageOutput(
            stage_id=self.stage_id,
            success=gate_passed,
            data=setup_data,
            warnings=warnings,
        )

    def _build_hotlib(
        self,
        state: Dict[str, Any],
        chapter_num: int,
        chapter_task: str,
        anchor_data: Dict[str, Any],
    ) -> str:
        """构建本章热库（约500字的紧凑信息集）。使用 AnchorData 的扁平结构。"""
        parts = []

        # 角色状态 (AnchorData 已是扁平字符串，非嵌套dict)
        name = anchor_data.get("protagonist_name", "")
        state_str = anchor_data.get("protagonist_state", "")
        if name:
            parts.append(f"主角: {name}，{state_str}")

        # 关键角色 (AnchorData 已是 List[str])
        key_chars = anchor_data.get("key_characters", [])
        for char_name in key_chars[:3]:
            parts.append(f"  角色: {char_name}")

        # 伏笔线索 (AnchorData 保留原始dict列表)
        active_threads = anchor_data.get("active_threads", [])
        if isinstance(active_threads, list):
            open_threads = [t for t in active_threads if isinstance(t, dict) and t.get("status") == "open"]
            for t in open_threads[:5]:
                parts.append(f"伏笔(Ch{t.get('planted_ch','?')}): {t.get('description','?')[:40]}")

        # 设定 (AnchorData 已是 List[str])
        locked_rules = anchor_data.get("locked_rules", [])
        for rule in locked_rules[-5:]:
            parts.append(f"设定: {rule}")

        parts.append(f"本章任务: {chapter_task}")
        return "\n".join(parts)

    def _analyze_chapter_task(
        self,
        chapter_task: str,
        chapter_num: int,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析章节任务，提取写作约束。"""
        analysis = {
            "is_opening": chapter_num <= 3,
            "has_combat": any(
                kw in chapter_task
                for kw in ["战斗", "打", "杀", "对决", "交锋", "反击", "逆袭", "爆发", "燃"]
            ),
            "has_dialogue": any(
                kw in chapter_task
                for kw in ["对话", "谈判", "说服", "审问", "争论", "告白"]
            ),
            "has_mystery": any(
                kw in chapter_task
                for kw in ["秘密", "真相", "谜底", "发现", "揭露", "隐藏"]
            ),
        }
        return analysis

    def validate_input(self, context: PipelineContext) -> bool:
        """W1需要W0的锚定数据"""
        return (
            context.get("state") is not None
            and context.get("anchor_data") is not None
        )


# ============ W2: 初稿生成 ============

class W2DraftStage(BaseStage):
    """W2: 初稿生成 — PromptBuilder + AI调用。

    核心职责:
    - 使用PromptBuilder构建完整的17层prompt
    - 调用call_ai()生成初稿
    - 返回StageOutput(draft=content)
    """

    stage_id = "W2"
    name = "初稿生成"
    knowledge_policy = {
        "layers": ["L01", "L02", "L03", "L04", "L05", "L06", "L07",
                    "L08", "L09", "L10", "L11", "L12", "L13", "L14",
                    "L15", "L16", "L17"],
        "inject_mode": "full",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W2：构建prompt → 调用AI → 获取初稿。"""
        warnings = []

        # 1. 使用PromptBuilder构建完整prompt
        prompt_builder = PromptBuilder()
        system_msg, user_msg = prompt_builder.build_system_and_user(context, stage_id="W2")

        # 2. 调用AI生成初稿
        draft_content = ""
        try:
            from .ai_client import call_ai
            draft_content = call_ai(user_msg, system_msg=system_msg, stage_id="W2") or ""
        except ImportError:
            warnings.append("ai_client不可用，返回空初稿")
        except Exception as e:
            warnings.append(f"AI调用异常: {e}")

        # 3. 检查初稿质量
        if not draft_content or len(draft_content.strip()) < 100:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                data={"draft": draft_content},
                errors=[f"初稿内容过短或为空({len(draft_content)}字)"],
            )

        # 4. 返回StageOutput
        return StageOutput(
            stage_id=self.stage_id,
            success=True,
            data={"draft": draft_content},
            warnings=warnings,
        )

    def validate_input(self, context: PipelineContext) -> bool:
        """W2需要state、chapter_task和基本配置"""
        return (
            context.get("state") is not None
            and context.get("chapter_task") is not None
            and context.get("chapter_num") is not None
        )

    def validate_output(self, output: StageOutput) -> bool:
        """W2输出需要包含draft且长度足够"""
        draft = output.data.get("draft", "")
        return len(draft.strip()) >= 100


# ============ W3: 质量检查 ============

class W3QCStage(BaseStage):
    """W3: 质量检查 — 违约检测 + 句式检查 + 逻辑质检。

    核心职责:
    - 对W2初稿进行质量检查
    - 检测AI味词汇、句式问题、逻辑不一致
    - 生成QC报告供W4参考
    """

    stage_id = "W3"
    name = "质量检查"
    knowledge_policy = {
        "layers": ["L05", "L16"],
        "inject_mode": "check_only",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W3：质量检查 + 生成QC报告。"""
        warnings = []

        # 1. 获取W2初稿
        w2_output = context.get_stage_output("W2")
        if not w2_output or not w2_output.success:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                errors=["W2初稿不可用，无法执行质检"],
            )

        draft = w2_output.data.get("draft", "")
        if not draft:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                errors=["W2初稿内容为空"],
            )

        # 2. 执行质量检查
        qc_report = self._run_quality_check(draft, context)

        # 3. 将QC报告写入context供W4使用
        context.set("qc_report", qc_report)

        return StageOutput(
            stage_id=self.stage_id,
            success=True,
            data={"qc_report": qc_report, "draft_for_polish": draft},
            warnings=warnings,
        )

    def _run_quality_check(
        self, draft: str, context: PipelineContext
    ) -> Dict[str, Any]:
        """对初稿执行质量检查。"""
        issues = []
        score = 1.0

        # AI味词汇检查
        ai_patterns = {
            "他感到": 0.05, "他心中": 0.05, "他暗道": 0.05, "他心里": 0.05,
            "缓缓地": 0.03, "淡淡地": 0.03, "微微地": 0.03,
            "忽然": 0.03, "突然": 0.03, "猛然": 0.03,
            "不是……而是": 0.10, "不是...而是": 0.10,
        }
        for pattern, penalty in ai_patterns.items():
            count = draft.count(pattern)
            if count > 0:
                per_1000 = count / max(len(draft) / 1000, 1)
                if per_1000 > 1.0:
                    issues.append(f"'{pattern}'出现{count}次({per_1000:.1f}/千字，超阈值)")
                    score -= penalty * min(per_1000, 3)

        # 句长检查
        sentences = [s.strip() for s in re.split(r'[。！？\n]', draft) if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            if avg_len < 15:
                issues.append(f"平均句长仅{avg_len:.0f}字(预期≥25字)")
                score -= 0.15

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
                issues.append(f"出现{max_consecutive_short}句连续短句(AI写法)")
                score -= 0.10

        # 对话率检查
        total_chars = len(draft.replace('\n', '').replace(' ', ''))
        dialogue_chars = sum(
            len(m.group())
            for m in re.finditer(r'[""\u201c][^""\u201d]+?[""\u201d]', draft)
        )
        dialogue_ratio = dialogue_chars / max(total_chars, 1)

        score = max(0.0, score)
        passed = score >= 0.7

        return {
            "passed": passed,
            "score": round(score, 2),
            "issues": issues,
            "dialogue_ratio": round(dialogue_ratio, 2),
            "avg_sentence_length": round(avg_len, 1) if sentences else 0,
            "retry_hint": "请针对以上问题逐条修正后重写。" if not passed else "",
        }

    def validate_input(self, context: PipelineContext) -> bool:
        """W3需要W2的输出"""
        w2_output = context.get_stage_output("W2")
        return w2_output is not None and w2_output.success


# ============ W4: 润色定稿 ============

class W4PolishStage(BaseStage):
    """W4: 润色定稿 — PromptBuilder + AI调用 + WriteGates(precommit)。

    核心职责:
    - 获取W2初稿（和W3 QC反馈，如果有）
    - 使用PromptBuilder构建润色prompt（含QC反馈）
    - 调用call_ai()润色
    - 执行precommit关卡（WriteGates）
    - 返回StageOutput(final=content)
    """

    stage_id = "W4"
    name = "润色定稿"
    knowledge_policy = {
        "layers": ["L01", "L02", "L03", "L04", "L05", "L06", "L07",
                    "L08", "L09", "L10", "L11", "L12", "L13", "L14",
                    "L15", "L16", "L17"],
        "inject_mode": "full",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W4：获取初稿+QC反馈 → 构建润色prompt → AI润色 → precommit关卡。"""
        warnings = []

        # 1. 获取初稿内容
        draft_content = self._get_draft_content(context)
        if not draft_content:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                errors=["无可用的初稿内容"],
            )

        # 2. 获取QC反馈（如果有W3）
        qc_feedback = ""
        qc_report = context.get("qc_report")
        if qc_report and not qc_report.get("passed", True):
            issues = qc_report.get("issues", [])
            if issues:
                qc_feedback = "【上一版的问题，请修正】\n" + "\n".join(
                    f"  - {i}" for i in issues[:5]
                )

        # 3. 将QC反馈写入context供PromptBuilder使用
        context.set("qc_feedback", qc_feedback)
        context.set("polish_source", draft_content)

        # 4. 使用PromptBuilder构建润色prompt
        prompt_builder = PromptBuilder()
        system_msg, user_msg = prompt_builder.build_system_and_user(context, stage_id="W4")

        # 5. 调用AI润色
        polished_content = ""
        try:
            from .ai_client import call_ai
            polished_content = call_ai(user_msg, system_msg=system_msg, stage_id="W4") or ""
        except ImportError:
            warnings.append("ai_client不可用，使用初稿作为最终内容")
            polished_content = draft_content
        except Exception as e:
            warnings.append(f"AI调用异常: {e}")
            polished_content = draft_content

        # 6. 如果润色失败，降级使用初稿
        if not polished_content or len(polished_content.strip()) < 100:
            warnings.append("润色内容过短，使用初稿作为最终内容")
            polished_content = draft_content

        # 7. 执行precommit关卡
        precommit_passed = True
        _project_dir = context.get("project_dir", "")
        _chapter_num = context.get("chapter_num", 1)
        # T02: precommit关卡
        try:
            from .write_gates import run_write_gate
            gate_report = run_write_gate(_project_dir, chapter=_chapter_num, stage="precommit", content=polished_content)
            if gate_report and not gate_report.get("ok", True):
                blocker_errors = [e for e in gate_report.get("errors", [])
                                 if e.get("severity") == "blocker"]
                if blocker_errors:
                    precommit_passed = False
                    warnings.append(f"precommit关卡阻断: {blocker_errors[0].get('message', '')}")
            context.set("gate_report_precommit", gate_report)
        except ImportError:
            warnings.append("write_gates不可用，跳过precommit关卡")

        return StageOutput(
            stage_id=self.stage_id,
            success=precommit_passed,
            data={"final": polished_content},
            warnings=warnings,
        )

    def _get_draft_content(self, context: PipelineContext) -> str:
        """获取初稿内容：优先W3的draft_for_polish，其次W2的draft。"""
        w3_output = context.get_stage_output("W3")
        if w3_output and w3_output.success:
            draft = w3_output.data.get("draft_for_polish", "")
            if draft:
                return draft

        w2_output = context.get_stage_output("W2")
        if w2_output and w2_output.success:
            return w2_output.data.get("draft", "")

        return ""

    def validate_input(self, context: PipelineContext) -> bool:
        """W4需要W2的输出"""
        w2_output = context.get_stage_output("W2")
        return w2_output is not None and w2_output.success

    def validate_output(self, output: StageOutput) -> bool:
        """W4输出需要包含final且长度足够"""
        final = output.data.get("final", "")
        return len(final.strip()) >= 100


# ============ W5: 导出收尾 ============

class W5ExportStage(BaseStage):
    """W5: 导出收尾 — DB写入 + WriteGates(postcommit) + 投影。

    核心职责:
    - 写入章节文件到正文目录
    - 更新state.json（伏笔/角色/设定/进度）
    - 执行DB写入（character_states/foreshadowing_threads/chapter_outputs）
    - 执行投影（五路投影 + 增量索引更新）
    - 执行postcommit关卡（WriteGates）
    """

    stage_id = "W5"
    name = "导出收尾"
    knowledge_policy = {
        "layers": [],
        "inject_mode": "none",
    }

    def run(self, context: PipelineContext) -> StageOutput:
        """执行W5：写文件 + 更新state + DB写入 + 投影 + postcommit。"""
        warnings = []
        export_data = {}

        # 1. 获取最终内容
        w4_output = context.get_stage_output("W4")
        if not w4_output or not w4_output.success:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                errors=["W4润色结果不可用，无法导出"],
            )

        final_content = w4_output.data.get("final", "")
        if not final_content:
            return StageOutput(
                stage_id=self.stage_id,
                success=False,
                errors=["W4润色内容为空"],
            )

        project_dir = context.get("project_dir", "")
        chapter_num = context.get("chapter_num", 1)
        chapter_task = context.get("chapter_task", "")
        state = context.get("state", {})

        # 2. 写入章节文件
        file_path = self._write_chapter_file(project_dir, chapter_num, final_content)
        export_data["file_path"] = str(file_path) if file_path else ""

        # 3. 更新state.json
        self._update_state(state, final_content, chapter_num, chapter_task, project_dir)

        # 4-8: 责任链——PostCommitHooks
        from .post_commit_hooks import default_chain
        chain = default_chain()
        hook_result = chain.execute(project_dir, chapter_num, final_content, state)
        export_data["hooks"] = hook_result
        context.set("hook_results", hook_result)
        for r in hook_result["details"]:
            if not r.get("applied"):
                warnings.append(f"{r['hook']}: {r.get('error', 'unknown')}")

        return StageOutput(
            stage_id=self.stage_id,
            success=True,
            data=export_data,
            warnings=warnings,
        )

    def _write_chapter_file(
        self, project_dir: str, chapter_num: int, content: str
    ) -> Optional[Path]:
        """写入章节文件到正文目录。"""
        if not project_dir:
            return None

        content_dir = Path(project_dir) / "正文"
        content_dir.mkdir(exist_ok=True)

        file_path = content_dir / f"第{chapter_num}章.txt"
        try:
            file_path.write_text(content, encoding="utf-8")
            return file_path
        except Exception as e:
            print(f"[W5] 写入章节文件失败: {e}")
            return None

    def _update_state(
        self,
        state: Dict[str, Any],
        content: str,
        chapter_num: int,
        chapter_task: str,
        project_dir: str,
    ) -> None:
        """更新state.json：伏笔/角色/设定/进度。

        迁移自 pangu_optimized.py 的 _update_state_after_writing()。
        """
        if not content or len(content) < 100:
            return

        from datetime import datetime

        # ---- 1. 伏笔追踪 ----
        foreshadow = state.get("foreshadowing", {})
        if isinstance(foreshadow, list):
            active_threads = foreshadow
            foreshadow = {"active_threads": active_threads}
        else:
            active_threads = foreshadow.get("active_threads", [])

        # 只提取真正的叙事伏笔，不提取对话中的随机问句
        foreshadow_patterns = [
            # 未完成的事件暗示
            r'(?:不是现在|还不到时候|等.{2,6}之后再说)',
            # 隐藏信息暗示
            r'(?:不知道.{2,10}意味着什么|没人.{2,10}知道.{2,10}真相)',
            # 重复出现的异常
            r'(?:又来了|再一次|第三次|每次|总是)',
        ]
        new_threads = []
        for pat in foreshadow_patterns:
            matches = re.findall(pat, content)
            for m in matches[:3]:  # 每种最多3条
                desc = m if isinstance(m, str) else str(m)
                if 8 < len(desc) < 60:
                    is_dup = any(desc[:10] in t.get("description", "") for t in active_threads)
                    if not is_dup:
                        new_threads.append({
                            "id": f"f{len(active_threads)+len(new_threads)+1:03d}",
                            "planted_ch": chapter_num,
                            "description": desc[:60],
                            "status": "open",
                            "resolved_ch": None,
                        })
        if new_threads:
            active_threads.extend(new_threads[:2])  # 每章最多2条新伏笔
            foreshadow["active_threads"] = active_threads
            foreshadow["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["foreshadowing"] = foreshadow

        # ---- 2. 角色追踪 ----
        characters = state.get("characters", {})
        if isinstance(characters, list):
            characters = {"key_characters": characters}
        char_pattern = re.findall(
            r'([\u4e00-\u9fff]{2,3})(?:冷笑|沉声|低声|大笑|苦笑|淡然|怒声)?(?:道|说|喊|问|喝)',
            content,
        )
        # 角色名黑名单：人称/连词/副词碎片/地名/常见非名
        _NAME_BLACKLIST = {
            "他的","她的","我的","你的","这个","那个","怎么","什么","为什么",
            "然后","但是","因为","所以","如果","虽然","不过","已经","可以","没有",
            "不是","就是","还是","只是","可能","应该","知道","觉得","看到","听到",
            "今天","昨天","刚才","后来","以前","一直","真的","好的","对了",
            "自己","别人","大家","他们","我们","派出所","公安局","不知道","没关系",
            "也就是","比如说","不清楚","不确定","有一种","有一个","什么样",
        }
        _COMMON_SURNAMES = set("林陈江张王李赵刘周吴郑杨黄朱马何高罗郭梁谢韩唐于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文")
        char_counter = {}
        for name in char_pattern:
            if name not in _NAME_BLACKLIST:
                char_counter[name] = char_counter.get(name, 0) + 1
        # 只保留出现≥2次且首字是常见姓氏的
        char_counter = {
            n: c for n, c in char_counter.items()
            if c >= 2 and n[0] in _COMMON_SURNAMES
        }

        if char_counter:
            sorted_chars = sorted(char_counter.items(), key=lambda x: -x[1])
            protagonist = characters.get("protagonist", {})
            if not protagonist.get("name"):
                protagonist["name"] = sorted_chars[0][0]
            protagonist["last_chapter"] = chapter_num
            characters["protagonist"] = protagonist

            key_chars = characters.get("key_characters", [])
            existing_names = {c.get("name") for c in key_chars}
            for name, count in sorted_chars[:5]:
                if name not in existing_names:
                    key_chars.append({
                        "name": name, "role": "unknown",
                        "current_state": "", "last_chapter": chapter_num,
                    })
                    existing_names.add(name)
                else:
                    for c in key_chars:
                        if c.get("name") == name:
                            c["last_chapter"] = chapter_num
                            break
            characters["key_characters"] = key_chars
            state["characters"] = characters

        # ---- 3. 设定日志 ----
        setting_log = state.get("setting_log", {})
        if isinstance(setting_log, list):
            locked_rules = setting_log
            setting_log = {"locked_rules": locked_rules}
        else:
            locked_rules = setting_log.get("locked_rules", [])

        setting_patterns = re.findall(
            r'(?:等级|境界|阶段|层数|级别|能力|技能|天赋|异能)[：:是为]([^\n。，]{5,40})',
            content,
        )
        for sp in setting_patterns:
            rule_str = f"Ch{chapter_num}: {sp.strip()}"
            if rule_str not in locked_rules:
                locked_rules.append(rule_str)
        if setting_patterns:
            setting_log["locked_rules"] = locked_rules[-30:]
            setting_log["last_checked_chapter"] = chapter_num
            state["setting_log"] = setting_log

        # ---- 4. 总字数更新 ----
        state["progress"]["total_words"] = (
            state["progress"].get("total_words", 0)
            + len(content.replace('\n', '').replace(' ', ''))
        )
        state["progress"]["current_chapter"] = chapter_num

        # ---- 5. Lorebook自动建议 ----
        lorebook = state.get("lorebook", {})
        if char_counter and isinstance(lorebook, dict):
            for name, count in sorted(char_counter.items(), key=lambda x: -x[1])[:5]:
                if name not in lorebook:
                    lorebook[name] = {
                        "description": f"（待补充）{name}，在Ch{chapter_num}首次出现，出现{count}次",
                        "triggers": [name],
                        "priority": 3 if count > 3 else 5,
                    }
            state["lorebook"] = lorebook

        # ---- 6. 写回state.json ----
        if project_dir:
            state_path = Path(project_dir) / "state.json"
            try:
                state_path.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                print(f"[W5] 写入state.json失败: {e}")

    def _build_extraction(self, state, content, chapter_num):
        """从state和content中提取记忆写入所需的extraction数据"""
        extraction = {"foreshadowing": [], "characters": {}, "setting_log": []}
        # 伏笔
        foreshadow = state.get("foreshadowing", {})
        if isinstance(foreshadow, dict):
            for t in foreshadow.get("active_threads", []):
                if isinstance(t, dict) and t.get("status") == "open":
                    extraction["foreshadowing"].append(t)
        # 角色
        characters = state.get("characters", {})
        if isinstance(characters, dict):
            for name, info in characters.items():
                if isinstance(info, dict):
                    extraction["characters"][name] = info
        # 设定
        setting_log = state.get("setting_log", {})
        if isinstance(setting_log, dict):
            for rule in setting_log.get("locked_rules", []):
                extraction["setting_log"].append({"rule": rule})
        return extraction

    def validate_input(self, context: PipelineContext) -> bool:
        """W5需要W4的输出"""
        w4_output = context.get_stage_output("W4")
        return w4_output is not None and w4_output.success
