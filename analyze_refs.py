#!/usr/bin/env python3
import sys, json
sys.path.insert(0, 'knowledge')
from db_manager import NovelReferenceDB
from chapter_analyzer import ChapterAnalyzer

db = NovelReferenceDB()
analyzer = ChapterAnalyzer()

top_ids = [1888, 760, 1886]
results = []
for tid in top_ids:
    book = db.get_book(tid)
    chaps = db.get_chapters(tid)
    if book and chaps:
        c = chaps[0].get('content', '')
        ana = analyzer.full_analysis(c, book['title'] or '')
        rd = ana.get('reading_difficulty', {})
        hooks = ana.get('hooks', [])
        dl = sum(1 for l in c.split('\n') if '“' in l or '"' in l)
        tl = max(1, len(c.split('\n')))
        results.append({
            'id': tid,
            'title': book['title'][:60],
            'genre': book.get('genre', ''),
            'author': (book.get('author') or '')[:25],
            'avg_sl': rd.get('avg_words_per_sentence', 0),
            'dr': dl * 100 // tl,
            'hooks': [(h['type'], h['count']) for h in hooks[:3]],
            'opening_preview': c[:500].replace('\n', ' ')
        })

with open('temp_ref.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Written {len(results)} results to temp_ref.json")
for r in results:
    print(f"\n[{r['id']}] {r['title']} | {r['genre']} | {r['author']}")
    print(f"  句均:{r['avg_sl']} 对话率:{r['dr']}% 钩子:{r['hooks']}")
    print(f"  开篇:{r['opening_preview'][:200]}...")
