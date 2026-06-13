-- ============================================================
-- 盘古AI创作引擎数据库架构 v3
-- 核心理念：从被动仓库 → 主动创作引擎
-- 
-- 关键改进：
-- 1. source_catalog: 素材来源追溯（网络文学/科幻/豆瓣等）
-- 2. chapter_features: 每章的多维特征（钩子/情绪/对话率等）
-- 3. genre_patterns: 跨书的模式挖掘（类型×章节位置→最优策略）
-- 4. writing_strategies: 预计算的可执行写作策略
-- ============================================================

-- 素材来源目录
CREATE TABLE IF NOT EXISTS source_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,          -- "网络文学20年十大玄幻", "世界科幻大师丛书"
    source_type TEXT NOT NULL,          -- "web_novel" / "sci_fi" / "douban" / "qidian_bestseller"
    root_path TEXT NOT NULL,            -- 素材库根路径
    book_count INTEGER DEFAULT 0,
    imported_count INTEGER DEFAULT 0,
    last_imported_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 书籍表（增强版：追溯来源+评级）
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT DEFAULT '',
    source_id INTEGER,                  -- FK → source_catalog
    genre TEXT NOT NULL,                -- 都市/玄幻/仙侠/科幻/历史/悬疑...
    sub_genre TEXT DEFAULT '',          -- 都市异能/古典仙侠/硬科幻...
    platform TEXT DEFAULT '',           -- 起点/番茄/七猫/豆瓣
    ranking INTEGER DEFAULT 0,          -- 排名（如果是爆款）
    rating REAL DEFAULT 0.0,            -- 豆瓣评分（如有）
    rating_count INTEGER DEFAULT 0,     -- 评分数
    complete_status TEXT DEFAULT '',     -- 完本/连载
    word_count_total INTEGER DEFAULT 0, -- 全书总字数
    chapter_count INTEGER DEFAULT 0,    -- 总章数
    imported_chapters INTEGER DEFAULT 0,-- 已导入章节数
    fingerprint_json TEXT DEFAULT '',    -- 全书风格指纹JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES source_catalog(id)
);

-- 章节表
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT DEFAULT '',
    content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    is_first_chapter INTEGER DEFAULT 0, -- 是否第一章
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id),
    UNIQUE(book_id, chapter_num)
);

-- ★ 核心新表：章节多维特征 ★
-- 每章提取一次，支持跨书跨类型模式挖掘
CREATE TABLE IF NOT EXISTS chapter_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL UNIQUE,
    book_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    chapter_position TEXT DEFAULT '',   -- opening(1-3) / early(4-10) / mid(11-30) / late(31+)
    
    -- 句法特征
    avg_sentence_len REAL DEFAULT 0,
    sentence_len_variance REAL DEFAULT 0,
    avg_paragraph_len REAL DEFAULT 0,
    
    -- 对话特征
    dialogue_ratio REAL DEFAULT 0,      -- 对话占比
    avg_dialogue_len REAL DEFAULT 0,    -- 平均对话长度
    speaker_count INTEGER DEFAULT 0,    -- 说话人数量
    
    -- 情绪特征
    pos_sentiment_ratio REAL DEFAULT 0,  -- 正向情绪句占比
    neg_sentiment_ratio REAL DEFAULT 0,  -- 负向情绪句占比
    emotion_variance REAL DEFAULT 0,     -- 情绪波动方差
    high_intensity_ratio REAL DEFAULT 0, -- 高强度句占比
    emotional_arc_json TEXT DEFAULT '',  -- JSON: 情绪曲线采样点
    
    -- 钩子特征
    hook_type TEXT DEFAULT '',           -- suspense/threat/reversal/expectation/emotional
    hook_strength REAL DEFAULT 0,        -- 0-100
    hook_emotion_cliff REAL DEFAULT 0,   -- 结尾情绪跳变幅度
    
    -- 事件特征
    event_count INTEGER DEFAULT 0,       -- 可识别的事件数
    action_density REAL DEFAULT 0,       -- 动作词密度（每千字）
    description_density REAL DEFAULT 0,  -- 描写词密度
    
    -- 元数据
    extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    extractor_version TEXT DEFAULT 'v1',
    FOREIGN KEY (chapter_id) REFERENCES chapters(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

-- ★ 核心新表：类型创作模式 ★
-- 跨书聚合：类型×章节位置→最优策略
CREATE TABLE IF NOT EXISTS genre_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genre TEXT NOT NULL,                 -- 类型
    platform TEXT DEFAULT '',            -- 平台（可选过滤）
    chapter_position TEXT NOT NULL,      -- opening/early/mid/late
    
    -- 聚合统计
    sample_count INTEGER DEFAULT 0,     -- 样本量
    
    -- 推荐句法参数
    rec_avg_sentence_len REAL DEFAULT 0,
    rec_dialogue_ratio REAL DEFAULT 0,
    
    -- 推荐钩子策略
    rec_hook_type TEXT DEFAULT '',              -- 最优钩子类型
    hook_type_distribution TEXT DEFAULT '',     -- JSON: {"suspense": 0.3, "expectation": 0.5, ...}
    
    -- 推荐情绪策略
    rec_emotion_arc TEXT DEFAULT '',            -- 推荐情绪曲线形状描述
    rec_pos_ratio REAL DEFAULT 0,
    rec_emotion_variance REAL DEFAULT 0,
    
    -- 推荐叙事策略
    rec_narrative_focus TEXT DEFAULT '',  -- action/dialogue/description
    rec_event_count REAL DEFAULT 0,       -- 推荐事件密度
    
    -- 关键洞察
    insight TEXT DEFAULT '',              -- 人类可读的模式发现
    confidence REAL DEFAULT 0.0,          -- 置信度
    
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(genre, platform, chapter_position)
);

-- ★ 核心新表：写作策略缓存 ★
-- 主动推荐引擎的输出，写前查询
CREATE TABLE IF NOT EXISTS writing_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genre TEXT NOT NULL,
    platform TEXT DEFAULT '',
    chapter_num INTEGER NOT NULL,        -- 目标章节号
    
    -- 推荐策略（结构化）
    strategy_json TEXT NOT NULL,          -- 完整策略JSON
    
    -- 来源
    pattern_id INTEGER,                  -- FK → genre_patterns
    reference_books TEXT DEFAULT '',     -- 参考的书籍列表
    reference_chapters TEXT DEFAULT '',   -- 参考的章节列表
    sample_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(genre, platform, chapter_num)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
CREATE INDEX IF NOT EXISTS idx_books_source ON books(source_id);
CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_chapter_features_book ON chapter_features(book_id);
CREATE INDEX IF NOT EXISTS idx_chapter_features_position ON chapter_features(chapter_position);
CREATE INDEX IF NOT EXISTS idx_genre_patterns_genre_pos ON genre_patterns(genre, chapter_position);
CREATE INDEX IF NOT EXISTS idx_writing_strategies_lookup ON writing_strategies(genre, platform, chapter_num);
