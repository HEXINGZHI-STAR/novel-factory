
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI车间执行记录数据库管理器
用于管理五车间流水线的完整执行过程，支持断点续传和回放
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime


class WorkshopDBManager:
    """车间执行记录数据库管理器"""
    
    WORKSHOP_NAMES = {
        0: 'w0_anchor',
        1: 'w1_setup',
        2: 'w2_draft',
        3: 'w3_qc',
        4: 'w4_polish'
    }
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent / 'novel_reference.db'
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库结构"""
        schema_path = Path(__file__).parent / 'workshop_db_schema.sql'
        if not schema_path.exists():
            print(u"警告：车间架构文件不存在 %s" % schema_path)
            return
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        conn = self._get_connection()
        conn.executescript(schema)
        conn.commit()
        conn.close()
    
    # ========== 任务管理 ==========
    def create_task(self, project_name, chapter_num, title, mode='general', genre=None, platform='qimao', word_count=2000):
        """创建新任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO workshop_tasks (project_name, chapter_num, title, mode, genre, platform, word_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (project_name, chapter_num, title, mode, genre, platform, word_count))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def get_task(self, task_id):
        """获取任务信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workshop_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_task_status(self, task_id, status, error_message=None):
        """更新任务状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status == 'completed':
            cursor.execute('''
                UPDATE workshop_tasks 
                SET status = ?, updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE id = ?
            ''', (status, error_message, task_id))
        else:
            cursor.execute('''
                UPDATE workshop_tasks 
                SET status = ?, updated_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE id = ?
            ''', (status, error_message, task_id))
        
        conn.commit()
        conn.close()
    
    def list_tasks(self, project_name=None, status=None, limit=100):
        """列出任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM workshop_tasks WHERE 1=1'
        params = []
        
        if project_name:
            query += ' AND project_name = ?'
            params.append(project_name)
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_pending_tasks(self, project_name=None):
        """获取待执行的任务"""
        return self.list_tasks(project_name, 'pending')
    
    # ========== 车间步骤管理 ==========
    def create_workshop_step(self, task_id, workshop_id, input_text=None):
        """创建车间步骤"""
        workshop_name = self.WORKSHOP_NAMES.get(workshop_id, 'w%d' % workshop_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO workshop_steps (task_id, workshop_id, workshop_name, status, input_text, start_time)
            VALUES (?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
        ''', (task_id, workshop_id, workshop_name, input_text))
        
        step_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return step_id
    
    def start_workshop_step(self, step_id):
        """开始执行车间步骤"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE workshop_steps 
            SET status = 'running', start_time = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (step_id,))
        
        conn.commit()
        conn.close()
    
    def complete_workshop_step(self, step_id, output_text, model_used, temperature, tokens_used, duration_seconds):
        """完成车间步骤"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE workshop_steps 
            SET status = 'completed', output_text = ?, model_used = ?, temperature = ?, 
                tokens_used = ?, end_time = CURRENT_TIMESTAMP, duration_seconds = ?
            WHERE id = ?
        ''', (output_text, model_used, temperature, tokens_used, duration_seconds, step_id))
        
        conn.commit()
        conn.close()
    
    def fail_workshop_step(self, step_id, error_message):
        """车间步骤失败"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE workshop_steps 
            SET status = 'failed', error_message = ?, end_time = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (error_message, step_id))
        
        conn.commit()
        conn.close()
    
    def get_workshop_steps(self, task_id):
        """获取任务的所有车间步骤"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workshop_steps WHERE task_id = ? ORDER BY workshop_id', (task_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_last_completed_step(self, task_id):
        """获取任务最后完成的步骤"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM workshop_steps 
            WHERE task_id = ? AND status = 'completed'
            ORDER BY workshop_id DESC LIMIT 1
        ''', (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # ========== 任务参数管理 ==========
    def set_task_parameter(self, task_id, key_name, value):
        """设置任务参数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 判断值类型
        value_type = 'string'
        string_value = None
        int_value = None
        bool_value = None
        json_value = None
        
        if isinstance(value, bool):
            value_type = 'bool'
            bool_value = 1 if value else 0
        elif isinstance(value, int):
            value_type = 'int'
            int_value = value
        elif isinstance(value, (dict, list)):
            value_type = 'json'
            json_value = json.dumps(value, ensure_ascii=False)
        else:
            string_value = str(value)
        
        cursor.execute('''
            INSERT OR REPLACE INTO task_parameters 
            (task_id, key_name, value_type, string_value, int_value, bool_value, json_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, key_name, value_type, string_value, int_value, bool_value, json_value))
        
        conn.commit()
        conn.close()
    
    def get_task_parameter(self, task_id, key_name):
        """获取任务参数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM task_parameters WHERE task_id = ? AND key_name = ?', (task_id, key_name))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        row = dict(row)
        if row['value_type'] == 'string':
            return row['string_value']
        elif row['value_type'] == 'int':
            return row['int_value']
        elif row['value_type'] == 'bool':
            return bool(row['bool_value'])
        elif row['value_type'] == 'json':
            return json.loads(row['json_value']) if row['json_value'] else None
        return None
    
    def get_all_task_parameters(self, task_id):
        """获取任务所有参数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM task_parameters WHERE task_id = ?', (task_id,))
        rows = cursor.fetchall()
        conn.close()
        
        params = {}
        for row in rows:
            row = dict(row)
            key_name = row['key_name']
            if row['value_type'] == 'string':
                params[key_name] = row['string_value']
            elif row['value_type'] == 'int':
                params[key_name] = row['int_value']
            elif row['value_type'] == 'bool':
                params[key_name] = bool(row['bool_value'])
            elif row['value_type'] == 'json':
                params[key_name] = json.loads(row['json_value']) if row['json_value'] else None
        return params
    
    # ========== RAG检索记录管理 ==========
    def record_rag_retrieval(self, task_id, workshop_id, query, top_k=3, retrieved_count=0, results=None):
        """记录RAG检索"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        results_json = json.dumps(results, ensure_ascii=False) if results else None
        
        cursor.execute('''
            INSERT INTO rag_retrievals (task_id, workshop_id, query, top_k, retrieved_count, results_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_id, workshop_id, query, top_k, retrieved_count, results_json))
        
        retrieval_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return retrieval_id
    
    def get_rag_retrievals(self, task_id, workshop_id=None):
        """获取RAG检索记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if workshop_id:
            cursor.execute('''
                SELECT * FROM rag_retrievals WHERE task_id = ? AND workshop_id = ? ORDER BY created_at
            ''', (task_id, workshop_id))
        else:
            cursor.execute('SELECT * FROM rag_retrievals WHERE task_id = ? ORDER BY created_at', (task_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        retrievals = []
        for row in rows:
            row_dict = dict(row)
            if row_dict['results_json']:
                row_dict['results'] = json.loads(row_dict['results_json'])
            else:
                row_dict['results'] = []
            retrievals.append(row_dict)
        return retrievals
    
    # ========== 章节输出管理 ==========
    def save_chapter_output(self, task_id, chapter_title, content, version=1, is_final=False):
        """保存章节输出"""
        word_count = len(content)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chapter_outputs (task_id, chapter_title, content, word_count, version, is_final)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_id, chapter_title, content, word_count, version, 1 if is_final else 0))
        
        output_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return output_id
    
    def get_chapter_outputs(self, task_id):
        """获取任务的章节输出"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chapter_outputs WHERE task_id = ? ORDER BY version DESC', (task_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_final_chapter_output(self, task_id):
        """获取最终章节输出"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chapter_outputs 
            WHERE task_id = ? AND is_final = 1 ORDER BY created_at DESC LIMIT 1
        ''', (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # ========== 断点续传功能 ==========
    def get_resumable_task(self, project_name, chapter_num):
        """获取可恢复的任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM workshop_tasks 
            WHERE project_name = ? AND chapter_num = ? AND status IN ('pending', 'paused', 'failed')
            ORDER BY created_at DESC LIMIT 1
        ''', (project_name, chapter_num))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_task_progress(self, task_id):
        """获取任务执行进度"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        steps = self.get_workshop_steps(task_id)
        completed_steps = [s for s in steps if s['status'] == 'completed']
        last_step = self.get_last_completed_step(task_id)
        
        return {
            'task': task,
            'total_steps': 5,
            'completed_steps': len(completed_steps),
            'last_completed_workshop': last_step['workshop_id'] if last_step else -1,
            'steps': steps
        }
    
    # ========== 统计信息 ==========
    def get_workshop_stats(self):
        """获取车间统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM workshop_tasks')
        stats['total_tasks'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT status, COUNT(*) FROM workshop_tasks GROUP BY status')
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute('''
            SELECT workshop_name, AVG(duration_seconds), AVG(tokens_used), COUNT(*)
            FROM workshop_steps 
            WHERE status = 'completed'
            GROUP BY workshop_name
        ''')
        stats['workshop_stats'] = {
            row[0]: {
                'avg_duration': row[1],
                'avg_tokens': row[2],
                'count': row[3]
            }
            for row in cursor.fetchall()
        }
        
        conn.close()
        return stats


def main():
    """测试数据库"""
    db = WorkshopDBManager()
    
    print("="*60)
    print(u"盘古AI车间执行记录数据库")
    print("="*60)
    
    stats = db.get_workshop_stats()
    print(u"\n统计信息:")
    print(u"  总任务数: %d" % stats.get('total_tasks', 0))
    print(u"  按状态: %s" % stats.get('by_status', {}))
    
    print(u"\n数据库初始化完成！")
    print(u"数据库位置: %s" % db.db_path)


if __name__ == '__main__':
    main()

