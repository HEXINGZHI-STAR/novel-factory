#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI风格指纹系统
从参考小说/章节中提取可量化的风格参数，建立风格数据库
让"素材"变成"可查询的风格模式"，直接指导AI写作
"""

import re
import json
import statistics
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

# 复用动态评分器
try:
    from dynamic_scorer import DynamicScorer
    HAS_SCORER = True
except ImportError:
    HAS_SCORER = False

# 复用数据库
try:
    from db_manager import NovelReferenceDB
    HAS_DB = True
except ImportError:
    HAS_DB = False


class StyleFingerprint:
    """
    风格指纹：从文本中提取的可量化写作参数
    
    包含维度：
    1. 句法指纹 - 平均句长、句长方差、段落长度分布
    2. 对话指纹 - 对话率、对话平均长度、说话人切换频率
    3. 情绪指纹 - 正向/负向情绪比、情绪波动方差、高潮密度
    4. 钩子指纹 - 钩子类型分布、钩子情绪强度
    5. 词汇指纹 - 高频词Top20、动作词密度、形容词密度
    """
    
    def __init__(self, text=None, title="", author="", genre="", platform=""):
        self.title = title
        self.author = author
        self.genre = genre
        self.platform = platform
        self.word_count = 0
        self.extracted_at = None
        
        # 句法指纹
        self.avg_sentence_len = 0.0
        self.median_sentence_len = 0.0
        self.sentence_len_variance = 0.0
        self.avg_paragraph_len = 0.0
        
        # 对话指纹
        self.dialogue_ratio = 0.0        # 对话段落占比
        self.avg_dialogue_len = 0.0      # 平均对话长度
        self.speaker_switch_rate = 0.0   # 说话人切换频率
        
        # 情绪指纹
        self.pos_ratio = 0.0             # 正向情绪句占比
        self.neg_ratio = 0.0             # 负向情绪句占比
        self.emotion_variance = 0.0      # 情绪波动方差
        self.high_intensity_ratio = 0.0  # 高强度句占比
        self.peak_density = 0.0          # 情绪高峰密度（每1000字）
        
        # 钩子指纹（从多章聚合）
        self.hook_types = Counter()       # 钩子类型分布
        self.avg_hook_strength = 0.0     # 平均钩子强度
        
        # 深层数学指纹（style_math.py）
        self.deep_score = 0.0            # 综合深度评分 (0-100)
        self.ngram_unique_ratio = 0.0    # N-gram唯一性
        self.ngram_entropy = 0.0         # N-gram熵
        self.zipf_r2 = 0.0              # Zipf幂律R2
        self.self_transition_rate = 0.0 # 句法自转移率（越低越好）
        self.complexity_score = 0.0     # 信息复杂度
        self.is_ai_templated = False     # 是否有AI模板痕迹
        
        # 词汇指纹
        self.top_words = Counter()        # 高频词
        self.action_density = 0.0         # 动作词密度
        self.adjective_density = 0.0      # 形容词密度
        
        # 综合维度
        self.rhythm_pace = ""             # 节奏类型：fast/medium/slow
        self.emotion_style = ""           # 情绪风格：intense/balanced/subdued
        self.narrative_mode = ""          # 叙事模式：action_driven/dialogue_driven/description_driven
        
        if text:
            self.extract(text)
    
    def extract(self, text):
        """从文本中提取所有指纹维度"""
        self.word_count = len(text.replace('\n', '').replace(' ', ''))
        self.extracted_at = datetime.now().isoformat()
        
        self._extract_syntax(text)
        self._extract_dialogue(text)
        self._extract_emotion(text)
        self._extract_vocabulary(text)
        self._extract_deep_math(text)
        self._classify_overall()
    
    def _extract_syntax(self, text):
        """提取句法指纹"""
        # 按句号/感叹号/问号分句
        sentences = re.split(r'[。！？!?\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 3]
        
        if not sentences:
            return
        
        sent_lens = [len(s) for s in sentences]
        self.avg_sentence_len = statistics.mean(sent_lens)
        self.median_sentence_len = statistics.median(sent_lens)
        self.sentence_len_variance = statistics.variance(sent_lens) if len(sent_lens) > 1 else 0
        
        # 段落长度
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if paragraphs:
            self.avg_paragraph_len = statistics.mean([len(p) for p in paragraphs])
    
    def _extract_dialogue(self, text):
        """提取对话指纹"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        dialogue_paras = []
        quote_count = 0
        
        dialogue_markers = {"说", "道", "问", "答", "喊", "叫", "吼", "骂", "冷声", "低声", "沉声", "淡淡道", "缓缓道"}
        
        for p in paragraphs:
            has_quote = bool(re.search(r'["""]', p))
            has_marker = any(m in p for m in dialogue_markers)
            if has_quote or (has_marker and len(p) < 120):
                dialogue_paras.append(p)
                quote_count += len(re.findall(r'["""]', p))
        
        self.dialogue_ratio = len(dialogue_paras) / max(len(paragraphs), 1)
        self.avg_dialogue_len = statistics.mean([len(p) for p in dialogue_paras]) if dialogue_paras else 0
        self.speaker_switch_rate = len(dialogue_paras) / max(quote_count // 2, 1) if quote_count > 0 else 0
    
    def _extract_emotion(self, text):
        """提取情绪指纹，需DynamicScorer"""
        if not HAS_SCORER:
            self.pos_ratio = 0.5
            self.neg_ratio = 0.3
            self.emotion_variance = 0.3
            self.high_intensity_ratio = 0.4
            return
        
        try:
            scorer = DynamicScorer()
            sentiment = scorer.analyze_sentences(text)
            
            if sentiment:
                scores = [s.score for s in sentiment]
                intensities = [s.intensity for s in sentiment]
                
                self.pos_ratio = sum(1 for s in scores if s > 0.2) / len(scores)
                self.neg_ratio = sum(1 for s in scores if s < -0.2) / len(scores)
                self.emotion_variance = statistics.variance(scores) if len(scores) > 1 else 0
                self.high_intensity_ratio = sum(1 for i in intensities if i > 0.5) / len(intensities)
                self.peak_density = sum(1 for i in intensities if i > 0.7) / (self.word_count / 1000) if self.word_count > 0 else 0
        except Exception:
            pass
    
    def _extract_vocabulary(self, text):
        """提取词汇指纹"""
        # 动作动词检测
        action_verbs = r'(走|跑|冲|抓|拿|拔|砍|杀|打|推|拉|踢|踹|挥|劈|刺|射|按|拍|砸|摔|扔|夺|抢|斩|撕|轰|爆|闪|掠|扑|翻|跃)'
        action_count = len(re.findall(action_verbs, text))
        self.action_density = action_count / max(self.word_count, 1) * 1000  # 每千字
        
        # 形容词检测（的+修饰）
        adj_pattern = r'的([^，。！？\n]{1,5})'
        adj_count = len(re.findall(adj_pattern, text))
        self.adjective_density = adj_count / max(self.word_count, 1) * 1000  # 每千字
        
        # 高频词Top20（用jieba如果可用）
        try:
            import jieba
            words = list(jieba.cut(text))
            # 过滤停用词
            stopwords = {'的', '了', '在', '是', '我', '你', '他', '她', '它', '这', '那', '吗', '吧', '啊', '呢',
                        '着', '就', '也', '都', '要', '会', '能', '不', '没', '有', '很', '和', '到', '说', '道',
                        '个', '一', '人', '来', '去', '上', '下', '里', '中', '大', '小', '多', '少', '把', '被'}
            word_counts = Counter(w for w in words if len(w) > 1 and w not in stopwords)
            self.top_words = word_counts.most_common(20)
        except ImportError:
            pass
    
    def _extract_deep_math(self, text):
        """提取深层数学指纹（N-gram/Zipf/句法模式）"""
        try:
            from style_math import DeepStyleMath
            dsm = DeepStyleMath(text)
            result = dsm.comprehensive_deep_score()
            
            self.deep_score = result["deep_score"]
            self.ngram_unique_ratio = result["details"]["ngram"].get("unique_ratio", 0)
            self.ngram_entropy = result["details"]["ngram"].get("entropy", 0)
            self.zipf_r2 = result["details"]["zipf"].get("zipf_r2", 0)
            self.self_transition_rate = result["details"]["markov"].get("self_transition_rate", 0)
            self.complexity_score = result["breakdown"]["信息复杂度"]
            
            # AI模板痕迹判定
            self.is_ai_templated = (
                self.ngram_unique_ratio < 0.65 or 
                self.self_transition_rate > 0.6
            )
        except Exception:
            pass
    
    def _classify_overall(self):
        """根据提取的参数对整体风格分类"""
        # 节奏分类
        if self.avg_sentence_len < 12 and self.dialogue_ratio > 0.35:
            self.rhythm_pace = "fast"
        elif self.avg_sentence_len > 22:
            self.rhythm_pace = "slow"
        else:
            self.rhythm_pace = "medium"
        
        # 情绪风格
        if self.emotion_variance > 0.4 and self.high_intensity_ratio > 0.3:
            self.emotion_style = "intense"
        elif self.emotion_variance < 0.15:
            self.emotion_style = "subdued"
        else:
            self.emotion_style = "balanced"
        
        # 叙事模式
        if self.dialogue_ratio > 0.4:
            self.narrative_mode = "dialogue_driven"
        elif self.action_density > 15:
            self.narrative_mode = "action_driven"
        else:
            self.narrative_mode = "description_driven"
    
    def to_dict(self):
        """转为可存储的字典"""
        return {
            "title": self.title,
            "author": self.author,
            "genre": self.genre,
            "platform": self.platform,
            "word_count": self.word_count,
            "extracted_at": self.extracted_at,
            "syntax": {
                "avg_sentence_len": round(self.avg_sentence_len, 1),
                "median_sentence_len": round(self.median_sentence_len, 1),
                "sentence_variance": round(self.sentence_len_variance, 2),
                "avg_paragraph_len": round(self.avg_paragraph_len, 1),
            },
            "dialogue": {
                "ratio": round(self.dialogue_ratio, 3),
                "avg_len": round(self.avg_dialogue_len, 1),
                "speaker_switch_rate": round(self.speaker_switch_rate, 3),
            },
            "emotion": {
                "pos_ratio": round(self.pos_ratio, 3),
                "neg_ratio": round(self.neg_ratio, 3),
                "variance": round(self.emotion_variance, 3),
                "high_intensity_ratio": round(self.high_intensity_ratio, 3),
                "peak_density": round(self.peak_density, 1),
            },
            "vocab": {
                "action_density": round(self.action_density, 1),
                "adjective_density": round(self.adjective_density, 1),
                "top_words": self.top_words[:10],
            },
            "classification": {
                "rhythm_pace": self.rhythm_pace,
                "emotion_style": self.emotion_style,
                "narrative_mode": self.narrative_mode,
            },
            "hook": {
                "avg_strength": round(self.avg_hook_strength, 1),
            },
            "deep_math": {
                "deep_score": round(self.deep_score, 1),
                "ngram_unique_ratio": round(self.ngram_unique_ratio, 4),
                "ngram_entropy": round(self.ngram_entropy, 2),
                "zipf_r2": round(self.zipf_r2, 4),
                "self_transition_rate": round(self.self_transition_rate, 3),
                "complexity": round(self.complexity_score, 1),
                "is_ai_templated": self.is_ai_templated,
            },
        }
    
    def describe(self):
        """生成人类可读的风格描述"""
        d = self.to_dict()
        lines = [
            f"=== {self.title} 风格指纹 ===",
            f"作者: {self.author} | 类型: {self.genre} | 平台: {self.platform}",
            f"",
            f"[句法] 均句长{d['syntax']['avg_sentence_len']}字 | 均段长{d['syntax']['avg_paragraph_len']}字",
            f"[对话] 对话率{d['dialogue']['ratio']:.0%} | 均对话长{d['dialogue']['avg_len']}字",
            f"[情绪] 正向{d['emotion']['pos_ratio']:.0%} 负向{d['emotion']['neg_ratio']:.0%} | 波动方差{d['emotion']['variance']:.2f}",
            f"[分类] 节奏:{self.rhythm_pace} 情绪:{self.emotion_style} 叙事:{self.narrative_mode}",
            f"[词汇] 动作密度{d['vocab']['action_density']}/千字 | 形容词密度{d['vocab']['adjective_density']}/千字",
        ]
        if self.top_words:
            words_str = " ".join([f"{w}({c})" for w, c in self.top_words[:8]])
            lines.append(f"[高频词] {words_str}")
        
        if self.deep_score > 0:
            lines.append(f"[深层] 综合评分{self.deep_score:.0f} | "
                         f"N-gram唯一性{self.ngram_unique_ratio:.0%} | "
                         f"Zipf R2 {self.zipf_r2:.2f} | "
                         f"{'AI模板痕迹' if self.is_ai_templated else '自然写作'}")
        
        return "\n".join(lines)


class StyleDatabase:
    """风格指纹数据库：存储/检索/匹配"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent / "style_fingerprints.json"
        self.db_path = Path(db_path)
        self.fingerprints = {}  # title -> StyleFingerprint.to_dict()
        self._load()
    
    def _load(self):
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.fingerprints = data.get("fingerprints", {})
            except Exception:
                self.fingerprints = {}
    
    def save(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "count": len(self.fingerprints),
                "fingerprints": self.fingerprints,
            }, f, ensure_ascii=False, indent=2)
    
    def add(self, fingerprint: StyleFingerprint):
        """添加或更新一个风格指纹"""
        key = f"{fingerprint.title}_{fingerprint.author}" if fingerprint.author else fingerprint.title
        self.fingerprints[key] = fingerprint.to_dict()
        self.save()
        return key
    
    def get(self, title):
        """获取指定书的风格指纹"""
        for key, fp in self.fingerprints.items():
            if fp.get("title") == title:
                return fp
        return None
    
    def query_by_genre(self, genre):
        """查询指定类型的所有风格指纹，返回聚合统计"""
        matches = [fp for fp in self.fingerprints.values() if fp.get("genre") == genre]
        if not matches:
            return None
        
        n = len(matches)
        
        # 聚合统计
        syntax_avg = {
            "avg_sentence_len": statistics.mean([fp["syntax"]["avg_sentence_len"] for fp in matches]),
            "avg_paragraph_len": statistics.mean([fp["syntax"]["avg_paragraph_len"] for fp in matches]),
            "sentence_variance": statistics.mean([fp["syntax"]["sentence_variance"] for fp in matches]),
        }
        
        dialogue_avg = {
            "ratio": statistics.mean([fp["dialogue"]["ratio"] for fp in matches]),
            "avg_len": statistics.mean([fp["dialogue"]["avg_len"] for fp in matches]),
        }
        
        emotion_avg = {
            "pos_ratio": statistics.mean([fp["emotion"]["pos_ratio"] for fp in matches]),
            "variance": statistics.mean([fp["emotion"]["variance"] for fp in matches]),
            "high_intensity_ratio": statistics.mean([fp["emotion"]["high_intensity_ratio"] for fp in matches]),
        }
        
        # 叙事模式分布
        modes = Counter(fp["classification"]["narrative_mode"] for fp in matches)
        rhythms = Counter(fp["classification"]["rhythm_pace"] for fp in matches)
        
        return {
            "genre": genre,
            "sample_count": n,
            "samples": [fp["title"] for fp in matches],
            "syntax_avg": syntax_avg,
            "dialogue_avg": dialogue_avg,
            "emotion_avg": emotion_avg,
            "dominant_narrative": modes.most_common(1)[0][0] if modes else "unknown",
            "dominant_rhythm": rhythms.most_common(1)[0][0] if rhythms else "unknown",
        }
    
    def match_for_writing(self, genre, platform=None):
        """
        给定目标类型/平台，返回最适合参考的风格参数。
        这是核心功能：写作时自动获取"该类型成功作品的平均风格参数"。
        """
        # 先按类型查询
        result = self.query_by_genre(genre)
        
        # 如果有平台过滤
        if platform and result:
            platform_matches = [fp for fp in self.fingerprints.values() 
                              if fp.get("genre") == genre and fp.get("platform") == platform]
            if platform_matches:
                # 平台匹配的样本更精确
                result["platform_matches"] = len(platform_matches)
                result["samples"] = [fp["title"] for fp in platform_matches]
        
        return result
    
    def get_writing_guidance(self, genre, platform=None):
        """
        生成可直接注入到AI prompt中的量化风格指引。
        让AI知道"该类型成功作品是这么写的"。
        """
        matched = self.match_for_writing(genre, platform)
        
        if not matched or matched.get("sample_count", 0) == 0:
            return ""
        
        syn = matched["syntax_avg"]
        dia = matched["dialogue_avg"]
        emo = matched["emotion_avg"]
        
        guidance = f"""
[风格参考] 基于{matched['sample_count']}本{genre}类型成功作品的量化分析：

句法参数：
- 平均句长: {syn['avg_sentence_len']:.0f}字（偏{'短句' if syn['avg_sentence_len'] < 15 else '中长句'}）
- 平均段长: {syn['avg_paragraph_len']:.0f}字
- 句长波动: {'高' if syn['sentence_variance'] > 1.5 else '中' if syn['sentence_variance'] > 0.8 else '低'}

对话参数：
- 对话率: {dia['ratio']:.0%}（该类型标准）
- 平均对话长度: {dia['avg_len']:.0f}字

情绪参数：
- 正向情绪占比: {emo['pos_ratio']:.0%}
- 情绪波动: {'大' if emo['variance'] > 0.35 else '中' if emo['variance'] > 0.2 else '小'}
- 高强度段落密度: {emo['high_intensity_ratio']:.0%}

主导模式: {matched['dominant_narrative']} | 主导节奏: {matched['dominant_rhythm']}
参考作品: {', '.join(matched['samples'][:5])}

[深层数学参考]
- 该类型作品的平均N-gram多样性: {self._get_deep_avg(genre, 'ngram_unique_ratio', 0.7):.0%}
- Zipf自然语言符合度R2: {self._get_deep_avg(genre, 'zipf_r2', 0.85):.2f}
- 句法节奏自转移率: {self._get_deep_avg(genre, 'self_transition_rate', 0.4):.0%}（越低越好）
- AI模板化风险: {'低' if self._get_deep_avg(genre, 'is_ai_templated', 0) < 0.3 else '需注意'}"""
        
        return guidance.strip()
    
    def _get_deep_avg(self, genre, field, default):
        """获取某类型的深层数学指标平均值"""
        matches = [fp for fp in self.fingerprints.values() 
                   if fp.get("genre") == genre]
        if not matches:
            return default
        values = [fp.get("deep_math", {}).get(field, 0) for fp in matches]
        values = [v for v in values if v > 0]
        return statistics.mean(values) if values else default


# ============ 从参考数据库批量提取指纹 ============

def extract_all_fingerprints(db_path=None, force=False):
    """
    从novel_reference.db中读取所有参考书章节，
    为每本书提取风格指纹并存入style_fingerprints.json
    """
    if not HAS_DB:
        print("[ERROR] db_manager.py不可用")
        return
    
    db = NovelReferenceDB(db_path)
    style_db = StyleDatabase()
    
    # 获取所有书籍
    conn = db._get_connection()
    books = conn.execute("SELECT id, title, author, genre, platform FROM books").fetchall()
    
    for book in books:
        book_id = book["id"]
        title = book["title"]
        
        # 检查是否已有指纹
        if not force and style_db.get(title):
            print(f"  [SKIP] {title} - 已存在指纹")
            continue
        
        # 读取所有章节
        chapters = conn.execute(
            "SELECT chapter_num, content FROM chapters WHERE book_id = ? ORDER BY chapter_num",
            (book_id,)
        ).fetchall()
        
        if not chapters:
            print(f"  [SKIP] {title} - 无章节内容")
            continue
        
        # 合并所有章节为全文
        full_text = "\n\n".join([ch["content"] for ch in chapters if ch["content"]])
        
        if len(full_text) < 500:
            print(f"  [SKIP] {title} - 内容不足({len(full_text)}字)")
            continue
        
        # 提取指纹
        fp = StyleFingerprint(
            text=full_text,
            title=title,
            author=book["author"] or "",
            genre=book["genre"] or "",
            platform=book["platform"] or "",
        )
        
        style_db.add(fp)
        print(f"  [OK] {title} - {fp.word_count}字, "
              f"句长{fp.avg_sentence_len:.0f}, 对话率{fp.dialogue_ratio:.0%}, "
              f"节奏:{fp.rhythm_pace}")
    
    conn.close()
    print(f"\n完成！共{len(style_db.fingerprints)}本书的风格指纹已入库")


# ============ 主入口 ============
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "extract":
            # 批量提取所有参考书指纹
            extract_all_fingerprints(force="--force" in sys.argv)
        
        elif cmd == "query":
            # 查询某类型的风格聚合
            genre = sys.argv[2] if len(sys.argv) > 2 else "urban_power"
            style_db = StyleDatabase()
            result = style_db.match_for_writing(genre)
            if result:
                print(f"\n{genre}类型风格聚合 (基于{result['sample_count']}个样本):")
                print(f"  均句长: {result['syntax_avg']['avg_sentence_len']:.1f}字")
                print(f"  对话率: {result['dialogue_avg']['ratio']:.0%}")
                print(f"  正向情绪: {result['emotion_avg']['pos_ratio']:.0%}")
                print(f"  主导叙事: {result['dominant_narrative']}")
                print(f"  参考作品: {', '.join(result['samples'][:5])}")
            else:
                print(f"未找到{genre}类型的风格数据")
        
        elif cmd == "guidance":
            # 生成写作指引
            genre = sys.argv[2] if len(sys.argv) > 2 else "urban_power"
            platform = sys.argv[3] if len(sys.argv) > 3 else None
            style_db = StyleDatabase()
            guidance = style_db.get_writing_guidance(genre, platform)
            print(guidance)
        
        elif cmd == "list":
            # 列出所有指纹
            style_db = StyleDatabase()
            for key, fp in style_db.fingerprints.items():
                print(f"  {fp['title']} ({fp.get('genre', '?')}) - "
                      f"句长{fp['syntax']['avg_sentence_len']}, "
                      f"对话率{fp['dialogue']['ratio']:.0%}")
        
        else:
            print(f"未知命令: {cmd}")
            print("可用: extract / query <genre> / guidance <genre> [platform] / list")
    
    else:
        print("盘古AI风格指纹系统")
        print("=" * 40)
        print("命令:")
        print("  extract              - 从参考数据库中批量提取风格指纹")
        print("  extract --force      - 强制重新提取")
        print("  query <genre>        - 查询某类型的风格聚合")
        print("  guidance <genre>     - 生成写作指引(可注入prompt)")
        print("  list                 - 列出所有指纹")
        print()
        
        # 快速演示
        try:
            style_db = StyleDatabase()
            if style_db.fingerprints:
                print(f"当前数据库: {len(style_db.fingerprints)}本书")
            else:
                print("数据库为空，运行 'python style_fingerprint.py extract' 提取指纹")
        except Exception as e:
            print(f"[WARN] {e}")
