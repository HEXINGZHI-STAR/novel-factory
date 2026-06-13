"""
盘古 · Ghost Writer 风格增强器

吸收 OneSpiral/ghost-writer 的 24 维法医风格分析中
盘古当前风格指纹未覆盖的 10 个核心维度:

  动词能量 · 修饰哲学 · 代词策略 · 口癖检测
  信心水平 · 幽默风格 · 情绪温度 · 证据策略
  开头招式 · 结尾模式
"""

from __future__ import annotations

import re, math
from typing import List, Dict, Tuple
from collections import Counter


class AIFlavorAudit:
    """
    7大AI壳层检测 (吸收 B1lli/remove-ai-flavor-writing-skill)

    每一类壳层都有正则模式 + 严重程度(1-3) + 改写建议
    """

    SHELL_RULES = {
        "binary_contrast": {
            "name": "二分对照壳",
            "severity": 3,
            "pattern": r"(?:不是|并非|不在于|不只是|不止是|不仅是).{0,32}(?:而是|而在于|更是)|与其说.{0,32}不如说",
            "fix": "如果A是铺垫，直接说B。如果AB都重要，改成具体关系，不要用'不是A而是B'的说教句式。"
        },
        "staged_sequence": {
            "name": "机械先后顺序",
            "severity": 2,
            "pattern": r"先.{0,24}(?:再|然后|后面|随后)|第一步.{0,60}第二步|从.{1,24}到.{1,24}",
            "fix": "只保留'顺序改变结果'的场景。用实际动作替代'先...再...'的仪式感排序。"
        },
        "essence_claim": {
            "name": "本质拔高壳",
            "severity": 3,
            "pattern": r"真正.{0,24}(?:的是|在于|决定|重要|打动|改变)|本质上|核心在于|底层逻辑",
            "fix": "不用'真正重要的是'拔高，直接说观点。读者不需要你帮他总结重点。"
        },
        "route_marker": {
            "name": "助手路标词",
            "severity": 3,
            "terms": ["下面我们来","接下来我会","我们可以看到","希望这能帮到你","作为AI","截至我的知识","简单来说","换句话说","值得一提的是","不可否认"],
        },
        "fake_intimacy": {
            "name": "假亲近",
            "severity": 2,
            "terms": ["你知道吗","相信我","不骗你","说句实话","讲真的","你猜怎么着","我跟你说"],
        },
        "fake_ending": {
            "name": "假互动结尾",
            "severity": 2,
            "pattern": r"你觉得呢[？?]$|你怎么看[？?]$|欢迎.{0,10}(?:留言|评论|讨论)|你有什么.{0,10}(?:经历|想法|看法)",
        },
        "over_summary": {
            "name": "过度总结",
            "severity": 2,
            "pattern": r"总而言之|综上所述|归纳起来|总的来看|一句话概括|简而言之",
        },
    }

    @classmethod
    def audit(cls, text: str) -> Dict:
        """扫描文本，返回AI壳层报告"""
        findings = []
        total_hits = 0
        for rule_id, rule in cls.SHELL_RULES.items():
            matches = []
            if "pattern" in rule:
                matches = re.findall(rule["pattern"], text)
            if "terms" in rule:
                for term in rule["terms"]:
                    count = text.count(term)
                    if count > 0:
                        matches.extend([term] * count)
            if matches:
                findings.append({
                    "id": rule_id,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "count": len(matches),
                    "samples": matches[:3],
                    "fix": rule["fix"],
                })
                total_hits += len(matches)

        score = max(0.0, 1.0 - total_hits * 0.05)  # 每个壳层扣5%
        return {
            "score": round(score, 2),
            "total_hits": total_hits,
            "findings": findings,
            "verdict": "干净" if score > 0.8 else "轻微AI味" if score > 0.5 else "AI壳层明显",
        }


class GhostWriterBoost:
    """ghost-writer 24维 → 盘古增强"""

    @classmethod
    def analyze(cls, text: str) -> Dict:
        return {
            "verb_energy": cls._verb_energy(text),
            "modifier_philosophy": cls._modifier_philosophy(text),
            "pronoun_strategy": cls._pronoun_strategy(text),
            "verbal_tics": cls._verbal_tics(text),
            "confidence_level": cls._confidence_level(text),
            "humor_style": cls._humor_style(text),
            "emotional_temperature": cls._emotional_temperature(text),
            "evidence_strategy": cls._evidence_strategy(text),
            "opening_move": cls._opening_move(text),
            "closing_pattern": cls._closing_pattern(text),
        }

    # === 动词能量 ===
    @classmethod
    def _verb_energy(cls, text: str) -> Dict:
        active_verbs = '砸摔撞打破抓推拉砍刺跑跳躲闪踢打'
        weak_verbs = '是的有在会被让给到了就也要能'
        active = sum(text.count(v) for v in active_verbs)
        weak = sum(text.count(v) for v in weak_verbs)
        ratio = active / max(weak, 1)
        return {"active": active, "weak": weak, "ratio": round(ratio, 2),
                "style": "高能动词派" if ratio > 0.5 else "中性" if ratio > 0.2 else "低能动词派"}

    # === 修饰哲学 ===
    @classmethod
    def _modifier_philosophy(cls, text: str) -> Dict:
        adverbs = len(re.findall(r'[一-鿿]{1,2}地', text))
        adjectives = len(re.findall(r'[很非常太极其特别十分格外].{1,3}', text))
        sentences = max(len(re.split(r'[。！？]', text)), 1)
        adv_per_sent = adverbs / sentences
        style = "斯巴达(几乎没有修饰)" if adv_per_sent < 0.3 else "选择性(精准修饰)" if adv_per_sent < 0.8 else "华丽(丰富修饰)"
        return {"adverbs": adverbs, "per_sentence": round(adv_per_sent, 2), "style": style}

    # === 代词策略 ===
    @classmethod
    def _pronoun_strategy(cls, text: str) -> Dict:
        i_count = text.count('我')
        you_count = text.count('你')
        we_count = text.count('我们')
        total = max(i_count + you_count + we_count, 1)
        return {"i": round(i_count/total, 2), "you": round(you_count/total, 2),
                "we": round(we_count/total, 2),
                "style": "我主导(个人叙事)" if i_count/total > 0.5 else "你主导(直接对话)" if you_count/total > 0.4 else "平衡"}

    # === 口癖检测 ===
    @classmethod
    def _verbal_tics(cls, text: str) -> List[str]:
        tics = []
        patterns = ['其实', '事实上', '说白了', '换句话说', '真的', '确实', '总之', '所以',
                    '讲真的', '说实话', '有意思的是', '最可怕的是', '你猜']
        for p in patterns:
            count = text.count(p)
            if count >= 3:
                tics.append(f"{p}({count}次)")
        return tics[:3]

    # === 信心水平 ===
    @classmethod
    def _confidence_level(cls, text: str) -> Dict:
        hedging = sum(text.count(w) for w in ['或许','可能','大概','似乎','也许','好像','感觉','觉得'])
        asserting = sum(text.count(w) for w in ['一定','肯定','毫无疑问','显然','明显','就是','绝对是'])
        total = max(hedging + asserting, 1)
        ratio = asserting / total
        level = "自信断言型" if ratio > 0.7 else "平衡" if ratio > 0.4 else "谨慎谦虚型"
        return {"hedging": hedging, "asserting": asserting, "ratio": round(ratio, 2), "style": level}

    # === 幽默风格 ===
    @classmethod
    def _humor_style(cls, text: str) -> Dict:
        self_dep = sum(text.count(w) for w in ['我他妈','我服了','我承认','我错了','我真','我也太'])
        sarcasm = text.count('呵呵') + text.count('笑死') + text.count('绝了')
        dry = text.count('顺便说一句') + text.count('对了') + text.count('说来好笑')
        if self_dep > sarcasm and self_dep > dry:
            return {"type": "自嘲型", "density": self_dep}
        elif sarcasm > dry:
            return {"type": "讽刺型", "density": sarcasm}
        elif dry > 0:
            return {"type": "冷幽默型", "density": dry}
        return {"type": "无"}

    # === 情绪温度 ===
    @classmethod
    def _emotional_temperature(cls, text: str) -> Dict:
        hot = sum(text.count(w) for w in ['愤怒','崩溃','大哭','暴怒','激动','疯狂','可怕'])
        warm = sum(text.count(w) for w in ['温暖','感动','鼻子一酸','笑了','安静','舒服'])
        cool = sum(text.count(w) for w in ['数据','分析','逻辑','事实','研究','统计'])
        total = max(hot + warm + cool, 1)
        dominant = max(hot, warm, cool)
        if dominant == hot: temp = "热(情绪充沛)"
        elif dominant == warm: temp = "暖(治愈温和)"
        else: temp = "冷(理性克制)"
        return {"hot": round(hot/total, 2), "warm": round(warm/total, 2),
                "cool": round(cool/total, 2), "style": temp}

    # === 证据策略 ===
    @classmethod
    def _evidence_strategy(cls, text: str) -> Dict:
        anecdote = sum(text.count(w) for w in ['有一次','那天','我记得','我有一个朋友','我认识'])
        data = sum(text.count(w) for w in ['根据','报告','研究表明','数据显示','统计','调查'])
        cite = sum(text.count(w) for w in ['说过','写道','讲过','提到','引用'])
        dominant = max(anecdote, data, cite)
        if dominant == anecdote: style = "亲身经历型"
        elif dominant == data: style = "数据驱动型"
        elif dominant == cite: style = "名人引用型"
        else: style = "无"
        return {"anecdote": anecdote, "data": data, "cite": cite, "style": style}

    # === 开头招式 ===
    @classmethod
    def _opening_move(cls, text: str) -> str:
        first_50 = text[:50]
        if '?' in first_50 or '?' in first_50: return "问题式开头"
        if any(w in first_50 for w in ['那天','有一次','我认识','上周','今天']): return "场景式开头"
        if any(w in first_50 for w in ['你知道吗','你猜','你是不是','每个人']): return "对话式开头"
        if len(first_50) < 20: return "冷开场(一句话冲击)"
        return "叙述式开头"

    # === 结尾模式 ===
    @classmethod
    def _closing_pattern(cls, text: str) -> str:
        last = text[-200:]
        if '?' in last or '?' in last: return "开放式结尾(留问题)"
        if any(w in last for w in ['后来','那天之后','从此','以后']): return "时间跳跃结尾"
        if any(w in last for w in ['光','影','风','雨','天','路','走','站']): return "画面收尾(落在物件/天气)"
        return "叙事收尾"
