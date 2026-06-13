"""
盘古AI - 统一数据库管理

之前: db_manager.py / unified_db_manager.py / workshop_db_manager.py 三套各管各的
现在: 一个 DatabaseManager 统一管理所有连接和表操作
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from .config import get_config

BASE_DIR = get_config().base_dir
DB_PATH = BASE_DIR / "knowledge" / "novel_reference.db"


class DatabaseManager:
    """
    统一数据库管理器。
    借鉴 Go 的 sql.DB 思想：连接池化、操作事务化、错误显式返回。
    """

    def __init__(self, db_path: Path = None):
        self._db_path = db_path or DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（懒初始化）"""
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句"""
        conn = self._get_conn()
        return conn.execute(sql, params)

    def commit(self):
        """提交事务"""
        if self._conn:
            self._conn.commit()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """查询单行"""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """查询多行"""
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    # ============ 兼容层 ============
    # 提供与旧版 db_manager / workshop_db_manager / unified_db_manager 兼容的接口
    # 逐步迁移后可删除

    def init_tables(self):
        """初始化所有必要的表"""
        conn = self._get_conn()

        # T02: Schema migration - 检测并迁移旧版表结构（在CREATE之前重命名旧表）
        self._migrate_t02_tables(conn)

        # 参考库表
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS novels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                genre TEXT,
                file_path TEXT,
                chapter_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                novel_id INTEGER REFERENCES novels(id),
                chapter_num INTEGER,
                title TEXT,
                content TEXT,
                word_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS workshop_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                chapter_num INTEGER,
                title TEXT,
                mode TEXT DEFAULT 'general',
                platform TEXT DEFAULT 'qimao',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS workshop_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES workshop_tasks(id),
                workshop_num INTEGER,
                input_text TEXT,
                output_text TEXT,
                model TEXT,
                temperature REAL DEFAULT 0.7,
                output_length INTEGER DEFAULT 0,
                elapsed_time REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS chapter_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES workshop_tasks(id),
                chapter_title TEXT,
                content TEXT,
                is_final INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- State↔DB 同步表 (T02-1)
            CREATE TABLE IF NOT EXISTS character_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                current_state TEXT DEFAULT '',
                location TEXT DEFAULT '',
                last_chapter INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_name, name)
            );

            CREATE TABLE IF NOT EXISTS foreshadowing_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                planted_ch INTEGER DEFAULT 0,
                resolved_ch INTEGER,
                priority INTEGER DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_name, thread_id)
            );

            CREATE TABLE IF NOT EXISTS setting_constraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                rule TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                status TEXT DEFAULT 'locked',
                source_chapter INTEGER DEFAULT 0,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                content TEXT DEFAULT '',
                triggers TEXT DEFAULT '[]',
                priority INTEGER DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_name, name)
            );

            CREATE TABLE IF NOT EXISTS ref_chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                chapter_num INTEGER NOT NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                word_count INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_name, chapter_num)
            );
        """)
        self.commit()

        # T02: 迁移旧表数据到新表（在新表创建后执行）
        self._migrate_t02_data(conn)
        self.commit()

    # ============ T02 Schema Migration ============

    def _migrate_t02_tables(self, conn):
        """T02: 迁移旧版5张表到新schema（rename + recreate + migrate）"""
        migrations = {
            'character_states': {
                'old_check_col': 'project_id',  # 旧schema有此列，新schema没有
            },
            'foreshadowing_threads': {
                'old_check_col': 'project_id',
            },
            'setting_constraints': {
                'old_check_col': 'project_id',
            },
            'knowledge_entries': {
                'old_check_col': 'entry_type',  # 旧schema独有列
            },
            'ref_chapters': {
                'old_check_col': 'book_id',  # 旧schema独有列
            },
        }

        for table, info in migrations.items():
            # 检查表是否存在
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not exists:
                continue

            # 检查是否有旧schema标志列
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if info['old_check_col'] not in cols:
                continue  # 已经是新schema，跳过

            # 旧schema → 重命名
            old_table = f"{table}_old"
            try:
                conn.execute(f"DROP TABLE IF EXISTS {old_table}")
                conn.execute(f"ALTER TABLE {table} RENAME TO {old_table}")
                print(f"[DB Migration] {table}: 旧表重命名为 {old_table}")
            except Exception as e:
                print(f"[DB Migration] {table}: 重命名失败 ({e})，跳过")
                conn.execute(f"DROP TABLE IF EXISTS {old_table}")
                continue

        self.commit()
        # 新表将由下面的 executescript(CREATE TABLE IF NOT EXISTS) 创建
        # 迁移数据在新表创建后执行

    def _migrate_t02_data(self, conn):
        """T02: 从 _old 表迁移数据到新表"""
        # 检查辅助表是否存在及其列名
        has_projects = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        ).fetchone() is not None
        has_books = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='books'"
        ).fetchone() is not None

        # 检测 projects 表的项目名列名（可能是 name 或 title）
        projects_name_col = "name"
        if has_projects:
            proj_cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
            if "name" not in proj_cols and "title" in proj_cols:
                projects_name_col = "title"

        # character_states
        if has_projects:
            cs_sql = f"""
                INSERT OR IGNORE INTO character_states (project_name, name, role, current_state, location, last_chapter, updated_at)
                SELECT
                    COALESCE((SELECT p.{projects_name_col} FROM projects p WHERE p.id = cs.project_id), 'default'),
                    cs.character_name, '', cs.current_mood, cs.current_location,
                    cs.last_updated_chapter, cs.updated_at
                FROM character_states_old cs
            """
        else:
            cs_sql = """
                INSERT OR IGNORE INTO character_states (project_name, name, role, current_state, location, last_chapter, updated_at)
                SELECT 'default', cs.character_name, '', cs.current_mood, cs.current_location,
                    cs.last_updated_chapter, cs.updated_at
                FROM character_states_old cs
            """

        # foreshadowing_threads
        if has_projects:
            ft_sql = f"""
                INSERT OR IGNORE INTO foreshadowing_threads (project_name, thread_id, description, status, planted_ch, resolved_ch, priority, updated_at)
                SELECT
                    COALESCE((SELECT p.{projects_name_col} FROM projects p WHERE p.id = ft.project_id), 'default'),
                    'thread_' || ft.id, ft.description, ft.status, ft.planted_in_chapter,
                    NULL, 5, ft.updated_at
                FROM foreshadowing_threads_old ft
            """
        else:
            ft_sql = """
                INSERT OR IGNORE INTO foreshadowing_threads (project_name, thread_id, description, status, planted_ch, resolved_ch, priority, updated_at)
                SELECT 'default', 'thread_' || ft.id, ft.description, ft.status, ft.planted_in_chapter,
                    NULL, 5, ft.updated_at
                FROM foreshadowing_threads_old ft
            """

        # setting_constraints
        if has_projects:
            sc_sql = f"""
                INSERT OR IGNORE INTO setting_constraints (project_name, rule, category, status, source_chapter, locked_at)
                SELECT
                    COALESCE((SELECT p.{projects_name_col} FROM projects p WHERE p.id = sc.project_id), 'default'),
                    sc.description, sc.constraint_type,
                    CASE WHEN sc.is_active = 1 THEN 'locked' ELSE 'archived' END,
                    0, sc.created_at
                FROM setting_constraints_old sc
            """
        else:
            sc_sql = """
                INSERT OR IGNORE INTO setting_constraints (project_name, rule, category, status, source_chapter, locked_at)
                SELECT 'default', sc.description, sc.constraint_type,
                    CASE WHEN sc.is_active = 1 THEN 'locked' ELSE 'archived' END,
                    0, sc.created_at
                FROM setting_constraints_old sc
            """

        # knowledge_entries (无 project_id 引用)
        ke_sql = """
            INSERT OR IGNORE INTO knowledge_entries (project_name, name, category, content, triggers, priority, updated_at)
            SELECT 'default', ke.title, COALESCE(ke.entry_type, 'general'), ke.content, '[]', 5, ke.updated_at
            FROM knowledge_entries_old ke
        """

        # ref_chapters — books表没有project_id，无法关联projects，直接用'default'
        rc_sql = """
            INSERT OR IGNORE INTO ref_chapters (project_name, chapter_num, title, content, word_count, summary, created_at)
            SELECT 'default', rc.chapter_num, rc.title, rc.content, rc.word_count,
                COALESCE(rc.analysis_result, ''), rc.created_at
            FROM ref_chapters_old rc
        """

        migration_sql = {
            'character_states': cs_sql,
            'foreshadowing_threads': ft_sql,
            'setting_constraints': sc_sql,
            'knowledge_entries': ke_sql,
            'ref_chapters': rc_sql,
        }

        for table, sql in migration_sql.items():
            old_table = f"{table}_old"
            # 检查旧表是否存在
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (old_table,)
            ).fetchone()
            if not exists:
                continue

            try:
                conn.execute(sql)
                migrated = conn.execute("SELECT changes()").fetchone()[0]
                print(f"[DB Migration] {table}: 迁移了 {migrated} 条记录")

                # 迁移成功后删除旧表
                conn.execute(f"DROP TABLE {old_table}")
                print(f"[DB Migration] {table}: 旧表已删除")
            except Exception as e:
                print(f"[DB Migration] {table}: 数据迁移失败 ({e})，保留旧表 {old_table}")
                # 不删除旧表，保留数据安全


# ============ 全局便捷函数 ============

_instance: Optional[DatabaseManager] = None


def get_db(db_path: Path = None) -> DatabaseManager:
    """获取全局数据库管理器（懒初始化）"""
    global _instance
    if _instance is None:
        _instance = DatabaseManager(db_path)
        _instance.init_tables()
    return _instance
