#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘古AI统一素材导入器 - 扫描全部书源，导入所有txt"""

import sqlite3, re, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 小说目录
DB_PATH = Path(__file__).parent / "novel_reference.db"

SOURCE_DIRS = [
    ("网络文学书单（网络文学704部经典电子书！130位大神作家作品合集！）", "", True),
    ("起点爆款小说120本", "", True),
    ("豆瓣读书（2020-2025）", "文学", False),
    ("豆瓣科幻书单300部+", "科幻", False),
]

SKIP_KEYWORDS = ['目录', '前言', '后记', '序言', '简介', '书单', '排行榜', '推荐',
                  '古诗', '诗词', '飞花令', '成语', '唐诗', '宋词', 'list', 'index']

GENRE_MAP = {
    '都市': '都市', '现代': '都市', '言情': '都市', '职场': '都市',
    '玄幻': '玄幻', '仙侠': '仙侠', '修真': '仙侠',
    '历史': '历史', '古代': '历史', '穿越': '历史', '三国': '历史',
    '科幻': '科幻', '末世': '科幻', '星际': '科幻', '未来': '科幻',
    '悬疑': '悬疑', '恐怖': '悬疑', '惊悚': '悬疑', '推理': '悬疑',
    '游戏': '游戏', '网游': '游戏', '电竞': '游戏',
    '武侠': '武侠', '军事': '军事', '体育': '体育', '篮球': '体育', '足球': '体育',
    '奇幻': '奇幻', '二次元': '二次元', '轻小说': '二次元',
}

def clean_name(name):
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[\[【][^\]】]*[\]】]', '', name)
    name = re.sub(r'[_\-整理精校著作]+', '', name)
    return name.strip()[:80]

def parse_filename(fname):
    name = Path(fname).stem
    # 《书名》作者：XXX
    m = re.match(r'《(.+?)》(?:作者[：:\s]*)?(.+)', name)
    if m:
        return clean_name(m.group(1)), m.group(2).strip()[:40]
    # (书名)作者：XXX
    m = re.match(r'\((.+?)\)(?:作者[：:\s]*)?(.+)', name)
    if m:
        return clean_name(m.group(1)), m.group(2).strip()[:40]
    # 书名 作者：XXX
    m = re.match(r'(.+?)\s+作者[：:](.+)', name)
    if m:
        return clean_name(m.group(1)), m.group(2).strip()[:40]
    return clean_name(name)[:60], ""

def extract_chapters(text, n=3):
    pat = re.compile(r'\n\s*第[一二三四五六七八九十百千\d]+[章回节卷](?:\s+\S+)?\s*\n')
    splits = [m.start() for m in pat.finditer(text)]
    if len(splits) < 2:
        return [text[:5000]]
    splits = sorted(set(splits))
    chs = []
    for i in range(min(len(splits)-1, n)):
        chs.append(text[splits[i]:splits[i+1]].strip()[:5000])
    return chs

def guess_genre(filename, parent_dir):
    for k, v in GENRE_MAP.items():
        if k in parent_dir or k in filename:
            return v
    return ""

def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    existing_titles = set()
    for row in conn.execute("SELECT title, author FROM books"):
        existing_titles.add((row[0], row[1]))
    
    total_new = 0
    total_ch = 0
    
    for dir_name, default_genre, _ in SOURCE_DIRS:
        src = BASE_DIR / dir_name
        if not src.exists():
            print(f"[SKIP] {dir_name}")
            continue
        
        files = [f for f in src.rglob("*.txt") 
                 if not any(k in f.name for k in SKIP_KEYWORDS)]
        print(f"\n{dir_name}: {len(files)} txts")
        
        for f in files:
            title, author = parse_filename(f.name)
            if not title or (title, author) in existing_titles:
                continue
            
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
                if len(text) < 500:
                    continue
            except:
                continue
            
            genre = default_genre or guess_genre(f.name, f.parent.name) or ""
            chapters = extract_chapters(text)
            
            conn.execute("INSERT INTO books (title,author,genre,is_reference,notes) VALUES (?,?,?,1,?)",
                        (title, author, genre, f"来源: {dir_name}"))
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            
            for i, ch in enumerate(chapters):
                if len(ch) < 100:
                    continue
                conn.execute("INSERT INTO chapters (book_id,chapter_num,content,word_count,is_opening) VALUES (?,?,?,?,1)",
                            (bid, i+1, ch, len(ch.replace('\n',''))))
            
            existing_titles.add((title, author))
            total_new += 1
            
            if total_new % 100 == 0:
                conn.commit()
                print(f"  {total_new}...")
    
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
    print(f"\n完成: +{total_new}本书 | 总计 {n}本书 {c}章")
    conn.close()

if __name__ == "__main__":
    main()
