#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参考小说提示词生成器
结合参考库分析，生成写作提示词
"""

from chapter_analyzer import ChapterAnalyzer


class ReferencePromptGenerator:
    """参考提示词生成器"""
    
    def __init__(self, analyzer=None):
        self.analyzer = analyzer or ChapterAnalyzer()
    
    def generate_style_guide(self, book_title, genre, author, analysis):
        """生成风格指引"""
        if not analysis:
            return ""
        
        guide_parts = []
        guide_parts.append(f"## 参考作品风格")
        guide_parts.append(f"- **作品**: {book_title}")
        if author:
            guide_parts.append(f"- **作者**: {author}")
        if genre:
            guide_parts.append(f"- **题材**: {genre}")
        
        # 钩子类型
        hooks = analysis.get('hooks', [])
        if hooks:
            hook_list = []
            for h in hooks[:3]:
                hook_type = h['type']
                hook_count = h['count']
                hook_list.append(f"{hook_type}({hook_count}次)")
            if hook_list:
                guide_parts.append(f"- **主要钩子**: {', '.join(hook_list)}")
        
        # 阅读难度
        difficulty = analysis.get('reading_difficulty', {})
        if difficulty:
            avg_len = difficulty.get('avg_words_per_sentence', 0)
            level = difficulty.get('difficulty_level', '未知')
            guide_parts.append(f"- **句子长度**: 平均 {avg_len} 字/句 ({level})")
        
        # 段落结构
        paragraphs = analysis.get('paragraphs', [])
        if paragraphs:
            avg_para_len = sum(p['word_count'] for p in paragraphs) / len(paragraphs)
            dialogue_count = sum(1 for p in paragraphs if p['has_dialogue'])
            dialogue_ratio = dialogue_count / len(paragraphs) * 100
            guide_parts.append(f"- **段落长度**: 平均 {round(avg_para_len, 1)} 字")
            guide_parts.append(f"- **对话占比**: {round(dialogue_ratio, 0)}%")
        
        return "\n".join(guide_parts)
    
    def generate_rhythm_guide(self, analysis):
        """生成节奏指引"""
        if not analysis:
            return ""
        
        pacing = analysis.get('pacing', {})
        if not pacing or not pacing.get('segments'):
            return ""
        
        parts = []
        parts.append("## 节奏参考")
        
        segments = pacing['segments']
        for seg in segments:
            pos = seg['position']
            density = seg['exclamation_count'] + seg['question_count'] + seg['dialogue_count'] // 2
            
            pace_desc = ""
            if density <= 1:
                pace_desc = "舒缓铺垫"
            elif density <= 3:
                pace_desc = "正常发展"
            else:
                pace_desc = "紧张高潮"
            
            parts.append(f"- {pos}: {pace_desc} (密度 {density})")
        
        return "\n".join(parts)
    
    def generate_opening_guide(self, analysis):
        """生成开篇指引"""
        if not analysis:
            return ""
        
        opening = analysis.get('opening_hook', {})
        if not opening:
            return ""
        
        parts = []
        parts.append("## 开篇技巧参考")
        
        if opening.get('has_immediate_hook'):
            parts.append("- [OK] 开篇设置了钩子")
        else:
            parts.append("- [WARN] 开篇可增强钩子设置")
        
        exclamation = opening.get('exclamation_count', 0)
        question = opening.get('question_count', 0)
        
        if exclamation + question > 0:
            parts.append(f"- **感叹号**: {exclamation} 个")
            parts.append(f"- **问号**: {question} 个")
        
        detected = opening.get('detected_hooks', [])
        if detected:
            hook_strs = [f"{h['type']}({h['count']})" for h in detected[:3]]
            parts.append(f"- **检测到**: {', '.join(hook_strs)}")
        
        return "\n".join(parts)
    
    def generate_suggestions(self, analysis):
        """生成具体建议"""
        if not analysis:
            return ""
        
        parts = []
        parts.append("## 写作建议")
        
        # 钩子建议
        hooks = analysis.get('hooks', [])
        if hooks:
            main_hook = hooks[0]
            parts.append(f"1. **重点钩子**: 多使用 {main_hook['type']} 类型的钩子")
        
        # 节奏建议
        pacing = analysis.get('pacing', {})
        if pacing:
            parts.append("2. **节奏把控**: 按照参考作品的密度变化安排内容")
        
        # 难度建议
        difficulty = analysis.get('reading_difficulty', {})
        if difficulty:
            avg_len = difficulty.get('avg_words_per_sentence', 0)
            if avg_len > 25:
                parts.append("3. **句子控制**: 适当断句，让阅读更轻松")
            elif avg_len < 15:
                parts.append("3. **句子变化**: 可适当加入一些长句增加层次感")
        
        # 对话建议
        paragraphs = analysis.get('paragraphs', [])
        if paragraphs:
            dialogue_ratio = sum(1 for p in paragraphs if p['has_dialogue']) / len(paragraphs) * 100
            if dialogue_ratio < 10:
                parts.append("4. **对话比例**: 可适当增加对话，让场景更生动")
            elif dialogue_ratio > 40:
                parts.append("4. **对话比例**: 可适当增加叙述描写")
        
        return "\n".join(parts)
    
    def generate_full_prompt(self, book_title, genre, author, chapter_content, mode_name="通用", platform="番茄"):
        """生成完整提示词"""
        if not chapter_content:
            return ""
        
        analysis = self.analyzer.full_analysis(chapter_content, book_title)
        
        prompt_parts = []
        prompt_parts.append("# 小说写作提示词")
        prompt_parts.append("")
        prompt_parts.append(f"## 任务信息")
        prompt_parts.append(f"- **创作模式**: {mode_name}")
        prompt_parts.append(f"- **发布平台**: {platform}")
        prompt_parts.append("")
        
        # 风格指引
        style_guide = self.generate_style_guide(book_title, genre, author, analysis)
        if style_guide:
            prompt_parts.append(style_guide)
            prompt_parts.append("")
        
        # 节奏指引
        rhythm_guide = self.generate_rhythm_guide(analysis)
        if rhythm_guide:
            prompt_parts.append(rhythm_guide)
            prompt_parts.append("")
        
        # 开篇指引
        opening_guide = self.generate_opening_guide(analysis)
        if opening_guide:
            prompt_parts.append(opening_guide)
            prompt_parts.append("")
        
        # 具体建议
        suggestions = self.generate_suggestions(analysis)
        if suggestions:
            prompt_parts.append(suggestions)
            prompt_parts.append("")
        
        # 参考原文
        prompt_parts.append("## 参考原文开篇")
        preview = chapter_content[:500] if len(chapter_content) > 500 else chapter_content
        prompt_parts.append("> " + preview.replace("\n", "\n> "))
        prompt_parts.append("")
        
        # 写作要求
        prompt_parts.append("## 写作要求")
        prompt_parts.append("1. 模仿参考作品的风格和节奏进行创作")
        prompt_parts.append("2. 保持在开篇设置钩子的写作习惯")
        prompt_parts.append("3. 章节字数控制在2000字左右（网文标准）")
        prompt_parts.append("4. 遵循对应创作模式和平台的写作要求")
        
        return "\n".join(prompt_parts)


def main():
    """测试生成器"""
    print("测试参考提示词生成器")
    print("="*70)
    
    test_content = """
"这是什么？"
主角看着眼前的景象，心中充满了震惊。
他从未见过这样的场景。
难道这就是传说中的...？
危险！
他猛地后退，但已经来不及了...
"""
    
    generator = ReferencePromptGenerator()
    prompt = generator.generate_full_prompt(
        book_title="测试小说",
        genre="玄幻",
        author="测试作者",
        chapter_content=test_content,
        mode_name="玄幻",
        platform="番茄"
    )
    
    print(prompt)


if __name__ == '__main__':
    main()
