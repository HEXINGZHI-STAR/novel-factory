#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI动态质量评分引擎
基于jieba分词+情感词典的动态文本质量评估，替代纯静态规则
无需GPU/PyTorch，纯Python即可运行
"""

import re
import math
import statistics
from pathlib import Path
from collections import Counter, defaultdict

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    print("[WARN] jieba未安装，回退到基础分词")


# ============ 内置情感词典 ============
# 基于中文情感分析常用词库精简，覆盖网文高频情绪

POSITIVE_WORDS = set("""
好 美 强 爽 喜 乐 笑 爱 暖 光 胜利 成功 突破 觉醒 碾压 打脸 逆袭 暴富
强大 无敌 完美 惊艳 震撼 激动 热血 畅快 痛快 征服 称霸 统治 崛起
轻松 从容 自信 嚣张 霸道 狂傲 骄傲 自豪 荣耀 辉煌 灿烂 耀眼
温柔 体贴 善良 可爱 甜美 幸福 甜蜜 快乐 满足 得意 欣慰 欣喜
获得 得到 拥有 掌握 控制 主宰 创造 开辟 开创 打造 建立 成就
飙升 暴涨 飞跃 突破 进化 升华 蜕变 新生 重生 觉醒 激活 开启
一剑 一刀 秒杀 完胜 碾压 横扫 荡平 踏平 灭杀 轰杀 瞬杀
""".split())

NEGATIVE_WORDS = set("""
死 杀 灭 毁 暗 冷 痛 恨 怒 怕 惨 绝望 崩溃 毁灭 灭亡 失败 打击 碾压
恐怖 恐惧 可怕 危机 危险 威胁 压迫 压制 凌辱 羞辱 耻辱 背叛 出卖
痛苦 折磨 煎熬 挣扎 忧郁 悲伤 伤心 难过 哭泣 流泪 崩溃 疯狂
愤怒 暴怒 怒火 憎恨 仇恨 怨毒 阴冷 阴森 冰冷 寒冷 黑暗 深渊
陷阱 圈套 阴谋 诡计 暗算 偷袭 埋伏 包围 绝境 死路 末路 绝路
不甘 不服 不忿 憋屈 屈辱 耻辱 羞辱 丢脸 出丑 狼狈 落魄 潦倒
妖兽 怪物 丧尸 恶魔 魔头 邪魔 妖孽 鬼怪 幽灵 骷髅 尸体 鲜血
""".split())

INTENSIFIERS = {
    "非常": 1.5, "极其": 2.0, "无比": 1.8, "极度": 1.8, "万分": 2.0,
    "太": 1.3, "很": 1.2, "好": 1.2, "真": 1.3, "特别": 1.5,
    "绝对": 1.6, "完全": 1.5, "彻底": 1.6, "根本": 1.5,
    "不怎么": 0.6, "不太": 0.5, "不怎么": 0.6, "有点": 0.7,
    "稍微": 0.7, "略微": 0.6, "几乎": 0.8, "勉强": 0.6,
}

NEGATORS = {"不", "没", "没有", "无", "非", "莫", "勿", "未", "别"}

# 动作张力词（高能量动作=更高的情绪强度）
HIGH_ENERGY_VERBS = set("""
斩杀 击杀 秒杀 轰杀 灭杀 绞杀 屠戮 碾压 横扫 踏平
暴起 暴怒 爆发 冲刺 飞掠 闪身 瞬移 撕裂 粉碎 炸裂
挥刀 拔剑 出拳 踢腿 翻身 纵身 掠出 扑去 冲去 杀去
""".split())

# 对话动作词（用于识别对话和非对话段落）
DIALOGUE_MARKERS = {"说", "道", "问", "答", "喊", "叫", "吼", "骂", "笑", "怒", "冷声", "低声", "沉声", "淡淡", "缓缓"}
DIALOGUE_OPEN = {"：", "?"}


class SentenceSentiment:
    """单句情感分析结果"""
    def __init__(self, text, score, pos_count, neg_count, intensity):
        self.text = text[:80]
        self.score = score        # -1.0 ~ 1.0
        self.pos_count = pos_count
        self.neg_count = neg_count
        self.intensity = intensity  # 0~1 强度


class DynamicScorer:
    """
    动态质量评分器
    分析维度：情绪密度、张力曲线、钩子力量、对话质量、节奏变化
    """
    
    def __init__(self):
        self._segmented_cache = {}
    
    def _segment(self, text):
        """分词（带缓存）"""
        cache_key = text[:500]
        if cache_key in self._segmented_cache:
            return self._segmented_cache[cache_key]
        
        if HAS_JIEBA:
            words = list(jieba.cut(text))
        else:
            words = text.split()
        
        if len(self._segmented_cache) > 200:
            self._segmented_cache.clear()
        self._segmented_cache[cache_key] = words
        return words
    
    def analyze_sentences(self, text):
        """逐句情感分析，返回 SentenceSentiment 列表"""
        # 按句号/感叹号/问号分句
        sentences = re.split(r'[。！？!?\n]', text)
        results = []
        
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            
            words = self._segment(sent)
            
            pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
            neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
            high_energy = sum(1 for w in words if w in HIGH_ENERGY_VERBS)
            
            # 统计否定词（翻转后面的情感）
            has_negator = any(w in NEGATORS for w in words)
            
            # 计算强度
            total_emotion = pos_count + neg_count
            intensity = min(1.0, total_emotion / max(len(words), 1) * 5 + high_energy * 0.3)
            
            # 计算得分
            if total_emotion == 0:
                score = 0.0
            else:
                raw_score = (pos_count - neg_count) / total_emotion
                if has_negator:
                    raw_score *= -0.5  # 否定词翻转
                score = max(-1.0, min(1.0, raw_score))
            
            results.append(SentenceSentiment(sent, score, pos_count, neg_count, intensity))
        
        return results
    
    def score_emotional_density(self, sentiment_results):
        """
        情绪密度评分 (0-100)
        衡量：情绪波动频率和幅度。好的网文每段都有情绪起伏。
        """
        if len(sentiment_results) < 3:
            return 30, "篇幅不足，无法评估情绪密度"
        
        # 情绪变化次数
        changes = 0
        prev_score = sentiment_results[0].score
        for s in sentiment_results[1:]:
            if abs(s.score - prev_score) > 0.3:
                changes += 1
                prev_score = s.score
        
        # 每1000字的变化率
        density = changes / max(len(sentiment_results), 1) * 10
        
        # 高强度句的比例
        high_intensity_sentences = sum(1 for s in sentiment_results if s.intensity > 0.5)
        intensity_ratio = high_intensity_sentences / max(len(sentiment_results), 1)
        
        # 综合得分
        score = min(100, density * 50 + intensity_ratio * 50)
        
        detail = (f"情绪波动{density:.1f}次/10句, "
                  f"高强度句{intensity_ratio:.0%}, "
                  f"情感变化{changes}次")
        return round(score, 1), detail
    
    def score_tension_curve(self, sentiment_results):
        """
        张力曲线评分 (0-100)
        衡量：情绪是否有起伏结构。理想的网文是"低→高→低→更高"的波浪形。
        单调平直 = 低分；有明显高潮 = 高分。
        """
        if len(sentiment_results) < 5:
            return 30, "篇幅不足"
        
        scores = [s.score for s in sentiment_results]
        intensities = [s.intensity for s in sentiment_results]
        
        # 方差：测量情绪波动幅度
        score_variance = statistics.variance(scores) if len(scores) > 1 else 0
        
        # 是否存在明显高潮（强度>0.7的句子）
        peaks = sum(1 for i in intensities if i > 0.7)
        has_peak = peaks >= 2
        
        # 结尾是否有情绪回落或二次推高（好的钩子往往在情绪高点戛然而止）
        last_3 = scores[-3:] if len(scores) >= 3 else scores
        climax_ending = any(abs(s) > 0.6 for s in last_3)
        
        # 正向情绪占比（爽文不应全程压抑）
        pos_ratio = sum(1 for s in sentiment_results if s.score > 0.2) / max(len(sentiment_results), 1)
        
        score = min(100, 
                    score_variance * 60 +       # 波动幅度
                    (20 if has_peak else 0) +   # 有高潮+20
                    (20 if climax_ending else 0) + # 结尾有力+20
                    min(20, pos_ratio * 30))    # 正向情绪
    
        detail = (f"情绪方差{score_variance:.2f}, "
                  f"高潮{'有' if has_peak else '无'}, "
                  f"结尾力度{'强' if climax_ending else '弱'}, "
                  f"正向比{pos_ratio:.0%}")
        return round(score, 1), detail
    
    def score_hook_power(self, sentiment_results):
        """
        钩子力量评分 (0-100)
        好的章末钩子通常在情绪高点突然中断，或制造强烈的"信息缺口"
        """
        if len(sentiment_results) < 3:
            return 30, "篇幅不足"
        
        # 取最后20%的内容作为"钩子区域"
        hook_start = max(0, len(sentiment_results) - max(3, len(sentiment_results) // 5))
        hook_sentences = sentiment_results[hook_start:]
        
        # 钩子区域的强度
        hook_intensity = statistics.mean([s.intensity for s in hook_sentences]) if hook_sentences else 0
        
        # 钩子区域是否有情绪断崖（高→突然低，或低→突然高，制造悬念）
        if len(hook_sentences) >= 2:
            last_scores = [s.score for s in hook_sentences[-3:]]
            # 检测最后的情绪方向
            if len(last_scores) >= 2:
                score_jump = abs(last_scores[-1] - last_scores[-2])
            else:
                score_jump = 0
        else:
            score_jump = 0
        
        # 是威胁型钩子还是期待型钩子？
        last_scores = [s.score for s in hook_sentences]
        if last_scores:
            is_threat = statistics.mean(last_scores) < -0.3  # 负情绪=威胁型
            is_positive_hook = statistics.mean(last_scores) > 0.3  # 正情绪=期待型
        else:
            is_threat = is_positive_hook = False
        
        # 评分
        base = hook_intensity * 40
        jump_bonus = min(30, score_jump * 40)
        type_bonus = 15 if is_positive_hook else (10 if is_threat else 0)  # 期待型>威胁型
        
        score = min(100, base + jump_bonus + type_bonus)
        
        hook_type = ("期待型" if is_positive_hook else 
                     ("威胁型" if is_threat else "中性"))
        detail = (f"钩子区域强度{hook_intensity:.2f}, "
                  f"情绪跳变{score_jump:.2f}, "
                  f"类型:{hook_type}")
        return round(score, 1), detail
    
    def score_dialogue_quality(self, text):
        """
        对话质量评分 (0-100)
        衡量：对话占比、说话人切换频率、对话信息密度
        """
        # 按段落分割
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        dialogue_paras = []
        quote_count = 0
        
        for p in paragraphs:
            has_quote = bool(re.search(r'["""]', p))
            has_dialogue_marker = any(m in p for m in DIALOGUE_MARKERS)
            if has_quote or (has_dialogue_marker and len(p) < 100):
                dialogue_paras.append(p)
                quote_count += len(re.findall(r'["""]', p))
        
        # 对话率
        dialogue_ratio = len(dialogue_paras) / max(len(paragraphs), 1)
        
        # 说话人切换频率（每段对话代表一次切换）
        switch_rate = len(dialogue_paras) / max(quote_count // 2, 1) if quote_count > 0 else 0
        
        # 对话信息密度（对话段落平均长度适中=有信息，过长=水对话）
        avg_dialogue_len = statistics.mean([len(p) for p in dialogue_paras]) if dialogue_paras else 0
        ideal_density = 1.0 - abs(avg_dialogue_len - 30) / 50  # 30字左右最佳
        
        score = min(100, 
                    dialogue_ratio * 50 + 
                    min(30, switch_rate * 30) + 
                    max(0, ideal_density * 20))
        
        detail = (f"对话率{dialogue_ratio:.0%}, "
                  f"平均对话长度{avg_dialogue_len:.0f}字, "
                  f"质量系数{ideal_density:.2f}")
        return round(score, 1), detail
    
    def score_opening_impact(self, text):
        """
        开篇冲击力评分 (0-100)
        检测第一句话是否有力，开篇是否迅速进入状态
        """
        # 取前300字
        opening = text[:300]
        
        # 第一句话
        first_sent = re.split(r'[。！？!?\n]', opening)[0].strip()
        
        # 负面特征检测
        penalties = 0
        detail_parts = []
        
        # 环境描写开头
        env_patterns = [r'阳光', r'月光', r'晨光', r'黄昏', r'清晨', r'傍晚', 
                       r'夜色', r'天空', r'微风', r'秋风', r'春雨', r'太阳', r'月亮']
        if any(re.search(p, first_sent) for p in env_patterns):
            penalties += 30
            detail_parts.append("环境描写开头-30")
        
        # 醒来/穿越类开头
        wake_patterns = [r'冻醒', r'吵醒', r'惊醒', r'醒来', r'睁开', r'苏醒']
        if any(re.search(p, first_sent[:50]) for p in wake_patterns):
            penalties += 40
            detail_parts.append("醒来类开头-40")
        
        # 没有动作动词的开头
        action_verbs = r'(走|跑|冲|抓|拿|拔|砍|杀|打|推|拉|踢|踹|挥|劈|刺|射|按|拍|砸|摔|扔|夺|抢)'
        if not re.search(action_verbs, first_sent[:30]):
            penalties += 15
            detail_parts.append("缺少动作动词-15")
        
        # 是否有金手指暗示
        golden_hints = [r'系统', r'觉醒', r'激活', r'升级', r'解锁', r'异能', r'空间', r'强化']
        if any(re.search(p, opening) for p in golden_hints):
            detail_parts.append("含金手指暗示+10")
        
        # 是否有人物互动(对话)
        if re.search(r'[""]|说|道|问', opening):
            detail_parts.append("含人物互动+10")
        
        score = max(0, 100 - penalties + 10 * (len(detail_parts) - penalties//15))
        return round(min(100, score), 1), ", ".join(detail_parts) if detail_parts else "开篇有力"
    
    def comprehensive_score(self, text, platform="qimao"):
        """
        综合动态质量评分 (0-100)
        融合所有维度的动态评分，返回完整的评分报告
        """
        sentiment_results = self.analyze_sentences(text)
        
        # 各维度评分
        emo_score, emo_detail = self.score_emotional_density(sentiment_results)
        tension_score, tension_detail = self.score_tension_curve(sentiment_results)
        hook_score, hook_detail = self.score_hook_power(sentiment_results)
        dialogue_score, dialogue_detail = self.score_dialogue_quality(text)
        opening_score, opening_detail = self.score_opening_impact(text)
        
        # 平台权重
        weights = {
            "fanqie":  {"opening": 0.25, "emo": 0.20, "tension": 0.20, "hook": 0.20, "dialogue": 0.15},
            "qimao":   {"opening": 0.20, "emo": 0.25, "tension": 0.15, "hook": 0.25, "dialogue": 0.15},
            "qidian":  {"opening": 0.15, "emo": 0.15, "tension": 0.30, "hook": 0.15, "dialogue": 0.25},
        }
        w = weights.get(platform, weights["qimao"])
        
        total = (
            w["opening"] * opening_score +
            w["emo"] * emo_score +
            w["tension"] * tension_score +
            w["hook"] * hook_score +
            w["dialogue"] * dialogue_score
        )
        
        return {
            "total_score": round(total, 1),
            "platform": platform,
            "breakdown": {
                "开篇冲击力": {"score": opening_score, "detail": opening_detail},
                "情绪密度": {"score": emo_score, "detail": emo_detail},
                "张力曲线": {"score": tension_score, "detail": tension_detail},
                "钩子力量": {"score": hook_score, "detail": hook_detail},
                "对话质量": {"score": dialogue_score, "detail": dialogue_detail},
            },
            "verdict": self._verdict(total)
        }
    
    def _verdict(self, score):
        if score >= 75:
            return "优秀 - 可直接投稿"
        elif score >= 60:
            return "良好 - 局部优化后投稿"
        elif score >= 45:
            return "一般 - 需要针对性修改"
        else:
            return "不合格 - 建议重写关键段落"


def score_chapter(text_or_path, platform="qimao", verbose=True):
    """
    对章节进行动态质量评分。
    参数可以是文本字符串或章节文件路径。
    """
    scorer = DynamicScorer()
    
    # 判断是路径还是文本
    if len(text_or_path) < 500 and Path(text_or_path).exists():
        content = Path(text_or_path).read_text(encoding='utf-8')
    else:
        content = text_or_path
    
    result = scorer.comprehensive_score(content, platform)
    
    if verbose:
        print(f"\n{'='*50}")
        print(f"  动态质量评分报告")
        print(f"{'='*50}")
        print(f"  总分: {result['total_score']}/100  [{result['verdict']}]")
        print(f"  平台权重: {platform}")
        print(f"  {'-'*40}")
        for dim, data in result['breakdown'].items():
            bar = '█' * int(data['score'] / 5) + '░' * (20 - int(data['score'] / 5))
            print(f"  {dim:　<6s} {bar} {data['score']:>5.1f}")
            print(f"         {data['detail']}")
        print(f"{'='*50}")
    
    return result


# ============ 批量评分 ============

def batch_score_project(project_dir, platform="qimao"):
    """对项目下所有章节进行批量动态评分"""
    project_path = Path(project_dir)
    text_dir = project_path / "正文"
    
    if not text_dir.exists():
        print(f"目录不存在: {text_dir}")
        return
    
    chapter_files = sorted(
        text_dir.glob("第*章*.txt"),
        key=lambda x: int(re.search(r'第(\d+)章', x.name).group(1)) if re.search(r'第(\d+)章', x.name) else 0
    )
    
    scorer = DynamicScorer()
    chapter_scores = []
    
    for cf in chapter_files:
        match = re.search(r'第(\d+)章', cf.name)
        ch_num = int(match.group(1)) if match else 1
        
        content = cf.read_text(encoding='utf-8')
        result = scorer.comprehensive_score(content, platform)
        chapter_scores.append((ch_num, result))
    
    # 打印汇总
    print(f"\n{'='*60}")
    print(f"  {project_path.name} - 全章动态评分汇总")
    print(f"{'='*60}")
    
    all_scores = [r['total_score'] for _, r in chapter_scores]
    avg_score = statistics.mean(all_scores) if all_scores else 0
    
    print(f"  章数: {len(chapter_scores)} | 平均分: {avg_score:.1f}")
    print(f"  {'-'*50}")
    
    for ch_num, r in chapter_scores:
        verdict_icon = "S" if r['total_score'] >= 75 else ("A" if r['total_score'] >= 60 else ("B" if r['total_score'] >= 45 else "C"))
        print(f"  {verdict_icon} 第{ch_num}章: {r['total_score']:>5.1f}分 | "
              f"开篇{r['breakdown']['开篇冲击力']['score']:.0f} "
              f"情绪{r['breakdown']['情绪密度']['score']:.0f} "
              f"张力{r['breakdown']['张力曲线']['score']:.0f} "
              f"钩子{r['breakdown']['钩子力量']['score']:.0f} "
              f"对话{r['breakdown']['对话质量']['score']:.0f}")
    
    print(f"{'='*60}")
    print(f"  平均分: {avg_score:.1f}/100")
    if avg_score >= 75:
        print(f"  结论: 整体质量优秀，可直接投稿")
    elif avg_score >= 60:
        print(f"  结论: 整体质量良好，低分章节需优化")
    else:
        print(f"  结论: 整体质量偏低，建议针对性修改低分章节")
    
    return chapter_scores


# ============ 主入口 ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
        platform = sys.argv[2] if len(sys.argv) > 2 else "qimao"
        
        path = Path(target)
        if path.is_dir():
            batch_score_project(target, platform)
        elif path.is_file():
            score_chapter(target, platform)
    else:
        print("动态评分工具")
        print("用法: python dynamic_scorer.py <章节文件或项目目录> [平台:fanqie/qimao/qidian]")
        print("示例: python dynamic_scorer.py ../projects/镇妖司：新科状元 qimao")
        print("示例: python dynamic_scorer.py ../projects/末世：我有一座外星空间站 fanqie")
