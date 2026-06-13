#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 统一写作管线引擎

统一双路径（快速/工坊）为单一Pipeline架构。
快速模式: W0 → W2 → W4 (跳过W1/W3/W5，W4后自动触发投影+DB写入)
工坊模式: W0 → W1 → W2 → W3 → W4 → W5

设计原则:
- PipelineConfig 工厂方法决定 active_stages
- WritingPipeline.run() 按 active_stages 顺序执行
- 快速模式通过 post_stage_hooks 在W4后自动执行投影/DB写入
- Stage执行失败时: warnings级别继续，errors级别视情况降级或终止
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

from .config import get_config, BASE_DIR


# ============ 数据结构 ============

@dataclass
class PipelineConfig:
    """Pipeline配置，支持快速模式和工坊模式两种工厂方法。

    Attributes:
        mode: "quick" or "workshop"
        quick_mode: 是否为快速模式
        project_dir: 项目目录绝对路径
        mode_rule: 模式规则文本（从modes/JSON加载）
        platform_rule: 平台规则文本（从platform_writing_profiles.json加载）
        chapter_num: 当前章节号
        chapter_task: 当前章节写作任务
        active_stages: 本次Pipeline需要执行的Stage列表
        stage_overrides: 各Stage的覆盖配置
    """
    mode: str
    quick_mode: bool
    project_dir: str
    mode_rule: str
    platform_rule: str
    chapter_num: int
    chapter_task: str
    active_stages: List[str]
    stage_overrides: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_quick_mode(
        cls,
        project_dir: str,
        chapter: int,
        task: str,
        mode: str = "general",
        platform: str = "qimao",
    ) -> "PipelineConfig":
        """从快速模式参数构建PipelineConfig。

        快速模式仅执行 W0 + W2 + W4，跳过W1/W3/W5。
        W4完成后通过post_stage_hooks自动触发投影和DB写入。
        """
        mode_rule = _load_mode_rule(mode)
        platform_rule = _load_platform_rule(platform)
        return cls(
            mode="quick",
            quick_mode=True,
            project_dir=project_dir,
            mode_rule=mode_rule,
            platform_rule=platform_rule,
            chapter_num=chapter,
            chapter_task=task,
            active_stages=["W0", "W2", "W4"],
        )

    @classmethod
    def from_workshop_mode(
        cls,
        project_dir: str,
        chapter: int,
        task: str,
        mode: str = "general",
        platform: str = "qimao",
    ) -> "PipelineConfig":
        """从工坊模式参数构建PipelineConfig。

        工坊模式执行全部 W0-W5，投影和DB写入在W5中执行。
        """
        mode_rule = _load_mode_rule(mode)
        platform_rule = _load_platform_rule(platform)
        return cls(
            mode="workshop",
            quick_mode=False,
            project_dir=project_dir,
            mode_rule=mode_rule,
            platform_rule=platform_rule,
            chapter_num=chapter,
            chapter_task=task,
            active_stages=["W0", "W1", "W2", "W3", "W4", "W5"],
        )


@dataclass
class PipelineContext:
    """Pipeline运行上下文，存储state、config和各Stage输出。

    所有Stage共享同一个PipelineContext实例，通过set/get传递数据。
    stage_outputs存储各Stage的执行结果，供后续Stage读取。
    """
    data: Dict[str, Any] = field(default_factory=dict)
    stage_outputs: Dict[str, "StageOutput"] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.data.get(key, default)

    def get_stage_output(self, stage_id: str) -> Optional["StageOutput"]:
        """获取指定Stage的输出"""
        return self.stage_outputs.get(stage_id)


@dataclass
class PipelineResult:
    """Pipeline执行结果

    Attributes:
        success: 是否整体成功（有内容输出即算成功，即使有warnings）
        chapter_content: 最终章节正文
        projections: 投影结果（五路投影的输出）
        db_records: 数据库写入记录
        warnings: 警告列表（不影响流程继续）
        errors: 错误列表（可能影响了流程）
    """
    success: bool
    chapter_content: str
    projections: Dict[str, Any] = field(default_factory=dict)
    db_records: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class StageOutput:
    """单个Stage的执行输出

    Attributes:
        stage_id: Stage标识，如"W0"/"W2"/"W4"
        success: 是否执行成功
        data: 输出数据字典（draft/final/qc_report等）
        warnings: 警告列表
        errors: 错误列表
    """
    stage_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ============ Pipeline引擎 ============

class WritingPipeline:
    """统一写作管线引擎，按active_stages顺序执行Stage。

    核心流程:
    1. 初始化PipelineConfig和PipelineContext
    2. 预读state.json和前文上下文
    3. 按active_stages顺序执行各Stage
    4. 快速模式下W4后自动触发投影/DB写入hooks
    5. 返回PipelineResult
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.stages: Dict[str, BaseStage] = {}
        self.context = PipelineContext(data={}, stage_outputs={})
        self._register_default_stages()
        self._init_context()

    def _register_default_stages(self) -> None:
        """注册所有默认Stage（W0-W5）

        使用延迟导入避免与stages.py的循环依赖。
        """
        from .stages import (
            W0AnchorStage, W1SetupStage, W2DraftStage,
            W3QCStage, W4PolishStage, W5ExportStage,
        )
        default_stages = [
            W0AnchorStage(),
            W1SetupStage(),
            W2DraftStage(),
            W3QCStage(),
            W4PolishStage(),
            W5ExportStage(),
        ]
        for stage in default_stages:
            self.register_stage(stage)

    def _init_context(self) -> None:
        """初始化PipelineContext，加载state.json和前文上下文"""
        project_dir = Path(self.config.project_dir)
        state_path = project_dir / "state.json"

        # 加载state.json + 校验数据形状
        state = {}
        if state_path.exists():
            try:
                raw = json.loads(state_path.read_text(encoding="utf-8"))
                from .state_validator import validate_state
                state = validate_state(raw)
            except Exception as e:
                print(f"[Pipeline] 加载state.json失败: {e}")

        info = state.get("project_info", {})

        # 填充context
        self.context.set("state", state)
        self.context.set("project_dir", str(project_dir))
        self.context.set("chapter_num", self.config.chapter_num)
        self.context.set("chapter_task", self.config.chapter_task)
        self.context.set("mode_name", info.get("genre", "general"))
        self.context.set("platform_name", info.get("platform", "qimao"))
        self.context.set("title", info.get("title", ""))
        self.context.set("quick_mode", self.config.quick_mode)
        self.context.set("mode_rule", self.config.mode_rule)
        self.context.set("platform_rule", self.config.platform_rule)
        self.context.set("context_content", "")

        # 加载前文上下文
        self._load_previous_context(project_dir, self.config.chapter_num)

        # T02: StateSync初始化
        try:
            from .state_sync import StateSync
            from .db import get_db
            db = get_db()
            state_sync = StateSync(str(project_dir), db)
            db_ctx = state_sync.sync_from_db()
            self.context.set("db_context", db_ctx)
            self.context.set("state_sync", state_sync)
        except ImportError:
            self.context.set("db_context", None)
            self.context.set("state_sync", None)
        except Exception as e:
            print(f"[Pipeline] StateSync初始化失败(降级): {e}")
            self.context.set("db_context", None)
            self.context.set("state_sync", None)

    def _load_previous_context(self, project_dir: Path, chapter_num: int) -> None:
        """加载前序章节作为上下文"""
        content_dir = project_dir / "正文"
        if not content_dir.exists():
            return

        prev_chapters = []
        max_chapters = 2
        for ch_num in range(max(1, chapter_num - max_chapters), chapter_num):
            possible_files = list(content_dir.glob(f"第{ch_num}章*.txt"))
            if possible_files:
                try:
                    content = possible_files[0].read_text(encoding="utf-8")
                    prev_chapters.append((ch_num, content))
                except Exception:
                    pass

        if not prev_chapters:
            return

        result = "## 前面的章节（上下文参考）\n\n"
        for ch_num, content in prev_chapters:
            result += f"### 第{ch_num}章\n\n"
            result += content[:1500]
            if len(content) > 1500:
                result += "\n...（本章内容较长，只显示前1500字）"
            result += "\n\n"

        self.context.set("context_content", result)

    def register_stage(self, stage: Any) -> None:
        """注册一个Stage到Pipeline"""
        self.stages[stage.stage_id] = stage

    def run(self) -> PipelineResult:
        """执行Pipeline，按active_stages顺序运行Stage。

        执行规则:
        - 只执行active_stages中的Stage，其余跳过
        - Stage失败时: warnings级别继续，errors级别视严重性决定
        - W2/W4为核心Stage，异常则终止Pipeline
        - 快速模式W4完成后自动触发投影+DB写入hooks
        """
        warnings: List[str] = []
        errors: List[str] = []

        print("=" * 60)
        print(f"  盘古Pipeline | mode={self.config.mode} | 第{self.config.chapter_num}章")
        print(f"  active_stages: {self.config.active_stages}")
        print("=" * 60)

        for stage_id in self.config.active_stages:
            if self._should_skip(stage_id):
                print(f"  [{stage_id}] 跳过(非active)")
                continue

            print(f"\n  [{stage_id}] 开始执行...")
            t0 = time.time()

            try:
                output = self._execute_stage(stage_id)
                self.context.stage_outputs[stage_id] = output

                elapsed = time.time() - t0
                content_len = len(str(output.data)) if output.data else 0
                status = "OK" if output.success else "FAIL"
                print(f"  [{stage_id}] {status} ({elapsed:.1f}s, {content_len}字)")

                if not output.success:
                    has_critical = any(
                        "critical" in e.lower() or "blocker" in e.lower()
                        for e in output.errors
                    )
                    if has_critical:
                        errors.extend(output.errors)
                        print(f"  [{stage_id}] 严重错误，终止Pipeline")
                        break
                    else:
                        warnings.extend(output.warnings)
                        errors.extend(output.errors)
                        print(f"  [{stage_id}] 有警告，继续执行")
                else:
                    warnings.extend(output.warnings)

            except Exception as e:
                error_msg = f"Stage {stage_id} 执行异常: {e}"
                errors.append(error_msg)
                print(f"  [{stage_id}] 异常: {e}")

                # 核心Stage(W2/W4)异常则终止
                if stage_id in ("W2", "W4"):
                    break

        # 获取最终章节内容
        chapter_content = self._extract_final_content()

        # 快速模式下W4完成后自动触发投影和DB写入（因为没有W5）
        if self.config.quick_mode and chapter_content:
            self._run_quick_mode_post_hooks(chapter_content, warnings, errors)

        # 判定整体成功
        success = len(errors) == 0 or bool(chapter_content)

        print("\n" + "=" * 60)
        print(f"  Pipeline执行完毕: {'成功' if success else '部分成功' if chapter_content else '失败'}")
        if warnings:
            print(f"  警告: {len(warnings)}个")
        if errors:
            print(f"  错误: {len(errors)}个")
        print("=" * 60)

        return PipelineResult(
            success=success,
            chapter_content=chapter_content,
            projections=self.context.get("projections", {}),
            db_records=self.context.get("db_records", {}),
            warnings=warnings,
            errors=errors,
        )

    def _execute_stage(self, stage_id: str) -> StageOutput:
        """执行单个Stage"""
        stage = self.stages.get(stage_id)
        if stage is None:
            return StageOutput(
                stage_id=stage_id,
                success=False,
                errors=[f"未注册的Stage: {stage_id}"],
            )

        # 设置当前执行的stage_id到context
        self.context.set("current_stage_id", stage_id)

        # 验证输入
        if not stage.validate_input(self.context):
            return StageOutput(
                stage_id=stage_id,
                success=False,
                errors=[f"Stage {stage_id} 输入验证失败"],
            )

        # 执行Stage
        output = stage.run(self.context)

        # 验证输出
        if output.success and not stage.validate_output(output):
            output.warnings.append(f"Stage {stage_id} 输出验证警告")

        return output

    def _should_skip(self, stage_id: str) -> bool:
        """判断是否跳过某个Stage"""
        return stage_id not in self.config.active_stages

    def _extract_final_content(self) -> str:
        """从Stage输出中提取最终章节内容"""
        # 优先使用W4的精修输出
        w4_output = self.context.get_stage_output("W4")
        if w4_output and w4_output.success:
            return w4_output.data.get("final", "")

        # 降级到W2的初稿
        w2_output = self.context.get_stage_output("W2")
        if w2_output and w2_output.success:
            return w2_output.data.get("draft", "")

        return ""

    def _run_quick_mode_post_hooks(
        self,
        chapter_content: str,
        warnings: List[str],
        errors: List[str],
    ) -> None:
        """责任链：执行所有 PostCommitHook。任一失败不中断后续。"""
        project_dir = self.config.project_dir
        chapter_num = self.config.chapter_num
        state = self.context.get("state", {})

        # 事件总线: 章节写完 → 发布事件
        from .event_bus import ChapterWritten, bus
        event = ChapterWritten()
        event.project = project_dir
        event.chapter = chapter_num
        event.words = len(chapter_content.replace('\n','').replace(' ',''))
        event.content = chapter_content
        event.state = state
        bus.dispatch(event)

        # 责任链 (保留，同时运行)
        from .post_commit_hooks import default_chain
        chain = default_chain()
        result = chain.execute(project_dir, chapter_num, chapter_content, state)
        self.context.set("hook_results", result)
        for r in result["details"]:
            if not r.get("applied"):
                warnings.append(f"{r['hook']}: {r.get('error', 'unknown')}")


# ============ 辅助函数 ============

def _load_mode_rule(mode_name: str) -> str:
    """加载模式规则文本（从modes/JSON文件）"""
    mode_file = BASE_DIR / "modes" / f"{mode_name}.json"
    if not mode_file.exists():
        # 尝试模糊匹配
        for mf in (BASE_DIR / "modes").glob("*.json"):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
                if data.get("mode_id") == mode_name or data.get("name", "").startswith(mode_name):
                    mode_file = mf
                    break
            except Exception:
                pass

    if not mode_file.exists():
        return ""

    try:
        mode = json.loads(mode_file.read_text(encoding="utf-8"))
        rules = []
        if mode.get("core_principle"):
            rules.append(f"核心原则: {mode['core_principle']}")

        w2 = mode.get("w2_special", {})
        if w2.get("dialogue_priority"):
            rules.append(f"对话优先级: {w2['dialogue_priority']}")
        if w2.get("action_style"):
            rules.append(f"动作风格: {w2['action_style']}")
        if w2.get("hook_types"):
            rules.append(f"可用钩子类型: {', '.join(w2['hook_types'])}")
        if w2.get("forbidden_hook_types"):
            rules.append(f"禁用钩子类型: {', '.join(w2['forbidden_hook_types'])}")

        w4 = mode.get("w4_special", {})
        if w4.get("emotion_parameter"):
            rules.append(f"情绪参数: {w4['emotion_parameter']}")
        if w4.get("sensory_priority"):
            rules.append(f"五感优先级: {' > '.join(w4['sensory_priority'])}")
        if w4.get("dialogue_style"):
            rules.append(f"对话风格: {w4['dialogue_style']}")
        if w4.get("taboo"):
            rules.append(f"禁用: {w4['taboo']}")

        return "\n".join(f"  - {r}" for r in rules) if rules else ""
    except Exception as e:
        print(f"[Pipeline] 加载模式规则失败: {e}")
        return ""


def _load_platform_rule(platform_name: str) -> str:
    """加载平台规则文本（从platform_writing_profiles.json）"""
    config_file = BASE_DIR / "knowledge" / "platform_writing_profiles.json"
    if not config_file.exists():
        return ""

    try:
        configs = json.loads(config_file.read_text(encoding="utf-8"))
        profile = configs.get("profiles", {}).get(platform_name)
        if not profile:
            return ""

        rules = []
        rules.append(f"平台: {profile.get('name', platform_name)}")
        rules.append(f"核心逻辑: {profile.get('core_logic', '')}")
        rules.append(f"章节字数: {profile.get('chapter_length', '2000')}字")

        opening = profile.get("opening", {})
        if opening.get("golden_rule"):
            rules.append(f"黄金开篇: {opening['golden_rule']}")

        sent = profile.get("sentence_rules", {})
        if sent.get("max_chars_per_sentence"):
            rules.append(f"句长上限: {sent['max_chars_per_sentence']}字")
        if sent.get("style"):
            rules.append(f"句法风格: {sent['style']}")

        dia = profile.get("dialogue_rules", {})
        if dia.get("min_ratio"):
            rules.append(f"对话率: ≥{int(dia['min_ratio']*100)}%")

        taboo = profile.get("taboo", [])
        if taboo:
            rules.append(f"禁忌: {', '.join(taboo[:5])}")

        return "\n".join(f"  - {r}" for r in rules) if rules else ""
    except Exception as e:
        print(f"[Pipeline] 加载平台规则失败: {e}")
        return ""
