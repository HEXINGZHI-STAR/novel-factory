#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI - 统一批量导入与全量分析脚本
功能：
  1. 扫描同目录下所有书籍资源（豆瓣/起点/素材库/网文/古诗词）
  2. 统一导入到参考库数据库（去重）
  3. 对已有正文的书籍跑chapter_analyzer全量分析
  4. 填充hooks/emotion_anchors/writing_techniques三表

用法：
  python bulk_import_and_analyze.py --scan          # 仅扫描
  python bulk_import_and_analyze.py --import         # 扫描+导入
  python bulk_import_and_analyze.py --analyze        # 对已有数据跑全量分析
  python bulk_import_and_analyze.py --all            # 全部执行
"""

import os
import sys
import re
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / "knowledge"))

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("bulk_import")

BASE_PATH = Path(r"D:\study\近思录\小说")
PANGU_PATH = BASE_PATH / "盘古AI"

# ========== 题材关键词映射 ==========
GENRE_KEYWORD_MAP = {
    "玄幻": ["斗破", "斗罗", "星辰变", "盘龙", "阳神", "亵渎", "紫川",
            "恶魔法则", "邪神", "无极魔道", "大魔王", "佛本是道",
            "武动", "大主宰", "灵域", "绝世", "完美世界", "遮天", "圣墟"],
    "仙侠": ["仙葫", "仙路", "诛仙", "凡人修仙", "一念永恒", "寸芒",
            "修仙", "仙逆", "求魔", "我欲封天", "蜀山"],
    "都市": ["都市", "重生", "系统", "神豪", "赘婿", "最强", "超级",
            "总裁", "校花", "保镖", "医神", "龙王", "战神", "兵王"],
    "历史": ["回到明朝", "步步生莲", "庆余年", "大明", "大唐", "三国",
            "宋", "历史", "穿越之", "权谋"],
    "科幻": ["三体", "银河", "星际", "末世", "废土", "机甲", "流浪",
            "沙丘", "基地", "科幻", "太空"],
    "悬疑": ["鬼", "诡", "规则", "无限", "密室", "推理", "探案",
            "诡异", "惊悚", "恐怖", "神秘"],
    "游戏": ["网游", "游戏", "电竞", "副本", "全息", "虚拟"],
    "军事": ["弹痕", "狼群", "狙击", "特种兵", "军事", "战争"],
    "言情": ["甜宠", "娇妻", "王妃", "皇后", "公主", "庶女",
            "嫡女", "宫斗", "宅斗", "豪门", "暖婚"],
    "体育": ["冠军", "篮球", "足球", "竞技", "热血"],
    "古风": ["诗", "词", "赋", "曲", "古文", "文言", "唐", "宋词"],
}

GENRE_MODE_MAP = {
    "都市": "urban_power", "仙侠": "general", "悬疑": "rule_mystery",
    "言情": "female_solo", "历史": "history_scholar", "科幻": "general",
    "玄幻": "general", "游戏": "general", "军事": "general",
    "体育": "general", "古风": "general",
    "武侠": "general", "奇幻": "general", "文学": "general",
    "心理": "general", "哲学": "general", "政治": "general",
    "教育": "general", "经济": "general", "艺术": "general",
    "计算机": "general", "传记": "general", "二次元": "general",
    "社会": "general",
}

# ========== 子目录名 → 题材映射（用于genre_hint='auto'） ==========
# 微信读书子目录映射（去掉"榜"后缀）
WEIREAD_DIR_GENRE_MAP = {
    "文学榜": "文学", "历史榜": "历史", "哲学宗教榜": "哲学",
    "心理榜": "心理", "政治军事榜": "政治", "教育学习榜": "教育",
    "科学科技榜": "科幻", "经济理财榜": "经济", "艺术榜": "艺术",
    "计算机榜": "计算机", "个人成长榜": "心理", "传记榜": "传记",
    "社会文化榜": "社会",
}

# 素材库/网络文学子目录关键词 → 题材映射
# 子目录名示例: "网络文学20年十大仙侠作家作品系列〖84部〗"
WANGWEN_DIR_GENRE_PATTERNS = [
    (r"仙侠", "仙侠"),
    (r"玄幻", "玄幻"),
    (r"都市", "都市"),
    (r"历史", "历史"),
    (r"科幻", "科幻"),
    (r"悬疑", "悬疑"),
    (r"游戏", "游戏"),
    (r"军事", "军事"),
    (r"言情", "言情"),
    (r"体育", "体育"),
    (r"武侠", "武侠"),
    (r"奇幻", "奇幻"),
    (r"西方奇幻", "奇幻"),
    (r"二次元", "二次元"),
]


def extract_genre_from_dirname(dir_name: str, source_name: str) -> str:
    """根据子目录名和来源名推断题材。

    Args:
        dir_name: 子目录名（如 '文学榜'、'网络文学20年十大仙侠作家作品系列'）
        source_name: 来源名称（用于选择映射规则）

    Returns:
        推断出的题材字符串，无法推断时返回空字符串
    """
    if "微信读书" in source_name:
        # 先精确匹配
        if dir_name in WEIREAD_DIR_GENRE_MAP:
            return WEIREAD_DIR_GENRE_MAP[dir_name]
        # 再尝试去掉"榜"字后匹配
        clean = dir_name.rstrip("榜")
        if clean in GENRE_MODE_MAP:
            return clean
        return ""

    if "素材库-网络文学" in source_name:
        # 按优先级模式匹配子目录名中的题材关键词
        for pattern, genre in WANGWEN_DIR_GENRE_PATTERNS:
            if re.search(pattern, dir_name):
                return genre
        return ""

    # 通用：尝试直接从目录名匹配题材关键词
    for pattern, genre in WANGWEN_DIR_GENRE_PATTERNS:
        if re.search(pattern, dir_name):
            return genre
    return ""

# ========== 文本提取 ==========
def extract_text_from_txt(file_path: Path, max_chars: int = 500000) -> str:
    """从txt文件提取文本"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                text = f.read(max_chars)
            if len(text) > 100:  # 至少100字才算有效
                return text
        except Exception:
            continue
    return ""


def extract_text_from_epub(file_path: Path, max_chars: int = 500000) -> str:
    """从epub提取文本（需ebooklib）"""
    try:
        import ebooklib
        from ebooklib import epub
        book = epub.read_epub(str(file_path), options={'ignore_ncx': True})
        text_parts = []
        total = 0
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content().decode('utf-8', errors='ignore')
            # 简单去HTML标签
            clean = re.sub(r'<[^>]+>', '', content)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean:
                text_parts.append(clean)
                total += len(clean)
                if total > max_chars:
                    break
        return '\n'.join(text_parts)
    except ImportError:
        return ""
    except Exception as e:
        logger.warning(f"EPUB提取失败 {file_path.name}: {e}")
        return ""


def extract_text(file_path: Path, max_chars: int = 500000) -> str:
    """根据文件类型提取文本"""
    ext = file_path.suffix.lower()
    if ext == '.txt':
        return extract_text_from_txt(file_path, max_chars)
    elif ext == '.epub':
        return extract_text_from_epub(file_path, max_chars)
    # mobi/azw3/pdf 需要额外库，暂不支持直接提取
    return ""


# ========== 书名标准化 ==========
def normalize_title(filename: str) -> str:
    """标准化书名"""
    name = filename
    for ext in [".txt", ".TXT", ".epub", ".mobi", ".azw3", ".pdf", ".jpg", ".JPG", ".png"]:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    for tag in ["（校对版全本）", "（精校版全本）", "（校对全本）", "（全本）",
               "（连载）", "【精校版】", "【校对版】", "（精校全本）",
               "（完整版）", "（精校版）", "【全本】"]:
        if tag in name:
            name = name.replace(tag, "")
    for sep in [" - ", "——"]:
        if sep in name:
            name = name.split(sep, 1)[0]
    return name.strip()


def guess_genre(filename: str, parent_dir: str = "", genre_hint: str = "",
                source_name: str = "", relative_dir: str = "") -> tuple:
    """推断题材和模式。

    优先级:
      1. genre_hint='auto'时，从relative_dir/parent_dir子目录名推断题材
      2. 基于书名+目录的关键词匹配
      3. 默认为'都市'

    Args:
        filename: 文件名
        parent_dir: 父目录路径
        genre_hint: 题材提示，'auto'表示从子目录名推断，其他值作为默认
        source_name: 来源名称（用于选择目录名映射规则）
        relative_dir: 相对于source_path的子目录路径

    Returns:
        (genre, mode) 元组
    """
    # 优先级1: auto模式从子目录名推断
    if genre_hint == "auto":
        # 尝试从relative_dir的各层目录名推断
        if relative_dir:
            parts = Path(relative_dir).parts
            for part in reversed(parts):  # 从最深目录开始匹配
                dir_genre = extract_genre_from_dirname(part, source_name)
                if dir_genre:
                    mode = GENRE_MODE_MAP.get(dir_genre, "general")
                    return dir_genre, mode

        # 尝试从parent_dir推断
        parent_name = Path(parent_dir).name if parent_dir else ""
        dir_genre = extract_genre_from_dirname(parent_name, source_name)
        if dir_genre:
            mode = GENRE_MODE_MAP.get(dir_genre, "general")
            return dir_genre, mode

    # 优先级2: 基于书名+目录的关键词匹配
    name = normalize_title(filename)
    full_text = f"{name} {parent_dir}"
    for genre, keywords in GENRE_KEYWORD_MAP.items():
        for keyword in keywords:
            if keyword in full_text:
                mode = GENRE_MODE_MAP.get(genre, "general")
                return genre, mode

    # 优先级3: 如果有非auto的genre_hint，使用它
    if genre_hint and genre_hint != "auto":
        mode = GENRE_MODE_MAP.get(genre_hint, "general")
        return genre_hint, mode

    return "都市", "urban_power"


def title_hash(title: str) -> str:
    """书名去重哈希"""
    normalized = re.sub(r'[\s\u3000\-_]', '', title.lower())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:12]


def _scan_zhihu_columns(source_name, source_path, platform, priority, genre_hint,
                        seen_hashes, stats):
    """知乎盐选专栏特殊扫描：子目录=专栏名(书名)，txt=章节。

    目录结构: 知乎盐选专栏/A开头盐选专栏/专栏名/1章节名.txt 2章节名.txt ...
    每个专栏名子目录视为一本"书"，内部txt为章节。

    Returns:
        (books_list, count, text_count)
    """
    books = []
    count = 0
    text_count = 0

    for letter_dir in source_path.iterdir():
        if not letter_dir.is_dir():
            continue
        for column_dir in letter_dir.iterdir():
            if not column_dir.is_dir():
                continue

            # 检查是否包含txt章节文件
            txt_files = sorted(column_dir.glob("*.txt"))
            if not txt_files:
                continue

            # 专栏名作为书名
            title = column_dir.name
            # 去掉可能的后缀标记
            for tag in [" 砚水", " 川戈"]:
                if title.endswith(tag):
                    title = title[:-len(tag)]
            thash = title_hash(title)

            # 去重
            if thash in seen_hashes:
                stats['duplicates'] += 1
                continue
            seen_hashes.add(thash)

            # 推断题材（从专栏名+父目录关键词）
            genre, mode = guess_genre(
                title, str(column_dir.parent),
                genre_hint=genre_hint,
                source_name=source_name,
                relative_dir=str(column_dir.relative_to(source_path)),
            )

            # 合计章节文件大小
            total_size = sum(f.stat().st_size for f in txt_files if f.exists())

            books.append({
                "title": title,
                "author": "",
                "file_path": str(column_dir),  # 指向专栏目录而非单个文件
                "file_ext": ".txt_dir",  # 特殊标记：目录级书籍
                "file_size": total_size,
                "genre": genre,
                "mode": mode,
                "platform": platform,
                "source": source_name,
                "priority": priority,
                "can_extract_text": True,  # 内部txt章节可提取
                "title_hash": thash,
                "_zhihu_column_dir": True,  # 标记为知乎专栏目录
            })
            count += 1
            text_count += 1

    return books, count, text_count


# ========== 扫描 ==========
def get_source_configs():
    """返回所有数据源配置列表。

    每个配置为dict，字段说明：
      name: 来源名称
      path: 根目录路径
      platform: 平台标识（qidian/mixed/douban/classic/素材库/微信读书）
      priority: 优先级（1=核心, 2=补充）
      genre_hint: 题材提示，'auto'表示从子目录名自动推断，其他值作为默认genre
      recursive: 是否递归扫描子目录
      format: 文件格式过滤，'txt'/'epub'/'mixed'/'all'
    """
    return [
        # === 原有数据源 ===
        {
            "name": "起点爆款小说120本",
            "path": BASE_PATH / "起点爆款小说120本",
            "platform": "起点",
            "priority": 1,
            "genre_hint": "玄幻",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "网络文学书单704部",
            "path": BASE_PATH / "网络文学书单（网络文学704部经典电子书！130位大神作家作品合集！）",
            "platform": "mixed",
            "priority": 1,
            "genre_hint": "",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "豆瓣读书",
            "path": BASE_PATH / "豆瓣读书（2020-2025）",
            "platform": "douban",
            "priority": 2,
            "genre_hint": "",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "豆瓣科幻书单",
            "path": BASE_PATH / "豆瓣科幻书单300部+",
            "platform": "douban",
            "priority": 2,
            "genre_hint": "科幻",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "古诗词大全集",
            "path": BASE_PATH / "古诗词大全集【281份高清资料整理版】",
            "platform": "classic",
            "priority": 2,
            "genre_hint": "古风",
            "recursive": True,
            "format": "mixed",
        },
        # === Step3新增数据源 ===
        {
            "name": "素材库-网络文学",
            "path": BASE_PATH / "素材库" / "网络文学",
            "platform": "素材库",
            "priority": 1,
            "genre_hint": "auto",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "素材库-科幻奇幻",
            "path": BASE_PATH / "素材库" / "科幻奇幻",
            "platform": "素材库",
            "priority": 1,
            "genre_hint": "科幻",
            "recursive": True,
            "format": "epub",
        },
        {
            "name": "微信读书榜单",
            "path": BASE_PATH / "未分析素材" / "微信读书榜单分类合集(1)",
            "platform": "微信读书",
            "priority": 1,
            "genre_hint": "auto",
            "recursive": True,
            "format": "mixed",
        },
        {
            "name": "知乎盐选专栏",
            "path": BASE_PATH / "未分析素材" / "《知乎严选专栏》(22大类2万多篇)",
            "platform": "zhihu_salt",
            "priority": 2,
            "genre_hint": "",
            "recursive": True,
            "format": "txt",
            # 特殊扫描模式：子目录=专栏名(书名)，txt=章节
            "scan_mode": "zhihu_column",
        },
    ]


def scan_all_sources(source_filter: str = ""):
    """扫描所有资源目录。

    Args:
        source_filter: 仅扫描指定来源（逗号分隔，匹配source name中的关键词）

    Returns:
        (all_books, stats) 元组
    """
    all_configs = get_source_configs()

    # 按 source_filter 过滤
    if source_filter:
        filter_keywords = [kw.strip() for kw in source_filter.split(",") if kw.strip()]
        filtered = []
        for cfg in all_configs:
            if any(kw in cfg["name"] for kw in filter_keywords):
                filtered.append(cfg)
        if not filtered:
            logger.warning(f"未找到匹配 '{source_filter}' 的数据源，可用: {[c['name'] for c in all_configs]}")
            return [], defaultdict(int)
        all_configs = filtered
        logger.info(f"过滤后数据源: {[c['name'] for c in all_configs]}")

    all_books = []
    seen_hashes = set()
    stats = defaultdict(int)

    for cfg in all_configs:
        source_name = cfg["name"]
        source_path = cfg["path"]
        platform = cfg["platform"]
        priority = cfg["priority"]
        genre_hint = cfg.get("genre_hint", "")
        fmt_filter = cfg.get("format", "mixed")

        if not source_path.exists():
            logger.warning(f"目录不存在: {source_path}")
            continue

        logger.info(f"扫描: {source_name} (genre_hint={genre_hint}, format={fmt_filter})")
        count = 0
        text_count = 0

        # 特殊扫描模式：知乎盐选专栏（子目录=书名，txt=章节）
        scan_mode = cfg.get("scan_mode", "")
        if scan_mode == "zhihu_column":
            column_books, count, text_count = _scan_zhihu_columns(
                source_name, source_path, platform, priority, genre_hint,
                seen_hashes, stats,
            )
            all_books.extend(column_books)
            logger.info(f"  找到 {count} 本专栏（可提取文本 {text_count} 本）")
            stats[source_name] = count
            continue

        # 确定允许的文件扩展名
        allowed_exts = ['.txt', '.epub', '.mobi', '.azw3', '.pdf']
        if fmt_filter == 'txt':
            allowed_exts = ['.txt']
        elif fmt_filter == 'epub':
            allowed_exts = ['.epub']

        for root, dirs, files in os.walk(source_path):
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in allowed_exts:
                    # 跳过图片等非书籍文件
                    if ext in ['.txt', '.epub', '.mobi', '.azw3', '.pdf']:
                        stats['skipped_format'] += 1
                    else:
                        stats['skipped_non_book'] += 1
                    continue

                file_path = Path(root) / fname
                title = normalize_title(fname)
                thash = title_hash(title)

                # 去重
                if thash in seen_hashes:
                    stats['duplicates'] += 1
                    continue
                seen_hashes.add(thash)

                # 计算相对目录（用于genre auto推断）
                try:
                    relative_dir = str(Path(root).relative_to(source_path))
                except ValueError:
                    relative_dir = ""

                genre, mode = guess_genre(
                    fname, str(root),
                    genre_hint=genre_hint,
                    source_name=source_name,
                    relative_dir=relative_dir,
                )
                can_extract = ext in ['.txt', '.epub']

                # 从文件名提取作者（微信读书/豆瓣格式: 书名 - 作者.epub）
                author = ""
                for sep in [" - ", "——"]:
                    if sep in title:
                        parts = title.split(sep, 1)
                        if len(parts) == 2 and len(parts[1]) < 20:
                            title = parts[0].strip()
                            author = parts[1].strip()
                        break

                all_books.append({
                    "title": title,
                    "author": author,
                    "file_path": str(file_path),
                    "file_ext": ext,
                    "file_size": file_path.stat().st_size if file_path.exists() else 0,
                    "genre": genre,
                    "mode": mode,
                    "platform": platform,
                    "source": source_name,
                    "priority": priority,
                    "can_extract_text": can_extract,
                    "title_hash": thash,
                })
                count += 1
                if can_extract:
                    text_count += 1

        logger.info(f"  找到 {count} 本（可提取文本 {text_count} 本）")
        stats[source_name] = count

    stats['total_unique'] = len(all_books)
    stats['can_extract'] = sum(1 for b in all_books if b['can_extract_text'])

    return all_books, stats


# ========== 导入数据库 ==========
def import_books_to_db(books, db_manager_class):
    """批量导入书籍到参考库"""
    try:
        db = db_manager_class()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return 0

    imported = 0
    skipped = 0

    # 获取已有书名哈希集合
    existing_titles = set()
    try:
        existing_books = db.list_books(limit=10000)
        for b in existing_books:
            thash = title_hash(b.get('title', ''))
            existing_titles.add(thash)
    except Exception:
        pass

    for i, book in enumerate(books):
        if book['title_hash'] in existing_titles:
            skipped += 1
            continue

        try:
            book_id = db.add_book(
                title=book['title'],
                author=book.get('author', ''),
                platform=book['platform'],
                genre=book['genre'],
                mode=book['mode'],
                notes=f"来源: {book['source']}",
            )
            imported += 1

            # 尝试提取文本并存储前3章（支持txt、epub、知乎专栏目录）
            if book['can_extract_text']:
                # 知乎专栏目录：合并所有章节txt
                if book.get('_zhihu_column_dir') or book['file_ext'] == '.txt_dir':
                    column_dir = Path(book['file_path'])
                    chapter_txts = sorted(column_dir.glob("*.txt"))
                    combined_text = ""
                    for ch_file in chapter_txts[:20]:  # 只取前20章的文本
                        ch_text = extract_text_from_txt(ch_file, max_chars=50000)
                        if ch_text:
                            combined_text += ch_text + "\n\n"
                    if combined_text and len(combined_text) > 500:
                        chapters = split_txt_into_chapters(combined_text, book['title'])
                        for ch_num, ch_text in chapters[:3]:
                            db.add_chapter(
                                book_id=book_id,
                                chapter_num=ch_num,
                                title=f"第{ch_num}章",
                                content=ch_text,
                                is_opening=(ch_num <= 3),
                            )
                else:
                    # 普通单文件书籍
                    text = extract_text(Path(book['file_path']))
                    if text:
                        chapters = split_txt_into_chapters(text, book['title'])
                        for ch_num, ch_text in chapters[:3]:  # 只存前3章
                            db.add_chapter(
                                book_id=book_id,
                                chapter_num=ch_num,
                                title=f"第{ch_num}章",
                                content=ch_text,
                                is_opening=(ch_num <= 3),
                            )

            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i+1}/{len(books)} (导入 {imported}, 跳过 {skipped})")

        except Exception as e:
            logger.warning(f"导入失败 {book['title']}: {e}")
            continue

    logger.info(f"导入完成: 导入 {imported} 本, 跳过已有 {skipped} 本")
    return imported


def split_txt_into_chapters(text: str, title: str, max_chapters: int = 10):
    """将txt文本按章节拆分"""
    # 常见章节分隔模式
    patterns = [
        r'^第[一二三四五六七八九十百千万零\d]+章',  # 第一章
        r'^第\d+章',  # 第1章
        r'^Chapter\s*\d+',  # Chapter 1
        r'^卷[一二三四五六七八九十\d]+',  # 卷一
    ]

    combined = '|'.join(f'({p})' for p in patterns)
    splits = list(re.finditer(combined, text, re.MULTILINE))

    if not splits:
        # 没有章节分隔，按2000字切分
        chunk_size = 2000
        chapters = []
        for i in range(0, min(len(text), max_chapters * chunk_size), chunk_size):
            chunk = text[i:i+chunk_size]
            if len(chunk) > 200:  # 至少200字才算有效章节
                chapters.append((i // chunk_size + 1, chunk))
        return chapters

    chapters = []
    for i, match in enumerate(splits[:max_chapters]):
        start = match.start()
        end = splits[i+1].start() if i+1 < len(splits) else min(start + 5000, len(text))
        ch_text = text[start:end].strip()
        if len(ch_text) > 100:
            chapters.append((i+1, ch_text))

    return chapters


# ========== 全量分析 ==========
def run_full_analysis(db_manager_class, chapter_analyzer_class):
    """对已有章节跑全量分析，填充hooks/emotion_anchors/writing_techniques三表"""
    try:
        db = db_manager_class()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return

    try:
        analyzer = chapter_analyzer_class()
    except Exception as e:
        logger.error(f"分析器初始化失败: {e}")
        return

    # 获取所有有内容的章节
    conn = db._get_connection() if hasattr(db, '_get_connection') else None
    if conn is None:
        logger.error("无法获取数据库连接")
        return

    cursor = conn.cursor()

    # 检查hooks表当前数据量
    cursor.execute("SELECT COUNT(*) FROM hooks")
    hooks_before = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM emotion_anchors")
    anchors_before = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM writing_techniques")
    techs_before = cursor.fetchone()[0]

    logger.info(f"分析前: hooks={hooks_before}, emotion_anchors={anchors_before}, writing_techniques={techs_before}")

    # 获取有内容的章节
    cursor.execute("""
        SELECT c.id, c.book_id, c.chapter_num, c.content, b.title, b.genre
        FROM chapters c
        JOIN books b ON c.book_id = b.id
        WHERE c.content IS NOT NULL AND LENGTH(c.content) > 500
        ORDER BY c.book_id, c.chapter_num
    """)

    rows = cursor.fetchall()
    logger.info(f"找到 {len(rows)} 个可分析章节")

    analyzed = 0
    for row in rows:
        chapter_id = row[0]
        book_id = row[1]
        chapter_num = row[2]
        content = row[3]
        book_title = row[4]
        genre = row[5]

        if not content or len(content) < 200:
            continue

        try:
            # 跑分析
            analysis = analyzer.full_analysis(content, book_title, f"第{chapter_num}章")

            # 写入hooks
            if analysis.get('hooks'):
                for hook in analysis['hooks'][:5]:  # 每章最多5个hook记录
                    hook_type = hook.get('type', 'unknown')
                    strength = min(hook.get('count', 1) * 2, 10)  # 简单换算强度
                    cursor.execute("""
                        INSERT INTO hooks (chapter_id, hook_type, position, strength, description)
                        VALUES (?, ?, ?, ?, ?)
                    """, (chapter_id, hook_type, 'middle', strength,
                          f"检测到{hook_type}类型钩子，关键词出现{hook.get('count',0)}次"))

            # 写入emotion_anchors
            if analysis.get('pacing') and analysis['pacing'].get('segments'):
                for seg in analysis['pacing']['segments'][:3]:
                    # 基于节奏密度推断情绪强度
                    intensity = min(
                        seg.get('exclamation_count', 0) * 2 +
                        seg.get('question_count', 0) * 1 +
                        seg.get('dialogue_count', 0) // 3,
                        10
                    )
                    if intensity > 0:
                        emotion_type = 'tension' if seg.get('exclamation_count', 0) > 2 else 'curiosity'
                        cursor.execute("""
                            INSERT INTO emotion_anchors (chapter_id, position, emotion_type, intensity, description)
                            VALUES (?, ?, ?, ?, ?)
                        """, (chapter_id, seg.get('segment', 1), emotion_type, intensity,
                              f"章节{seg.get('position','')}区域，感叹号{seg.get('exclamation_count',0)}问号{seg.get('question_count',0)}"))

            # 写入writing_techniques
            if analysis.get('opening_hook') and analysis['opening_hook'].get('has_immediate_hook'):
                cursor.execute("""
                    INSERT INTO writing_techniques (chapter_id, book_id, technique_type, name, description, effectiveness_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chapter_id, book_id, 'opening', '开篇钩子',
                      f"《{book_title}》第{chapter_num}章在开篇300字内设置了钩子",
                      analysis['opening_hook'].get('exclamation_count', 0) * 2 +
                      analysis['opening_hook'].get('question_count', 0) * 2))

            analyzed += 1
            if analyzed % 50 == 0:
                conn.commit()
                logger.info(f"分析进度: {analyzed}/{len(rows)}")

        except Exception as e:
            logger.warning(f"分析章节 {chapter_id} 失败: {e}")
            continue

    conn.commit()

    # 统计结果
    cursor.execute("SELECT COUNT(*) FROM hooks")
    hooks_after = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM emotion_anchors")
    anchors_after = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM writing_techniques")
    techs_after = cursor.fetchone()[0]

    logger.info(f"分析完成! 已分析 {analyzed} 章")
    logger.info(f"  hooks: {hooks_before} → {hooks_after} (+{hooks_after - hooks_before})")
    logger.info(f"  emotion_anchors: {anchors_before} → {anchors_after} (+{anchors_after - anchors_before})")
    logger.info(f"  writing_techniques: {techs_before} → {techs_after} (+{techs_after - techs_before})")


# ========== 主流程 ==========
def main():
    parser = argparse.ArgumentParser(description="盘古AI - 统一批量导入与全量分析")
    parser.add_argument('--scan', action='store_true', help='仅扫描，不导入')
    parser.add_argument('--import', dest='do_import', action='store_true', help='扫描+导入')
    parser.add_argument('--analyze', action='store_true', help='对已有数据跑全量分析')
    parser.add_argument('--all', action='store_true', help='全部执行')
    parser.add_argument('--limit', type=int, default=0, help='限制导入数量（0=不限制）')
    parser.add_argument('--source', type=str, default='', help='仅导入指定来源（逗号分隔关键词，如"微信读书,素材库"）')
    args = parser.parse_args()

    if not any([args.scan, args.do_import, args.analyze, args.all]):
        parser.print_help()
        return

    print("=" * 70)
    print("  盘古AI - 统一批量导入与全量分析工具")
    print("=" * 70)

    # ---- Step 1: 扫描 ----
    if args.scan or args.do_import or args.all:
        logger.info("\n===== STEP 1: 扫描资源目录 =====")
        books, stats = scan_all_sources(source_filter=args.source)

        print(f"\n扫描结果:")
        print(f"  去重后总书籍: {stats['total_unique']}")
        print(f"  可提取文本: {stats['can_extract']}")
        print(f"  跳过非书籍文件: {stats.get('skipped_non_book', 0)}")
        print(f"  跳过格式不符: {stats.get('skipped_format', 0)}")
        print(f"  去重跳过: {stats.get('duplicates', 0)}")
        print(f"\n各目录:")
        for key, val in stats.items():
            if key not in ['total_unique', 'can_extract', 'skipped_non_book', 'skipped_format', 'duplicates']:
                print(f"  {key}: {val}")

        # 题材分布
        genre_dist = defaultdict(int)
        for b in books:
            genre_dist[b['genre']] += 1
        print(f"\n题材分布:")
        for genre, cnt in sorted(genre_dist.items(), key=lambda x: -x[1]):
            print(f"  {genre}: {cnt}")

        # 保存扫描结果
        scan_path = PANGU_PATH / "scan_results.json"
        with open(scan_path, 'w', encoding='utf-8') as f:
            json.dump({
                "scan_time": datetime.now().isoformat(),
                "stats": dict(stats),
                "genre_distribution": dict(genre_dist),
                "sample_books": books[:100],  # 只存前100本示例
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"扫描结果已保存: {scan_path}")

    # ---- Step 2: 导入 ----
    if args.do_import or args.all:
        logger.info("\n===== STEP 2: 导入到数据库 =====")
        try:
            from db_manager import NovelReferenceDB
        except ImportError:
            logger.error("无法导入NovelReferenceDB，请确认knowledge目录在路径中")
            return

        if 'books' not in dir():
            books, stats = scan_all_sources(source_filter=args.source)

        # 限制数量（调试用）
        if args.limit > 0:
            books = books[:args.limit]
            logger.info(f"限制导入数量: {args.limit}")

        imported = import_books_to_db(books, NovelReferenceDB)

        # 显示导入后统计
        try:
            db = NovelReferenceDB()
            new_stats = db.get_stats()
            print(f"\n导入后数据库统计:")
            print(f"  总书籍: {new_stats['total_books']}")
            print(f"  参考书籍: {new_stats['reference_books']}")
            print(f"  总章节: {new_stats['total_chapters']}")
            if new_stats.get('by_genre'):
                print(f"  题材分布: {new_stats['by_genre']}")
        except Exception as e:
            logger.warning(f"无法读取导入后统计: {e}")

    # ---- Step 3: 全量分析 ----
    if args.analyze or args.all:
        logger.info("\n===== STEP 3: 全量分析 =====")
        try:
            from db_manager import NovelReferenceDB
            from chapter_analyzer import ChapterAnalyzer
        except ImportError as e:
            logger.error(f"无法导入必要模块: {e}")
            return

        run_full_analysis(NovelReferenceDB, ChapterAnalyzer)

    print("\n" + "=" * 70)
    print("  全部任务完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
