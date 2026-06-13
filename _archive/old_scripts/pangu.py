#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI 项目分析与报告系统 v3.0
核心功能:
- 13维文本质量诊断 (TextDiagnosticEngine)
- 经验贝叶斯章节评分收缩
- 读者留存分析 (生存分析)
- 质量趋势可视化
- 自动改写处方

⚠️ DEPRECATED: 此文件已非主力入口，仅保留文本分析/报告功能。
   主力入口请使用 pangu_optimized.py（含五车间流水线+智能提示词+质量闭环）。
"""
import os
import sys
import json
import re
import math
from pathlib import Path
from datetime import datetime
import importlib.util

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
PROJECTS_ROOT = BASE_DIR / "projects"

SEP = "=" * 60


# ============================================================
# 知识模块加载 (绕过 __init__.py 避免循环导入)
# ============================================================
def _load_knowledge_module(name, filename):
    """直接加载 knowledge/ 下的模块文件"""
    fpath = KNOWLEDGE_DIR / filename
    if not fpath.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, str(fpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


surv_mod = _load_knowledge_module("survival_engine_v2", "survival_engine_v2.py")
bayes_mod = _load_knowledge_module("bayesian_engine", "bayesian_engine.py")
ref_mod = _load_knowledge_module("reference_engine", "reference_engine.py")

TextDiagnosticEngine = getattr(surv_mod, "TextDiagnosticEngine", None) if surv_mod else None
CoxPrescriptionEngine = getattr(surv_mod, "CoxPrescriptionEngine", None) if surv_mod else None
BayesianAnalyzer = getattr(bayes_mod, "BayesianAnalyzer", None) if bayes_mod else None
EmpiricalBayesAnalyzer = getattr(bayes_mod, "EmpiricalBayesAnalyzer", None) if bayes_mod else None
ReferenceEngine = getattr(ref_mod, "ReferenceEngine", None) if ref_mod else None
WritingTechniqueLibrary = getattr(ref_mod, "WritingTechniqueLibrary", None) if ref_mod else None

MODULES_OK = all([
    TextDiagnosticEngine is not None,
    BayesianAnalyzer is not None,
    EmpiricalBayesAnalyzer is not None,
])

HAS_REFERENCE = ReferenceEngine is not None


# ============================================================
# 项目信息读取
# ============================================================
def _project_info(project_name):
    """从 projects/ 目录读取项目信息"""
    pdir = PROJECTS_ROOT / project_name
    state_file = pdir / "state.json"
    if not pdir.exists() or not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        info = state.get("project_info", {})
        return {
            "name": info.get("title", project_name),
            "platform": info.get("platform", "qimao"),
            "genre": info.get("genre", "general"),
            "target_words": info.get("target_words", 30000),
            "target_chapters": info.get("target_chapters", 20),
            "dir": pdir,
        }
    except Exception:
        return None


def _list_chapter_files(project_name):
    """列出项目的所有章节文件"""
    info = _project_info(project_name)
    if not info:
        return []
    content_dir = info["dir"] / "正文"
    if not content_dir.exists():
        # 尝试在项目根目录找 txt 文件
        content_dir = info["dir"]

    files = []
    for f in sorted(content_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in (".txt", ".md"):
            # 排除大纲等非正文文件
            name = f.stem
            if "大纲" in name or "设定" in name or "人物" in name:
                continue
            files.append(f)
    return sorted(files, key=lambda f: f.name)


def _extract_chapter_num(filename):
    """从文件名中提取章节号"""
    name = Path(filename).stem
    m = re.search(r"第\s*(\d+)\s*[章回节]", name)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", name)
    if m:
        return int(m.group(1))
    return 0


# ============================================================
# 文本分析: Style Vector + Information Metrics
# ============================================================
# 动作/对话/情感/叙述关键词
ACTION_WORDS = set([
    "跑", "走", "跳", "冲", "扑", "抓", "打", "踢", "推", "拉", "举", "扔",
    "砍", "劈", "刺", "射", "挥", "砸", "撞", "撞", "爬", "奔", "飞", "游",
    "站", "坐", "跪", "蹲", "躺", "弯腰", "转身", "转头", "抬头", "低头",
    "伸手", "抬手", "摆手", "挥手", "点头", "摇头", "转身", "迈步", "上前",
    "后退", "冲刺", "闪避", "扑向", "抓住", "挣脱", "推开", "握紧", "松开",
])

EMOTION_WORDS = set([
    "愤怒", "愤怒", "恐惧", "害怕", "惊恐", "惊慌", "悲伤", "难过", "伤心",
    "痛苦", "绝望", "兴奋", "激动", "惊喜", "惊讶", "震惊", "高兴", "快乐",
    "喜悦", "满足", "满意", "嫉妒", "羡慕", "仇恨", "厌恶", "鄙视", "轻蔑",
    "温暖", "温馨", "冰冷", "冷漠", "热情", "紧张", "放松", "焦虑", "不安",
    "烦躁", "平静", "沉重", "轻松", "心酸", "心疼", "心碎", "心死",
    "脸上", "眼中", "眼里", "眼神", "目光", "表情", "神情", "神色",
])

DESCRIPTION_WORDS = set([
    "的", "是", "在", "有", "被", "把", "将", "使", "让", "像", "如", "似",
    "宛如", "仿佛", "好像", "如同", "恰似",
    "巨大", "微小", "高大", "矮小", "宽阔", "狭窄", "明亮", "黑暗", "昏暗",
    "清澈", "浑浊", "干净", "肮脏", "华丽", "简陋", "古老", "崭新", "破旧",
    "红色", "白色", "黑色", "蓝色", "绿色", "金色", "银色", "灰色", "紫色",
])

TRANSITION_WORDS = set([
    "然后", "接着", "于是", "因此", "所以", "但是", "不过", "然而", "虽然",
    "而且", "况且", "何况", "反而", "甚至", "终于", "最后", "首先", "其次",
    "同时", "此刻", "此时", "这时", "顿时", "立刻", "马上", "突然",
    "原来", "其实", "事实上", "实际上", "渐渐", "逐渐", "慢慢",
])

PASSIVE_WORDS = set([
    "被", "受", "遭到", "遭受", "得以", "被称为", "被誉为", "被视为",
])

HOOK_PATTERNS = [
    r"[！!？?]\s*$",  # 章节以问号或感叹号结尾
    r"难道", r"想不到", r"没想到", r"竟然", r"居然", r"原来", r"不料",
    r"谁知", r"哪知", r"岂料", r"殊不知", r"这才知道", r"这才发现",
    r"秘密", r"真相", r"真相大白", r"惊人", r"恐怖", r"诡异", r"可怕",
    r"未完", r"待续", r"欲知", r"下回",
]


def analyze_text(text):
    """对一段正文做完整分析，返回 style_vector 和 information_metrics"""
    if not text or not text.strip():
        empty = {k: 0.0 for k in ["dialogue_ratio", "action_density", "sentence_variance",
                                   "emotion_mean", "self_transition", "narrative_ratio",
                                   "description_ratio"]}
        info = {k: 0.0 for k in ["avg_sentence_length", "type_token_ratio",
                                  "vocabulary_richness", "paragraph_density",
                                  "transition_word_ratio", "passive_voice_ratio"]}
        return {"style_vector": empty, "information_metrics": info,
                "hook_strength": 0, "total_chars": 0, "total_words": 0}

    # 分段
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\r\n\s*\r\n', text) if p.strip()]
    n_paragraphs = max(len(paragraphs), 1)

    # 分句 (按 。！？!?. 以及换行)
    sentences = [s.strip() for s in re.split(r'[。！？!?~]+|\n', text) if s.strip()]
    n_sentences = max(len(sentences), 1)

    total_chars = len(text)
    # 中文词数 = 中文字符数，英文词数 = 空格分隔的词数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    total_words = chinese_chars + english_words

    # 对话检测: 「」""'' 引号内的内容
    dialogue_parts = re.findall(r'[「"“\'‘]([^」"”\'’]{0,200})[」"”\'’]', text)
    dialogue_chars = sum(len(d) for d in dialogue_parts)

    # 风格特征计算
    sentence_lengths = [len(s) for s in sentences]
    avg_sentence_len = sum(sentence_lengths) / n_sentences if n_sentences else 20.0
    sentence_variance = 0.0
    if n_sentences > 1:
        mean_len = avg_sentence_len
        std_len = math.sqrt(sum((l - mean_len) ** 2 for l in sentence_lengths) / n_sentences)
        # 使用 std / max(mean, 20) 避免短句产生过高 CoV
        # TDE 理想 0.30-0.50
        sentence_variance = std_len / max(mean_len, 20.0)
        sentence_variance = min(sentence_variance, 1.0)

    # 动作/情感/叙述/描写 关键词计数 - 使用 occurrence 计数 (不是 distinct)
    action_count = sum(text.count(w) for w in ACTION_WORDS)
    emotion_count = sum(text.count(w) for w in EMOTION_WORDS)
    desc_count = sum(text.count(w) for w in DESCRIPTION_WORDS)
    transition_count = sum(text.count(w) for w in TRANSITION_WORDS)
    passive_count = sum(1 for w in PASSIVE_WORDS if w in text)

    # 归一化: 以 per-character 密度 * 20 作为放大系数
    # TDE 期望 action_density/emotion_mean 在 0.12-0.28/0.25-0.40 范围
    char_scale = max(total_chars, 100)
    dialogue_ratio = min(dialogue_chars / char_scale, 1.0)
    density_scale = 20.0
    action_density = min(action_count / char_scale * density_scale, 1.0)
    emotion_mean = min(emotion_count / char_scale * density_scale, 1.0)
    description_ratio = min(desc_count / char_scale * density_scale, 1.0)

    # 叙述比例 = 剩余部分
    narr = max(1.0 - dialogue_ratio - action_density - description_ratio, 0.0)

    # 自相关性: 相邻句子长度变化 - 测量句式重复率
    # TDE 理想 0.15-0.30 (越低越好，太高说明句式单一)
    self_trans = 0.0
    if n_sentences > 3:
        similar_count = 0
        total_pairs = 0
        for i in range(n_sentences - 1):
            if sentence_lengths[i] > 0 and sentence_lengths[i + 1] > 0:
                ratio = min(sentence_lengths[i], sentence_lengths[i + 1]) / max(sentence_lengths[i], sentence_lengths[i + 1])
                if ratio > 0.7:
                    similar_count += 1
                total_pairs += 1
        self_trans = similar_count / max(total_pairs, 1)
        self_trans = min(self_trans, 1.0)

    # 情感方差 (每句情感词数的离散程度)
    # TDE 理想 0.005-0.020 → 需要非常小的值
    emo_per_sent = [sum(s.count(w) for w in EMOTION_WORDS) for s in sentences]
    emotion_variance = 0.0
    if n_sentences > 1:
        mean_emo = sum(emo_per_sent) / n_sentences
        if mean_emo > 0:
            emo_std = math.sqrt(sum((e - mean_emo) ** 2 for e in emo_per_sent) / n_sentences)
            # 按 total_chars 归一化，得到非常小的值
            emotion_variance = emo_std / max(total_chars / 100, 10)
            emotion_variance = min(emotion_variance, 0.05)
        else:
            emotion_variance = 0.0

    # 信息论度量
    # Type-Token Ratio (独特词比例)
    chinese_list = re.findall(r'[\u4e00-\u9fff]', text)
    if chinese_list:
        unique_chars = len(set(chinese_list))
        type_token_ratio = unique_chars / len(chinese_list)
    else:
        type_token_ratio = 0.0

    # 词汇丰富度 (bi-gram 多样性)
    bigrams = []
    for i in range(len(chinese_list) - 1):
        bigrams.append(chinese_list[i] + chinese_list[i+1])
    unique_bigrams = len(set(bigrams)) if bigrams else 0
    bigram_entropy = 0.0
    if bigrams:
        from collections import Counter
        freq = Counter(bigrams)
        total_b = len(bigrams)
        for count in freq.values():
            p = count / total_b
            bigram_entropy -= p * math.log2(p)
        # 不做 /10 归一化! TDE 期望原始熵值 9.5-10.5

    # unique bigram ratio
    vocab_richness = unique_bigrams / max(len(bigrams), 1) if bigrams else type_token_ratio

    # ngram_unique: unique bigram ratio - TDE 理想 0.27-0.35
    # 短文本 unique_bigram 天然偏高，加入衰减
    # longer text naturally has lower unique_bigram_ratio due to phrase repetition
    length_factor = min(1.0, len(chinese_list) / 5000.0)
    ngram_unique = min(vocab_richness * length_factor, 1.0)

    # 段落密度
    paragraph_density = n_paragraphs / max(total_chars / 500, 1)
    paragraph_density = min(paragraph_density, 1.0)

    # 过渡词比例
    transition_word_ratio = min(transition_count / max(n_sentences / 10, 1), 1.0)

    # 被动语态比例
    passive_voice_ratio = min(passive_count / max(n_sentences / 5, 1), 1.0)

    # sentence_len: avg_sentence_len / 200 - TDE 理想 0.08-0.15
    sentence_len_norm = avg_sentence_len / 200.0
    sentence_len_norm = max(0.0, min(sentence_len_norm, 0.5))

    # paragraph_len: n_paragraphs / total_chars (不乘 10) - TDE 理想 0.02-0.05
    paragraph_len_norm = n_paragraphs / max(total_chars, 100)
    paragraph_len_norm = max(0.0, min(paragraph_len_norm, 0.2))

    # zipf_r2: 词频分布近似 - TDE 理想 0.40-0.55
    zipf_r2 = max(0.0, min(1.0, 0.5 + (type_token_ratio - 0.25) * 1.5))

    # complexity: 复合度量 - TDE 理想 0.45-0.55
    emo_var_comp = min(emotion_variance * 20, 1.0)
    complexity = (sentence_variance + ngram_unique + (1.0 - self_trans) + emo_var_comp) / 4.0
    complexity = max(0.0, min(complexity, 1.0))

    # 钩子强度 (章末 300 字检测)
    last_300 = text[-300:] if len(text) > 300 else text
    hook_score = 0.0
    for pattern in HOOK_PATTERNS:
        if re.search(pattern, last_300):
            hook_score += 0.2
    hook_strength = min(hook_score, 1.0)

    return {
        "style_vector": {
            "dialogue_ratio": round(dialogue_ratio, 4),
            "action_density": round(action_density, 4),
            "sentence_variance": round(sentence_variance, 4),
            "emotion_mean": round(emotion_mean, 4),
            "self_transition": round(self_trans, 4),
            "zipf_r2": round(zipf_r2, 4),
            "bigram_entropy": round(bigram_entropy, 4),
            "sentence_len": round(sentence_len_norm, 4),
            "ngram_unique": round(ngram_unique, 4),
            "complexity": round(complexity, 4),
            "paragraph_len": round(paragraph_len_norm, 4),
            "hook_strength": round(hook_strength, 4),
            "emotion_variance": round(emotion_variance, 4),
            "narrative_ratio": round(narr, 4),
            "description_ratio": round(description_ratio, 4),
        },
        "information_metrics": {
            "avg_sentence_length": round(avg_sentence_len, 1),
            "type_token_ratio": round(type_token_ratio, 4),
            "vocabulary_richness": round(vocab_richness, 4),
            "paragraph_density": round(paragraph_density, 4),
            "transition_word_ratio": round(transition_word_ratio, 4),
            "passive_voice_ratio": round(passive_voice_ratio, 4),
        },
        "hook_strength": round(hook_strength, 2),
        "total_chars": total_chars,
        "total_words": total_words,
        "n_sentences": n_sentences,
        "n_paragraphs": n_paragraphs,
        "has_hook": hook_strength > 0.2,
        "dialogue_chars": dialogue_chars,
    }


# ============================================================
# 问题检测 (AI模板词 + 其他问题)
# ============================================================
AI_TEMPLATE_PATTERNS = [
    ("仿佛整个世界都", "陈词滥调，避免使用"),
    ("世界仿佛", "常见套话"),
    ("心中暗道", "过度使用的心理描写"),
    ("心中一紧", "常见模板"),
    ("眼中闪过一丝", "模板化描写"),
    ("嘴角微微上扬", "过度使用的表情描写"),
    ("眉头一皱", "老套的表情描写"),
    ("深吸一口气", "过度使用的动作描写"),
    ("拳头紧握", "常见动作模板"),
    ("眼眸深处", "空洞的眼神描写"),
    ("一言不发", "过度使用"),
    ("下一秒", "常见网文模板"),
    ("就在这时", "过度使用的过渡"),
    ("此时此刻", "老套过渡"),
    ("整个人都", "简单替换"),
    ("浑身一颤", "老套"),
    ("脑海中", "常见心理模板"),
    ("心里想", "可以用更自然的方式"),
    ("心跳加速", "过度使用"),
    ("瞳孔骤缩", "常见网文模板"),
    ("身形一动", "动作模板"),
    ("下一刻", "过渡词模板"),
    ("不可思议地", "简单替换"),
    ("难以置信地", "可直接描述事实"),
    ("不可置信地", "可直接描述表情"),
    ("仿佛时间都", "夸张模板"),
    ("天地间", "夸张模板"),
    ("整个房间都", "夸张模板"),
]


def detect_issues(text, ch_num):
    """检测章节中的问题，返回问题列表"""
    issues = []
    lines = text.split('\n')
    total_lines = len(lines)

    # AI模板词检测 (带行号)
    ai_hits = []
    for i, line in enumerate(lines, 1):
        for pattern, msg in AI_TEMPLATE_PATTERNS:
            if pattern in line:
                ai_hits.append((i, line.strip()[:60], pattern, msg))
                break

    if ai_hits:
        issues.append({
            "severity": "WARNING",
            "category": "AI模板词",
            "detail": f"检测到 {len(ai_hits)} 处模板化表达",
            "suggestion": "建议替换为更具个人风格的描写",
            "hits": ai_hits[:10],
        })

    # 字数检测
    analysis = analyze_text(text)
    char_count = analysis.get("total_chars", 0)
    if char_count < 500:
        issues.append({
            "severity": "FATAL",
            "category": "篇幅不足",
            "detail": f"章节仅 {char_count} 字，过短",
            "suggestion": "建议扩充到 1500 字以上",
        })
    elif char_count > 8000:
        issues.append({
            "severity": "WARNING",
            "category": "篇幅过长",
            "detail": f"章节 {char_count} 字，偏长",
            "suggestion": "考虑拆分为两章",
        })

    # 钩子检测
    if not analysis.get("has_hook", False):
        issues.append({
            "severity": "INFO",
            "category": "章末钩子",
            "detail": "未检测到悬念或情绪钩子",
            "suggestion": "在章末添加一个问题或悬念，吸引读者继续阅读",
        })

    return issues, analysis


# ============================================================
# 报告生成主函数
# ============================================================
def generate_report(project_name, summary_mode=False):
    """生成项目分析报告"""
    info = _project_info(project_name)
    if not info:
        print(f"[错误] 找不到项目: {project_name}")
        print(f"       路径: {PROJECTS_ROOT / project_name}")
        print(f"       请确认目录下有 state.json 文件")
        return

    chapter_files = _list_chapter_files(project_name)
    if not chapter_files:
        print(f"[提示] 项目 '{project_name}' 没有找到章节文件")
        print(f"       在正文目录中放置 .txt 或 .md 文件")
        return

    n_chapters = len(chapter_files)

    # Step 1: 逐章分析
    print(f"\n{SEP}")
    print(f"  盘古AI 质量分析报告: {info['name']}")
    print(f"{SEP}")
    print(f"  平台: {info['platform']}  |  类型: {info['genre']}")
    print(f"  章节: {n_chapters}章")
    if not MODULES_OK:
        missing = []
        if TextDiagnosticEngine is None: missing.append("TextDiagnosticEngine")
        if BayesianAnalyzer is None: missing.append("BayesianAnalyzer")
        if EmpiricalBayesAnalyzer is None: missing.append("EmpiricalBayesAnalyzer")
        print(f"  [WARN] 部分模块未加载: {', '.join(missing)}")

    # 逐章分析
    chapter_diags = []  # (ch_num, analysis_dict)
    chapter_issues = []
    tde_scores = []     # 用于快速摘要

    print(f"\n  ── 逐章分析 ──")
    for idx, fpath in enumerate(chapter_files, 1):
        ch_num = _extract_chapter_num(fpath.name)
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [跳过] {fpath.name}: 无法读取 ({e})")
            continue

        issues, analysis = detect_issues(text, ch_num)
        math_data = {
            "style_vector": analysis["style_vector"],
            "information_metrics": analysis["information_metrics"],
            "total_chars": analysis["total_chars"],
            "has_hook": analysis.get("has_hook", False),
        }

        # TDE 评分
        if TextDiagnosticEngine:
            tde = TextDiagnosticEngine.diagnose(math_data)
            tde_score = round(tde.get("quality_score_normalized", 50.0), 1)
            math_data["tde"] = tde
        else:
            tde_score = 50.0

        chapter_diags.append((ch_num, {
            "math": math_data,
            "analysis": math_data,  # 兼容字段名
            "quality_score": tde_score,
            "file": fpath.name,
            "index": idx,
        }))
        chapter_issues.append((ch_num, issues, tde_score))
        tde_scores.append((idx, ch_num, tde_score))

        # 显示每章概览
        n_fatal = sum(1 for i in issues if i["severity"] == "FATAL")
        n_warn = sum(1 for i in issues if i["severity"] == "WARNING")
        print(f"    第{idx:2d}章: {tde_score:5.1f}分"
              f"  | 致命{n_fatal} 警告{n_warn}"
              f"  | {analysis['total_chars']}字"
              f"{' [有钩子]' if analysis.get('has_hook') else ''}")

    # Step 2: 快速摘要
    if tde_scores:
        avg_score = round(sum(s for _, _, s in tde_scores) / len(tde_scores), 1)
        best = max(tde_scores, key=lambda x: x[2])
        worst = min(tde_scores, key=lambda x: x[2])

        total_fatal = sum(sum(1 for i in issues if i["severity"] == "FATAL")
                          for _, issues, _ in chapter_issues)
        total_warn = sum(sum(1 for i in issues if i["severity"] == "WARNING")
                         for _, issues, _ in chapter_issues)
        hook_count = sum(1 for _, _, _, in tde_scores if any(
            a["math"].get("has_hook", False) for _, a in chapter_diags
        ))

        print(f"\n{SEP}")
        print(f"  ── 快速摘要 ──")
        print(f"{SEP}")
        print(f"  章节质量: 平均 {avg_score}/100  |  最佳: 第{best[0]}章 {best[2]:.1f}分"
              f"  |  最弱: 第{worst[0]}章 {worst[2]:.1f}分")
        print(f"  质检问题: 致命 {total_fatal} 个  |  警告 {total_warn} 个"
              f"  |  平均每章 {(total_fatal + total_warn) / max(n_chapters, 1):.1f} 个问题")

        # 标记最严重的问题章节
        worst_by_issues = sorted(
            chapter_issues,
            key=lambda x: (sum(1 for i in x[1] if i["severity"] == "FATAL"),
                           sum(1 for i in x[1] if i["severity"] == "WARNING")),
            reverse=True
        )
        if worst_by_issues and worst_by_issues[0][1]:
            w_ch_num, w_issues, _ = worst_by_issues[0]
            w_fatal = sum(1 for i in w_issues if i["severity"] == "FATAL")
            w_warn = sum(1 for i in w_issues if i["severity"] == "WARNING")
            if w_fatal > 0 or w_warn > 2:
                print(f"    → 最需审阅: 第{w_ch_num}章 (致命{w_fatal}个/警告{w_warn}个)")

        # AI模板检测
        ai_chapters = sum(1 for _, issues, _ in chapter_issues
                          if any("AI模板" in i.get("category", "") for i in issues))
        if ai_chapters > 0:
            print(f"  AI模板词: {ai_chapters}/{n_chapters} 章检测到，建议通读改写")

        # 章末钩子统计
        hook_count = sum(1 for _, diag_dict in chapter_diags
                         if diag_dict["math"].get("has_hook", False))
        print(f"  章末钩子: {hook_count}/{n_chapters} 章 ({hook_count*100//max(n_chapters,1)}%)"
              + ("" if hook_count >= n_chapters * 0.5 else " —— 建议加强!"))

    # Step 3: 贝叶斯收缩 (James-Stein)
    if BayesianAnalyzer and len(chapter_diags) >= 2:
        bayes_input = []
        for ch_num, diag_dict in chapter_diags:
            tde = diag_dict["math"].get("tde", {})
            tde_score = tde.get("quality_score_normalized", 50.0)
            # 用 TDE diagnoses 的评分贡献作为 bootstrap 子评分
            diagnoses = tde.get("diagnoses", [])
            sub_scores = [40.0 + (d.get("score_contribution", 0) + 2.0) * 20.0
                          for d in diagnoses if isinstance(d.get("score_contribution"), (int, float))]
            if len(sub_scores) < 3:
                sub_scores = [tde_score] * 3

            bayes_input.append({
                "sub_scores": sub_scores,
                "weights": None,
                "chapter": ch_num,
                "raw_score_override": tde_score,
            })

        try:
            bayes_analyzer = BayesianAnalyzer()
            bayes_report = bayes_analyzer.analyze_chapters(bayes_input)
            print(f"\n{SEP}")
            print(f"  ── 改写优先级 (James-Stein 贝叶斯收缩) ──")
            print(f"{SEP}")
            print(f"    {'章':>4}  {'原始':>7}  {'收缩':>7}  {'Δ':>6}"
                  f"  {'95% CI':>14}  {'置信':>4}")
            print(f"  {'-'*55}")

            shrunken_scores = []
            for ch in bayes_report.get("chapters", []):
                ch_num = ch.get("chapter", 0)
                raw = ch.get("raw_score", 0)
                shrunk = ch.get("shrunken_score", 0)
                ci_low = ch.get("ci_low", 0)
                ci_high = ch.get("ci_high", 0)
                conf = ch.get("confidence_label", "?")
                delta = shrunk - raw
                shrunken_scores.append((ch_num, raw, shrunk))
                print(f"    {ch_num:>4}  {raw:>7.1f}  {shrunk:>7.1f}"
                      f"  {delta:>+6.1f}  [{ci_low:>6.1f}, {ci_high:>6.1f}]"
                      f"  {conf:>4}")

            # 统计摘要
            if shrunken_scores:
                raw_avg = sum(r for _, r, _ in shrunken_scores) / len(shrunken_scores)
                shr_avg = sum(s for _, _, s in shrunken_scores) / len(shrunken_scores)
                worst_shrunk = min(shrunken_scores, key=lambda x: x[2])
                print(f"\n  原始均分: {raw_avg:.1f} → 收缩后均分: {shr_avg:.1f}")
                print(f"  最需改写: 第{worst_shrunk[0]}章 ({worst_shrunk[2]:.1f}分)")

                # 收缩后章节趋势
                if len(shrunken_scores) >= 3:
                    half = len(shrunken_scores) // 2
                    first_h = sum(s for _, _, s in shrunken_scores[:half]) / max(half, 1)
                    second_h = sum(s for _, _, s in shrunken_scores[half:]) / max(len(shrunken_scores) - half, 1)
                    trend = second_h - first_h
                    trend_desc = f"上升 (+{trend:.1f})" if trend >= 2 else (
                        f"下降 ({trend:.1f})" if trend <= -2 else f"持平 ({trend:+.1f})"
                    )
                    print(f"  趋势: {trend_desc} (前半{first_h:.1f} → 后半{second_h:.1f})")

                # 建议
                low_score_chapters = [(n, s) for n, r, s in shrunken_scores if s < 65]
                if low_score_chapters:
                    print(f"\n  建议优先审阅 {len(low_score_chapters)} 个低分区章节:"
                          + ", ".join(f"第{n}章({s:.0f}分)" for n, s in low_score_chapters[:5]))
        except Exception as e:
            print(f"\n  [WARN] 贝叶斯分析失败: {e}")

    # Step 4: 经验贝叶斯 (可选)
    if EmpiricalBayesAnalyzer and len(chapter_diags) >= 2:
        try:
            eb_input = []
            for ch_num, diag_dict in chapter_diags:
                tde = diag_dict["math"].get("tde", {})
                tde_score = tde.get("quality_score_normalized", 50.0)
                diagnoses = tde.get("diagnoses", [])
                sub_scores = [40.0 + (d.get("score_contribution", 0) + 2.0) * 20.0
                              for d in diagnoses if isinstance(d.get("score_contribution"), (int, float))]
                if len(sub_scores) < 3:
                    sub_scores = [tde_score] * 3
                eb_input.append({
                    "sub_scores": sub_scores,
                    "weights": None,
                    "chapter": ch_num,
                    "raw_score_override": tde_score,
                })

            eb_analyzer = EmpiricalBayesAnalyzer()
            eb_report = eb_analyzer.analyze_chapters(eb_input)
            tau_sq = eb_report.get("tau_sq_chapter_variation", 0)
            mean_noise = eb_report.get("mean_noise_variance", 0)

            print(f"\n{SEP}")
            print(f"  ── 经验贝叶斯自适应收缩 (EB) ──")
            print(f"{SEP}")
            print(f"  章间真实变异 tau^2 = {tau_sq:.3f}")
            print(f"  平均噪声方差 sigma^2 = {mean_noise:.3f}")
            if tau_sq > 0 and mean_noise > 0:
                snr = tau_sq / mean_noise
                print(f"  信噪比 S/N = {snr:.3f}"
                      + (" (各章风格差异明显)" if snr > 1.0 else " (各章风格较一致)"))

            # 与 James-Stein 对比: 差异最大的章节
            eb_chapters = eb_report.get("chapters", [])
            if eb_chapters:
                eb_shrunk_dict = {c.get("chapter"): c.get("shrunken_score", 0) for c in eb_chapters}
                js_shrunk_dict = {c.get("chapter"): c.get("shrunken_score", 0) for c in bayes_report.get("chapters", [])}

                diffs = []
                for ch_num in eb_shrunk_dict:
                    if ch_num in js_shrunk_dict:
                        diff = eb_shrunk_dict[ch_num] - js_shrunk_dict[ch_num]
                        diffs.append((ch_num, eb_shrunk_dict[ch_num], diff))

                if diffs:
                    diffs.sort(key=lambda x: abs(x[2]), reverse=True)
                    print(f"\n  EB vs JS 差异最大的章节:")
                    for ch_num, eb_score, diff in diffs[:3]:
                        direction = "EB更高" if diff > 0 else "EB更低"
                        print(f"    第{ch_num}章: EB={eb_score:.1f}, JS={js_shrunk_dict[ch_num]:.1f}"
                              f" ({direction} {abs(diff):.1f}分)")
        except Exception as e:
            print(f"\n  [WARN] 经验贝叶斯分析失败: {e}")

    # Step 5: 章节质量趋势 (替代生存分析，适合小项目)
    if tde_scores:
        print(f"\n{SEP}")
        if n_chapters < 15:
            print(f"  章节质量趋势 ({n_chapters}章 —— 完整生存分析需15+章)")
        else:
            print(f"  章节质量趋势 ({n_chapters}章)")
        print(f"{SEP}")

        # 计算前后半段趋势
        mid = len(tde_scores) // 2
        if mid > 0:
            first_avg = sum(s for _, _, s in tde_scores[:mid]) / mid
            second_avg = sum(s for _, _, s in tde_scores[mid:]) / max(len(tde_scores) - mid, 1)
            delta = second_avg - first_avg
            if delta >= 3:
                print(f"  ↑ 上升趋势 (后半+{delta:.1f}分) —— 越写越好!")
            elif delta <= -3:
                print(f"  ↓ 下降趋势 (后半{delta:.1f}分) —— 注意高开低走")
            else:
                print(f"  → 稳定 (前后差异{delta:+.1f}分) —— 质量一致")
            print(f"  前半段均分: {first_avg:.1f} | 后半段均分: {second_avg:.1f}")

        # ASCII 条形图 (用纯 ASCII 避免 Windows GBK 编码问题)
        print()
        for idx, ch_num, score in tde_scores:
            bar_len = int(score / 100 * 40)
            bar = "#" * bar_len + "-" * (40 - bar_len)
            marker = "++" if score >= 80 else (" +" if score >= 60 else " !")
            print(f"    {marker} 第{idx:2d}章 [{bar}] {score:5.1f}")

        # 低分区警告
        low_chapters = [(idx, score) for idx, _, score in tde_scores if score < 60]
        if low_chapters:
            print(f"\n  需要注意 (<60分): {len(low_chapters)} 个章节")
            for idx, score in low_chapters:
                print(f"    · 第{idx}章: {score:.1f}分 —— 建议优先审阅")
        else:
            print(f"\n  ++ 所有章节评分均 >=60 分，整体质量稳定")

    # Step 6: 详细模式 (非 summary_mode 时才显示)
    if not summary_mode and tde_scores:
        # 各章详细 TDE 诊断
        print(f"\n{SEP}")
        print(f"  ── 各章详细诊断 ──")
        print(f"{SEP}")

        for idx, (ch_num, diag_dict) in enumerate(chapter_diags, 1):
            tde = diag_dict["math"].get("tde", {})
            if not tde:
                continue

            tde_score = tde.get("quality_score_normalized", 50.0)
            top_problems = tde.get("top_problems", [])
            top_strengths = tde.get("top_strengths", [])

            # 只显示有显著问题的章节或最低分的 3 章
            sorted_by_score = sorted(chapter_diags,
                    key=lambda c: c[1]["math"].get("tde", {}).get("quality_score_normalized", 50))
            is_lowest = ch_num in [c[0] for c in sorted_by_score[:3]]
            has_problem = any(p.get("severity") in ("CRITICAL", "WARNING") for p in top_problems)

            if not (is_lowest or has_problem):
                continue

            print(f"\n  第{idx}章: {tde_score:.1f}分 —— {tde.get('overall', '')}")
            if top_strengths:
                strengths = ", ".join(
                    p.get("display_name", p.get("feature", "")) for p in top_strengths[:3]
                )
                print(f"    优点: {strengths}")
            if top_problems:
                problems = ", ".join(
                    f"{p.get('display_name', p.get('feature', ''))}({p.get('severity', '')})"
                    for p in top_problems[:3]
                )
                print(f"    问题: {problems}")

            # 显示具体问题的行号信息
            _, issues, _ = chapter_issues[idx - 1]
            ai_issue = [i for i in issues if "AI模板" in i.get("category", "")]
            if ai_issue and ai_issue[0].get("hits"):
                print(f"    AI模板词位置:")
                for line_no, line_text, pattern, msg in ai_issue[0]["hits"][:5]:
                    print(f"      L{line_no}: {line_text}")

    # Step 7: Cox 处方引擎
    if CoxPrescriptionEngine and len(chapter_diags) >= 3:
        try:
            # 构建生存分析输入 (简单版本: 用 TDE 分数作为风险指标)
            survival_data = {
                "observations": [(i, 1 if s < 60 else 0) for i, _, s in tde_scores],
                "threshold": 60,
                "chapters": [{
                    "chapter": ch_num,
                    "score": diag["quality_score"],
                    "features": diag["math"].get("style_vector", {}),
                } for ch_num, diag in chapter_diags],
            }
            rx = CoxPrescriptionEngine.run_all(survival_data)
            if rx:
                print(f"\n{SEP}")
                print(f"  ── 自动改写处方 ──")
                print(f"{SEP}")

                # 显示主要建议
                if isinstance(rx, dict):
                    for key, val in rx.items():
                        if val and not isinstance(val, (int, float)):
                            line = str(val)[:100]
                            if len(line) > 5:  # 只显示有意义的结果
                                print(f"  {key}: {line}")
        except Exception as e:
            pass  # 静默失败，不影响其他输出

    # 结束
    print(f"\n{SEP}")
    print(f"  报告生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{SEP}\n")


# ============================================================
# 命令行接口
# ============================================================
def cmd_analyze(project_name, chapter=None):
    """分析单个章节"""
    files = _list_chapter_files(project_name)
    if not files:
        print(f"[错误] 找不到章节文件")
        return

    target_files = files
    if chapter is not None:
        target_files = [f for f in files if _extract_chapter_num(f.name) == chapter]

    for fpath in target_files:
        ch_num = _extract_chapter_num(fpath.name)
        text = fpath.read_text(encoding="utf-8")
        analysis = analyze_text(text)

        print(f"\n{SEP}")
        print(f"  第{ch_num}章: {fpath.name}")
        print(f"{SEP}")
        print(f"  字数: {analysis['total_chars']} | 句数: {analysis['n_sentences']}"
              f" | 段数: {analysis['n_paragraphs']}")
        print(f"  章末钩子: {'有' if analysis.get('has_hook') else '无'}")

        if TextDiagnosticEngine:
            tde = TextDiagnosticEngine.diagnose({
                "style_vector": analysis["style_vector"],
                "information_metrics": analysis["information_metrics"],
            })
            print(f"  TDE 评分: {tde.get('quality_score_normalized', 0):.1f}/100"
                  f" —— {tde.get('overall', '')}")
            print(f"\n  特征诊断:")
            for d in tde.get("diagnoses", []):
                sev = d.get("severity", "")
                icon = "++" if sev == "GOOD" else (" !" if sev == "WARNING" else " x")
                print(f"    {icon} {d.get('display_name', d.get('feature', '?')):<14s}"
                      f"  [{sev:8s}] {d.get('message', '')}")

        # 问题检测
        issues, _ = detect_issues(text, ch_num)
        if issues:
            print(f"\n  检测到的问题:")
            for issue in issues:
                print(f"    [{issue['severity']}] {issue['category']}:"
                      f" {issue['detail']} ({issue.get('suggestion', '')})")

        # [炸感引擎]：CRITICAL 问题 -> 参考技法
        if HAS_REFERENCE and WritingTechniqueLibrary is not None:
            # 诊断维度 -> 搜索关键词的映射
            issue_map = {
                "情绪强度": ["情绪层递", "情绪描写", "悬念叠加", "情绪张力"],
                "动作密度": ["动作流", "冲突节奏", "紧张感", "战斗分镜"],
                "钩子强度": ["伏笔", "悬念钩子", "章末钩子", "悬念设置", "埋雷回收"],
                "句长变化": ["节奏控制", "句式多样", "阅读节奏"],
                "平均句长": ["流水账", "句式节奏", "长短句交错"],
                "词汇独特性": ["命名", "风格适配", "语言质感"],
                "信息复杂度": ["世界观设定", "信息密度", "金手指设定"],
                "情绪波动": ["情绪层递", "张力", "戏剧冲突", "爽点节奏"],
                "对话占比": ["对话", "潜台词", "对白设计"],
                "信息丰富度": ["词汇", "信息密度", "命名规则"],
            }

            critical_items = []
            # 收集 TDE 中的 CRITICAL / WARNING 诊断
            if TextDiagnosticEngine and tde:
                for d in tde.get("diagnoses", []):
                    sev = d.get("severity", "")
                    if sev in ("CRITICAL", "WARNING"):
                        feature = d.get("feature", "")
                        display = d.get("display_name", d.get("feature", ""))
                        critical_items.append((feature, display, sev))

            # 章末钩子强制检测
            if not analysis.get("has_hook"):
                critical_items.append(("钩子强度", "章末没有悬念钩子", "CRITICAL"))

            if critical_items:
                print(f"\n{SEP}")
                print(f"  [炸感引擎] 从你的参考资料里找可以直接用的改进技法")
                print(f"{SEP}")

                n_shown = 0
                for feature, display, sev in critical_items[:4]:
                    # 映射关键词
                    keywords = issue_map.get(feature, [])
                    if not keywords:
                        # 弱匹配：用 display_name 的关键词兜底
                        for k in issue_map:
                            if k in display or (display and display[:2] and display[:2] in k):
                                keywords = issue_map[k]
                                break
                    if not keywords:
                        continue

                    # 跨 CSV 库搜索
                    seen_keys = set()
                    suggestions = []
                    for kw in keywords[:2]:
                        results = WritingTechniqueLibrary.search(kw, max_results=3)
                        for lib_name, entries in results.items():
                            for e in entries[:2]:
                                name = (e.get("技法名称") or e.get("桥段名称")
                                        or e.get("编号") or e.get("爽点类型", ""))
                                summary = (e.get("核心摘要", "")
                                           or e.get("爽点描述", "")
                                           or e.get("说明", ""))
                                entry_key = f"{lib_name}|{name}"
                                if name and summary and entry_key not in seen_keys:
                                    seen_keys.add(entry_key)
                                    suggestions.append((name, summary, lib_name))

                    if suggestions:
                        print(f"\n  【{sev}】{display}")
                        print(f"  -> 参考这 {min(3, len(suggestions))} 条技法：")
                        for name, summary, lib in suggestions[:3]:
                            s = summary.strip().replace("\n", " ")[:75]
                            if len(summary.strip()) > 75:
                                s += "..."
                            print(f"    - [{lib}] {name}")
                            print(f"      {s}")
                        n_shown += 1

                if n_shown == 0:
                    print(f"\n  （技法库暂未精准匹配到，可试试：python pangu.py search <你的问题关键词>）")

                print()


def cmd_status():
    """显示系统状态和项目列表"""
    print(f"\n{SEP}")
    print(f"  盘古AI 系统状态 v3.0")
    print(f"{SEP}")

    # 模块状态
    print(f"\n  知识模块:")
    print(f"    TextDiagnosticEngine   : {'OK' if TextDiagnosticEngine else '缺失'}")
    print(f"    BayesianAnalyzer       : {'OK' if BayesianAnalyzer else '缺失'}")
    print(f"    EmpiricalBayesAnalyzer : {'OK' if EmpiricalBayesAnalyzer else '缺失'}")
    print(f"    CoxPrescriptionEngine  : {'OK' if CoxPrescriptionEngine else '缺失'}")
    print(f"    ReferenceEngine        : {'OK' if ReferenceEngine else '缺失'}"
          f"{'（统计库未安装, 降级模式）' if surv_mod and not getattr(surv_mod, 'HAS_STATS', True) else ''}")

    # 项目列表
    print(f"\n  现有项目:")
    if PROJECTS_ROOT.exists():
        projects = sorted([p for p in PROJECTS_ROOT.iterdir() if p.is_dir()])
        for p in projects:
            n_chapters = len(list((p / "正文").iterdir())) if (p / "正文").exists() else 0
            print(f"    - {p.name} ({n_chapters}章)")
    else:
        print(f"    (尚无项目)")

    print()


# ============================================================
# 参考资源命令 (search / refs)
# ============================================================

def _cmd_search(keyword):
    """搜索写作技法库"""
    if not HAS_REFERENCE or WritingTechniqueLibrary is None:
        print("[错误] ReferenceEngine 未加载")
        return
    results = WritingTechniqueLibrary.search(keyword, max_results=5)
    print(f"\n  搜索关键词: {keyword}")
    print(f"  {'='*56}")
    found = False
    for lib_name, entries in results.items():
        if entries:
            found = True
            print(f"\n  [{lib_name}] 找到 {len(entries)} 条:")
            for i, entry in enumerate(entries, 1):
                name = (entry.get("技法名称") or entry.get("桥段名称") or
                        entry.get("编号") or f"#{i}")
                summary = entry.get("核心摘要", entry.get("爽点描述", ""))
                if len(summary) > 80:
                    summary = summary[:80] + "..."
                print(f"    {i}. {name}")
                if summary:
                    print(f"       {summary}")
    if not found:
        print("\n  未找到相关条目，试试其他关键词")
    print()


def _cmd_refs(subcmd="status"):
    """参考资源状态 / 子列表"""
    if not HAS_REFERENCE or ReferenceEngine is None:
        print("[错误] ReferenceEngine 未加载")
        return
    engine = ReferenceEngine()

    if subcmd == "status":
        engine.print_status()
    elif subcmd in ("techniques", "tech", "技法"):
        stats = engine.stats()
        csv_stats = stats.get("csv_libraries", {})
        print(f"\n  CSV 技法库:")
        for name, count in csv_stats.items():
            print(f"    - {name}: {count} 条")
    elif subcmd in ("templates", "模版", "模板"):
        print(f"\n  核心写作模板: {len(engine.templates.list())} 个")
        for t in engine.templates.list():
            print(f"    - {t}")
        print(f"\n  题材模板: {len(engine.templates.list_genres())} 种")
        for g in engine.templates.list_genres():
            print(f"    - {g}")
    elif subcmd in ("guides", "writing", "指南"):
        guides = engine.writing.list()
        print(f"\n  写作专项指南 ({len(guides)} 篇):")
        for g in guides:
            print(f"    - {g}")
    else:
        print(f"未知子命令: {subcmd}")
        print("可用: status, techniques, templates, guides")
    print()


def main():
    args = sys.argv[1:]

    if not args:
        print("盘古AI —— 项目分析与报告系统")
        print()
        print("用法: python pangu.py <命令> [参数]")
        print()
        print("  analyze <项目> [章节号]       章节详细分析")
        print("  report  <项目> [--summary]     项目综合报告")
        print("  status                          系统状态")
        print("  list                            项目列表")
        print("  search  <关键词>                搜索写作技法库")
        print("  refs   [techniques|templates]   参考资源状态")
        print()
        print("示例:")
        print('  python pangu.py report "逻辑之下"')
        print('  python pangu.py analyze "逻辑之下" 1')
        print('  python pangu.py search 伏笔')
        print('  python pangu.py refs techniques')
        return

    cmd = args[0].lower()

    if cmd == "report":
        if len(args) < 2:
            print("[错误] 请指定项目名: python pangu.py report <项目名>")
            return
        flags = [a.lower() for a in args[2:]]
        summary_mode = "--summary" in flags or "-s" in flags
        generate_report(args[1], summary_mode=summary_mode)

    elif cmd == "analyze":
        if len(args) < 2:
            print("[错误] 请指定项目名: python pangu.py analyze <项目名>")
            return
        ch = int(args[2]) if len(args) >= 3 else None
        cmd_analyze(args[1], ch)

    elif cmd in ("status", "list", "ls"):
        cmd_status()

    elif cmd == "search":
        if len(args) < 2:
            print("[错误] 请指定搜索关键词: python pangu.py search <关键词>")
            return
        keyword = " ".join(args[1:])
        _cmd_search(keyword)

    elif cmd in ("refs", "reference", "references"):
        sub = args[1].lower() if len(args) > 1 else "status"
        _cmd_refs(sub)

    else:
        print(f"未知命令: {cmd}")
        print("可用命令: analyze, report, status, list, search, refs")


if __name__ == "__main__":
    main()
