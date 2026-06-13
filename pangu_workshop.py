#!/usr/bin/env python3
"""
盘古工作室 (Pangu Workshop)

不需要HTTP服务器——直接调pangu_core Pipeline。
一个人、一台电脑、一个项目、一批章节。

用法:
    # 写一章
    python pangu_workshop.py write --project "消失的第四个人" --chapter 2

    # 批量写 3 章
    python pangu_workshop.py batch --project "消失的第四个人" --from 2 --to 4

    # 快速模式 (跳过W1/W3/W5)
    python pangu_workshop.py write --project "消失的第四个人" --chapter 2 --fast

    # 工坊模式 (全W0-W5)
    python pangu_workshop.py write --project "消失的第四个人" --chapter 2 --workshop

    # 审查已写的章
    python pangu_workshop.py review --project "消失的第四个人" --chapter 1

    # 项目状态
    python pangu_workshop.py status --project "消失的第四个人"

    # 列出所有项目
    python pangu_workshop.py projects
"""

from __future__ import annotations

import sys, os, io
# 强制UTF-8: 修复Windows GBK乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') if hasattr(sys.stdout, 'buffer') else sys.stdout
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8') if hasattr(sys.stderr, 'buffer') else sys.stderr
os.environ['PYTHONIOENCODING'] = 'utf-8'

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


# ================================================================
# 环境设置
# ================================================================

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 项目搜索路径
PROJECT_ROOTS = [
    BASE_DIR / "projects",
    BASE_DIR.parent / "webnovel-test",
]

# 章节任务模板 (当章纲不存在时使用)
DEFAULT_TASKS: Dict[int, str] = {}


def find_project(name: str) -> Optional[Path]:
    """在所有项目根目录中搜索项目 (目录名或state.json标题匹配)"""
    for root in PROJECT_ROOTS:
        proj = root / name
        if proj.exists():
            return proj
    # 模糊搜索: 目录名 + state.json标题
    name_lower = name.lower()
    for root in PROJECT_ROOTS:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            # 目录名匹配
            if name_lower in child.name.lower():
                return child
            # state.json标题匹配
            state = load_state(child)
            if state:
                title = state.get("project_info", {}).get("title", "")
                if name_lower in title.lower():
                    return child
    return None


def load_outline(project_dir: Path) -> dict:
    """加载总纲，提取章任务"""
    outline_file = project_dir / "大纲" / "总纲.md"
    tasks = {}
    if outline_file.exists():
        content = outline_file.read_text(encoding="utf-8")
        # 简单提取: 找"第N章"行
        import re
        for line in content.split('\n'):
            m = re.match(r'.*第(\d+)章[：:]\s*(.+)', line)
            if m:
                tasks[int(m.group(1))] = m.group(2)
    return tasks


def load_state(project_dir: Path) -> dict:
    """加载项目状态"""
    for state_file in [
        project_dir / ".webnovel" / "state.json",
        project_dir / "state.json",
    ]:
        if state_file.exists():
            return json.loads(state_file.read_text(encoding="utf-8"))
    return {}


def _start_banner():
    """盘古启动自检面板"""
    import requests, sqlite3
    from pangu_math.accelerated import HAS_NUMPY

    print()
    print('╔══════════════════════════════════════════════════════╗')
    print('║          盘 古 AI 写 作 系 统  v2.0                   ║')
    print('║          P A N G U   S T U D I O                     ║')
    print('╚══════════════════════════════════════════════════════╝')
    print()

    from dotenv import load_dotenv; load_dotenv(override=True)
    from pangu_core.config import reset_config, get_config; reset_config()
    cfg = get_config()
    print(f'  [1/6] 配置引擎 ................ OK ({cfg.model})')

    try:
        r = requests.post(f'{cfg.base_url}/chat/completions',
            headers={'Authorization': f'Bearer {cfg.api_key}', 'Content-Type': 'application/json'},
            json={'model': cfg.model, 'messages': [{'role':'user','content':'OK'}], 'max_tokens':5}, timeout=10)
        if r.status_code == 200: print('  [2/6] API连接 ................. OK')
        elif r.status_code == 401: print('  [2/6] API连接 ................. KEY无效')
        else: print(f'  [2/6] API连接 ................. OK (status={r.status_code})')
    except Exception as e:
        print(f'  [2/6] API连接 ................. 网络异常')

    print('  [3/6] Pipeline引擎 ............. OK (W0-W5 五车间)')
    numpy_status = 'YES' if HAS_NUMPY else 'fallback'
    print(f'  [4/6] 数学引擎 ................. OK (numpy={numpy_status})')

    db_path = BASE_DIR / 'knowledge' / 'novel_reference.db'
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        n = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
        p0 = conn.execute('SELECT COUNT(*) FROM books WHERE priority_score>=100').fetchone()[0]
        conn.close()
        print(f'  [5/6] 参考库 ................... OK ({n}本, {p0}P0)')

    proj_count = sum(1 for root in PROJECT_ROOTS if root.exists()
        for d in root.iterdir() if d.is_dir() and ((d/'.webnovel'/'state.json').exists() or (d/'state.json').exists()))
    print(f'  [6/6] 项目 ..................... OK ({proj_count}个)')
    print()
    print('  ╔════════════════════════════════╗')
    print('  ║  盘古已就绪，可以开始写作。     ║')
    print('  ╚════════════════════════════════╝')
    print()



def _validate_project(proj_dir):
    """写前预检——校验项目完整性"""
    from pangu_core.state_validator import validate_state
    import json
    
    print(f'\\n项目预检: {proj_dir.name}')
    issues = 0
    
    # 1. state.json
    state_path = proj_dir / "state.json"
    webnovel_path = proj_dir / ".webnovel" / "state.json"
    if state_path.exists() or webnovel_path.exists():
        sp = state_path if state_path.exists() else webnovel_path
        try:
            raw = json.loads(sp.read_text(encoding='utf-8'))
            state = validate_state(raw)
            print(f'  [OK] state.json (已校验)')
            print(f'       主角: {state["characters"]["protagonist"].get("name", "?")}')
            print(f'       伏笔: {len(state["foreshadowing"]["active_threads"])}条')
            print(f'       设定: {len(state["setting_log"]["locked_rules"])}条')
        except Exception as e:
            print(f'  [FAIL] state.json: {e}')
            issues += 1
    else:
        print(f'  [FAIL] state.json 不存在')
        issues += 1
    
    # 2. 大纲
    outline = proj_dir / "大纲" / "总纲.md"
    if outline.exists():
        size = outline.stat().st_size
        print(f'  [OK] 总纲.md ({size}B)')
    else:
        print(f'  [WARN] 总纲.md 不存在')
    
    # 3. 设定
    for f in ['主角卡.md', '世界观.md']:
        fp = proj_dir / '设定集' / f
        if fp.exists():
            print(f'  [OK] {f} ({fp.stat().st_size}B)')
        else:
            print(f'  [WARN] {f} 不存在')
    
    # 4. 正文
    content_dir = proj_dir / '正文'
    if content_dir.exists():
        chapters = list(content_dir.glob('*.txt'))
        print(f'  [OK] 正文 ({len(chapters)}章)')
    else:
        print(f'  [WARN] 正文目录不存在')
    
    # 5. API
    from pangu_core.config import get_config
    cfg = get_config()
    if cfg.api_key:
        print(f'  [OK] API Key ({cfg.model})')
    else:
        print(f'  [FAIL] API Key 未配置')
        issues += 1
    
    verdict = '通过' if issues == 0 else f'{issues}个问题'
    print(f'\\n  预检: {verdict}')


def _write_article(topic, angle, article_type, words):
    """写公众号文章"""
    from pangu_core.article_pipeline import ArticlePipeline, ArticleConfig
    sep = '=' * 50
    print('\n' + sep)
    print('  盘古文章模式 | ' + article_type)
    print('  选题: ' + topic)
    print('  角度: ' + angle)
    print(sep + '\n')
    config = ArticleConfig(topic=topic, angle=angle, article_type=article_type, target_words=words)
    result = ArticlePipeline(config).run()
    print('\n字数: ' + str(result.words) + ' | 金句: ' + str(result.golden_sentences) + ' | 素材: ' + str(result.material_usage))
    print('说服力: ' + str(round(result.persuasion_score, 2)))
    if result.content:
        from pathlib import Path
        Path('projects/文章测试/正文').mkdir(parents=True, exist_ok=True)
        fname = topic[:10] + '.txt'
        Path('projects/文章测试/正文/' + fname).write_text(result.content, encoding='utf-8')
        print('已保存: ' + fname)
        print('\n' + result.content[:400] + '...')

def _check_api_key():
    """预检 API Key 是否有效"""
    from pangu_core.config import get_config
    cfg = get_config()
    if not cfg.api_key:
        print("[ERROR] 未配置 DEEPSEEK_API_KEY！请在 .env 中设置")
        print("  获取地址: https://platform.deepseek.com/")
        sys.exit(1)

    # 快速连通性检查
    try:
        import requests
        r = requests.post(
            f"{cfg.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
            json={"model": cfg.model, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 5},
            timeout=10)
        if r.status_code == 200:
            print(f"  [API] Key valid ({cfg.model})")
        elif r.status_code == 401:
            print(f"[ERROR] API Key 无效 (401)！请更新 .env 中的 DEEPSEEK_API_KEY")
            sys.exit(1)
        else:
            print(f"  [API] Status {r.status_code}, 继续尝试...")
    except Exception as e:
        print(f"  [API] 连通性检查失败: {e}，继续尝试...")


# ================================================================
# 核心操作
# ================================================================

def write_chapter(project_dir: Path, chapter_num: int,
                   mode: str = "quick", chapter_task: str = None,
                   dry_run: bool = False) -> bool:
    """
    写一章。

    Args:
        project_dir: 项目目录
        chapter_num: 章号
        mode: "quick" (W0→W2→W4) 或 "workshop" (W0→W1→W2→W3→W4→W5)
        chapter_task: 章任务 (None则从总纲提取)
        dry_run: 仅显示配置，不执行

    Returns: 成功与否
    """
    from pangu_core.pipeline import WritingPipeline, PipelineConfig

    # 获取章任务 (自动注入平台对话率要求)
    if chapter_task is None:
        tasks = load_outline(project_dir)
        chapter_task = tasks.get(chapter_num, f"第{chapter_num}章正文")
    # 确保章任务包含平台对话率要求
    dia_keywords = ['对话≥','对话占比≥','对话率≥','对话≥','dialiogue']
    if not any(kw in chapter_task for kw in dia_keywords):
        from pangu_workshop_smart import SmartStrategyEngine
        pre = SmartStrategyEngine(project_dir).pre_write_platform_check(chapter_num)
        dia_pct = pre['platform_requires']['dia_pct']
        chapter_task += f'【平台要求:对话≥{dia_pct:.0%}】'

    # 获取模式
    state = load_state(project_dir)
    genre = state.get("project_info", {}).get("genre", "general")
    platform = state.get("project_info", {}).get("platform", "qimao")

    # 写前策略分析
    from pangu_workshop_smart import SmartStrategyEngine
    engine = SmartStrategyEngine(project_dir)
    pre_check = engine.pre_write_platform_check(chapter_num)

    print(f"\n{'='*60}")
    print(f"  盘古工作室 | {project_dir.name} | 第{chapter_num}章")
    print(f"  模式: {mode} | 题材: {genre} | 平台: {platform}")
    print(f"  {'─'*50}")
    print(f"  [写前策略] {pre_check['advice']}")
    if pre_check['trend_opportunity'] < 30:
        print(f"  [!] 当前题材机会偏低({pre_check['trend_opportunity']}/100)，建议关注: {pre_check['recommended_genre']}")
    print(f"  [平台要求] 对话≥{pre_check['platform_requires']['dia_pct']:.0%} | ≥{pre_check['platform_requires']['words_min']}字 | {pre_check['platform_requires']['hook_type']}")
    print(f"  [策略参数] T={pre_check['strategy']['temperature']} | 钩子={pre_check['strategy']['hook']} | W4={pre_check['w4_mode']}")
    print(f"{'='*60}")

    if dry_run:
        print("  [DRY RUN] 配置验证通过，未执行生成")
        return True

    # 构建配置
    if mode == "quick":
        config = PipelineConfig.from_quick_mode(
            project_dir=str(project_dir),
            chapter=chapter_num,
            task=chapter_task,
            mode=genre,
            platform=platform,
        )
    else:
        config = PipelineConfig.from_workshop_mode(
            project_dir=str(project_dir),
            chapter=chapter_num,
            task=chapter_task,
            mode=genre,
            platform=platform,
        )

    # 执行
    t0 = time.time()
    pipeline = WritingPipeline(config)
    result = pipeline.run()

    elapsed = time.time() - t0
    words = len(result.chapter_content.replace('\n', '').replace(' ', ''))

    print(f"\n  {'='*60}")
    print(f"  结果: {'成功' if result.success else '部分成功'}")
    print(f"  字数: {words} | 耗时: {elapsed:.0f}s")
    if result.warnings:
        print(f"  警告: {len(result.warnings)}个")
    if result.errors:
        print(f"  错误: {len(result.errors)}个")
    print(f"  {'='*60}")

    # PID自调节: 质量不够 → 自动调参重试
    if result.success and words > 500:
        from pangu_math.stats.distribution import SentenceStats
        from pangu_math.probability.guard import GuardEvaluator
        sent = SentenceStats.from_text(result.chapter_content)
        guard = GuardEvaluator().evaluate(result.chapter_content)
        # GUARD < 0.4 或 AI > 0.6 → 自动重试
        if guard['quality_score'] < 0.35 or sent.ai_risk_score() > 0.6:
            print(f"\n  [!] 质量偏低(GUARD={guard['quality_score']:.2f} AI={sent.ai_risk_score():.2f}) → PID自动重试")
            from pangu_core.pid_controller import PipelineSelfTuner
            tuner = PipelineSelfTuner()
            metrics = {'dialogue_ratio': sent.short_sentence_ratio, 'mean_len': sent.mean_sentence_length, 'ai_risk': sent.ai_risk_score()}
            adj = tuner.tune(metrics)
            print(f"  [PID] 自动调整: {adj}")
            # 用调整后的参数重写
            if mode == "quick":
                config2 = PipelineConfig.from_quick_mode(project_dir=str(project_dir), chapter=chapter_num, task=chapter_task + '【对话优先·短段·快节奏】', mode=genre, platform=platform)
            else:
                config2 = PipelineConfig.from_workshop_mode(project_dir=str(project_dir), chapter=chapter_num, task=chapter_task + '【对话优先·短段·快节奏】', mode=genre, platform=platform)
            result2 = WritingPipeline(config2).run()
            w2 = len(result2.chapter_content.replace('\n','').replace(' ',''))
            if w2 > words:
                result = result2
                words = w2
                print(f"  [PID] 重写完成: {words}字")

    return result.success


def batch_write(project_dir: Path, from_ch: int, to_ch: int,
                 mode: str = "quick", delay: float = 2.0) -> dict:
    """
    批量写多章。

    Args:
        delay: 每章之间的间隔秒数 (避免API限流)
    """
    results = {"success": 0, "failed": 0, "chapters": []}

    for ch in range(from_ch, to_ch + 1):
        ok = write_chapter(project_dir, ch, mode=mode)
        results["chapters"].append({"chapter": ch, "success": ok})
        if ok:
            results["success"] += 1
        else:
            results["failed"] += 1

        if ch < to_ch:
            print(f"\n  ⏳ 等待 {delay}s (避免API限流)...")
            time.sleep(delay)

    print(f"\n{'='*60}")
    print(f"  批量完成: {results['success']}/{results['failed'] + results['success']} 成功")
    print(f"{'='*60}")
    return results


def review_chapter(project_dir: Path, chapter_num: int) -> dict:
    """审查已写章节，输出完整情报"""
    from pangu_intelligence import analyze_chapter

    state = load_state(project_dir)
    ci = analyze_chapter(str(project_dir), chapter_num, state=state)

    print(f"\n{'='*60}")
    print(f"  审查: {project_dir.name} 第{chapter_num}章")
    print(f"{'='*60}")
    print(f"  字数: {ci.word_count}")
    print(f"  句均: {ci.sentence_stats.get('mean_len', '?')}字")
    print(f"  CV:   {ci.sentence_stats.get('cv', '?')}")
    print(f"  TTR:  {ci.diversity_stats.get('char_ttr', '?')}")
    print(f"  可读性: {ci.readability_score.get('total', '?')}分 ({ci.readability_score.get('grade', '?')})")
    print(f"  情绪复杂度: {ci.emotion_spectrum.get('complexity', '?')}")
    print(f"  张力峰值: {ci.tension_envelope.get('peak_value', '?')} @ {ci.tension_envelope.get('peak_position', '?')}")
    print(f"  角色中心: {ci.character_network.get('most_central', '?')}")
    print(f"  伏笔健康: {ci.foreshadow_health.get('health_score', '?')}")
    print(f"  AI风险: {ci.ai_risk_score:.2f}")
    print(f"  质量后验: {ci.quality_posterior:.1%}")
    print(f"  审计意见: {ci.audit_opinion}")
    print(f"  建议: {ci.recommendation}")
    if ci.next_chapter_advice:
        print(f"  下章: {ci.next_chapter_advice}")

    return ci.to_dict()


def project_status(project_dir: Path):
    """显示项目状态"""
    state = load_state(project_dir)
    info = state.get("project_info", {})
    progress = state.get("progress", {})

    print(f"\n{'='*60}")
    print(f"  {info.get('title', project_dir.name)}")
    print(f"{'='*60}")
    print(f"  平台: {info.get('platform', '?')} | 题材: {info.get('genre', '?')}")
    print(f"  目标: {info.get('target_words', '?')}字 / {info.get('target_chapters', '?')}章")
    print(f"  进度: 第{progress.get('current_chapter', 0)}章 / {info.get('target_chapters', '?')}章")
    print(f"  已写: {progress.get('total_words', 0)}字")

    # 正文目录
    content_dir = project_dir / "正文"
    if content_dir.exists():
        chapters = sorted(content_dir.glob("第*章*"))
        print(f"  已存档: {len(chapters)}章")
        for ch_file in chapters[-5:]:
            size = ch_file.stat().st_size
            print(f"    {ch_file.name} ({size:,}B)")

    # 审查记录
    checkpoints = state.get("review_checkpoints", [])
    if checkpoints:
        scores = [cp.get("score", 0) for cp in checkpoints]
        print(f"  审查记录: {len(checkpoints)}次 | 均分: {sum(scores)/len(scores):.0f}")

    # 伏笔状态
    foreshadow = state.get("foreshadowing", {}).get("active_threads", [])
    if foreshadow:
        open_count = sum(1 for t in foreshadow if t.get("status") == "open")
        print(f"  伏笔: {len(foreshadow)}条 | 活跃: {open_count}")


def list_projects():
    """列出所有可用项目"""
    print(f"\n{'='*60}")
    print(f"  盘古工作室 — 项目列表")
    print(f"{'='*60}")

    found = 0
    for root in PROJECT_ROOTS:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            state_file = (
                child / ".webnovel" / "state.json" if (child / ".webnovel").exists()
                else child / "state.json"
            )
            if state_file.exists():
                try:
                    s = json.loads(state_file.read_text(encoding="utf-8"))
                    info = s.get("project_info", {})
                    prog = s.get("progress", {})
                    print(f"  [{info.get('platform', '?')}] {info.get('title', child.name)}")
                    print(f"    进度: Ch{prog.get('current_chapter', 0)}/{info.get('target_chapters', '?')} | {prog.get('total_words', 0)}字")
                    found += 1
                except Exception:
                    pass

    if not found:
        print("  未找到项目。在 projects/ 或 webnovel-test/ 下创建项目目录。")


# ================================================================
# CLI
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="盘古工作室 — 一个人、一台电脑、一批章节",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pangu_workshop.py projects
  python pangu_workshop.py status --project "消失的第四个人"
  python pangu_workshop.py write --project "消失的第四个人" --chapter 2
  python pangu_workshop.py batch --project "消失的第四个人" --from 2 --to 5
  python pangu_workshop.py review --project "消失的第四个人" --chapter 1
        """,
    )

    sub = parser.add_subparsers(dest="command", help="操作")

    # write
    p_write = sub.add_parser("write", help="写一章")
    p_write.add_argument("--project", "-p", required=True, help="项目名")
    p_write.add_argument("--chapter", "-c", type=int, required=True, help="章号")
    p_write.add_argument("--task", "-t", help="章任务 (默认从总纲读取)")
    p_write.add_argument("--fast", action="store_true", help="快速模式 (W0→W2→W4, 跳过W1/W3/W5)")
    p_write.add_argument("--workshop", action="store_true", default=True, help="工坊模式 (W0→W1→W2→W3→W4→W5, 默认)")
    p_write.add_argument("--dry-run", action="store_true", help="仅验证配置，不调用AI")

    # batch
    p_batch = sub.add_parser("batch", help="批量写多章")
    p_batch.add_argument("--project", "-p", required=True, help="项目名")
    p_batch.add_argument("--from", dest="from_ch", type=int, required=True, help="起始章")
    p_batch.add_argument("--to", dest="to_ch", type=int, required=True, help="结束章")
    p_batch.add_argument("--fast", action="store_true", help="快速模式")
    p_batch.add_argument("--workshop", action="store_true", default=True, help="工坊模式 (默认)")
    p_batch.add_argument("--delay", type=float, default=3.0, help="章间间隔秒数")

    # review
    p_review = sub.add_parser("review", help="审查章节")
    p_review.add_argument("--project", "-p", required=True, help="项目名")
    p_review.add_argument("--chapter", "-c", type=int, required=True, help="章号")

    # status
    p_status = sub.add_parser("status", help="项目状态")
    p_status.add_argument("--project", "-p", required=True, help="项目名")

    # projects
    sub.add_parser("projects", help="列出所有项目")

    # start
    sub.add_parser("start", help="启动盘古 — 系统自检面板")

    # validate
    p_val = sub.add_parser("validate", help="写前预检 — 检查项目完整性"); p_val.add_argument("--project", "-p", required=True, help="项目名")

    # article
    p_article = sub.add_parser("article", help="写文章 — 公众号情感/观点/热点文")
    p_article.add_argument("--topic", "-t", required=True, help="选题")
    p_article.add_argument("--angle", "-a", required=True, help="角度")
    p_article.add_argument("--type", choices=["情感文","观点文","热点文"], default="情感文", help="文章类型")
    p_article.add_argument("--words", type=int, default=1500, help="目标字数")

    # start
    sub.add_parser("start", help="启动盘古 — 系统自检 + 状态面板")


    args = parser.parse_args()

    
    if args.command == "start":
        _start_banner()
        return

    if args.command == "validate":
        proj_dir = find_project(args.project)
        if not proj_dir:
            print(f"[ERROR] 项目 '{args.project}' 未找到")
            return
        _validate_project(proj_dir)
        return

    if args.command == "projects":
        list_projects()
        return

    if args.command == "start":
        _start_banner()
        return

    if args.command == "validate":
        proj_dir = find_project(args.project)
        if not proj_dir:
            print(f"[ERROR] 项目 '{args.project}' 未找到")
            return
        _validate_project(proj_dir)
        return

    if not args.command:
        parser.print_help()
        return

    if args.command == "article":
        _write_article(args.topic, args.angle, args.type, args.words)
        return

    # 需要 --project 的命令
    proj_dir = find_project(args.project)
    if proj_dir is None:
        print(f"[ERROR] 项目 '{args.project}' 未找到")
        print(f"  搜索路径: {[str(r) for r in PROJECT_ROOTS]}")
        sys.exit(1)

    if args.command == "write":
        mode = "quick" if getattr(args, "fast", False) else "workshop"
        _check_api_key()
        write_chapter(proj_dir, args.chapter, mode=mode,
                       chapter_task=getattr(args, "task", None),
                       dry_run=getattr(args, "dry_run", False))

    elif args.command == "batch":
        mode = "quick" if getattr(args, "fast", False) else "workshop"
        _check_api_key()
        batch_write(proj_dir, args.from_ch, args.to_ch, mode=mode,
                     delay=getattr(args, "delay", 3.0))

    elif args.command == "review":
        review_chapter(proj_dir, args.chapter)

    elif args.command == "status":
        project_status(proj_dir)


if __name__ == "__main__":
    main()
