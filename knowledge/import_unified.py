#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI 统一导入脚本
合并所有8个碎片化导入脚本的功能，支持去重、批量导入、进度报告

用法:
  python knowledge/import_unified.py              # 扫描默认路径，导入新书
  python knowledge/import_unified.py --dedup-only # 仅去重
  python knowledge/import_unified.py --stats      # 查看统计
  python knowledge/import_unified.py --dir PATH   # 扫描指定目录
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "knowledge"))
try:
    from db_manager import NovelReferenceDB
except ImportError:
    print("错误: 无法导入 db_manager")
    sys.exit(1)

BASE_PATH = Path(r"d:\study\近思录\小说")
NETWORK_LIT = BASE_PATH / "素材库" / "网络文学"
DOUBAN_LIT = BASE_PATH / "素材库" / "豆瓣读书"

# 题材关键词映射（统一起点+豆瓣）
GENRE_MAP = {
    # 起点分类
    "玄幻": ["斗破", "斗罗", "星辰变", "盘龙", "长生界", "阳神", "亵渎", "紫川",
             "恶魔法则", "邪神传说", "无极魔道", "大魔王", "黑山老妖", "佛本是道"],
    "仙侠": ["仙葫", "仙路烟尘", "惟我独仙", "寸芒", "诛仙", "凡人修仙", "遮天",
             "完美世界", "一念永恒", "剑来"],
    "都市": ["纨绔才子", "邪气凛然", "天王", "我的分身在未来", "龙域",
             "混在三国当军阀", "校花的贴身", "重生之都市", "都市之"],
    "历史": ["回到明朝当王爷", "步步生莲", "江山美色", "大争之世", "庆余年",
             "迷失在康熙末年", "随波逐流之一代军师", "大汉帝国风云录", "唐砖", "赘婿"],
    "军事": ["弹痕", "第五部队", "狼群", "狙击王", "终身制职业", "刺血"],
    "游戏": ["网游之", "网游-", "王牌进化", "法师传奇", "猛龙过江", "全职高手"],
    "科幻": ["星际之", "小兵传奇", "机动风暴", "武装风暴", "天擎", "三体", "流浪地球"],
    "言情": ["何以笙箫默", "微微一笑很倾城", "杉杉来吃", "泡沫之夏", "步步惊心",
             "花千骨", "三生三世", "琅琊榜"],
    "体育": ["冠军教父", "我们是冠军", "校园篮球风云", "篮神", "足球之恋"],
    "西方奇幻": ["佣兵天下", "兽血沸腾", "冰火魔厨", "善良的死神", "空速星痕",
                 "生肖守护神", "琴帝", "变脸武士", "召唤千军"],
    "悬疑": ["无限恐怖", "盗墓笔记", "鬼吹灯", "心理罪", "十宗罪", "法医秦明"],
}


def guess_genre(filename):
    """根据文件名推断题材"""
    name = filename.lower()
    for genre, keywords in GENRE_MAP.items():
        for kw in keywords:
            if kw.lower() in name:
                return genre, "general"
    return "都市", "general"


def normalize_name(filename):
    """标准化文件名"""
    name = filename
    for ext in [".txt", ".epub", ".mobi", ".azw3", ".pdf"]:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    # 去掉常见标记
    tags = ["（校对版全本）", "（精校版全本）", "（校对全本）", "（全本）",
            "（连载）", "[21册][多看版]", "（实体书全+番外补遗）",
            "（校对安全+番外）", "（校对安全）"]
    for tag in tags:
        name = name.replace(tag, "")
    return name.strip()


def extract_author(filename):
    """从文件名提取作者信息"""
    for sep in ["作者：", "作者:", "作者-", "——作者"]:
        if sep in filename:
            parts = filename.split(sep, 1)
            return parts[1].split(".")[0].split("（")[0].strip()[:30]
    return None


def parse_chapters(filepath, num_chapters=3):
    """解析文件前N章"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = filepath.read_text(encoding='gbk')
        except Exception:
            return []

    chapter_pat = re.compile(
        r'第[0-9一二三四五六七八九十百千万]+[章节].*?(?=第[0-9一二三四五六七八九十百千万]+[章节]|$)',
        re.DOTALL
    )
    matches = chapter_pat.findall(content)
    chapters = []
    for i, m in enumerate(matches[:num_chapters]):
        first_line = m.strip().split('\n')[0]
        chapters.append({
            'chapter_num': i + 1,
            'title': first_line if ('章' in first_line or '节' in first_line) else f"第{i+1}章",
            'content': m.strip()
        })
    return chapters


def scan_directory(directory, db):
    """扫描目录下所有TXT文件并导入"""
    if not directory.exists():
        print(f"目录不存在: {directory}")
        return 0, 0

    txt_files = list(directory.rglob("*.txt"))
    print(f"扫描到 {len(txt_files)} 个TXT文件")

    new_books = 0
    new_chapters = 0

    for tf in txt_files:
        name = normalize_name(tf.name)
        genre, mode = guess_genre(name)
        author = extract_author(tf.name)

        # 检查是否已存在
        existing = db.list_books(limit=5000)
        existing_titles = {(b['title'] or '').lower() for b in existing}

        if name.lower() in existing_titles:
            continue  # 跳过重复

        try:
            book_id = db.add_book(
                title=name[:100], author=author, platform="qidian",
                genre=genre, mode=mode, is_reference=True
            )
            chapters = parse_chapters(tf, num_chapters=3)
            for ch in chapters:
                db.add_chapter(book_id, ch['chapter_num'],
                              title=ch['title'], content=ch['content'],
                              is_opening=(ch['chapter_num'] == 1))
                new_chapters += 1
            new_books += 1
            if new_books % 10 == 0:
                print(f"  已导入 {new_books} 本新书...")
        except Exception as e:
            print(f"  ✗ 导入失败 {tf.name}: {e}")
            continue

    return new_books, new_chapters


def dedup_database(db):
    """数据库去重"""
    books = db.list_books(limit=5000)
    seen = {}
    dupes = []

    for b in books:
        key = (b['title'] or '').lower()
        if key in seen:
            dupes.append((b['id'], b['title']))
        else:
            seen[key] = b['id']

    print(f"发现 {len(dupes)} 本重复书籍")
    # 不自动删除，只报告
    for dup_id, dup_title in dupes[:20]:
        print(f"  [重复] ID={dup_id}: {dup_title[:60]}")
    return dupes


def main():
    import sys
    args = sys.argv[1:]

    db = NovelReferenceDB()

    if "--stats" in args:
        stats = db.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    if "--dedup-only" in args:
        print("=== 数据库去重检查 ===")
        dedup_database(db)
        return

    if "--dir" in args:
        idx = args.index("--dir")
        scan_dir = Path(args[idx + 1]) if idx + 1 < len(args) else None
    else:
        scan_dir = NETWORK_LIT

    print("=== 盘古AI 统一导入 ===")
    print(f"扫描目录: {scan_dir}")
    print(f"当前数据库: {db.get_stats()['total_books']} 本书\n")

    new_books, new_chapters = scan_directory(scan_dir, db)
    dedup_database(db)

    stats = db.get_stats()
    print(f"\n=== 导入完成 ===")
    print(f"新增书籍: {new_books} 本")
    print(f"新增章节: {new_chapters} 章")
    print(f"数据库总计: {stats['total_books']} 本书, {stats['total_chapters']} 章")


if __name__ == "__main__":
    main()
