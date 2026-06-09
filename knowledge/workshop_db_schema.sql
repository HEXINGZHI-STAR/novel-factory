-- 盘古AI车间执行记录数据库架构
-- 用于存储五车间流水线的完整执行过程，支持断点续传和回放

-- =============================================
-- 任务表：存储单个创作任务
-- =============================================
CREATE TABLE IF NOT EXISTS workshop_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT NOT NULL,
    mode TEXT DEFAULT 'general',
    genre TEXT,
    platform TEXT DEFAULT 'qimao',
    word_count INTEGER DEFAULT 2000,
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed, paused
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error_message TEXT
);

-- =============================================
-- 车间步骤表：存储每个车间的执行记录
-- =============================================
CREATE TABLE IF NOT EXISTS workshop_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    workshop_id INTEGER NOT NULL,  -- 0-4, W0-W4
    workshop_name TEXT NOT NULL,   -- w0_anchor, w1_setup, etc.
    status TEXT DEFAULT 'pending', -- pending, running, completed, failed, skipped
    input_text TEXT,               -- 输入给该车间的内容
    output_text TEXT,              -- 车间输出内容
    model_used TEXT,               -- 使用的模型
    temperature REAL,              -- 温度参数
    tokens_used INTEGER,           -- 消耗的Token数
    start_time DATETIME,
    end_time DATETIME,
    duration_seconds REAL,         -- 执行耗时（秒）
    error_message TEXT,            -- 错误信息（如果失败）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

-- =============================================
-- 任务参数表：存储任务的输入参数
-- =============================================
CREATE TABLE IF NOT EXISTS task_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    key_name TEXT NOT NULL,
    value_type TEXT NOT NULL,      -- string, int, bool, json
    string_value TEXT,
    int_value INTEGER,
    bool_value INTEGER,
    json_value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE,
    UNIQUE(task_id, key_name)
);

-- =============================================
-- RAG检索记录表：存储每次RAG检索的结果
-- =============================================
CREATE TABLE IF NOT EXISTS rag_retrievals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    workshop_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    top_k INTEGER DEFAULT 3,
    retrieved_count INTEGER,
    results_json TEXT,            -- 检索结果的JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

-- =============================================
-- 输出存档表：存储最终章节内容
-- =============================================
CREATE TABLE IF NOT EXISTS chapter_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    chapter_title TEXT,
    content TEXT NOT NULL,
    word_count INTEGER,
    version INTEGER DEFAULT 1,
    is_final BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workshop_tasks(id) ON DELETE CASCADE
);

-- =============================================
-- 索引优化
-- =============================================
CREATE INDEX IF NOT EXISTS idx_tasks_project ON workshop_tasks(project_name);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON workshop_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON workshop_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_steps_task ON workshop_steps(task_id);
CREATE INDEX IF NOT EXISTS idx_steps_workshop ON workshop_steps(workshop_id);
CREATE INDEX IF NOT EXISTS idx_params_task ON task_parameters(task_id);
CREATE INDEX IF NOT EXISTS idx_rag_task ON rag_retrievals(task_id);
CREATE INDEX IF NOT EXISTS idx_outputs_task ON chapter_outputs(task_id);
