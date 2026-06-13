"""
盘古数学 · 中文可读性评估

指标:
  - 字频加权分: 高频字比例 → 越常用越易读
  - 句法复杂度: 平均句长 + 从句密度
  - 笔画负担: 平均每字笔画数 → 越多越费力
  - 段落呼吸: 段长变异 → 节奏感
  - 标点熵: 标点多样性 → 语气的丰富度

目标读者分级:
  A: 小学 (可读性>80)
  B: 中学 (60-80)
  C: 大学 (40-60)
  D: 专业 (20-40)
  E: 学术 (<20)

网文平台适配:
  番茄/七猫 → 目标B-C级 (大众可读)
  起点 → B-D级 (允许稍复杂)
  知乎盐选 → C-D级 (知识读者)

用法:
    score = chinese_readability(chapter_text)
    print(f"可读性: {score.score:.1f}, 级别: {score.grade}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple
from collections import Counter


# ================================================================
# 中文笔画数据 (最常用500字的笔画数)
# ================================================================

# 前200高频汉字的笔画数 (康熙字典标准)
_COMMON_CHAR_STROKES: dict = {
    '的':8,'一':1,'是':9,'在':6,'不':4,'了':2,'有':6,'和':8,'人':2,
    '这':7,'中':4,'大':3,'为':4,'上':3,'个':3,'国':8,'我':7,'以':5,
    '要':9,'他':5,'时':7,'来':7,'用':5,'们':5,'生':5,'到':8,'作':7,
    '地':6,'于':3,'出':5,'就':12,'分':4,'对':5,'成':6,'会':6,'可':5,
    '主':5,'发':5,'年':6,'动':6,'同':6,'工':3,'也':3,'能':10,'下':3,
    '过':6,'子':3,'说':9,'产':6,'种':9,'面':9,'而':6,'方':4,'后':6,
    '多':6,'定':8,'行':6,'学':8,'法':8,'所':8,'民':5,'得':11,'经':8,
    '十':2,'三':3,'之':3,'进':7,'着':11,'等':12,'部':10,'度':9,'家':10,
    '电':5,'力':2,'里':7,'如':6,'水':4,'化':4,'高':10,'自':6,'二':2,
    '理':11,'起':10,'小':3,'物':8,'现':8,'实':8,'加':5,'量':12,'都':10,
    '两':7,'体':7,'制':8,'机':6,'当':6,'使':8,'点':9,'从':4,'业':5,
    '本':5,'去':5,'把':7,'性':8,'应':7,'开':4,'它':5,'合':6,'因':6,
    '只':5,'些':8,'想':13,'前':9,'什':4,'么':3,'样':10,'意':13,'没':7,
    '看':9,'道':12,'问':6,'很':9,'最':12,'新':13,'天':4,'老':6,'长':4,
    '知':8,'已':3,'明':8,'正':5,'关':6,'重':9,'并':6,'将':9,'外':5,
    '间':7,'向':6,'与':3,'觉':9,'再':6,'公':4,'无':4,'回':6,'太':4,
    '日':4,'由':5,'被':10,'给':9,'认':4,'头':5,'但':7,'利':7,'文':4,
    '比':4,'内':4,'目':5,'情':11,'百':6,'建':8,'色':6,'手':4,'打':5,
    '光':6,'门':3,'代':5,'问':6,'次':6,'通':10,'品':9,'战':9,'接':11,
    '立':5,'记':5,'己':3,'口':3,'路':13,'少':4,'名':6,'步':7,'西':6,
}


def _estimate_strokes(char: str) -> int:
    """估算汉字笔画数 (查表 + 结构推测)"""
    if char in _COMMON_CHAR_STROKES:
        return _COMMON_CHAR_STROKES[char]
    # 未收录的字按部件推测 (粗略)
    uni = ord(char)
    if 0x4E00 <= uni <= 0x9FFF:
        return 10  # 中位数笔画
    return 0


# ================================================================
# 可读性分数
# ================================================================

@dataclass
class ReadabilityScore:
    """中文可读性评估结果"""
    total_score: float = 0.0          # 0-100综合分
    grade: str = ""                   # A-E分级

    # 子指标
    sentence_ease: float = 0.0        # 句长易读度
    word_freq_ease: float = 0.0       # 字频易读度
    stroke_ease: float = 0.0          # 笔画负担
    paragraph_ease: float = 0.0       # 段落呼吸
    punctuation_diversity: float = 0.0 # 标点熵

    # 原始数据
    avg_sentence_len: float = 0.0
    common_char_ratio: float = 0.0    # 高频字占比
    avg_strokes: float = 0.0          # 平均每字笔画
    para_cv: float = 0.0              # 段长变异系数

    @classmethod
    def from_text(cls, text: str):
        score = cls()

        # 1. 句长易读度
        sentences = re.split(r'[。！？!?\n]', text)
        sent_lens = [len(s.strip()) for s in sentences if s.strip()]
        if sent_lens:
            avg_sl = sum(sent_lens) / len(sent_lens)
            score.avg_sentence_len = avg_sl
            # 句均15-25字最佳，偏离则扣分
            if 15 <= avg_sl <= 25:
                score.sentence_ease = 100
            elif avg_sl < 10:
                score.sentence_ease = max(30, 100 - (15 - avg_sl) * 5)
            else:
                score.sentence_ease = max(30, 100 - (avg_sl - 25) * 2)

        # 2. 字频易读度
        chars = re.findall(r'[一-鿿]', text)
        if chars:
            common = sum(1 for c in chars if c in _COMMON_CHAR_STROKES)
            score.common_char_ratio = common / len(chars)
            score.word_freq_ease = min(100, score.common_char_ratio * 120)

        # 3. 笔画负担
        if chars:
            strokes = [_estimate_strokes(c) for c in chars]
            score.avg_strokes = sum(strokes) / len(strokes)
            # 平均笔画<7最佳，>12费力
            if score.avg_strokes <= 7:
                score.stroke_ease = 100
            else:
                score.stroke_ease = max(20, 100 - (score.avg_strokes - 7) * 15)

        # 4. 段落呼吸
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        if len(paragraphs) > 1:
            para_lens = [len(p) for p in paragraphs]
            mean_p = sum(para_lens) / len(para_lens)
            std_p = math.sqrt(sum((l - mean_p)**2 for l in para_lens) / len(para_lens))
            score.para_cv = std_p / mean_p if mean_p > 0 else 0.0
            # CV在0.3-0.7之间最适合阅读 (有节奏但不乱)
            if 0.3 <= score.para_cv <= 0.7:
                score.paragraph_ease = 100
            elif score.para_cv < 0.1:
                score.paragraph_ease = 50
            else:
                score.paragraph_ease = max(40, 100 - (score.para_cv - 0.7) * 80)

        # 5. 标点多样性
        punct_chars = re.findall(r'[，。！？、；：""''…—]', text)
        if punct_chars:
            punct_counter = Counter(punct_chars)
            punct_types = len(punct_counter)
            # 理想的标点使用: 逗号+句号为主，有适量问号/叹号/引号
            score.punctuation_diversity = punct_types
            if punct_types >= 6:
                score.punctuation_diversity = 100
            elif punct_types >= 4:
                score.punctuation_diversity = 70 + (punct_types - 4) * 15
            else:
                score.punctuation_diversity = max(30, punct_types * 15)

        # 综合分
        score.total_score = (
            score.sentence_ease * 0.25 +
            score.word_freq_ease * 0.20 +
            score.stroke_ease * 0.15 +
            score.paragraph_ease * 0.20 +
            score.punctuation_diversity * 0.20
        )

        # 分级
        score.grade = _classify_grade(score.total_score)

        return score

    def summary(self) -> str:
        return (
            f"可读性={self.total_score:.0f} ({self.grade}级) "
            f"句均={self.avg_sentence_len:.1f}字 "
            f"高频字={self.common_char_ratio:.1%} "
            f"笔画={self.avg_strokes:.1f}"
        )


def _classify_grade(score: float) -> str:
    if score >= 80: return "A-小学"
    if score >= 60: return "B-中学"
    if score >= 40: return "C-大学"
    if score >= 20: return "D-专业"
    return "E-学术"


def chinese_readability(text: str) -> ReadabilityScore:
    """便捷函数: 一次调用获取可读性评估"""
    return ReadabilityScore.from_text(text)
