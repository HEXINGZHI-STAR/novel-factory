"""
盘古AI 写作面板 - Gradio版
启动: python pangu_dashboard.py
"""
import sys, io, os, json, re, time, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
BASE = Path(__file__).resolve().parent

import gradio as gr

# ====== 项目扫描 ======
def scan_projects():
    projects = []
    for root in [BASE/"projects", BASE.parent/"webnovel-test"]:
        if not root.exists(): continue
        for child in sorted(root.iterdir()):
            if not child.is_dir(): continue
            for sf in [child/'.webnovel'/'state.json', child/'state.json']:
                if sf.exists():
                    s = json.loads(sf.read_text(encoding='utf-8'))
                    info = s.get('project_info',{})
                    prog = s.get('progress',{})
                    projects.append((
                        info.get('title', child.name),
                        info.get('platform','?'),
                        info.get('genre','?'),
                        f"{prog.get('current_chapter',0)}/{info.get('target_chapters','?')}",
                        prog.get('total_words',0),
                    ))
                    break
    return projects

# ====== 写章 ======
def write_chapter(project_name, chapter_num, task, mode):
    if not project_name: return "❌ 请选择项目", "", ""

    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config; reset_config()
    from pangu_core.pipeline import WritingPipeline, PipelineConfig
    from pangu_workshop_smart import SmartStrategyEngine

    # 查找项目
    for root in [BASE/"projects", BASE.parent/"webnovel-test"]:
        if not root.exists(): continue
        for child in root.iterdir():
            if not child.is_dir(): continue
            for sf in [child/'.webnovel'/'state.json', child/'state.json']:
                if sf.exists():
                    s = json.loads(sf.read_text(encoding='utf-8'))
                    if s.get('project_info',{}).get('title','') == project_name:
                        proj_dir = child
                        state = s
                        break

    if 'proj_dir' not in dir():
        return "❌ 项目未找到", "", ""

    engine = SmartStrategyEngine(proj_dir)
    if not task.strip():
        task = engine.generate_chapter_task(chapter_num)

    use_workshop = "工坊" in mode
    config = (PipelineConfig.from_workshop_mode if use_workshop else PipelineConfig.from_quick_mode)(
        project_dir=str(proj_dir), chapter=int(chapter_num), task=task,
        mode=state.get('project_info',{}).get('genre','general'),
        platform=state.get('project_info',{}).get('platform','qimao'),
    )

    t0 = time.time()
    result = WritingPipeline(config).run()
    elapsed = time.time() - t0

    wc = len(result.chapter_content.replace('\n','').replace(' ',''))
    quotes = re.findall(r'[\"\"\"\"「」]([^\"\"\"\"「」]{2,})[\"\"\"\"「」]', result.chapter_content)

    log = f"✅ 完成！{wc:,}字 | {elapsed:.0f}秒 | {len(quotes)}段对话 | {'成功' if result.success else '部分成功'}"

    if result.success and wc > 500:
        (proj_dir/'正文'/f'第{chapter_num}章.txt').write_text(result.chapter_content, encoding='utf-8')
        log += "\n已自动保存到正文目录"

    return log, result.chapter_content, task

# ====== 审查 ======
def review_chapter(project_name, chapter_num):
    if not project_name: return "❌ 请选择项目", {}

    from pangu_intelligence import analyze_chapter

    for root in [BASE/"projects", BASE.parent/"webnovel-test"]:
        if not root.exists(): continue
        for child in root.iterdir():
            if not child.is_dir(): continue
            for sf in [child/'.webnovel'/'state.json', child/'state.json']:
                if sf.exists():
                    s = json.loads(sf.read_text(encoding='utf-8'))
                    if s.get('project_info',{}).get('title','') == project_name:
                        proj_dir = child
                        state = s
                        break

    content_dir = proj_dir/'正文'
    ch_files = list(content_dir.glob(f'*第{chapter_num}章*')) + list(content_dir.glob(f'*Ch{chapter_num}*'))
    if not ch_files: return f"❌ 第{chapter_num}章不存在", {}

    text = ch_files[0].read_text(encoding='utf-8')
    ci = analyze_chapter(str(proj_dir), int(chapter_num), text, state)
    wc = len(text.replace('\n','').replace(' ',''))
    quotes = re.findall(r'[\"\"\"\"「」]([^\"\"\"\"「」]{2,})[\"\"\"\"「」]', text)

    report = f"""## 审查报告
- **字数**: {wc:,}
- **对话段**: {len(quotes)}
- **AI风险**: {ci.ai_risk_score:.2f}
- **质量后验**: {ci.quality_posterior:.0%}
- **审计**: {ci.audit_opinion}
- **句均**: {ci.sentence_stats.get('mean_len','?')}字 | CV: {ci.sentence_stats.get('cv','?')}
- **节奏质量**: {ci.tension_envelope.get('pacing_quality','?')}
- **建议**: {ci.recommendation}
"""
    return report, {"字数":wc,"对话":len(quotes),"AI风险":ci.ai_risk_score,"质量":f"{ci.quality_posterior:.0%}"}

# ====== 参考库 ======
def top_books():
    try:
        conn = sqlite3.connect(str(BASE/'knowledge'/'novel_reference.db'))
        conn.row_factory = sqlite3.Row
        books = conn.execute(
            "SELECT title, author, genre, priority_score FROM books WHERE priority_score>=100 ORDER BY priority_score DESC LIMIT 15"
        ).fetchall()
        conn.close()
        return [[b['title'][:35], b['author'] or '?', b['genre'] or '?', f"{b['priority_score']:.0f}"] for b in books]
    except:
        return []

# ====== 新建项目 ======
def create_project(title, platform, genre, chapters, selling_points):
    if not title: return "❌ 请输入书名", []
    from datetime import datetime
    proj_dir = BASE/"projects"/title
    proj_dir.mkdir(parents=True, exist_ok=True)
    for d in ["大纲","设定集","正文","审查报告"]: (proj_dir/d).mkdir(exist_ok=True)

    state = {
        "project_info": {
            "title": title, "genre": genre, "platform": platform,
            "target_chapters": int(chapters), "target_words": int(chapters)*3000,
            "core_selling_points": selling_points,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        },
        "progress": {"current_chapter":0, "total_words":0, "current_volume":1},
        "characters": {"protagonist": {"name":"","current_state":"","last_chapter":0}, "key_characters":[]},
        "foreshadowing": {"active_threads":[]},
        "setting_log": {"locked_rules":[]},
        "review_checkpoints":[], "chapter_meta":{},
    }
    (proj_dir/"state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (proj_dir/"大纲"/"总纲.md").write_text(f"# {title} 总纲\n\n## 故事一句话\n\n## 核心主线\n\n## 卷划分\n", encoding='utf-8')
    (proj_dir/"设定集"/"主角卡.md").write_text(f"# 主角卡\n\n- 姓名：\n- 身份：\n- 性格：\n", encoding='utf-8')
    (proj_dir/"设定集"/"世界观.md").write_text(f"# 世界观设定\n\n## 世界一句话\n\n## 核心规则\n", encoding='utf-8')
    return f"✅ 项目「{title}」创建成功！", scan_projects()

# ====== UI ======
with gr.Blocks(title="盘古AI写作面板", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📚 盘古AI 写作面板")

    # 项目选择器
    proj_list = [p[0] for p in scan_projects()]

    with gr.Row():
        project = gr.Dropdown(proj_list, label="📁 项目", value=proj_list[0] if proj_list else None, scale=3)
        chapter = gr.Number(label="章节号", value=1, precision=0, scale=1)
        mode = gr.Radio(["快速 (W0→W2→W4)", "工坊 (W0-W5)"], label="模式", value="工坊 (W0-W5)", scale=2)

    with gr.Tabs():
        with gr.Tab("✍️ 写章"):
            task_input = gr.Textbox(label="章任务 (留空自动生成)", lines=3, placeholder="例如: 沈夜骑马游街，连中三元。太监突传密旨调任镇妖司...")
            write_btn = gr.Button("🚀 开始写章", variant="primary")

            with gr.Row():
                log_output = gr.Textbox(label="执行日志", lines=3, scale=1)

            content_output = gr.Textbox(label="正文", lines=20, scale=1)

            write_btn.click(
                write_chapter,
                [project, chapter, task_input, mode],
                [log_output, content_output, task_input]
            )

        with gr.Tab("🔍 审查"):
            review_ch = gr.Number(label="审查章节号", value=1, precision=0)
            review_btn = gr.Button("🔍 审查", variant="secondary")
            review_report = gr.Markdown()
            review_metrics = gr.JSON(label="指标")
            review_btn.click(review_chapter, [project, review_ch], [review_report, review_metrics])

        with gr.Tab("📚 项目一览"):
            proj_table = gr.Dataframe(
                headers=["书名","平台","题材","进度","字数"],
                value=scan_projects(),
                interactive=False,
            )
            refresh_btn = gr.Button("刷新")
            refresh_btn.click(lambda: scan_projects(), outputs=proj_table)

        with gr.Tab("🧠 知识库"):
            kb_table = gr.Dataframe(
                headers=["书名","作者","题材","优先级"],
                value=top_books(),
                interactive=False,
            )

        with gr.Tab("➕ 新建项目"):
            with gr.Row():
                new_title = gr.Textbox(label="书名", placeholder="输入书名")
                new_platform = gr.Dropdown(["七猫","知乎盐选","起点","番茄","晋江"], label="平台", value="起点")
                new_genre = gr.Dropdown(["悬疑","玄幻","都市","治愈","规则怪谈","科幻","历史","言情"], label="题材", value="悬疑")
            new_chapters = gr.Number(label="目标章节数", value=100, precision=0)
            new_selling = gr.Textbox(label="核心卖点", lines=2, placeholder="一句话说清为什么读者选这本")
            new_btn = gr.Button("创建项目", variant="primary")
            new_log = gr.Textbox(label="结果", lines=2)
            new_btn.click(
                create_project,
                [new_title,new_platform,new_genre,new_chapters,new_selling],
                [new_log, proj_table]
            ).then(
                lambda: gr.Dropdown(choices=[p[0] for p in scan_projects()]),
                outputs=project
            )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8502, share=False)
