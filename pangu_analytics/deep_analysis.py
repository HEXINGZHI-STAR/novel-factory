"""
盘古 · 深度文本分析 (吸收 StyloMetrix + qhchina + pybiber)

不依赖外部NLP包，直接用 numpy/scikit-learn 实现:
  1. 50维风格指纹 (吸收StyloMetrix的270维核心)
  2. LDA主题自动发现 (吸收qhchina的中文主题建模)
  3. 多维语域分析 (吸收pybiber的Biber 67维方法)

对4,475本参考书的应用:
  - 自动发现"悬疑"和"刑侦"的统计差异 → 题材细分
  - 检测哪些书是真正的悬疑推理 (而非标签错误)
  - 多维度语域分析 → 七猫爽文 vs 知乎盐选的区别
"""

from __future__ import annotations

import re, math
from typing import List, Dict, Tuple
from collections import Counter


# ================================================================
# 1. 50维扩展风格指纹
# ================================================================

class DeepStylometry:
    """
    50维风格指纹 (吸收 StyloMetrix 的 270 维核心)。

    维度分布:
      1-10:  词汇 (TTR, Hapax, 高频词密度, Yule's K, 熵)
      11-20: 句法 (句均, CV, 从句密度, 被动语态, 疑问句比)
      21-30: 语法 (虚词密度, 连词密度, 代词密度, 助词比)
      31-40: 标点 (逗/句/问/叹/引/省略 各自密度+熵)
      41-50: 结构 (段均, 段CV, 短段比, 对话密度, 叙述密度)
    """

    @classmethod
    def extract(cls, text: str) -> List[float]:
        features = []
        chars = re.sub(r'[^一-鿿]', '', text)
        total = max(len(chars), 1)

        # === 词汇维 (1-10) ===
        char_counter = Counter(chars)
        unique = len(char_counter)
        features.append(unique / total)                    # 1. TTR
        hapax = sum(1 for c in char_counter.values() if c == 1)
        features.append(hapax / max(unique, 1))            # 2. Hapax ratio
        top50 = sum(c for _, c in char_counter.most_common(50))
        features.append(top50 / total)                      # 3. Top50覆盖率
        # Yule's K = 10^4 * Σ(V(m,2)) / N^2
        yule = sum(c * (c - 1) for c in char_counter.values())
        features.append(min(1.0, yule / (total * total)))  # 4. Yule's K (归一化)
        # 熵
        ent = -sum((c/total) * math.log2(c/total) for c in char_counter.values())
        features.append(ent / math.log2(max(unique, 2)))   # 5. 归一化熵
        # 5个占位 (对外来词/成语/俗语/古语/方言 — 需要词典)
        features.extend([0.0] * 5)                         # 6-10

        # === 句法维 (11-20) ===
        sentences = re.split(r'[。！？!?\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 2]
        if sentences:
            lens = [len(s) for s in sentences]
            mu = sum(lens) / len(lens)
            features.append(mu / 50)                        # 11. 句均 (归一化)
            sigma = math.sqrt(sum((l - mu)**2 for l in lens) / len(lens))
            features.append(sigma / max(mu, 1))             # 12. CV
            features.append(sum(1 for l in lens if l >= 31) / len(lens))  # 13. 长句率
            features.append(sum(1 for l in lens if l <= 10) / len(lens))  # 14. 短句率
        else:
            features.extend([0.0] * 4)

        # 从句密度 (逗号密度近似)
        features.append(text.count('，') / total)           # 15. 逗号密度
        features.append(text.count('的') / total)           # 16. 的字密度
        features.append(text.count('被') / total)           # 17. 被动语态
        q_count = text.count('？') + text.count('?')
        features.append(q_count / max(len(sentences), 1))   # 18. 问句比
        features.extend([0.0] * 2)                          # 19-20 占位

        # === 语法维 (21-30) ===
        func_words = '的了一是在有和就不也都要会可能还把被从对到'
        features.append(sum(text.count(w) for w in func_words) / total)  # 21. 虚词密度
        conjunctions = '和与或者但是然而因此所以如果虽然不过'
        features.append(sum(text.count(w) for w in conjunctions) / total)  # 22. 连词密度
        pronouns = '你我他她它我们你们他们自己'
        features.append(sum(text.count(w) for w in pronouns) / total)      # 23. 代词密度
        features.extend([0.0] * 7)                          # 24-30 占位

        # === 标点维 (31-40) ===
        punct = {'，': 0, '。': 0, '？': 0, '！': 0, '"': 0, '"': 0, '"': 0, '"': 0, '：': 0, '；': 0, '…': 0}
        total_punct = 0
        for ch in text:
            if ch in punct:
                punct[ch] += 1
                total_punct += 1
        for p in punct:
            features.append(punct[p] / max(total_punct, 1))  # 31-40
        # 补齐到10个
        needed = 10 - len(punct)
        features.extend([0.0] * max(0, needed))

        # === 结构维 (41-50) ===
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) > 1:
            plens = [len(p) for p in paragraphs]
            pmean = sum(plens) / len(plens)
            features.append(pmean / 500)                    # 41. 段均
            pstd = math.sqrt(sum((l - pmean)**2 for l in plens) / len(plens))
            features.append(pstd / max(pmean, 1))           # 42. 段CV
            features.append(sum(1 for l in plens if l <= 80) / len(plens))  # 43. 短段比
        else:
            features.extend([0.0] * 3)

        # 对话密度
        dialogues = re.findall(r'[\"\"「]([^\"\"」]{2,})[\"\"」]', text)
        dia_chars = sum(len(d) for d in dialogues)
        features.append(dia_chars / total)                  # 44. 对话密度

        features.extend([0.0] * 6)                          # 45-50 占位

        return features[:50]  # 确保恰好50维


# ================================================================
# 2. LDA 主题自动发现 (吸收 qhchina)
# ================================================================

class TopicDiscovery:
    """
    用 scikit-learn LDA 自动发现参考书库的主题分布。

    应用:
      - 4,475本书 → 自动归为K个主题
      - 发现"标签悬疑"和"真正悬疑"的统计差异
    """

    @classmethod
    def discover(cls, documents: List[str], n_topics: int = 10, n_words: int = 8) -> Dict:
        """
        对文档集做LDA主题建模。

        Args:
            documents: 文本列表
            n_topics: 主题数
            n_words: 每个主题显示的关键词数

        Returns:
            {"topics": {0: {"words": [...], "weight": 0.15}, ...}, "doc_topics": [[...]]}
        """
        try:
            from sklearn.feature_extraction.text import CountVectorizer
            from sklearn.decomposition import LatentDirichletAllocation

            # 中文: 字符2-gram作为特征
            def char_tokenizer(text):
                chars = re.sub(r'[^一-鿿]', '', text)
                return [chars[i:i+2] for i in range(len(chars) - 1)]

            vectorizer = CountVectorizer(
                tokenizer=char_tokenizer, max_features=5000,
                max_df=0.7, min_df=5)
            X = vectorizer.fit_transform(documents)

            lda = LatentDirichletAllocation(
                n_components=n_topics, max_iter=10,
                learning_method='online', random_state=42)
            lda.fit(X)

            # 提取每个主题的关键词
            feature_names = vectorizer.get_feature_names_out()
            topics = {}
            for topic_idx, topic in enumerate(lda.components_):
                top_words = [feature_names[i]
                             for i in topic.argsort()[-n_words:][::-1]]
                topics[topic_idx] = {
                    "words": top_words,
                    "weight": float(topic.sum() / lda.components_.sum()),
                }

            # 每篇文档的主题分布
            doc_topics = lda.transform(X)

            return {"topics": topics, "doc_topics": doc_topics.tolist(),
                    "n_docs": len(documents)}

        except ImportError:
            return {"error": "scikit-learn not available"}
        except Exception as e:
            return {"error": str(e)}


# ================================================================
# 3. 多维语域分析 (吸收 pybiber)
# ================================================================

class RegisterAnalysis:
    """
    Biber 风格的多维语域分析。

    5个核心维度 (简化自 Biber 1988 的 7 维):
      Dim1: 信息密度 vs 交互性
      Dim2: 叙事性 vs 非叙事性
      Dim3: 情境依赖 vs 精细表达
      Dim4: 说服性
      Dim5: 抽象性 vs 非抽象性

    盘古应用: 自动判断一篇文本是"七猫爽文"还是"知乎盐选"
    """

    @classmethod
    def analyze(cls, text: str) -> Dict:
        chars = len(re.sub(r'[^一-鿿]', '', text))
        words = max(chars / 2, 1)  # 中文"词"的近似

        # Dim1: 信息密度 (名词+形容词密度 vs 代词+动词密度)
        nouns_adj = sum(text.count(w) for w in '的地得了着过')
        pronouns_verbs = sum(text.count(w) for w in '你我他她它说去做来走跑看')
        dim1 = (nouns_adj - pronouns_verbs / 2) / words

        # Dim2: 叙事性 (过去时间标记 + 第三人称 vs 现在时)
        narrative_markers = sum(text.count(w) for w in '了过曾经那时当时后来以前')
        non_narrative = sum(text.count(w) for w in '现在目前此刻正在将要去')
        dim2 = (narrative_markers - non_narrative) / words

        # Dim3: 情境依赖 (省略+短句 vs 从句+长句)
        sentences = re.split(r'[。！？]', text)
        short_sents = sum(1 for s in sentences if len(s) < 15)
        dim3 = short_sents / max(len(sentences), 1)

        # Dim4: 说服性 (情态词+副词 vs 无标记)
        persuasive = sum(text.count(w) for w in '应该必须一定肯定绝不能不许')
        dim4 = persuasive / words

        # Dim5: 抽象性 (连词+被动 vs 具体动作)
        abstract = sum(text.count(w) for w in '因为所以如果但是然而虽然')
        concrete = sum(text.count(w) for w in '推拉打抓握跑走吃')
        dim5 = (abstract - concrete / 3) / words

        # 体裁判定
        if dim3 > 0.4 and dim1 < 0.1:
            genre = "七猫爽文 (短句+低信息密度)"
        elif dim1 > 0.2 and dim2 > 0.1:
            genre = "起点玄幻 (高信息+强叙事)"
        elif dim4 > 0.05:
            genre = "知乎盐选 (说服性+观点驱动)"
        else:
            genre = "通用叙事"

        return {
            "dim1_informational": round(dim1, 4),
            "dim2_narrative": round(dim2, 4),
            "dim3_context_dependent": round(dim3, 4),
            "dim4_persuasive": round(dim4, 4),
            "dim5_abstract": round(dim5, 4),
            "predicted_genre": genre,
        }
