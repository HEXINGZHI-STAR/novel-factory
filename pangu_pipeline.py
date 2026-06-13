#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI · 固化创作流水线
========================
你只需要输入方向，系统自动完成:
  ① 搜参考书 → ② 分析风格 → ③ 出提示词 → ④ 调DeepSeek生成 → ⑤ 归档

⚠️ DEPRECATED: 此文件已非主力入口，流水线功能已集成到 pangu_core/pipeline.py (WritingPipeline)。
   唯一入口: python pangu_workshop.py write --project <项目> --chapter <N>

用法:
  python pangu_pipeline.py "玄幻爽文，主角重生回到高考那年，用未来记忆逆袭"

流程铁律:
  1. 用户只提供方向（题材/平台/风格/一句话概念）
  2. 系统搜数据库找匹配参考书并分析风格
  3. 系统生成注入模式+平台+参考风格的提示词
  4. 调用 DeepSeek API 生成大纲和正文
  5. 系统创建项目文件夹，保存所有输出
  6. 全程不人工写正文
"""

import os, sys, json, time, re, argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "knowledge"))
sys.path.insert(0, str(BASE_DIR / "backend"))

# ── 导入系统模块 ──
try:
    from db_manager import NovelReferenceDB
    from chapter_analyzer import ChapterAnalyzer
    from reference_prompt import ReferencePromptGenerator
    from unified_db_manager import UnifiedDBManager
except ImportError as e:
    print(f"[FATAL] 缺少核心模块: {e}")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[FATAL] 需要安装 requests: pip install requests")
    sys.exit(1)

# ── 配置 ──
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1") + "/chat/completions"
MODEL = os.getenv("AI_MODEL", "deepseek-chat")
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# ── 平台风格底色 ──
PLATFORM_TONES = {
    "qimao": "七猫风格，节奏快开篇抓人，短句多对话，情绪浓烈不克制，语言通俗好读，每章结尾让人想翻下一章。",
    "fanqie": "番茄风格，节奏快大白话，开篇300字出冲突，主角杀伐果断不圣母不内耗，每章有打脸或逆袭。",
    "qidian": "起点风格，允许中长句可稍慢热，世界观有纵深感，人物有成长弧光，钩子多用悬念和信息缺口。",
    "jinjiang": "晋江风格，细腻五感丰富，对话有潜台词话不说满，情绪渗透型不直给，主角人设鲜明情感细腻。",
}

# ── 题材关键词映射（用于搜参考书） ──
GENRE_SEARCH_TERMS = {
    "玄幻": ["玄幻", "仙侠", "奇幻", "西方奇幻"],
    "都市": ["都市", "言情"],
    "科幻": ["科幻", "游戏"],
    "历史": ["历史", "军事"],
    "悬疑": ["悬疑"],
    "体育": ["体育"],
    "二次元": ["二次元"],
}

def print_step(step_num, title):
    print(f"\n{'='*60}\n  [{step_num}/5] {title}\n{'='*60}")

# ═══════════════════════════════════════════════
# 步骤1: 搜参考书 + 分析风格
# ═══════════════════════════════════════════════
def find_and_analyze_references(genre: str, platform: str = "qimao", top_k: int = 5):
    """在753本参考书中搜索同题材书籍，分析风格特征"""
    print_step(1, f"搜参考书 → 题材:{genre} 平台:{platform}")

    db = NovelReferenceDB()
    analyzer = ChapterAnalyzer()
    all_books = db.list_books(only_reference=True, limit=5000)

    # 搜索同题材
    search_terms = GENRE_SEARCH_TERMS.get(genre, [genre])
    candidates = []
    for b in all_books:
        bg = (b.get('genre') or '').strip()
        if any(t in bg for t in search_terms):
            chaps = db.get_chapters(b['id'])
            if chaps and chaps[0].get('content', ''):
                wc = sum(c.get('word_count') or 0 for c in chaps)
                candidates.append((b, chaps, wc))

    candidates.sort(key=lambda x: -x[2])  # 按字数排序

    if not candidates:
        print(f"  ⚠ 未找到 {genre} 题材参考书，使用全部有章节的书籍")
        for b in all_books:
            chaps = db.get_chapters(b['id'])
            if chaps and chaps[0].get('content', ''):
                wc = sum(c.get('word_count') or 0 for c in chaps)
                candidates.append((b, chaps, wc))
        candidates.sort(key=lambda x: -x[2])

    top = candidates[:top_k]
    print(f"  找到 {len(candidates)} 本同题材书籍，取前 {len(top)} 本分析\n")

    ref_analysis = []
    for i, (book, chaps, wc) in enumerate(top, 1):
        content = chaps[0].get('content', '')
        ana = analyzer.full_analysis(content, book['title'] or '')
        rd = ana.get('reading_difficulty', {})
        hooks = ana.get('hooks', [])

        d_lines = sum(1 for line in content.split('\n') if '"' in line or '"' in line or '“' in line)
        total_lines = max(1, len(content.split('\n')))
        dialogue_ratio = d_lines * 100 // total_lines

        info = {
            'title': book['title'][:50], 'genre': book.get('genre', ''),
            'author': book.get('author', ''), 'words': wc,
            'avg_sentence_len': rd.get('avg_words_per_sentence', 0),
            'hooks': [(h['type'], h['count']) for h in hooks[:3]],
            'dialogue_ratio': dialogue_ratio,
            'opening_sample': content[:200].replace('\n', ' ')
        }
        ref_analysis.append(info)

        print(f"  [{i}] {info['title'][:40]}")
        print(f"      题材:{info['genre']} 字数:{info['words']} 句均:{info['avg_sentence_len']}字 对话率:{info['dialogue_ratio']}%")
        print(f"      钩子:{info['hooks']}")

    return ref_analysis


# ═══════════════════════════════════════════════
# 步骤2: 构建提示词
# ═══════════════════════════════════════════════
def build_pipeline_prompt(concept: str, genre: str, platform: str, ref_analysis: list):
    """基于参考书分析 + 平台规则 + 模式配置，构建完整提示词"""
    print_step(2, "构建提示词")

    # 加载模式配置
    udb = UnifiedDBManager()
    mode_id = "general"  # 默认通用模式
    mode_info = ""
    try:
        mode = udb.get_mode(mode_id)
        if mode:
            mode_info = mode.get("core_principle", "")
    except:
        pass

    # 平台风格
    platform_tone = PLATFORM_TONES.get(platform, PLATFORM_TONES["qimao"])

    # 参考书风格摘要
    ref_summary = ""
    if ref_analysis:
        avg_sl = sum(r['avg_sentence_len'] for r in ref_analysis) / len(ref_analysis)
        avg_dr = sum(r['dialogue_ratio'] for r in ref_analysis) / len(ref_analysis)
        top_hooks = set()
        for r in ref_analysis:
            for h, _ in r['hooks'][:2]:
                top_hooks.add(h)
        ref_summary = f"""
参考了 {len(ref_analysis)} 本同题材书籍的风格特征:
- 平均句长: {avg_sl:.0f}字/句
- 平均对话率: {avg_dr:.0f}%
- 常用钩子类型: {', '.join(top_hooks) if top_hooks else '悬念+疑问'}
- 参考书目: {', '.join(r['title'][:20] for r in ref_analysis[:3])}
"""

    # ── 大纲生成提示词（硬性必须包含以下全部章节）──
    outline_prompt = f"""你是一位擅长{platform_tone}

{mode_info}

{ref_summary}

请为以下小说概念生成完整大纲：

核心概念：{concept}
目标平台：{platform}
题材：{genre}

【硬性要求】以下每个章节都必须输出，缺一不可，顺序不可变：

## 一、书名（3个候选，选最好的标★）

## 二、作品简介
### 一句话版（30字以内）
### 完整版（200字左右，必须包含主角+困境+金手指+核心悬念）

## 三、核心卖点（5条，每条一句话，卖点之间不重复）

## 四、人物设定（主角+女主+关键配角+反派，每人含身份/性格/核心矛盾/在故事中的作用）

## 五、世界观要点（5条以内）

## 六、大纲（按平台和题材决定章节数）
"""

    # ── 第1章正文生成提示词 ──
    chapter1_prompt = f"""你是一位擅长{platform_tone}

{mode_info}

{ref_summary}

请写一篇小说的第1章。

小说概念：{concept}
题材：{genre}
平台：{platform}

要求：约2500字。直接输出正文，不要前言后记。"""

    print(f"  大纲提示词: {len(outline_prompt)}字")
    print(f"  第1章提示词: {len(chapter1_prompt)}字")

    return outline_prompt, chapter1_prompt


# ═══════════════════════════════════════════════
# 步骤3: 调用 DeepSeek
# ═══════════════════════════════════════════════
def call_deepseek(prompt: str, label: str = "生成"):
    """调用 DeepSeek API"""
    print(f"\n  [{label}] 调用 DeepSeek...")

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4000}

    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=data, headers=headers, timeout=180)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # 清理
                content = re.sub(r'^好的[，,。！!]?\s*', '', content)
                content = re.sub(r'^好的，以下是.*?\n', '', content)
                wc = len(content.replace('\n', '').replace(' ', ''))
                print(f"  [{label}] 完成 — {wc}字")
                return content
            else:
                print(f"  [{label}] HTTP {resp.status_code}, 重试...")
                time.sleep(3)
        except Exception as e:
            print(f"  [{label}] {e}, 重试...")
            time.sleep(3)

    print(f"  [{label}] 失败")
    return None


# ═══════════════════════════════════════════════
# 步骤4+5: 创建项目并保存
# ═══════════════════════════════════════════════
def create_project_and_save(concept: str, genre: str, platform: str, outline: str, chapter1: str):
    """创建项目文件夹，保存大纲和正文，写入 state.json"""
    print_step(4, "归档项目")

    # 从大纲中提取书名
    title_match = re.search(r'书名[：:]\s*[《]?(.+?)[》]?', outline or '')
    if not title_match:
        title_match = re.search(r'[《](.+?)[》]', outline or '')
    title = title_match.group(1).strip() if title_match else concept[:20].replace('，', ' ').replace('、', ' ')

    # 安全目录名
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    project_dir = PROJECTS_DIR / safe_title
    if project_dir.exists():
        i = 2
        while (PROJECTS_DIR / f"{safe_title}_{i}").exists():
            i += 1
        project_dir = PROJECTS_DIR / f"{safe_title}_{i}"

    (project_dir / "大纲").mkdir(parents=True, exist_ok=True)
    (project_dir / "正文").mkdir(parents=True, exist_ok=True)

    # 保存大纲
    outline_file = project_dir / "大纲" / "总大纲.md"
    outline_file.write_text(outline or "(生成失败)", encoding='utf-8')

    # 保存第1章
    chapter_file = project_dir / "正文" / "第1章.txt"
    chapter_file.write_text(chapter1 or "(生成失败)", encoding='utf-8')

    # 写入状态
    state = {
        "project_info": {
            "title": title, "genre": genre, "platform": platform,
            "concept": concept, "target_chapters": 12,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "progress": {"current_chapter": 1, "total_words": len(chapter1 or '')},
        "pipeline_version": "1.0"
    }
    (project_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n  书名: 《{title}》")
    print(f"  路径: {project_dir}")
    print(f"  大纲: {outline_file}")
    print(f"  第1章: {chapter_file}")

    return project_dir, title


# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="盘古AI固化创作流水线")
    parser.add_argument("concept", help="一句话小说概念")
    parser.add_argument("--genre", default="玄幻", help="题材 (默认:玄幻)")
    parser.add_argument("--platform", default="qimao", help="平台 (默认:qimao)")
    parser.add_argument("--ref-count", type=int, default=5, help="参考书数量 (默认:5)")
    parser.add_argument("--skip-outline", action="store_true", help="跳过大纲生成")
    parser.add_argument("--skip-chapter1", action="store_true", help="跳过第1章生成")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║                 盘古AI · 固化创作流水线                       ║
║  ①搜参考书 → ②分析风格 → ③出提示词 → ④DeepSeek → ⑤归档    ║
╚══════════════════════════════════════════════════════════════╝
""")
    print(f"  方向: {args.concept}")
    print(f"  题材: {args.genre}  平台: {args.platform}")
    print(f"  模型: {MODEL}")

    # ① 搜参考书 + 分析
    ref_analysis = find_and_analyze_references(args.genre, args.platform, args.ref_count)

    # ② 构建提示词
    outline_prompt, chapter1_prompt = build_pipeline_prompt(
        args.concept, args.genre, args.platform, ref_analysis
    )

    # ③+④ 调 DeepSeek 生成
    outline = None
    chapter1 = None

    if not args.skip_outline:
        print_step(3, "生成大纲")
        outline = call_deepseek(outline_prompt, "大纲")

    if not args.skip_chapter1:
        step_label = "3" if args.skip_outline else "4"
        print_step(int(step_label), "生成第1章")
        chapter1 = call_deepseek(chapter1_prompt, "第1章")

    # ⑤ 归档
    project_dir, title = create_project_and_save(
        args.concept, args.genre, args.platform, outline, chapter1
    )

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    流水线完成                                ║
║  书名: 《{title}》                                          ║
║  路径: {project_dir}                                        ║
║  参考书: {len(ref_analysis)}本                               ║
║  下一步: 用 pangu_optimized.py 继续写后续章节                 ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
