#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
章节内容分析器
自动分析参考小说章节的写作要素
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class ChapterAnalyzer:
    """章节内容分析器"""
    
    def __init__(self):
        # 钩子类型关键词
        self.hook_keywords = {
            'suspense': ['悬念', '神秘', '未知', '奇怪', '诡异', '秘密', '疑惑', '不解', '为什么', '怎么回事', '竟然', '居然', '意外'],
            'danger': ['危险', '危机', '恐怖', '可怕', '死亡', '尸体', '害怕', '恐惧', '紧张', '惊慌', '追杀', '致命'],
            'question': ['是谁', '什么', '哪里', '怎么', '为什么', '难道', '莫非', '究竟', '到底', '疑问', '困惑'],
            'shock': ['震惊', '震撼', '吃惊', '难以置信', '不敢相信', '震撼', '惊呆', '傻了'],
            'conflict': ['冲突', '争吵', '打架', '矛盾', '对立', '敌人', '对手', '仇人', '憎恨', '愤怒'],
            'attraction': ['美女', '帅哥', '诱惑', '吸引', '魅力', '惊艳', '漂亮', '帅气', '一见钟情']
        }
        
        # 标点符号统计
        self.punctuation = {
            'exclamation': '!',
            'question': '?',
            'ellipsis': '…',
            'suspension': '......'
        }
    
    def count_chinese_words(self, text: str) -> int:
        """统计中文字数"""
        if not text:
            return 0
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return len(chinese_chars)
    
    def count_sentences(self, text: str) -> int:
        """统计句子数量（以。！？为分隔）"""
        if not text:
            return 0
        sentences = re.split(r'[。！？!?]', text)
        return len([s for s in sentences if s.strip()])
    
    def analyze_paragraphs(self, text: str) -> List[Dict]:
        """分析段落结构"""
        if not text:
            return []
        
        paragraphs = text.split('\n')
        result = []
        
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue
            
            word_count = self.count_chinese_words(para)
            result.append({
                'index': i + 1,
                'word_count': word_count,
                'has_dialogue': '"' in para or '“' in para,
                'content': para[:50] if len(para) > 50 else para
            })
        
        return result
    
    def detect_hook_types(self, text: str) -> List[Dict]:
        """检测钩子类型"""
        if not text:
            return []
        
        results = []
        
        for hook_type, keywords in self.hook_keywords.items():
            count = 0
            for keyword in keywords:
                count += text.count(keyword)
            
            if count > 0:
                results.append({
                    'type': hook_type,
                    'count': count,
                    'keywords': keywords[:5]
                })
        
        # 按数量排序
        results.sort(key=lambda x: x['count'], reverse=True)
        return results
    
    def analyze_pacing(self, text: str, num_segments: int = 5) -> Dict:
        """分析节奏（分段统计不同位置的密度）"""
        if not text:
            return {}
        
        words = list(text)
        if len(words) < num_segments:
            return {}
        
        segment_size = len(words) // num_segments
        segments = []
        
        for i in range(num_segments):
            start = i * segment_size
            end = (i + 1) * segment_size if i < num_segments - 1 else len(words)
            segment_text = ''.join(words[start:end])
            
            seg_stats = {
                'segment': i + 1,
                'position': f"{i * 100 // num_segments}%-{(i + 1) * 100 // num_segments}%",
                'word_count': self.count_chinese_words(segment_text),
                'exclamation_count': segment_text.count('!') + segment_text.count('！'),
                'question_count': segment_text.count('?') + segment_text.count('？'),
                'dialogue_count': segment_text.count('"') + segment_text.count('“')
            }
            segments.append(seg_stats)
        
        return {
            'total_segments': num_segments,
            'segments': segments
        }
    
    def detect_character_introduction(self, text: str) -> List[Dict]:
        """检测人物出场方式"""
        # 简单的人物出场检测模式
        patterns = [
            r'[叫名是]做?["“]?([\u4e00-\u9fff]{2,4})["”]?',
            r'([\u4e00-\u9fff]{2,4})说',
            r'([\u4e00-\u9fff]{2,4})想',
            r'([\u4e00-\u9fff]{2,4})看'
        ]
        
        characters = {}
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for name in matches:
                if len(name) >= 2 and len(name) <= 4:
                    pos = text.find(name)
                    if pos != -1:
                        if name not in characters or pos < characters[name]:
                            characters[name] = pos
        
        result = []
        for name, pos in sorted(characters.items(), key=lambda x: x[1]):
            result.append({
                'name': name,
                'position': pos,
                'position_percent': round(pos / len(text) * 100, 1) if len(text) > 0 else 0
            })
        
        return result[:10]  # 返回前10个人物
    
    def calculate_reading_difficulty(self, text: str) -> Dict:
        """计算阅读难度（简单估算）"""
        if not text:
            return {}
        
        word_count = self.count_chinese_words(text)
        sentence_count = self.count_sentences(text)
        
        avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
        
        return {
            'total_words': word_count,
            'total_sentences': sentence_count,
            'avg_words_per_sentence': round(avg_words_per_sentence, 1),
            'difficulty_level': '简单' if avg_words_per_sentence < 15 else '中等' if avg_words_per_sentence < 25 else '复杂'
        }
    
    def find_opening_hook(self, text: str) -> Optional[Dict]:
        """查找开篇钩子（前300字）"""
        if not text:
            return None
        
        opening_text = text[:300]
        
        # 统计标点符号
        exclamation = opening_text.count('!') + opening_text.count('！')
        question = opening_text.count('?') + opening_text.count('？')
        
        # 检测钩子关键词
        hooks = self.detect_hook_types(opening_text)
        
        return {
            'opening_text': opening_text,
            'exclamation_count': exclamation,
            'question_count': question,
            'detected_hooks': hooks,
            'has_immediate_hook': len(hooks) > 0 or (exclamation + question) > 2
        }
    
    def full_analysis(self, text: str, book_title: str = '', chapter_title: str = '') -> Dict:
        """完整的章节分析"""
        if not text:
            return {}
        
        result = {
            'book_title': book_title,
            'chapter_title': chapter_title,
            'word_count': self.count_chinese_words(text),
            'reading_difficulty': self.calculate_reading_difficulty(text),
            'paragraphs': self.analyze_paragraphs(text),
            'hooks': self.detect_hook_types(text),
            'opening_hook': self.find_opening_hook(text),
            'pacing': self.analyze_pacing(text),
            'characters': self.detect_character_introduction(text)
        }
        
        return result
    
    def generate_analysis_report(self, analysis: Dict) -> str:
        """生成分析报告（可读文本格式）"""
        if not analysis:
            return "无内容可分析"
        
        lines = []
        lines.append("="*70)
        if analysis.get('book_title'):
            lines.append(f"书籍: {analysis['book_title']}")
        if analysis.get('chapter_title'):
            lines.append(f"章节: {analysis['chapter_title']}")
        lines.append(f"字数: {analysis.get('word_count', 0)}")
        lines.append("="*70)
        
        # 阅读难度
        if analysis.get('reading_difficulty'):
            rd = analysis['reading_difficulty']
            lines.append("\n【阅读难度】")
            lines.append(f"  总句数: {rd.get('total_sentences', 0)}")
            lines.append(f"  平均句长: {rd.get('avg_words_per_sentence', 0)} 字/句")
            lines.append(f"  难度等级: {rd.get('difficulty_level', '未知')}")
        
        # 开篇钩子
        if analysis.get('opening_hook'):
            oh = analysis['opening_hook']
            lines.append("\n【开篇分析】（前300字）")
            lines.append(f"  是否有立即钩子: {'是' if oh.get('has_immediate_hook') else '否'}")
            lines.append(f"  感叹号数量: {oh.get('exclamation_count', 0)}")
            lines.append(f"  问号数量: {oh.get('question_count', 0)}")
            
            if oh.get('detected_hooks'):
                lines.append(f"  检测到的钩子类型:")
                for hook in oh['detected_hooks'][:3]:
                    lines.append(f"    - {hook['type']}: {hook['count']}次")
        
        # 钩子类型
        if analysis.get('hooks'):
            lines.append("\n【钩子类型】")
            for i, hook in enumerate(analysis['hooks'], 1):
                lines.append(f"  {i}. {hook['type']}: {hook['count']}次")
        
        # 节奏分析
        if analysis.get('pacing') and analysis['pacing'].get('segments'):
            lines.append("\n【节奏分布】")
            for seg in analysis['pacing']['segments']:
                density = seg['exclamation_count'] + seg['question_count'] + seg['dialogue_count'] // 2
                lines.append(f"  {seg['position']}: 密度指数 {density}")
        
        # 人物出场
        if analysis.get('characters'):
            lines.append("\n【人物出场顺序】")
            for char in analysis['characters'][:5]:
                lines.append(f"  - {char['name']}: 约在全文{char['position_percent']}%处出场")
        
        # 段落分析
        if analysis.get('paragraphs'):
            paras = analysis['paragraphs']
            avg_para_len = sum(p['word_count'] for p in paras) / len(paras) if paras else 0
            lines.append("\n【段落结构】")
            lines.append(f"  总段落数: {len(paras)}")
            lines.append(f"  平均段落长度: {round(avg_para_len, 1)} 字")
            dialogue_paras = sum(1 for p in paras if p['has_dialogue'])
            lines.append(f"  含对话段落: {dialogue_paras} 段 ({dialogue_paras / len(paras) * 100:.0f}%)")
        
        lines.append("\n" + "="*70)
        lines.append("【写作参考建议】")
        
        suggestions = []
        
        if analysis.get('opening_hook') and not analysis['opening_hook'].get('has_immediate_hook'):
            suggestions.append("  - 开篇可以设置更强的钩子，在第一章尽早吸引读者")
        
        if analysis.get('reading_difficulty', {}).get('avg_words_per_sentence', 0) > 25:
            suggestions.append("  - 句子偏长，可以适当断句，让阅读更轻松")
        
        hooks = analysis.get('hooks', [])
        if len(hooks) < 2:
            suggestions.append("  - 可以尝试加入更多元化的钩子类型（悬念、冲突、疑问等）")
        
        if not suggestions:
            suggestions.append("  - 当前写作节奏良好！")
        
        lines.extend(suggestions)
        lines.append("="*70)
        
        return '\n'.join(lines)


def main():
    """测试分析器"""
    print("章节内容分析器")
    
    analyzer = ChapterAnalyzer()
    
    # 测试文本
    test_text = """
    "这是什么？"
    林天看着地上那个发光的东西，心中充满了疑惑。
    竟然是一只会发光的虫子！
    这太奇怪了！
    他小心翼翼地走过去，却发现那虫子突然动了一下。
    "难道是……"
    林天的心跳瞬间加速，一种不祥的预感涌上心头。
    危险！
    他猛地退后一步，但已经来不及了……
    """
    
    analysis = analyzer.full_analysis(test_text, "测试小说", "第一章")
    report = analyzer.generate_analysis_report(analysis)
    print(report)


if __name__ == '__main__':
    main()
