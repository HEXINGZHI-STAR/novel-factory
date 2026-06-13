#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI数学核心引擎 — Java Bridge专用
======================================
本文件为Java Bridge专用，独立运行，不依赖 pangu_math/ 包。
供 backend-java/ 通过 PythonBridge 调用。

⚠ 注意: 此文件与 pangu_math/ 是并行实现，不是同一代码库。
  - pangu_math/accelerated.py → Python Pipeline用 (numpy加速)
  - knowledge/pangu_math_core.py → Java后端用 (纯Python，无外部依赖)

将线性代数、傅里叶分析、微积分、马尔可夫链、信息论
等数学分支嵌入写作分析系统的底层。

数学分支 → 写作建模:
  线性代数  → 风格向量空间、主成分、协方差、特征分解
  傅里叶分析 → 情绪频率分解、叙事韵律频谱
  积分学    → 累积张力、情绪曲线下面积、衰减卷积
  马尔可夫链 → 叙事状态转移、稳态分布、吸收概率
  信息论    → 词汇熵、KL散度、互信息、信道容量

所有操作均为纯Python实现（不依赖numpy），
矩阵运算使用自实现的O(n^3)算法（适用于20维空间）。
"""

import math
import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


# ============================================================
# 0. 基础工具：纯Python向量与矩阵运算
# ============================================================

@dataclass
class Vector:
    """n维向量，支持所有标准向量空间运算"""
    values: List[float]
    
    def __post_init__(self):
        self.dim = len(self.values)
    
    def __len__(self): return self.dim
    def __getitem__(self, i): return self.values[i]
    def __iter__(self): return iter(self.values)
    
    # 向量加法
    def __add__(self, other):
        return Vector([a + b for a, b in zip(self.values, other.values)])
    
    def __sub__(self, other):
        return Vector([a - b for a, b in zip(self.values, other.values)])
    
    # 标量乘法
    def __mul__(self, scalar):
        return Vector([v * scalar for v in self.values])
    
    def __rmul__(self, scalar):
        return self.__mul__(scalar)
    
    # 内积
    def dot(self, other) -> float:
        return sum(a * b for a, b in zip(self.values, other.values))
    
    # L2范数
    def norm(self) -> float:
        return math.sqrt(self.dot(self))
    
    # 归一化
    def normalize(self):
        n = self.norm()
        if n == 0: return Vector(self.values[:])
        return Vector([v / n for v in self.values])
    
    # 余弦相似度
    def cosine(self, other) -> float:
        n1, n2 = self.norm(), other.norm()
        if n1 == 0 or n2 == 0: return 0
        return self.dot(other) / (n1 * n2)
    
    # 欧氏距离
    def distance(self, other) -> float:
        return math.sqrt(sum((a - b)**2 for a, b in zip(self.values, other.values)))
    
    def to_list(self): return self.values[:]


@dataclass
class Matrix:
    """m×n矩阵"""
    rows: int
    cols: int
    data: List[List[float]]
    
    @classmethod
    def zeros(cls, rows, cols):
        return cls(rows, cols, [[0.0]*cols for _ in range(rows)])
    
    @classmethod
    def identity(cls, n):
        m = cls.zeros(n, n)
        for i in range(n):
            m.data[i][i] = 1.0
        return m
    
    def __getitem__(self, idx):
        return self.data[idx]
    
    # 矩阵乘法 C = A @ B
    def matmul(self, other: 'Matrix') -> 'Matrix':
        assert self.cols == other.rows
        result = Matrix.zeros(self.rows, other.cols)
        for i in range(self.rows):
            for k in range(self.cols):
                aik = self.data[i][k]
                if aik != 0:
                    for j in range(other.cols):
                        result.data[i][j] += aik * other.data[k][j]
        return result
    
    # 矩阵×向量
    def mv_product(self, vec: Vector) -> Vector:
        assert self.cols == len(vec)
        return Vector([sum(self.data[i][j] * vec[j] for j in range(self.cols)) for i in range(self.rows)])
    
    # 转置
    def transpose(self) -> 'Matrix':
        return Matrix(self.cols, self.rows, [[self.data[j][i] for j in range(self.rows)] for i in range(self.cols)])
    
    # 幂迭代求最大特征值和特征向量
    def power_iteration(self, max_iter=100, tol=1e-6):
        """幂迭代法求绝对值最大的特征值及对应特征向量"""
        v = Vector([1.0] * self.rows)
        v = v.normalize()
        lambda_old = 0
        for _ in range(max_iter):
            Av = self.mv_product(v)
            lambda_new = Av.dot(v)
            v = Av.normalize()
            if abs(lambda_new - lambda_old) < tol:
                break
            lambda_old = lambda_new
        return lambda_new, v
    
    def eigenvalues(self, n_eigs=3):
        """Simplified: get top n_eigs eigenvalues via deflation"""
        A = self
        eigs = []
        for _ in range(min(n_eigs, self.rows)):
            lam, vec = A.power_iteration()
            eigs.append((lam, vec))
            # Deflation
            v_outer = Matrix(self.rows, self.rows, 
                           [[vec[i] * vec[j] for j in range(self.rows)] for i in range(self.rows)])
            new_data = [[A.data[i][j] - lam * v_outer.data[i][j] for j in range(self.cols)] for i in range(self.rows)]
            A = Matrix(self.rows, self.cols, new_data)
        return eigs


def covariance_matrix(vectors: List[Vector]) -> Matrix:
    """计算多个向量的协方差矩阵"""
    n = len(vectors)
    d = vectors[0].dim
    # 均值
    mean = Vector([sum(v[i] for v in vectors) / n for i in range(d)])
    # 协方差
    cov = Matrix.zeros(d, d)
    for v in vectors:
        diff = v - mean
        for i in range(d):
            for j in range(d):
                cov.data[i][j] += diff[i] * diff[j]
    for i in range(d):
        for j in range(d):
            cov.data[i][j] /= (n - 1) if n > 1 else 1
    return cov


def svd_approximate(matrix: Matrix, k=2):
    """
    简化版SVD：A ≈ U Σ V^T
    对A^T A求特征分解得到右奇异向量V
    """
    ATA = matrix.transpose().matmul(matrix)
    eigs = ATA.eigenvalues(k)
    
    singular_values = []
    V_cols = []
    for lam, vec in eigs:
        if lam > 0:
            sigma = math.sqrt(lam)
            singular_values.append(sigma)
            V_cols.append(vec.values)
    
    # U = A V Σ^{-1}
    V = Matrix(len(V_cols), matrix.cols, V_cols).transpose() if V_cols else Matrix.zeros(matrix.cols, k)
    U_data = []
    for i in range(matrix.rows):
        ui = [0.0] * len(singular_values)
        for j in range(len(singular_values)):
            for t in range(matrix.cols):
                ui[j] += matrix.data[i][t] * V.data[t][j] / singular_values[j]
        U_data.append(ui)
    
    return {
        "U": Matrix(matrix.rows, len(singular_values), U_data) if singular_values else None,
        "S": singular_values,
        "V": V if singular_values else None,
    }


# ============================================================
# 1. 线性代数引擎：风格向量空间
# ============================================================

class LinearAlgebraEngine:
    """
    将章节映射到向量空间 ℝᵈ，执行内积、相似度、
    协方差分析、主成分提取等操作。
    
    核心洞察：
    - 协方差矩阵的特征向量 = 风格的"主方向"
    - 最大特征值对应的方向 = 该类型作品差异最大的维度
    - SVD降维 = 用2-3个"基础风格"线性组合近似任何章节
    """
    
    # 特征维度定义 (12维核心向量)
    FEATURES = [
        "sentence_len",       # 均句长
        "sentence_variance",  # 句长方差
        "paragraph_len",      # 均段长
        "dialogue_ratio",     # 对话率
        "emotion_mean",       # 平均情绪值
        "emotion_variance",   # 情绪波动
        "hook_strength",      # 钩子强度
        "action_density",     # 动作密度
        "ngram_unique",       # N-gram唯一性
        "zipf_r2",            # Zipf自然度
        "self_transition",    # 句法自转移率(低=好)
        "complexity",         # 信息复杂度
    ]
    
    DIM = len(FEATURES)
    
    @classmethod
    def extract_vector(cls, text) -> Vector:
        """
        从文本提取12维单位风格向量。
        每个分量归一化到 [0,1]，高维空间中的单位超球面上。
        """
        raw = cls._extract_raw(text)
        v = []
        for name in cls.FEATURES:
            v.append(raw.get(name, 0.5))
        vec = Vector(v)
        n = vec.norm()
        return vec if n == 0 else vec * (1.0 / n)
    
    @classmethod
    def _extract_raw(cls, text) -> Dict[str, float]:
        """提取原始特征值（未归一化）"""
        clean = text.replace('\n', ' ').replace(' ', '')
        wc = max(len(clean), 1)
        
        # 句法
        sents = [s.strip() for s in re.split(r'[。！？!?…\.\n]+', text) if len(s.strip()) >= 3]
        sent_lens = [len(s) for s in sents] if sents else [20]
        avg_sl = sum(sent_lens) / len(sent_lens)
        var_sl = sum((x - avg_sl)**2 for x in sent_lens) / len(sent_lens)
        
        # 段落
        paras = [p.strip() for p in text.split('\n') if p.strip()]
        avg_pl = sum(len(p) for p in paras) / max(len(paras), 1)
        
        # 对话
        dm = {"说", "道", "问", "答", "喊", "叫", "吼", "骂"}
        d_paras = [p for p in paras if any(m in p for m in dm) or '"' in p]
        d_ratio = len(d_paras) / max(len(paras), 1)
        
        # 情绪（简化：基于情感词典的快速估计）
        pos_words = set("好美强爽喜乐笑爱暖光胜成突破觉醒碾压打脸逆袭".split())
        neg_words = set("死灭毁暗冷痛苦恨怒怕惨绝望崩溃失败打击".split())
        pos_c = sum(1 for c in text if c in ''.join(pos_words)) / 100
        neg_c = sum(1 for c in text if c in ''.join(neg_words)) / 100
        emo_mean = (pos_c - neg_c) / max(pos_c + neg_c, 1) + 0.5
        emo_var = abs(pos_c - neg_c) / max(wc, 1) * 1000
        
        # 钩子（简化：章末200字情绪跳变）
        ending = text[-200:] if len(text) > 200 else text
        ending_pos = sum(1 for c in ending if c in ''.join(pos_words)) / 100
        ending_neg = sum(1 for c in ending if c in ''.join(neg_words)) / 100
        hook = abs(ending_pos - ending_neg) * 50 + 30
        hook = min(100, max(0, hook))
        
        # 动作密度
        av = "走跑冲抓拿拔砍杀打推拉踢踹挥劈刺射斩翻跃扑闪"
        action_d = len([c for c in text if c in av]) / wc * 1000
        
        # N-gram唯一性
        bigrams = [clean[i:i+2] for i in range(len(clean)-1)]
        ngram_u = len(set(bigrams)) / max(len(bigrams), 1)
        
        # Zipf近似（词频分布的Gini系数）
        char_counter = Counter(clean)
        sorted_freqs = sorted(char_counter.values(), reverse=True)
        total = sum(sorted_freqs)
        gini = sum((i+1) * f for i, f in enumerate(sorted_freqs[:50])) / (total * 25) if total > 0 else 0.5
        zipf = min(1, 1 - abs(gini - 0.5))
        
        # 句法自转移
        len_classes = ["S" if l < 10 else "M" if l < 25 else "L" for l in sent_lens]
        self_trans = sum(1 for i in range(len(len_classes)-1) if len_classes[i] == len_classes[i+1]) / max(len(len_classes)-1, 1)
        
        # 信息复杂度
        word_counter = Counter()
        for i in range(len(clean)-1):
            word_counter[clean[i:i+2]] += 1
        total_grams = sum(word_counter.values())
        entropy = -sum((c/total_grams) * math.log2(c/total_grams) for c in word_counter.values())
        complexity = min(1, entropy / 10)
        
        return {
            "sentence_len": min(1, avg_sl / 60),
            "sentence_variance": min(1, var_sl / 50),
            "paragraph_len": min(1, avg_pl / 300),
            "dialogue_ratio": d_ratio,
            "emotion_mean": emo_mean,
            "emotion_variance": min(1, emo_var / 5),
            "hook_strength": hook / 100,
            "action_density": min(1, action_d / 30),
            "ngram_unique": ngram_u,
            "zipf_r2": zipf,
            "self_transition": 1 - self_trans,  # 反转：高=好
            "complexity": complexity,
        }
    
    @classmethod
    def compare(cls, text1, text2) -> Dict:
        """
        比较两个文本在向量空间中的关系。
        返回余弦相似度和欧氏距离。
        """
        v1 = cls.extract_vector(text1)
        v2 = cls.extract_vector(text2)
        
        # 各维度差异
        dim_diffs = {}
        for i, name in enumerate(cls.FEATURES):
            dim_diffs[name] = round(v1[i] - v2[i], 3)
        
        return {
            "cosine_similarity": round(v1.cosine(v2), 3),
            "euclidean_distance": round(v1.distance(v2), 3),
            "inner_product": round(v1.dot(v2), 3),
            "is_similar": v1.cosine(v2) > 0.85,
            "max_divergence_dim": max(dim_diffs, key=lambda k: abs(dim_diffs[k])),
            "dimension_differences": dim_diffs,
        }
    
    @classmethod
    def analyze_corpus(cls, texts: List[str]) -> Dict:
        """
        对一个文本集合进行线性代数分析。
        返回协方差矩阵的特征分解、主导风格方向。
        """
        vectors = [cls.extract_vector(t) for t in texts if len(t) > 200]
        if len(vectors) < 3:
            return {"error": "样本不足", "min_required": 3}
        
        # 协方差矩阵
        cov = covariance_matrix(vectors)
        
        # 特征分解
        eigs = cov.eigenvalues(3)
        
        # 主成分解释
        total_var = sum(abs(lam) for lam, _ in eigs)
        pc_analysis = []
        for i, (lam, vec) in enumerate(eigs):
            explained = abs(lam) / total_var * 100 if total_var > 0 else 0
            # 找出这个主成分中权重最大的维度
            top_dims = sorted(
                [(cls.FEATURES[j], abs(vec[j])) for j in range(len(vec)) if abs(vec[j]) > 0.2],
                key=lambda x: -x[1]
            )[:3]
            pc_analysis.append({
                "pc": i + 1,
                "eigenvalue": round(lam, 4),
                "explained_variance": round(explained, 1),
                "dominant_dimensions": top_dims,
                "interpretation": cls._interpret_pc(top_dims),
            })
        
        return {
            "n_samples": len(vectors),
            "covariance_matrix_dims": (cls.DIM, cls.DIM),
            "principal_components": pc_analysis,
            "total_variance_explained": round(sum(abs(lam) for lam, _ in eigs) / max(sum(abs(cov.data[i][i]) for i in range(cls.DIM)), 1) * 100, 1),
        }
    
    @classmethod
    def _interpret_pc(cls, top_dims):
        """解释主成分的含义"""
        names = [d[0] for d in top_dims]
        if "emotion_variance" in names and "hook_strength" in names:
            return "情感驱动力（情绪波动+钩子=读者的情感牵引）"
        elif "dialogue_ratio" in names and "sentence_len" in names:
            return "对话节奏（对话率+句长=叙事速度）"
        elif "ngram_unique" in names and "complexity" in names:
            return "语言丰富度（词汇多样性+信息复杂度）"
        elif "action_density" in names and "self_transition" in names:
            return "动作强度（动作密度+句法变化=场面调度）"
        return "综合风格"


# ============================================================
# 2. 傅里叶频谱分析
# ============================================================

class FourierAnalyzer:
    """
    将文本的情绪/密度序列进行离散傅里叶变换，
    分解为频率分量，分析叙事韵律。
    
    核心洞察：
    - 健康的网文应该有0.1-0.3Hz的主频（每3-10句一个情绪波动）
    - 低频过强 = 叙事拖沓
    - 高频过强 = 叙事碎片化
    - 频谱平坦 = 缺乏节奏感
    """
    
    @classmethod
    def extract_emotion_sequence(cls, text) -> List[float]:
        """
        逐句提取情绪值，形成时域信号 f(t)。
        每句话一个情绪采样点。
        """
        sents = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) >= 3]
        if len(sents) < 8:
            return []
        
        pos_words = set("好美强爽喜乐笑爱暖光胜成突破觉醒碾压打脸逆袭开心幸福甜蜜".split())
        neg_words = set("死灭毁暗冷痛苦恨怒怕惨绝望崩溃失败打击悲伤愤怒".split())
        
        sequence = []
        for sent in sents:
            p = sum(1 for w in sent if w in pos_words)
            n = sum(1 for w in sent if w in neg_words)
            total = p + n + 1
            sequence.append((p - n) / total)
        
        return sequence
    
    @classmethod
    def extract_density_sequence(cls, text) -> List[float]:
        """
        逐句提取信息密度（动作词+专有名词的出现频率）。
        """
        sents = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) >= 3]
        if len(sents) < 8:
            return []
        
        action_chars = set("走跑冲抓拿拔砍杀打推拉踢踹挥劈刺射斩翻跃扑闪")
        
        sequence = []
        for sent in sents:
            density = sum(1 for c in sent if c in action_chars) / max(len(sent), 1)
            sequence.append(density)
        
        return sequence
    
    @classmethod
    def dft(cls, sequence: List[float]) -> Dict:
        """
        离散傅里叶变换。
        X[k] = Σ x[n]·exp(-2πi·k·n/N)
        
        返回功率谱：|X[k]|²
        """
        N = len(sequence)
        if N < 4:
            return {"error": "序列过短", "min_required": 4}
        
        # 计算DFT
        spectrum = []
        for k in range(N // 2):
            real = 0.0
            imag = 0.0
            for n in range(N):
                angle = 2 * math.pi * k * n / N
                real += sequence[n] * math.cos(angle)
                imag -= sequence[n] * math.sin(angle)
            power = real**2 + imag**2
            spectrum.append({
                "frequency_idx": k,
                "frequency_hz": k / N,
                "period_sentences": N / (k + 1),
                "power": power,
                "amplitude": math.sqrt(power),
            })
        
        # 归一化功率
        total_power = sum(s["power"] for s in spectrum)
        if total_power > 0:
            for s in spectrum:
                s["normalized_power"] = s["power"] / total_power
        
        # 找出主频
        dominant = max(spectrum, key=lambda s: s["power"])
        
        # 频谱分布
        low_freq = sum(s["power"] for s in spectrum if s["frequency_hz"] < 0.1)
        mid_freq = sum(s["power"] for s in spectrum if 0.1 <= s["frequency_hz"] < 0.3)
        high_freq = sum(s["power"] for s in spectrum if s["frequency_hz"] >= 0.3)
        
        total = low_freq + mid_freq + high_freq
        if total > 0:
            low_ratio = low_freq / total
            mid_ratio = mid_freq / total
            high_ratio = high_freq / total
        else:
            low_ratio = mid_ratio = high_ratio = 0.33
        
        # 诊断
        if mid_ratio > 0.4:
            rhythm_label = "健康律动（中频主导，情绪起伏适中）"
        elif low_ratio > 0.5:
            rhythm_label = "叙事偏慢（低频主导，情绪变化缓慢）"
        elif high_ratio > 0.4:
            rhythm_label = "叙事碎片化（高频主导，节奏零散）"
        else:
            rhythm_label = "频谱分散（缺乏主导节奏）"
        
        return {
            "sequence_length": N,
            "dominant_frequency": round(dominant["frequency_hz"], 3),
            "dominant_period": round(dominant["period_sentences"], 1),
            "dominant_power_ratio": round(dominant.get("normalized_power", 0), 3),
            "spectrum_distribution": {
                "low_freq": round(low_ratio, 3),
                "mid_freq": round(mid_ratio, 3),
                "high_freq": round(high_ratio, 3),
            },
            "rhythm_diagnosis": rhythm_label,
            "rhythm_score": round(min(100, mid_ratio * 150 + 25), 1),
        }
    
    @classmethod
    def analyze(cls, text) -> Dict:
        """完整频谱分析"""
        emotion_seq = cls.extract_emotion_sequence(text)
        density_seq = cls.extract_density_sequence(text)
        
        result = {
            "text_length": len(text),
            "sentence_count": len(emotion_seq),
        }
        
        if emotion_seq:
            result["emotion_spectrum"] = cls.dft(emotion_seq)
        if density_seq:
            result["density_spectrum"] = cls.dft(density_seq)
        
        # 双谱交叉分析
        if emotion_seq and density_seq and len(emotion_seq) == len(density_seq):
            # 情绪与密度的互相关
            n = len(emotion_seq)
            em = sum(emotion_seq) / n
            dm = sum(density_seq) / n
            cross_corr = sum((emotion_seq[i] - em) * (density_seq[i] - dm) for i in range(n))
            cross_corr /= (n - 1) if n > 1 else 1
            result["emotion_density_correlation"] = round(cross_corr, 3)
            if cross_corr > 0.5:
                result["coupling"] = "情绪与密度高度共振（情绪高点即动作高点，典型的爽文节奏）"
            elif cross_corr > 0.2:
                result["coupling"] = "情绪与密度弱正相关"
            elif cross_corr < -0.2:
                result["coupling"] = "情绪与密度负相关（情绪与动作脱节，需注意）"
            else:
                result["coupling"] = "情绪与密度独立运作"
        
        return result


# ============================================================
# 2.5 拉普拉斯变换：钩子衰减的复频域分析
# ============================================================

class LaplaceAnalyzer:
    """
    拉普拉斯变换：将时域的钩子/张力函数映射到复频域（s域）。
    
    数学定义: L{f(t)} = ∫₀^∞ f(t)·e^(-st) dt
    
    写作建模:
    - f(t) = 第t句的钩子强度信号
    - s = 衰减率参数（读者遗忘速度）
    - L{f}(s) = 在遗忘率s下，钩子的"持续影响力"
    
    核心洞察:
    - s→0  (慢衰减): 长期钩子（世界观悬念、人物命运）
    - s→0.5 (中衰减): 中期钩子（章节悬念）
    - s→2  (快衰减): 短期钩子（句末反转、对话悬念）
    
    优质网文需要在三个衰减频段都有足够的能量分布。
    如果长期钩子(s→0)能量为0，说明没有让读者想"知道结局"的东西。
    如果短期钩子(s→2)能量过高，说明靠小技巧撑场面，缺乏实质内容。
    """
    
    @classmethod
    def extract_hook_signal(cls, text) -> List[float]:
        """
        逐句提取钩子强度信号 h(t)。
        
        钩子信号 = 悬念词密度 + 反转语气 + 问题句 + 信息缺口
        """
        sents = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) >= 3]
        if len(sents) < 8:
            return []
        
        # 钩子关键词
        suspense_words = set("突然忽然竟然没想到原来难道为什么究竟到底恐怕万一如果可能秘密真相阴谋意外惊人震惊".split())
        cliffhanger_chars = set("？！…")
        revelation_words = set("原来其实根本真相答案关键终于最后".split())
        question_words = set("为什么怎么难道究竟到底莫非".split())
        
        signals = []
        for sent in sents:
            score = 0.0
            l = len(sent)
            # 悬念词密度
            susp = sum(1 for i in range(len(sent)) for w in suspense_words if sent[i:i+len(w)] in suspense_words)
            score += susp / max(l, 1) * 50
            
            # 反转/悬念标点
            cliff = sum(1 for c in sent if c in cliffhanger_chars)
            score += cliff * 3
            
            # 揭秘词
            rev = sum(1 for c in sent if c in ''.join(revelation_words))
            score += rev * 2
            
            # 疑问句（钩子最强）
            if '？' in sent or '?' in sent:
                score += 5
            
            # 信息缺口（省略号结尾）
            if sent.endswith('…') or sent.endswith('...'):
                score += 4
            
            signals.append(min(10, score))
        
        return signals
    
    @classmethod
    def laplace_transform(cls, signal: List[float], max_s=5.0, n_points=20) -> Dict:
        """
        L{f}(s) = ∫₀^∞ f(t)·e^(-st) dt
        
        对离散信号用梯形法则数值积分。
        采样s ∈ [0, max_s]共n_points个点。
        """
        N = len(signal)
        if N < 4:
            return {"error": "信号过短"}
        
        results = []
        dt = 1.0  # 时间步长=1句
        
        for si in range(n_points):
            s = max_s * si / (n_points - 1) if n_points > 1 else 0
            
            # 梯形积分 ∫ f(t)·e^(-st) dt
            laplace_val = 0.0
            for t in range(N):
                ft = signal[t]
                decay = math.exp(-s * t)
                laplace_val += ft * decay * dt
            
            # 边界修正（梯形法则的半步）
            laplace_val -= (signal[0] * math.exp(-s * 0) + signal[-1] * math.exp(-s * (N-1))) * dt / 2
            
            results.append({
                "s": round(s, 2),
                "decay_rate": "长期(世界观悬念)" if s < 0.3 else "中期(章节悬念)" if s < 1.0 else "短期(句末钩子)",
                "laplace_value": round(laplace_val, 3),
            })
        
        # 三个特征s值的能量
        s_long = cls._interpolate(results, 0.1)
        s_mid = cls._interpolate(results, 0.7)
        s_short = cls._interpolate(results, 2.0)
        
        total = s_long + s_mid + s_short
        if total > 0:
            long_ratio = s_long / total
            mid_ratio = s_mid / total
            short_ratio = s_short / total
        else:
            long_ratio = mid_ratio = short_ratio = 0.33
        
        # 诊断
        diagnoses = []
        if long_ratio < 0.2:
            diagnoses.append("[!] 长期钩子能量不足：缺乏让读者追更的终极悬念")
        if short_ratio > 0.6:
            diagnoses.append("[!] 短期钩子过密：靠小技巧撑场面，缺乏叙事深度")
        if mid_ratio > 0.35:
            diagnoses.append("[OK] 中期钩子充足：章节级悬念驱动良好")
        if long_ratio > 0.3:
            diagnoses.append("[OK] 长期钩子有力：世界观/主线悬念牵引力强")
        
        hook_health = 50
        if long_ratio > 0.25 and mid_ratio > 0.25:
            hook_health = 85
        elif long_ratio > 0.2 or mid_ratio > 0.3:
            hook_health = 65
        elif short_ratio > 0.7:
            hook_health = 30
        
        return {
            "signal_length": N,
            "total_laplace_energy": round(sum(r["laplace_value"] for r in results), 3),
            "frequency_bands": {
                "long_term": round(long_ratio, 3),
                "mid_term": round(mid_ratio, 3),
                "short_term": round(short_ratio, 3),
            },
            "hook_health_score": hook_health,
            "diagnoses": diagnoses if diagnoses else ["钩子能量分布正常"],
            "summary": f"长期{long_ratio:.0%}/中期{mid_ratio:.0%}/短期{short_ratio:.0%} | 健康分{hook_health}",
        }
    
    @staticmethod
    def _interpolate(results, target_s):
        """在结果列表中插值获取指定s值的Laplace值"""
        for i, r in enumerate(results):
            if r["s"] >= target_s:
                if i == 0:
                    return r["laplace_value"]
                prev = results[i-1]
                frac = (target_s - prev["s"]) / (r["s"] - prev["s"]) if r["s"] != prev["s"] else 0
                return prev["laplace_value"] + frac * (r["laplace_value"] - prev["laplace_value"])
        return results[-1]["laplace_value"] if results else 0
    
    @classmethod
    def analyze(cls, text) -> Dict:
        """完整拉普拉斯分析"""
        hook_signal = cls.extract_hook_signal(text)
        if not hook_signal:
            return {"error": "信号提取失败"}
        return cls.laplace_transform(hook_signal)


# ============================================================
# 3. 积分度量：累积函数与衰减卷积
# ============================================================

class IntegralCalculus:
    """
    对叙事弧线执行积分运算。
    
    核心度量：
    - ∫₀^ᵀ |f'(t)| dt  = 总情绪变化量（整章的"事件量"）
    - ∫₀^ᵀ max(0, f(t)) dt = 正向情绪总量
    - 累积张力函数 C(t) = ∫₀ᵗ f(s) ds（递增或递减趋势）
    - 钩子衰减卷积: h(t) * e^(-λt)（读者记忆中的钩子残留）
    """
    
    @classmethod
    def trapezoidal_integrate(cls, sequence: List[float], step=1.0) -> float:
        """梯形法则数值积分 ∫f(t)dt"""
        if len(sequence) < 2:
            return 0
        total = 0
        for i in range(len(sequence) - 1):
            total += (sequence[i] + sequence[i+1]) * step / 2
        return total
    
    @classmethod
    def cumulative_function(cls, sequence: List[float]) -> List[float]:
        """累积函数 C(t) = ∫₀ᵗ f(s) ds"""
        cum = [0.0]
        for i, val in enumerate(sequence):
            cum.append(cum[-1] + val)
        return cum
    
    @classmethod
    def total_variation(cls, sequence: List[float]) -> float:
        """总变差 TV = Σ|Δf|: 衡量序列的总体变化量"""
        if len(sequence) < 2:
            return 0
        return sum(abs(sequence[i+1] - sequence[i]) for i in range(len(sequence)-1))
    
    @classmethod
    def hook_decay_convolution(cls, hook_strength: float, chapters_ago: int, decay_lambda=0.3) -> float:
        """
        钩子衰减卷积。
        第k章前的钩子对当前章读者的残留影响 = strength * e^(-λk)
        """
        return hook_strength * math.exp(-decay_lambda * chapters_ago)
    
    @classmethod
    def analyze_chapter(cls, text) -> Dict:
        """
        对章节进行积分分析。
        返回情绪弧线的各种积分度量。
        """
        emotion = FourierAnalyzer.extract_emotion_sequence(text)
        density = FourierAnalyzer.extract_density_sequence(text)
        
        result = {}
        
        if emotion and len(emotion) >= 4:
            # 总情绪能
            total_energy = cls.trapezoidal_integrate(emotion)
            
            # 正向/负向情绪面积
            pos_energy = cls.trapezoidal_integrate([max(0, e) for e in emotion])
            neg_energy = abs(cls.trapezoidal_integrate([min(0, e) for e in emotion]))
            
            # 总变差（事件的量）
            tv = cls.total_variation(emotion)
            
            # 累积函数
            cum = cls.cumulative_function(emotion)
            cum_end = cum[-1]  # 结尾累积值：正=情绪净正向
            
            # 情绪曲线形状
            if abs(emotion[0]) > abs(emotion[-1]):
                arc_shape = "V形弧线（先抑后扬）" if cum_end > 0 else "倒V形（开始有力/逐渐疲软）"
            elif emotion[-1] > emotion[0]:
                arc_shape = "上升弧线（情绪递增，爽文常规）"
            else:
                arc_shape = "下降弧线（情绪递减，注意节奏）"
            
            result["emotional_arc"] = {
                "total_energy": round(total_energy, 2),
                "positive_area": round(pos_energy, 2),
                "negative_area": round(neg_energy, 2),
                "pos_neg_ratio": round(pos_energy / max(neg_energy, 0.01), 1),
                "total_variation": round(tv, 2),
                "cumulative_endpoint": round(cum_end, 2),
                "arc_shape": arc_shape,
                "energy_density": round(total_energy / max(len(emotion), 1), 4),  # 单位句长能量
            }
            
            # 质量评分
            if abs(pos_energy / max(neg_energy, 0.01) - 2) < 1:
                arc_score = 75  # 接近2:1正负比 = 爽文黄金比例
            elif pos_energy > neg_energy:
                arc_score = 60
            else:
                arc_score = 40
            result["arc_quality_score"] = round(arc_score + min(25, tv * 10), 1)
        
        return result
    
    @classmethod
    def analyze_sequence(cls, chapter_results: List[Dict]) -> Dict:
        """
        跨章节积分分析。
        连起来看整卷的情绪走势。
        """
        if len(chapter_results) < 2:
            return {"error": "需要至少2章"}
        
        # 提取每章的指标
        energies = []
        arcs = []
        for r in chapter_results:
            arc = r.get("emotional_arc", {})
            if arc:
                energies.append(arc.get("total_energy", 0))
                arcs.append(arc.get("arc_shape", ""))
        
        if not energies:
            return {"error": "无有效数据"}
        
        # 总体能量趋势
        mean_energy = sum(energies) / len(energies)
        variances = [(e - mean_energy)**2 for e in energies]
        energy_variance = sum(variances) / len(variances)
        
        # 能量单调性检测
        increasing = sum(1 for i in range(len(energies)-1) if energies[i+1] > energies[i])
        decreasing = sum(1 for i in range(len(energies)-1) if energies[i+1] < energies[i])
        total_pairs = len(energies) - 1
        
        if increasing / max(total_pairs, 1) > 0.7:
            trend = "能量持续攀升（优质连载特征）"
        elif decreasing / max(total_pairs, 1) > 0.7:
            trend = "能量持续下降（读者流失风险）"
        else:
            trend = "能量波动（需要稳定节奏）"
        
        return {
            "chapter_count": len(chapter_results),
            "mean_energy": round(mean_energy, 2),
            "energy_variance": round(energy_variance, 2),
            "energy_trend": trend,
            "arch_shapes": Counter(arcs).most_common(3),
        }


# ============================================================
# 4. 马尔可夫叙事链
# ============================================================

class MarkovNarrative:
    """
    将叙事视为马尔可夫链。
    
    叙事状态空间: {conflict, resolution, exposition, climax, dialogue, action, transition}
    状态转移由文本特征决定（不是预分类，而是从特征向量推断）。
    
    核心运算:
    - 转移矩阵 P: P_ij = P(st_{t+1}=j | st_t=i)
    - 稳态分布 π: πP = π（长期叙事平衡态）
    - 吸收态检测：是否存在无法逃脱的状态？
    """
    
    STATES = ["exposition", "dialogue", "action", "conflict", "climax", "resolution", "transition"]
    N_STATES = len(STATES)
    
    @classmethod
    def classify_sentence(cls, sent, prev_state=None):
        """根据句子特征归类叙事状态"""
        l = len(sent)
        has_dialogue = bool(re.search(r'["""]|说|道|问|答', sent))
        has_action = bool(re.search(r'走|跑|冲|抓|拿|拔|砍|杀|打|推|拉|踢|踹|挥|劈|刺|射|斩|翻|跃|扑|闪', sent))
        has_conflict = bool(re.search(r'怒|恨|杀|灭|死|痛|恐|怕|绝望|危险|威胁', sent))
        has_climax = bool(re.search(r'轰|爆|炸|裂|碎|一瞬间|猛然|骤然|突然|猛然间', sent))
        has_resolution = bool(re.search(r'终于|最后|后来|之后|从此|于是|就这样|便|就', sent))
        has_transition = bool(re.search(r'时间|转眼|片刻|不久|渐渐|慢慢|忽然|突然', sent))
        
        if has_climax and has_action:
            return "climax"
        elif has_dialogue and l < 50:
            return "dialogue"
        elif has_action:
            return "action"
        elif has_conflict:
            return "conflict"
        elif has_resolution:
            return "resolution"
        elif has_transition:
            return "transition"
        else:
            return "exposition"
    
    @classmethod
    def build_chain(cls, text) -> Dict:
        """
        从文本构建马尔可夫链。
        返回转移矩阵、稳态分布等。
        """
        sents = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) >= 5]
        if len(sents) < 10:
            return {"error": "句子不足", "min_required": 10}
        
        # 分类每句话
        states = []
        prev = None
        for sent in sents:
            state = cls.classify_sentence(sent, prev)
            states.append(state)
            prev = state
        
        # 构建转移计数矩阵
        trans_count = [[0] * cls.N_STATES for _ in range(cls.N_STATES)]
        for t in range(len(states) - 1):
            i = cls.STATES.index(states[t])
            j = cls.STATES.index(states[t+1])
            trans_count[i][j] += 1
        
        # 转为概率矩阵
        trans_prob = [[0.0] * cls.N_STATES for _ in range(cls.N_STATES)]
        for i in range(cls.N_STATES):
            total = sum(trans_count[i])
            if total > 0:
                for j in range(cls.N_STATES):
                    trans_prob[i][j] = trans_count[i][j] / total
            else:
                trans_prob[i][i] = 1.0  # 吸收态
        
        # 稳态分布（幂迭代）
        pi = [1.0 / cls.N_STATES] * cls.N_STATES
        for _ in range(50):
            new_pi = [0.0] * cls.N_STATES
            for j in range(cls.N_STATES):
                for i in range(cls.N_STATES):
                    new_pi[j] += pi[i] * trans_prob[i][j]
            pi = new_pi
        
        # 状态分布
        state_count = Counter(states)
        total = len(states)
        state_dist = {s: state_count.get(s, 0) / total for s in cls.STATES}
        
        # 解释
        dominant = max(state_dist, key=state_dist.get)
        dom_ratio = state_dist[dominant]
        
        if dom_ratio > 0.5:
            chain_health = f"叙事偏于{dominant}（{dom_ratio:.0%}），过于单一"
            health_score = 30
        elif dom_ratio > 0.35:
            chain_health = f"{dominant}为主（{dom_ratio:.0%}），基本健康"
            health_score = 60
        else:
            chain_health = "叙事状态分散，变化丰富"
            health_score = 80
        
        # 计算吸收概率
        absorbing = []
        for i in range(cls.N_STATES):
            if abs(trans_prob[i][i] - 1.0) < 0.01:
                absorbing.append(cls.STATES[i])
        
        return {
            "sentence_count": len(sents),
            "state_distribution": state_dist,
            "steady_state": {cls.STATES[i]: round(pi[i], 3) for i in range(cls.N_STATES)},
            "transition_matrix": {cls.STATES[i]: {cls.STATES[j]: round(trans_prob[i][j], 3) for j in range(cls.N_STATES)} for i in range(cls.N_STATES)},
            "absorbing_states": absorbing if absorbing else ["无"],
            "chain_health": chain_health,
            "health_score": health_score,
            "mixing_time_estimate": cls._mixing_time(trans_prob),
        }
    
    @classmethod
    def _mixing_time(cls, trans_prob):
        """
        用幂迭代估计转移矩阵的第二大特征值，计算混合时间。
        混合时间 ≈ 1 / (1 - |λ₂|)，λ₂是第二大特征值（第一大为1）。
        """
        try:
            n = len(trans_prob)
            if n <= 1:
                return 1
            # 构造Matrix对象求特征值
            m = Matrix(n, n, [row[:] for row in trans_prob])
            eigs = m.eigenvalues(3)
            # 找第二大特征值（排除≈1的第一大）
            second_eig = 0.5  # 默认
            for lam, _ in eigs:
                if abs(lam - 1.0) > 0.01:  # 不是最大特征值1
                    second_eig = abs(lam)
                    break
            if second_eig >= 1.0:
                return 50  # 周期性链
            return max(1, int(1 / (1 - second_eig)))
        except Exception:
            return 10
    
    @classmethod
    def _estimate_eigen(cls, matrix):
        """估计转移矩阵的特征值（用于混合时间）"""
        # 简化：用幂迭代近似第二大特征值
        results = [(1.0, [])]  # 第一大特征值=1（马尔可夫性）
        # 返回[(eigval, eigvec)]列表
        return results


# ============================================================
# 5. 信息论：从香农熵到KL散度
# ============================================================

class InformationTheory:
    """
    信息论分析套件。
    
    - 香农熵 H(X) = -Σ p(x) log p(x)：词汇/句式的不可预测性
    - KL散度 D(P||Q) = Σ P(x) log P(x)/Q(x)：两个分布的"距离"
    - 互信息 I(X;Y)：两个特征之间的依赖性
    """
    
    @classmethod
    def shannon_entropy(cls, counter: Counter, total=None) -> float:
        """计算香农熵"""
        if total is None:
            total = sum(counter.values())
        if total == 0:
            return 0
        return -sum((c / total) * math.log2(c / total) for c in counter.values() if c > 0)
    
    @classmethod
    def word_entropy(cls, text) -> Dict:
        """词汇熵：衡量词汇多样性"""
        clean = text.replace('\n', '')
        # Bigram频率
        bigrams = [clean[i:i+2] for i in range(len(clean)-1)]
        bigram_counter = Counter(bigrams)
        
        # 字符频率
        char_counter = Counter(clean)
        
        bigram_entropy = cls.shannon_entropy(bigram_counter)
        char_entropy = cls.shannon_entropy(char_counter)
        
        max_bigram = math.log2(len(bigram_counter)) if bigram_counter else 10
        
        return {
            "bigram_entropy": round(bigram_entropy, 2),
            "char_entropy": round(char_entropy, 2),
            "bigram_uniqueness": round(len(bigram_counter) / max(len(bigrams), 1), 3),
            "vocab_richness": round(bigram_entropy / max(max_bigram, 1), 3) if max_bigram > 0 else 0,
            "interpretation": "词汇丰富多变" if bigram_entropy > 7 else 
                             "词汇适中" if bigram_entropy > 5 else
                             "词汇重复较多，需扩充"
        }
    
    @classmethod
    def kl_divergence(cls, P: Counter, Q: Counter, smooth=0.01) -> float:
        """
        KL散度 D_KL(P||Q) = Σ P(x) log(P(x)/Q(x))
        衡量P分布相对于Q分布的"信息损失"。
        """
        all_keys = set(P.keys()) | set(Q.keys())
        total_p = sum(P.values())
        total_q = sum(Q.values())
        
        kl = 0.0
        for key in all_keys:
            p = (P.get(key, 0) + smooth) / (total_p + smooth * len(all_keys))
            q = (Q.get(key, 0) + smooth) / (total_q + smooth * len(all_keys))
            kl += p * math.log2(p / q)
        
        return kl
    
    @classmethod
    def js_distance(cls, P: Counter, Q: Counter) -> float:
        """
        Jensen-Shannon距离（对称化KL散度）。
        更稳定的分布距离度量。
        """
        M = Counter()
        all_keys = set(P.keys()) | set(Q.keys())
        total_p = sum(P.values())
        total_q = sum(Q.values())
        for k in all_keys:
            M[k] = (P.get(k, 0) / max(total_p, 1) + Q.get(k, 0) / max(total_q, 1)) / 2
        return math.sqrt((cls.kl_divergence(P, M) + cls.kl_divergence(Q, M)) / 2)
    
    @classmethod
    def compare_texts(cls, text1, text2) -> Dict:
        """
        用信息论方法比较两个文本。
        JS距离越小 = 风格越接近。
        """
        from collections import Counter
        
        # Bigram分布
        c1 = ''.join(text1.replace('\n', ''))
        c2 = ''.join(text2.replace('\n', ''))
        bg1 = Counter([c1[i:i+2] for i in range(len(c1)-1)])
        bg2 = Counter([c2[i:i+2] for i in range(len(c2)-1)])
        
        js_dist = cls.js_distance(bg1, bg2)
        
        # 各自的信息熵
        h1 = cls.shannon_entropy(bg1)
        h2 = cls.shannon_entropy(bg2)
        
        return {
            "js_distance": round(js_dist, 4),
            "style_similarity": round(max(0, 1 - js_dist / 2), 3),  # 归一化到 [0,1]
            "h1_entropy": round(h1, 2),
            "h2_entropy": round(h2, 2),
            "interpretation": "高度相似" if js_dist < 0.3 else
                             "中度相似" if js_dist < 0.6 else
                             "风格差异大",
        }
    
    @classmethod
    def mutual_information(cls, text, dim1_extractor, dim2_extractor, n_bins=5) -> float:
        """
        两个特征维度之间的互信息。
        量化"知道dim1后，dim2的不确定性减少了多少"。
        
        例如：dim1="对话率的高低" dim2="钩子强度的高低"
        高互信息 → 两者有强关联 → 在写作时可联动优化。
        """
        pass  # 需样本充足时才有意义，先占位


# ============================================================
# 6. 统一数学引擎
# ============================================================

class PanguMathEngine:
    """
    盘古AI统一数学引擎。
    集成了线性代数、傅里叶分析、积分学、马尔可夫链、信息论。
    
    使用方式:
        engine = PanguMathEngine()
        result = engine.full_analysis(text)
        
        # 写作优化
        guidance = engine.write_optimization(result)
    """
    
    def __init__(self):
        self.la = LinearAlgebraEngine()
        self.fourier = FourierAnalyzer()
        self.laplace = LaplaceAnalyzer()
        self.integral = IntegralCalculus()
        self.markov = MarkovNarrative()
        self.info = InformationTheory()
    
    def full_analysis(self, text, chapter_num=1) -> Dict:
        """对一段文本运行全部数学分析。
        
        文本<100字：返回基线结果
        100-299字：返回轻量分析
        300+字：完整全分析
        """
        text_len = len(text)
        
        # 基线结果（文本过短时）
        baseline = {
            "chapter_num": chapter_num,
            "text_length": text_len,
            "mode": "baseline" if text_len < 100 else "light" if text_len < 300 else "full",
            "style_vector": {},
            "vector_norm": 0,
            "fourier_analysis": {"note": "文本过短，省略傅里叶分析"},
            "laplace_analysis": {"hook_health_score": 50, "summary": "文本过短，钩子分析不可靠"},
            "integral_analysis": {"emotional_arc": {}, "arc_quality_score": 50},
            "markov_chain": {"state_distribution": {}, "chain_health": "未知", "health_score": 50},
            "information_metrics": {"bigram_entropy": 5.0, "vocab_richness": 0.5},
            "overall_math_score": 50,
        }
        
        if text_len < 100:
            return baseline
        
        # 提取向量
        style_vec = LinearAlgebraEngine.extract_vector(text)
        
        # 各层分析（按文本长度降级）
        fourier_result = FourierAnalyzer.analyze(text) if text_len >= 300 else baseline["fourier_analysis"]
        laplace_result = LaplaceAnalyzer.analyze(text) if text_len >= 300 else baseline["laplace_analysis"]
        integral_result = IntegralCalculus.analyze_chapter(text) if text_len >= 200 else baseline["integral_analysis"]
        markov_result = MarkovNarrative.build_chain(text) if text_len >= 100 else baseline["markov_chain"]
        info_result = InformationTheory.word_entropy(text) if text_len >= 100 else baseline["information_metrics"]
        
        # 综合评分
        scores_weights = []
        if isinstance(fourier_result, dict) and fourier_result.get("emotion_spectrum"):
            rs = fourier_result["emotion_spectrum"].get("rhythm_score", 50)
            if isinstance(rs, (int, float)):
                scores_weights.append((rs, 0.20))
        if isinstance(laplace_result, dict) and laplace_result.get("hook_health_score"):
            ls = laplace_result["hook_health_score"]
            if isinstance(ls, (int, float)):
                scores_weights.append((ls, 0.20))
        if isinstance(integral_result, dict) and integral_result.get("arc_quality_score") and isinstance(integral_result["arc_quality_score"], (int, float)):
            scores_weights.append((integral_result["arc_quality_score"], 0.20))
        if isinstance(markov_result, dict) and markov_result.get("health_score") and isinstance(markov_result["health_score"], (int, float)):
            scores_weights.append((markov_result["health_score"], 0.20))
        if isinstance(info_result, dict) and info_result.get("vocab_richness") and isinstance(info_result["vocab_richness"], (int, float)):
            scores_weights.append((info_result["vocab_richness"] * 100, 0.20))
        
        if scores_weights:
            total_weight = sum(w for _, w in scores_weights)
            overall = sum(s * w for s, w in scores_weights) / total_weight if total_weight > 0 else 50
        else:
            overall = 50
        
        result = {
            "chapter_num": chapter_num,
            "text_length": text_len,
            "mode": "full" if text_len >= 300 else "light",
            "style_vector": {LinearAlgebraEngine.FEATURES[i]: round(style_vec[i], 3) for i in range(min(LinearAlgebraEngine.DIM, len(style_vec)))},
            "vector_norm": round(style_vec.norm(), 3) if hasattr(style_vec, 'norm') else 0,
            "fourier_analysis": fourier_result,
            "laplace_analysis": laplace_result,
            "integral_analysis": integral_result,
            "markov_chain": markov_result,
            "information_metrics": info_result,
            "overall_math_score": round(overall, 1),
        }
        
        return result
    
    def compare_chapters(self, text1, text2) -> Dict:
        """比较两个章节在数学意义上的差异"""
        # 向量空间比较
        vector_comp = LinearAlgebraEngine.compare(text1, text2)
        
        # 信息论比较
        info_comp = InformationTheory.compare_texts(text1, text2)
        
        # 马尔可夫比较
        m1 = MarkovNarrative.build_chain(text1)
        m2 = MarkovNarrative.build_chain(text2)
        
        # 综合差异分数（越小越相似）
        composite_diff = (
            (1 - vector_comp["cosine_similarity"]) * 0.4 +
            (info_comp["js_distance"]) * 0.4 +
            (abs(m1.get("health_score", 50) - m2.get("health_score", 50)) / 100) * 0.2
        )
        
        return {
            "vector_space": vector_comp,
            "information_theory": info_comp,
            "markov": {"ch1_health": m1.get("health_score"), "ch2_health": m2.get("health_score")},
            "composite_difference": round(composite_diff, 3),
            "are_by_same_author": composite_diff < 0.3,  # 阈值判断
        }
    
    def corpus_pca(self, texts: List[str]) -> Dict:
        """对一组文本进行PCA分析，找出风格主导方向"""
        return LinearAlgebraEngine.analyze_corpus(texts)
    
    def get_guidance_prompt(self, result: Dict, platform: str = "qimao") -> str:
        """
        将数学分析结果翻译为可注入AI prompt的写作优化指引。
        每一行都是基于具体数学度量的可操作建议。
        """
        if "error" in result:
            return ""
        
        lines = []
        score = result.get("overall_math_score", 50)
        
        # 开场
        lines.append(f"[数学引擎诊断] 本章综合质量分: {score:.0f}/100")
        
        # === 拉普拉斯分析 (钩子衰减) ===
        laplace = result.get("laplace_analysis", {})
        if laplace.get("frequency_bands"):
            bands = laplace["frequency_bands"]
            lines.append(f"  [拉普拉斯] 钩子能量分布: 长期{bands['long_term']:.0%} 中期{bands['mid_term']:.0%} 短期{bands['short_term']:.0%}")
            for diag in laplace.get("diagnoses", []):
                lines.append(f"    {diag}")
            
            # 可操作建议
            if bands["long_term"] < 0.2:
                lines.append("    → 建议：在章节中暗示或推进主线悬念（如：主角的终极目标、隐藏真相的线索）")
            if bands["short_term"] > 0.6:
                lines.append("    → 建议：减少句末反转技巧，增加实质性情节推进")
        
        # === 傅里叶分析 ===
        fourier = result.get("fourier_analysis", {})
        if fourier.get("emotion_spectrum"):
            fs = fourier["emotion_spectrum"]
            lines.append(f"  [傅里叶] 叙事节律: {fs.get('rhythm_diagnosis', '')}")
            dist = fs.get("spectrum_distribution", {})
            if dist.get("low_freq", 0) > 0.5:
                lines.append("    → 建议：增加情绪波动频次，每3-5句出现一次情绪变化")
            if dist.get("high_freq", 0) > 0.4:
                lines.append("    → 建议：放缓节奏，给读者喘息空间，合并零散的情绪碎片")
        
        if fourier.get("coupling"):
            lines.append(f"  [交叉谱] 情绪-密度耦合: {fourier['coupling']}")
        
        # === 积分分析 ===
        integral = result.get("integral_analysis", {})
        arc = integral.get("emotional_arc", {})
        if arc:
            lines.append(f"  [积分] 情绪弧线: {arc.get('arc_shape', '')}")
            ratio = arc.get("pos_neg_ratio", 0)
            if ratio < 1.5:
                lines.append("    → 建议：增加正向情绪比重，爽文黄金正负比约为2:1")
            elif ratio > 4:
                lines.append("    → 建议：适度增加冲突/挫折，避免情绪过于平坦")
            lines.append(f"    → 总事件量(TV): {arc.get('total_variation', 0):.1f}")
        
        # === 马尔可夫 ===
        markov = result.get("markov_chain", {})
        if markov.get("chain_health"):
            lines.append(f"  [马尔可夫] 叙事状态: {markov['chain_health']}")
            dist_m = markov.get("state_distribution", {})
            if dist_m:
                # 找出过高的状态
                for s, v in dist_m.items():
                    if v > 0.5:
                        lines.append(f"    → 建议：{s}占比{v:.0%}过高，需要增加其他叙事状态的穿插")
        
        # === 信息论 ===
        info = result.get("information_metrics", {})
        if info:
            lines.append(f"  [信息论] 词汇熵: {info.get('bigram_entropy', 0):.1f}bits | {info.get('interpretation', '')}")
            if info.get("vocab_richness", 1) < 0.5:
                lines.append("    → 建议：扩充词汇量，避免重复使用相同的表达模式")
        
        # === 平台微调 ===
        platform_tips = {
            "qimao": "七猫：保持2:1正负情绪比，黄金三章钩子密度≥0.3",
            "fanqie": "番茄：首句即冲突，500字内亮金手指，对话率≥40%",
            "qidian": "起点：世界观深度优先，句法复杂度可高于其他平台",
        }
        lines.append(f"  [平台] {platform_tips.get(platform, platform_tips['qimao'])}")
        
        # 总结
        if score >= 75:
            lines.append("  [结论] 本章数学质量良好，可按当前方向继续")
        elif score >= 55:
            lines.append("  [结论] 本章基本合格，请根据上述建议微调")
        else:
            lines.append("  [结论] [!!] 本章数学质量偏低，建议重点关注上述优化方向后重写")
        
        return "\n".join(lines)
    
    def sequence_analysis(self, chapter_texts: List[str]) -> Dict:
        """
        对连续章节序列进行跨章数学分析。
        这是"全卷级"的数学视角。
        """
        results = []
        for i, text in enumerate(chapter_texts):
            if len(text) < 500:
                continue
            r = self.full_analysis(text, i + 1)
            results.append(r)
        
        if len(results) < 2:
            return {"error": "需要至少2章", "found": len(results)}
        
        # 积分序列分析
        integral_results = [r.get("integral_analysis", {}) for r in results]
        seq_integral = IntegralCalculus.analyze_sequence(integral_results)
        
        # 风格漂移检测
        vectors = [LinearAlgebraEngine.extract_vector(t) for t in chapter_texts if len(t) > 500]
        drift = 0
        if len(vectors) >= 2:
            for i in range(len(vectors) - 1):
                drift += vectors[i].distance(vectors[i+1])
            drift /= (len(vectors) - 1)
        
        # 评分
        scores = [r["overall_math_score"] for r in results]
        score_trend = "上升" if len(scores) >= 2 and scores[-1] > scores[0] else "下降" if scores[-1] < scores[0] else "持平"
        
        return {
            "chapter_count": len(results),
            "mean_score": round(sum(scores) / len(scores), 1),
            "score_trend": score_trend,
            "style_drift_per_chapter": round(drift, 4),
            "integral_sequence": seq_integral,
            "chapter_scores": {r["chapter_num"]: r["overall_math_score"] for r in results},
        }


# ============================================================
# 7. 命令行接口
# ============================================================

def format_analysis(result):
    """格式化输出完整分析"""
    print(f"\n{'='*60}")
    print(f"  盘古数学引擎 — 完整分析")
    print(f"{'='*60}")
    
    if "error" in result:
        print(f"  [ERROR] {result['error']}")
        return
    
    print(f"  综合数学评分: {result['overall_math_score']:.1f}/100")
    print(f"  风格向量范数: {result['vector_norm']:.3f}")
    
    # 傅里叶
    fourier = result.get("fourier_analysis", {})
    if fourier.get("emotion_spectrum"):
        fs = fourier["emotion_spectrum"]
        print(f"\n  [傅里叶频谱] {fs.get('rhythm_diagnosis', '')}")
        print(f"    主频: {fs.get('dominant_frequency', 0):.3f}Hz "
              f"(每{fs.get('dominant_period', 0):.1f}句一个节拍)")
        dist = fs.get("spectrum_distribution", {})
        print(f"    频谱分布: 低{dist.get('low_freq', 0):.1%} "
              f"中{dist.get('mid_freq', 0):.1%} "
              f"高{dist.get('high_freq', 0):.1%}")
    
    if fourier.get("coupling"):
        print(f"    情绪-密度耦合: {fourier['coupling']}")
    
    # 拉普拉斯
    laplace = result.get("laplace_analysis", {})
    if laplace.get("frequency_bands"):
        bands = laplace["frequency_bands"]
        print(f"\n  [拉普拉斯变换] 钩子衰减分析")
        print(f"    能量分布: 长期{bands['long_term']:.0%} 中期{bands['mid_term']:.0%} 短期{bands['short_term']:.0%}")
        for d in laplace.get("diagnoses", []):
            print(f"    {d}")
        print(f"    钩子健康分: {laplace.get('hook_health_score', 50)}/100")
    
    # 积分
    integral = result.get("integral_analysis", {})
    if integral.get("emotional_arc"):
        arc = integral["emotional_arc"]
        print(f"\n  [积分分析] {arc.get('arc_shape', '')}")
        print(f"    情绪总面积: {arc.get('total_energy', 0):.2f}")
        print(f"    正负面积比: {arc.get('pos_neg_ratio', 0):.1f}:1")
        print(f"    总变差(事件量): {arc.get('total_variation', 0):.2f}")
    
    # 马尔可夫
    markov = result.get("markov_chain", {})
    if markov.get("chain_health"):
        print(f"\n  [马尔可夫链] {markov['chain_health']}")
        dom = markov.get("state_distribution", {})
        print(f"    状态分布: " + " ".join(
            f"{s}={dom.get(s, 0):.1%}" for s in MarkovNarrative.STATES))
    
    # 信息论
    info = result.get("information_metrics", {})
    print(f"\n  [信息论] {info.get('interpretation', '')}")
    print(f"    Bigram熵: {info.get('bigram_entropy', 0):.2f} bits")
    print(f"    词汇丰富度: {info.get('vocab_richness', 0):.3f}")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("盘古AI数学核心引擎")
        print("=" * 40)
        print("分析命令:")
        print("  analyze <file>                 - 完整数学分析")
        print("  compare <file1> <file2>        - 两章比较")
        print("  sequence <dir>                 - 序列分析")
        print("  corpus <dir> [n]               - PCA/主成分分析")
        return
    
    cmd = sys.argv[1]
    engine = PanguMathEngine()
    
    if cmd == "analyze":
        target = sys.argv[2]
        ch_num = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        text = Path(target).read_text(encoding='utf-8', errors='ignore')
        result = engine.full_analysis(text, ch_num)
        format_analysis(result)
    
    elif cmd == "compare":
        t1 = Path(sys.argv[2]).read_text(encoding='utf-8', errors='ignore')
        t2 = Path(sys.argv[3]).read_text(encoding='utf-8', errors='ignore')
        result = engine.compare_chapters(t1, t2)
        print(f"\n两章数学比较:")
        print(f"  余弦相似度: {result['vector_space']['cosine_similarity']:.3f}")
        print(f"  JS风格距离: {result['information_theory']['js_distance']:.4f}")
        print(f"  复合差异: {result['composite_difference']:.3f}")
        print(f"  同作者判定: {result['are_by_same_author']}")
        if not result['are_by_same_author']:
            max_dim = result['vector_space']['max_divergence_dim']
            diff = result['vector_space']['dimension_differences'][max_dim]
            print(f"  最大差异维度: {max_dim} ({diff:+.3f})")
    
    elif cmd == "sequence":
        target_dir = Path(sys.argv[2])
        txts = sorted(target_dir.glob("**/*.txt"))[:10]
        texts = []
        for t in txts:
            text = t.read_text(encoding='utf-8', errors='ignore')
            if len(text) > 500:
                texts.append(text)
        
        result = engine.sequence_analysis(texts)
        if "error" in result:
            print(f"[ERROR] {result['error']}")
        else:
            print(f"\n序列分析 ({result['chapter_count']}章):")
            print(f"  均分: {result['mean_score']:.1f} | 趋势: {result['score_trend']}")
            print(f"  风格漂移/章: {result['style_drift_per_chapter']:.4f}")
            for ch, sc in result["chapter_scores"].items():
                bar = "#" * int(sc / 5) + "-" * (20 - int(sc / 5))
                print(f"  第{ch}章: [{bar}] {sc:.1f}")
    
    elif cmd == "corpus":
        target_dir = Path(sys.argv[2])
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        txts = list(target_dir.glob("**/*.txt"))[:n]
        texts = [t.read_text(encoding='utf-8', errors='ignore') for t in txts if t.stat().st_size > 1000]
        
        result = engine.corpus_pca(texts)
        if "error" in result:
            print(f"[ERROR] {result['error']}")
        else:
            print(f"\nPCA分析 ({result['n_samples']}个样本):")
            for pc in result["principal_components"]:
                print(f"\n  PC{pc['pc']}: {pc['explained_variance']}% 方差解释")
                print(f"  λ={pc['eigenvalue']:.4f}")
                print(f"  主导维度: {', '.join(f'{d}({w:.2f})' for d, w in pc['dominant_dimensions'])}")
                print(f"  含义: {pc['interpretation']}")


if __name__ == "__main__":
    main()
