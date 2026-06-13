#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI创作引擎 v3
从"被动仓库"升级为"主动创作引擎"

核心能力：
1. 多源素材统一入库（网络文学/科幻/豆瓣等）
2. 每章提取多维特征（钩子/情绪/对话/句法）
3. 跨书跨类型模式挖掘（类型×章节位置→最优策略）
4. 主动写作策略推荐（写前查询，获得可执行指引）
"""

import re
import json
import sqlite3
import statistics
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

# 复用现有工具
try:
    from style_fingerprint import StyleFingerprint, DynamicScorer
except ImportError:
    StyleFingerprint = None
    DynamicScorer = None


# ============================================================
# 素材源映射：路径→类型→题材
# ============================================================

# 素材库根目录：knowledge/ → 盘古ai/ → 小说/素材库/
MATERIAL_ROOT = Path(__file__).resolve().parent.parent.parent / "素材库"

# 网络文学十大类别 → 题材映射
NETWORK_LIT_GENRES = {
    "网络文学20年十大玄幻作家作品系列": "玄幻",
    "网络文学20年十大仙侠作家作品系列": "仙侠",
    "网络文学20年十大都市作家作品系列": "都市",
    "网络文学20年十大历史作家作品系列": "历史",
    "网络文学20年十大科幻作家作品系列": "科幻",
    "网络文学20年十大悬疑作家作品系列": "悬疑",
    "网络文学20年十大游戏作家作品系列": "游戏",
    "网络文学20年十大体育作家作品系列": "体育",
    "网络文学20年十大军事作家作品系列": "军事",
    "网络文学20年十大西方奇幻作家作品系列": "奇幻",
    "网络文学20年十大言情作家作品系列": "言情",
}

# 都市类的爆款/豆瓣书标记
DOUBAN_MARKERS = [
    "三体", "一九八四", "球状闪电", "呼吸", "尤比克", "盲视", "沙丘",
    "华氏451", "人类简史", "云游", "克拉拉与太阳", "冬牧场",
    "地下室手记", "厌女", "可能性的艺术", "刀锋", "南明史",
    "两京十五日", "克拉拉与太阳", "一日三秋", "下沉年代",
    "亲爱的生活", "仿制药的真相", "名侦探的献祭", 
]

# 起点爆款标记（玄幻/仙侠/历史等类别中的代表作）
QIDIAN_BESTSELLERS = [
    "斗破苍穹", "斗罗大陆", "星辰变", "盘龙", "紫川", "亵渎",
    "佛本是道", "恶魔法则", "庆余年", "回到明朝当王爷",
    "佣兵天下", "兽血沸腾", "无限恐怖", "仙葫", "寸芒",
    "冠军教父", "法师传奇", "猛龙过江", "王牌进化",
    "天擎", "小兵传奇", "机动风暴", "武装风暴",
]


class CreativeEngine:
    """
    盘古AI创作引擎
    
    使用方式：
        engine = CreativeEngine()
        engine.import_all_sources()          # 首次使用：导入所有素材
        engine.mine_all_genre_patterns()     # 模式挖掘
        strategy = engine.recommend_strategy("玄幻", chapter_num=3)  # 写前推荐
    """
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent / "creative_engine.db"
        self.db_path = Path(db_path)
        self._init_db()
    
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    
    def _init_db(self):
        """初始化数据库架构"""
        schema_path = Path(__file__).parent / "creative_engine_schema.sql"
        if not schema_path.exists():
            print(f"[ERROR] Schema文件不存在: {schema_path}")
            return
        
        conn = self._get_conn()
        with open(schema_path, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
    
    # ========== 素材导入 ==========
    
    def import_all_sources(self, force=False):
        """
        从素材库所有子目录导入书籍和章节。
        自动识别题材、平台、来源。
        """
        print("=" * 60)
        print("  盘古创作引擎 - 全源素材导入")
        print("=" * 60)
        
        if not MATERIAL_ROOT.exists():
            print(f"[ERROR] 素材库不存在: {MATERIAL_ROOT}")
            return
        
        stats = {"total_files": 0, "imported": 0, "skipped": 0, "errors": 0}
        
        # 1. 导入网络文学十大类别
        netlit_path = MATERIAL_ROOT / "网络文学"
        if netlit_path.exists():
            for dir_name, genre in NETWORK_LIT_GENRES.items():
                dir_path = netlit_path / dir_name
                if dir_path.exists():
                    print(f"\n[{genre}] {dir_name}")
                    source_type = "qidian_bestseller" if genre in ("玄幻", "仙侠", "历史", "玄幻") else "web_novel"
                    self._import_directory(dir_path, genre, source_type, stats, force)
        
        # 2. 导入科幻奇幻
        scifi_path = MATERIAL_ROOT / "科幻奇幻"
        if scifi_path.exists():
            print(f"\n[科幻] 世界科幻大师丛书")
            self._import_directory(scifi_path, "科幻", "sci_fi", stats, force)
        
        # 3. 合并去重（同书不同格式）
        self._deduplicate_books()
        
        print(f"\n{'=' * 60}")
        print(f"导入完成: 总扫描{stats['total_files']} | "
              f"导入{stats['imported']} | 跳过{stats['skipped']} | 错误{stats['errors']}")
        print(f"{'=' * 60}")
        
        return stats
    
    def _import_directory(self, dir_path, genre, source_type, stats, force):
        """导入一个目录下的所有txt文件"""
        source_name = dir_path.name
        
        # 注册或更新来源
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT id FROM source_catalog WHERE source_name=?",
            (source_name,)
        )
        row = cursor.fetchone()
        if row:
            source_id = row[0]
            if not force:
                already = conn.execute(
                    "SELECT COUNT(*) as cnt FROM books WHERE source_id=?", (source_id,)
                ).fetchone()["cnt"]
                if already > 0:
                    print(f"  [SKIP] 已导入(源ID={source_id}，{already}本书)")
                    conn.close()
                    stats["skipped"] += already
                    return
        else:
            conn.execute(
                "INSERT INTO source_catalog (source_name, source_type, root_path) VALUES (?,?,?)",
                (source_name, source_type, str(dir_path))
            )
            source_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        
        # 扫描txt文件
        txt_files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.TXT"))
        
        for txt_file in txt_files:
            stats["total_files"] += 1
            title = txt_file.stem
            
            # 跳过非小说文件
            if len(title) < 2 or title in ("README", "index", "目录", "说明"):
                continue
            
            # 检查是否已存在
            existing = conn.execute(
                "SELECT id, imported_chapters FROM books WHERE title=? AND source_id=?",
                (title, source_id)
            ).fetchone()
            
            if existing and not force:
                stats["skipped"] += 1
                continue
            
            # 解析小说
            try:
                content = self._read_text_file(txt_file)
                if not content or len(content) < 200:
                    stats["skipped"] += 1
                    continue
                
                chapters = self._split_chapters(content)
                if not chapters:
                    stats["skipped"] += 1
                    continue
                
                # 判断子分类和平台
                sub_genre, platform, ranking = self._classify_book(title, genre)
                
                # 插入或更新书籍
                total_words = sum(len(ch) for ch in chapters)
                
                if existing:
                    book_id = existing["id"]
                    conn.execute(
                        "UPDATE books SET sub_genre=?, platform=?, ranking=?, "
                        "word_count_total=?, chapter_count=?, imported_chapters=? WHERE id=?",
                        (sub_genre, platform, ranking, total_words, len(chapters), len(chapters), book_id)
                    )
                else:
                    conn.execute(
                        "INSERT INTO books (title, author, source_id, genre, sub_genre, "
                        "platform, ranking, word_count_total, chapter_count, imported_chapters) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (title, "", source_id, genre, sub_genre, platform, ranking,
                         total_words, len(chapters), len(chapters))
                    )
                    book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                # 插入章节（只取前30章用于模式分析）
                for i, ch_content in enumerate(chapters[:30], 1):
                    ch_word_count = len(ch_content.replace('\n', '').replace(' ', ''))
                    conn.execute(
                        "INSERT OR REPLACE INTO chapters (book_id, chapter_num, content, word_count, is_first_chapter) "
                        "VALUES (?,?,?,?,?)",
                        (book_id, i, ch_content, ch_word_count, 1 if i == 1 else 0)
                    )
                
                conn.commit()
                stats["imported"] += 1
                print(f"  [OK] {title} ({len(chapters)}章/{total_words}字)"
                      f" | {genre}/{sub_genre} | {platform}")
                
            except Exception as e:
                stats["errors"] += 1
                print(f"  [ERR] {title}: {e}")
        
        conn.close()
    
    def _read_text_file(self, filepath):
        """读取文本文件，自动处理编码"""
        for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                if len(content) > 200:
                    return content
            except (UnicodeDecodeError, UnicodeError):
                continue
        return None
    
    def _split_chapters(self, content):
        """智能分章：自动识别常见章节标记"""
        # 常见章节标记
        patterns = [
            r'(第[零一二三四五六七八九十百千万\d]+[章节回卷])',
            r'(第\s*\d+\s*章)',
            r'(Chapter\s*\d+)',
            r'(\n第[零一二三四五六七八九十百千万\d]+[章节回卷])',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, content))
            if len(matches) >= 3:
                break
        
        if len(matches) < 2:
            # 无法识别章节，按长度切分（每章约3000字）
            chunk_size = 3000
            return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size) if len(content[i:i+chunk_size]) > 200]
        
        chapters = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(content)
            ch = content[start:end].strip()
            # 去除章节标题行
            ch = re.sub(r'^.*?[章节回卷].*?\n', '', ch, count=1)
            if len(ch) > 200:
                chapters.append(ch)
        
        return chapters
    
    def _classify_book(self, title, genre):
        """根据书名和题材判断子分类、平台、是否为爆款"""
        platform = "未知"
        sub_genre = genre
        ranking = 0
        
        # 起点爆款标记
        if any(bs in title for bs in QIDIAN_BESTSELLERS):
            platform = "起点"
            ranking = 5  # 高排名
        elif "豆瓣" in str(title) or any(dm in title for dm in DOUBAN_MARKERS):
            platform = "豆瓣"
            ranking = 3
        
        # 细分子分类
        if genre == "玄幻":
            if any(kw in title for kw in ["斗破", "斗罗", "盘龙", "星辰变"]):
                sub_genre = "东方玄幻"
                ranking = max(ranking, 5)
            elif any(kw in title for kw in ["佣兵", "兽血", "善良的死神"]):
                sub_genre = "西方奇幻"
                platform = "起点"
        
        return sub_genre, platform, ranking
    
    def _deduplicate_books(self):
        """合并同书不同格式的重复记录"""
        conn = self._get_conn()
        # 找同名书籍
        dupes = conn.execute(
            "SELECT title, COUNT(*) as cnt, GROUP_CONCAT(id) as ids FROM books "
            "GROUP BY title HAVING cnt > 1"
        ).fetchall()
        
        removed = 0
        for dupe in dupes:
            ids = [int(x) for x in dupe["ids"].split(",")]
            keep_id = ids[0]
            for dup_id in ids[1:]:
                # 把重复的章节移到保留的记录
                conn.execute(
                    "UPDATE chapters SET book_id=? WHERE book_id=?",
                    (keep_id, dup_id)
                )
                conn.execute("DELETE FROM books WHERE id=?", (dup_id,))
                removed += 1
        
        conn.commit()
        conn.close()
        if removed:
            print(f"  去重: 移除{removed}条重复书籍记录")
    
    # ========== 特征提取 ==========
    
    def extract_all_features(self, force=False):
        """
        为所有已导入的章节提取多维特征。
        填充 chapter_features 表。
        """
        conn = self._get_conn()
        
        # 获取待处理的章节
        if force:
            conn.execute("DELETE FROM chapter_features")
        
        chapters = conn.execute(
            "SELECT c.id, c.book_id, c.chapter_num, c.content, b.genre "
            "FROM chapters c JOIN books b ON c.book_id=b.id "
            "WHERE c.id NOT IN (SELECT chapter_id FROM chapter_features) "
            "ORDER BY b.genre, c.chapter_num"
        ).fetchall()
        
        total = len(chapters)
        print(f"\n特征提取: {total}个章节待处理...")
        
        scorer = None
        if DynamicScorer:
            try:
                scorer = DynamicScorer()
            except Exception:
                pass
        
        for i, ch in enumerate(chapters):
            if i % 50 == 0:
                print(f"  进度: {i}/{total}")
            
            features = self._extract_chapter_features(ch["content"], ch["chapter_num"], scorer)
            
            conn.execute(
                """INSERT OR REPLACE INTO chapter_features 
                (chapter_id, book_id, chapter_num, chapter_position,
                 avg_sentence_len, sentence_len_variance, avg_paragraph_len,
                 dialogue_ratio, avg_dialogue_len,
                 pos_sentiment_ratio, neg_sentiment_ratio, emotion_variance, high_intensity_ratio,
                 hook_type, hook_strength, hook_emotion_cliff,
                 event_count, action_density, description_density)
                VALUES (?,?,?,?, ?,?,?, ?,?, ?,?,?,?, ?,?,?, ?,?,?)""",
                (ch["id"], ch["book_id"], ch["chapter_num"], features["chapter_position"],
                 features["avg_sentence_len"], features["sentence_len_variance"], features["avg_paragraph_len"],
                 features["dialogue_ratio"], features["avg_dialogue_len"],
                 features["pos_ratio"], features["neg_ratio"], features["emotion_variance"], features["high_intensity_ratio"],
                 features["hook_type"], features["hook_strength"], features["hook_emotion_cliff"],
                 features["event_count"], features["action_density"], features["description_density"])
            )
        
        conn.commit()
        conn.close()
        print(f"  完成: {total}个章节特征已入库")
    
    def _extract_chapter_features(self, content, chapter_num, scorer=None):
        """提取单章的多维特征"""
        # 章节位置分类
        if chapter_num <= 3:
            position = "opening"
        elif chapter_num <= 10:
            position = "early"
        elif chapter_num <= 30:
            position = "mid"
        else:
            position = "late"
        
        # 句法——修复：用更精准的中文分句
        # 中文句号、感叹号、问号、省略号都算一句结束
        sentences = re.split(r'[。！？!?…\.]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 3]
        sent_lens = [len(s) for s in sentences] if sentences else [20]
        
        # 段落
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        para_lens = [len(p) for p in paragraphs] if paragraphs else [100]
        
        # 对话
        dialogue_markers = {"说", "道", "问", "答", "喊", "叫", "吼", "骂"}
        dialogue_paras = [p for p in paragraphs if any(m in p for m in dialogue_markers) or re.search(r'["""]', p)]
        
        # 情绪（使用动态评分器）
        pos_ratio = neg_ratio = emotion_var = high_intensity = 0
        hook_type = "unknown"
        hook_strength = hook_cliff = 0
        
        if scorer:
            try:
                sentiment = scorer.analyze_sentences(content)
                if sentiment:
                    scores = [s.score for s in sentiment]
                    intensities = [s.intensity for s in sentiment]
                    pos_ratio = sum(1 for s in scores if s > 0.2) / len(scores)
                    neg_ratio = sum(1 for s in scores if s < -0.2) / len(scores)
                    emotion_var = statistics.variance(scores) if len(scores) > 1 else 0
                    high_intensity = sum(1 for i in intensities if i > 0.5) / len(intensities)
                    
                    # 钩子分析
                    last_3 = scores[-3:] if len(scores) >= 3 else scores
                    if last_3:
                        hook_cliff = abs(last_3[-1] - last_3[-2]) if len(last_3) >= 2 else 0
                        avg_last = sum(last_3) / len(last_3)
                        if avg_last > 0.3:
                            hook_type = "expectation"
                        elif avg_last < -0.3:
                            hook_type = "threat"
                        elif hook_cliff > 0.5:
                            hook_type = "reversal"
                        else:
                            hook_type = "suspense"
                    
                    hook_s, _ = scorer.score_hook_power(sentiment)
                    hook_strength = hook_s
            except Exception:
                pass
        
        # 事件密度
        action_verbs = r'(走|跑|冲|抓|拿|拔|砍|杀|打|推|拉|踢|踹|挥|劈|刺|射)'
        event_count = len(re.findall(action_verbs, content))
        word_count = max(len(content.replace('\n', '').replace(' ', '')), 1)
        
        return {
            "chapter_position": position,
            "avg_sentence_len": statistics.mean(sent_lens),
            "sentence_len_variance": statistics.variance(sent_lens) if len(sent_lens) > 1 else 0,
            "avg_paragraph_len": statistics.mean(para_lens),
            "dialogue_ratio": len(dialogue_paras) / max(len(paragraphs), 1),
            "avg_dialogue_len": statistics.mean([len(p) for p in dialogue_paras]) if dialogue_paras else 0,
            "pos_ratio": pos_ratio,
            "neg_ratio": neg_ratio,
            "emotion_variance": emotion_var,
            "high_intensity_ratio": high_intensity,
            "hook_type": hook_type,
            "hook_strength": hook_strength,
            "hook_emotion_cliff": hook_cliff,
            "event_count": event_count,
            "action_density": event_count / word_count * 1000,
            "description_density": 0,  # 后续精细化
        }
    
    # ========== 模式挖掘 ==========
    
    def mine_all_genre_patterns(self):
        """
        跨书跨类型模式挖掘。
        从 chapter_features 聚合出 genre_patterns。
        这是"被动仓库→主动引擎"的关键步骤。
        """
        conn = self._get_conn()
        
        # 清理旧模式
        conn.execute("DELETE FROM genre_patterns")
        
        # 获取所有(类型, 章节位置)组合
        combos = conn.execute(
            "SELECT DISTINCT b.genre, cf.chapter_position "
            "FROM chapter_features cf JOIN books b ON cf.book_id=b.id "
            "WHERE b.genre != '' "
            "ORDER BY b.genre, cf.chapter_position"
        ).fetchall()
        
        print(f"\n模式挖掘: {len(combos)}个(类型×位置)组合...")
        
        for combo in combos:
            genre = combo["genre"]
            position = combo["chapter_position"]
            
            # 聚合该组合下所有章节的特征
            stats = conn.execute(
                """SELECT 
                    COUNT(*) as sample_count,
                    AVG(avg_sentence_len) as avg_sent,
                    AVG(dialogue_ratio) as avg_dialogue,
                    AVG(pos_sentiment_ratio) as avg_pos,
                    AVG(emotion_variance) as avg_emotion_var,
                    AVG(hook_strength) as avg_hook_strength,
                    AVG(action_density) as avg_action
                FROM chapter_features cf 
                JOIN books b ON cf.book_id=b.id
                WHERE b.genre=? AND cf.chapter_position=?""",
                (genre, position)
            ).fetchone()
            
            if not stats or stats["sample_count"] < 3:
                continue
            
            # 最优钩子类型
            hook_dist = conn.execute(
                """SELECT hook_type, COUNT(*) as cnt 
                FROM chapter_features cf JOIN books b ON cf.book_id=b.id
                WHERE b.genre=? AND cf.chapter_position=? AND hook_type != 'unknown'
                GROUP BY hook_type ORDER BY cnt DESC""",
                (genre, position)
            ).fetchall()
            
            hook_dist_dict = {h["hook_type"]: h["cnt"] for h in hook_dist}
            total_hooks = sum(hook_dist_dict.values())
            hook_dist_json = json.dumps(
                {k: round(v/total_hooks, 3) for k, v in hook_dist_dict.items()}
            ) if total_hooks > 0 else "{}"
            
            best_hook = hook_dist[0]["hook_type"] if hook_dist else "unknown"
            
            # 生成洞察
            insight = self._generate_insight(genre, position, stats, hook_dist_dict)
            
            conn.execute(
                """INSERT INTO genre_patterns 
                (genre, chapter_position, sample_count,
                 rec_avg_sentence_len, rec_dialogue_ratio,
                 rec_hook_type, hook_type_distribution,
                 rec_pos_ratio, rec_emotion_variance,
                 rec_event_count, rec_narrative_focus,
                 insight, confidence)
                VALUES (?,?,?, ?,?, ?,?, ?,?, ?,?, ?,?)""",
                (genre, position, stats["sample_count"],
                 round(stats["avg_sent"], 1) if stats["avg_sent"] else 0,
                 round(stats["avg_dialogue"], 3) if stats["avg_dialogue"] else 0,
                 best_hook, hook_dist_json,
                 round(stats["avg_pos"], 3) if stats["avg_pos"] else 0,
                 round(stats["avg_emotion_var"], 3) if stats["avg_emotion_var"] else 0,
                 round(stats["avg_action"], 1) if stats["avg_action"] else 0,
                 self._classify_narrative(stats),
                 insight,
                 min(0.95, stats["sample_count"] / 50)  # 样本越多置信度越高
                )
            )
        
        conn.commit()
        
        # 统计
        total_patterns = conn.execute("SELECT COUNT(*) as cnt FROM genre_patterns").fetchone()["cnt"]
        conn.close()
        print(f"  完成: {total_patterns}个创作模式已入库")
    
    def _classify_narrative(self, stats):
        """根据聚合统计判断主导叙事模式"""
        dialogue = stats["avg_dialogue"] or 0
        action = stats["avg_action"] or 0
        if dialogue > 0.35:
            return "dialogue_driven"
        elif action > 5:
            return "action_driven"
        return "description_driven"
    
    def _generate_insight(self, genre, position, stats, hook_dist):
        """生成人类可读的模式洞察"""
        hook_str = "、".join([f"{k}({v}章)" for k, v in sorted(hook_dist.items(), key=lambda x: -x[1])[:3]])
        
        position_cn = {"opening": "开篇(1-3章)", "early": "前期(4-10章)", "mid": "中期(11-30章)", "late": "后期(31章+)"}
        pos_name = position_cn.get(position, position)
        
        sent_len = stats["avg_sent"] or 0
        
        insight = (
            f"{genre}类型{pos_name}的特征: "
            f"均句长{sent_len:.0f}字, "
            f"对话率{(stats['avg_dialogue'] or 0)*100:.0f}%, "
            f"最优钩子类型为{next(iter(hook_dist)) if hook_dist else '未知'}, "
            f"基于{stats['sample_count']}个章节样本"
        )
        return insight
    
    # ========== 主动推荐引擎 ★ ==========
    
    def recommend_strategy(self, genre, chapter_num=1, platform=""):
        """
        ★ 核心功能：主动写作策略推荐 ★
        
        给定类型和章节号，返回基于模式挖掘的可执行写作策略。
        
        返回:
        {
            "chapter_num": 3,
            "genre": "玄幻",
            "sample_count": 45,
            "confidence": 0.9,
            "recommendations": {
                "sentence": {"avg_len": 15, "detail": "偏短句，节奏快"},
                "dialogue": {"ratio": 0.42, "detail": "对话率为该类型标准值"},
                "hook": {"type": "expectation", "distribution": {...}, "detail": "最佳钩子类型"},
                "emotion": {"arc": "...", "pos_ratio": 0.35, ...},
                "narrative": {"focus": "action_driven"},
            },
            "reference_books": [...],
            "insight": "人类可读的模式发现",
            "actionable_tips": ["具体可执行的建议1", "建议2", ...]
        }
        """
        # 确定章节位置
        if chapter_num <= 3:
            position = "opening"
        elif chapter_num <= 10:
            position = "early"
        elif chapter_num <= 30:
            position = "mid"
        else:
            position = "late"
        
        conn = self._get_conn()
        
        # 查询预计算的模式
        pattern = conn.execute(
            "SELECT * FROM genre_patterns WHERE genre=? AND chapter_position=? ORDER BY sample_count DESC LIMIT 1",
            (genre, position)
        ).fetchone()
        
        if not pattern:
            # 没有该类型的精准数据，用通用模式
            pattern = conn.execute(
                "SELECT * FROM genre_patterns WHERE genre=? ORDER BY sample_count DESC LIMIT 1",
                (genre,)
            ).fetchone()
        
        if not pattern:
            # 用全类型平均作为兜底
            conn.close()
            return self._fallback_strategy(genre, chapter_num)
        
        # 查找参考书籍
        ref_books = conn.execute(
            """SELECT DISTINCT b.title, b.author, b.platform, b.ranking
            FROM chapter_features cf 
            JOIN books b ON cf.book_id=b.id
            WHERE b.genre=? AND cf.chapter_position=?
            ORDER BY b.ranking DESC LIMIT 5""",
            (genre, position)
        ).fetchall()
        
        conn.close()
        
        # 解析钩子分布
        hook_dist = json.loads(pattern["hook_type_distribution"]) if pattern["hook_type_distribution"] else {}
        
        # 构建推荐
        strategy = {
            "chapter_num": chapter_num,
            "chapter_position": position,
            "genre": genre,
            "platform": platform or "all",
            "sample_count": pattern["sample_count"],
            "confidence": round(pattern["confidence"], 2),
            "recommendations": {
                "sentence": {
                    "avg_len": pattern["rec_avg_sentence_len"],
                    "detail": f"该类型{position}阶段均句长{pattern['rec_avg_sentence_len']:.0f}字"
                },
                "dialogue": {
                    "ratio": pattern["rec_dialogue_ratio"],
                    "detail": f"对话率{pattern['rec_dialogue_ratio']*100:.0f}%"
                },
                "hook": {
                    "type": pattern["rec_hook_type"],
                    "distribution": hook_dist,
                    "detail": f"最优钩子：{pattern['rec_hook_type']}"
                },
                "emotion": {
                    "pos_ratio": pattern["rec_pos_ratio"],
                    "variance": pattern["rec_emotion_variance"],
                    "detail": f"正向情绪{pattern['rec_pos_ratio']*100:.0f}%，波动{'大' if (pattern['rec_emotion_variance'] or 0) > 0.3 else '中'}"
                },
                "narrative": {
                    "focus": pattern["rec_narrative_focus"],
                }
            },
            "reference_books": [
                {"title": rb["title"], "author": rb["author"], "platform": rb["platform"]}
                for rb in ref_books
            ],
            "insight": pattern["insight"],
            "actionable_tips": self._generate_tips(pattern, genre, position, chapter_num),
        }
        
        return strategy
    
    def _fallback_strategy(self, genre, chapter_num):
        """无数据时的兜底策略"""
        return {
            "chapter_num": chapter_num,
            "genre": genre,
            "sample_count": 0,
            "confidence": 0.1,
            "insight": "该类型暂无足够样本，使用通用网文策略",
            "actionable_tips": [
                "黄金三章：第一句发生事情，主角主动行动",
                "300字内出冲突，500字亮金手指",
                "章末留强钩子，让读者必须点下一章",
                "对话率保持在35%-45%之间",
            ]
        }
    
    def _generate_tips(self, pattern, genre, position, chapter_num):
        """根据模式生成可执行的具体建议"""
        tips = []
        hook_type = pattern["rec_hook_type"]
        
        if position == "opening" and chapter_num == 1:
            tips.append(f"第1章开篇避免环境描写，第一句话就发生事情")
            tips.append(f"前500字内展示或暗示金手指")
        elif position == "opening" and chapter_num == 2:
            tips.append(f"第2章深化人设，用事件而非旁白展示性格")
            tips.append(f"钩子类型从第1章切换（避免连续同类型钩子）")
        elif position == "opening" and chapter_num == 3:
            tips.append(f"第3章完成第一个完整爽点闭环（压抑→爆发→获得→展示）")
            tips.append(f"锚定全书主线方向")
        
        if hook_type == "expectation":
            tips.append(f"推荐使用期待型钩子：暗示下一章会看到更强大的东西")
        elif hook_type == "threat":
            tips.append(f"推荐使用危机型钩子：制造紧迫感，但不要每章都用")
        elif hook_type == "suspense":
            tips.append(f"推荐使用悬念型钩子：制造信息缺口，'他不知道的是...'")
        
        sent_len = pattern["rec_avg_sentence_len"] or 20
        if sent_len < 15:
            tips.append(f"保持短句风格（均句长{sent_len:.0f}字），节奏紧凑")
        elif sent_len > 25:
            tips.append(f"可以采用中长句（均句长{sent_len:.0f}字），但注意段落不要太长")
        
        dialogue_ratio = pattern["rec_dialogue_ratio"] or 0.35
        tips.append(f"对话率目标约{dialogue_ratio*100:.0f}%")
        
        return tips
    
    def get_strategy_prompt(self, genre, chapter_num=1, platform=""):
        """
        将推荐策略转化为可直接注入AI system prompt的文本。
        """
        strategy = self.recommend_strategy(genre, chapter_num, platform)
        
        if strategy.get("sample_count", 0) == 0:
            return ""
        
        rec = strategy["recommendations"]
        tips = strategy.get("actionable_tips", [])
        
        prompt = f"""
[创作引擎战略指引] 
基于{strategy['sample_count']}个{genre}类型章节的模式分析（置信度{strategy['confidence']:.0%}）：

句法参数：均句长{rec['sentence']['avg_len']:.0f}字
对话参数：目标对话率{rec['dialogue']['ratio']*100:.0f}%
钩子策略：最优类型为「{rec['hook']['type']}」
情绪策略：正向情绪{rec['emotion']['pos_ratio']*100:.0f}%，波动{'偏大' if rec['emotion']['variance'] > 0.3 else '适中'}
叙事焦点：{rec['narrative']['focus']}

模式发现：{strategy['insight']}

具体建议：
""" + "\n".join([f"- {tip}" for tip in tips])
        
        if strategy.get("reference_books"):
            refs = "、".join([f"《{rb['title']}》" for rb in strategy["reference_books"][:5]])
            prompt += f"\n\n参考作品：{refs}"
        
        return prompt.strip()


# ============================================================
# 便捷命令行入口
# ============================================================

def main():
    import sys
    
    engine = CreativeEngine()
    
    if len(sys.argv) < 2:
        print("盘古AI创作引擎 v3")
        print("=" * 40)
        print("命令:")
        print("  import              - 从素材库导入所有书籍")
        print("  import --force      - 强制重新导入")
        print("  features            - 提取所有章节特征")
        print("  mine                - 挖掘类型创作模式")
        print("  recommend <genre> [chapter] [platform] - 获取写作策略推荐")
        print("  pipeline            - 完整流水线(import→features→mine)")
        print("  stats               - 查看数据库统计")
        print()
        return
    
    cmd = sys.argv[1]
    
    if cmd == "import":
        force = "--force" in sys.argv
        engine.import_all_sources(force=force)
    
    elif cmd == "features":
        force = "--force" in sys.argv
        engine.extract_all_features(force=force)
    
    elif cmd == "mine":
        engine.mine_all_genre_patterns()
    
    elif cmd == "pipeline":
        print("完整流水线: import → features → mine")
        engine.import_all_sources()
        engine.extract_all_features()
        engine.mine_all_genre_patterns()
        print("\n流水线完成！现在可以使用 'recommend' 命令获取策略推荐")
    
    elif cmd == "recommend":
        genre = sys.argv[2] if len(sys.argv) > 2 else "玄幻"
        chapter = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        platform = sys.argv[4] if len(sys.argv) > 4 else ""
        
        strategy = engine.recommend_strategy(genre, chapter, platform)
        
        if strategy.get("sample_count", 0) == 0:
            print(f"\n{genre}类型暂无足够数据，使用通用策略")
        else:
            print(f"\n{'='*50}")
            print(f"  创作策略推荐")
            print(f"{'='*50}")
            print(f"  类型: {genre} | 章节: 第{chapter}章")
            print(f"  样本量: {strategy['sample_count']} | 置信度: {strategy['confidence']:.0%}")
            print(f"  {'-'*40}")
            
            rec = strategy["recommendations"]
            print(f"  句法: 均句长{rec['sentence']['avg_len']:.0f}字")
            print(f"  对话: {rec['dialogue']['ratio']*100:.0f}%")
            print(f"  钩子: {rec['hook']['type']} (分布: {rec['hook']['distribution']})")
            print(f"  情绪: 正向{rec['emotion']['pos_ratio']*100:.0f}%")
            print(f"  叙事: {rec['narrative']['focus']}")
            print(f"  {'-'*40}")
            print(f"  洞察: {strategy['insight']}")
            print(f"  {'-'*40}")
            print(f"  执行建议:")
            for tip in strategy.get("actionable_tips", []):
                print(f"    → {tip}")
            
            if strategy.get("reference_books"):
                refs = "、".join([f"《{rb['title']}》" for rb in strategy["reference_books"][:5]])
                print(f"\n  参考作品: {refs}")
    
    elif cmd == "stats":
        conn = engine._get_conn()
        books = conn.execute("SELECT COUNT(*) as cnt FROM books").fetchone()["cnt"]
        chapters = conn.execute("SELECT COUNT(*) as cnt FROM chapters").fetchone()["cnt"]
        features = conn.execute("SELECT COUNT(*) as cnt FROM chapter_features").fetchone()["cnt"]
        patterns = conn.execute("SELECT COUNT(*) as cnt FROM genre_patterns").fetchone()["cnt"]
        genres = conn.execute("SELECT genre, COUNT(*) as cnt FROM books GROUP BY genre ORDER BY cnt DESC").fetchall()
        conn.close()
        
        print(f"\n数据库统计")
        print(f"{'='*40}")
        print(f"  书籍: {books}本")
        print(f"  章节: {chapters}章")
        print(f"  特征: {features}个（已分析）")
        print(f"  模式: {patterns}个（已挖掘）")
        print(f"  {'-'*40}")
        print(f"  类型分布:")
        for g in genres:
            bar = "█" * min(30, g["cnt"] // 2)
            print(f"    {g['genre']:　<8s} {bar} {g['cnt']}本")
    
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
