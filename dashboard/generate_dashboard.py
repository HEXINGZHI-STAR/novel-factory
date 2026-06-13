#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - Dashboard 数据生成器

自动从项目数据生成可视化面板：
  1. 读取 projects/{name}/state.json
  2. 读取 .story-system/ 合同数据
  3. 读取 memory_scratchpad.json 记忆数据
  4. 读取 RAG 引擎统计
  5. 生成嵌入式HTML Dashboard
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


def load_json_safe(path: Path) -> Dict:
    """安全加载JSON文件"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def collect_project_data(project_name: str) -> Dict[str, Any]:
    """收集项目全部数据"""
    project_dir = BASE_DIR / "projects" / project_name
    data = {
        "project_name": project_name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state": {},
        "contracts": {},
        "memory": {},
        "rag_stats": {},
        "gates_stats": {},
    }

    # 1. 项目状态
    state = load_json_safe(project_dir / "state.json")
    data["state"] = state

    # 2. Story System 合同数据
    story_system_dir = project_dir / ".story-system"
    if story_system_dir.exists():
        master_setting = load_json_safe(story_system_dir / "MASTER_SETTING.json")
        data["contracts"]["master_setting"] = master_setting

        # 章节合同
        chapters_dir = story_system_dir / "chapters"
        if chapters_dir.exists():
            chapter_contracts = []
            for cf in sorted(chapters_dir.glob("chapter_*.json")):
                contract = load_json_safe(cf)
                if contract:
                    chapter_contracts.append(contract)
            data["contracts"]["chapters"] = chapter_contracts
            data["contracts"]["total_chapters"] = len(chapter_contracts)

    # 3. 记忆数据
    memory_file = project_dir / "memory_scratchpad.json"
    if memory_file.exists():
        memory_data = load_json_safe(memory_file)
        data["memory"] = memory_data
        # 计算记忆层统计
        items = memory_data.get("items", [])
        layer_counts = {"working": 0, "episodic": 0, "semantic": 0}
        for item in items:
            layer = item.get("layer", "working")
            if layer in layer_counts:
                layer_counts[layer] += 1
        data["memory"]["layer_counts"] = layer_counts
        data["memory"]["total_items"] = len(items)

    # 4. RAG 统计
    try:
        sys.path.insert(0, str(BASE_DIR / "backend"))
        from rag_engine import get_rag
        rag = get_rag(project_name)
        data["rag_stats"] = rag.get_stats()
    except Exception as e:
        data["rag_stats"] = {"error": str(e)}

    # 5. Write Gates 统计（从日志或.meta文件读取）
    gates_dir = project_dir / ".gates"
    if gates_dir.exists():
        gate_reports = []
        for gf in sorted(gates_dir.glob("*.json")):
            report = load_json_safe(gf)
            if report:
                gate_reports.append(report)
        data["gates_stats"]["reports"] = gate_reports
        data["gates_stats"]["total"] = len(gate_reports)

    return data


def generate_dashboard(data: Dict[str, Any], output_path: Path) -> None:
    """生成嵌入式HTML Dashboard"""

    state = data.get("state", {})
    project_info = state.get("project_info", {})
    characters = state.get("characters", {})
    foreshadowing = state.get("foreshadowing", {})
    setting_log = state.get("setting_log", {})
    setting_log_count = len(setting_log) if isinstance(setting_log, (list, dict)) else 0
    chapter_meta = state.get("chapter_meta", {})
    progress = state.get("progress", {})

    total_chapters = progress.get("current_chapter", 0)
    total_words = progress.get("total_words", 0)
    avg_words = round(total_words / total_chapters) if total_chapters > 0 else 0

    # Write Gates统计
    gates_stats = data.get("gates_stats", {})
    gates_total = gates_stats.get("total", 0)

    # 合同统计
    contracts = data.get("contracts", {})
    contract_chapters = contracts.get("total_chapters", 0)
    has_master_setting = bool(contracts.get("master_setting"))
    master_setting_badge = "success" if has_master_setting else "warning"
    master_setting_text = "已构建" if has_master_setting else "未构建"

    # 记忆统计
    memory = data.get("memory", {})
    layer_counts = memory.get("layer_counts", {"working": 0, "episodic": 0, "semantic": 0})
    memory_total = memory.get("total_items", 0)

    # RAG统计
    rag_stats = data.get("rag_stats", {})
    has_semantic = bool(rag_stats.get("semantic_available"))
    semantic_badge = "success" if has_semantic else "danger"
    semantic_text = "是" if has_semantic else "否"

    # 伏笔统计
    if isinstance(foreshadowing, list):
        foreshadowing_items = foreshadowing
    elif isinstance(foreshadowing, dict):
        foreshadowing_items = list(foreshadowing.values())
    else:
        foreshadowing_items = []
    foreshadowing_planted = sum(1 for v in foreshadowing_items if isinstance(v, dict) and v.get("status") == "planted")
    foreshadowing_paid = sum(1 for v in foreshadowing_items if isinstance(v, dict) and v.get("status") == "paid_off")
    foreshadowing_total = len(foreshadowing_items)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>盘古AI Dashboard - {data['project_name']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 20px;
            color: #e0e0e0;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }}
        .header h1 {{ color: #00d2ff; font-size: 28px; margin-bottom: 5px; }}
        .header p {{ color: #8892b0; font-size: 13px; }}
        .header .timestamp {{ color: #64ffda; font-size: 12px; margin-top: 8px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 25px; }}
        .card {{
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            padding: 25px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card h2 {{ color: #00d2ff; font-size: 16px; margin-bottom: 18px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .metric {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #8892b0; font-size: 13px; }}
        .metric-value {{ font-size: 22px; font-weight: 700; color: #e6f1ff; }}
        .metric-value.success {{ color: #64ffda; }}
        .metric-value.warning {{ color: #ffd166; }}
        .metric-value.danger {{ color: #ff6b6b; }}
        .badge {{
            display: inline-block; padding: 4px 10px; border-radius: 12px;
            font-size: 11px; font-weight: 600;
        }}
        .badge.success {{ background: rgba(100,255,218,0.15); color: #64ffda; }}
        .badge.warning {{ background: rgba(255,209,102,0.15); color: #ffd166; }}
        .badge.danger {{ background: rgba(255,107,107,0.15); color: #ff6b6b; }}
        .progress-bar {{ width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; margin-top: 8px; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #00d2ff, #64ffda); border-radius: 3px; transition: width 0.3s; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th {{ text-align: left; padding: 8px; background: rgba(255,255,255,0.03); color: #8892b0; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; color: #ccd6f6; }}
        .section-title {{ color: #ccd6f6; font-size: 20px; font-weight: 700; margin: 30px 0 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>盘古AI Dashboard</h1>
            <p>项目: {data['project_name']} | 模式: {project_info.get('mode', '?')} | 平台: {project_info.get('platform', '?')}</p>
            <p class="timestamp">生成时间: {data['generated_at']}</p>
        </div>

        <div class="section-title">核心指标</div>
        <div class="grid">
            <div class="card">
                <h2>进度统计</h2>
                <div class="metric">
                    <span class="metric-label">已完成章节</span>
                    <span class="metric-value">{total_chapters}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">总字数</span>
                    <span class="metric-value">{total_words:,}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">章均字数</span>
                    <span class="metric-value">{avg_words}</span>
                </div>
            </div>

            <div class="card">
                <h2>Write Gates</h2>
                <div class="metric">
                    <span class="metric-label">检测报告数</span>
                    <span class="metric-value">{gates_total}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">三层关卡</span>
                    <span class="metric-value">prewrite/precommit/postcommit</span>
                </div>
            </div>

            <div class="card">
                <h2>Story System</h2>
                <div class="metric">
                    <span class="metric-label">合同章节数</span>
                    <span class="metric-value">{contract_chapters}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">MASTER_SETTING</span>
                    <span class="badge {master_setting_badge}">{master_setting_text}</span>
                </div>
            </div>

            <div class="card">
                <h2>长期记忆</h2>
                <div class="metric">
                    <span class="metric-label">Working</span>
                    <span class="metric-value success">{layer_counts.get('working', 0)}</span>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: {min(layer_counts.get('working', 0) / max(memory_total, 1) * 100, 100):.0f}%"></div></div>
                <div class="metric">
                    <span class="metric-label">Episodic</span>
                    <span class="metric-value warning">{layer_counts.get('episodic', 0)}</span>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: {min(layer_counts.get('episodic', 0) / max(memory_total, 1) * 100, 100):.0f}%"></div></div>
                <div class="metric">
                    <span class="metric-label">Semantic</span>
                    <span class="metric-value" style="color:#a78bfa">{layer_counts.get('semantic', 0)}</span>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: {min(layer_counts.get('semantic', 0) / max(memory_total, 1) * 100, 100):.0f}%"></div></div>
            </div>

            <div class="card">
                <h2>RAG检索</h2>
                <div class="metric">
                    <span class="metric-label">检索模式</span>
                    <span class="metric-value" style="font-size:14px">{rag_stats.get('search_mode', 'N/A')}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">知识库文档数</span>
                    <span class="metric-value">{rag_stats.get('total_documents', 0)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">语义索引可用</span>
                    <span class="badge {semantic_badge}">{semantic_text}</span>
                </div>
            </div>

            <div class="card">
                <h2>伏笔追踪</h2>
                <div class="metric">
                    <span class="metric-label">总伏笔数</span>
                    <span class="metric-value">{foreshadowing_total}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">已埋设</span>
                    <span class="metric-value warning">{foreshadowing_planted}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">已回收</span>
                    <span class="metric-value success">{foreshadowing_paid}</span>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: {(foreshadowing_paid / max(foreshadowing_total, 1) * 100):.0f}%"></div></div>
            </div>
        </div>

        <div class="section-title">人物图谱</div>
        <div class="card">
            <h2>核心人物 ({len(characters)})</h2>
            <table>
                <thead><tr><th>姓名</th><th>角色</th><th>执念</th><th>底线</th></tr></thead>
                <tbody>
                    {"".join(f'<tr><td>{name}</td><td>{v.get("role","?")}</td><td>{str(v.get("obsession",""))[:20]}</td><td>{str(v.get("bottom_line",""))[:20]}</td></tr>' for name, v in list(characters.items())[:10])}
                </tbody>
            </table>
        </div>

        <div class="section-title">系统架构</div>
        <div class="card">
            <h2>Prompt注入链路 (11层)</h2>
            <table>
                <thead><tr><th>层级</th><th>名称</th><th>状态</th></tr></thead>
                <tbody>
                    <tr><td>L1</td><td>核心人设</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L2</td><td>模式数据</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L3</td><td>题材模板</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L4</td><td>情绪锚点</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L5</td><td>RAG知识检索</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L6</td><td>Lorebook</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L7</td><td>伏笔提醒</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L8</td><td>De-AI规则</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L9</td><td>模式深度注入</td><td><span class="badge success">已注入</span></td></tr>
                    <tr><td>L10</td><td>Story Contract</td><td><span class="badge success">新增</span></td></tr>
                    <tr><td>L11</td><td>Memory Pack</td><td><span class="badge success">新增</span></td></tr>
                </tbody>
            </table>
        </div>

        <div style="text-align:center; padding:30px; color:#8892b0; font-size:12px;">
            盘古AI写作系统 | webnovel-writer合并执行 | {data['generated_at']}
        </div>
    </div>
</body>
</html>"""

    output_path.write_text(html, encoding='utf-8')
    print(f"[Dashboard] 生成完成: {output_path}")


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="盘古AI Dashboard生成器")
    parser.add_argument("project_name", help="项目名称（如：深渊猎人）")
    parser.add_argument("--output", "-o", help="输出路径（默认：dashboard/{project_name}.html）")
    args = parser.parse_args()

    print(f"[Dashboard] 正在收集项目数据: {args.project_name}")
    data = collect_project_data(args.project_name)

    output_path = Path(args.output) if args.output else BASE_DIR / "dashboard" / f"{args.project_name}.html"
    output_path.parent.mkdir(exist_ok=True)

    generate_dashboard(data, output_path)
    print(f"[Dashboard] 打开浏览器查看: {output_path}")


if __name__ == "__main__":
    main()
