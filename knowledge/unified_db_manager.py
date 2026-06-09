#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
盘古AI系统 - 统一数据库管理器
整合所有配置和数据到单一数据库，大幅提升效率
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

class UnifiedDBManager:
    """统一数据库管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'novel_reference.db'
        self.db_path = db_path
        self._conn = None
        self._init_db()
    
    def _init_db(self):
        """初始化数据库结构"""
        schema_path = Path(__file__).parent / 'unified_db_schema.sql'
        if not schema_path.exists():
            print(f"警告：Schema文件不存在 {schema_path}")
            return
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        self._get_connection()
        self._conn.executescript(schema)
        self._conn.commit()
    
    def _get_connection(self):
        """获取数据库连接（保持连接）"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def _execute_query(self, query: str, params: tuple = None, commit: bool = True):
        """执行SQL查询"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if commit:
            conn.commit()
        return cursor
    
    # =============================================
    # 项目管理
    # =============================================
    
    def create_project(self, title: str, project_dir: str, mode_id: str, 
                      platform_id: str, target_words: int = 400000, 
                      target_chapters: int = 200) -> int:
        """创建新项目"""
        cursor = self._execute_query("""
            INSERT OR REPLACE INTO projects 
            (title, project_dir, mode_id, platform_id, target_words, target_chapters)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, project_dir, mode_id, platform_id, target_words, target_chapters))
        return cursor.lastrowid
    
    def get_project_by_dir(self, project_dir: str) -> Optional[Dict]:
        """通过项目目录获取项目"""
        cursor = self._execute_query("""
            SELECT * FROM projects WHERE project_dir = ?
        """, (project_dir,), commit=False)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_projects(self, status: Optional[str] = None) -> List[Dict]:
        """获取所有项目"""
        if status:
            cursor = self._execute_query("""
                SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC
            """, (status,), commit=False)
        else:
            cursor = self._execute_query("""
                SELECT * FROM projects ORDER BY updated_at DESC
            """, commit=False)
        return [dict(row) for row in cursor.fetchall()]
    
    def update_project_progress(self, project_id: int, current_chapter: int, 
                               total_words: int):
        """更新项目进度"""
        self._execute_query("""
            UPDATE projects 
            SET current_chapter = ?, total_words = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (current_chapter, total_words, project_id))
    
    def get_project_progress(self, project_id: int) -> Optional[Dict]:
        """获取项目进度（通过视图）"""
        cursor = self._execute_query("""
            SELECT * FROM project_progress_view WHERE id = ?
        """, (project_id,), commit=False)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # =============================================
    # 章节管理
    # =============================================
    
    def create_chapter(self, project_id: int, chapter_num: int, 
                      title: Optional[str] = None, task: Optional[str] = None,
                      ai_generated: bool = False, workshop_task_id: Optional[int] = None) -> int:
        """创建章节记录"""
        cursor = self._execute_query("""
            INSERT OR REPLACE INTO project_chapters 
            (project_id, chapter_num, title, task, ai_generated, workshop_task_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, chapter_num, title, task, 1 if ai_generated else 0, workshop_task_id))
        return cursor.lastrowid

    def get_chapters(self, project_id: int) -> List[Dict]:
        """获取项目的所有章节"""
        cursor = self._execute_query("""
            SELECT * FROM project_chapters WHERE project_id = ? ORDER BY chapter_num
        """, (project_id,), commit=False)
        return [dict(row) for row in cursor.fetchall()]

    def update_chapter_word_count(self, chapter_id: int, word_count: int):
        """更新章节字数"""
        self._execute_query("""
            UPDATE project_chapters 
            SET word_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (word_count, chapter_id))
    
    # =============================================
    # 模式配置管理
    # =============================================
    
    def import_mode_from_json(self, json_path: str):
        """从JSON文件导入模式配置"""
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"模式文件不存在: {json_path}")
            return False
        
        with open(json_path, 'r', encoding='utf-8') as f:
            mode_data = json.load(f)
        
        mode_id = mode_data.get('mode_id', json_path.stem)
        
        # 导入主模式配置
        self._execute_query("""
            INSERT OR REPLACE INTO modes 
            (mode_id, name, description, target_platforms, core_principle, 
             chapter_structure, success_metrics, is_active, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, '1.0')
        """, (
            mode_id,
            mode_data.get('name', mode_id),
            mode_data.get('description'),
            json.dumps(mode_data.get('target_platforms', [])),
            mode_data.get('core_principle'),
            json.dumps(mode_data.get('chapter_structure', {})),
            json.dumps(mode_data.get('success_metrics', {}))
        ))
        
        # 导入车间配置
        for workshop_id in range(5):
            workshop_key = f'w{workshop_id}_special'
            if workshop_key in mode_data:
                self._execute_query("""
                    INSERT OR REPLACE INTO mode_workshop_configs
                    (mode_id, workshop_id, config_key, config_value)
                    VALUES (?, ?, ?, ?)
                """, (
                    mode_id,
                    workshop_id,
                    workshop_key,
                    json.dumps(mode_data[workshop_key])
                ))
        
        print(f"[OK] 成功导入模式: {mode_id}")
        return True
    
    def get_mode(self, mode_id: str) -> Optional[Dict]:
        """获取模式配置"""
        cursor = self._execute_query("""
            SELECT * FROM modes WHERE mode_id = ?
        """, (mode_id,), commit=False)
        row = cursor.fetchone()
        if not row:
            return None
        
        mode_data = dict(row)
        
        # 解析JSON字段
        for key in ['target_platforms', 'chapter_structure', 'success_metrics']:
            if mode_data.get(key):
                try:
                    mode_data[key] = json.loads(mode_data[key])
                except:
                    mode_data[key] = None
        
        # 获取车间配置
        cursor = self._execute_query("""
            SELECT * FROM mode_workshop_configs WHERE mode_id = ?
        """, (mode_id,), commit=False)
        workshop_configs = {}
        for row in cursor.fetchall():
            row_dict = dict(row)
            try:
                workshop_configs[row_dict['config_key']] = json.loads(row_dict['config_value'])
            except:
                workshop_configs[row_dict['config_key']] = row_dict['config_value']
        
        mode_data['workshop_configs'] = workshop_configs
        return mode_data
    
    def get_all_modes(self) -> List[Dict]:
        """获取所有模式（通过视图）"""
        cursor = self._execute_query("""
            SELECT * FROM mode_overview_view WHERE is_active = 1 ORDER BY mode_id
        """, commit=False)
        modes = []
        for row in cursor.fetchall():
            mode_dict = dict(row)
            if mode_dict.get('target_platforms'):
                try:
                    mode_dict['target_platforms'] = json.loads(mode_dict['target_platforms'])
                except:
                    pass
            modes.append(mode_dict)
        return modes
    
    # =============================================
    # 平台配置管理
    # =============================================
    
    def import_platforms_from_json(self, json_path: str):
        """从JSON文件导入平台配置"""
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"平台文件不存在: {json_path}")
            return False
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        profiles = data.get('profiles', {})
        count = 0
        
        for platform_id, platform_data in profiles.items():
            self._execute_query("""
                INSERT OR REPLACE INTO platforms 
                (platform_id, name, core_logic, key_metric, chapter_length,
                 opening_rules, paragraph_rules, sentence_rules, dialogue_rules,
                 scene_rules, emotion_delivery, satisfaction_points, character_rules,
                 taboo, ai_trace_high_risk, is_active, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '1.0')
            """, (
                platform_id,
                platform_data.get('name', platform_id),
                platform_data.get('core_logic'),
                platform_data.get('key_metric'),
                platform_data.get('chapter_length'),
                json.dumps(platform_data.get('opening', {})),
                json.dumps(platform_data.get('paragraph_rules', {})),
                json.dumps(platform_data.get('sentence_rules', {})),
                json.dumps(platform_data.get('dialogue_rules', {})),
                json.dumps(platform_data.get('scene_rules', {})),
                json.dumps(platform_data.get('emotion_delivery', {})),
                json.dumps(platform_data.get('satisfaction_points', {})),
                json.dumps(platform_data.get('character_rules', {})),
                json.dumps(platform_data.get('taboo', [])),
                json.dumps(platform_data.get('ai_trace_high_risk', []))
            ))
            count += 1
        
        print(f"[OK] 成功导入 {count} 个平台配置")
        return True
    
    def get_platform(self, platform_id: str) -> Optional[Dict]:
        """获取平台配置"""
        cursor = self._execute_query("""
            SELECT * FROM platforms WHERE platform_id = ?
        """, (platform_id,), commit=False)
        row = cursor.fetchone()
        if not row:
            return None
        
        platform_data = dict(row)
        
        # 解析JSON字段
        json_fields = ['opening_rules', 'paragraph_rules', 'sentence_rules', 
                      'dialogue_rules', 'scene_rules', 'emotion_delivery', 
                      'satisfaction_points', 'character_rules', 'taboo', 'ai_trace_high_risk']
        
        for key in json_fields:
            if platform_data.get(key):
                try:
                    platform_data[key] = json.loads(platform_data[key])
                except:
                    platform_data[key] = None
        
        return platform_data
    
    def get_all_platforms(self) -> List[Dict]:
        """获取所有平台（通过视图）"""
        cursor = self._execute_query("""
            SELECT * FROM platform_overview_view WHERE is_active = 1 ORDER BY platform_id
        """, commit=False)
        return [dict(row) for row in cursor.fetchall()]
    
    # =============================================
    # 长篇一致性管理
    # =============================================
    
    def add_foreshadowing(self, project_id: int, description: str, 
                         planted_in_chapter: int, hints: Optional[List] = None):
        """添加伏笔"""
        self._execute_query("""
            INSERT INTO foreshadowing_threads
            (project_id, description, planted_in_chapter, hints, status)
            VALUES (?, ?, ?, ?, 'active')
        """, (
            project_id,
            description,
            planted_in_chapter,
            json.dumps(hints or [])
        ))
    
    def get_foreshadowing(self, project_id: int) -> List[Dict]:
        """获取项目的所有伏笔"""
        cursor = self._execute_query("""
            SELECT * FROM foreshadowing_threads WHERE project_id = ? ORDER BY planted_in_chapter
        """, (project_id,), commit=False)
        foreshadowings = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict.get('hints'):
                try:
                    row_dict['hints'] = json.loads(row_dict['hints'])
                except:
                    row_dict['hints'] = []
            foreshadowings.append(row_dict)
        return foreshadowings
    
    def add_character(self, project_id: int, character_name: str, 
                     current_location: Optional[str] = None, 
                     current_mood: Optional[str] = None, 
                     relationships: Optional[Dict] = None):
        """添加角色"""
        self._execute_query("""
            INSERT OR REPLACE INTO character_states
            (project_id, character_name, current_location, current_mood, relationships)
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            character_name,
            current_location,
            current_mood,
            json.dumps(relationships or {})
        ))
    
    def get_characters(self, project_id: int) -> List[Dict]:
        """获取项目的所有角色"""
        cursor = self._execute_query("""
            SELECT * FROM character_states WHERE project_id = ? ORDER BY character_name
        """, (project_id,), commit=False)
        characters = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict.get('relationships'):
                try:
                    row_dict['relationships'] = json.loads(row_dict['relationships'])
                except:
                    row_dict['relationships'] = {}
            characters.append(row_dict)
        return characters
    
    def add_setting_constraint(self, project_id: int, constraint_type: str, description: str):
        """添加设定约束"""
        self._execute_query("""
            INSERT INTO setting_constraints
            (project_id, constraint_type, description)
            VALUES (?, ?, ?)
        """, (project_id, constraint_type, description))
    
    def get_setting_constraints(self, project_id: int) -> List[Dict]:
        """获取项目的设定约束"""
        cursor = self._execute_query("""
            SELECT * FROM setting_constraints WHERE project_id = ? AND is_active = 1
        """, (project_id,), commit=False)
        return [dict(row) for row in cursor.fetchall()]
    
    # =============================================
    # 批量导入和迁移
    # =============================================
    
    def migrate_existing_projects(self, projects_dir: str):
        """迁移现有的项目JSON文件到数据库"""
        projects_dir = Path(projects_dir)
        if not projects_dir.exists():
            print(f"项目目录不存在: {projects_dir}")
            return 0
        
        count = 0
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            
            state_file = project_dir / 'state.json'
            if not state_file.exists():
                continue
            
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                project_info = state.get('project_info', {})
                progress = state.get('progress', {})
                chapter_meta = state.get('chapter_meta', {})
                
                # 创建项目
                title = project_info.get('title', project_dir.name)
                mode_id = project_info.get('genre', 'general')
                platform_id = project_info.get('platform', 'qimao')
                
                project_id = self.create_project(
                    title=title,
                    project_dir=str(project_dir),
                    mode_id=mode_id,
                    platform_id=platform_id,
                    target_words=project_info.get('target_words', 400000),
                    target_chapters=project_info.get('target_chapters', 200)
                )
                
                # 更新进度
                self.update_project_progress(
                    project_id,
                    progress.get('current_chapter', 0),
                    progress.get('total_words', 0)
                )
                
                # 导入章节
                for chapter_key, chapter_data in chapter_meta.items():
                    match = chapter_key.split('_')
                    if len(match) == 2 and match[0] == 'chapter':
                        chapter_num = int(match[1])
                        self.create_chapter(
                            project_id=project_id,
                            chapter_num=chapter_num,
                            title=f"第{chapter_num}章",
                            task=chapter_data.get('task'),
                            ai_generated=chapter_data.get('ai_generated', False)
                        )
                
                count += 1
                print(f"[OK] 迁移项目: {title}")
                
            except Exception as e:
                print(f"[ERROR] 迁移失败 {project_dir}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n[OK] 成功迁移 {count} 个项目")
        return count
    
    def get_stats(self) -> Dict:
        """获取数据库统计"""
        cursor = self._execute_query("SELECT COUNT(*) FROM projects", commit=False)
        total_projects = cursor.fetchone()[0]

        cursor = self._execute_query("SELECT COUNT(*) FROM project_chapters", commit=False)
        total_chapters = cursor.fetchone()[0]

        cursor = self._execute_query("SELECT COUNT(*) FROM modes WHERE is_active = 1", commit=False)
        total_modes = cursor.fetchone()[0]

        cursor = self._execute_query("SELECT COUNT(*) FROM platforms WHERE is_active = 1", commit=False)
        total_platforms = cursor.fetchone()[0]

        cursor = self._execute_query("SELECT COUNT(*) FROM workshop_tasks", commit=False)
        total_workshop_tasks = cursor.fetchone()[0]

        cursor = self._execute_query("SELECT COUNT(*) FROM books", commit=False)
        total_books = cursor.fetchone()[0]

        return {
            'total_projects': total_projects,
            'total_chapters': total_chapters,
            'total_modes': total_modes,
            'total_platforms': total_platforms,
            'total_workshop_tasks': total_workshop_tasks,
            'total_books': total_books
        }


def main():
    """测试数据库管理器"""
    db = UnifiedDBManager()

    print("=" * 60)
    print("盘古AI系统 - 统一数据库管理器")
    print("=" * 60)

    stats = db.get_stats()
    print(f"\n[统计] 数据库统计:")
    print(f"   项目数: {stats['total_projects']}")
    print(f"   章节数: {stats['total_chapters']}")
    print(f"   模式数: {stats['total_modes']}")
    print(f"   平台数: {stats['total_platforms']}")
    print(f"   车间任务: {stats['total_workshop_tasks']}")
    print(f"   参考书籍: {stats['total_books']}")

    print("\n[OK] 数据库初始化成功！")


if __name__ == '__main__':
    main()
