#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI — 分维度迭代改写
=========================
不是一次性重写整章，而是5轮递进：
  每轮只改一个维度，AI专注度最大化。

Pass 1: 钩子密度 (拉普拉斯驱动)  — 句级/段级钩子
Pass 2: 对话节奏 (傅里叶驱动)    — 对话率+节律
Pass 3: 情绪平衡 (积分学驱动)    — 正负情绪比+弧线
Pass 4: 动作密度 (马尔可夫驱动)  — 降exposition+增climax
Pass 5: 润色整合                — 全局一致性+去AI味

用法:
    python multi_pass_rewrite.py "末世：我有一座外星空间站" 1 -y
    python multi_pass_rewrite.py "末世：我有一座外星空间站" --all -y
"""

import sys
import os
import re
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# -----------------------------------------------------------
PROJECTS_ROOT = Path(__file__).resolve().parent / "projects"
KNOWLEDGE_ROOT = Path(__file__).resolve().parent / "knowledge"
sys.path.insert(0, str(KNOWLEDGE_ROOT))

# API 配置: 只从环境变量 DEEPSEEK_API_KEY 读取
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
API_MODEL = "deepseek-v4-flash"
API_TEMP = 0.72
API_MAX_TOKENS = 4000
API_TIMEOUT = 150


# ============================================================
# PASS 1: 钩子密度 (拉普拉斯驱动)
# ============================================================

def pass1_hooks(text: str, chapter_num: int, platform: str) -> str:
    """
    目标: 提升句级/段级钩子密度
    - 每300-500字插入悬疑问句或紧急情境转换
    - 段尾埋钩子
    """
    print("  [P1] 目标: 句级钩子从0% → >5%，段级钩子 >10%")

    system = f"""你是{platform}网文的章节改写专家。本轮你只需要做一件事：增加句级和段级钩子。

## 什么是句级钩子（每8-12句插一个）
- 悬疑问句: "可他没注意到的是……" "这真的是巧合吗？"
- 紧急情境转换: "就在这时——" "他还来不及反应——"
- 威胁预告: "危险正在靠近，而他一无所知。"
- 数量: 每300-500字至少1个句级钩子

## 什么是段级钩子（每3-5段一个）
- 段落结尾留悬念或未解之谜
- 突然出现的变量
- 角色做出意外的选择

## 改写规则
- 保留原有人物、情节、世界观100%不变
- 只在段落衔接处和段落结尾处插入钩子句子
- 不要改变原有情节走向
- 改写后字数应与原文接近

## 禁止
- 不要在每段都加钩子（过度紧张）
- 不要改变叙事视角
- 不要添加新的剧情线"""

    user = f"请在原文基础上增加句级和段级钩子。直接输出改写后的正文，不要前言后记。\n\n--- 原文 ---\n{text.strip()}"
    return _call(system, user)


# ============================================================
# PASS 2: 对话节奏 (傅里叶驱动)
# ============================================================

def pass2_dialogue(text: str, chapter_num: int, platform: str) -> str:
    """
    目标: 提升对话率 + 打破平铺节律
    - 将纯说明段落改为角色对话揭示信息
    - 对话率从当前水平提升到45%+
    """
    print("  [P2] 目标: 对话率 >45%，打破单调节律")

    system = f"""你是{platform}网文的章节改写专家。本轮你只做一件事：大幅提升对话占比，打破纯叙述。

## 具体操作
1. 找出所有超过3句的纯叙述/说明/内心独白段落
2. 将其改为角色之间的对话来传递同样的信息
3. 每段对话必须:
   - 推进情节 或 展示性格 或 建立关系 (三选一)
   - 有潜台词 (角色说的和想的可以不完全一致)
4. 对话中穿插简短的动作描写 (<8字)

## 对话节奏
- 快节奏: 短句对答 (每句≤15字，针锋相对)
- 慢节奏: 长句独白 (揭示世界观/回忆/计划，用于关键信息点)
- 交替使用，避免连续10句以上同节奏

## 改写规则
- 保持原情节100%不变
- 不要改变已有的人物性格和关系
- 改写后字数与原文接近

## 禁止
- 废话对话 ("你来了""嗯""今天天气不错")
- 信息重复 (前文说过的不再对话复述)"""

    user = f"请改写本章，大幅增加对话占比，将叙述改为对话揭示信息。直接输出改写后的正文。\n\n--- 原文 ---\n{text.strip()}"
    return _call(system, user)


# ============================================================
# PASS 3: 情绪平衡 (积分学驱动)
# ============================================================

def pass3_emotion(text: str, chapter_num: int, platform: str) -> str:
    """
    目标: 修复正负情绪比
    - 每5段插入一个积极情绪点
    - 确保情绪有起伏弧线
    """
    print("  [P3] 目标: 正负情绪比从0:1 → >1:3，建立情绪弧线")

    system = f"""你是{platform}网文的章节改写专家。本轮你只做一件事：平衡正负情绪，建立情绪弧线。

## 当前问题
原文负面情绪过重，缺乏正向情绪点，读者会感到压抑疲劳。

## 具体操作
1. 每5个叙事段落插入一个积极情绪点，类型轮换:
   - 成就感: 角色完成了一个小目标/解锁了能力
   - 希望感: 出现了新的可能性/线索
   - 温暖感: 角色间的信任/默契瞬间
   - 幽默感: 一个意想不到的轻松时刻/反差
2. 确保积极情绪是"真实的"，不是廉价的——要服务剧情
3. 情绪弧线: 本章至少出现 紧张→希望→再紧张→小胜利 的波动

## 改写规则
- 保留原有人物性格 (悲观的角色不会突然乐观，但可以"看到一丝希望")
- 积极点必须是情节有机部分，不能硬塞
- 改写后字数与原文接近

## 禁止
- 无脑正能量 ("一切都会好起来的")
- 破坏紧张氛围 (悬疑场景不要插笑话)
- 角色性格突变"""

    user = f"请改写本章，在不破坏原有紧张感的前提下，增加真实的积极情绪点。直接输出正文。\n\n--- 原文 ---\n{text.strip()}"
    return _call(system, user)


# ============================================================
# PASS 4: 动作密度 (马尔可夫驱动)
# ============================================================

def pass4_action(text: str, chapter_num: int, platform: str) -> str:
    """
    目标: 降exposition + 增action/climax
    - 将世界观说明改为角色通过行动发现
    - 减少纯说明段落
    """
    print("  [P4] 目标: exposition从 >50% → <40%，action/climax >15%")

    system = f"""你是{platform}网文的章节改写专家。本轮你只做一件事：减少世界观铺陈，增加角色主动行动。

## 具体操作
1. 找出所有"说明性段落" (解释世界观/系统规则/背景设定)
2. 将说明改为: 角色通过行动、实验、试探来发现规则
   例: 不说"这个空间站有重力系统"，而写"他按下按钮，身体猛地一沉——重力场启动了"
3. 确保主角始终在"做"而非"想":
   - 主角的每一个想法都要立刻转化为行动
   - 内心独白不超过2句
4. 增加对手/环境的主动对抗:
   - 给主角的每个行动制造1-2个小障碍
   - 障碍不要重复

## 改写规则
- 情节走向100%不变
- 核心信息不丢失 (说明文字中的世界设定通过行动重述)
- 改写后字数与原文接近

## 禁止
- 动作描写空洞 ("他快速移动" → 应该说"他翻身滚过走廊")
- 为动作而动作 (每个动作要有叙事目的)"""

    user = f"请改写本章，将说明改为行动，减少世界观铺陈。直接输出正文。\n\n--- 原文 ---\n{text.strip()}"
    return _call(system, user)


# ============================================================
# PASS 5: 润色整合
# ============================================================

def pass5_polish(text: str, chapter_num: int, platform: str) -> str:
    """
    目标: 全局润色 + 去AI模板味 + 平台格式统一
    """
    print("  [P5] 目标: 全局润色，去AI模板味，统一平台格式")

    platform_rules = {
        "qimao": "段落≤3行, 句均≤18字, 对话率≥45%, 一章一高潮",
        "fanqie": "段落≤3行, 句均≤15字, 对话率≥40%, 300字内出冲突",
        "qidian": "段落≤5行, 句均≤25字, 对话率≥30%, 逻辑严密",
    }
    rule = platform_rules.get(platform, platform_rules["qimao"])

    system = f"""你是{platform}网文的终审编辑。本轮做最后的润色。

## 平台格式 ({platform})
{rule}

## 去AI味检查
禁止以下词汇，如果出现必须替换:
- "瞳孔骤然收缩" / "倒吸一口凉气" / "嘴角勾起一抹冷笑"
- "眼中闪过一丝" / "二话不说" / "话音刚落"
- "令人窒息的" / "不可思议的" / "难以言喻的"
- 任何"他的内心充满了……"类模板

## 感官检查
- 每个场景至少3种感官 (视+听+触/嗅/味)

## 改写规则
- 只做微调: 换词、调句式、修格式
- 不改变情节和结构
- 改写后字数与原文接近"""

    user = f"请做最终润色: 去AI模板味、修平台格式、感官补全。直接输出正文。\n\n--- 原文 ---\n{text.strip()}"
    return _call(system, user)


# ============================================================
# 引擎
# ============================================================

def _call(system: str, user: str) -> str:
    """调用AI"""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for attempt in range(3):
        try:
            if attempt > 0:
                print(f"    重试 {attempt}/3...")
            response = requests.post(
                f"{API_BASE}/chat/completions",
                json={"model": API_MODEL, "messages": messages,
                      "temperature": API_TEMP, "max_tokens": API_MAX_TOKENS},
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                timeout=API_TIMEOUT,
            )
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # 清理
                for prefix in ["好的", "没问题", "以下是我", "这是"]:
                    content = re.sub(rf'^{prefix}.*?正文[：:]?\s*', '', content)
                return content.strip()
            else:
                print(f"    API错误: {response.status_code}")
        except Exception as e:
            print(f"    调用异常: {e}")
    return None


def _diagnose_dimension(text: str, chapter_num: int, pass_name: str) -> dict:
    """单维度诊断"""
    try:
        from pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        full = engine.full_analysis(text, chapter_num)

        if pass_name == "P1":
            lp = full.get("laplace_analysis", {})
            bands = lp.get("frequency_bands", {})
            return {
                "score": lp.get("hook_health_score", 0),
                "summary": lp.get("summary", ""),
                "short_term_pct": round(bands.get("short_term", 0) * 100),
                "mid_term_pct": round(bands.get("mid_term", 0) * 100),
                "long_term_pct": round(bands.get("long_term", 0) * 100),
            }
        elif pass_name == "P2":
            # 估算对话率（支持中英文引号）
            dialogue_lines = len(re.findall(r'[""\u201c\u201d\u300c\u300d][^""\u201c\u201d\u300c\u300d]+[""\u201c\u201d\u300c\u300d]', text))
            all_sents = max(len(re.split(r'[。！？!?\n]+', text)), 1)
            dialogue_ratio = dialogue_lines / all_sents * 100 if all_sents > 0 else 0
            ft = full.get("fourier_analysis", {}).get("emotion_spectrum", {})
            return {
                "dialogue_ratio": round(dialogue_ratio, 1),
                "rhythm_type": ft.get("rhythm_type", "未知"),
                "rhythm_diagnosis": ft.get("rhythm_diagnosis", ""),
            }
        elif pass_name == "P3":
            integral = full.get("integral_analysis", {}).get("emotional_arc", {})
            return {
                "arc_shape": integral.get("arc_shape", "未知"),
                "pos_neg_ratio": integral.get("pos_neg_ratio", 0),
                "arc_area": integral.get("arc_area", 0),
                "tv": integral.get("total_variation", 0),
            }
        elif pass_name == "P4":
            mc = full.get("markov_chain", {})
            dist = mc.get("state_distribution", {})
            return {
                "chain_health": mc.get("chain_health", "未知"),
                "exposition_pct": round(dist.get("exposition", 0) * 100),
                "action_pct": round(dist.get("action", 0) * 100),
                "climax_pct": round(dist.get("climax", 0) * 100),
                "dialogue_pct": round(dist.get("dialogue", 0) * 100),
            }
        elif pass_name == "P5":
            return {"math_score": full.get("overall_math_score", 0)}
    except Exception as e:
        return {"error": str(e)}


def _format_dim(d: dict, pass_name: str) -> str:
    """格式化维度诊断"""
    if pass_name == "P1":
        return "钩子: 短期%.0f%% 中期%.0f%% 长期%.0f%% — %s" % (
            d.get("short_term_pct", 0), d.get("mid_term_pct", 0),
            d.get("long_term_pct", 0), d.get("summary", "?"))
    elif pass_name == "P2":
        return "对话率%.1f%% 节律:%s" % (d.get("dialogue_ratio", 0), d.get("rhythm_type", "?"))
    elif pass_name == "P3":
        return "弧线:%s 正负比:%.1f" % (d.get("arc_shape", "?"), d.get("pos_neg_ratio", 0))
    elif pass_name == "P4":
        return "expo:%.0f%% action:%.0f%% climax:%.0f%% -> %s" % (
            d.get("exposition_pct", 0), d.get("action_pct", 0),
            d.get("climax_pct", 0), d.get("chain_health", "?"))
    elif pass_name == "P5":
        return "数学评分:%.1f" % d.get("math_score", 0)
    return str(d)


# ============================================================
# 主流程
# ============================================================

def multi_pass_rewrite(project_name: str, chapter_num: int, platform: str = "qimao") -> dict:
    """分维度迭代改写单章"""

    project_dir = PROJECTS_ROOT / project_name / "正文"

    # 找原文件
    orig_file = None
    for f in sorted(project_dir.glob("第%d章*.txt" % chapter_num)):
        if "重写" not in f.name and "multi_pass" not in f.name and "\u91cd\u5199" not in f.name:
            orig_file = f
            break
    if not orig_file:
        return {"error": "找不到第%d章原文件" % chapter_num}

    text = orig_file.read_text(encoding='utf-8').strip()
    orig_wc = len(re.sub(r'\s', '', text))

    print(f"\n{'='*60}")
    print(f"  分维度迭代改编写 — {project_name} 第{chapter_num}章")
    print(f"  平台:{platform} | 原始:{orig_wc}字")
    print(f"{'='*60}")

    # 初始诊断
    print("\n[初始诊断]")
    try:
        from pangu_math_core import PanguMathEngine
        engine = PanguMathEngine()
        init_full = engine.full_analysis(text, chapter_num)
        init_score = init_full.get("overall_math_score", 0)
        print("  数学评分: %.1f/100" % init_score)
    except Exception as e:
        init_score = 0
        print("  初始诊断失败: %s" % e)

    # 维度追踪
    passes = [
        ("P1", "钩子密度", pass1_hooks),
        ("P2", "对话节奏", pass2_dialogue),
        ("P3", "情绪平衡", pass3_emotion),
        ("P4", "动作密度", pass4_action),
        ("P5", "润色整合", pass5_polish),
    ]

    current_text = text
    trail = []

    for pass_id, pass_label, pass_fn in passes:
        print("\n[%s] %s" % (pass_id, pass_label))

        # 改前诊断
        before_dim = _diagnose_dimension(current_text, chapter_num, pass_id)
        before_str = _format_dim(before_dim, pass_id)
        print("  改前: %s" % before_str)

        # 执行改写
        rewritten = pass_fn(current_text, chapter_num, platform)
        if not rewritten:
            print("  [SKIP] 本轮改写失败，保留当前文本")
            continue

        # 改后诊断
        after_dim = _diagnose_dimension(rewritten, chapter_num, pass_id)
        after_str = _format_dim(after_dim, pass_id)
        print("  改后: %s" % after_str)
        print("  字数: %d -> %d" % (len(re.sub(r'\s', '', current_text)), len(re.sub(r'\s', '', rewritten))))

        # 保存本轮结果
        rw_wc = len(re.sub(r'\s', '', rewritten))
        timestamp = datetime.now().strftime("%H%M%S")
        saved = project_dir / ("第%d章_%s_%s_%s.txt" % (chapter_num, pass_id, pass_label, timestamp))
        saved.write_text(rewritten, encoding='utf-8')

        trail.append({
            "pass": pass_id,
            "label": pass_label,
            "before": before_str,
            "after": after_str,
            "word_count": rw_wc,
            "saved": str(saved),
        })

        current_text = rewritten
        time.sleep(0.5)

    # 最终诊断
    print("\n[最终诊断]")
    try:
        final_full = engine.full_analysis(current_text, chapter_num)
        final_score = final_full.get("overall_math_score", 0)
        final_wc = len(re.sub(r'\s', '', current_text))
        print("  数学评分: %.1f -> %.1f (%+.1f)" % (init_score, final_score, final_score - init_score))
        print("  字数: %d -> %d" % (orig_wc, final_wc))
    except Exception as e:
        final_score = 0
        print("  最终诊断失败: %s" % e)

    # 保存终稿
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_path = project_dir / ("第%d章_multi_pass_final_%s.txt" % (chapter_num, timestamp))
    header = "# 盘古AI 分维度迭代改编写 (5轮递进)\n"
    header += "# 日期: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M")
    header += "# 原始字数: %d | 最终字数: %d\n" % (orig_wc, final_wc)
    header += "# 原始评分: %.1f | 最终评分: %.1f\n" % (init_score, final_score)
    header += "# 迭代路径:\n"
    for t in trail:
        header += "#   %s -> %s\n" % (t["pass"], t["after"])
    header += "-" * 40 + "\n\n"
    final_path.write_text(header + current_text, encoding='utf-8')

    return {
        "project": project_name,
        "chapter": chapter_num,
        "word_count_before": orig_wc,
        "word_count_after": final_wc,
        "score_before": init_score,
        "score_after": final_score,
        "score_delta": final_score - init_score,
        "trail": trail,
        "final_path": str(final_path),
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) < 2:
        print("用法:")
        print("  python multi_pass_rewrite.py <项目名> <章节号> [平台] [-y]")
        print("  python multi_pass_rewrite.py <项目名> --all [平台] [-y]")
        print()
        print("示例:")
        print('  python multi_pass_rewrite.py "末世：我有一座外星空间站" 1 qimao -y')
        print('  python multi_pass_rewrite.py "末世：我有一座外星空间站" --all -y')
        sys.exit(0)

    project_name = args[0]

    platform = "qimao"
    auto_confirm = False

    for arg in args[1:]:
        if arg in ("qimao", "fanqie", "qidian"):
            platform = arg
        elif arg == "-y":
            auto_confirm = True

    if "--all" in args:
        # 批量
        body = PROJECTS_ROOT / project_name / "正文"
        ch_files = sorted([
            f for f in body.glob("第*章*.txt")
            if "重写" not in f.name and "multi_pass" not in f.name and "\u91cd\u5199" not in f.name
        ], key=lambda f: int(re.search(r'第(\d+)章', f.name).group(1)) if re.search(r'第(\d+)章', f.name) else 999)

        if not ch_files:
            print("[FAIL] 无章节文件")
            sys.exit(1)

        total = len(ch_files)
        print("=" * 60)
        print("  分维度批量改编写: %s (%d章)" % (project_name, total))
        print("=" * 60)

        all_results = []
        total_before = 0
        total_after = 0

        for i, f in enumerate(ch_files, 1):
            ch_num = int(re.search(r'第(\d+)章', f.name).group(1))
            print("\n[%d/%d]" % (i, total))
            result = multi_pass_rewrite(project_name, ch_num, platform)
            if "error" in result:
                print("  [SKIP] %s" % result["error"])
                continue
            all_results.append(result)
            total_before += result["score_before"]
            total_after += result["score_after"]
            if i < total:
                time.sleep(1)

        n = len(all_results)
        print("\n" + "=" * 60)
        print("  批量改编写完成")
        print("=" * 60)
        print("  完成: %d/%d章" % (n, total))
        if n > 0:
            avg_b = total_before / n
            avg_a = total_after / n
            print("  均分: %.1f -> %.1f (%+.1f)" % (avg_b, avg_a, avg_a - avg_b))
            for r in all_results:
                delta = r["score_delta"]
                sign = "+" if delta >= 0 else ""
                print("  第%d章: %.1f -> %.1f (%s%.1f) | %d->%d字" % (
                    r["chapter"], r["score_before"], r["score_after"],
                    sign, delta,
                    r["word_count_before"], r["word_count_after"]))
    else:
        chapter_num = int(args[1])
        result = multi_pass_rewrite(project_name, chapter_num, platform)
        if "error" in result:
            print("[FAIL] %s" % result["error"])
            sys.exit(1)
        print("\n" + "=" * 60)
        print("  分维度改编写完成")
        print("=" * 60)
        print("  分数: %.1f -> %.1f (%+.1f)" % (result["score_before"], result["score_after"], result["score_delta"]))
        print("  字数: %d -> %d" % (result["word_count_before"], result["word_count_after"]))
        for t in result["trail"]:
            print("  %s: %s" % (t["pass"], t["after"]))
        print("  终稿: %s" % result["final_path"])
