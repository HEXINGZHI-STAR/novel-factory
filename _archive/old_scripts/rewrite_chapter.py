#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI — 小说改编重写模块
=========================
基于已有小说章节，通过全系统分析诊断问题，然后调用AI进行智能改编重写。

核心流程:
1. 读取原文章节
2. 呼吸工作流诊断 (10阶段管道)
3. 数学引擎全分析 (6分支)
4. 构建"诊断驱动"的重写提示词
5. 调用DeepSeek重写
6. 对比前后质量变化

用法:
    python rewrite_chapter.py <项目名> <章节号> [平台] [-y 自动确认]

示例:
    python rewrite_chapter.py "末世：我有一座外星空间站" 1
    python rewrite_chapter.py "镇妖司：新科状元" 1 qimao -y
"""

import sys
import os
import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置
# ============================================================

PROJECTS_ROOT = Path(__file__).resolve().parent / "projects"
KNOWLEDGE_ROOT = Path(__file__).resolve().parent / "knowledge"

# 将knowledge加入路径
sys.path.insert(0, str(KNOWLEDGE_ROOT))

# API配置 (与主系统一致)
# API 配置: 只从环境变量 DEEPSEEK_API_KEY 读取
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
API_MODEL = "deepseek-v4-flash"
API_TEMP = 0.7
API_MAX_TOKENS = 4000
API_TIMEOUT = 120


# ============================================================
# 步骤1: 读取原文章节
# ============================================================

def load_original(project_name: str, chapter_num: int) -> dict:
    """读取原始章节"""
    project_dir = PROJECTS_ROOT / project_name
    if not project_dir.exists():
        return {"error": f"项目不存在: {project_name}"}

    body_dir = project_dir / "正文"
    if not body_dir.exists():
        return {"error": "项目没有正文目录"}

    # 查找匹配的章节文件
    ch_files = list(body_dir.glob(f"第{chapter_num}章*.txt"))
    if not ch_files:
        return {"error": f"找不到第{chapter_num}章"}

    text = ch_files[0].read_text(encoding='utf-8', errors='ignore')
    word_count = len(re.sub(r'\s', '', text))

    # 读取state.json获取元信息
    state = {}
    state_file = project_dir / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    info = state.get("project_info", {})

    return {
        "text": text,
        "word_count": word_count,
        "chapter_num": chapter_num,
        "project_name": project_name,
        "platform": info.get("platform", "qimao"),
        "genre": info.get("genre", "unknown"),
        "title": info.get("title", project_name),
        "chapter_file": str(ch_files[0]),
    }


# ============================================================
# 步骤2: 诊断分析
# ============================================================

def diagnose(original: dict) -> dict:
    """对原始章节执行完整诊断"""
    text = original["text"]
    chapter_num = original["chapter_num"]
    platform = original["platform"]
    genre = original["genre"]

    diagnoses = {}

    # 2.1 质量检查
    try:
        from quality_checker import check_chapter
        quality = check_chapter(text, platform, chapter_num)
        issues = len(getattr(quality, 'issues', [])) if quality else 0
        warnings_count = len(getattr(quality, 'warnings', [])) if quality else 0
        fatals = len(getattr(quality, 'fatals', [])) if quality else 0
        diagnoses["quality"] = {
            "passed": fatals == 0 and issues == 0,
            "fatals": fatals,
            "issues": issues,
            "warnings": warnings_count,
        }
        print(f"  [质量检查] 致命{fatals} 问题{issues} 警告{warnings_count}")
    except Exception as e:
        diagnoses["quality"] = {"error": str(e)}

    # 2.2 动态评分
    try:
        from dynamic_scorer import DynamicScorer
        scorer = DynamicScorer()
        dynamic = scorer.comprehensive_score(text, platform)
        diagnoses["dynamic"] = dynamic
        print(f"  [动态评分] {dynamic.get('total_score', '?')}/100 — {dynamic.get('verdict', '?')}")
    except Exception as e:
        diagnoses["dynamic"] = {"error": str(e)}

    # 2.3 数学引擎全分析
    try:
        from pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        math_result = engine.full_analysis(text, chapter_num)
        diagnoses["math"] = math_result

        # 提取关键诊断
        math_issues = []
        fourier = math_result.get("fourier_analysis", {}).get("emotion_spectrum", {})
        if fourier and fourier.get("rhythm_type") == "分散":
            math_issues.append("情绪节奏分散，缺乏主导频率")

        laplace = math_result.get("laplace_analysis", {})
        l_summary = laplace.get("summary", "")
        if "短期" in l_summary and laplace.get("score", 0) < 60:
            math_issues.append("钩子衰减不健康，短期驱动不足")

        integral = math_result.get("integral_analysis", {}).get("emotional_arc", {})
        if integral.get("pos_neg_ratio", 2) < 0.5:
            math_issues.append("正负情绪严重失衡，缺乏正向情绪")

        markov = math_result.get("markov_chain", {})
        if markov.get("chain_health") == "不良":
            math_issues.append("叙事状态链不健康")

        info = math_result.get("information_metrics", {})
        bigram_e = info.get("bigram_entropy", 0)
        if bigram_e > 11:
            math_issues.append(f"词汇过于丰富(熵{bigram_e:.1f}bits)，可能影响可读性")

        diagnoses["math_issues"] = math_issues
        print(f"  [数学引擎] {math_result.get('overall_math_score', '?')}/100 — {len(math_issues)}个问题")
    except Exception as e:
        diagnoses["math"] = {"error": str(e)}
        diagnoses["math_issues"] = []

    # 2.4 风格指纹
    try:
        from style_fingerprint import StyleFingerprint
        fp = StyleFingerprint(text, platform=platform)
        style_result = fp.to_dict()
        diagnoses["style"] = style_result

        deep = style_result.get("deep_math", {})
        ai_flag = deep.get("ai_template_detected", False) if isinstance(deep, dict) else False
        if ai_flag:
            diagnoses["math_issues"].append("检测到AI模板化特征，需人工化润色")

        print(f"  [风格指纹] AI模板检测:{'有' if ai_flag else '无'}")
    except Exception as e:
        diagnoses["style"] = {"error": str(e)}

    # 2.5 创作引擎策略
    try:
        from creative_engine import CreativeEngine
        ce = CreativeEngine()
        strategy = ce.recommend_strategy(genre, chapter_num, platform)
        diagnoses["strategy"] = strategy
        print(f"  [创作引擎] {len(strategy.get('actionable_tips', []))}条策略建议")
    except Exception as e:
        diagnoses["strategy"] = {"error": str(e)}

    return diagnoses


# ============================================================
# 步骤3: 构建重写提示词
# ============================================================

def build_rewrite_prompt(original: dict, diagnoses: dict) -> tuple:
    """
    构建"诊断驱动"的重写提示词。
    返回 (system_msg, user_msg)
    """
    text = original["text"]
    platform = original["platform"]
    genre = original["genre"]
    chapter_num = original["chapter_num"]
    title = original["title"]

    # ---- 收集所有需要修复的问题 ----
    all_issues = []

    # 质量问题
    quality = diagnoses.get("quality", {})
    if quality.get("fatals", 0) > 0:
        all_issues.append(f"★ 质量致命问题{quality['fatals']}个，必须修复")
    if quality.get("issues", 0) > 0:
        all_issues.append(f"● 质量问题{quality['issues']}个")

    # 动态评分弱项
    dynamic = diagnoses.get("dynamic", {})
    breakdown = dynamic.get("breakdown", {})
    for name, data in breakdown.items():
        s = data.get("score", 100)
        if s < 60:
            all_issues.append(f"● {name}评分{s}/100过低 — {data.get('detail', '需改进')}")

    # 数学引擎问题
    math_issues = diagnoses.get("math_issues", [])
    all_issues.extend([f"● {issue}" for issue in math_issues])

    # 平台约束
    platform_rules = {
        "qimao": "句均≤18字, 段落≤3行, 对话率≥45%, 一章一高潮, 情绪极致浓烈",
        "fanqie": "句均≤15字, 段落≤3行, 对话率≥40%, 300字内出冲突, 情绪直给不迂回",
        "qidian": "句均≤25字, 段落≤5行, 对话率≥30%, 逻辑严密, 延迟爆发, 智商在线",
    }
    platform_rule = platform_rules.get(platform, platform_rules["qimao"])

    # ---- System Message ----
    system_msg = f"""你是一位精通{platform}平台网文写作的资深作者，正在进行章节修订。

## 修改原则
1. 保持原有的世界观、人物设定和核心情节不变
2. 重点修复诊断发现的问题
3. 提升可读性和读者留存力
4. 避免AI模板化表达

## 平台硬性约束 ({platform})
{platform_rule}

## 写作铁律
- 禁止以下AI套话: "瞳孔骤然收缩""倒吸一口凉气""嘴角勾起一抹冷笑""眼中闪过一丝""二话不说""话音刚落"
- 每个场景至少包含3种感官描写 (视觉+听觉/触觉/嗅觉)
- 对话必须推进情节或展示性格，不能是废话
- 展示不告知: 用动作和细节表达情绪，不用"他感到"类叙述
- 第一章: 第一句话发生事 → 主角主动行动 → 金手指展示 → 爽点 → 强钩子

## 本章发现的问题 (必须逐一修复)
{chr(10).join(all_issues) if all_issues else '(无重大问题)'}

## 风格要求
- 网文白描风格，拒绝散文腔
- 情绪饱满，节奏紧凑
- 对话自然有力
- 适合手机阅读 (短段落)"""

    # ---- User Message ----
    # 查找前文上下文
    prev_context = ""
    if chapter_num > 1:
        project_dir = PROJECTS_ROOT / original["project_name"]
        prev_file = project_dir / "正文" / f"第{chapter_num - 1}章.txt"
        if prev_file.exists():
            prev_text = prev_file.read_text(encoding='utf-8', errors='ignore')
            prev_tail = prev_text[-300:] if len(prev_text) > 300 else prev_text
            prev_context = f"\n\n## 前一章结尾（供衔接参考）\n{prev_tail}"

    user_msg = f"""请重写小说《{title}》第{chapter_num}章。

## 原文（需要重写）
{'-'*40}
{text}
{'-'*40}
{prev_context}

## 重写要求
1. 保持原有人物、情节走向和世界观设定
2. 修复上述"本章发现的问题"中的所有问题
3. 遵循平台硬性约束
4. 保留原文中的亮点和有效表达
5. 字数: 与原文接近 ({original['word_count']}字左右)
6. 直接输出重写后的正文，不要前言后记

第{chapter_num}章重写稿："""

    return system_msg, user_msg


# ============================================================
# 步骤4: 调用AI重写
# ============================================================

def call_ai_rewrite(system_msg: str, user_msg: str) -> str:
    """调用AI进行重写"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    for attempt in range(3):
        try:
            if attempt > 0:
                print(f"  重试 {attempt}/3...")

            response = requests.post(
                f"{API_BASE}/chat/completions",
                json={
                    "model": API_MODEL,
                    "messages": messages,
                    "temperature": API_TEMP,
                    "max_tokens": API_MAX_TOKENS,
                },
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=API_TIMEOUT,
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # 清理AI输出
                content = re.sub(r'^(好的|没问题|以下是我的|这是).*?正文[：:]?\s*', '', content)
                content = re.sub(r'^[#＝=].*$', '', content, flags=re.MULTILINE).strip()
                return content
            else:
                print(f"  API错误: {response.status_code}")

        except Exception as e:
            print(f"  调用失败: {e}")

    return None


# ============================================================
# 步骤5: 对比前后质量
# ============================================================

def compare_versions(original: dict, rewritten_text: str, platform: str) -> dict:
    """对比原版和重写版的质量"""
    after_wc = len(re.sub(r'\s', '', rewritten_text))
    result = {"word_count_before": original["word_count"],
              "word_count_after": after_wc}

    # 对重写版也做一次分析
    try:
        from pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        before_math = engine.full_analysis(original["text"], original["chapter_num"])
        after_math = engine.full_analysis(rewritten_text, original["chapter_num"])

        before_score = before_math.get("overall_math_score", 0)
        after_score = after_math.get("overall_math_score", 0)
        delta = after_score - before_score
        result["math_score_before"] = round(before_score, 1)
        result["math_score_after"] = round(after_score, 1)
        result["math_score_delta"] = round(delta, 1)
        result["improved"] = delta > 0
    except Exception as e:
        result["compare_error"] = str(e)

    # 风格指纹对比
    try:
        from style_fingerprint import StyleFingerprint
        fp_before = StyleFingerprint(original["text"], platform=platform)
        fp_after = StyleFingerprint(rewritten_text, platform=platform)

        before_d = fp_before.to_dict()
        after_d = fp_after.to_dict()

        # 比较AI模板检测
        dm_before = before_d.get("deep_math", {})
        dm_after = after_d.get("deep_math", {})

        result["ai_template_before"] = dm_before.get("ai_template_detected", None) if isinstance(dm_before, dict) else None
        result["ai_template_after"] = dm_after.get("ai_template_detected", None) if isinstance(dm_after, dict) else None
    except Exception:
        pass

    return result


# ============================================================
# 主流程
# ============================================================

def rewrite_chapter(project_name: str, chapter_num: int,
                    platform: str = None, auto_confirm: bool = False) -> dict:
    """
    改编重写指定章节。
    
    参数:
        project_name: 项目名称
        chapter_num: 章节号
        platform: 目标平台 (覆盖原项目的平台设置)
        auto_confirm: 跳过确认直接执行
    
    返回:
        dict with keys: original, rewritten, diagnosis, comparison, saved_path
    """
    print(f"\n{'='*60}")
    print(f"  盘古AI改编重写")
    print(f"  项目: {project_name} | 第{chapter_num}章")
    print(f"{'='*60}")

    # Step 1: 加载原文
    print("\n[1/5] 加载原文...")
    original = load_original(project_name, chapter_num)
    if "error" in original:
        print(f"  [FAIL] {original['error']}")
        return original
    if platform:
        original["platform"] = platform
    print(f"  [+OK] {original['word_count']}字 | 平台:{original['platform']} | 类型:{original['genre']}")

    # Step 2: 诊断分析
    print("\n[2/5] 诊断分析...")
    diagnoses = diagnose(original)

    # 打印问题汇总
    math_issues = diagnoses.get("math_issues", [])
    if math_issues:
        print(f"\n  发现 {len(math_issues)} 个问题:")
        for issue in math_issues:
            print(f"    {issue}")

    # Step 3: 构建重写提示词
    print("\n[3/5] 构建重写提示词...")
    system_msg, user_msg = build_rewrite_prompt(original, diagnoses)
    print(f"  [+OK] System约束 {len(system_msg)}字 | User任务 {len(user_msg)}字")

    # Step 4: 确认 & 调用AI
    if not auto_confirm:
        print(f"\n{'='*60}")
        print(f"  即将调用 DeepSeek v4 进行重写...")
        print(f"  原始字数: {original['word_count']}字")
        print(f"{'='*60}")
        confirm = input("\n确认重写？(y/n): ").strip().lower()
        if confirm != 'y':
            return {"cancelled": True, "diagnoses": diagnoses}

    print("\n[4/5] AI重写中...")
    rewritten_text = call_ai_rewrite(system_msg, user_msg)
    if not rewritten_text:
        print("  [FAIL] 重写失败")
        return {"error": "AI调用失败", "diagnoses": diagnoses}

    rewrote_wc = len(re.sub(r'\s', '', rewritten_text))
    print(f"  [+OK] 重写完成 | {rewrote_wc}字")

    # Step 5: 对比 & 保存
    print("\n[5/5] 对比分析 & 保存...")
    comparison = compare_versions(original, rewritten_text, original["platform"])

    # 生成版本文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = PROJECTS_ROOT / project_name / "正文"
    version_file = project_dir / f"第{chapter_num}章_重写{timestamp}.txt"

    # 保存重写稿
    header = f"# 盘古AI改编重写 | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    header += f"# 原始字数: {original['word_count']} | 重写字数: {rewrote_wc}\n"
    if "math_score_before" in comparison:
        header += f"# 数学评分: {comparison['math_score_before']} → {comparison['math_score_after']} "
        header += f"({'↑' if comparison.get('improved') else '↓'}{abs(comparison.get('math_score_delta', 0))})\n"
    header += "-" * 40 + "\n\n"

    version_file.write_text(header + rewritten_text, encoding='utf-8')
    print(f"\n  [OK] 已保存到: {version_file}")

    # 打印对比
    print(f"\n{'='*60}")
    print(f"  重写前后对比")
    print(f"{'='*60}")
    print(f"  字数: {comparison.get('word_count_before', '?')} → {comparison.get('word_count_after', '?')}")
    if "math_score_before" in comparison:
        before = comparison["math_score_before"]
        after = comparison["math_score_after"]
        delta = comparison["math_score_delta"]
        direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        print(f"  数学评分: {before} → {after} ({direction}{abs(delta)})")

    result = {
        "original": original,
        "diagnoses": diagnoses,
        "rewritten_text": rewritten_text,
        "comparison": comparison,
        "saved_path": str(version_file),
    }
    return result


# ============================================================
# 批量重写整个项目
# ============================================================

def rewrite_project(project_name: str, platform: str = None,
                    auto_confirm: bool = False) -> dict:
    """
    批量重写项目的所有章节。
    
    按章节顺序逐一重写，保留章节间上下文。
    """
    project_dir = PROJECTS_ROOT / project_name
    if not project_dir.exists():
        return {"error": f"项目不存在: {project_name}"}

    body_dir = project_dir / "正文"
    if not body_dir.exists():
        return {"error": "无正文目录"}

    # 收集章节文件（排除已有的重写文件）
    ch_files = sorted([
        f for f in body_dir.glob("第*章*.txt")
        if "重写" not in f.name
    ], key=lambda f: _extract_chapter_num(f.name))

    if not ch_files:
        return {"error": "无章节文件"}

    total = len(ch_files)
    print(f"\n{'='*60}")
    print(f"  盘古AI 批量改编写")
    print(f"  项目: {project_name} | {total} 章")
    print(f"{'='*60}")

    info = load_original(project_name, 1)
    if platform:
        info["platform"] = platform

    results = []
    total_before_score = 0
    total_after_score = 0

    for i, ch_file in enumerate(ch_files, 1):
        chapter_num = _extract_chapter_num(ch_file.name)
        print(f"\n{'─'*60}")
        print(f"  [{i}/{total}] 第{chapter_num}章")
        print(f"{'─'*60}")

        # 加载原文
        original = load_original(project_name, chapter_num)
        if "error" in original:
            print(f"  [SKIP] {original['error']}")
            continue
        if info.get("platform"):
            original["platform"] = info["platform"]

        # 诊断
        diagnoses = diagnose(original)

        # 构建提示词（包含前章上下文）
        system_msg, user_msg = build_rewrite_prompt(original, diagnoses)

        # 重写
        rewritten_text = call_ai_rewrite(system_msg, user_msg)
        if not rewritten_text:
            print(f"  [SKIP] AI调用失败")
            continue

        # 对比
        comparison = compare_versions(original, rewritten_text, original["platform"])

        # 保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_file = body_dir / f"第{chapter_num}章_重写{timestamp}.txt"

        rewrote_wc = len(re.sub(r'\s', '', rewritten_text))
        header = f"# 盘古AI批量改编写 | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        header += f"# 原字数: {original['word_count']} | 重写字数: {rewrote_wc}\n"
        if "math_score_before" in comparison:
            bs = comparison["math_score_before"]
            as_ = comparison["math_score_after"]
            d = comparison.get("math_score_delta", 0)
            sign = "+" if d > 0 else ""
            header += f"# 数学评分: {bs} -> {as_} ({sign}{d})\n"
        header += "-" * 40 + "\n\n"

        version_file.write_text(header + rewritten_text, encoding='utf-8')

        # 累积统计
        total_before_score += comparison.get("math_score_before", 0)
        total_after_score += comparison.get("math_score_after", 0)

        chapter_result = {
            "chapter_num": chapter_num,
            "word_count_before": original["word_count"],
            "word_count_after": rewrote_wc,
            "math_before": comparison.get("math_score_before", 0),
            "math_after": comparison.get("math_score_after", 0),
            "delta": comparison.get("math_score_delta", 0),
            "saved_path": str(version_file),
        }
        results.append(chapter_result)

        # 等1秒避免API限流
        if i < total:
            time.sleep(1)

    # 汇总
    n = len(results)
    avg_before = total_before_score / n if n > 0 else 0
    avg_after = total_after_score / n if n > 0 else 0

    summary = {
        "project": project_name,
        "total_chapters": total,
        "rewritten": n,
        "avg_score_before": round(avg_before, 1),
        "avg_score_after": round(avg_after, 1),
        "avg_delta": round(avg_after - avg_before, 1),
        "chapters": results,
    }

    print(f"\n{'='*60}")
    print(f"  批量改编写完成")
    print(f"{'='*60}")
    print(f"  重写: {n}/{total} 章")
    print(f"  均分: {avg_before:.1f} -> {avg_after:.1f} ({'+' if avg_after>=avg_before else ''}{avg_after-avg_before:.1f})")
    for r in results:
        d = r["delta"]
        sign = "+" if d >= 0 else ""
        print(f"  第{r['chapter_num']}章: {r['math_before']} -> {r['math_after']} ({sign}{d}) | {r['word_count_before']}->{r['word_count_after']}字")

    return summary


def _extract_chapter_num(filename: str) -> int:
    """从文件名提取章节号"""
    m = re.search(r'第(\d+)章', filename)
    return int(m.group(1)) if m else 0


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) < 2 and "--all" not in args:
        print("用法: python rewrite_chapter.py <项目名> <章节号> [平台] [-y]")
        print("      python rewrite_chapter.py <项目名> --all [平台] [-y]   # 重写全部章节")
        print()
        print("示例:")
        print('  python rewrite_chapter.py "末世：我有一座外星空间站" 1')
        print('  python rewrite_chapter.py "末世：我有一座外星空间站" --all qimao -y')
        print()
        print("可用项目:")
        for name in sorted([d.name for d in PROJECTS_ROOT.iterdir() if d.is_dir() and not d.name.startswith('_')]):
            ch_count = len(list((PROJECTS_ROOT / name / "正文").glob("*.txt"))) if (PROJECTS_ROOT / name / "正文").exists() else 0
            print(f"  · {name} ({ch_count}章)")
        sys.exit(0)

    project_name = args[0]

    # 检查是否是 --all 模式
    if "--all" in args:
        platform = None
        auto_confirm = False
        for arg in args[1:]:
            if arg in ("qimao", "fanqie", "qidian"):
                platform = arg
            elif arg == "-y":
                auto_confirm = True

        result = rewrite_project(project_name, platform, auto_confirm)
        if "error" in result:
            print(f"\n[FAIL] {result['error']}")
            sys.exit(1)
        sys.exit(0)

    # 单章模式
    try:
        chapter_num = int(args[1])
    except ValueError:
        print(f"无效的章节号: {args[1]}")
        sys.exit(1)

    platform = None
    auto_confirm = False
    for arg in args[2:]:
        if arg in ("qimao", "fanqie", "qidian"):
            platform = arg
        elif arg == "-y":
            auto_confirm = True

    result = rewrite_chapter(project_name, chapter_num, platform, auto_confirm)

    if "error" in result:
        print(f"\n[FAIL] 失败: {result['error']}")
        sys.exit(1)
    elif result.get("cancelled"):
        print("\n已取消")
    else:
        print(f"\n{'='*60}")
        print("  重写完成！")
        print(f"  原稿: {result['original']['chapter_file']}")
        print(f"  新稿: {result['saved_path']}")
        print(f"{'='*60}")
