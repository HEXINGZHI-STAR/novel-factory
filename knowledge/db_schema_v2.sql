-- 盘古AI小说创作系统 - V2数据库架构
-- 增加车间流水线执行记录、项目状态持久化、断点续传支持

-- =======================================
-- 项目管理表
-- =======================================
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    genre TEXT,
    platform TEXT DEFAULT 'qimao',
    mode TEXT DEFAULT 'general',
    target_words INTEGER DEFAULT 400000,
    target_chapters INTEGER DEFAULT 200,
    current_chapter INTEGER DEFAULT 1,
    total_words_written INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =======================================
-- 车间执行任务表
-- =======================================
CREATE TABLE IF NOT EXISTS workshop_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    task_type TEXT NOT NULL, -- w0, w1, w2, w3, w4
    task_desc TEXT,
    input_data TEXT, -- JSON格式的输入数据
    output_data TEXT, -- JSON格式的输出数据
    status TEXT DEFAULT 'pending', -- pending, running, success, failed
    model_used TEXT,
    tokens_used INTEGER DEFAULT 0,
    start_time DATETIME,
    end_time DATETIME,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =======================================
-- 项目状态快照表
-- =======================================
CREATE TABLE IF NOT EXISTS project_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    snapshot_type TEXT NOT NULL, -- w0, w1, w2, w3, w4, final
    hot_storage TEXT, -- 热库内容（JSON）
    cold_storage TEXT, -- 冷库内容（JSON）
    chapter_content TEXT, -- 章节内容
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =======================================
-- 风格参考库缓存表（优化RAG）
-- =======================================
CREATE TABLE IF NOT EXISTS style_reference_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    genre TEXT,
    platform TEXT,
    query TEXT NOT NULL,
    reference_data TEXT NOT NULL, -- JSON格式的参考数据
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =======================================
-- 索引优化（大幅提升查询效率）
-- =======================================
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(project_name);
CREATE INDEX IF NOT EXISTS idx_workshop_tasks_project_chapter ON workshop_tasks(project_id, chapter_num);
CREATE INDEX IF NOT EXISTS idx_workshop_tasks_status ON workshop_tasks(status);
CREATE INDEX IF NOT EXISTS idx_snapshots_project_chapter_type ON project_snapshots(project_id, chapter_num, snapshot_type);
CREATE INDEX IF NOT EXISTS idx_style_cache_query ON style_reference_cache(query);

-- =======================================
-- 保持原有小说参考库表不变
-- =======================================

-- 书籍表
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    platform TEXT,
    genre TEXT,
    mode TEXT,
    word_count INTEGER,
    chapter_count INTEGER,
    status TEXT DEFAULT 'ongoing',
    rating REAL,
    is_reference BOOLEAN DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 章节表
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER,
    is_opening BOOLEAN DEFAULT 0,
    is_ending BOOLEAN DEFAULT