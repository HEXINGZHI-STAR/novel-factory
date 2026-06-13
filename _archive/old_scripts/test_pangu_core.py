#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 pangu_core 核心包"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 测试1: 导入核心包
print('[1] 导入 pangu_core')
from pangu_core import Config, get_config, AIClient, call_ai, clean_ai_output
from pangu_core import DatabaseManager, get_db, KnowledgeInjector, SentenceParams, build_system_prompt
print('  OK: 所有公共API导入成功')

# 测试2: 配置
print('\n[2] 配置管理')
cfg = get_config()
print(f'  base_dir: {cfg.base_dir}')
print(f'  model: {cfg.model}')

# 测试3: 句式参数（唯一真值来源）
print('\n[3] 句式参数 - 唯一真值来源')
from pangu_core.prompts import GENRE_PARAMS, MODE_TO_GENRE, get_params_for_mode
print(f'  题材数: {len(GENRE_PARAMS)}')
print(f'  模式映射数: {len(MODE_TO_GENRE)}')

for mode in ['general', 'urban_power', 'rule_mystery', 'xianxia', 'military', 'fantasy']:
    params = get_params_for_mode(mode)
    print(f'  mode={mode:15s} -> mu_L={params.mu_L}, p_long={params.p_long}')

# 测试4: 知识注入
print('\n[4] 知识注入')
for stage_id in range(5):
    msg = build_system_prompt(stage_id, 'xianxia', 'qimao')
    has_sentence = 'mu_L' in msg
    has_ai_ban = 'AI' in msg and '禁令' in msg
    label = "YES" if has_sentence else "no"
    label2 = "YES" if has_ai_ban else "no"
    print(f'  W{stage_id}: {len(msg):>5}字, 句式参数={label}, AI禁令={label2}')

# 测试5: AI输出清理
print('\n[5] AI输出清理')
test = '好的，以下是我为您创作的小说：\n\n正文开始\n\n他缓缓地睁开眼睛。\n\n希望您喜欢！'
cleaned = clean_ai_output(test)
print(f'  原文: {repr(test[:50])}...')
print(f'  清理: {repr(cleaned[:50])}...')

# 测试6: 数据库
print('\n[6] 数据库管理')
db = get_db()
result = db.query_one('SELECT count(*) as cnt FROM sqlite_master WHERE type="table"')
print(f'  数据库表数: {result["cnt"] if result else 0}')

# 测试7: 验证无双重定义bug
print('\n[7] 验证 MODE_TO_GENRE 无双重定义')
import pangu_core.prompts as p
assert p.MODE_TO_GENRE['general'] == '通用', f'BUG: general映射到了{p.MODE_TO_GENRE["general"]}'
print(f'  OK: general -> {p.MODE_TO_GENRE["general"]}')

print('\n所有测试通过!')
