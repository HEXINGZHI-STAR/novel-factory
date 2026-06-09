#!/usr/bin/env python3
"""深度搜索：规则怪谈 × 鬼灭架构 交叉参考书"""
import sys, json
sys.path.insert(0, 'knowledge')
from db_manager import NovelReferenceDB
from chapter_analyzer import ChapterAnalyzer

db = NovelReferenceDB()
analyzer = ChapterAnalyzer()
books = db.list_books(limit=5000)

# 鬼灭架构关键词：组织/等级/柱/队士/呼吸法/鬼月
ORG_KW = ['司','殿','堂','阁','府','院','卫','队','品','柱','官','令','主','首','长']
RULE_KW = ['规则','不准','禁止','不能','必须','否则','违反','违规','触犯']
MONSTER_KW = ['妖','魔','鬼','怪','尸','骸','变','异','畸','化']
LOGIC_KW = ['漏洞','破绽','推理','逻辑','判断','分析','三段','演绎','归纳']

results = []
for b in books:
    chaps = db.get_chapters(b['id'])
    if not chaps or not chaps[0].get('content',''): continue
    content = chaps[0].get('content','')
    title = (b['title'] or '').lower()
    genre = (b.get('genre') or '').strip()

    # 计算四维得分
    org = sum(content[:3000].count(kw) for kw in ORG_KW)
    rule = sum(content[:3000].count(kw) for kw in RULE_KW)
    monster = sum(content[:3000].count(kw) for kw in MONSTER_KW)
    logic = sum(content[:3000].count(kw) for kw in LOGIC_KW)
    total = org + rule + monster + logic

    if total < 8: continue  # 过滤低相关度

    ana = analyzer.full_analysis(content, title)
    rd = ana.get('reading_difficulty',{})
    hooks = ana.get('hooks',[])
    dl = sum(1 for l in content.split('\n') if '"' in l or '“' in l)
    tl = max(1, len(content.split('\n')))
    wc = sum(c.get('word_count') or 0 for c in chaps)

    results.append({
        'id': b['id'], 'title': b['title'][:50], 'genre': genre,
        'words': wc, 'org': org, 'rule': rule, 'monster': monster, 'logic': logic,
        'total': total, 'avg_sl': rd.get('avg_words_per_sentence',0),
        'dr': dl*100//tl, 'hooks': [(h['type'],h['count']) for h in hooks[:3]],
        'opening': content[:400].replace('\n',' ')
    })

# 按规则+逻辑得分排序（最匹配规则怪谈+智力斗争）
results.sort(key=lambda x: -(x['rule'] + x['logic']))

print(f"找到 {len(results)} 本双维匹配参考书\n")

with open('temp_deep_refs.json', 'w', encoding='utf-8') as f:
    json.dump(results[:15], f, ensure_ascii=False, indent=2)

for i, r in enumerate(results[:10], 1):
    print(f"[{i}] [{r['id']}] {r['title'][:45]}")
    print(f"    题材:{r['genre']} 字数:{r['words']}")
    print(f"    组织:{r['org']} 规则:{r['rule']} 妖魔:{r['monster']} 逻辑:{r['logic']}")
    print(f"    句均:{r['avg_sl']}字 对话率:{r['dr']}% 钩子:{r['hooks']}")
    print(f"    开篇:{r['opening'][:120]}...")
    print()

print("详细结果已保存到 temp_deep_refs.json")
