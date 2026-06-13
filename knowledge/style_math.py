#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI深层数学风格模型
超越表面统计的深层文本分析：
1. N-gram模式分析 (检测AI模板化程度)
2. Zipf幂律符合度 (自然语言vs生成文本)
3. 信息熵 (叙事复杂度)
4. TF-IDF原创性评分
5. 句法模式马尔可夫链
6. 可读性/节奏量化
"""

import re
import math
import statistics
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


class DeepStyleMath:
    """深层数学风格分析器"""
    
    def __init__(self, text=None):
        self.text = text
        self.chars = list(text) if text else []
        self.sentences = []
        self.words = []
        self._preprocess()
    
    def _preprocess(self):
        if not self.text:
            return
        # 分句
        self.sentences = [s.strip() for s in re.split(r'[。！？!?\n]+', self.text) if len(s.strip()) >= 3]
        # 简易分词（单字+双字）
        try:
            import jieba
            self.words = list(jieba.cut(self.text))
        except ImportError:
            self.words = list(self.text)
    
    # ========== 1. N-gram 模式分析 ==========
    
    def ngram_analysis(self, n=2):
        """
        N-gram去重率和唯一率。
        AI文本通常有更高的bigram重复率（模板化），
        高质量人类写作的bigram多样性更高。
        
        返回: {
            unique_ratio: 唯一N-gram占比 (越高越有原创性)
            top_repeated: 最重复的N-gram列表
            entropy: N-gram分布的香农熵 (越高越多样)
        }
        """
        if len(self.chars) < n:
            return {"unique_ratio": 0, "top_repeated": [], "entropy": 0, "interpretation": "文本过短"}
        
        ngrams = []
        for i in range(len(self.chars) - n + 1):
            ngrams.append(''.join(self.chars[i:i+n]))
        
        counter = Counter(ngrams)
        unique_ratio = len(counter) / len(ngrams) if ngrams else 0
        
        # 香农熵
        total = len(ngrams)
        entropy = 0
        for count in counter.values():
            p = count / total
            entropy -= p * math.log2(p)
        
        # 最重复的 N-gram（可能是AI模板）
        top_repeated = counter.most_common(10)
        repeated_ratio = sum(c for _, c in top_repeated[:3]) / total if total else 0
        
        # 解释
        if unique_ratio > 0.85 and entropy > 8:
            interp = "高多样性：文本原创性好，非模板化"
        elif unique_ratio > 0.7:
            interp = "中等多样性：正常写作水平"
        elif unique_ratio > 0.5:
            interp = "偏低多样性：可能存在模板化写作"
        else:
            interp = "低多样性：高度重复，强烈AI模板痕迹"
        
        return {
            "unique_ratio": round(unique_ratio, 4),
            "entropy": round(entropy, 2),
            "max_entropy": round(math.log2(len(counter)), 2),
            "top_repeated": [(ng, cnt, round(cnt/total*100, 2)) for ng, cnt in top_repeated[:5]],
            "repeated_ratio": round(repeated_ratio, 4),
            "interpretation": interp,
            "quality_score": round(min(100, unique_ratio * 100 + (1 - repeated_ratio) * 20), 1),
        }
    
    # ========== 2. Zipf幂律符合度 ==========
    
    def zipf_analysis(self):
        """
        Zipf定律：自然语言的词频分布遵循幂律分布。
        AI生成的文本往往偏离这个分布——要么过于均匀（随机），
        要么过于集中（反复使用相同词汇）。
        
        返回 R² 拟合度：越接近1越像自然语言。
        """
        if len(self.words) < 50:
            return {"zipf_r2": 0, "interpretation": "文本过短"}
        
        counter = Counter(self.words)
        # 取频次前N个
        sorted_freqs = sorted(counter.values(), reverse=True)
        
        # 计算幂律拟合度（简化版：log-log线性回归的R²）
        ranks = list(range(1, min(len(sorted_freqs), 200) + 1))
        freqs = sorted_freqs[:len(ranks)]
        
        if len(ranks) < 10:
            return {"zipf_r2": 0, "interpretation": "词汇量过少"}
        
        log_ranks = [math.log(r) for r in ranks]
        log_freqs = [math.log(f) for f in freqs]
        
        n = len(ranks)
        sum_x = sum(log_ranks)
        sum_y = sum(log_freqs)
        sum_xy = sum(x * y for x, y in zip(log_ranks, log_freqs))
        sum_x2 = sum(x * x for x in log_ranks)
        sum_y2 = sum(y * y for y in log_freqs)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        
        # Pearson R²
        r_num = n * sum_xy - sum_x * sum_y
        r_den = math.sqrt((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2))
        r = r_num / r_den if r_den != 0 else 0
        r2 = r * r
        
        if r2 > 0.9:
            interp = "优秀：词频分布高度符合自然语言规律"
        elif r2 > 0.75:
            interp = "良好：基本符合自然语言分布"
        elif r2 > 0.5:
            interp = "一般：词频分布略偏离自然语言"
        else:
            interp = "差：词频分布异常，可能为AI生成或文本质量低"
        
        return {
            "zipf_r2": round(r2, 4),
            "slope": round(slope, 2),
            "vocab_size": len(counter),
            "hapax_ratio": round(sum(1 for c in counter.values() if c == 1) / len(counter), 3) if counter else 0,
            "interpretation": interp,
            "quality_score": round(min(100, r2 * 100), 1),
        }
    
    # ========== 3. 句法模式马尔可夫链 ==========
    
    def sentence_pattern_markov(self):
        """
        分析句法模式的转移概率。
        将句子按长度分为"短(<10)/中(10-25)/长(>25)"三类，
        计算三类之间的转移矩阵。
        
        好的网文：短-中-长交替，转移矩阵均匀
        差的作品：连续长句或连续短句（单调）
        """
        if len(self.sentences) < 10:
            return {"interpretation": "句子过少"}
        
        def classify(ln):
            if ln < 10: return "S"   # 短
            if ln < 25: return "M"   # 中
            return "L"               # 长
        
        lens = [len(s) for s in self.sentences]
        classes = [classify(ln) for ln in lens]
        
        # 计数转移
        transitions = defaultdict(int)
        for i in range(len(classes) - 1):
            transitions[(classes[i], classes[i+1])] += 1
        
        # 自转移率（同类→同类，越低越好，说明有变化）
        same_class_transitions = sum(
            c for (a, b), c in transitions.items() if a == b
        )
        total_transitions = sum(transitions.values())
        self_transition_rate = same_class_transitions / total_transitions if total_transitions else 0
        
        # 转移熵（越高越多样）
        t_entropy = 0
        for c in transitions.values():
            p = c / total_transitions
            t_entropy -= p * math.log2(p)
        
        max_possible = math.log2(9)  # 3x3=9种可能
        
        if self_transition_rate < 0.3 and t_entropy > 2.0:
            interp = "优秀：句长有节奏变化，避免单调"
        elif self_transition_rate < 0.5:
            interp = "良好：有基本的句长变化"
        elif self_transition_rate < 0.7:
            interp = "偏差：相同长度句子连续较多"
        else:
            interp = "差：高度重复的句长模式，节奏单调"
        
        return {
            "self_transition_rate": round(self_transition_rate, 3),
            "transition_entropy": round(t_entropy, 2),
            "max_entropy": round(max_possible, 2),
            "sentence_length_dist": {
                "short": round(sum(1 for c in classes if c == 'S') / len(classes), 3),
                "medium": round(sum(1 for c in classes if c == 'M') / len(classes), 3),
                "long": round(sum(1 for c in classes if c == 'L') / len(classes), 3),
            },
            "avg_sentence_len": round(statistics.mean(lens), 1),
            "sentence_len_variance": round(statistics.variance(lens) if len(lens) > 1 else 0, 1),
            "interpretation": interp,
            "quality_score": round(min(100, (1 - self_transition_rate) * 100), 1),
        }
    
    # ========== 4. 信息复杂度 ==========
    
    def information_complexity(self):
        """
        多维度信息复杂度。
        - 词汇熵：词汇使用多样性
        - 句长熵：句子长度变化程度
        - 段落密度：信息密度
        """
        if len(self.words) < 20:
            return {"interpretation": "文本过短"}
        
        # 词汇熵
        word_counter = Counter(self.words)
        word_total = len(self.words)
        word_entropy = 0
        for count in word_counter.values():
            p = count / word_total
            word_entropy -= p * math.log2(p)
        
        # 句长熵
        if len(self.sentences) >= 5:
            sent_lens = [len(s) for s in self.sentences]
            sent_counter = Counter(sent_lens)
            sent_entropy = 0
            for count in sent_counter.values():
                p = count / len(sent_lens)
                sent_entropy -= p * math.log2(p)
        else:
            sent_entropy = 0
        
        # 综合复杂度
        complexity = word_entropy * 0.5 + sent_entropy * 0.5
        
        if complexity > 8:
            interp = "高复杂度：词汇和句式丰富多变"
        elif complexity > 6:
            interp = "中高复杂度：有一定的语言丰富度"
        elif complexity > 4:
            interp = "中等复杂度：适合网文阅读"
        else:
            interp = "低复杂度：词汇和句式变化不足"
        
        return {
            "word_entropy": round(word_entropy, 2),
            "sentence_entropy": round(sent_entropy, 2),
            "complexity": round(complexity, 2),
            "type_token_ratio": round(len(word_counter) / max(word_total, 1), 4),
            "interpretation": interp,
        }
    
    # ========== 5. 综合深度评分 ==========
    
    def comprehensive_deep_score(self):
        """综合所有深层数学模型给出0-100分"""
        scores = {}
        total_weight = 0
        
        # N-gram分析
        ng = self.ngram_analysis()
        scores["ngram_quality"] = ng.get("quality_score", 50)
        
        # Zipf分析
        zf = self.zipf_analysis()
        scores["zipf_naturalness"] = zf.get("quality_score", 50)
        
        # 句法模式
        sm = self.sentence_pattern_markov()
        scores["rhythm_variety"] = sm.get("quality_score", 50)
        
        # 信息复杂度
        ic = self.information_complexity()
        # 映射复杂度到0-100分
        complexity = ic.get("complexity", 5)
        if 4 <= complexity <= 7:
            complexity_score = 75
        elif complexity > 7:
            complexity_score = 90
        else:
            complexity_score = max(30, complexity * 15)
        scores["complexity"] = complexity_score
        
        # 加权综合
        weights = {
            "ngram_quality": 0.30,
            "zipf_naturalness": 0.20,
            "rhythm_variety": 0.30,
            "complexity": 0.20,
        }
        
        total = sum(scores[k] * weights[k] for k in weights)
        
        return {
            "deep_score": round(total, 1),
            "breakdown": {
                "N-gram多样性": round(scores["ngram_quality"], 1),
                "Zipf自然度": round(scores["zipf_naturalness"], 1),
                "节奏变化": round(scores["rhythm_variety"], 1),
                "信息复杂度": round(scores["complexity"], 1),
            },
            "details": {
                "ngram": ng,
                "zipf": zf,
                "markov": sm,
                "complexity": ic,
            },
        }


# ============ 工具函数 ============

def analyze_text(filepath_or_text):
    """对一个文本文件或字符串进行深层数学分析"""
    if len(filepath_or_text) < 500 and Path(filepath_or_text).exists():
        text = Path(filepath_or_text).read_text(encoding='utf-8', errors='ignore')
    else:
        text = filepath_or_text
    
    dsm = DeepStyleMath(text)
    result = dsm.comprehensive_deep_score()
    
    print(f"\n{'='*50}")
    print(f"深层数学风格分析")
    print(f"{'='*50}")
    print(f"综合深度评分: {result['deep_score']}/100")
    print(f"\n各维度得分:")
    for dim, score in result["breakdown"].items():
        bar = '#' * int(score / 5) + '-' * (20 - int(score / 5))
        print(f"  {dim}: [{bar}] {score:.0f}")
    
    # N-gram 细节
    ng = result["details"]["ngram"]
    print(f"\n[N-gram分析] {ng.get('interpretation', '')}")
    print(f"  唯一bigram比: {ng.get('unique_ratio', 0):.2%}")
    if ng.get('top_repeated'):
        print(f"  最重复序列: {', '.join(f'{t[0]}({t[2]}%)' for t in ng['top_repeated'][:3])}")
    
    # Zipf
    zf = result["details"]["zipf"]
    print(f"\n[Zipf自然度] {zf.get('interpretation', '')}")
    print(f"  R2: {zf.get('zipf_r2', 0):.3f} | 词汇量: {zf.get('vocab_size', 0)}")
    
    # 句法模式
    sm = result["details"]["markov"]
    if 'interpretation' in sm:
        print(f"\n[句法节奏] {sm['interpretation']}")
        print(f"  自转移率: {sm.get('self_transition_rate', 0):.1%}")
        dist = sm.get('sentence_length_dist', {})
        print(f"  短/中/长: {dist.get('short',0):.0%}/{dist.get('medium',0):.0%}/{dist.get('long',0):.0%}")
    
    return result


# ============ 主入口 ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
        path = Path(target)
        if path.is_file():
            analyze_text(target)
        elif path.is_dir():
            # 对目录下所有章节批量分析
            txts = list(path.glob("**/*.txt"))
            print(f"分析 {len(txts)} 个文件...")
            scores = []
            for t in txts[:10]:  # 最多10个
                try:
                    text = t.read_text(encoding='utf-8', errors='ignore')
                    if len(text) < 500:
                        continue
                    dsm = DeepStyleMath(text)
                    r = dsm.comprehensive_deep_score()
                    scores.append(r['deep_score'])
                    print(f"  {t.name[:40]}: {r['deep_score']:.0f}")
                except:
                    pass
            if scores:
                print(f"\n平均深度评分: {statistics.mean(scores):.1f}/100")
        else:
            print("文件/目录不存在")
    else:
        print("深度数学风格分析")
        print("用法: python style_math.py <文本文件或项目目录>")
        print("示例: python style_math.py ../projects/末世：我有一座外星空间站/正文/第1章.txt")
