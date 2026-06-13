#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎盐选专栏批量入库脚本
将知乎盐选专栏的20,773篇文章批量导入到 novel_reference.db 数据库中。

运行方式：
    D:\ProgramData\Anaconda3\python.exe import_zhihu_salt.py
"""

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# ============================================================
# 配置
# ============================================================
SOURCE_DIR = Path(r"D:/study/近思录/小说/未分析素材/《知乎严选专栏》(22大类2万多篇)")
DB_PATH = Path(r"D:/study/近思录/小说/盘古AI/knowledge/novel_reference.db")
BATCH_SIZE = 500  # 每BATCH_SIZE条commit一次

# ============================================================
# 情绪词典
# ============================================================
POSITIVE_WORDS = [
    '惊喜', '快乐', '感动', '温暖', '希望', '幸福', '甜蜜', '欢乐',
    '欣慰', '释然', '骄傲', '满足', '期待', '安心', '感恩', '喜悦',
    '兴奋', '自信', '勇敢', '豁然开朗', '开心', '愉快', '幸福', '美好',
    '笑容', '微笑', '拥抱', '温柔', '宠爱', '珍惜', '守护', '陪伴',
]
NEGATIVE_WORDS = [
    '悲伤', '愤怒', '恐惧', '绝望', '痛苦', '焦虑', '孤独', '失落',
    '悔恨', '嫉妒', '羞耻', '厌恶', '紧张', '迷茫', '委屈', '心碎',
    '崩溃', '窒息', '冰冷', '黑暗', '哭泣', '泪水', '颤抖', '绝望',
    '恐惧', '噩梦', '伤害', '背叛', '抛弃', '欺骗', '绝望', '死亡',
]

# 转折词（用于识别悬念钩子）
SUSPENSE_WORDS = ['但', '但是', '然而', '可是', '却', '突然', '忽然', '没想到', '谁知', '不料', '竟然', '居然', '偏偏']

# 感官词
COLOR_WORDS = ['红', '橙', '黄', '绿', '蓝', '紫', '黑', '白', '灰', '金', '银', '粉', '暗红', '血红', '雪白', '漆黑', '苍白']
SOUND_WORDS = ['响', '声', '鸣', '叫', '喊', '嚷', '吼', '哭', '笑', '嗡', '咔嚓', '砰', '叮', '咚', '哗', '嘶', '呼']
TOUCH_WORDS = ['冷', '热', '冰', '暖', '凉', '烫', '痛', '痒', '麻', '涩', '滑', '粗糙', '柔软', '坚硬', '湿润']

# ============================================================
# 类型映射表（根据书名关键词推断genre）
# ============================================================
GENRE_KEYWORDS = [
    (['悬疑', '推理', '侦探', '谜案', '凶手', '案', '刑侦', '犯罪', '破案'], '悬疑推理'),
    (['恐怖', '惊悚', '鬼', '灵异', '诡异', '怪谈', '灵'], '恐怖惊悚'),
    (['恋爱', '爱情', '甜', '宠', '暗恋', '暗恋', '追妻', '娇妻', '总裁', '霸总', '傲娇', '情', '婚', '心'], '言情甜宠'),
    (['古风', '穿越', '重生', '宫', '帝', '皇', '将', '相', '朝', '江湖', '仙', '修', '武侠'], '古风穿越'),
    (['科幻', '末世', '星际', '异星', '深空', '宇宙', '未来', '机甲', 'AI'], '科幻末世'),
    (['职场', '商战', '金融', '创业', '公司', '投资'], '职场商战'),
    (['校园', '青春', '少年', '同学', '高中', '大学', '老师', '学'], '青春校园'),
    (['历史', '王朝', '帝国', '战', '三国', '大明', '大唐'], '历史战争'),
    (['心理', '人性', '灵魂', '梦', '暗'], '心理人性'),
    (['奇幻', '魔', '妖', '怪', '神', '龙', '异'], '奇幻玄幻'),
]

DEFAULT_GENRE = '社会现实'


def infer_genre(title: str) -> str:
    """根据书名关键词推断类型。"""
    for keywords, genre in GENRE_KEYWORDS:
        for kw in keywords:
            if kw in title:
                return genre
    return DEFAULT_GENRE


# ============================================================
# 文件读取（多编码支持）
# ============================================================
def read_text_file(filepath: Path) -> Optional[str]:
    """读取txt文件，优先utf-8，失败尝试gbk/gb18030。"""
    for encoding in ('utf-8', 'gbk', 'gb18030', 'utf-8-sig'):
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            if content.strip():
                return content
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


# ============================================================
# 文本清洗与提取
# ============================================================
def clean_content(raw_content: str) -> Tuple[str, Optional[str]]:
    """
    清洗txt内容，去掉开头的来源标识行。
    返回 (cleaned_content, author_or_None)
    """
    lines = raw_content.split('\n')
    author = None
    content_start_idx = 0

    # 跳过开头的元数据行（来源标识、作者等）
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            content_start_idx = i + 1
            continue
        # 检查作者信息
        if stripped.startswith('作者') or stripped.startswith('作者：') or stripped.startswith('作者:'):
            author_match = re.search(r'作者[：:]\s*(.+)', stripped)
            if author_match:
                author = author_match.group(1).strip()
            content_start_idx = i + 1
            continue
        # 检查来源链接行
        if stripped.startswith('原文链接') or stripped.startswith('来源') or stripped.startswith('链接'):
            content_start_idx = i + 1
            continue
        if stripped.startswith('http://') or stripped.startswith('https://'):
            content_start_idx = i + 1
            continue
        # 遇到非元数据行，停止跳过
        break

    cleaned = '\n'.join(lines[content_start_idx:]).strip()
    return cleaned, author


def extract_chapter_info(filename: str) -> Tuple[int, str]:
    """
    从文件名提取章节号和标题。
    例如 "1念念无果.txt" → (1, "念念无果")
    例如 "12余烬未凉.txt" → (12, "余烬未凉")
    """
    name = filename.replace('.txt', '')
    match = re.match(r'^(\d+)(.*)', name)
    if match:
        chapter_num = int(match.group(1))
        chapter_title = match.group(2).strip()
        if not chapter_title:
            chapter_title = f"第{chapter_num}章"
        return chapter_num, chapter_title
    return 1, name


# ============================================================
# 钩子提取
# ============================================================
def split_paragraphs(text: str) -> List[str]:
    """将文本按段落分割，过滤空段。"""
    paras = re.split(r'\n\s*\n|\n', text)
    return [p.strip() for p in paras if p.strip()]


def extract_opening_hook(paragraphs: List[str]) -> Optional[str]:
    """从开头3段提取开篇钩子。"""
    opening_text = ' '.join(paragraphs[:3])
    if not opening_text:
        return None
    # 截取最吸引人的句子（≤100字）
    sentences = re.split(r'[。！？…]', opening_text)
    for s in sentences:
        s = s.strip()
        if 10 <= len(s) <= 100:
            return s
    # 如果没有合适的句子，截取前100字
    return opening_text[:100].strip() if opening_text else None


def extract_suspense_hook(text: str) -> Optional[str]:
    """从章节中间(50%-70%位置)提取悬念钩子。"""
    total_len = len(text)
    if total_len < 200:
        return None

    start_pos = int(total_len * 0.5)
    end_pos = int(total_len * 0.7)
    middle_text = text[start_pos:end_pos]

    # 寻找含转折词的句子
    sentences = re.split(r'[。！？…]', middle_text)
    for s in sentences:
        s = s.strip()
        for word in SUSPENSE_WORDS:
            if word in s and 10 <= len(s) <= 100:
                return s

    return None


def extract_ending_hook(paragraphs: List[str]) -> Optional[str]:
    """从末尾1-2段提取结尾钩子。"""
    if not paragraphs:
        return None
    ending_text = ' '.join(paragraphs[-2:]) if len(paragraphs) >= 2 else paragraphs[-1]
    sentences = re.split(r'[。！？…]', ending_text)
    for s in reversed(sentences):
        s = s.strip()
        if 10 <= len(s) <= 100:
            return s
    return ending_text[:100].strip() if ending_text else None


# ============================================================
# 情绪锚点提取
# ============================================================
def detect_emotion_transitions(text: str) -> List[Dict]:
    """
    检测情绪转折点。
    返回列表，每项包含:
        position (int): 字符位置
        emotion_type (str): '正面→负面' 或 '负面→正面'
        intensity (int): 转折前后情绪词密度差 * 100
        quote (str): 转折点前后各50字上下文
    """
    if len(text) < 500:
        return []

    # 用滑动窗口检测情绪变化
    window_size = 200
    step = 100
    transitions = []

    prev_sentiment = None
    prev_pos_density = 0.0
    prev_neg_density = 0.0

    for offset in range(0, len(text) - window_size + 1, step):
        window = text[offset:offset + window_size]
        pos_count = sum(window.count(w) for w in POSITIVE_WORDS)
        neg_count = sum(window.count(w) for w in NEGATIVE_WORDS)
        total_words = len(window)
        if total_words == 0:
            continue

        pos_density = pos_count / total_words
        neg_density = neg_count / total_words
        current_sentiment = 'positive' if pos_density > neg_density else 'negative'

        if prev_sentiment is not None and current_sentiment != prev_sentiment:
            emotion_type = '正面→负面' if prev_sentiment == 'positive' else '负面→正面'
            intensity = int(abs(prev_pos_density - pos_density + prev_neg_density - neg_density) * 10000)
            intensity = max(1, min(intensity, 100))

            # 提取转折点前后各50字上下文
            center = offset + window_size // 2
            ctx_start = max(0, center - 50)
            ctx_end = min(len(text), center + 50)
            quote = text[ctx_start:ctx_end].replace('\n', ' ').strip()

            transitions.append({
                'position': center,
                'emotion_type': emotion_type,
                'intensity': intensity,
                'quote': quote[:200],  # 限制长度
            })

        prev_sentiment = current_sentiment
        prev_pos_density = pos_density
        prev_neg_density = neg_density

    # 最多保留3个最强转折点
    transitions.sort(key=lambda x: x['intensity'], reverse=True)
    return transitions[:3]


# ============================================================
# 写作技法分析
# ============================================================
def analyze_writing_techniques(text: str, book_id: int, chapter_id: int) -> List[Dict]:
    """
    分析写作技法，返回技法记录列表。
    """
    techniques = []
    total_len = len(text)
    if total_len < 100:
        return techniques

    # 1. 对话占比
    dialogue_pattern = r'[「"「"『](.+?)[」"」"』]'
    dialogue_matches = re.findall(dialogue_pattern, text)
    dialogue_chars = sum(len(m) for m in dialogue_matches)
    dialogue_ratio = dialogue_chars / total_len if total_len > 0 else 0
    techniques.append({
        'chapter_id': chapter_id,
        'book_id': book_id,
        'technique_type': 'dialogue_ratio',
        'name': '对话占比',
        'description': f'对话文本占总字数的比例: {dialogue_ratio:.1%}',
        'example_text': dialogue_matches[0][:100] if dialogue_matches else '',
        'usage_context': f'对话占比{dialogue_ratio:.1%}，{"高对话驱动叙事" if dialogue_ratio > 0.3 else "以叙述为主对话为辅" if dialogue_ratio > 0.1 else "极少对话以描写为主"}',
        'effectiveness_score': int(dialogue_ratio * 100),
    })

    # 2. 叙事视角
    first_person_count = text.count('我')
    third_person_indicators = sum(text.count(w) for w in ['他', '她', '它'])
    total_pronouns = first_person_count + third_person_indicators
    if total_pronouns > 0:
        first_ratio = first_person_count / total_pronouns
    else:
        first_ratio = 0
    pov_type = '第一人称' if first_ratio > 0.5 else '第三人称' if first_ratio < 0.3 else '混合视角'
    techniques.append({
        'chapter_id': chapter_id,
        'book_id': book_id,
        'technique_type': 'pov_type',
        'name': '叙事视角',
        'description': f'叙事视角类型: {pov_type}（第一人称代词占比{first_ratio:.1%}）',
        'example_text': '',
        'usage_context': pov_type,
        'effectiveness_score': int(first_ratio * 100) if first_ratio > 0.5 else int((1 - first_ratio) * 100),
    })

    # 3. 句式节奏（短句<15字占比）
    sentences = re.split(r'[。！？…；\n]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        short_count = sum(1 for s in sentences if len(s) < 15)
        short_ratio = short_count / len(sentences)
        rhythm = '快节奏' if short_ratio > 0.5 else '中等节奏' if short_ratio > 0.3 else '慢节奏'
    else:
        short_ratio = 0
        rhythm = '无法判断'
    techniques.append({
        'chapter_id': chapter_id,
        'book_id': book_id,
        'technique_type': 'sentence_rhythm',
        'name': '句式节奏',
        'description': f'短句(<15字)占比: {short_ratio:.1%}，{rhythm}',
        'example_text': '',
        'usage_context': rhythm,
        'effectiveness_score': int(short_ratio * 100),
    })

    # 4. 感官描写密度
    color_count = sum(text.count(w) for w in COLOR_WORDS)
    sound_count = sum(text.count(w) for w in SOUND_WORDS)
    touch_count = sum(text.count(w) for w in TOUCH_WORDS)
    sensory_total = color_count + sound_count + touch_count
    sensory_density = sensory_total / total_len * 1000 if total_len > 0 else 0  # 每千字感官词数
    sensory_level = '丰富' if sensory_density > 10 else '中等' if sensory_density > 5 else '稀少'
    techniques.append({
        'chapter_id': chapter_id,
        'book_id': book_id,
        'technique_type': 'sensory_detail',
        'name': '感官描写密度',
        'description': f'每千字感官词数: {sensory_density:.1f}（视觉{color_count} 听觉{sound_count} 触觉{touch_count}），{sensory_level}',
        'example_text': '',
        'usage_context': sensory_level,
        'effectiveness_score': int(min(sensory_density * 10, 100)),
    })

    return techniques


# ============================================================
# 去重辅助
# ============================================================
def get_existing_books(conn: sqlite3.Connection) -> set:
    """获取已存在的 books title 集合，用于去重。"""
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM books")
    return {row[0] for row in cursor.fetchall()}


# ============================================================
# 主流程
# ============================================================
def main():
    start_time = time.time()
    print("=" * 60)
    print("知乎盐选专栏批量入库脚本")
    print("=" * 60)
    print(f"源目录: {SOURCE_DIR}")
    print(f"数据库: {DB_PATH}")
    print()

    if not SOURCE_DIR.exists():
        print(f"ERROR: 源目录不存在: {SOURCE_DIR}")
        return

    if not DB_PATH.exists():
        print(f"ERROR: 数据库不存在: {DB_PATH}")
        return

    # 连接数据库（不启用FK约束，与现有数据保持一致）
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cursor = conn.cursor()

    # 获取已有书籍（去重用）
    existing_titles = get_existing_books(conn)
    print(f"数据库已有 {len(existing_titles)} 本书籍")

    # 统计计数
    stats = {
        'books_inserted': 0,
        'books_skipped': 0,
        'chapters_inserted': 0,
        'hooks_inserted': 0,
        'emotion_anchors_inserted': 0,
        'writing_techniques_inserted': 0,
        'files_error': 0,
    }

    # 批量缓存
    batch_books = []
    batch_chapters = []
    batch_hooks = []
    batch_emotion_anchors = []
    batch_writing_techniques = []
    batch_counter = 0

    # 遍历22个首字母目录
    letter_dirs = sorted([d for d in SOURCE_DIR.iterdir() if d.is_dir()])
    total_letters = len(letter_dirs)
    print(f"共发现 {total_letters} 个首字母目录")
    print()

    for letter_idx, letter_dir in enumerate(letter_dirs, 1):
        letter_name = letter_dir.name
        book_dirs = sorted([d for d in letter_dir.iterdir() if d.is_dir()])
        print(f"[{letter_idx}/{total_letters}] 处理 {letter_name} ({len(book_dirs)} 个专栏)...")

        for book_dir in book_dirs:
            book_title_raw = book_dir.name

            # 去重检查
            if book_title_raw in existing_titles:
                stats['books_skipped'] += 1
                continue

            # 收集该书的章节文件
            chapter_files = sorted(
                [f for f in book_dir.iterdir() if f.is_file() and f.suffix == '.txt'],
                key=lambda f: f.name
            )

            if not chapter_files:
                continue

            # 读取所有章节
            chapters_data = []
            book_author = None
            book_word_count = 0

            for ch_file in chapter_files:
                content_raw = read_text_file(ch_file)
                if content_raw is None:
                    stats['files_error'] += 1
                    continue

                content_cleaned, author_from_file = clean_content(content_raw)
                if author_from_file and not book_author:
                    book_author = author_from_file

                chapter_num, chapter_title = extract_chapter_info(ch_file.name)
                word_count = len(content_cleaned)
                book_word_count += word_count

                chapters_data.append({
                    'chapter_num': chapter_num,
                    'title': chapter_title,
                    'content': content_cleaned,
                    'word_count': word_count,
                })

            if not chapters_data:
                continue

            # 章节按编号排序
            chapters_data.sort(key=lambda x: x['chapter_num'])

            # 推断genre
            genre = infer_genre(book_title_raw)

            # ---- 插入 books ----
            cursor.execute(
                """INSERT INTO books (title, author, platform, genre, mode, word_count, chapter_count, status, is_reference, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    book_title_raw,
                    book_author,
                    '知乎盐选',
                    genre,
                    None,
                    book_word_count,
                    len(chapters_data),
                    'completed',
                    1,
                    letter_name,
                )
            )
            book_id = cursor.lastrowid
            existing_titles.add(book_title_raw)
            stats['books_inserted'] += 1
            batch_counter += 1

            # ---- 插入 chapters + hooks + emotion_anchors + writing_techniques ----
            for ch_data in chapters_data:
                is_opening = 1 if ch_data['chapter_num'] <= 3 else 0

                cursor.execute(
                    """INSERT INTO chapters (book_id, chapter_num, title, content, word_count, is_opening, is_ending)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        book_id,
                        ch_data['chapter_num'],
                        ch_data['title'],
                        ch_data['content'],
                        ch_data['word_count'],
                        is_opening,
                        0,
                    )
                )
                chapter_id = cursor.lastrowid
                stats['chapters_inserted'] += 1
                batch_counter += 1

                # 提取钩子
                paragraphs = split_paragraphs(ch_data['content'])
                text = ch_data['content']

                # 开篇钩子
                opening_hook = extract_opening_hook(paragraphs)
                if opening_hook:
                    cursor.execute(
                        """INSERT INTO hooks (chapter_id, hook_type, position, strength, description, quote)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (chapter_id, 'opening', 'start', None, '开篇钩子', opening_hook[:100])
                    )
                    stats['hooks_inserted'] += 1
                    batch_counter += 1

                # 悬念钩子
                suspense_hook = extract_suspense_hook(text)
                if suspense_hook:
                    cursor.execute(
                        """INSERT INTO hooks (chapter_id, hook_type, position, strength, description, quote)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (chapter_id, 'suspense', 'middle', None, '悬念钩子', suspense_hook[:100])
                    )
                    stats['hooks_inserted'] += 1
                    batch_counter += 1

                # 结尾钩子
                ending_hook = extract_ending_hook(paragraphs)
                if ending_hook:
                    cursor.execute(
                        """INSERT INTO hooks (chapter_id, hook_type, position, strength, description, quote)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (chapter_id, 'emotion', 'end', None, '结尾钩子', ending_hook[:100])
                    )
                    stats['hooks_inserted'] += 1
                    batch_counter += 1

                # 情绪转折点
                emotion_transitions = detect_emotion_transitions(text)
                for et in emotion_transitions:
                    cursor.execute(
                        """INSERT INTO emotion_anchors (chapter_id, position, emotion_type, intensity, description, quote)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            chapter_id,
                            et['position'],
                            et['emotion_type'],
                            et['intensity'],
                            f"情绪转折: {et['emotion_type']}",
                            et['quote'],
                        )
                    )
                    stats['emotion_anchors_inserted'] += 1
                    batch_counter += 1

                # 写作技法分析
                techniques = analyze_writing_techniques(text, book_id, chapter_id)
                for tech in techniques:
                    cursor.execute(
                        """INSERT INTO writing_techniques (chapter_id, book_id, technique_type, name, description, example_text, usage_context, effectiveness_score)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            tech['chapter_id'],
                            tech['book_id'],
                            tech['technique_type'],
                            tech['name'],
                            tech['description'],
                            tech['example_text'][:200] if tech['example_text'] else '',
                            tech['usage_context'],
                            tech['effectiveness_score'],
                        )
                    )
                    stats['writing_techniques_inserted'] += 1
                    batch_counter += 1

                # 批量提交
                if batch_counter >= BATCH_SIZE:
                    conn.commit()
                    batch_counter = 0

        # 每处理完一个首字母目录打印进度
        elapsed = time.time() - start_time
        print(f"  -> 已入库 {stats['books_inserted']} 本书, {stats['chapters_inserted']} 章"
              f" (跳过 {stats['books_skipped']} 本, 错误 {stats['files_error']} 文件)"
              f" [耗时 {elapsed:.1f}s]")

    # 最终提交
    conn.commit()
    conn.close()

    # 打印汇总
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print("导入完成！统计汇总：")
    print("-" * 40)
    print(f"  入库书籍数:     {stats['books_inserted']}")
    print(f"  跳过书籍数:     {stats['books_skipped']} (已存在)")
    print(f"  入库章节数:     {stats['chapters_inserted']}")
    print(f"  钩子记录数:     {stats['hooks_inserted']}")
    print(f"  情绪锚点数:     {stats['emotion_anchors_inserted']}")
    print(f"  写作技法数:     {stats['writing_techniques_inserted']}")
    print(f"  读取失败文件:   {stats['files_error']}")
    print(f"  总耗时:         {elapsed:.1f}s")
    print("=" * 60)


if __name__ == '__main__':
    main()
