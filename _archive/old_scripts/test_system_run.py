#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI系统 - 自动化运行测试
测试核心功能链路，不需要交互式输入
"""
import os
import sys
import json
import time
from pathlib import Path

# 设置项目根目录
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR / 'knowledge'))
sys.path.insert(0, str(BASE_DIR / 'backend'))

# 清除 __pycache__ 毒化
import shutil
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        try:
            shutil.rmtree(os.path.join(root, '__pycache__'))
        except:
            pass

print("=" * 60)
print("  盘古AI系统 - 自动化运行测试")
print("=" * 60)

# ========== 测试1: 模块导入 ==========
print("\n[测试1] 模块导入检测")
print("-" * 40)

modules_ok = 0
modules_fail = 0

# 核心模块
core_modules = {
    'pangu_core.config': 'Config',
    'pangu_core.ai_client': 'AIClient',
    'pangu_core.db': 'DatabaseManager',
    'pangu_core.prompts': 'KnowledgeInjector',
    'pangu_core.write_gates': 'run_write_gate',
    'pangu_core.story_contracts': 'build_and_inject_chapter_contract',
    'pangu_core.memory_layers': 'PanguMemoryOrchestrator',
    'pangu_core.rag_hybrid': 'PanguHybridRAG',
    'pangu_core.beat_sheet': 'build_and_inject_beat_sheet',
    'pangu_core.projection': 'run_projections',
}

for mod_name, cls_name in core_modules.items():
    try:
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name, None)
        if cls:
            print(f"  ✓ {mod_name}.{cls_name}")
            modules_ok += 1
        else:
            print(f"  ✗ {mod_name}.{cls_name} — 类不存在")
            modules_fail += 1
    except Exception as e:
        print(f"  ✗ {mod_name} — {str(e)[:60]}")
        modules_fail += 1

# knowledge模块
k_modules = {
    'creative_engine': 'CreativeEngine',
    'style_fingerprint': 'StyleDatabase',
    'quality_10d': 'full_10d_score',
    'pangu_math_core': 'PanguMathEngine',
}

for mod_name, cls_name in k_modules.items():
    try:
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name, None)
        if cls:
            print(f"  ✓ {mod_name}.{cls_name}")
            modules_ok += 1
        else:
            print(f"  ✗ {mod_name}.{cls_name} — 类不存在")
            modules_fail += 1
    except Exception as e:
        print(f"  ✗ {mod_name} — {str(e)[:60]}")
        modules_fail += 1

print(f"\n  结果: {modules_ok}通过 / {modules_fail}失败")

# ========== 测试2: 数据库连通性 ==========
print("\n[测试2] 数据库连通性检测")
print("-" * 40)

import sqlite3

for db_path in ['knowledge/creative_engine.db', 'knowledge/novel_reference.db']:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        total_rows = 0
        for t in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
                count = cursor.fetchone()[0]
                total_rows += count
                if count > 0:
                    print(f"  {t}: {count:,} 行")
            except:
                pass
        print(f"  → {db_path}: {len(tables)}表, 共{total_rows:,}行")
        conn.close()
    else:
        print(f"  ✗ {db_path} 不存在!")

# ========== 测试3: 项目列表 ==========
print("\n[测试3] 现有项目")
print("-" * 40)

projects_dir = BASE_DIR / 'projects'
if projects_dir.exists():
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir():
            state_file = p / 'state.json'
            text_dir = p / '正文'
            chapters = []
            if text_dir.exists():
                chapters = [f for f in os.listdir(text_dir) if f.endswith('.txt')]
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text(encoding='utf-8'))
                    info = state.get('project_info', {})
                    title = info.get('title', p.name)
                    progress = state.get('progress', {})
                    cur = progress.get('current_chapter', 0)
                    mode = info.get('mode', '?')
                    # 检查高级功能状态
                    has_lorebook = bool(state.get('lorebook', []))
                    has_foreshadow = bool(state.get('foreshadowing', {}).get('active_threads', []))
                    has_characters = bool(state.get('characters', {}).get('key_characters', []))
                    has_beat = bool(state.get('beat_sheet', []))
                    features = []
                    if has_lorebook: features.append('Lorebook')
                    if has_foreshadow: features.append('伏笔')
                    if has_characters: features.append('角色')
                    if has_beat: features.append('Beat')
                    feat_str = ' '.join(features) if features else '空追踪'
                    print(f"  {title} | {cur}章 | {mode} | {feat_str} | {len(chapters)}文件")
                except:
                    print(f"  {p.name} | state.json解析失败")
            else:
                print(f"  {p.name} | 无state.json | {len(chapters)}文件")

# ========== 测试4: API连通性 ==========
print("\n[测试4] API连通性测试")
print("-" * 40)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

api_key = os.environ.get('DEEPSEEK_API_KEY', '')
if api_key:
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    try:
        import requests
        resp = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': '回复"盘古系统连接正常"六个字'}],
                'max_tokens': 20,
                'temperature': 0.1
            },
            timeout=15
        )
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            print(f"  API响应: {content.strip()}")
            print(f"  状态: ✓ 连接正常")
        else:
            print(f"  状态: ✗ HTTP {resp.status_code}")
            print(f"  响应: {resp.text[:100]}")
    except Exception as e:
        print(f"  状态: ✗ 连接失败 — {str(e)[:80]}")
else:
    print("  状态: ✗ 未配置DEEPSEEK_API_KEY")

# ========== 测试5: Prompt注入链路 ==========
print("\n[测试5] Prompt注入链路测试")
print("-" * 40)

try:
    # 模拟build_smart_prompt的各层注入
    from pangu_core.prompts import KnowledgeInjector, build_system_prompt, GENRE_PARAMS

    # 找一个已有项目来测试
    test_project = None
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir() and (p / 'state.json').exists():
            test_project = p
            break

    if test_project:
        state = json.loads((test_project / 'state.json').read_text(encoding='utf-8'))
        info = state.get('project_info', {})
        mode = info.get('mode', '都市_power')
        title = info.get('title', test_project.name)
        print(f"  测试项目: {title} (模式: {mode})")

        # 检查各层注入能力
        layers = []
        # L1: 通用写作规则 (always)
        layers.append(('L1-通用规则', True))
        # L2: 模式深度注入
        try:
            mode_file = BASE_DIR / 'modes' / f'{mode}.json'
            layers.append(('L2-模式深度注入', mode_file.exists()))
        except:
            layers.append(('L2-模式深度注入', False))
        # L3: 题材模板
        try:
            from pangu_core.prompts import get_genre_for_mode
            genre = get_genre_for_mode(mode)
            layers.append(('L3-题材模板', bool(genre)))
        except:
            layers.append(('L3-题材模板', False))
        # L4: 句式参数
        try:
            from pangu_core.prompts import get_params_for_mode
            params = get_params_for_mode(mode)
            layers.append(('L4-句式参数', bool(params)))
        except:
            layers.append(('L4-句式参数', False))
        # L5: 情绪锚点
        try:
            from pangu_optimized import _extract_emotion_anchors
            anchors = _extract_emotion_anchors(state)
            layers.append(('L5-情绪锚点', bool(anchors)))
        except:
            layers.append(('L5-情绪锚点', 'N/A'))
        # L6: 风格指纹
        try:
            from style_fingerprint import StyleDatabase
            sdb = StyleDatabase()
            layers.append(('L6-风格指纹', True))
        except:
            layers.append(('L6-风格指纹', False))
        # L7: 知识检索
        layers.append(('L7-知识检索', True))  # always available via DB
        # L8: Lorebook
        lorebook = state.get('lorebook', [])
        layers.append(('L8-Lorebook', len(lorebook) > 0))
        # L9: De-AI规则
        try:
            from pangu_optimized import _load_de_ai_rules
            rules = _load_de_ai_rules()
            layers.append(('L9-De-AI', bool(rules)))
        except:
            layers.append(('L9-De-AI', 'N/A'))
        # L10: Story Contract (workflow path only)
        try:
            from pangu_core.story_contracts import build_and_inject_chapter_contract
            layers.append(('L10-Story Contract', True))
        except:
            layers.append(('L10-Story Contract', False))
        # L11: Memory Pack (workflow path only)
        try:
            from pangu_core.memory_layers import PanguMemoryOrchestrator
            layers.append(('L11-Memory Pack', True))
        except:
            layers.append(('L11-Memory Pack', False))
        # L12: Beat Sheet (workflow path only)
        try:
            from pangu_core.beat_sheet import build_and_inject_beat_sheet
            layers.append(('L12-Beat Sheet', True))
        except:
            layers.append(('L12-Beat Sheet', False))

        for layer_name, status in layers:
            if status is True:
                print(f"  ✓ {layer_name}")
            elif status is False:
                print(f"  ✗ {layer_name} — 未就绪")
            else:
                print(f"  ? {layer_name} — {status}")
    else:
        print("  无项目可测试")

except Exception as e:
    print(f"  测试中断: {str(e)[:100]}")
    import traceback
    traceback.print_exc()

# ========== 测试6: 写作链路端到端 ==========
print("\n[测试6] 端到端写作链路测试")
print("-" * 40)

try:
    # 找一个有数据的项目
    test_project = None
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir() and (p / 'state.json').exists():
            state = json.loads((p / 'state.json').read_text(encoding='utf-8'))
            if state.get('progress', {}).get('current_chapter', 0) > 0:
                test_project = p
                break

    if test_project and api_key:
        from pangu_optimized import load_config, CONFIG as PANGU_CONFIG
        # load_config() has already been called at import time

        state = json.loads((test_project / 'state.json').read_text(encoding='utf-8'))
        info = state.get('project_info', {})
        title = info.get('title', test_project.name)
        cur_ch = state.get('progress', {}).get('current_chapter', 0) + 1
        mode = info.get('mode', '都市_power')

        print(f"  测试项目: {title} (第{cur_ch}章, 模式: {mode})")
        print(f"  正在构建Prompt...")

        from pangu_optimized import build_smart_prompt
        system_msg, user_msg = build_smart_prompt(
            project_dir=str(test_project),
            chapter_num=cur_ch,
            chapter_task="测试章节：主角在清晨醒来，回忆昨夜梦境",
            mode=mode,
        )

        print(f"  System Prompt: {len(system_msg)} 字符")
        print(f"  User Prompt: {len(user_msg)} 字符")

        # 检查注入内容
        injection_checks = {
            '通用规则': '写作' in system_msg,
            '句式参数': 'CV_L' in system_msg or 'mu_L' in system_msg,
            '模式注入': mode.split('_')[0] in system_msg if mode else False,
            'De-AI规则': 'De-AI' in system_msg or 'AI味' in system_msg,
            '题材模板': '题材' in system_msg or 'genre' in system_msg.lower(),
        }
        for check_name, result in injection_checks.items():
            print(f"    {'✓' if result else '✗'} {check_name}")

        # 调用API生成（短文本测试）
        print(f"\n  调用DeepSeek API生成测试文本...")
        import requests as req

        resp = req.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': PANGU_CONFIG.get('model', 'deepseek-chat'),
                'messages': [
                    {'role': 'system', 'content': system_msg[:3000]},  # 截断避免超长
                    {'role': 'user', 'content': user_msg[:2000]}
                ],
                'max_tokens': 500,
                'temperature': 0.7
            },
            timeout=30
        )

        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            char_count = len(content.replace('\n', '').replace(' ', ''))
            print(f"  ✓ 生成成功！{char_count}字")
            print(f"\n  --- 生成内容预览 ---")
            # 显示前200字
            preview = content[:200].replace('\n', '\n  ')
            print(f"  {preview}...")
        else:
            print(f"  ✗ API返回错误: HTTP {resp.status_code}")
            print(f"  {resp.text[:200]}")
    else:
        if not test_project:
            print("  跳过: 没有已写章节的项目")
        if not api_key:
            print("  跳过: 未配置API Key")

except Exception as e:
    print(f"  测试中断: {str(e)[:100]}")
    import traceback
    traceback.print_exc()

# ========== 测试7: Workflow Engine 5车间 ==========
print("\n[测试7] 五车间流水线检测")
print("-" * 40)

try:
    from workflow_engine import WorkflowEngine, HAS_WRITE_GATES, HAS_BEAT_SHEET, HAS_REFERENCE_ENGINE, HAS_MODE_INJECTOR, HAS_MEMORY_BANK

    print(f"  Write Gates: {'✓' if HAS_WRITE_GATES else '✗'}")
    print(f"  Beat Sheet: {'✓' if HAS_BEAT_SHEET else '✗'}")
    print(f"  Reference Engine: {'✓' if HAS_REFERENCE_ENGINE else '✗'}")
    print(f"  Mode Injector: {'✓' if HAS_MODE_INJECTOR else '✗'}")
    print(f"  Memory Bank: {'✓' if HAS_MEMORY_BANK else '✗'}")

    # 检查是否有5个车间
    import inspect
    engine_methods = [m for m in dir(WorkflowEngine) if m.startswith('_stage_') or m.startswith('run')]
    print(f"  WorkflowEngine方法: {', '.join(engine_methods[:10])}")

except Exception as e:
    print(f"  ✗ workflow_engine导入失败: {str(e)[:80]}")

# ========== 汇总 ==========
print("\n" + "=" * 60)
print("  测试完成!")
print("=" * 60)
