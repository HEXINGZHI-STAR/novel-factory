#!/usr/bin/env python3
"""精准搜索：朝堂官场 + 斩妖除魔 + 查案推理 三元素交叉参考书"""
import sys, json
sys.path.insert(0, 'knowledge')
from db_manager import NovelReferenceDB
from chapter_analyzer import ChapterAnalyzer

db = NovelReferenceDB()
analyzer = ChapterAnalyzer()
books = db.list_books(limit=5000)

# 三大元素关键词
COURT_KW = ['朝', '官', '奏', '旨', '圣', '臣', '殿', '阁', '尚书', '侍郎', '衙门', '吏部', '兵部', '刑部', '翰林', '状元', '进士']
DEMON_KW = ['妖', '魔', '鬼', '怪', '斩', '猎', '灭', '镇', '诛', '除']
CASE_KW = ['案', '查', '线索', '证据', '凶', '尸', '血', '密', '秘', '暗', '计', '谋', '局', '真相']

results = []
for b in books:
    chaps = db.get_chapters(b['id'])
    if not chaps or not chaps[0].get('content', ''):
        continue
    content = chaps[0].get('content', '')
    title = b['title'] or ''
    genre = (b.get('genre') or '').strip()

    # 计算三大元素得分
    court_score = sum(content[:3000].count(kw) for kw in COURT_KW)
    demon_score = sum(content[:3000].count(kw) for kw in DEMON_KW)
    case_score = sum(content[:3000].count(kw) for kw in CASE_KW)
    total = court_score + demon_score + case_score

    if total < 15:  # 过滤低相关度
        continue

    ana = analyzer.full_analysis(content, title)
    rd = ana.get('reading_difficulty', {})
    hooks = ana.get('hooks', [])
    dl = sum(1 for l in content.split('\n') if '“' in l or '"' in l)
    tl = max(1, len(content.split('\n')))
    wc = sum(c.get('word_count') or 0 for c in chaps)

    results.append({
        'id': b['id'], 'title': title[:50], 'genre': genre,
        'author': (b.get('author') or '')[:20], 'words': wc,
        'court': court_score, 'demon': demon_score, 'case': case_score, 'total': total,
        'avg_sl': rd.get('avg_words_per_sentence', 0),
        'dr': dl * 100 // tl,
        'hooks': [(h['type'], h['count']) for h in hooks[:3]],
        'opening': content[:300].replace('\n', ' ')
    })

results.sort(key=lambda x: -x['total'])

with open('temp_ref.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"找到 {len(results)} 本高度相关参考书\n")
for i, r in enumerate(results[:12], 1):
    print(f"[{i}] [{r['id']}] {r['title'][:45]}")
    print(f"    题材:{r['genre']} 作者:{r['author']} 字数:{r['words']}")
    print(f"    朝堂:{r['court']} 妖魔:{r['demon']} 查案:{r['case']} 总分:{r['total']}")
    print(f"    句均:{r['avg_sl']}字 对话率:{r['dr']}% 钩子:{r['hooks']}")
    print(f"    开篇:{r['opening'][:150]}...")
    print()
