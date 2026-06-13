#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI参考资源引擎 v2.0
集成 CSV 写作技法库、题材模板、设定模板、写作参考文档

核心能力:
1. CSV参考库: 50+写作技法, 50+桥段套路, 50+爽点节奏, 50+金手指设定
2. 题材模板: 37种主流网文题材的完整写作配置
3. 设定模板: 世界观/主角卡/反派/女主/金手指/力量体系
4. 大纲模板: 总纲/卷节拍表/卷时间线
5. 写作参考: 对话/情绪/场景/战斗/润色/反AI等专项指南
"""

import os
import csv
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).parent
REFERENCES_DIR = BASE_DIR / 'references'
CSV_DIR = REFERENCES_DIR / 'csv'
WRITING_DIR = REFERENCES_DIR / 'writing'
PLAN_DIR = REFERENCES_DIR / 'plan'
REVIEW_DIR = REFERENCES_DIR / 'review'
TEMPLATES_DIR = BASE_DIR / 'templates'
GENRE_DIR = TEMPLATES_DIR / 'genres'


# ============================================================================
# CSV参考库引擎
# ============================================================================

class WritingTechniqueLibrary:
    """写作技法库：从 CSV 文件加载和查询写作技法"""

    _cache = {}

    @classmethod
    def load(cls, filename):
        """加载并缓存单个CSV文件"""
        if filename in cls._cache:
            return cls._cache[filename]

        filepath = CSV_DIR / filename
        if not filepath.exists():
            cls._cache[filename] = []
            return []

        entries = []
        try:
            with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 清理空字段
                    entry = {k.strip(): (v.strip() if isinstance(v, str) else v)
                             for k, v in row.items() if k}
                    if entry and any(entry.values()):
                        entries.append(entry)
        except Exception as e:
            print(f"[WARN] 加载 {filename} 失败: {e}")
            entries = []

        cls._cache[filename] = entries
        return entries

    @classmethod
    def techniques(cls):
        """写作技法库 (50+)：声线差异化、蓄压爆发、伏笔台账等"""
        return cls.load('写作技法.csv')

    @classmethod
    def plot_beats(cls):
        """桥段套路库 (50+)：退婚流、火葬场、打脸权威、战神归来等"""
        return cls.load('桥段套路.csv')

    @classmethod
    def payoffs(cls):
        """爽点与节奏库 (50+)：压抑后爆发、微反转补刀、高潮分布等"""
        return cls.load('爽点与节奏.csv')

    @classmethod
    def golden_fingers(cls):
        """金手指与设定库 (50+)：各类系统、异能、穿越、重生设定"""
        return cls.load('金手指与设定.csv')

    @classmethod
    def characters(cls):
        """人设与关系库：角色设计、关系网络、配角功能分配"""
        return cls.load('人设与关系.csv')

    @classmethod
    def scenes(cls):
        """场景写法库：多感官环境、动态天气、战斗分镜等"""
        return cls.load('场景写法.csv')

    @classmethod
    def naming(cls):
        """命名规则库：角色名、功法名、地名、势力名等"""
        return cls.load('命名规则.csv')

    @classmethod
    def genre_reasoning(cls):
        """题材与调性推理：从设定反推题材、风格定位"""
        return cls.load('题材与调性推理.csv')

    @classmethod
    def review_rules(cls):
        """裁决规则库：审查标准、阻断条件、优先级判定"""
        return cls.load('裁决规则.csv')

    @classmethod
    def search(cls, query, libraries=None, max_results=5):
        """关键词检索多个库

        Args:
            query: 搜索词
            libraries: 指定库名列表，None=所有库
            max_results: 每个库返回的最大结果数
        """
        if libraries is None:
            libraries = ['techniques', 'plot_beats', 'payoffs',
                        'golden_fingers', 'characters', 'scenes']

        results = {}
        lib_map = {
            'techniques': cls.techniques,
            'plot_beats': cls.plot_beats,
            'payoffs': cls.payoffs,
            'golden_fingers': cls.golden_fingers,
            'characters': cls.characters,
            'scenes': cls.scenes,
            'naming': cls.naming,
        }

        for lib_name in libraries:
            if lib_name not in lib_map:
                continue
            data = lib_map[lib_name]()
            if not data:
                continue

            matches = []
            for entry in data:
                text = ' '.join(str(v) for v in entry.values()).lower()
                if query.lower() in text:
                    matches.append(entry)
                if len(matches) >= max_results:
                    break
            if matches:
                results[lib_name] = matches

        return results

    @classmethod
    def summary(cls):
        """所有库的统计摘要"""
        return {
            '写作技法': len(cls.techniques()),
            '桥段套路': len(cls.plot_beats()),
            '爽点与节奏': len(cls.payoffs()),
            '金手指与设定': len(cls.golden_fingers()),
            '人设与关系': len(cls.characters()),
            '场景写法': len(cls.scenes()),
            '命名规则': len(cls.naming()),
            '题材推理': len(cls.genre_reasoning()),
            '裁决规则': len(cls.review_rules()),
        }


# ============================================================================
# 写作参考文档引擎
# ============================================================================

class WritingReference:
    """写作专项参考文档：对话、情绪、场景、战斗、润色、反AI等"""

    DOCS = {
        'dialogue': 'dialogue-writing.md',
        'emotion': 'emotion-psychology.md',
        'scene': 'scene-description.md',
        'combat': 'combat-scenes.md',
        'polish': 'polish-guide.md',
        'anti_ai': 'anti-ai-guide.md',
        'typesetting': 'typesetting.md',
        'desire': 'desire-description.md',
        'hook_payoff': 'genre-hook-payoff-library.md',
        'style_adapter': 'style-adapter.md',
        'style_variants': 'style-variants.md',
        'sentence_structure': 'sentence-structure-reference.md',
        'sentence_structure_v2': 'sentence-structure-reference-v2.md',
        'sentence_structure_v3': 'sentence-structure-reference-v3.md',
    }

    @classmethod
    def get(cls, doc_key):
        """获取指定参考文档的内容"""
        filename = cls.DOCS.get(doc_key)
        if not filename:
            return None
        filepath = WRITING_DIR / filename
        if not filepath.exists():
            return None
        try:
            return filepath.read_text(encoding='utf-8')
        except Exception:
            return None

    @classmethod
    def list(cls):
        """列出可用的写作参考文档"""
        return list(cls.DOCS.keys())


# ============================================================================
# 计划/大纲/设定模板引擎
# ============================================================================

class TemplateEngine:
    """写作模板引擎：大纲、设定、题材配置"""

    TEMPLATES = {
        'outline_main': '大纲-总纲.md',
        'outline_beat': '大纲-卷节拍表.md',
        'outline_timeline': '大纲-卷时间线.md',
        'setting_world': '设定集-世界观.md',
        'setting_protagonist': '设定集-主角卡.md',
        'setting_group': '设定集-主角组.md',
        'setting_antagonist': '设定集-反派设计.md',
        'setting_heroine': '设定集-女主卡.md',
        'setting_power': '设定集-力量体系.md',
        'setting_golden_finger': '设定集-金手指.md',
        'composite_genre': '复合题材-融合逻辑.md',
        'index_schema': 'index-schema.md',
        'state_schema': 'state-schema.md',
        'golden_finger_templates': 'golden-finger-templates.md',
    }

    @classmethod
    def get(cls, template_key):
        """获取模板内容"""
        filename = cls.TEMPLATES.get(template_key)
        if not filename:
            return None
        filepath = TEMPLATES_DIR / filename
        if not filepath.exists():
            return None
        try:
            return filepath.read_text(encoding='utf-8')
        except Exception:
            return None

    @classmethod
    def list(cls):
        """列出可用的模板"""
        return list(cls.TEMPLATES.keys())

    @classmethod
    def list_genres(cls):
        """列出所有可用的题材模板 (37种)"""
        if not GENRE_DIR.exists():
            return []
        genres = []
        for f in sorted(GENRE_DIR.iterdir()):
            if f.suffix == '.md':
                genres.append(f.stem)
        return genres

    @classmethod
    def get_genre(cls, genre_name):
        """获取指定题材的写作指南"""
        filepath = GENRE_DIR / f"{genre_name}.md"
        if not filepath.exists():
            return None
        try:
            return filepath.read_text(encoding='utf-8')
        except Exception:
            return None

    @classmethod
    def genre_profiles(cls):
        """获取题材配置档案 (hook/payoff/pacing配置)"""
        filepath = REFERENCES_DIR / 'genre-profiles.md'
        if not filepath.exists():
            return None
        try:
            return filepath.read_text(encoding='utf-8')
        except Exception:
            return None


# ============================================================================
# 审查/约束参考引擎
# ============================================================================

class ReviewReference:
    """审查与约束参考：核心约束、爽点指南、审查schema等"""

    @classmethod
    def core_constraints(cls):
        """核心约束文档：叙事硬约束"""
        filepath = REFERENCES_DIR / 'core-constraints.md'
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None

    @classmethod
    def cool_points(cls):
        """爽点指南：高效兑现爽点的方法"""
        filepath = REFERENCES_DIR / 'cool-points-guide.md'
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None

    @classmethod
    def review_schema(cls):
        """审查输出 Schema"""
        filepath = REVIEW_DIR / 'review-schema.md'
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None

    @classmethod
    def common_mistakes(cls):
        """常见写作错误清单"""
        filepath = REVIEW_DIR / 'common-mistakes.md'
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None

    @classmethod
    def pacing_control(cls):
        """节奏控制参考"""
        filepath = REVIEW_DIR / 'pacing-control.md'
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None


# ============================================================================
# 大纲/计划参考引擎
# ============================================================================

class OutlineReference:
    """大纲与计划参考：章节规划、冲突设计、世界观设定等"""

    _DOC_MAP = {
        'chapter_planning': 'chapter-planning.md',
        'conflict_design': 'conflict-design.md',
        'outline_structure': 'outline-structure.md',
        'plot_frameworks': 'plot-frameworks.md',
        'genre_volume_pacing': 'genre-volume-pacing.md',
        'character_design': 'character-design.md',
        'world_rules': 'world-rules.md',
        'power_systems': 'power-systems.md',
        'faction_systems': 'faction-systems.md',
        'setting_consistency': 'setting-consistency.md',
        'genre_tropes': 'genre-tropes.md',
        'selling_points': 'selling-points.md',
        'market_positioning': 'market-positioning.md',
        'inspiration_collection': 'inspiration-collection.md',
        'creativity_constraints': 'creativity-constraints.md',
        'creative_combination': 'creative-combination.md',
        'anti_trope_xianxia': 'anti-trope-xianxia.md',
        'anti_trope_urban': 'anti-trope-urban.md',
        'anti_trope_rules_mystery': 'anti-trope-rules-mystery.md',
        'anti_trope_game': 'anti-trope-game.md',
        'init_schema': 'init-collection-schema.md',
        'system_data_flow': 'system-data-flow.md',
    }

    @classmethod
    def get(cls, doc_key):
        filename = cls._DOC_MAP.get(doc_key)
        if not filename:
            return None
        filepath = PLAN_DIR / filename
        return filepath.read_text(encoding='utf-8') if filepath.exists() else None

    @classmethod
    def list(cls):
        return list(cls._DOC_MAP.keys())


# ============================================================================
# 统一访问入口
# ============================================================================

class ReferenceEngine:
    """盘古AI参考资源的统一访问入口"""

    def __init__(self):
        self.techniques = WritingTechniqueLibrary
        self.writing = WritingReference
        self.templates = TemplateEngine
        self.review = ReviewReference
        self.outline = OutlineReference

    def stats(self):
        """系统参考资源总统计"""
        return {
            'csv_libraries': self.techniques.summary(),
            'writing_guides': len(self.writing.list()),
            'core_templates': len(self.templates.list()),
            'genre_templates': len(self.templates.list_genres()),
            'outline_references': len(self.outline.list()),
            'total_reference_files': self._count_files(),
        }

    def _count_files(self):
        count = 0
        for d in [CSV_DIR, WRITING_DIR, PLAN_DIR, REVIEW_DIR, TEMPLATES_DIR]:
            if d.exists():
                count += sum(1 for f in d.rglob('*') if f.is_file())
        return count

    def print_status(self):
        """打印友好的状态信息"""
        s = self.stats()
        print("=" * 60)
        print("  盘古AI参考资源引擎 v2.0")
        print("=" * 60)

        print(f"\n  CSV技法库 ({sum(s['csv_libraries'].values())} 条):")
        for name, count in s['csv_libraries'].items():
            bar = '█' * min(count // 5, 20)
            print(f"    {name:>10}: {count:3d} {bar}")

        print(f"\n  写作专项指南: {s['writing_guides']} 篇")
        for k in self.writing.list():
            print(f"    - {k}")

        print(f"\n  核心写作模板: {s['core_templates']} 个")
        for k in self.templates.list():
            print(f"    - {k}")

        print(f"\n  题材模板: {s['genre_templates']} 种")
        genres = self.templates.list_genres()
        if genres:
            line = "    "
            for g in genres:
                if len(line) + len(g) + 2 > 70:
                    print(line)
                    line = "    "
                line += g + "、"
            print(line.rstrip('、'))

        print(f"\n  大纲/计划参考: {s['outline_references']} 篇")
        print(f"\n  总参考文件数: {s['total_reference_files']}")
        print("=" * 60)


# ============================================================================
# CLI (命令行使用)
# ============================================================================

def _cli():
    engine = ReferenceEngine()

    import sys
    argv = sys.argv[1:]
    if len(argv) < 1:
        engine.print_status()
        print("\n用法: python reference_engine.py <命令> [参数]")
        print("  status                  - 资源状态")
        print("  search <关键词>         - 全文检索写作技法")
        print("  technique <编号>        - 查看某写作技法详情")
        print("  template <名>           - 查看某写作模板")
        print("  genre <题材名>          - 查看某题材指南")
        print("  writing <文档名>        - 查看某写作专项指南")
        print("  list-techniques         - 列出所有写作技法标题")
        print("  list-genres             - 列出所有题材")
        print("  list-templates          - 列出所有核心模板")
        print("  list-writing            - 列出所有写作专项指南")
        return

    cmd = argv[0].lower()

    if cmd == 'status':
        engine.print_status()

    elif cmd == 'search' and len(argv) >= 2:
        query = ' '.join(argv[1:])
        results = engine.techniques.search(query, max_results=3)
        if not results:
            print(f"未找到包含 '{query}' 的条目")
            return
        for lib_name, matches in results.items():
            print(f"\n[{lib_name}] 找到 {len(matches)} 条:")
            for i, entry in enumerate(matches, 1):
                title = (entry.get('技法名称') or entry.get('桥段名称') or
                        entry.get('节奏类型') or entry.get('金手指名称') or
                        entry.get('编号') or '未知')
                summary = entry.get('核心摘要', '')[:60]
                print(f"  {i}. {title} - {summary}...")

    elif cmd == 'technique' and len(argv) >= 2:
        target = argv[1]
        all_techs = (engine.techniques.techniques() +
                     engine.techniques.plot_beats() +
                     engine.techniques.payoffs() +
                     engine.techniques.golden_fingers())
        for t in all_techs:
            tid = t.get('编号', '')
            if tid == target or target in str(t.values()):
                print(f"\n【{t.get('编号', '')}】")
                for k, v in t.items():
                    if v and str(v).strip():
                        print(f"  {k}: {v[:200] if len(str(v)) > 200 else v}")
                break
        else:
            print(f"未找到技法: {target}")

    elif cmd == 'template' and len(argv) >= 2:
        content = engine.templates.get(argv[1])
        if content:
            print(content[:3000])
        else:
            print(f"未找到模板 '{argv[1]}'。可用: {', '.join(engine.templates.list())}")

    elif cmd == 'genre' and len(argv) >= 2:
        content = engine.templates.get_genre(argv[1])
        if content:
            print(content[:3000])
        else:
            print(f"未找到题材 '{argv[1]}'。可用: {', '.join(engine.templates.list_genres())}")

    elif cmd == 'writing' and len(argv) >= 2:
        content = engine.writing.get(argv[1])
        if content:
            print(content[:3000])
        else:
            print(f"未找到写作指南 '{argv[1]}'。可用: {', '.join(engine.writing.list())}")

    elif cmd == 'list-techniques':
        for lib_name in ['techniques', 'plot_beats', 'payoffs', 'golden_fingers']:
            lib_map = {
                'techniques': engine.techniques.techniques,
                'plot_beats': engine.techniques.plot_beats,
                'payoffs': engine.techniques.payoffs,
                'golden_fingers': engine.techniques.golden_fingers,
            }
            data = lib_map[lib_name]()
            print(f"\n[{lib_name}] ({len(data)} 条):")
            for t in data:
                title = (t.get('技法名称') or t.get('桥段名称') or
                        t.get('节奏类型') or t.get('金手指名称') or t.get('编号'))
                print(f"  {t.get('编号',''):>6} {title}")

    elif cmd == 'list-genres':
        genres = engine.templates.list_genres()
        print(f"题材模板 ({len(genres)} 种):")
        for g in genres:
            print(f"  - {g}")

    elif cmd == 'list-templates':
        print(f"核心写作模板 ({len(engine.templates.list())} 个):")
        for t in engine.templates.list():
            print(f"  - {t}")

    elif cmd == 'list-writing':
        print(f"写作专项指南 ({len(engine.writing.list())} 篇):")
        for w in engine.writing.list():
            print(f"  - {w}")

    else:
        print(f"未知命令: {cmd}")


if __name__ == '__main__':
    _cli()
