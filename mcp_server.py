"""
盘古 MCP Server (Model Context Protocol)

让 Claude Code/VSCode 直接调用盘古 Pipeline、数学引擎和情报中心。

配置方式 (项目根目录 .mcp.json):
{
  "mcpServers": {
    "pangu": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "${workspaceFolder}/盘古AI"
    }
  }
}

暴露的工具:
  - pangu_status         项目概览
  - pangu_diagnose       全维度智能诊断
  - pangu_write          写一章 (调用Pipeline)
  - pangu_review         审查章节
  - pangu_analyze_text   数学分析一段文本
  - pangu_strategy       获取下一章最优策略
  - pangu_task           自动生成章任务
"""

from __future__ import annotations

import sys
import json
import math
from pathlib import Path
from typing import Optional

# 确保盘古在路径中
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# === MCP SDK ===
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("[WARN] mcp not installed. pip install mcp", file=sys.stderr)

# === Pangu imports ===
from pangu_workshop import find_project, load_state, load_outline
from pangu_workshop_smart import SmartStrategyEngine, diagnose_project


def _fmt_pct(val) -> str:
    """安全格式化百分比"""
    try:
        return f"{float(val):.1%}"
    except (TypeError, ValueError):
        return str(val) if val else "N/A"


# ================================================================
# 工具实现
# ================================================================

async def tool_status(project: str = "") -> str:
    """项目概览"""
    if not project:
        # 列出所有项目
        from pangu_workshop import PROJECT_ROOTS
        lines = ["# 盘古项目列表\n"]
        for root in PROJECT_ROOTS:
            if not root.exists():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                state = load_state(child)
                if not state:
                    continue
                info = state.get("project_info", {})
                prog = state.get("progress", {})
                lines.append(
                    f"- **{info.get('title', child.name)}** "
                    f"[{info.get('platform', '?')}] "
                    f"Ch{prog.get('current_chapter', 0)}/{info.get('target_chapters', '?')} "
                    f"{prog.get('total_words', 0)}字"
                )
        return "\n".join(lines) if len(lines) > 1 else "未找到项目"

    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    state = load_state(proj)
    info = state.get("project_info", {})
    prog = state.get("progress", {})

    return f"""## {info.get('title', proj.name)}

| 属性 | 值 |
|------|-----|
| 平台 | {info.get('platform', '?')} |
| 题材 | {info.get('genre', '?')} |
| 进度 | 第{prog.get('current_chapter', 0)}/{info.get('target_chapters', '?')}章 |
| 字数 | {prog.get('total_words', 0)}字 |
| 核心卖点 | {info.get('core_selling_points', '')} |
"""


async def tool_diagnose(project: str) -> str:
    """全维度智能诊断"""
    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    state = load_state(proj)
    info = state.get("project_info", {})
    prog = state.get("progress", {})
    current_ch = prog.get("current_chapter", 0)

    lines = [f"# {info.get('title', proj.name)} 诊断报告\n"]

    # 基础
    lines.append(f"进度: {current_ch}/{info.get('target_chapters', '?')}章 | {prog.get('total_words', 0)}字")

    # 审查最新章
    if current_ch > 0:
        try:
            from pangu_intelligence import analyze_chapter
            ci = analyze_chapter(str(proj), current_ch, state=state)
            lines.append(f"\n## 最新章 Ch{current_ch}")
            lines.append(f"- 字数: {ci.word_count}")
            lines.append(f"- 句均: {ci.sentence_stats.get('mean_len', '?')}字")
            lines.append(f"- AI风险: {ci.ai_risk_score:.2f}")
            lines.append(f"- 质量后验: {_fmt_pct(ci.quality_posterior)}")
            lines.append(f"- 节奏质量: {ci.tension_envelope.get('pacing_quality', '?'):.2f}")
            lines.append(f"- 审计: {ci.audit_opinion}")
            if ci.recommendation:
                lines.append(f"- 建议: {ci.recommendation}")
        except Exception as e:
            lines.append(f"\n审查失败: {e}")

    # 伏笔
    from pangu_math.graph.foreshadow_graph import ForeshadowGraph
    fg = ForeshadowGraph.from_state(state)
    lines.append(f"\n## 伏笔网络")
    lines.append(f"活跃={fg.total_open} 已回收={fg.total_resolved} 健康={fg.health_score():.2f}")
    if fg.expired_threads:
        lines.append(f"[!] 过期: {len(fg.expired_threads)}条")

    # 策略
    engine = SmartStrategyEngine(proj)
    next_ch = current_ch + 1
    strategy = engine.recommend_strategy(next_ch)
    task = engine.generate_chapter_task(next_ch)

    lines.append(f"\n## 下章策略 Ch{next_ch}")
    lines.append(f"- 模式: {strategy.mode} | 字数: {strategy.target_words} | 温度: {strategy.temperature}")
    lines.append(f"- 钩子: {strategy.hook_type}")
    if strategy.release_type:
        lines.append(f"- 释放: {strategy.release_type}")
    if strategy.use_claude_w4:
        lines.append(f"- 💎 Claude精修W4")
    lines.append(f"\n**任务**: {task}")

    return "\n".join(lines)


async def tool_write(project: str, chapter: int, mode: str = "auto",
                      task: str = "") -> str:
    """写一章"""
    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    # 自动策略
    if mode == "auto":
        engine = SmartStrategyEngine(proj)
        strategy = engine.recommend_strategy(chapter)
        mode = strategy.mode
        if not task:
            task = engine.generate_chapter_task(chapter)

    from pangu_workshop import write_chapter
    ok = write_chapter(proj, chapter, mode=mode, chapter_task=task or None,
                        dry_run=False)

    if ok:
        return f"Ch{chapter} 写作完成。运行 pangu_workshop.py review -p \"{project}\" -c {chapter} 查看详情。"
    return f"Ch{chapter} 写作失败。请检查API Key配置和网络连接。"


async def tool_review(project: str, chapter: int) -> str:
    """审查章节"""
    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    from pangu_intelligence import analyze_chapter
    state = load_state(proj)
    ci = analyze_chapter(str(proj), chapter, state=state)

    return f"""## Ch{chapter} 审查报告

| 指标 | 值 |
|------|-----|
| 字数 | {ci.word_count} |
| 句均 | {ci.sentence_stats.get('mean_len', '?')}字 |
| CV | {ci.sentence_stats.get('cv', '?')} |
| TTR | {ci.diversity_stats.get('char_ttr', '?')} |
| 可读性 | {ci.readability_score.get('total', '?')}分 ({ci.readability_score.get('grade', '?')}) |
| AI风险 | {ci.ai_risk_score:.2f} |
| 质量后验 | {_fmt_pct(ci.quality_posterior)} |
| 张力质量 | {ci.tension_envelope.get('pacing_quality', '?'):.2f} |
| 审计 | {ci.audit_opinion} |

**建议**: {ci.recommendation}
**下章**: {ci.next_chapter_advice}
"""


async def tool_analyze_text(text: str) -> str:
    """数学分析一段文本"""
    from pangu_math.stats.distribution import SentenceStats
    from pangu_math.stats.diversity import LexicalDiversity
    from pangu_math.stats.readability import chinese_readability
    from pangu_math.signal.tension_envelope import TensionEnvelope
    from pangu_math.signal.emotion_spectrum import EmotionSpectrum

    sent = SentenceStats.from_text(text)
    ld = LexicalDiversity.from_text(text)
    read = chinese_readability(text)
    te = TensionEnvelope.from_text(text)
    es = EmotionSpectrum.from_text(text)

    return f"""## 文本分析

| 指标 | 值 | 判定 |
|------|-----|------|
| 字数 | {len(text.replace(chr(10),'').replace(' ',''))} | — |
| 句均 | {sent.mean_sentence_length:.1f}字 | {"[!]短" if sent.mean_sentence_length<15 else "[OK]"} |
| 句CV | {sent.cv_sentence_length:.3f} | {"[!]低" if sent.cv_sentence_length<0.25 else "[OK]"} |
| TTR | {ld.char_ttr:.3f} | — |
| MTLD | {ld.mtld:.0f} | — |
| 可读性 | {read.total_score:.0f} ({read.grade}) | — |
| 情绪复杂度 | {es.complexity:.2f} | — |
| 张力峰值 | {te.peak_value:.1f} @ {te.peak_position:.0%} | — |
| AI风险 | {sent.ai_risk_score():.2f} | {"[!]高" if sent.ai_risk_score()>0.5 else "[OK]"} |
"""


async def tool_strategy(project: str, chapter: int = 0) -> str:
    """获取写作策略"""
    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    state = load_state(proj)
    ch = chapter or state.get("progress", {}).get("current_chapter", 0) + 1
    engine = SmartStrategyEngine(proj)
    s = engine.recommend_strategy(ch)

    return f"""## Ch{ch} 推荐策略

| 参数 | 值 |
|------|-----|
| 模式 | {s.mode} |
| 目标字数 | {s.target_words} |
| 温度 | {s.temperature} |
| 钩子类型 | {s.hook_type} |
| 情绪释放 | {s.release_type or '无'} |
| Claude精修 | {'是' if s.use_claude_w4 else '否'} |
| 重点维度 | {', '.join(s.priority_dimensions) if s.priority_dimensions else '无'} |
"""


async def tool_task(project: str, chapter: int = 0) -> str:
    """自动生成章任务"""
    proj = find_project(project)
    if not proj:
        return f"项目 '{project}' 未找到"

    state = load_state(proj)
    ch = chapter or state.get("progress", {}).get("current_chapter", 0) + 1
    engine = SmartStrategyEngine(proj)
    task = engine.generate_chapter_task(ch)

    return f"## Ch{ch} 写作任务\n\n{task}"


# ================================================================
# MCP Server
# ================================================================

TOOLS = {
    "pangu_status":    (tool_status,    "项目概览。不传参数列出所有项目，传project名查看单项目"),
    "pangu_diagnose":  (tool_diagnose,  "全维度智能诊断：审查+伏笔+策略+经济学"),
    "pangu_write":     (tool_write,     "写一章。project=项目名, chapter=章号, mode=auto/quick/workshop, task=章任务"),
    "pangu_review":    (tool_review,    "审查章节并输出情报报告"),
    "pangu_analyze":   (tool_analyze_text, "数学分析一段文本：句法/多样性/可读性/情绪/张力/AI风险"),
    "pangu_strategy":  (tool_strategy,  "获取下一章最优写作策略"),
    "pangu_task":      (tool_task,      "自动生成章任务描述"),
}


async def run_mcp():
    """启动 MCP stdio server"""
    if not HAS_MCP:
        print("[FATAL] pip install mcp", file=sys.stderr)
        sys.exit(1)

    server = Server("pangu")

    for name, (func, desc) in TOOLS.items():
        # 闭包捕获
        async def make_handler(f=func):
            async def handler(**kwargs):
                result = await f(**kwargs)
                return [TextContent(type="text", text=str(result))]
            return handler

        server.add_tool(
            Tool(name=name, description=desc, inputSchema={
                "type": "object",
                "properties": _get_params(func),
            }),
            await make_handler(),
        )

    async with stdio_server() as (read, write):
        await server.run(read, write)


def _get_params(func) -> dict:
    """从函数签名提取参数schema"""
    import inspect
    sig = inspect.signature(func)
    props = {}
    for name, param in sig.parameters.items():
        if param.annotation == str:
            props[name] = {"type": "string", "description": name}
        elif param.annotation == int:
            props[name] = {"type": "integer", "description": name}
        else:
            props[name] = {"type": "string", "description": name}
    return props


# ================================================================
# 直接调用模式 (不用MCP时)
# ================================================================

async def direct_call(tool_name: str, **kwargs):
    """不启动MCP服务器，直接调用工具"""
    func, _ = TOOLS[tool_name]
    return await func(**kwargs)


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) > 1:
        # 直接调用模式
        tool = sys.argv[1]
        kwargs = {}
        for arg in sys.argv[2:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                kwargs[k] = int(v) if v.isdigit() else v

        result = asyncio.run(direct_call(tool, **kwargs))
        print(result)
    else:
        # MCP Server 模式
        asyncio.run(run_mcp())
