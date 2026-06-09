-- 盘古AI小说参考库数据库架构
-- 用于存储、分析和管理网文小说参考资料

-- 书籍表：存储小说基本信息
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    platform TEXT,                -- 发布平台：fanqie, qidian, qimao, jinjiang
    genre TEXT,                   -- 题材类型
    mode TEXT,                    -- 创作模式：healing_life, urban_power, female_solo, etc.
    word_count INTEGER,           -- 总字数
    chapter_count INTEGER,        -- 章节数
    status TEXT DEFAULT 'ongoing',-- 状态：ongoing, completed
    rating REAL,                  -- 评分（1-5）
    is_reference BOOLEAN DEFAULT 0, -- 是否作为参考样本
    notes TEXT,                   -- 备注
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 章节表：存储单章内容
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER,
    is_opening BOOLEAN DEFAULT 0,  -- 是否是开篇章节（第1-3章）
    is_ending BOOLEAN DEFAULT 0,   -- 是否是结尾章节
    hook_strength INTEGER,         -- 钩子强度评分
    analysis_result TEXT,          -- 分析结果JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- 风格标签表：风格分类体系
CREATE TABLE IF NOT EXISTS style_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,                 -- 分类：emotion, rhythm, narrative, etc.
    description TEXT,
    color TEXT,                    -- 显示颜色
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 书籍风格关联表
CREATE TABLE IF NOT EXISTS book_style_tags (
    book_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    confidence REAL DEFAULT 1.0,   -- 置信度
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES style_tags(id) ON DELETE CASCADE
);

-- 情绪锚点表：分析到的情绪触发器
CREATE TABLE IF NOT EXISTS emotion_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    position INTEGER,              -- 在文中的位置
    emotion_type TEXT NOT NULL,    -- 情绪类型：anger, joy, surprise, etc.
    intensity INTEGER,             -- 强度 1-10
    description TEXT,
    quote TEXT,                    -- 原文引用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- 钩子表：分析到的章节钩子
CREATE TABLE IF NOT EXISTS hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    hook_type TEXT NOT NULL,       -- 钩子类型
    position TEXT,                 -- 位置：opening, middle, ending
    strength INTEGER,              -- 强度 1-10
    description TEXT,
    quote TEXT,                    -- 原文引用
    effect_analysis TEXT,          -- 效果分析
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- 写作技巧表：提取的写作手法
CREATE TABLE IF NOT EXISTS writing_techniques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER,
    book_id INTEGER,
    technique_type TEXT NOT NULL,  -- 技巧类型
    name TEXT NOT NULL,
    description TEXT,
    example_text TEXT,             -- 示例文本
    usage_context TEXT,            -- 使用场景
    effectiveness_score INTEGER,   -- 效果评分
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_books_platform ON books(platform);
CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
CREATE INDEX IF NOT EXISTS idx_books_mode ON books(mode);
CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_hooks_chapter ON hooks(chapter_id);
CREATE INDEX IF NOT EXISTS idx_emotion_chapter ON emotion_anchors(chapter_id);
