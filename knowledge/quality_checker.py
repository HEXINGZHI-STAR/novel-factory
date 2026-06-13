#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI开篇质量门禁
自动检测AI写作中的致命问题，对标番茄/七猫/起点审稿标准
"""

import re
from pathlib import Path
from collections import Counter


# ============ AI高风险表达的推荐替换写法 ============
# 每类模板词 -> 3 个更自然的替换思路
AI_PHRASE_REPLACEMENTS = {
    "瞳孔": ["他的瞳孔猛地缩了一下", "眼尾一跳", "视线顿了顿"],
    "嘴角": ["他轻轻笑了", "露出一点似笑非笑的弧度", "唇角动了动"],
    "冷笑": ["嗤了一声", "语气里带着一丝冷", "似笑非笑"],
    "倒吸": ["他愣了一下", "喉头一紧", "浑身都僵住了"],
    "脸色大变": ["他的脸瞬间白了", "表情彻底僵住", "声音都变了调"],
    "心中一惊": ["他手一抖", "脚步停了", "呼吸顿了半拍"],
    "心头一颤": ["指尖发麻", "心里咯噔一下", "整个人都绷紧了"],
    "心中一沉": ["一股寒意涌上来", "他心里一紧", "一股不祥的预感"],
    "脑子里飞速": ["他飞快地想", "思绪乱转", "脑子里瞬间转过几个念头"],
    "在末世活了": ["他在这世道摸爬滚打", "经历了那么多", "一路走来见多了这种事"],
    "二话不说": ["他没多话", "没等对方说完", "动作快得不留余地"],
    "话音刚落": ["话还没说完", "话音未落", "声音刚落下"],
    "心脏狠狠": ["心跳漏了一拍", "胸口像被什么撞了一下", "心跳突然就狠了起来"],
    "忽然": ["就在这时", "下一刻", "忽然之间"],
    "突然": ["猛地", "骤然", "毫无征兆"],
    "此子断不可留": ["不能让他走", "这人留不得", "今天必须除掉他"],
    "恐怖如斯": ["厉害到这种地步", "实力当真骇人", "这可不是一般人"],
    "眼神冰冷": ["目光冷了下去", "眼里没了温度", "视线像两把刀"],
    "心里一阵": ["一股暖流", "一阵说不出的滋味", "忽然有些动容"],
    "莫名有些感动": ["心头微微一暖", "有点不是滋味", "竟有些动容"],
}



AI_HIGH_RISK_WORDS = [
    # 表情/神态模板
    "瞳孔骤然", "瞳孔猛地", "瞳孔狠狠", "瞳孔收缩",
    "嘴角勾起", "嘴角露出一抹", "嘴角微", "嘴角上扬",
    "冷哼一声", "冷冷一笑", "冷笑一声",
    "倒吸一口凉气", "倒吸一口冷气",
    "脸色大变", "脸色一变", "面色一变",
    "心头一颤", "心中一惊", "心中一沉", "心中暗暗",
    "不由得倒吸", "不禁冷笑",
    # 叙事模板
    "二话不说",
    "话音刚落",
    "心脏狠狠", "心脏猛地",
    "脑子里飞速", "大脑飞速",
    "忽然", "突然", "猛然", "骤然",
    "此子断不可留", "恐怖如斯",
    # 情绪模板
    "心里一阵", "莫名有些感动", "莫名一阵",
    "眼神冰冷", "冰冷的目光", "冰冷的眼神",
]

AI_HIGH_RISK_PATTERNS = [
    (r"只见\s", "【代言】'只见'——直接写画面，不需要代言读者"),
    (r"只听得\s", "【代言】'只听得'——直接写声音"),
    (r"只感到\s", "【代言】'只感到'——直接写感受"),
    (r"心中一惊", "【模板】'心中一惊'→用身体感受替代"),
    (r"心中一沉", "【模板】'心中一沉'→用具体意象替代"),
    (r"他脑子里", "【偷懒】'他脑子里……'→展示推理过程，不概括"),
    (r"在末世活了.*什么.*没见过", "【告知】用旁白告知经历→用具体回忆替代"),
    (r"圣贤书里说过", "【万能解释】'圣贤书里说过'→建立有边界的规则"),
]


class ChapterQualityReport:
    """章节质检报告"""

    def __init__(self):
        self.issues = []           # 问题列表
        self.warnings = []         # 警告
        self.fatals = []           # 致命错误
        self.metrics = {}          # 量化指标
        self.passed = True
        self._line_counts = {}     # 每类问题的行级明细

    def add_issue(self, severity, category, detail, suggestion="",
                   line_number=None, raw_text=None):
        entry = {
            "severity": severity,  # fatal / warning / info
            "category": category,
            "detail": detail,
            "suggestion": suggestion,
            "line": line_number,    # 新增: 行号
            "raw": raw_text,        # 新增: 原文片段
        }
        self.issues.append(entry)
        if severity == "fatal":
            self.fatals.append(entry)
            self.passed = False
        elif severity == "warning":
            self.warnings.append(entry)
        # 统计各类问题
        self._line_counts.setdefault(category, 0)
        self._line_counts[category] += 1
    
    def summary(self):
        """生成可读摘要"""
        lines = []
        lines.append(f"{'='*50}")
        lines.append(f"章节质量报告: {'通过' if self.passed else '不合格'}")
        lines.append(f"{'='*50}")
        
        if self.fatals:
            lines.append(f"\n[致命错误] ({len(self.fatals)}项，必须修复):")
            for i, f in enumerate(self.fatals, 1):
                lines.append(f"  {i}. [{f['category']}] {f['detail']}")
                if f['suggestion']:
                    lines.append(f"     → {f['suggestion']}")
        
        if self.warnings:
            lines.append(f"\n[警告] ({len(self.warnings)}项):")
            for i, w in enumerate(self.warnings, 1):
                lines.append(f"  {i}. [{w['category']}] {w['detail']}")
        
        # 量化指标
        if self.metrics:
            lines.append(f"\n[量化指标]:")
            for k, v in self.metrics.items():
                lines.append(f"  {k}: {v}")
        
        if self.passed and not self.warnings:
            lines.append(f"\n[通过] 所有检测通过，章节质量合格")
        
        return "\n".join(lines)


def check_chapter(content, platform="qimao", chapter_num=1, mode="general"):
    """
    对章节内容进行全面的开篇质量检测。
    
    参数:
        content: 章节正文文本
        platform: 目标平台 (fanqie/qimao/qidian)
        chapter_num: 章节编号
        mode: 写作模式
    
    返回: ChapterQualityReport
    """
    report = ChapterQualityReport()
    
    if not content or len(content) < 100:
        report.add_issue("fatal", "内容", "章节内容过短或为空")
        return report
    
    # 统计基础指标
    word_count = len(content.replace('\n', '').replace(' ', ''))
    report.metrics["总字数"] = word_count
    
    # 1. AI高风险表达检测
    check_ai_traces(content, report)
    
    # 2. 开篇质量检测（前3章重点检查）
    if chapter_num <= 3:
        check_opening_quality(content, platform, chapter_num, report)
    
    # 3. POV一致性与人称检测
    check_pov_consistency(content, report)
    
    # 4. 对话率检测
    check_dialogue_ratio(content, platform, report)
    
    # 5. 章末钩子检测
    check_ending_hook(content, chapter_num, report)
    
    # 6. 感官丰富度检测
    check_sensory_richness(content, report)
    
    # 7. 段落长度检测（移动端适配）
    check_paragraph_length(content, platform, report)
    
    return report


def check_ai_traces(content, report):
    """检测AI高风险表达（逐行扫描 + 定位 + 具体替换建议）"""
    # 1. 逐行扫描关键词
    text_lines = content.split('\n')
    line_hits = []  # [(line_number, matched_word, line_text)]
    for idx, line in enumerate(text_lines, 1):
        for word in AI_HIGH_RISK_WORDS:
            if word in line:
                line_hits.append((idx, word, line.strip()))
                break  # 每行只记一次，避免同一行重复记

    # 2. 正则检测
    pattern_hits = []
    for pattern, msg in AI_HIGH_RISK_PATTERNS:
        for idx, line in enumerate(text_lines, 1):
            ms = re.findall(pattern, line)
            if ms:
                pattern_hits.append((idx, msg, line.strip()))

    total_hits = len(line_hits) + len(pattern_hits)
    if total_hits == 0:
        return

    # 3. 汇总报告 —— 给出具体行号 + 原文 + 替换建议（最多展示5条，其余计数）
    max_show = 5
    shown = 0
    top_lines = line_hits[:max_show] + pattern_hits[:max(0, max_show - len(line_hits))]

    for line_num, matched_word, line_text in top_lines:
        # 查找替换建议
        suggestions = []
        for key, replacements in AI_PHRASE_REPLACEMENTS.items():
            if key in matched_word:
                suggestions = replacements
                break
        suggestion_str = " / ".join(suggestions[:2]) if suggestions else \
            "改为具体动作/神态描写，不要概括心理"
        report.add_issue(
            "fatal" if total_hits > 6 else "warning",
            "AI模板表达",
            f"第{line_num}行: '{line_text[:40]}' —— 出现模板词『{matched_word[:8]}』",
            f"建议替换为: {suggestion_str}",
            line_number=line_num,
            raw_text=line_text
        )
        shown += 1

    # 4. 汇总统计（如果超过 max_show 条）
    remaining = total_hits - shown
    if remaining > 0:
        report.add_issue(
            "warning",
            "AI模板表达",
            f"另有 {remaining} 处模板表达未逐一列出",
            "全文检查，统一替换为个性化、动作化的表达",
        )


def check_opening_quality(content, platform, chapter_num, report):
    """检测开篇质量：冲突位置、金手指展示时机"""
    if platform == "fanqie":
        conflict_threshold = 300
        golden_threshold = 500
    elif platform == "qimao":
        conflict_threshold = 500
        golden_threshold = 800
    else:  # qidian
        conflict_threshold = 800
        golden_threshold = 1000
    
    first_300 = content[:conflict_threshold * 3]  # 取前900字作为采样
    
    # 检测是否有动作/对话（冲突存在的间接指标）
    has_action = bool(re.search(r'[，。！？](他|她|我|你|林|沈|陈|张|李|王|赵|周|吴|郑)[^，。！？]{0,30}(说|道|问|喊|吼|叫|骂|笑|走|跑|冲|抓|拿|拔|砍|杀|打)', first_300))
    has_dialogue = '说' in first_300 or '道' in first_300 or '问' in first_300 or '：' in first_300
    
    # 检测是否以环境/天气开篇
    first_sentence = content[:100].strip()
    env_patterns = [r'^.{0,20}(阳光|月光|晨光|黄昏|清晨|傍晚|夜色|天空|大地|微风|秋风|春雨)',
                    r'^.{0,20}(月光|阳光).*(透过|洒|照)',
                    r'^.{0,10}(是|被).{0,5}(冻醒|吵醒|惊醒|唤醒)']
    
    for pat in env_patterns:
        if re.search(pat, first_sentence):
            report.add_issue(
                "fatal" if chapter_num == 1 else "warning",
                "开篇",
                f"开篇疑似环境描写/醒来类开篇：\"{first_sentence[:60]}...\"",
                "禁止环境描写/醒来类开篇。第一句话必须发生事情：用动作、对话或异常事件开篇。"
            )
            break
    
    if not (has_action or has_dialogue):
        report.add_issue(
            "fatal" if chapter_num == 1 else "warning",
            "开篇",
            f"前{conflict_threshold}字内未检测到明确的动作或对话",
            f"平台要求：{platform}需在{conflict_threshold}字内出现冲突场景"
        )
    
    report.metrics["开篇检测"] = f"动作:{'有' if has_action else '无'} 对话:{'有' if has_dialogue else '无'}"


def check_pov_consistency(content, report):
    """检测POV人称一致性"""
    # 分割段落，检测人称切换模式
    paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    
    first_person_count = 0
    third_person_count = 0
    
    for p in paragraphs:
        # 统计"我"和"他/她"的出现（排除对话中的）
        # 简化版：只看段落开头
        if p.startswith('我'):
            first_person_count += 1
        elif p.startswith('他') or p.startswith('她'):
            third_person_count += 1
    
    total_markers = first_person_count + third_person_count
    if total_markers > 20:
        first_ratio = first_person_count / total_markers
        third_ratio = third_person_count / total_markers
        
        # 如果有显著的混合（两种人称都超过30%）
        if first_ratio > 0.3 and third_ratio > 0.3:
            report.add_issue(
                "fatal",
                "POV一致性",
                f"检测到人称混合：第一人称{first_ratio:.0%}，第三人称{third_ratio:.0%}",
                "全文必须统一人称。这是直接淘汰级错误。"
            )
        elif first_ratio > 0.1 and third_ratio > 0.1:
            report.add_issue(
                "warning",
                "POV一致性",
                f"存在人称不一致风险：第一人称{first_ratio:.0%}，第三人称{third_ratio:.0%}",
                "确认所有人称使用一致，排除AI切换人称的问题。"
            )


def check_dialogue_ratio(content, platform, report):
    """检测对话率，并定位哪些段落实质无对话"""
    # 统计对话行（以引号或冒号+说/道开头的行）
    dialogue_chars = 0
    total_chars = len(content.replace('\n', '').replace(' ', ''))

    # 统计引号内的内容
    quote_pattern = re.compile(r'["""][^""""]+?["\u201d"]')
    for match in quote_pattern.finditer(content):
        dialogue_chars += len(match.group())

    dialogue_ratio = dialogue_chars / max(total_chars, 1)
    report.metrics["对话率"] = f"{dialogue_ratio:.0%}"

    # 平台对话率门槛
    thresholds = {"fanqie": 0.35, "qimao": 0.40, "qidian": 0.25}
    threshold = thresholds.get(platform, 0.30)

    if dialogue_ratio < threshold:
        # 定位前 5 个无对话的长段落（提示可以在哪里插入对话）
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        long_narrative_paragraphs = []
        for idx, p in enumerate(paragraphs, 1):
            is_dialogue = ('说' in p[:15] or '道' in p[:15] or
                          re.match(r'^["\u201c]', p) or
                          p.startswith('"') or p.startswith('他') and '说' in p)
            if len(p) > 80 and not is_dialogue:
                long_narrative_paragraphs.append((idx, p[:40]))
                if len(long_narrative_paragraphs) >= 3:
                    break

        detail = f"对话率{dialogue_ratio:.0%}，低于{platform}平台建议值{threshold:.0%}"
        if long_narrative_paragraphs:
            pos_list = "、".join(f"第{idx}段" for idx, _ in long_narrative_paragraphs)
            detail += f"。建议在 {pos_list} 附近插入对话"

        suggestion = "1) 把叙述改为对白（用对话展示信息）; 2) 在紧张场景用短对话加速节奏; 3) 用对白代替内心独白"
        report.add_issue(
            "warning",
            "对话率",
            detail,
            suggestion
        )


def check_ending_hook(content, chapter_num, report):
    """检测章末钩子 + 显示末段原文 + 具体建议"""
    # 取最后 3 个非空段落
    paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    last_paragraphs = paragraphs[-3:] if len(paragraphs) >= 3 else paragraphs
    last_200 = content[-200:] if len(content) > 200 else content

    # 检测钩子类型的关键词
    suspense_keywords = ["不知道的是", "没注意到", "却没看到", "背后的", "秘密", "真相"]
    crisis_keywords = ["逼近", "袭来", "涌来", "降临", "危险", "劫", "危机"]
    reversal_keywords = ["其实", "原来", "竟是", "居然是", "不是.*而是"]
    expectation_keywords = ["接下来", "等着他", "将要", "即将", "马上", "更强的"]

    hook_types_found = []
    if any(kw in last_200 for kw in suspense_keywords):
        hook_types_found.append("悬念型")
    if any(kw in last_200 for kw in crisis_keywords):
        hook_types_found.append("危机型")
    if any(re.search(p, last_200) for p in reversal_keywords):
        hook_types_found.append("反转型")
    if any(kw in last_200 for kw in expectation_keywords):
        hook_types_found.append("期待型")

    if not hook_types_found:
        last_text = " | ".join(p[:30] for p in last_paragraphs[-2:]) if last_paragraphs else ""
        report.add_issue(
            "fatal" if chapter_num <= 3 else "warning",
            "章末钩子",
            f"末段无钩子 —— 当前结尾: '{last_text[:60]}'",
            "建议在结尾加入以下其一: 1) 悬念(但他不知道的是...) 2) 危机(黑暗中一双眼睛...) 3) 反转(原来她不是...) 4) 期待(明天的拍卖会他势在必得...)"
        )
    else:
        report.metrics["钩子类型"] = "、".join(hook_types_found)
        # 检测到钩子也给出一条温和的改进建议
        if len(hook_types_found) == 1 and len(last_200) < 30:
            report.add_issue(
                "info",
                "章末钩子",
                f"检测到{hook_types_found[0]}钩子，可进一步强化收尾的节奏感",
                "在钩子句后立即换段，让它成为本章的最后一句（即所谓'断尾'处理）"
            )


def check_sensory_richness(content, report):
    """检测感官丰富度"""
    sensory_patterns = {
        "视觉": len(re.findall(r'(看到|看见|望着|盯着|映入|颜色|红色|蓝色|白色|黑色|金色|银色|光|暗)', content)),
        "听觉": len(re.findall(r'(听到|听见|声音|响起|传来|轰|响|静|默|回声)', content)),
        "触觉": len(re.findall(r'(冷|热|暖|凉|痛|麻|痒|重|轻|硬|软|粗糙|光滑|冰|火|烫)', content)),
        "嗅觉": len(re.findall(r'(闻到|气味|香味|臭味|腥|焦|烟|花香|腐|霉)', content)),
    }
    
    active_senses = sum(1 for v in sensory_patterns.values() if v > 0)
    report.metrics["感官丰富度"] = f"{active_senses}/4种感官激活"
    
    if active_senses < 2:
        report.add_issue(
            "warning",
            "感官描写",
            f"仅激活{active_senses}种感官。建议每个场景至少激活3种感官。",
            "增加听觉/触觉/嗅觉描写，避免纯视觉叙事。"
        )


def check_paragraph_length(content, platform, report):
    """检测段落长度（移动端适配）"""
    max_lines = {"fanqie": 3, "qimao": 3, "qidian": 5}
    threshold = max_lines.get(platform, 4)
    
    paragraphs = [p for p in content.split('\n') if p.strip()]
    long_paras = [p for p in paragraphs if len(p) > 150]
    
    if len(long_paras) > 3:
        report.add_issue(
            "warning",
            "排版",
            f"{len(long_paras)}个段落超过150字，移动端阅读体验差",
            f"手机端每段不超过{threshold}行。用短句、对话、动作切分长段落。"
        )


def check_chapter_file(filepath, platform="qimao", chapter_num=1, mode="general", verbose=True):
    """
    检测一个章节文件并打印报告。
    返回 True 表示通过，False 表示不合格。
    """
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在: {filepath}")
        return False
    
    content = path.read_text(encoding='utf-8')
    report = check_chapter(content, platform, chapter_num, mode)
    
    if verbose:
        print(report.summary())
    
    return report.passed


def batch_check_project(project_dir, platform="qimao", mode="general"):
    """批量检测项目下所有章节"""
    project_path = Path(project_dir)
    text_dir = project_path / "正文"
    
    if not text_dir.exists():
        print(f"项目目录不存在或没有正文: {project_dir}")
        return
    
    chapter_files = sorted(
        text_dir.glob("第*章*.txt"),
        key=lambda x: int(re.search(r'第(\d+)章', x.name).group(1)) if re.search(r'第(\d+)章', x.name) else 0
    )
    
    print(f"\n{'='*60}")
    print(f"批量质量检测: {project_path.name}")
    print(f"平台: {platform} | 模式: {mode}")
    print(f"检测章节数: {len(chapter_files)}")
    print(f"{'='*60}")
    
    all_passed = True
    for cf in chapter_files:
        match = re.search(r'第(\d+)章', cf.name)
        ch_num = int(match.group(1)) if match else 1
        
        print(f"\n--- 第{ch_num}章 ---")
        passed = check_chapter_file(cf, platform, ch_num, mode, verbose=True)
        if not passed:
            all_passed = False
    
    print(f"\n{'='*60}")
    print(f"总结: {'全部通过' if all_passed else '存在问题，请修复后重新投稿'}")
    print(f"{'='*60}")
    
    return all_passed


# ============ 主入口 ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
        platform = sys.argv[2] if len(sys.argv) > 2 else "qimao"
        
        path = Path(target)
        if path.is_dir():
            batch_check_project(target, platform)
        elif path.is_file():
            match = re.search(r'第(\d+)章', path.name)
            ch_num = int(match.group(1)) if match else 1
            check_chapter_file(target, platform, ch_num)
    else:
        # 示例
        project = Path(__file__).parent.parent / "projects" / "镇妖司：新科状元"
        if project.exists():
            batch_check_project(project, "qimao")
        else:
            print("用法: python quality_checker.py <章节文件或项目目录> [平台]")
            print("示例: python quality_checker.py projects/镇妖司：新科状元 qimao")
