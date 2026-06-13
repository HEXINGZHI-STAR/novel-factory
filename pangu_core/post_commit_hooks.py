"""
盘古AI · Post-Commit Hook 责任链

借鉴 Java Servlet Filter Chain 模式:
每个 Hook 只做一件事，通过 next() 串联。
任一 Hook 失败不影响后续——独立降级，独立日志。

替代 pipeline.py 中 _run_quick_mode_post_hooks 的 5 个 try/except。

用法:
    chain = HookChain()
    chain.register(DBWriteHook())
    chain.register(ProjectionHook())
    chain.register(MemoryCommitHook())
    chain.register(PostCommitGateHook())
    chain.register(IntelligenceHook())
    chain.register(KPIUpdateHook())
    result = chain.execute(context, chapter_content)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ================================================================
# Hook 接口
# ================================================================

class PostCommitHook(ABC):
    """后提交钩子抽象。每个钩子独立执行，返回执行结果。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """钩子名称（用于日志）"""
        ...

    @abstractmethod
    def execute(self, project_dir: str, chapter_num: int,
                chapter_content: str, state: dict) -> dict:
        """执行钩子。返回 {"applied": True/False, "detail": ...}。"""
        ...


# ================================================================
# Hook 实现
# ================================================================

class DBWriteHook(PostCommitHook):
    name = "DB写入"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from .state_sync import StateSync
            from .db import get_db
            db = get_db()
            state_sync = StateSync(project_dir, db)
            counts = state_sync.sync_to_db(state)
            return {"applied": True, "detail": str(counts)}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


class ProjectionHook(PostCommitHook):
    name = "投影"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from .projection import run_projections
            info = state.get("project_info", {})
            mode_name = info.get("genre", "general")
            proj = run_projections(project_dir, chapter_num, chapter_content, "", mode_name)
            return {"applied": True, "detail": f"{sum(1 for v in proj.values() if v.get('applied'))}/5路"}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


class MemoryCommitHook(PostCommitHook):
    name = "记忆提交"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from .memory_layers import PanguMemoryOrchestrator
            from pathlib import Path
            orchestrator = PanguMemoryOrchestrator(Path(project_dir))
            orchestrator.commit_memory(chapter_num, chapter_content)
            return {"applied": True, "detail": "OK"}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


class PostCommitGateHook(PostCommitHook):
    name = "postcommit关卡"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from .write_gates import run_write_gate
            gate = run_write_gate(project_dir, chapter=chapter_num, stage="postcommit")
            ok = gate.get("ok", True) if gate else True
            if not ok:
                blockers = [e for e in gate.get("errors", [])
                           if e.get("severity") == "blocker"]
                if blockers:
                    return {"applied": False, "blocked": True,
                            "detail": blockers[0].get("message", "")[:80]}
            return {"applied": True, "detail": "OK" if ok else "FAIL"}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


class IntelligenceHook(PostCommitHook):
    name = "情报中心"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from pangu_intelligence import pipeline_post_commit_hook
            ci = pipeline_post_commit_hook(project_dir, chapter_num, chapter_content, state)
            return {"applied": True, "detail": ci.summary()[:80] if ci else "N/A"}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


class KPIUpdateHook(PostCommitHook):
    name = "KPI更新"

    def execute(self, project_dir, chapter_num, chapter_content, state):
        try:
            from pangu_project.kpi import KPIDashboard
            wc = len(chapter_content.replace('\n', '').replace(' ', ''))
            dash = KPIDashboard(project_dir)
            dash.record(chapter_num, score=80, words=wc, cost=0.003, time_h=0.5)
            return {"applied": True, "detail": f"{dash.overall_score():.0f}/100"}
        except Exception as e:
            return {"applied": False, "error": str(e)[:100]}


# ================================================================
# 责任链
# ================================================================

@dataclass
class HookChain:
    """责任链：按注册顺序执行所有 Hook。"""
    hooks: List[PostCommitHook] = field(default_factory=list)
    results: List[dict] = field(default_factory=list)

    def register(self, hook: PostCommitHook):
        self.hooks.append(hook)
        return self  # fluent API

    def execute(self, project_dir: str, chapter_num: int,
                chapter_content: str, state: dict) -> dict:
        """执行全部 Hook，收集结果。任一失败不中断后续。"""
        self.results = []
        for hook in self.hooks:
            result = hook.execute(project_dir, chapter_num, chapter_content, state)
            self.results.append({"hook": hook.name, **result})
            status = "OK" if result.get("applied") else "FAIL"
            blocked = " BLOCKED" if result.get("blocked") else ""
            print(f"  [hook] {hook.name}: {status}{blocked}")
        return self.summary()

    def summary(self) -> dict:
        applied = sum(1 for r in self.results if r.get("applied"))
        blocked = [r for r in self.results if r.get("blocked")]
        return {
            "total": len(self.results),
            "applied": applied,
            "blocked": len(blocked),
            "details": self.results,
        }


# ================================================================
# 默认链
# ================================================================

def default_chain() -> HookChain:
    """生产环境默认 Hook 链。"""
    return (HookChain()
        .register(DBWriteHook())
        .register(ProjectionHook())
        .register(MemoryCommitHook())
        .register(PostCommitGateHook())
        .register(IntelligenceHook())
        .register(KPIUpdateHook()))
