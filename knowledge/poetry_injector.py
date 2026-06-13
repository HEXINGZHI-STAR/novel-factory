#!/usr/bin/env python3
"""古诗词写作注入器 — 用古典诗词提升AI写作的文学性

核心思路：
- AI写作最大的问题是"词语贫乏"——只会用"他感到""突然""缓缓地"
- 古诗词是中文最精炼的文学表达，3000年积累的意象/修辞/情感
- 按场景/情感/意象检索，注入到W2/W4的prompt中
- 不是让AI写古文，而是让AI用古诗词的"思维方式"写现代文
"""

import csv
import os
import random


class PoetryInjector:
    """古诗词写作注入器"""
    
    def __init__(self, csv_path=None):
        if csv_path is None:
            csv_path = os.path.join(os.path.dirname(__file__), 
                                    "references", "csv", "poetry_imagery.csv")
        self.csv_path = csv_path
        self.data = []
        self._load()
    
    def _load(self):
        """加载CSV数据"""
        if not os.path.exists(self.csv_path):
            return
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data.append(row)
    
    def search_by_imagery(self, imagery_keyword):
        """按意象搜索"""
        return [r for r in self.data 
                if imagery_keyword in r.get("imagery", "") 
                or imagery_keyword in r.get("classic_line", "")]
    
    def search_by_emotion(self, emotion_keyword):
        """按情感搜索"""
        return [r for r in self.data 
                if emotion_keyword in r.get("emotion", "")
                or emotion_keyword in r.get("category", "")]
    
    def search_by_scene(self, scene_keyword):
        """按场景搜索"""
        return [r for r in self.data 
                if scene_keyword in r.get("scene_type", "")
                or scene_keyword in r.get("category", "")]
    
    def get_replacement_for_ai_phrase(self, ai_phrase):
        """为AI味表达找到古诗词替代"""
        # AI味表达 → 古诗词意象映射
        AI_TO_POETRY = {
            "他感到悲伤": ("emotion", "悲愤|孤独|思乡"),
            "他看着月亮": ("imagery", "月"),
            "气氛很紧张": ("scene", "战场"),
            "风吹过": ("imagery", "风"),
            "下着雨": ("imagery", "雨"),
            "下着雪": ("imagery", "雪"),
            "花开了": ("imagery", "花"),
            "他拔出剑": ("imagery", "剑"),
            "他喝了一口酒": ("imagery", "酒"),
            "山很高": ("imagery", "山"),
            "水流很急": ("imagery", "水"),
            "他要离开了": ("emotion", "离别"),
            "他想家了": ("emotion", "思乡"),
            "他很有志气": ("emotion", "壮志"),
            "他很孤独": ("emotion", "孤独"),
            "他们相爱了": ("emotion", "爱情"),
            "战场上": ("scene", "战场"),
            "夜晚": ("scene", "月夜"),
            "他看着远方": ("imagery", "山|水"),
        }
        
        if ai_phrase in AI_TO_POETRY:
            category, keyword = AI_TO_POETRY[ai_phrase]
            if category == "imagery":
                results = self.search_by_imagery(keyword)
            elif category == "emotion":
                results = self.search_by_emotion(keyword)
            else:
                results = self.search_by_scene(keyword)
            
            if results:
                r = random.choice(results)
                return {
                    "ai_phrase": ai_phrase,
                    "poetry_line": r.get("classic_line", ""),
                    "author": r.get("author", ""),
                    "novel_usage": r.get("novel_usage", ""),
                }
        return None
    
    def generate_injection_prompt(self, mode="general", scene_type=None, emotion=None):
        """生成古诗词注入prompt（用于W2/W4注入）"""
        if not self.data:
            return ""
        
        # 根据模式选择意象偏好
        MODE_IMAGERY = {
            "crazy_lit": ["剑", "火", "酒", "风"],
            "urban_power": ["火", "光", "风", "水"],
            "female_solo": ["花", "月", "水", "山"],
            "reality_revenge": ["剑", "火", "酒", "雪"],
            "folk_horror": ["月", "风", "雨", "火"],
            "rule_mystery": ["月", "风", "雨", "雪"],
            "healing_life": ["花", "雨", "月", "山"],
            "healing_life_v2": ["花", "雨", "月", "山"],
            "romance": ["花", "月", "雨", "酒"],
            "history_scholar": ["山", "水", "月", "剑"],
            "retro_life": ["花", "酒", "月", "山"],
            "general": ["月", "风", "雨", "雪", "花", "剑"],
        }
        
        preferred = MODE_IMAGERY.get(mode, MODE_IMAGERY["general"])
        
        # 搜索匹配的诗句
        selected = []
        for imagery in preferred:
            matches = self.search_by_imagery(imagery)
            if matches:
                selected.append(random.choice(matches))
            if len(selected) >= 5:
                break
        
        # 如果有场景/情感需求，追加
        if scene_type:
            scene_matches = self.search_by_scene(scene_type)
            if scene_matches:
                selected.append(random.choice(scene_matches))
        
        if emotion:
            emotion_matches = self.search_by_emotion(emotion)
            if emotion_matches:
                selected.append(random.choice(emotion_matches))
        
        if not selected:
            return ""
        
        # 构建prompt
        prompt_parts = ["【古诗词意象库——替代AI味表达的文学化写法】"]
        prompt_parts.append("以下古诗词意象可用于替代AI味模板词，不是让角色念诗，而是用这种思维方式写现代文：\n")
        
        for r in selected[:6]:
            line = r.get("classic_line", "")
            usage = r.get("novel_usage", "")
            author = r.get("author", "")
            if line and usage:
                prompt_parts.append(f'- \u201c{line}\u201d({author}) \u2192 {usage}')
        
        prompt_parts.append("\n【使用规则】")
        prompt_parts.append("1. 不是让角色念诗，而是用古诗词的意象思维写现代文")
        prompt_parts.append("2. '他看着月亮想家了' → '月亮照在舷窗上，他想起北境的冬夜'")
        prompt_parts.append("3. '气氛很紧张' → '空气像凝固了，连呼吸都带着铁锈味'")
        prompt_parts.append("4. 禁止直接引用诗句，只借鉴意象和修辞手法")
        
        return "\n".join(prompt_parts)


# 便捷接口
def get_poetry_prompt(mode="general", scene_type=None, emotion=None):
    """获取古诗词注入prompt"""
    injector = PoetryInjector()
    return injector.generate_injection_prompt(mode, scene_type, emotion)
