-- =============================================
-- 盘古AI系统 - 统一数据库Schema
-- 将所有JSON配置迁移到数据库，提升效率
-- =============================================

-- =============================================
-- 1. 车间执行记录表（先创建，被其他表引用）
-- =============================================
CREATE TABLE IF NOT EXISTS workshop_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT,
    mode TEXT DEFAULT 'general',
    genre TEXT,
    platform TEXT DEFAULT 'qimao',
    word_count INTEGER DEFAULT 2000,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workshop_tasks_project ON workshop_tasks(project_name);
CREATE INDEX IF NOT EXISTS idx_workshop_tasks_status ON workshop_tasks(status);

CREATE TABLE IF NOT EXISTS workshop_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    workshop_id INTEGER NOT NULL,
    workshop_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    input_text TEXT,
    output_text TEXT,
    model_used TEXT,
    temperature REAL,
    tokens_used INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds REAL,
    error_message TEXT,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workshop_steps_task ON workshop_steps(task_id);

CREATE TABLE IF NOT EXISTS task_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    key_name TEXT NOT NULL,
    value_type TEXT NOT NULL,
    string_value TEXT,
    int_value INTEGER,
    bool_value INTEGER,
    json_value TEXT,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE,
    UNIQUE(task_id, key_name)
);

CREATE TABLE IF NOT EXISTS rag_retrievals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    workshop_id INTEGER NOT NULL,
    query TEXT,
    top_k INTEGER DEFAULT 3,
    retrieved_count INTEGER DEFAULT 0,
    results_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rag_task ON rag_retrievals(task_id);

CREATE TABLE IF NOT EXISTS chapter_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    chapter_title TEXT,
    content TEXT,
    word_count INTEGER,
    version INTEGER DEFAULT 1,
    is_final INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chapter_outputs_task ON chapter_outputs(task_id);

-- =============================================
-- 2. 模式配置表 (替代 modes/*.json)
-- =============================================
CREATE TABLE IF NOT EXISTS modes (
    mode_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    target_platforms TEXT,
    core_principle TEXT,
    chapter_structure TEXT,
    success_metrics TEXT,
    is_active BOOLEAN DEFAULT 1,
    version TEXT DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mode_workshop_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode_id TEXT NOT NULL,
    workshop_id INTEGER NOT NULL,
    config_key TEXT NOT NULL,
    config_value TEXT NOT NULL,
    FOREIGN KEY (mode_id) REFERENCES modes(mode_id) ON DELETE CASCADE,
    UNIQUE(mode_id, workshop_id, config_key)
);

-- =============================================
-- 3. 平台配置表 (替代 platform_writing_profiles.json)
-- =============================================
CREATE TABLE IF NOT EXISTS platforms (
    platform_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    core_logic TEXT,
    key_metric TEXT,
    chapter_length TEXT,
    opening_rules TEXT,
    paragraph_rules TEXT,
    sentence_rules TEXT,
    dialogue_rules TEXT,
    scene_rules TEXT,
    emotion_delivery TEXT,
    satisfaction_points TEXT,
    character_rules TEXT,
    taboo TEXT,
    ai_trace_high_risk TEXT,
    is_active BOOLEAN DEFAULT 1,
    version TEXT DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 4. 参考库表 (来自 db_schema.sql)
-- =============================================
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ref_chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER,
    is_opening BOOLEAN DEFAULT 0,
    is_ending BOOLEAN DEFAULT 0,
    hook_strength INTEGER,
    analysis_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS style_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    description TEXT,
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS book_style_tags (
    book_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES style_tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS emotion_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    position INTEGER,
    emotion_type TEXT NOT NULL,
    intensity INTEGER,
    description TEXT,
    quote TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES ref_chapters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    hook_type TEXT NOT NULL,
    position TEXT,
    strength INTEGER,
    description TEXT,
    quote TEXT,
    effect_analysis TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES ref_chapters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS writing_techniques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER,
    book_id INTEGER,
    technique_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    example_text TEXT,
    usage_context TEXT,
    effectiveness_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 5. 项目管理表 (替代 projects/*/state.json)
-- =============================================
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    project_dir TEXT NOT NULL UNIQUE,
    mode_id TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    target_words INTEGER DEFAULT 400000,
    target_chapters INTEGER DEFAULT 200,
    current_chapter INTEGER DEFAULT 0,
    total_words INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mode_id) REFERENCES modes(mode_id),
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id)
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_platform ON projects(platform_id);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at);

-- =============================================
-- 6. 章节元数据表 (替代 state.json chapter_meta)
-- =============================================
CREATE TABLE IF NOT EXISTS project_chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT,
    task TEXT,
    word_count INTEGER DEFAULT 0,
    ai_generated BOOLEAN DEFAULT 0,
    workshop_task_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (workshop_task_id) REFERENCES workshop_tasks(id),
    UNIQUE(project_id, chapter_num)
);

CREATE INDEX IF NOT EXISTS idx_project_chapters_project ON project_chapters(project_id);
CREATE INDEX IF NOT EXISTS idx_project_chapters_num ON project_chapters(chapter_num);

-- =============================================
-- 7. 长篇一致性表
-- =============================================
CREATE TABLE IF NOT EXISTS foreshadowing_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    planted_in_chapter INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    hints TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_foreshadowing_project ON foreshadowing_threads(project_id);
CREATE INDEX IF NOT EXISTS idx_foreshadowing_status ON foreshadowing_threads(status);

CREATE TABLE IF NOT EXISTS character_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    character_name TEXT NOT NULL,
    current_location TEXT,
    current_mood TEXT,
    relationships TEXT,
    last_updated_chapter INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, character_name)
);

CREATE INDEX IF NOT EXISTS idx_characters_project ON character_states(project_id);

CREATE TABLE IF NOT EXISTS setting_constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    constraint_type TEXT NOT NULL,
    description TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_settings_project ON setting_constraints(project_id);

-- =============================================
-- 8. 知识条目表
-- =============================================
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_book_id INTEGER,
    tags TEXT,
    embedding BLOB,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_book_id) REFERENCES books(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_entries(source_book_id);

-- =============================================
-- 索引优化
-- =============================================
CREATE INDEX IF NOT EXISTS idx_books_platform ON books(platform);
CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
CREATE INDEX IF NOT EXISTS idx_books_mode ON books(mode);
CREATE INDEX IF NOT EXISTS idx_ref_chapters_book ON ref_chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_hooks_chapter ON hooks(chapter_id);
CREATE INDEX IF NOT EXISTS idx_emotion_chapter ON emotion_anchors(chapter_id);

-- =============================================
-- 视图：项目进度概览
-- =============================================
CREATE VIEW IF NOT EXISTS project_progress_view AS
SELECT 
    p.id,
    p.title,
    m.name as mode_name,
    pf.name as platform_name,
    p.current_chapter,
    p.target_chapters,
    p.total_words,
    p.target_words,
    p.status,
    COUNT(DISTINCT c.id) as total_chapters_written,
    ROUND(p.current_chapter * 100.0 / p.target_chapters, 1) as progress_percent
FROM projects p
LEFT JOIN modes m ON p.mode_id = m.mode_id
LEFT JOIN platforms pf ON p.platform_id = pf.platform_id
LEFT JOIN project_chapters c ON p.id = c.project_id
GROUP BY p.id;

-- =============================================
-- 视图：平台配置概览
-- =============================================
CREATE VIEW IF NOT EXISTS platform_overview_view AS
SELECT 
    platform_id,
    name,
    core_logic,
    key_metric,
    chapter_length,
    is_active,
    version,
    updated_at
FROM platforms;

-- =============================================
-- 视图：模式配置概览
-- =============================================
CREATE VIEW IF NOT EXISTS mode_overview_view AS
SELECT 
    m.mode_id,
    m.name,
    m.description,
    m.target_platforms,
    COUNT(DISTINCT mwc.id) as workshop_config_count,
    m.is_active,
    m.version,
    m.updated_at
FROM modes m
LEFT JOIN mode_workshop_configs mwc ON m.mode_id = mwc.mode_id
GROUP BY m.mode_id;
