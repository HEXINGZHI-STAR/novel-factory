#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI · Write Gates 三层关卡
从 webnovel-writer write_gates 移植并适配盘古项目结构

三层关卡：
  prewrite  → W0之前调用，检查项目状态是否允许写作
  precommit → W4之后、状态更新之前调用，检查生成内容质量
  postcommit → 状态更新之后调用，检查投影完整性

盘古适配要点：
  - 不依赖 .story-system/ 目录，改用 projects/{name}/state.json
  - 检查 state.json 中的 伏笔/角色/设定/lorebook 字段
  - 正文文件在 正文/ 目录下
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# 数据结构与工具函数（从 webnovel-writer 移植）
# ============================================================

SCHEMA_VERSION = "pangu-write-gate/v1"
STAGES = ("prewrite", "precommit", "postcommit")


def issue(
    code: str,
    *,
    message: str,
    severity: str = "blocker",
    path: str = "",
    impact: str = "",
    repair: str = "",
    details: Any = None,
) -> Dict[str, Any]:
    """构建单个问题字典"""
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "path": path,
        "impact": impact,
        "repair": repair,
        "details": details,
    }


def gate_report(
    *,
    stage: str,
    project_dir: str | Path,
    chapter: int,
    phase: str,
    errors: List[Dict[str, Any]] | None = None,
    warnings: List[Dict[str, Any]] | None = None,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """构建关卡报告"""
    errors = errors or []
    warnings = warnings or []
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "project_dir": str(project_dir),
        "chapter": chapter,
        "phase": phase,
        "ok": not any(item.get("severity") == "blocker" for item in errors),
        "errors": errors,
        "warnings": warnings,
        "details": details or {},
    }


def format_gate_report(report: Dict[str, Any], output_format: str = "json") -> str:
    """格式化关卡报告为可读文本"""
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    status = "OK" if report.get("ok") else "ERROR"
    lines = [
        f"{status} write-gate {report.get('stage')}",
        f"project_dir: {report.get('project_dir')}",
        f"chapter: {report.get('chapter')}",
        f"phase: {report.get('phase')}",
    ]
    for item in report.get("errors") or []:
        lines.append(f"ERROR {item.get('code')}: {item.get('message')}")
        if item.get("path"):
            lines.append(f"  path: {item.get('path')}")
        if item.get("impact"):
            lines.append(f"  impact: {item.get('impact')}")
        if item.get("repair"):
            lines.append(f"  repair: {item.get('repair')}")
    for item in report.get("warnings") or []:
        lines.append(f"WARNING {item.get('code')}: {item.get('message')}")
    return "\n".join(lines)


# ============================================================
# 盘古项目状态读取
# ============================================================

def _load_state(project_dir: Path) -> Optional[Dict[str, Any]]:
    """读取项目 state.json，失败返回 None"""
    state_file = project_dir / "state.json"
    if not state_file.is_file():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _get_phase(project_dir: Path, chapter: int) -> str:
    """推断项目当前阶段（简化版，不依赖 webnovel-writer 的 project_phase 模块）"""
    state = _load_state(project_dir)
    if state is None:
        return "no_project"
    progress = state.get("progress", {})
    current = progress.get("current_chapter", 0)
    total_words = progress.get("total_words", 0)

    if current == 0:
        return "init_ready"   # 可以开始写第一章
    if chapter <= current:
        return "draft_in_progress"   # 正在写作中
    # chapter > current: 需要先进行规划
    return "plan_in_progress"


def _find_chapter_file(project_dir: Path, chapter: int) -> Optional[Path]:
    """查找正文文件（适配盘古的 正文/第X章_xxx.txt 命名规则）"""
    text_dir = project_dir / "正文"
    if not text_dir.is_dir():
        return None
    # 尝试精确匹配
    for f in text_dir.iterdir():
        if f.is_file() and f.suffix == ".txt":
            m = re.search(r"第(\d+)章", f.stem)
            if m and int(m.group(1)) == chapter:
                return f
    return None


# ============================================================
# Prewrite Gate（写前关卡）
# ============================================================

def run_prewrite_gate(project_dir: Path, chapter: int) -> Dict[str, Any]:
    """
    写前关卡：检查项目是否准备好写作本章

    检查项：
      1. state.json 存在且合法
      2. project_info 包含必要的 title/mode/platform
      3. characters 非空（至少有主角信息）
      4. setting_log 已初始化（有世界规则）
      5. 本章 task 已在 chapter_meta 中定义（非首章时）
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    phase = _get_phase(project_dir, chapter)
    details: Dict[str, Any] = {"phase": phase}

    # ---- 1. state.json 检查 ----
    state = _load_state(project_dir)
    if state is None:
        errors.append(issue(
            "state_missing",
            message=f"state.json 不存在或无法读取: {project_dir / 'state.json'}",
            impact="无法获取项目状态，写作将使用空上下文",
            repair="检查项目目录是否完整，或重新创建项目",
            path=str(project_dir / "state.json"),
        ))
        return gate_report(
            stage="prewrite",
            project_dir=project_dir,
            chapter=chapter,
            phase="no_project",
            errors=errors,
            warnings=warnings,
            details=details,
        )

    details["state_loaded"] = True

    # ---- 2. project_info 检查 ----
    proj_info = state.get("project_info", {})
    if not isinstance(proj_info, dict):
        errors.append(issue(
            "project_info_invalid",
            message="project_info 字段不存在或格式错误",
            impact="无法获取作品题材/模式/平台信息",
            repair="检查 state.json 中 project_info 字段",
            path=str(project_dir / "state.json"),
        ))
    else:
        missing_fields = []
        for f in ("title", "mode", "platform"):
            if not proj_info.get(f):
                missing_fields.append(f)
        if missing_fields:
            warnings.append(issue(
                "project_info_incomplete",
                message=f"project_info 缺少字段: {', '.join(missing_fields)}",
                severity="warning",
                impact="可能影响提示词注入准确度",
                repair=f"补全 state.json 中的 {', '.join(missing_fields)} 字段",
                path=str(project_dir / "state.json"),
            ))

    # ---- 3. characters 检查 ----
    characters = state.get("characters", {})
    if not isinstance(characters, dict) or len(characters) == 0:
        warnings.append(issue(
            "characters_empty",
            message="characters 字段为空，未定义任何角色",
            severity="warning",
            impact="AI 生成时可能角色塑造不一致",
            repair="在 state.json 中补全主要角色信息",
            path=str(project_dir / "state.json"),
        ))
    else:
        # 检查是否有主角
        has_protagonist = any(
            isinstance(c, dict) and c.get("role") == "主角"
            for c in characters.values()
        )
        if not has_protagonist:
            warnings.append(issue(
                "no_protagonist",
                message="未找到 role=主角 的角色定义",
                severity="warning",
                impact="AI 可能不知道谁是第一视角",
                repair="在 characters 中至少定义一个 role=主角 的角色",
            ))

    # ---- 4. setting_log 检查 ----
    setting_log = state.get("setting_log", [])
    if not isinstance(setting_log, list) or len(setting_log) == 0:
        warnings.append(issue(
            "setting_log_empty",
            message="setting_log 为空，未定义世界规则",
            severity="warning",
            impact="生成内容可能与世界观设定冲突",
            repair="在 state.json 中初始化 setting_log",
        ))

    # ---- 5. chapter_meta / 本章 task 检查 ----
    chapter_meta = state.get("chapter_meta", {})
    chapter_key = f"chapter_{chapter}"
    if chapter > 1 and chapter_key not in chapter_meta:
        warnings.append(issue(
            "chapter_task_undefined",
            message=f"第{chapter}章的 task 未在 chapter_meta 中定义",
            severity="warning",
            impact="AI 不知道本章应该写什么",
            repair=f"在 chapter_meta 中添加 {chapter_key}.task",
        ))

    # ---- 6. 伏笔/设定追踪字段检查 ----
    for field_name in ("foreshadowing", "setting_log"):
        field_val = state.get(field_name)
        if field_val is None:
            warnings.append(issue(
                f"{field_name}_missing",
                message=f"state.json 缺少 {field_name} 字段",
                severity="warning",
                impact=f"{field_name} 追踪将在此章后失效",
                repair=f"在 state.json 中初始化 {field_name} 字段",
            ))

    details["characters_count"] = len(characters) if isinstance(characters, dict) else 0
    details["setting_rules_count"] = len(setting_log) if isinstance(setting_log, list) else 0
    details["foreshadowing_count"] = len(state.get("foreshadowing", [])) if isinstance(state.get("foreshadowing"), list) else 0

    return gate_report(
        stage="prewrite",
        project_dir=project_dir,
        chapter=chapter,
        phase=phase,
        errors=errors,
        warnings=warnings,
        details=details,
    )


# ============================================================
# Precommit Gate（写后提交前关卡）
# ============================================================

def run_precommit_gate(
    project_dir: Path,
    chapter: int,
    content: str = "",
) -> Dict[str, Any]:
    """
    写后提交前关卡：检查生成的正文内容是否合格

    检查项：
      1. 正文文件存在且非空
      2. 内容长度合理（≥500字）
      3. 复用盘古已有的 _inline_quick_score 逻辑检测质量
      4. 检查合同节点覆盖（如果有定义本章必写节点）
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    phase = _get_phase(project_dir, chapter)
    details: Dict[str, Any] = {"phase": phase}

    # ---- 1. 正文文件检查 ----
    chapter_file = _find_chapter_file(project_dir, chapter)
    actual_content = content or ""

    if chapter_file is None:
        if not actual_content:
            errors.append(issue(
                "chapter_file_missing",
                message=f"第{chapter}章正文文件不存在，且未提供内容参数",
                path=str(project_dir / "正文"),
                impact="没有可提交的正文",
                repair="先完成正文生成并保存到 正文/ 目录",
            ))
            return gate_report(
                stage="precommit",
                project_dir=project_dir,
                chapter=chapter,
                phase=phase,
                errors=errors,
                warnings=warnings,
                details=details,
            )
    else:
        if not actual_content:
            try:
                actual_content = chapter_file.read_text(encoding="utf-8")
            except OSError:
                errors.append(issue(
                    "chapter_file_unreadable",
                    message=f"无法读取正文文件: {chapter_file}",
                    path=str(chapter_file),
                    impact="无法检查正文质量",
                    repair="检查文件权限和编码",
                ))
                actual_content = ""

    # ---- 2. 内容长度检查 ----
    if not actual_content or len(actual_content.strip()) < 100:
        errors.append(issue(
            "content_too_short",
            message=f"正文内容过短（{len(actual_content)}字，预期≥500字）",
            impact="章节内容不完整",
            repair="重新生成正文，确保输出≥500字",
        ))
        details["content_length"] = len(actual_content)
        return gate_report(
            stage="precommit",
            project_dir=project_dir,
            chapter=chapter,
            phase=phase,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    details["content_length"] = len(actual_content)

    # ---- 3. 质量检查（复用盘古的 inline_quick_score 逻辑）----
    quality_issues = _check_content_quality(actual_content)
    for qi in quality_issues:
        if qi.get("severity") == "blocker":
            errors.append(qi)
        else:
            warnings.append(qi)
    details["quality_issues_count"] = len(quality_issues)

    # ---- 4. 合同节点覆盖检查 ----
    state = _load_state(project_dir)
    if state is not None:
        chapter_meta = state.get("chapter_meta", {})
        chapter_key = f"chapter_{chapter}"
        meta = chapter_meta.get(chapter_key, {})
        mandatories = meta.get("must_cover_nodes", [])
        if mandatories:
            # 检查必写节点是否出现在正文中
            missing_nodes = []
            for node in mandatories:
                if node not in actual_content:
                    missing_nodes.append(node)
            if missing_nodes:
                warnings.append(issue(
                    "mandatory_nodes_not_covered",
                    message=f"必写情节点未覆盖: {', '.join(missing_nodes[:3])}",
                    severity="warning",
                    impact="本章可能偏离规划",
                    repair="在提示词中强调必写节点，或手动补充",
                ))
                details["missing_nodes"] = missing_nodes

    return gate_report(
        stage="precommit",
        project_dir=project_dir,
        chapter=chapter,
        phase=phase,
        errors=errors,
        warnings=warnings,
        details=details,
    )


def _check_content_quality(content: str) -> List[Dict[str, Any]]:
    """
    简化版内容质量检查，复用盘古 quality_checker 的检测逻辑
    不依赖外部模块，纯正则实现
    """
    issues: List[Dict[str, Any]] = []

    # AI 高风险词汇检查
    ai_high_risk = [
        ("他感到", "AI模板表达：'他感到'→用具体动作代替"),
        ("他心中", "AI模板表达：'他心中'→展示内心活动"),
        ("他暗道", "AI模板表达：'他暗道'→用对话或动作"),
        ("缓缓地", "AI味副词：'缓缓地'→用具体动作节奏"),
        ("淡淡地", "AI味副词：'淡淡地'→用神态描写"),
        ("忽然", "AI过渡词：'忽然'→用具体触发事件"),
        ("突然", "AI过渡词：'突然'→铺垫后自然发生"),
        ("不是……而是", "AI判断结构：'不是……而是'→用对比动作展示"),
    ]
    for pattern, suggestion in ai_high_risk:
        count = content.count(pattern)
        if count > 0:
            issues.append(issue(
                "ai_template",
                message=f"AI模板表达 '{pattern}' 出现{count}次",
                severity="blocker" if count >= 3 else "warning",
                repair=suggestion,
            ))

    # 连续短句检查
    sentences = [s.strip() for s in re.split(r'[。！？\n]', content) if s.strip()]
    if sentences:
        short_count = sum(1 for s in sentences if len(s) <= 12)
        short_ratio = short_count / len(sentences)
        if short_ratio > 0.3:
            issues.append(issue(
                "too_many_short_sentences",
                message=f"短句率{short_ratio:.0%}过高（≥30%），AI特征明显",
                severity="warning",
                repair="将短句合并或扩展为复合句（≥25字）",
            ))

        # 平均句长检查
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        if avg_len < 18:
            issues.append(issue(
                "avg_sentence_too_short",
                message=f"平均句长仅{avg_len:.0f}字（预期≥25字），AI写法特征",
                severity="warning",
                repair="扩展句子，加入动作/环境/心理的具体描写",
            ))

    # 章末钩子检查
    last_200 = content[-200:] if len(content) > 200 else content
    hook_keywords = ["不知道的是", "却没看到", "背后的", "秘密", "真相",
                     "逼近", "危机", "原来", "居然", "接下来", "即将"]
    has_hook = any(kw in last_200 for kw in hook_keywords)
    if not has_hook and len(content) > 500:
        issues.append(issue(
            "no_ending_hook",
            message="章末未检测到钩子（悬念/危机/反转/期待）",
            severity="warning",
            repair="在章末加入：悬念（但他不知道...）/危机（黑暗中...）/反转（原来...）",
        ))

    return issues


# ============================================================
# Postcommit Gate（提交后关卡）
# ============================================================

def run_postcommit_gate(
    project_dir: Path,
    chapter: int,
) -> Dict[str, Any]:
    """
    提交后关卡：检查状态更新和投影的完整性

    检查项：
      1. state.json 成功更新（progress.current_chapter 已前进）
      2. 伏笔/角色/设定 字段已写入（非首次）
      3. lorebook 字段已更新（如果启用）
      4. 正文文件确实存在且非空
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    details: Dict[str, Any] = {}

    state = _load_state(project_dir)
    if state is None:
        errors.append(issue(
            "state_missing_postcommit",
            message="postcommit 检查失败：state.json 不存在",
            impact="状态追踪已中断",
            repair="手动修复 state.json 或重新运行本章",
            path=str(project_dir / "state.json"),
        ))
        return gate_report(
            stage="postcommit",
            project_dir=project_dir,
            chapter=chapter,
            phase="error",
            errors=errors,
            warnings=warnings,
            details=details,
        )

    # ---- 1. progress 检查 ----
    progress = state.get("progress", {})
    current = progress.get("current_chapter", 0)
    details["current_chapter"] = current
    details["expected_chapter"] = chapter

    if current < chapter:
        warnings.append(issue(
            "progress_not_advanced",
            message=f"progress.current_chapter={current}，期望≥{chapter}",
            severity="warning",
            impact="项目进度未正确更新",
            repair="检查 _update_state_after_writing 是否被正确调用",
        ))

    # ---- 2. 伏笔/角色/设定 字段检查 ----
    foresadowing = state.get("foreshadowing", None)
    if foresadowing is None:
        warnings.append(issue(
            "foreshadowing_not_updated",
            message="state.json 中 foreshadowing 字段不存在",
            severity="warning",
            impact="伏笔追踪已中断",
            repair="在 state.json 中初始化 foreshadowing 字段",
        ))
    else:
        details["foreshadowing_count"] = len(foresadowing) if isinstance(foresadowing, list) else 0

    characters = state.get("characters", None)
    if characters is None:
        warnings.append(issue(
            "characters_not_updated",
            message="state.json 中 characters 字段不存在",
            severity="warning",
            impact="角色状态追踪已中断",
            repair="检查 _update_state_after_writing 中的角色更新逻辑",
        ))

    setting_log = state.get("setting_log", None)
    if setting_log is None:
        warnings.append(issue(
            "setting_log_not_updated",
            message="state.json 中 setting_log 字段不存在",
            severity="warning",
            impact="世界规则追踪已中断",
            repair="在 state.json 中初始化 setting_log 字段",
        ))

    # ---- 3. lorebook 字段检查（如果之前存在）----
    lorebook = state.get("lorebook", None)
    if lorebook is not None:
        details["lorebook_keys"] = list(lorebook.keys()) if isinstance(lorebook, dict) else []
    # lorebook 不存在不算错误（可能未启用）

    # ---- 4. 正文文件存在性检查 ----
    chapter_file = _find_chapter_file(project_dir, chapter)
    if chapter_file is None:
        errors.append(issue(
            "chapter_file_not_found_postcommit",
            message=f"提交后未找到第{chapter}章正文文件",
            path=str(project_dir / "正文"),
            impact="正文丢失，读者无法阅读本章",
            repair="检查正文文件保存逻辑",
        ))
    elif chapter_file.is_file():
        try:
            content = chapter_file.read_text(encoding="utf-8")
            if not content.strip():
                errors.append(issue(
                    "chapter_file_empty_postcommit",
                    message=f"第{chapter}章正文文件为空",
                    path=str(chapter_file),
                    impact="提交了空章节",
                    repair="重新生成本章正文",
                ))
            else:
                details["chapter_word_count"] = len(content)
        except OSError:
            warnings.append(issue(
                "chapter_file_unreadable_postcommit",
                message=f"无法读取提交后的正文文件: {chapter_file}",
                severity="warning",
            ))

    # ---- 5. chapter_meta 更新检查 ----
    chapter_meta = state.get("chapter_meta", {})
    chapter_key = f"chapter_{chapter}"
    if chapter_key not in chapter_meta:
        warnings.append(issue(
            "chapter_meta_not_updated",
            message=f"chapter_meta 中缺少 {chapter_key} 记录",
            severity="warning",
            impact="章节元数据未记录，后续上下文可能缺失",
            repair="检查 _update_state_after_writing 中的 chapter_meta 更新",
        ))
    else:
        meta = chapter_meta[chapter_key]
        details["chapter_meta_has_summary"] = bool(meta.get("summary"))
        details["chapter_meta_has_word_count"] = bool(meta.get("word_count"))

    return gate_report(
        stage="postcommit",
        project_dir=project_dir,
        chapter=chapter,
        phase=_get_phase(project_dir, chapter),
        errors=errors,
        warnings=warnings,
        details=details,
    )


# ============================================================
# 统一入口
# ============================================================

def run_write_gate(
    project_dir: str | Path,
    *,
    chapter: int,
    stage: str,
    content: str = "",
) -> Dict[str, Any]:
    """
    统一入口：运行指定阶段的 Write Gate

    参数：
      project_dir: 项目根目录（包含 state.json 的目录）
      chapter: 目标章节号
      stage: "prewrite" | "precommit" | "postcommit"
      content: （仅 precommit 需要）生成的正文内容
    """
    project_path = Path(project_dir).expanduser().resolve()
    if stage == "prewrite":
        return run_prewrite_gate(project_path, chapter)
    if stage == "precommit":
        return run_precommit_gate(project_path, chapter, content=content)
    if stage == "postcommit":
        return run_postcommit_gate(project_path, chapter)
    raise ValueError(f"未知的 write-gate stage: {stage}")


# ============================================================
# CLI 入口（供测试用）
# ============================================================

if __name__ == "__main__":
    import sys

    def _print_report(report: Dict[str, Any]) -> None:
        print(format_gate_report(report, output_format="text"))
        print()
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if len(sys.argv) >= 4:
        project = sys.argv[1]
        stage = sys.argv[2]
        chapter = int(sys.argv[3])
        content = sys.argv[4] if len(sys.argv) > 4 else ""
        report = run_write_gate(project, chapter=chapter, stage=stage, content=content)
        _print_report(report)
    else:
        # 自测：使用第一个可用项目
        print("用法: python write_gates.py <项目目录> <stage> <章节号> [正文内容]")
        print("示例: python write_gates.py projects/深渊猎人 prewrite 1")
        print("\n自测模式：尝试查找可用项目...")

        # 查找可用的项目目录
        candidates = [
            Path(__file__).parent.parent / "projects" / "深渊猎人",
            Path(__file__).parent.parent / "projects" / "镇妖司：新科状元",
        ]
        for cand in candidates:
            if (cand / "state.json").is_file():
                print(f"\n自测项目: {cand}")
                for stage in ("prewrite", "precommit", "postcommit"):
                    print(f"\n{'='*50}")
                    report = run_write_gate(cand, chapter=1, stage=stage)
                    print(format_gate_report(report, output_format="text"))
                break
        else:
            print("未找到可用项目，跳过自测")
